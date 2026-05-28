"""
FastAPI 入口：客服系统 /chat 端点，支持多轮对话记忆 + Mem0 用户画像。
"""
import uuid
import time
import os
import json
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.config import settings
from backend.middleware.auth import auth_middleware
from backend.middleware.rate_limit import rate_limit_middleware

from backend.graph.main_graph import main_graph
from backend.graph.state import AgentState
from backend.memory.session_store import (
    create_session,
    load_history,
    save_message,
    ensure_session,
)
from backend.memory.mem0_store import search_user_memory, save_user_memory
from backend.tools.search_knowledge import search_knowledge
from backend.tools.response_cache import cache_stats, get_cached, set_cache
from backend.tools.feedback_store import save_feedback, get_feedback_stats as _feedback_stats
from backend.tools.intent_stats import record_intent, get_intent_stats, get_intent_trend
from backend.tools.cost_tracker import get_cost_summary, get_cost_trend
from backend.tools.knowledge_manager import list_entries, add_entry, update_entry, delete_entry, rebuild_index
from backend.logger import logger


app = FastAPI(title="智能客服系统", version="1.2.0")

# 启动时预加载本地意图分类模型
@app.on_event("startup")
async def warmup_model():
    try:
        from backend.inference.intent_classifier import warmup
        warmup()
        logger.info("本地意图分类模型已加载")
    except Exception as e:
        logger.warning("本地模型加载失败，将使用 DeepSeek fallback: {}", str(e))

# 中间件（先认证再限流）
app.middleware("http")(auth_middleware)
app.middleware("http")(rate_limit_middleware)


class ChatRequest(BaseModel):
    """聊天请求体"""
    message: str
    session_id: Optional[str] = None  # 不传则创建新会话
    user_id: Optional[str] = None     # 主系统传来的用户标识


class FeedbackRequest(BaseModel):
    """反馈请求体"""
    session_id: str
    reply_index: int
    rating: str  # "up" 或 "down"


class KnowledgeEntry(BaseModel):
    """知识条目"""
    title: str
    content: str
    source: str = "faq"


class KnowledgeUpdate(BaseModel):
    """知识条目更新"""
    title: str = ""
    content: str = ""


class ChatResponse(BaseModel):
    """聊天响应体"""
    reply: str
    session_id: str
    reply_index: int = 0  # 用于反馈追踪


