"""
知识库检索工具 —— 基于 Qdrant 向量语义检索。
自动初始化知识库（首次运行时加载 FAQ 文档并生成 embedding）。
"""

from backend.tools.vector_store import vector_search, init_knowledge_base


def search_knowledge(query: str, top_k: int = 3) -> list[dict]:
    """语义检索知识库。

    Args:
        query: 用户查询文本
        top_k: 返回结果数

    Returns:
        [{"content": str, "score": float, "source": str, "title": str}, ...]
    """
    # 延迟初始化：首次调用时自动加载知识库
    return vector_search(query, top_k=top_k)


def initialize_knowledge():
    """手动初始化知识库（可提前调用）。"""
    init_knowledge_base()
