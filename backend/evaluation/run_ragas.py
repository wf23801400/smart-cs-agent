"""
Ragas RAG 评测脚本 —— 评估 FAQ Agent 的检索和回答质量。

指标说明：
- context_precision  : 检索回的文档中，相关的排前面了吗？
- context_recall     : 标准答案需要的信息，检索出来了吗？
- faithfulness       : 回答是否忠于检索到的文档（不编造）？
- answer_relevancy   : 回答是否切题？

运行方式：
  cd backend && python -m evaluation.run_ragas
"""

import sys
import os

# 确保项目根在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.test_dataset import DATASET
from tools.search_knowledge import search_knowledge

# ── 第1步：通过 HTTP API 调用 FAQ Agent ──────────────

import requests
import json
import time

FAQ_API = "http://localhost:8000/chat"
EVAL_SEARCH_API = "http://localhost:8000/eval/search"

def run_faq(question: str) -> tuple[str, list[str]]:
    """通过 API 获取：回答（/chat） + 检索上下文（/eval/search）。"""
    # 1. 调 /chat API 获取回答
    r = requests.post(
        FAQ_API,
        json={"message": question},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    answer = data.get("reply", "")

    # 2. 调 /eval/search 获取真实检索上下文
    r2 = requests.get(EVAL_SEARCH_API, params={"q": question, "top_k": 3}, timeout=30)
    r2.raise_for_status()
    sdata = r2.json()
    contexts = [item["content"] for item in sdata.get("results", [])]

    return answer, contexts


# ── 第3步：构建 Ragas 评测数据集 ────────────────────

from datasets import Dataset as HFDataset

def build_eval_dataset():
    """对所有测试问题跑 FAQ Agent，收集回答和上下文。"""
    records = []
    print(f"\n{'='*60}")
    print(f"  跑 {len(DATASET)} 条 FAQ 评测...")
    print(f"{'='*60}\n")

    for i, item in enumerate(DATASET):
        question = item["question"]
        ground_truth = item["ground_truth"]

        try:
            answer, contexts = run_faq(question)
        except Exception as e:
            print(f"[{i+1}/{len(DATASET)}] ❌ {question[:40]}... 失败: {e}")
            answer = "（请求失败）"
            contexts = []

        records.append({
            "question": question,
            "answer": answer,
            "contexts": contexts,
            "ground_truth": ground_truth,
        })

        print(f"[{i+1}/{len(DATASET)}] {question[:40]}...")
        time.sleep(0.5)  # 避免压垮后端单 worker

    return HFDataset.from_list(records)


# ── 第4步：运行 Ragas 评测 ──────────────────────────

from ragas import evaluate, EvaluationDataset
from ragas.metrics.collections import (
    Faithfulness,
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
)
from ragas.llms import llm_factory

def run_evaluation():
    """主流程：构建数据 → 跑 Ragas 评测 → 输出报告。"""
    print("\n🚀 开始 Ragas 评测（使用 DeepSeek 作为裁判模型）\n")

    # 构建数据
    hf_dataset = build_eval_dataset()

    # 转换为 Ragas EvaluationDataset
    eval_dataset = EvaluationDataset.from_hf_dataset(hf_dataset)

    # ── 第4步：运行 Ragas 评测 ──────────────────────────
    from openai import OpenAI
    openai_client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        base_url="https://api.deepseek.com",
    )
    eval_llm = llm_factory(
        "deepseek-chat",
        client=openai_client,
        temperature=0.0,
    )

    # 选择指标（需传入 eval_llm；跳过 AnswerRelevancy 需额外 embedding）
    metrics = [
        ContextPrecision(llm=eval_llm),
        ContextRecall(llm=eval_llm),
        Faithfulness(llm=eval_llm),
    ]

    # 跑评测
    result = evaluate(
        dataset=eval_dataset,
        metrics=metrics,
    )

    # ── 输出报告 ──────────────────────────────

    print(f"\n{'='*60}")
    print(f"  📊 Ragas 评测结果")
    print(f"{'='*60}\n")

    df = result.to_pandas()
    metric_avgs = {}

    for metric in metrics:
        col = metric.name
        if col in df.columns:
            avg = df[col].mean()
            metric_avgs[col] = avg
            bar = "█" * int(avg * 20)
            print(f"  {col:<20s}: {avg:.3f}  {bar}")

    print(f"\n{'='*60}")
    print(f"  综合评分: {sum(metric_avgs.values()) / len(metric_avgs):.3f}")
    print(f"{'='*60}\n")

    # 逐条详情
    print("─" * 60)
    print("  逐条详情")
    print("─" * 60)

    for i, item in enumerate(DATASET):
        row = df.iloc[i]
        print(f"\n[{i+1}] {item['question']}")
        print(f"    答案: {row.get('answer', 'N/A')[:120]}...")
        scores = []
        for metric in metrics:
            col = metric.name
            if col in row:
                scores.append(f"{col}={row[col]:.2f}")
        print(f"    评分: {', '.join(scores)}")

    return df


if __name__ == "__main__":
    run_evaluation()
