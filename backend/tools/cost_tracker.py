"""LLM 成本追踪 —— LangChain callback 自动捕获 token 用量 + SQLite 存储。

Token 位置（已验证）：
- response.llm_output["token_usage"]  → prompt_tokens / completion_tokens
- gen.message.usage_metadata         → input_tokens / output_tokens
- response.llm_output["model_name"]  → 实际模型名（如 deepseek-v4-flash）
"""
import sqlite3
from langchain_core.callbacks import BaseCallbackHandler

DB = "backend/data/llm_costs.db"

# DeepSeek 价格 (元/百万 tokens)
PRICE_MAP = {
    "deepseek-chat": {"input": 1.0, "output": 2.0},
    "deepseek-v4-flash": {"input": 1.0, "output": 2.0},
    "deepseek-reasoner": {"input": 4.0, "output": 16.0},
}
DEFAULT_PRICE = {"input": 1.0, "output": 2.0}


def _get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cost_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent TEXT NOT NULL DEFAULT 'unknown',
            model TEXT NOT NULL DEFAULT 'deepseek-chat',
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cost_rmb REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cost_agent ON cost_log(agent)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cost_date ON cost_log(created_at)")
    conn.commit()
    return conn


def _calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price = PRICE_MAP.get(model, DEFAULT_PRICE)
    return (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000


class CostTrackingHandler(BaseCallbackHandler):
    """LangChain callback：在每次 LLM 调用结束时自动记录 token 用量。"""

    def on_llm_end(self, response, **kwargs) -> None:
        try:
            llm_output = response.llm_output or {}

            # 获取 token_usage（已确认 DeepSeek 在此位置）
            usage = llm_output.get("token_usage", {})
            if not usage:
                return

            model = llm_output.get("model_name", "deepseek-chat")
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            if input_tokens == 0 and output_tokens == 0:
                return

            cost = _calc_cost(model, input_tokens, output_tokens)

            # 从 tags 获取 agent 名（LangGraph 会加 seq:step:X 前缀，取最后一个非 seq 的）
            agent = "unknown"
            tags = kwargs.get("tags", [])
            for t in tags:
                if not t.startswith("seq:"):
                    agent = t
                    break

            conn = _get_conn()
            conn.execute(
                "INSERT INTO cost_log (agent, model, input_tokens, output_tokens, cost_rmb, created_at) "
                "VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))",
                (agent, model, input_tokens, output_tokens, cost),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass  # 成本追踪失败不影响主流程


cost_handler = CostTrackingHandler()


def get_cost_summary(days: int = 7) -> dict:
    """获取最近 N 天的成本汇总。"""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT agent, COUNT(*) as calls, SUM(input_tokens) as inp, SUM(output_tokens) as outp, SUM(cost_rmb) as cost "
        "FROM cost_log "
        "WHERE created_at >= datetime('now', 'localtime', ?) "
        "GROUP BY agent ORDER BY cost DESC",
        (f"-{days} days",),
    ).fetchall()
    conn.close()

    total_cost = sum(r["cost"] or 0 for r in rows)
    total_in = sum(r["inp"] or 0 for r in rows)
    total_out = sum(r["outp"] or 0 for r in rows)

    return {
        "period_days": days,
        "total_cost_rmb": round(total_cost, 6),
        "total_tokens": {"input": total_in, "output": total_out},
        "by_agent": [
            {
                "agent": r["agent"],
                "calls": r["calls"],
                "input_tokens": r["inp"] or 0,
                "output_tokens": r["outp"] or 0,
                "cost_rmb": round(r["cost"] or 0, 6),
            }
            for r in rows
        ],
    }


def get_cost_trend(days: int = 7) -> dict:
    """每日成本趋势。"""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT date(created_at) as d, COUNT(*) as calls, SUM(input_tokens) as inp, SUM(output_tokens) as outp, SUM(cost_rmb) as cost "
        "FROM cost_log "
        "WHERE created_at >= datetime('now', 'localtime', ?) "
        "GROUP BY d ORDER BY d ASC",
        (f"-{days} days",),
    ).fetchall()
    conn.close()

    return {
        "period_days": days,
        "daily": [
            {
                "date": r["d"],
                "calls": r["calls"],
                "input_tokens": r["inp"] or 0,
                "output_tokens": r["outp"] or 0,
                "cost_rmb": round(r["cost"] or 0, 6),
            }
            for r in rows
        ],
    }
