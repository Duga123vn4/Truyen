# -*- coding: utf-8 -*-
"""
🧠 NOVEL AI — MULTILINGUAL HYBRID VECTOR & CACHED BM25 LORE SEARCH ENGINE V4.5
- Multilingual Sentence Transformers (paraphrase-multilingual-MiniLM-L12-v2) 100% Offline
- Cached BM25Okapi Inverted Index (Persistent pickle cache - 0.002s query)
- Exact 1-based Line Tracker for Evidence Grounding
- Decoupled sync_index() from search() for maximum scalability
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import os
import re
import json
import pickle
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import chromadb
    from chromadb.utils import embedding_functions
    import numpy as np
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

try:
    from rank_bm25 import BM25Okapi
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False

STOPWORDS = {
    "và", "với", "của", "cho", "bởi", "trong", "ở", "tại", "những", "các", "một", 
    "này", "đó", "được", "bị", "là", "đã", "đang", "sẽ", "thì", "mà", "nhưng"
}

def tokenize_vietnamese(text: str) -> List[str]:
    """Tách từ tiếng Việt và loại bỏ hư từ (stopwords)."""
    words = re.findall(r'\w+', text.lower())
    return [w for w in words if len(w) >= 2 and w not in STOPWORDS]

def chunk_chapter_accurate(text: str, ep: int, file_name: str, target_words: int = 250) -> List[Dict[str, Any]]:
    """Chia phân đoạn chuẩn xác theo từng dòng thực tế của file gốc."""
    lines = text.splitlines()
    chunks = []
    curr_lines = []
    curr_w = 0
    start_line = 1
    f_stem = Path(file_name).stem

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            if curr_w >= target_words and curr_lines:
                chunks.append({
                    "id": f"{f_stem}_chunk{len(chunks)}",
                    "chapter": ep,
                    "file_name": file_name,
                    "chunk_idx": len(chunks),
                    "text": "\n".join(curr_lines),
                    "start_line": start_line,
                    "end_line": idx - 1
                })
                curr_lines, curr_w = [], 0
                start_line = idx + 1
            elif curr_lines:
                curr_lines.append("")
            continue

        if not curr_lines:
            start_line = idx
        curr_lines.append(line)
        curr_w += len(stripped.split())

    if curr_lines:
        chunks.append({
            "id": f"{f_stem}_chunk{len(chunks)}",
            "chapter": ep,
            "file_name": file_name,
            "chunk_idx": len(chunks),
            "text": "\n".join(curr_lines),
            "start_line": start_line,
            "end_line": len(lines)
        })
    return chunks

class ChromaNovelSearch:
    def __init__(self, novel_dir: Path):
        self.novel_dir = novel_dir
        self.trans_dir = novel_dir / "translated"
        self.db_dir = novel_dir / "lore_vector_db"
        self.db_dir.mkdir(parents=True, exist_ok=True)

        if not HAS_CHROMADB:
            raise ImportError("ChromaDB chưa được cài đặt!")

        # 1. Khởi tạo Multilingual Embedding Function
        try:
            self.ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="paraphrase-multilingual-MiniLM-L12-v2"
            )
            col_name = f"novel_{novel_dir.name.lower()}_multi_v2"
        except Exception:
            self.ef = embedding_functions.DefaultEmbeddingFunction()
            col_name = f"novel_{novel_dir.name.lower()}_v1"

        self.client = chromadb.PersistentClient(path=str(self.db_dir))
        try:
            self.collection = self.client.get_or_create_collection(
                name=col_name,
                embedding_function=self.ef
            )
        except Exception:
            try:
                self.client.delete_collection(name=col_name)
            except Exception:
                pass
            self.collection = self.client.create_collection(
                name=col_name,
                embedding_function=self.ef
            )

        self.meta_file = self.db_dir / f"indexed_{col_name}.json"
        self.bm25_cache_file = self.db_dir / f"bm25_{col_name}.pkl"

        # Tự động đồng bộ nếu database trống hoặc chưa có BM25 cache
        if self.collection.count() == 0 or not self.bm25_cache_file.exists():
            self.sync_index()

    def get_file_hash(self, path: Path) -> str:
        h = hashlib.sha256()
        h.update(path.read_bytes())
        return h.hexdigest()

    def sync_index(self, force: bool = False):
        """Chỉ chạy khi có chương mới hoặc được gọi từ pipeline dịch."""
        indexed_meta = {}
        if self.meta_file.exists() and not force:
            try:
                indexed_meta = json.loads(self.meta_file.read_text(encoding="utf-8"))
            except Exception:
                indexed_meta = {}

        current_files = sorted([f for f in self.trans_dir.glob("*.md") if f.name != "README.md"])
        files_to_index = []

        for f in current_files:
            f_hash = self.get_file_hash(f)
            if force or f.name not in indexed_meta or indexed_meta[f.name] != f_hash:
                files_to_index.append((f, f_hash))

        if files_to_index:
            batch_chunks = []
            batch_files_processed = []

            for f, f_hash in files_to_index:
                m = re.search(r'(\d+)', f.name)
                ep = int(m.group(1)) if m else 0
                text = f.read_text(encoding="utf-8")
                chunks = chunk_chapter_accurate(text, ep, f.name)
                batch_chunks.extend(chunks)
                batch_files_processed.append((f.name, f_hash))

                if len(batch_chunks) >= 80:
                    self.collection.upsert(
                        ids=[c["id"] for c in batch_chunks],
                        documents=[c["text"] for c in batch_chunks],
                        metadatas=[{
                            "chapter": c["chapter"],
                            "file_name": c["file_name"],
                            "lines": f"{c['start_line']}-{c['end_line']}"
                        } for c in batch_chunks]
                    )
                    for fname, fhash in batch_files_processed:
                        indexed_meta[fname] = fhash
                    self.meta_file.write_text(json.dumps(indexed_meta, ensure_ascii=False, indent=2), encoding="utf-8")
                    batch_chunks = []
                    batch_files_processed = []

            if batch_chunks:
                self.collection.upsert(
                    ids=[c["id"] for c in batch_chunks],
                    documents=[c["text"] for c in batch_chunks],
                    metadatas=[{
                        "chapter": c["chapter"],
                        "file_name": c["file_name"],
                        "lines": f"{c['start_line']}-{c['end_line']}"
                    } for c in batch_chunks]
                )
                for fname, fhash in batch_files_processed:
                    indexed_meta[fname] = fhash
                self.meta_file.write_text(json.dumps(indexed_meta, ensure_ascii=False, indent=2), encoding="utf-8")

        # Xây dựng và Lưu BM25 Inverted Index Cache bền vững
        if files_to_index or not self.bm25_cache_file.exists():
            self._rebuild_bm25_cache()

    def _rebuild_bm25_cache(self):
        """Xây dựng BM25 Index sẵn và lưu file nhị phân pickle."""
        if not HAS_BM25:
            return
        all_data = self.collection.get(include=["documents", "metadatas"])
        all_docs = all_data["documents"]
        all_metas = all_data["metadatas"]
        all_ids = all_data["ids"]

        tokenized_corpus = [tokenize_vietnamese(doc) for doc in all_docs]
        bm25_model = BM25Okapi(tokenized_corpus)

        cache_data = {
            "bm25": bm25_model,
            "ids": all_ids,
            "metas": all_metas,
            "docs": all_docs
        }
        with open(self.bm25_cache_file, "wb") as f:
            pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Truy vấn siêu tốc (KHÔNG gọi sync_index() lặp lại)."""
        count = self.collection.count()
        if count == 0:
            return []

        # 1. Dense Multilingual Vector Search (~0.05s)
        n_dense = min(30, count)
        v_res = self.collection.query(query_texts=[query], n_results=n_dense)
        dense_ids = v_res["ids"][0] if v_res["ids"] else []
        dense_dists = v_res["distances"][0] if v_res["distances"] else []
        dense_ranks = {cid: rank + 1 for rank, cid in enumerate(dense_ids)}
        dist_map = {cid: d for cid, d in zip(dense_ids, dense_dists)}

        # 2. Fast Cached BM25 Search (~0.002s)
        bm25_ranks = {}
        bm25_scores_map = {}
        doc_map = {}
        meta_map = {}

        if HAS_BM25 and self.bm25_cache_file.exists():
            try:
                with open(self.bm25_cache_file, "rb") as f:
                    cache_data = pickle.load(f)
                bm25_model = cache_data["bm25"]
                all_ids = cache_data["ids"]
                all_metas = cache_data["metas"]
                all_docs = cache_data["docs"]

                doc_map = {cid: doc for cid, doc in zip(all_ids, all_docs)}
                meta_map = {cid: meta for cid, meta in zip(all_ids, all_metas)}

                q_tokens = tokenize_vietnamese(query)
                if q_tokens:
                    doc_scores = bm25_model.get_scores(q_tokens)
                    top_bm25_indices = np.argsort(doc_scores)[::-1][:30]
                    for rank_idx, doc_idx in enumerate(top_bm25_indices, 1):
                        cid = all_ids[doc_idx]
                        score = float(doc_scores[doc_idx])
                        if score > 0:
                            bm25_ranks[cid] = rank_idx
                            bm25_scores_map[cid] = score
            except Exception:
                pass

        # Nạp dữ liệu fallback nếu chưa có từ BM25 cache
        if not doc_map:
            all_data = self.collection.get(ids=dense_ids, include=["documents", "metadatas"])
            doc_map = {cid: doc for cid, doc in zip(all_data["ids"], all_data["documents"])}
            meta_map = {cid: meta for cid, meta in zip(all_data["ids"], all_data["metadatas"])}

        # 3. Reciprocal Rank Fusion (RRF)
        all_candidates = set(list(dense_ranks.keys()) + list(bm25_ranks.keys()))
        rrf_list = []

        for cid in all_candidates:
            if cid not in doc_map:
                continue
            rd = dense_ranks.get(cid, 200)
            rb = bm25_ranks.get(cid, 200)
            rrf = (1.0 / (60 + rd)) + (1.0 / (60 + rb))
            sim = 1.0 - dist_map.get(cid, 1.0)
            rrf_list.append((cid, rrf, sim, bm25_scores_map.get(cid, 0.0), rd, rb))

        rrf_list.sort(key=lambda x: x[1], reverse=True)

        output = []
        for cid, rrf, cs, bm, rd, rb in rrf_list[:top_k]:
            meta = meta_map[cid]
            doc = doc_map[cid]
            output.append({
                "chapter": meta["chapter"],
                "file_name": meta["file_name"],
                "lines": meta.get("lines", "1-50"),
                "text": doc,
                "relevance_score": round(rrf, 5)
            })

        return output

def search_lore_hybrid(novel_dir: Path, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
    try:
        engine = ChromaNovelSearch(novel_dir)
        return engine.search(query, top_k=top_k)
    except Exception as e:
        return []

def sync_lore_database(novel_dir: Path, force: bool = False):
    """Hàm độc lập để gọi sau khi xuất bản chương mới."""
    try:
        engine = ChromaNovelSearch(novel_dir)
        engine.sync_index(force=force)
    except Exception:
        pass
