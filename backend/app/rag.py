from __future__ import annotations

import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any, Iterable

from .knowledge import load_action_catalog


BASE_DIR = Path(__file__).resolve().parents[2]
RAG_DIR = BASE_DIR / "knowledge" / "rag_store"
LOCAL_INDEX_FILE = RAG_DIR / "local_index.json"

DEFAULT_COLLECTION = "kangjian_rehab_knowledge"
DEFAULT_VECTOR_SIZE = 512


def _normal_provider() -> str:
    provider = os.getenv("RAG_VECTOR_PROVIDER", "auto").strip().lower()
    if provider in {"qdrant", "chroma", "local", "auto"}:
        return provider
    return "auto"


def _tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    words = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", text)
    bigrams = [text[index : index + 2] for index in range(max(0, len(text) - 1))]
    return [token for token in [*words, *bigrams] if token.strip()]


class HashingEmbeddings:
    """Small deterministic embedding model used by all vector-store adapters."""

    def __init__(self, size: int = DEFAULT_VECTOR_SIZE):
        self.size = size

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * self.size
        for token in _tokenize(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.size
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents(texts)

    async def aembed_query(self, text: str) -> list[float]:
        return self.embed_query(text)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    return float(sum(left * right for left, right in zip(a, b)))


def _clean_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool | None]:
    cleaned = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            cleaned[key] = value
        else:
            cleaned[key] = json.dumps(value, ensure_ascii=False)
    return cleaned


def _chunk_text(text: str, chunk_size: int = 700, overlap: int = 100) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(text):
            break
        start += max(1, chunk_size - overlap)
    return chunks


def _langchain_split(text: str) -> list[str]:
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=100)
        return [chunk for chunk in splitter.split_text(text) if chunk.strip()]
    except Exception:
        return _chunk_text(text)


def build_source_documents() -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for action in load_action_catalog():
        action_id = action.get("id") or action.get("name")
        body_regions = action.get("body_regions") or []
        target_conditions = action.get("target_conditions") or []
        text = "\n".join(
            [
                f"动作名称：{action.get('name', '')}",
                f"适用部位：{'、'.join(body_regions)}",
                f"适应症：{'、'.join(target_conditions)}",
                f"建议剂量：{action.get('sets', 1)}组，每组{action.get('reps', 1)}次；{action.get('frequency', '')}",
                f"动作说明：{action.get('description', '')}",
                f"禁忌症：{action.get('contraindications', '')}",
                f"进阶：{action.get('progression', '')}",
                f"降阶：{action.get('regression', '')}",
            ]
        )
        documents.append(
            {
                "id": f"action:{action_id}",
                "text": text,
                "metadata": {
                    "source": "actions.json",
                    "kind": "action",
                    "action_id": action_id,
                    "title": action.get("name", ""),
                    "body_regions": body_regions,
                    "target_conditions": target_conditions,
                },
            }
        )

    try:
        from .education import PREVENTION_TIPS, REGION_ARTICLE_SUMMARY

        for region, summary in REGION_ARTICLE_SUMMARY.items():
            tips = PREVENTION_TIPS.get(region, [])
            documents.append(
                {
                    "id": f"article:{region}",
                    "text": (
                        f"{region}康复科普：{summary} "
                        f"预防建议：{'；'.join(tips)} "
                        "训练应遵循疼痛可控、循序渐进、动作标准和出现红旗症状及时就医的原则。"
                    ),
                    "metadata": {
                        "source": "education.py",
                        "kind": "article",
                        "title": f"{region}康复与预防建议",
                        "body_regions": [region],
                        "target_conditions": [],
                    },
                }
            )
    except Exception:
        pass

    return documents


def build_index_documents() -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for document in build_source_documents():
        for index, chunk in enumerate(_langchain_split(document["text"])):
            metadata = {**document["metadata"], "chunk": index}
            chunks.append(
                {
                    "id": f"{document['id']}#{index}",
                    "text": chunk,
                    "metadata": metadata,
                }
            )
    return chunks