@app.get("/health")
def health_check():
    """健康检查端点"""
    return {"status": "ok", "env": settings.APP_ENV}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    客服对话端点，支持多轮对话记忆 + Mem0 用户画像。
    - 传 session_id 继续历史对话
    - 不传则创建新会话
    """
    # 获取或创建会话，优先用主系统传来的 user_id 做 Mem0 标识
    session_id = request.session_id or create_session()
    ensure_session(session_id)

    # 主系统传来的用户标识（用于跨会话记忆）
    mem0_user_id = request.user_id or session_id
    if request.user_id:
        logger.bind(component="main", user_id=request.user_id, session_id=session_id).info(f"主系统用户: {request.user_id} → session: {session_id}")

    # 保存用户消息
    save_message(session_id, "user", request.message)

    # 加载历史消息
    history = load_history(session_id, limit=20)

    # 对话截断：超过10轮自动摘要前文
    if len(history) >= 20:
        try:
            old_part = history[:16]  # 前8轮
            recent_part = history[16:]  # 后2轮
            old_text = "\n".join(
                f"{'用户' if m['role']=='user' else '客服'}: {m['content'][:100]}"
                for m in old_part
            )
            from openai import OpenAI
            client = OpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL)
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": f"用一句话总结以下客服对话要点：\n{old_text}"}],
                max_tokens=80,
            )
            summary = resp.choices[0].message.content
            history = [{"role": "system", "content": f"[对话摘要] {summary}"}] + recent_part
            logger.bind(component="main", session_id=session_id).info("已摘要前8轮对话")
        except Exception as e:
            logger.bind(component="main", session_id=session_id).warning(f"摘要失败: {e}")

    # Mem0 检索用户记忆（用主系统 userId，跨会话生效）
    memory_context = search_user_memory(mem0_user_id, request.message)

    # 缓存检查：同意图+相似问题命中则直接返回
    # 用简单关键词判断意图（避免调 LLM）
    msg_lower = request.message.lower()
    if any(kw in msg_lower for kw in ["退货", "退款", "几天", "保修", "物流", "快递", "客服", "上班", "电话"]):
        intent_guess = "faq"
    elif any(kw in msg_lower for kw in ["我要退", "帮我退", "退了吧", "退款"]):
        intent_guess = "return"
    elif any(kw in msg_lower for kw in ["投诉", "太差", "态度"]):
        intent_guess = "complaint"
    else:
        intent_guess = "general"

    cached = get_cached(intent_guess, request.message)
    if cached:
        reply_index = len([m for m in history if m["role"] == "assistant"]) + 1
        logger.bind(component="main", intent=intent_guess).info(f"缓存命中 intent={intent_guess}")
        save_message(session_id, "assistant", cached)
        return ChatResponse(reply=cached, session_id=session_id, reply_index=reply_index)

    # 构建初始状态（含历史对话 + 用户记忆）
    initial_state: AgentState = {
        "messages": history,
        "intent": "",
        "order_info": {},
        "knowledge_results": [],
        "ticket_id": "",
        "final_reply": "",
        "memory_context": memory_context,
    }

    # 调用 LangGraph
    try:
        result = main_graph.invoke(initial_state)
    except Exception:
        logger.opt(exception=True).error("主图调用失败")
        return {"reply": "抱歉，系统暂时繁忙，请稍后再试或联系人工客服。", "session_id": session_id, "reply_index": 0}

    # 提取回复并保存
    reply = result.get("final_reply", "抱歉，系统处理异常，请稍后重试。")
    intent = result.get("intent", "")
    record_intent(session_id, intent, request.message)  # 记录意图分布

    # 人工兜底检测：连续2轮同意图+用户仍不满 → 升级
    should_escalate = False
    if len(history) >= 4:
        user_rounds = [m for m in history if m["role"] == "user"]
        frustration_kw = ["还是", "不行", "不对", "没用", "解决", "再问", "老是", "怎么回事", "为什么"]
        # 最近2轮用户消息都含不满关键词
        recent_user = user_rounds[-2:]
        if len(recent_user) >= 2:
            frustrated_count = sum(
                1 for m in recent_user
                if any(kw in m["content"] for kw in frustration_kw)
            )
            should_escalate = frustrated_count >= 2

    if should_escalate:
        ticket_id = f"TKT-ESC-{int(time.time())}"
        reply = (
            f"我已经把您的问题升级给人工客服了，他们会优先处理 🙏\n"
            f"升级工单号：{ticket_id}\n"
            f"预计30分钟内与您联系。"
        )
        logger.bind(component="main", intent=intent, ticket_id=ticket_id).warning(f"升级到人工")

    save_message(session_id, "assistant", reply)

    # 计算回复序号
    reply_index = len([m for m in history if m["role"] == "assistant"]) + 1
    if should_escalate:
        reply_index += 1  # 升级回复也算一轮

    # Mem0 保存用户记忆（用最近 2 轮对话提取）
    recent = history[-4:] + [
        {"role": "user", "content": request.message},
        {"role": "assistant", "content": reply},
    ]
    save_user_memory(mem0_user_id, recent)

    return ChatResponse(reply=reply, session_id=session_id, reply_index=reply_index)


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    流式客服对话端点（SSE），逐 token 推送回复。
    前端通过 EventSource 或 fetch + ReadableStream 接收。
    """
    session_id = request.session_id or create_session()
    ensure_session(session_id)
    mem0_user_id = request.user_id or session_id

    if request.user_id:
        logger.bind(component="main", user_id=request.user_id, session_id=session_id).info(
            f"流式 - 主系统用户: {request.user_id} → session: {session_id}"
        )

    save_message(session_id, "user", request.message)
    history = load_history(session_id, limit=20)

    # ── 历史截断（同 /chat） ──
    if len(history) >= 20:
        try:
            old_part = history[:16]
            recent_part = history[16:]
            old_text = "\n".join(
                f"{'用户' if m['role']=='user' else '客服'}: {m['content'][:100]}"
                for m in old_part
            )
            from openai import OpenAI
            client = OpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL)
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": f"用一句话总结以下客服对话要点：\n{old_text}"}],
                max_tokens=80,
            )
            summary = resp.choices[0].message.content
            history = [{"role": "system", "content": f"[对话摘要] {summary}"}] + recent_part
        except Exception as e:
            logger.bind(component="main", session_id=session_id).warning(f"流式摘要失败: {e}")

    memory_context = search_user_memory(mem0_user_id, request.message)

    # ── 意图猜测（同 /chat） ──
    msg_lower = request.message.lower()
    if any(kw in msg_lower for kw in ["退货", "退款", "几天", "保修", "物流", "快递", "客服", "上班", "电话"]):
        intent_guess = "faq"
    elif any(kw in msg_lower for kw in ["我要退", "帮我退", "退了吧"]):
        intent_guess = "return"
    elif any(kw in msg_lower for kw in ["投诉", "太差", "态度"]):
        intent_guess = "complaint"
    else:
        intent_guess = "general"

    # ── 缓存命中：直接返回，不走 Graph ──
    cached = get_cached(intent_guess, request.message)
    if cached:
        reply_index = len([m for m in history if m["role"] == "assistant"]) + 1
        save_message(session_id, "assistant", cached)
        logger.bind(component="main", intent=intent_guess).info(f"流式缓存命中 intent={intent_guess}")

        async def cached_stream():
            yield f"data: {json.dumps({'type': 'token', 'content': cached}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'reply': cached, 'session_id': session_id, 'reply_index': reply_index}, ensure_ascii=False)}\n\n"

        return StreamingResponse(cached_stream(), media_type="text/event-stream")

    initial_state: AgentState = {
        "messages": history,
        "intent": "",
        "order_info": {},
        "knowledge_results": [],
        "ticket_id": "",
        "final_reply": "",
        "memory_context": memory_context,
    }

    async def event_generator():
        collected_reply = ""

        try:
            # 先发一个"分析中"进度
            yield f"data: {json.dumps({'type': 'status', 'content': '正在分析您的问题...'}, ensure_ascii=False)}\n\n"

            # 在后台线程运行同步 graph（astream_events 在 0.2.60 有兼容问题）
            import asyncio
            result = await asyncio.to_thread(main_graph.invoke, initial_state)
            collected_reply = result.get("final_reply", "")

            final_reply = collected_reply.strip() or "抱歉，系统暂时繁忙，请稍后再试或联系人工客服。"

            # ── 人工兜底检测 ──
            should_escalate = False
            if len(history) >= 4:
                user_rounds = [m for m in history if m["role"] == "user"]
                frustration_kw = ["还是", "不行", "不对", "没用", "解决", "再问", "老是", "怎么回事", "为什么"]
                recent_user = user_rounds[-2:]
                if len(recent_user) >= 2:
                    frustrated_count = sum(
                        1 for m in recent_user
                        if any(kw in m["content"] for kw in frustration_kw)
                    )
                    should_escalate = frustrated_count >= 2

            if should_escalate:
                ticket_id = f"TKT-ESC-{int(time.time())}"
                final_reply = (
                    f"我已经把您的问题升级给人工客服了，他们会优先处理 🙏\n"
                    f"升级工单号：{ticket_id}\n"
                    f"预计30分钟内与您联系。"
                )
                logger.bind(component="main", intent=intent_guess, ticket_id=ticket_id).warning(f"流式升级到人工")

            record_intent(session_id, intent_guess, request.message)
            save_message(session_id, "assistant", final_reply)

            reply_index = len([m for m in history if m["role"] == "assistant"]) + 1
            if should_escalate:
                reply_index += 1

            # Mem0 保存
            recent = history[-4:] + [
                {"role": "user", "content": request.message},
                {"role": "assistant", "content": final_reply},
            ]
            save_user_memory(mem0_user_id, recent)

            # 推送完整回复（模拟 token 流 → 实际是整段回复）
            yield f"data: {json.dumps({'type': 'token', 'content': final_reply}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'reply': final_reply, 'session_id': session_id, 'reply_index': reply_index}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.opt(exception=True).bind(component="main").error(f"流式异常: {e}")
            error_msg = "抱歉，系统暂时繁忙，请稍后再试或联系人工客服。"
            yield f"data: {json.dumps({'type': 'token', 'content': error_msg}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'reply': error_msg, 'session_id': session_id, 'reply_index': 0}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/sessions/{session_id}")
