# 智能客服系统 — 技术点清单

> 项目路径：`C:\Ccode\smart-cs-agent`  
> 后端：FastAPI + LangGraph + DeepSeek + Qdrant  
> 前端：React + Vite

---

## 架构总览

```
用户 → POST /chat → parse_input → dispatcher → [faq/return/complaint/general] → coordinator → 回复
                                                     ↑
                                               Mem0 用户记忆
                                               Qdrant 知识检索
                                               LangSmith 全链路追踪
```

---

## 一、LangGraph 图编排

**作用：** 多 Agent 协作的流程引擎，管理节点执行顺序和条件路由。

**实现文件：** `backend/graph/main_graph.py`

```python
from langgraph.graph import StateGraph, END

workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("parse_input", parse_input_node)
workflow.add_node("dispatcher_agent", dispatcher_agent_node)
workflow.add_node("faq_agent", faq_graph)         # 子 Graph
workflow.add_node("return_agent", return_graph)   # 子 Graph
workflow.add_node("complaint_agent", complaint_graph)
workflow.add_node("general_agent", general_graph)
workflow.add_node("coordinator", coordinator_node)

# 条件路由：根据意图分发到不同子 Agent
workflow.add_conditional_edges(
    "check_cache", cache_router,
    {"faq_agent": "faq_agent", "return_agent": "return_agent", ...}
)
```

**流程链：** `parse_input → dispatcher → check_cache → [命中→coordinator] / [未命中→router→子Agent] → coordinator → save_cache → END`

---

## 二、Agent 状态定义（TypedDict）

**作用：** 所有节点间共享的结构化状态字典（不可变，每个节点返回新 state）。

**实现文件：** `backend/graph/state.py`

```python
class AgentState(TypedDict):
    messages: list[dict]       # 对话历史
    intent: str                # faq/return/complaint/general
    order_info: dict           # 订单信息
    knowledge_results: list[dict]  # RAG 检索结果
    ticket_id: str             # 工单号
    final_reply: str           # 最终回复
    memory_context: str        # Mem0 用户画像
```

---

## 三、多 Agent 意图路由

**作用：** 用 LLM 对用户消息意图分类，路由到对应子 Agent。

**实现文件：** `backend/graph/main_graph.py` → `dispatcher_agent_node()`

**分类 Prompt：**
```
return  → 用户明确要求退货、换货、退款
faq     → 询问政策规则、操作方法、物流时效
complaint → 投诉商品质量、服务态度、物流延误
general → 问候、闲聊、无法归类
```

**容错机制：** JSON 解析失败 → 正则兜底 → 默认 `general`

```python
try:
    result = json.loads(response_content)
    intent = result.get("intent", "general")
except json.JSONDecodeError:
    match = re.search(r'"intent"\s*:\s*"(faq|return|complaint|general)"', response_content)
    intent = match.group(1) if match else "general"
```

---

## 四、子 Agent 图（独立 Subgraph）

### 4.1 FAQ Agent — 知识库检索

**文件：** `backend/graph/agents/faq_agent.py`

**流程：** 检索知识库 → LLM 结合检索结果生成回复

```python
def search_and_reply_node(state):
    knowledge_results = search_knowledge(user_msg, top_k=3)
    # 注入知识库内容到 Prompt
    reply = safe_llm_invoke(faq_llm, [
        {"role": "system", "content": "根据知识库提供的内容回答..."},
        {"role": "user", "content": f"参考内容:\n{knowledge_text}\n\n问题:{user_msg}"}
    ], fallback=FALLBACK_GENERAL)
```

### 4.2 Return Agent — 退货处理

**文件：** `backend/graph/agents/return_agent.py`

**流程：** 验证订单 → 检索退换政策 → 生成工单 → 客服回复

```python
return_builder.add_node("check_order", check_order_node)
return_builder.add_node("search_policy", search_policy_node)
return_builder.add_node("create_ticket", create_ticket_node)
return_builder.add_node("generate_reply", generate_reply_node)
```

### 4.3 Complaint Agent — 投诉处理

**文件：** `backend/graph/agents/complaint_agent.py`

**流程：** 评估严重等级(low/medium/high) → 生成工单 → 安抚回复

**等级影响回复策略：**
- `low` → 记录反馈，转达给相关部门
- `medium` → 2 小时内电话联系
- `high` → 30 分钟内高级客服经理优先致电

### 4.4 General Agent — 通用兜底

**文件：** `backend/graph/agents/general_agent.py`

**职责：** 处理闲聊、问候、奇葩问题（temperature=0.7，回答更灵活）

---

## 五、RAG 知识检索

**架构：** Qdrant 向量数据库 + 硅基流动 BGE-large-zh-v1.5 Embedding

