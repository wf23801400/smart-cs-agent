"""
Mem0 用户记忆层 —— 跨会话用户画像管理。
存储用户偏好、历史行为、个人信息，每次对话自动检索和更新。
"""

import os
from pathlib import Path

from mem0 import Memory

# ── 配置 ──────────────────────────────────────────

MEM0_QDRANT_PATH = str(Path(__file__).parent.parent / "data" / "mem0_qdrant")
MEM0_HISTORY_PATH = str(Path(__file__).parent.parent / "data" / "mem0_history.db")

DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")
SILICONFLOW_KEY = os.getenv("SILICONFLOW_API_KEY", "sk-mtjiarcgratjoivrdvjqmylejeqzbwuuhzwpkzxqpgzatoyk")

MEM0_CONFIG = {
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "BAAI/bge-large-zh-v1.5",
            "api_key": SILICONFLOW_KEY,
            "openai_base_url": "https://api.siliconflow.cn/v1",
        },
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "path": MEM0_QDRANT_PATH,
            "embedding_model_dims": 1024,
        },
    },
    "llm": {
        "provider": "openai",
        "config": {
            "model": "deepseek-chat",
            "api_key": DEEPSEEK_KEY,
            "openai_base_url": "https://api.deepseek.com",
        },
    },
    "history_db_path": MEM0_HISTORY_PATH,
}


# ── 单例 ──────────────────────────────────────────

_memory: Memory | None = None


def _get_memory() -> Memory:
    global _memory
    if _memory is None:
        _memory = Memory.from_config(MEM0_CONFIG)
    return _memory


# ── 对外接口 ──────────────────────────────────────

def search_user_memory(user_id: str, query: str, limit: int = 5) -> str:
    """检索用户相关记忆，返回自然语言描述。

    Args:
        user_id: 用户标识（如 session_id）
        query: 当前用户消息（用于语义匹配）
        limit: 返回记忆条数

    Returns:
        记忆文本，如 "用户叫张三，偏好支付宝退款，上次买过耳机"；无记忆时返回空字符串
    """
    memory = _get_memory()
    try:
        raw = memory.search(query, filters={"user_id": user_id}, top_k=limit)
        # Mem0 v2 返回 {"results": [...]}
        results = raw.get("results", []) if isinstance(raw, dict) else raw
        if not results:
            return ""

        memories = [r.get("memory", "") for r in results if isinstance(r, dict) and r.get("memory")]
        if not memories:
            return ""

        return "用户记忆：" + "；".join(memories)
    except Exception as e:
        print(f"[mem0] 检索失败: {e}")
        return ""


def save_user_memory(user_id: str, messages: list[dict]) -> None:
    """从对话中提取并保存用户记忆。

    Args:
        user_id: 用户标识
        messages: 对话消息列表 [{"role": "user"/"assistant", "content": "..."}]
    """
    memory = _get_memory()
    try:
        # Mem0.add 会从 messages 中自动提取值得记忆的信息
        memory.add(messages, user_id=user_id)
    except Exception as e:
        print(f"[mem0] 保存失败: {e}")