def get_session_history(session_id: str):
    """查看会话历史"""
    history = load_history(session_id, limit=50)
    memory = search_user_memory(session_id, "")
    return {
        "session_id": session_id,
        "messages": history,
        "count": len(history),
        "memory": memory,
    }


@app.get("/eval/search")
def eval_search(q: str, top_k: int = 3):
    """评测用：直接返回向量检索结果（不做 LLM 回答）。"""
    results = search_knowledge(q, top_k=top_k)
    return {
        "query": q,
        "results": [
            {"content": r["content"], "score": r["score"], "source": r["source"]}
            for r in results
        ],
    }


@app.get("/cache/stats")
def get_cache_stats():
    """缓存统计。"""
    return cache_stats()


@app.get("/feedback/stats")
def get_feedback_stats():
    """反馈统计。"""
    return _feedback_stats()


@app.get("/stats/intents")
def intent_distribution(days: int = 7):
    """意图分布统计。"""
    return get_intent_stats(days=days)


@app.get("/stats/intents/trend")
def intent_trend(days: int = 7):
    """意图每日趋势。"""
    return get_intent_trend(days=days)


@app.get("/cost/summary")
def cost_summary(days: int = 7):
    """LLM 成本汇总。"""
    return get_cost_summary(days=days)


@app.get("/cost/trend")
def cost_trend(days: int = 7):
    """LLM 成本每日趋势。"""
    return get_cost_trend(days=days)


@app.post("/feedback")
def submit_feedback(req: FeedbackRequest):
    """提交反馈评价。"""
    return save_feedback(req.session_id, req.reply_index, req.rating)


# ── 知识库管理 ────────────────────────────────────

@app.get("/knowledge")
def list_knowledge():
    """列出所有知识条目。"""
    return list_entries()


@app.post("/knowledge")
def create_knowledge(entry: KnowledgeEntry):
    """新增知识条目。"""
    return add_entry(entry.title, entry.content, entry.source)


@app.put("/knowledge/{point_id}")
def update_knowledge(point_id: int, update: KnowledgeUpdate):
    """编辑知识条目。"""
    return update_entry(point_id, title=update.title, content=update.content)


@app.delete("/knowledge/{point_id}")
def delete_knowledge(point_id: int):
    """删除知识条目。"""
    return delete_entry(point_id)


@app.post("/knowledge/reindex")
def reindex_knowledge():
    """重建索引（从 md 文件重新加载）。"""
    return rebuild_index()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
