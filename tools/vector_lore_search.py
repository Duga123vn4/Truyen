# -*- coding: utf-8 -*-
"""
🧠 NOVEL AI — HYBRID VECTOR & BM25 LORE SEARCH ENGINE V4.0 ULTIMATE
Kết hợp Dense Vector (ChromaDB Local ONNX) + Sparse BM25 + Reciprocal Rank Fusion (RRF).
Tự động lưu Vector Cache bền vững, tự đồng bộ khi có chương mới.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import os
import re
import json
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Any

try:
    import chromadb
    from chromadb.utils import embedding_functions
    import numpy as np
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

def chunk_chapter_text(text: str, chapter_num: int, file_name: str, target_words: int = 250) -> List[Dict[str, Any]]:
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    curr = []
    curr_w = 0
    start_line = 1
    curr_line = 1
    f_stem = Path(file_name).stem

    for p in paras:
        curr.append(p)
        curr_w += len(p.split())
        if curr_w >= target_words:
            chunks.append({
                "id": f"{f_stem}_chunk{len(chunks)}",
                "chapter": chapter_num,
                "file_name": file_name,
                "chunk_idx": len(chunks),
                "text": "\n\n".join(curr),
                "start_line": start_line,
                "end_line": curr_line + p.count("\n")
            })
            curr, curr_w = [], 0
            start_line = curr_line + p.count("\n") + 2
        curr_line += p.count("\n") + 2

    if curr:
        chunks.append({
            "id": f"{f_stem}_chunk{len(chunks)}",
            "chapter": chapter_num,
            "file_name": file_name,
            "chunk_idx": len(chunks),
            "text": "\n\n".join(curr),
            "start_line": start_line,
            "end_line": curr_line
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

        self.client = chromadb.PersistentClient(path=str(self.db_dir))
        self.ef = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name=f"novel_{novel_dir.name.lower()}",
            embedding_function=self.ef
        )
        self.meta_file = self.db_dir / "indexed_files.json"
        self.sync_index()

    def get_file_hash(self, path: Path) -> str:
        h = hashlib.sha256()
        h.update(path.read_bytes())
        return h.hexdigest()

    def sync_index(self):
        """Tự động kiểm tra file mới/sửa để index bù siêu tốc theo batch."""
        indexed_meta = {}
        if self.meta_file.exists():
            try:
                indexed_meta = json.loads(self.meta_file.read_text(encoding="utf-8"))
            except Exception:
                indexed_meta = {}

        current_files = sorted([f for f in self.trans_dir.glob("*.md") if f.name != "README.md"])
        files_to_index = []

        for f in current_files:
            f_hash = self.get_file_hash(f)
            if f.name not in indexed_meta or indexed_meta[f.name] != f_hash:
                files_to_index.append((f, f_hash))

        if not files_to_index:
            return

        batch_chunks = []
        batch_files_processed = []

        for f, f_hash in files_to_index:
            m = re.search(r'(\d+)', f.name)
            ep = int(m.group(1)) if m else 0
            text = f.read_text(encoding="utf-8")
            chunks = chunk_chapter_text(text, ep, f.name)
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

    def search(self, query: str, top_k: int = 6) -> List[Dict[str, Any]]:
        """Truy vấn Hybrid Search (Chroma Dense Vector + BM25 Sparse + RRF)."""
        self.sync_index()
        count = self.collection.count()
        if count == 0:
            return []

        # 1. Dense Vector Query
        n_dense = min(30, count)
        v_res = self.collection.query(query_texts=[query], n_results=n_dense)

        # 2. Sparse BM25 Query
        stopwords = {"và", "với", "của", "cho", "bởi", "trong", "ở", "tại", "những", "các", "một", "này", "đó", "được", "bị", "là", "đã", "đang", "sẽ"}
        q_words = [w.lower() for w in re.split(r'\s+', query) if len(w) >= 2 and w.lower() not in stopwords]

        synonyms = {
            "tỏ tình": ["tỏ tình", "ngỏ lời", "bày tỏ", "tiến tới", "yêu đương", "tâm tư", "thích"],
            "từ chối": ["từ chối", "bác bỏ", "không chấp nhận", "không có cửa", "lệnh cấm yêu", "luật cấm yêu"],
            "yêu": ["yêu đương", "tình cảm", "tỏ tình", "lệnh cấm yêu", "luật cấm yêu"]
        }
        expanded_words = set(q_words)
        for qw in q_words:
            for syn_key, syn_list in synonyms.items():
                if qw in syn_key or syn_key in qw:
                    expanded_words.update(syn_list)

        all_data = self.collection.get(include=["documents", "metadatas"])
        all_docs = all_data["documents"]
        all_metas = all_data["metadatas"]
        all_ids = all_data["ids"]

        N = len(all_docs)
        doc_lens = [len(d.split()) for d in all_docs]
        avgdl = sum(doc_lens) / N if N > 0 else 1.0
        k1, b = 1.5, 0.75

        doc_lowers = [d.lower() for d in all_docs]
        df_map = {}
        for w in expanded_words:
            df_map[w] = sum(1 for dl in doc_lowers if w in dl)

        bm25_scores = {}
        for idx, cid in enumerate(all_ids):
            dl = doc_lowers[idx]
            clen = doc_lens[idx]
            score = 0.0
            for w in expanded_words:
                tf = dl.count(w)
                if tf > 0:
                    df = df_map[w]
                    idf = np.log((N - df + 0.5) / (df + 0.5) + 1.0)
                    score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (clen / avgdl)))
            bm25_scores[cid] = score

        # 3. Reciprocal Rank Fusion (RRF)
        dense_ranks = {cid: rank + 1 for rank, cid in enumerate(v_res["ids"][0])}
        bm25_ranked_ids = sorted(bm25_scores.keys(), key=lambda x: bm25_scores[x], reverse=True)
        bm25_ranks = {cid: rank + 1 for rank, cid in enumerate(bm25_ranked_ids)}

        all_candidates = set(list(dense_ranks.keys()) + list(bm25_ranked_ids[:30]))
        rrf_list = []
        dist_map = {cid: d for cid, d in zip(v_res["ids"][0], v_res["distances"][0])}
        doc_map = {cid: doc for cid, doc in zip(all_ids, all_docs)}
        meta_map = {cid: meta for cid, meta in zip(all_ids, all_metas)}

        for cid in all_candidates:
            rd = dense_ranks.get(cid, 200)
            rb = bm25_ranks.get(cid, 200)
            rrf = (1.0 / (60 + rd)) + (1.0 / (60 + rb))
            sim = 1.0 - dist_map.get(cid, 1.0)
            rrf_list.append((cid, rrf, sim, bm25_scores.get(cid, 0.0), rd, rb))

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

def search_lore_hybrid(novel_dir: Path, query: str, top_k: int = 6) -> List[Dict[str, Any]]:
    try:
        engine = ChromaNovelSearch(novel_dir)
        return engine.search(query, top_k=top_k)
    except Exception as e:
        return []
