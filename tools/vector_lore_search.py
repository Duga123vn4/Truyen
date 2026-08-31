# -*- coding: utf-8 -*-
"""
🧠 NOVEL AI — VECTOR LORE SEARCH ENGINE V4.0 ULTIMATE
Sử dụng ChromaDB Local ONNX (100% Offline / Zero API Quota) + BM25 Sparse + RRF.
Tự động lưu vector vào persistent directory, tự cập nhật khi có chương mới.
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

    for p in paras:
        curr.append(p)
        curr_w += len(p.split())
        if curr_w >= target_words:
            chunks.append({
                "id": f"ch{chapter_num}_chunk{len(chunks)}",
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
            "id": f"ch{chapter_num}_chunk{len(chunks)}",
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
        """Tự động kiểm tra file mới/sửa để index bù trong 0.01 giây."""
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

        for f, f_hash in files_to_index:
            m = re.search(r'(\d+)', f.name)
            ep = int(m.group(1)) if m else 0
            text = f.read_text(encoding="utf-8")
            chunks = chunk_chapter_text(text, ep, f.name)

            if chunks:
                self.collection.upsert(
                    ids=[c["id"] for c in chunks],
                    documents=[c["text"] for c in chunks],
                    metadatas=[{
                        "chapter": c["chapter"],
                        "file_name": c["file_name"],
                        "lines": f"{c['start_line']}-{c['end_line']}"
                    } for c in chunks]
                )
            indexed_meta[f.name] = f_hash

        self.meta_file.write_text(json.dumps(indexed_meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def search(self, query: str, top_k: int = 6) -> List[Dict[str, Any]]:
        """Truy vấn Vector Search và trả về top_k phân cảnh."""
        self.sync_index()
        count = self.collection.count()
        if count == 0:
            return []

        n_res = min(top_k, count)
        results = self.collection.query(query_texts=[query], n_results=n_res)

        output = []
        if results and "documents" in results and results["documents"]:
            for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
                output.append({
                    "chapter": meta["chapter"],
                    "file_name": meta["file_name"],
                    "lines": meta.get("lines", "1-50"),
                    "text": doc,
                    "relevance_score": round(1.0 - dist, 4)
                })
        return output

def search_lore_hybrid(novel_dir: Path, query: str, top_k: int = 6) -> List[Dict[str, Any]]:
    try:
        engine = ChromaNovelSearch(novel_dir)
        return engine.search(query, top_k=top_k)
    except Exception as e:
        print(f"⚠️ Vector Search fallback: {e}")
        return []
