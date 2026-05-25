"""
Qdrant 向量存储 —— 本地模式 + 硅基流动 Embedding API。
封装知识库加载、API embedding、语义检索。
"""

import os
import re
from pathlib import Path

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# ── 配置 ──────────────────────────────────────────

COLLECTION_NAME = "faq_knowledge"
VECTOR_SIZE = 1024  # BAAI/bge-large-zh-v1.5 输出维度
EMBEDDING_MODEL = "BAAI/bge-large-zh-v1.5"
EMBEDDING_API_URL = "https://api.siliconflow.cn/v1/embeddings"
EMBEDDING_API_KEY = os.getenv("SILICONFLOW_API_KEY", "sk-mtjiarcgratjoivrdvjqmylejeqzbwuuhzwpkzxqpgzatoyk")

QDRANT_PATH = Path(__file__).parent.parent / "data" / "qdrant_db"
KNOWLEDGE_DIR = Path(__file__).parent.parent / "data" / "knowledge"

# ── 单例 ──────────────────────────────────────────

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        QDRANT_PATH.mkdir(parents=True, exist_ok=True)
        _client = QdrantClient(path=str(QDRANT_PATH))
    return _client


# ── Embedding ─────────────────────────────────────

def _embed(texts: list[str]) -> list[list[float]]:
    """调用硅基流动 Embedding API，批量向量化。"""
    resp = httpx.post(
        EMBEDDING_API_URL,
        json={
            "model": EMBEDDING_MODEL,
            "input": texts,
            "encoding_format": "float",
        },
        headers={
            "Authorization": f"Bearer {EMBEDDING_API_KEY}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    # 按 index 排序确保顺序
    items = sorted(data["data"], key=lambda x: x["index"])
    return [item["embedding"] for item in items]


# ── 分块 ──────────────────────────────────────────

def _split_chunks(text: str, source: str) -> list[dict]:
    """按 ## 标题分割文档为 chunks。"""
    chunks = []
    sections = re.split(r"\n(?=## )", text)
    for section in sections:
        section = section.strip()
        if not section:
            continue
        title_match = re.match(r"^## (.+)", section)
        title = title_match.group(1) if title_match else ""

        paragraphs = section.split("\n\n")
        buffer = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(buffer) + len(para) < 500:
                buffer += "\n" + para if buffer else para
            else:
                if buffer:
                    chunks.append({"text": buffer.strip(), "source": source, "title": title})
                buffer = para
        if buffer:
            chunks.append({"text": buffer.strip(), "source": source, "title": title})

    return chunks


# ── 初始化 ────────────────────────────────────────

def init_knowledge_base():
    """初始化知识库：加载 FAQ → 分块 → API embedding → 存入 Qdrant。"""
    client = _get_client()

    # 检查是否已有数据
    if client.collection_exists(COLLECTION_NAME):
        print("[vector_store] 集合已存在，跳过初始化")
        return

    # 创建集合
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )

    # 加载所有 FAQ 文档
    all_chunks = []
    for md_file in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        source = md_file.stem
        chunks = _split_chunks(text, source)
        all_chunks.extend(chunks)

    if not all_chunks:
        print("[vector_store] 未找到知识文档")
        return

    # 批量 Embedding（每批最多 32 条）
    print(f"[vector_store] 正在向量化 {len(all_chunks)} 条文档片段...")
    texts = [c["text"] for c in all_chunks]
    all_embeddings = []
    batch_size = 32
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        all_embeddings.extend(_embed(batch))
        print(f"[vector_store]   {min(i + batch_size, len(texts))}/{len(texts)}")

    # 写入 Qdrant
    points = [
        PointStruct(
            id=i,
            vector=emb,
            payload={
                "content": c["text"],
                "source": c["source"],
                "title": c.get("title", ""),
            },
        )
        for i, (emb, c) in enumerate(zip(all_embeddings, all_chunks))
    ]

    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"[vector_store] 知识库初始化完成: {len(points)} 条文档片段")


# ── 检索 ──────────────────────────────────────────

def vector_search(query: str, top_k: int = 3) -> list[dict]:
    """语义检索知识库。

    Returns:
        [{"content": str, "score": float, "source": str, "title": str}, ...]
    """
    client = _get_client()

    if not client.collection_exists(COLLECTION_NAME):
        print("[vector_store] 知识库未初始化，正在初始化...")
        init_knowledge_base()

    query_vec = _embed([query])[0]

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec,
        limit=top_k,
    ).points

    return [
        {
            "content": r.payload.get("content", ""),
            "score": round(r.score, 4),
            "source": r.payload.get("source", ""),
            "title": r.payload.get("title", ""),
        }
        for r in results
    ]