**实现文件：**
- `backend/tools/vector_store.py` — Qdrant 初始化、Embedding API、检索
- `backend/tools/search_knowledge.py` — 检索封装

```python
# vector_store.py
def vector_search(query: str, top_k: int = 3) -> list[dict]:
    query_vec = _embed([query])[0]                         # 硅基流动 API
    results = client.query_points(
        collection_name="faq_knowledge",
        query=query_vec,
        limit=top_k,
    ).points
    return [{"content": r.payload["content"], "score": r.score} for r in results]
```

**文档分块策略：** 按 `## ` 标题分割，每块 ≤ 500 字符

---

## 六、Embedding（硅基流动）

**模型：** `BAAI/bge-large-zh-v1.5`（1024维，中文语义检索）

**实现：** `backend/tools/vector_store.py` → `_embed()`

```python
resp = httpx.post(
    "https://api.siliconflow.cn/v1/embeddings",
    json={"model": "BAAI/bge-large-zh-v1.5", "input": texts, "encoding_format": "float"},
    headers={"Authorization": f"Bearer {SILICONFLOW_API_KEY}"},
)
embeddings = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
```

---

## 七、Mem0 用户记忆

**作用：** 跨会话用户画像，自动从对话中提取偏好、行为等信息。

**实现文件：** `backend/memory/mem0_store.py`

```python
from mem0 import Memory

memory = Memory.from_config({
    "embedder": {"provider": "openai", "config": {"model": "BAAI/bge-large-zh-v1.5", ...}},
    "vector_store": {"provider": "qdrant", "config": {"embedding_model_dims": 1024}},
    "llm": {"provider": "openai", "config": {"model": "deepseek-chat", ...}},
})

def search_user_memory(user_id, query) -> str:
    results = memory.search(query, filters={"user_id": user_id})
    return "用户记忆：" + "；".join(memories)

def save_user_memory(user_id, messages):
    memory.add(messages, user_id=user_id)
```

---

## 八、LLM 调用安全包装（降级处理）

**作用：** 统一处理超时、API 错误、空返回，确保异常不扩散到 FastAPI。

**实现文件：** `backend/tools/llm_utils.py`

```python
def safe_llm_invoke(llm, messages, fallback, timeout=30) -> str:
    try:
        llm.request_timeout = timeout
        response = llm.invoke(messages)
        content = response.content
        return content if content and content.strip() else fallback
    except Exception as e:
        print(f"[llm_utils] ❌ LLM 调用失败: {e}")
        return fallback

# 预定义 fallback
FALLBACK_GENERAL = "抱歉，我这边暂时有点卡顿😅 请稍后再试..."
FALLBACK_DISPATCHER = '{"intent": "general"}'
```

---

## 九、LLM 配置（DeepSeek）

**文件：** `backend/config.py`

```python
from langchain_openai import ChatOpenAI

# 6 个 LLM 实例，不同温度适配不同场景
dispatcher_llm  = ChatOpenAI(model="deepseek-chat", temperature=0.3, tags=["dispatcher"])
faq_llm         = ChatOpenAI(model="deepseek-chat", temperature=0.5, tags=["faq"])
return_llm      = ChatOpenAI(model="deepseek-chat", temperature=0.3, tags=["return"])
complaint_llm   = ChatOpenAI(model="deepseek-chat", temperature=0.5, tags=["complaint"])
general_llm     = ChatOpenAI(model="deepseek-chat", temperature=0.7, tags=["general"])
coordinator_llm = ChatOpenAI(model="deepseek-chat", temperature=0.5, tags=["coordinator"])
```

**为什么不同 Agent 用不同 temperature：**
| Agent | temperature | 原因 |
|-------|------------|------|
| dispatcher | 0.3 | 意图分类需要稳定 |
| return | 0.3 | 退换流程需严谨 |
| faq | 0.5 | 回复需自然但准确 |
| complaint | 0.5 | 安抚话术需自然 |
| general | 0.7 | 闲聊需灵活多变 |

---

## 十、会话记忆（多轮对话）

**存储：** SQLite (`backend/data/sessions.db`)

**实现文件：** `backend/memory/session_store.py`

```python
def load_history(session_id, limit=20) -> list[dict]:
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE session_id=? ORDER BY id ASC LIMIT ?",
        (session_id, limit)
    ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]

def save_message(session_id, role, content):
    conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)", ...)
```

---

## 十一、生产化增强四件套

### 11.1 同义问题缓存

**文件：** `backend/tools/response_cache.py`

**策略：** API 层拦截（不放进 LangGraph 节点），MD5 精确匹配

