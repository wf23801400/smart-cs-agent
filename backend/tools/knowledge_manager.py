"""知识库管理 —— 增删改 FAQ 条目 + 自动同步 Qdrant + md 文件。"""
import os
import re
from pathlib import Path
from backend.tools.vector_store import (
    _get_client,
    _embed,
    COLLECTION_NAME,
    KNOWLEDGE_DIR,
    VECTOR_SIZE,
    Distance,
    VectorParams,
    PointStruct,
)


def list_entries() -> list[dict]:
    """列出所有知识条目。"""
    client = _get_client()
    if not client.collection_exists(COLLECTION_NAME):
        return []

    # scroll 获取所有 points
    points, _ = client.scroll(collection_name=COLLECTION_NAME, limit=1000)
    return [
        {
            "id": p.id,
            "title": p.payload.get("title", ""),
            "content": p.payload.get("content", ""),
            "source": p.payload.get("source", ""),
        }
        for p in points
    ]


def add_entry(title: str, content: str, source: str = "faq") -> dict:
    """新增知识条目 → embedding → 写入 Qdrant → 更新 md。"""
    client = _get_client()

    # 确保集合存在
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

    # 获取下一个 ID
    points, _ = client.scroll(collection_name=COLLECTION_NAME, limit=1000, with_vectors=False)
    max_id = max([p.id for p in points], default=-1)
    new_id = max_id + 1

    # Embedding
    full_text = f"## {title}\n\n{content}"
    vector = _embed([full_text])[0]

    # 写入 Qdrant
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=new_id,
                vector=vector,
                payload={"content": full_text, "source": source, "title": title},
            )
        ],
    )

    # 更新 md 文件
    _sync_to_md(source)

    return {"id": new_id, "title": title, "content": full_text, "source": source}


def update_entry(point_id: int, title: str = "", content: str = "") -> dict:
    """编辑知识条目 → 重新 embedding → 更新 Qdrant → 更新 md。"""
    client = _get_client()

    # 查找现有 point
    points = client.retrieve(
        collection_name=COLLECTION_NAME,
        ids=[point_id],
        with_payload=True,
    )
    if not points:
        raise ValueError(f"条目 {point_id} 不存在")

    old = points[0].payload
    new_title = title or old.get("title", "")
    source = old.get("source", "faq")
    full_text = f"## {new_title}\n\n{content}" if content else old.get("content", "")

    # 重新 Embedding
    vector = _embed([full_text])[0]

    # 更新 Qdrant
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=point_id,
                vector=vector,
                payload={"content": full_text, "source": source, "title": new_title},
            )
        ],
    )

    # 更新 md 文件
    _sync_to_md(source)

    return {"id": point_id, "title": new_title, "content": full_text, "source": source}


def delete_entry(point_id: int) -> dict:
    """删除知识条目 → 从 Qdrant 删除 → 更新 md。"""
    client = _get_client()

    # 查找 source
    points = client.retrieve(
        collection_name=COLLECTION_NAME,
        ids=[point_id],
        with_payload=True,
    )
    if not points:
        raise ValueError(f"条目 {point_id} 不存在")

    source = points[0].payload.get("source", "faq")

    # 删除
    client.delete(collection_name=COLLECTION_NAME, points_selector=[point_id])

    # 更新 md 文件
    _sync_to_md(source)

    return {"deleted": point_id, "source": source}


def rebuild_index() -> dict:
    """重建索引：删除旧集合 → 重新从 md 文件加载。"""
    from backend.tools.vector_store import init_knowledge_base

    client = _get_client()
    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)

    init_knowledge_base()
    entries = list_entries()
    return {"status": "ok", "count": len(entries)}


def _sync_to_md(source: str):
    """将 Qdrant 中该 source 的所有条目同步回 md 文件。"""
    client = _get_client()
    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        limit=1000,
        with_payload=True,
    )

    # 按 source 过滤
    source_entries = []
    for p in points:
        if p.payload.get("source", "") == source:
            source_entries.append(p)

    # 按 id 排序
    source_entries.sort(key=lambda p: p.id)

    # 写入 md 文件
    md_path = KNOWLEDGE_DIR / f"{source}.md"
    lines = ["# 电商客服常见问题知识库\n"]
    for p in source_entries:
        title = p.payload.get("title", "")
        content = p.payload.get("content", "")
        if content.startswith(f"## {title}"):
            lines.append(f"\n{content}\n")
        else:
            lines.append(f"\n## {title}\n\n{content}\n")

    md_path.write_text("\n".join(lines), encoding="utf-8")