class LocalVectorStore:
    provider = "local"

    def __init__(self):
        self.embeddings = HashingEmbeddings()

    def reindex(self, documents: list[dict[str, Any]]) -> dict[str, Any]:
        RAG_DIR.mkdir(parents=True, exist_ok=True)
        texts = [document["text"] for document in documents]
        vectors = self.embeddings.embed_documents(texts)
        payload = {
            "provider": self.provider,
            "collection": DEFAULT_COLLECTION,
            "vector_size": self.embeddings.size,
            "documents": [
                {**document, "vector": vector}
                for document, vector in zip(documents, vectors)
            ],
        }
        LOCAL_INDEX_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.status(extra={"indexed_documents": len(documents)})

    def search(self, query: str, limit: int = 5, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if not LOCAL_INDEX_FILE.exists():
            self.reindex(build_index_documents())
        payload = json.loads(LOCAL_INDEX_FILE.read_text(encoding="utf-8"))
        query_vector = self.embeddings.embed_query(query)
        results = []
        for document in payload.get("documents", []):
            if not _metadata_matches(document.get("metadata") or {}, filters):
                continue
            score = _cosine(query_vector, document.get("vector") or [])
            if score <= 0:
                continue
            results.append(
                {
                    "id": document["id"],
                    "text": document["text"],
                    "metadata": document.get("metadata") or {},
                    "score": round(score, 4),
                }
            )
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[: max(1, min(limit, 20))]

    def status(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        count = 0
        if LOCAL_INDEX_FILE.exists():
            try:
                count = len(json.loads(LOCAL_INDEX_FILE.read_text(encoding="utf-8")).get("documents", []))
            except Exception:
                count = 0
        return {
            "provider": self.provider,
            "collection": DEFAULT_COLLECTION,
            "available": True,
            "indexed_documents": count,
            "path": str(LOCAL_INDEX_FILE.relative_to(BASE_DIR)),
            **(extra or {}),
        }


class ChromaVectorStore:
    provider = "chroma"

    def __init__(self):
        import chromadb

        self.embeddings = HashingEmbeddings()
        self.path = os.getenv("CHROMA_PERSIST_DIR", str(RAG_DIR / "chroma"))
        self.collection_name = os.getenv("CHROMA_COLLECTION", DEFAULT_COLLECTION)
        self.client = chromadb.PersistentClient(path=self.path)
        self.collection = self.client.get_or_create_collection(self.collection_name)

    def reindex(self, documents: list[dict[str, Any]]) -> dict[str, Any]:
        ids = [document["id"] for document in documents]
        try:
            self.collection.delete(ids=self.collection.get().get("ids", []))
        except Exception:
            pass
        if documents:
            self.collection.upsert(
                ids=ids,
                documents=[document["text"] for document in documents],
                metadatas=[_clean_metadata(document["metadata"]) for document in documents],
                embeddings=self.embeddings.embed_documents([document["text"] for document in documents]),
            )
        return self.status(extra={"indexed_documents": len(documents)})

    def search(self, query: str, limit: int = 5, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        result = self.collection.query(
            query_embeddings=[self.embeddings.embed_query(query)],
            n_results=max(1, min(limit, 20)),
            where=_chroma_where(filters),
        )
        items = []
        for item_id, text, metadata, distance in zip(
            result.get("ids", [[]])[0],
            result.get("documents", [[]])[0],
            result.get("metadatas", [[]])[0],
            result.get("distances", [[]])[0],
        ):
            items.append(
                {
                    "id": item_id,
                    "text": text,
                    "metadata": _restore_metadata(metadata or {}),
                    "score": round(1 / (1 + float(distance or 0)), 4),
                }
            )
        return items

    def status(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "collection": self.collection_name,
            "available": True,
            "indexed_documents": self.collection.count(),
            "path": self.path,
            **(extra or {}),
        }


class QdrantVectorStore:
    provider = "qdrant"

    def __init__(self):
        from qdrant_client import QdrantClient

        self.embeddings = HashingEmbeddings()
        self.collection_name = os.getenv("QDRANT_COLLECTION", DEFAULT_COLLECTION)
        url = os.getenv("QDRANT_URL")
        path = os.getenv("QDRANT_PATH", str(RAG_DIR / "qdrant"))
        self.client = QdrantClient(url=url) if url else QdrantClient(path=path)

    def reindex(self, documents: list[dict[str, Any]]) -> dict[str, Any]:
        from qdrant_client.http.models import Distance, PointStruct, VectorParams

        try:
            self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=DEFAULT_VECTOR_SIZE, distance=Distance.COSINE),
            )
        except AttributeError:
            self.client.delete_collection(collection_name=self.collection_name)
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=DEFAULT_VECTOR_SIZE, distance=Distance.COSINE),
            )
        points = [
            PointStruct(
                id=_stable_int_id(document["id"]),
                vector=vector,
                payload={
                    "doc_id": document["id"],
                    "text": document["text"],
                    **_clean_metadata(document["metadata"]),
                },
            )
            for document, vector in zip(
                documents,
                self.embeddings.embed_documents([document["text"] for document in documents]),
            )
        ]
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)
        return self.status(extra={"indexed_documents": len(documents)})

    def search(self, query: str, limit: int = 5, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        query_vector = self.embeddings.embed_query(query)
        result_limit = max(1, min(limit, 20))
        if hasattr(self.client, "search"):
            hits = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=result_limit,
            )
        else:
            result = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=result_limit,
            )
            hits = getattr(result, "points", result)
        items = []
        for hit in hits:
            payload = hit.payload or {}
            metadata = {
                key: value
                for key, value in payload.items()
                if key not in {"doc_id", "text"}
            }
            metadata = _restore_metadata(metadata)
            if not _metadata_matches(metadata, filters):
                continue
            items.append(
                {
                    "id": payload.get("doc_id") or str(hit.id),
                    "text": payload.get("text") or "",
                    "metadata": metadata,
                    "score": round(float(hit.score or 0), 4),
                }
            )
        return items

    def status(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        count = 0
        try:
            count = self.client.count(collection_name=self.collection_name).count
        except Exception:
            count = 0
        return {
            "provider": self.provider,
            "collection": self.collection_name,
            "available": True,
            "indexed_documents": count,
            **(extra or {}),
        }


def _stable_int_id(value: str) -> int:
    return int.from_bytes(hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest(), "big", signed=False)


def _metadata_matches(metadata: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    if not filters:
        return True
    for key, expected in filters.items():
        if expected in (None, "", []):
            continue
        actual = metadata.get(key)
        if isinstance(actual, str):
            try:
                actual = json.loads(actual)
            except Exception:
                pass
        if isinstance(actual, list):
            expected_items = expected if isinstance(expected, list) else [expected]
            if not set(expected_items) & set(actual):
                return False
        elif actual != expected:
            return False
    return True


def _chroma_where(filters: dict[str, Any] | None) -> dict[str, Any] | None:
    if not filters:
        return None
    clauses = []
    for key, expected in filters.items():
        if expected in (None, "", []):
            continue
        if isinstance(expected, list):
            clauses.append({key: {"$in": expected}})
        else:
            clauses.append({key: expected})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _restore_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    restored = {}
    for key, value in metadata.items():
        if isinstance(value, str) and value[:1] in {"[", "{"}:
            try:
                restored[key] = json.loads(value)
                continue
            except Exception:
                pass
        restored[key] = value
    return restored


def get_vector_store():
    provider = _normal_provider()
    errors = []
    if provider in {"auto", "chroma"}:
        try:
            return ChromaVectorStore()
        except Exception as exc:
            errors.append(f"chroma unavailable: {exc}")
            if provider == "chroma":
                raise
    if provider in {"auto", "qdrant"}:
        try:
            return QdrantVectorStore()
        except Exception as exc:
            errors.append(f"qdrant unavailable: {exc}")
            if provider == "qdrant":
                raise
    store = LocalVectorStore()
    store._errors = errors
    return store


def reindex_knowledge() -> dict[str, Any]:
    documents = build_index_documents()
    store = get_vector_store()
    status = store.reindex(documents)
    return {**status, "source_documents": len(build_source_documents())}


def retrieve_contexts(
    query: str,
    limit: int = 5,
    body_regions: list[str] | None = None,
    kind: str | None = None,
) -> list[dict[str, Any]]:
    if not query or not query.strip():
        return []
    filters = {
        "body_regions": body_regions,
        "kind": kind,
    }
    store = get_vector_store()
    try:
        results = store.search(query=query, limit=limit, filters=filters)
        if results:
            return results
        if filters:
            relaxed_results = store.search(query=query, limit=limit, filters=None)
            if relaxed_results:
                return relaxed_results
        status = store.status()
        if status.get("indexed_documents", 0) == 0:
            store.reindex(build_index_documents())
            results = store.search(query=query, limit=limit, filters=filters)
            if results:
                return results
            return store.search(query=query, limit=limit, filters=None)
        return results
    except Exception:
        fallback = LocalVectorStore()
        return fallback.search(query=query, limit=limit, filters=filters)


def rag_status() -> dict[str, Any]:
    store = get_vector_store()
    status = store.status()
    errors = getattr(store, "_errors", [])
    if errors:
        status["fallback_reasons"] = errors
    try:
        import langchain  # noqa: F401

        status["langchain_available"] = True
    except Exception:
        status["langchain_available"] = False
    try:
        import langgraph  # noqa: F401

        status["langgraph_available"] = True
    except Exception:
        status["langgraph_available"] = False
    return status


def contexts_to_prompt(contexts: Iterable[dict[str, Any]]) -> str:
    lines = []
    for index, item in enumerate(contexts, start=1):
        metadata = item.get("metadata") or {}
        title = metadata.get("title") or item.get("id")
        lines.append(f"[{index}] {title}: {item.get('text', '')}")
    return "\n".join(lines)