```python
def get_cached(intent, question) -> str | None:
    key = hashlib.md5(f"{intent}|{normalize(question)}".encode()).hexdigest()
    row = conn.execute("SELECT answer FROM cache WHERE cache_key=?", (key,)).fetchone()
    return row[0] if row else None
```

### 11.2 人工兜底协议

**文件：** `backend/main.py` → `/chat` 出口逻辑

**触发条件：** history ≥ 4（2轮对话）+ 最近2条用户消息含不满关键词

```python
frustration_kw = ["还是", "不行", "不对", "没用", "解决", "再问", "老是", "怎么回事", "为什么"]
if len(history) >= 4 and frustrated_count >= 2:
    reply = f"已升级至人工客服...工单号: TKT-ESC-{timestamp}"
```

### 11.3 反馈闭环

**文件：** `backend/tools/feedback_store.py`

```python
# POST /feedback  → 点赞/踩
# GET /feedback/stats → {"total": N, "up": X, "down": Y, "up_ratio": 0.5}
```

### 11.4 对话超长截断

**文件：** `backend/main.py` → `/chat` 入口

**策略：** history ≥ 20条（10轮）→ DeepSeek 摘要前8轮 → 保留后2轮

```python
if len(history) >= 20:
    summary = deepseek_summarize(history[:16])
    history = [{"role": "system", "content": f"[对话摘要] {summary}"}] + history[16:]
```

---

## 十二、运营监控

### 12.1 意图分布看板

**文件：** `backend/tools/intent_stats.py`

**端点：**
- `GET /stats/intents` — 最近7天各类意图占比
- `GET /stats/intents/trend` — 每日趋势

### 12.2 LLM 成本追踪

**文件：** `backend/tools/cost_tracker.py`

**方案：** LangChain callback 自动捕获 + SQLite 存储

```python
class CostTrackingHandler(BaseCallbackHandler):
    def on_llm_end(self, response, **kwargs):
        usage = response.llm_output["token_usage"]
        cost = (input_tokens*1 + output_tokens*2) / 1_000_000  # DeepSeek 定价
        # 写入 SQLite
```

**关键坑：** LangGraph 覆盖 tags（加 `seq:step:X` 前缀），需跳过 `seq:` 开头的 tag 取 Agent 名

**端点：**
- `GET /cost/summary` — 按 Agent 汇总成本
- `GET /cost/trend` — 每日趋势

### 12.3 知识库管理

**文件：** `backend/tools/knowledge_manager.py`

**端点：**
- `GET /knowledge` — 列出所有条目
- `POST /knowledge` — 新增（自动 Embedding + 同步 md）
- `PUT /knowledge/{id}` — 编辑
- `DELETE /knowledge/{id}` — 删除
- `POST /knowledge/reindex` — 重建索引

---

## 十三、LangSmith 全链路追踪

**配置：** `backend/config.py`

```python
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")
if LANGCHAIN_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = "smart-cs-agent"
```

**可视化：** `https://smith.langchain.com` → 项目 `smart-cs-agent`

**追踪内容：** 每次请求的完整调用链、每个 Agent 节点的 token 消耗、延迟分布

---

## 十四、FastAPI 端点

**文件：** `backend/main.py`

| 端点 | 方法 | 功能 |
|------|------|------|
| `/chat` | POST | 客服对话 |
| `/sessions/{id}` | GET | 查看会话历史 |
| `/feedback` | POST | 提交反馈(👍/👎) |
| `/feedback/stats` | GET | 反馈统计 |
| `/stats/intents` | GET | 意图分布 |
| `/stats/intents/trend` | GET | 意图每日趋势 |
| `/cost/summary` | GET | 成本汇总 |
| `/cost/trend` | GET | 成本趋势 |
| `/knowledge` | GET | 列出知识条目 |
| `/knowledge` | POST | 新增知识 |
| `/knowledge/{id}` | PUT | 编辑知识 |
| `/knowledge/{id}` | DELETE | 删除知识 |
| `/knowledge/reindex` | POST | 重建索引 |

---

## 技术栈速查表

| 技术 | 用途 | 核心文件 |
|------|------|---------|
| LangGraph | 多 Agent 图编排 | `graph/main_graph.py` |
| DeepSeek API | LLM 调用 | `config.py`, `llm_utils.py` |
| Qdrant | 向量检索 | `tools/vector_store.py` |
| 硅基流动 Embedding | 文本向量化 | `tools/vector_store.py` |
| Mem0 | 跨会话用户记忆 | `memory/mem0_store.py` |
| LangChain Callback | 成本追踪 | `tools/cost_tracker.py` |
| LangSmith | 全链路追踪 | `config.py` |
| FastAPI | HTTP 服务 | `main.py` |
| SQLite | 会话/反馈/缓存/统计 | 各 `*_store.py` |
| React + Vite | 前端 | `frontend/` |
