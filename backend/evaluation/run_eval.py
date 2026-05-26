"""
轻量 RAG 评测脚本 —— 不依赖 Ragas，用 DeepSeek 做裁判。

指标：
1. context_recall  : 检索是否命中预期关键词（规则打分）
2. faithfulness   : LLM 判断回答是否忠于知识库（不编造）
3. answer_score   : LLM 综合评分（准确度 + 完整性 + 友好度）

运行：cd backend && DEEPSEEK_API_KEY=xxx python -m evaluation.run_eval
"""

import sys, os, json, re, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from evaluation.test_dataset import DATASET
from openai import OpenAI

from backend.config import settings

# ── 配置 ─────────────────────────────────────────

FAQ_API = "http://localhost:8000/chat"
SEARCH_API = "http://localhost:8000/eval/search"
OPENAI_CLIENT = OpenAI(
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
)

JUDGE_MODEL = "deepseek-chat"


# ── 工具函数 ──────────────────────────────────────

def call_llm(system: str, user: str, temp: float = 0.0) -> str:
    """调用 DeepSeek 裁判模型。"""
    resp = OPENAI_CLIENT.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temp,
    )
    return resp.choices[0].message.content


def get_answer_and_contexts(question: str) -> tuple[str, list[str]]:
    """通过 API 获取回答和检索上下文。"""
    r = requests.post(FAQ_API, json={"message": question}, timeout=30)
    r.raise_for_status()
    answer = r.json().get("reply", "")

    r2 = requests.get(SEARCH_API, params={"q": question, "top_k": 3}, timeout=30)
    r2.raise_for_status()
    contexts = [item["content"] for item in r2.json().get("results", [])]

    return answer, contexts


# ── 指标1：关键词召回率 ──────────────────────────

def score_context_recall(contexts: list[str], expected_keywords: list[str]) -> float:
    """检索到的文档是否覆盖了预期关键词。"""
    all_text = " ".join(contexts).lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in all_text)
    return hits / len(expected_keywords) if expected_keywords else 0.0


# ── 指标2：忠实度 LLM-as-Judge ────────────────────

def score_faithfulness(answer: str, contexts: list[str]) -> float:
    """LLM 判断回答是否忠于检索文档（不编造不存在的信息）。"""
    ctx_text = "\n\n---\n\n".join(c[:300] for c in contexts)
    prompt = f"""你是 RAG 评测裁判。判断回答是否忠于以下检索文档。

【检索文档】
{ctx_text}

【回答】
{answer}

评分标准：
- 1.0 分：回答完全基于文档，无编造
- 0.7 分：回答大部分基于文档，有少量合理推断
- 0.4 分：回答有部分不在文档中的信息
- 0.0 分：回答大量编造，与文档无关

严格按 JSON 输出：{{"score": 0.0, "reason": "一句话理由"}}"""
    result = call_llm("你是严格的 RAG 忠实度裁判", prompt)
    try:
        return float(json.loads(result)["score"])
    except Exception:
        match = re.search(r"(\d\.?\d*)", result)
        return float(match.group(1)) if match else 0.5


# ── 指标3：综合质量 LLM-as-Judge ──────────────────

def score_answer_quality(answer: str, ground_truth: str, question: str) -> float:
    """LLM 综合评分：准确度 + 完整性 + 友好度。"""
    prompt = f"""你是客服质量评测裁判。对客服回答评分。

【用户问题】
{question}

【标准答案】
{ground_truth}

【客服回答】
{answer}

评分维度（各 0-1 分）：
- 准确度：回答与标准答案是否一致
- 完整性：是否覆盖标准答案的关键信息
- 友好度：语气是否亲切自然（客服场景加分项）

严格按 JSON 输出：{{"accuracy": 0.0, "completeness": 0.0, "friendliness": 0.0}}"""
    result = call_llm("你是严格的客服质量裁判", prompt)
    try:
        scores = json.loads(result)
        return round((scores["accuracy"] + scores["completeness"] + scores["friendliness"]) / 3, 3)
    except Exception:
        match = re.findall(r"(\d\.?\d*)", result)
        if len(match) >= 3:
            return round(sum(float(m) for m in match[:3]) / 3, 3)
        return 0.5


# ── 主流程 ────────────────────────────────────────

def run():
    print(f"\n{'='*60}")
    print(f"  📊 轻量 RAG 评测（DeepSeek 裁判）")
    print(f"  数据: {len(DATASET)} 条 | 指标: Recall + Faithfulness + Quality")
    print(f"{'='*60}\n")

    results = []
    for i, item in enumerate(DATASET):
        q = item["question"]
        gt = item["ground_truth"]
        kws = item.get("expected_keywords", [])

        try:
            answer, contexts = get_answer_and_contexts(q)
        except Exception as e:
            print(f"[{i+1}] ❌ {q[:30]}... API失败: {e}")
            results.append({"question": q, "recall": 0, "faithfulness": 0, "quality": 0, "answer": "(失败)", "error": str(e)})
            continue

        recall = score_context_recall(contexts, kws)
        faith = score_faithfulness(answer, contexts)
        quality = score_answer_quality(answer, gt, q)

        results.append({
            "question": q,
            "recall": round(recall, 3),
            "faithfulness": round(faith, 3),
            "quality": round(quality, 3),
            "answer": answer[:120],
        })

        print(f"[{i+1}/{len(DATASET)}] {q[:40]}... R={recall:.2f} F={faith:.2f} Q={quality:.2f}")
        time.sleep(0.3)

    # ── 汇总 ────────────────────────────────────

    avg_recall = sum(r["recall"] for r in results) / len(results)
    avg_faith = sum(r["faithfulness"] for r in results) / len(results)
    avg_quality = sum(r["quality"] for r in results) / len(results)
    overall = round((avg_recall + avg_faith + avg_quality) / 3, 3)

    print(f"\n{'='*60}")
    print(f"  📊 评测汇总")
    print(f"{'='*60}")
    print(f"  Context Recall : {avg_recall:.3f}")
    print(f"  Faithfulness   : {avg_faith:.3f}")
    print(f"  Answer Quality : {avg_quality:.3f}")
    print(f"  ─────────────────────────────")
    print(f"  综合评分        : {overall:.3f}")
    print(f"{'='*60}")

    # ── 短板诊断 ────────────────────────────────

    low_recall = [r for r in results if r["recall"] < 0.5]
    low_faith = [r for r in results if r["faithfulness"] < 0.5]
    low_quality = [r for r in results if r["quality"] < 0.5]

    if low_recall:
        print(f"\n⚠️  检索召回不足 ({len(low_recall)} 条):")
        for r in low_recall[:3]:
            print(f"   [{r['recall']:.2f}] {r['question']}")

    if low_faith:
        print(f"\n⚠️  忠实度偏低 ({len(low_faith)} 条):")
        for r in low_faith[:3]:
            print(f"   [{r['faithfulness']:.2f}] {r['question']}")

    if low_quality:
        print(f"\n⚠️  回答质量偏低 ({len(low_quality)} 条):")
        for r in low_quality[:3]:
            print(f"   [{r['quality']:.2f}] {r['question']}")

    return results


if __name__ == "__main__":
    run()
