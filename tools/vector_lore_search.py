# -*- coding: utf-8 -*-
"""
🧠 NOVEL AI — MULTILINGUAL HYBRID VECTOR & CACHED BM25 LORE SEARCH ENGINE V6.0 (ENTERPRISE)
- Dual-Index Architecture: Synchronized Chapter Scenes & Canon Milestone Events (events.md, timeline)
- Chronological & Temporal Awareness: Automatic Intent Detection (RECENCY vs. ORIGIN vs. NEUTRAL)
- Offline Sentence Transformers (paraphrase-multilingual-MiniLM-L12-v2) + Persistent Cached BM25Okapi
- Exact 1-based Line Tracker & Anchor Grounding
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
from typing import List, Dict, Any, Optional, Tuple

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
    "này", "đó", "được", "bị", "là", "đã", "đang", "sẽ", "thì", "mà", "nhưng", "về", "như"
}

RECENCY_KEYWORDS = [
    "hiện tại", "bây giờ", "mới nhất", "gần đây", "sau cùng", "sau khi",
    "kết cục", "trước mắt", "sau đó", "cuối cùng", "tình hình bây giờ",
    "đang như thế nào", "hiện giờ", "gần nhất", "tập mới"
]

ORIGIN_KEYWORDS = [
    "ban đầu", "lúc đầu", "quá khứ", "nguồn gốc", "khởi đầu", "tại sao bị",
    "lý do vì sao", "lần đầu", "trước đây", "thời gian đầu", "xuất thân"
]

def detect_temporal_intent(query: str) -> str:
    """Tự động nhận diện ý định thời gian trong câu hỏi của người dùng."""
    q_lower = query.lower()
    if any(k in q_lower for k in RECENCY_KEYWORDS):
        return "RECENCY"
    if any(k in q_lower for k in ORIGIN_KEYWORDS):
        return "ORIGIN"
    return "NEUTRAL"

def tokenize_vietnamese(text: str) -> List[str]:
    """Tách từ tiếng Việt và loại bỏ hư từ (stopwords)."""
    words = re.findall(r'\w+', text.lower())
    return [w for w in words if len(w) >= 2 and w not in STOPWORDS]

def chunk_chapter_accurate(text: str, ep: int, file_name: str, target_words: int = 250) -> List[Dict[str, Any]]:
    """Chia phân đoạn chuẩn xác theo từng dòng thực tế của file chương dịch."""
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
                    "doc_type": "chapter_text",
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
            "doc_type": "chapter_text",
            "chunk_idx": len(chunks),
            "text": "\n".join(curr_lines),
            "start_line": start_line,
            "end_line": len(lines)
        })
    return chunks

def chunk_glossary_events(glossary_dir: Path) -> List[Dict[str, Any]]:
    """Trích xuất toàn bộ các mốc sự kiện từ events.md và relationship_timeline.md thành Milestone Chunks."""
    chunks = []
    events_file = glossary_dir / "events.md"
    timeline_file = glossary_dir / "relationship_timeline.md"

    if events_file.exists():
        lines = events_file.read_text(encoding="utf-8").splitlines()
        # 1. Quét các dòng bảng: | **Tập 196** | • Hayama Ritsuki... | ... | ... |
        for idx, line in enumerate(lines, 1):
            m_table = re.search(r'\|\s*\*\*Tập\s*(\d+)\*\*\s*\|\s*(.*?)\|\s*(.*?)\|\s*(.*?)\|', line)
            if m_table:
                ep = int(m_table.group(1))
                summary = m_table.group(2).replace('<br>', '\n').strip()
                chars = m_table.group(3).strip()
                loc = m_table.group(4).strip()
                chunk_text = f"【MỐC SỰ KIỆN TẬP {ep}】\n- Diễn biến: {summary}\n- Nhân vật trọng tâm: {chars}\n- Địa điểm: {loc}"
                chunks.append({
                    "id": f"event_milestone_table_ch{ep}_{idx}",
                    "chapter": ep,
                    "file_name": "events.md",
                    "doc_type": "event_milestone",
                    "chunk_idx": len(chunks),
                    "text": chunk_text,
                    "start_line": idx,
                    "end_line": idx
                })

        # 2. Quét các mục Header: ### Tập 200:\n- ...\n- ...
        full_text = "\n".join(lines)
        header_blocks = re.finditer(r'### Tập (\d+):?\s*\n((?:- [^\n]+\n?)+)', full_text)
        for m_sec in header_blocks:
            ep = int(m_sec.group(1))
            sec_text = m_sec.group(2).strip()
            chunk_text = f"【MỐC SỰ KIỆN TẬP {ep}】\n{sec_text}"
            chunks.append({
                "id": f"event_milestone_sec_ch{ep}_{len(chunks)}",
                "chapter": ep,
                "file_name": "events.md",
                "doc_type": "event_milestone",
                "chunk_idx": len(chunks),
                "text": chunk_text,
                "start_line": 1,
                "end_line": 1
            })

    if timeline_file.exists():
        t_text = timeline_file.read_text(encoding="utf-8")
        rel_blocks = re.finditer(r'### \d+\.\s*👥\s*([^\n]+)\s*\n((?:\* \*\*Tập [^\n]+\n?)+)', t_text)
        for m_rel in rel_blocks:
            pair = m_rel.group(1).strip()
            stages = m_rel.group(2).strip()
            chunk_text = f"【DÒNG TIẾN TRÌNH QUAN HỆ & XƯNG HÔ】\nNhân vật: {pair}\n{stages}"
            chunks.append({
                "id": f"rel_milestone_{len(chunks)}",
                "chapter": 0,
                "file_name": "relationship_timeline.md",
                "doc_type": "relationship_milestone",
                "chunk_idx": len(chunks),
                "text": chunk_text,
                "start_line": 1,
                "end_line": 1
            })

    return chunks

class ChromaNovelSearch:
    def __init__(self, novel_dir: Path):
        self.novel_dir = novel_dir
        self.trans_dir = novel_dir / "translated"
        self.glossary_dir = novel_dir / "glossary"
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
        """Đồng bộ song song cả chương truyện dịch (translated/) và các mốc sự kiện (glossary/)."""
        indexed_meta = {}
        if self.meta_file.exists() and not force:
            try:
                indexed_meta = json.loads(self.meta_file.read_text(encoding="utf-8"))
            except Exception:
                indexed_meta = {}

        # 1. Đồng bộ các file chương dịch
        current_files = sorted([f for f in self.trans_dir.glob("*.md") if f.name != "README.md"])
        files_to_index = []

        for f in current_files:
            f_hash = self.get_file_hash(f)
            if force or f.name not in indexed_meta or indexed_meta[f.name] != f_hash:
                files_to_index.append((f, f_hash))

        # 2. Đồng bộ các mốc sự kiện trong glossary/
        glossary_files = [self.glossary_dir / "events.md", self.glossary_dir / "relationship_timeline.md"]
        sync_glossary = False
        for gf in glossary_files:
            if gf.exists():
                g_hash = self.get_file_hash(gf)
                if force or gf.name not in indexed_meta or indexed_meta[gf.name] != g_hash:
                    sync_glossary = True
                    indexed_meta[gf.name] = g_hash

        has_updates = bool(files_to_index or sync_glossary)

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
                            "doc_type": c.get("doc_type", "chapter_text"),
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
                        "doc_type": c.get("doc_type", "chapter_text"),
                        "lines": f"{c['start_line']}-{c['end_line']}"
                    } for c in batch_chunks]
                )
                for fname, fhash in batch_files_processed:
                    indexed_meta[fname] = fhash
                self.meta_file.write_text(json.dumps(indexed_meta, ensure_ascii=False, indent=2), encoding="utf-8")

        # Nạp các mốc sự kiện từ events.md & timeline
        if sync_glossary:
            event_chunks = chunk_glossary_events(self.glossary_dir)
            if event_chunks:
                self.collection.upsert(
                    ids=[c["id"] for c in event_chunks],
                    documents=[c["text"] for c in event_chunks],
                    metadatas=[{
                        "chapter": c["chapter"],
                        "file_name": c["file_name"],
                        "doc_type": c["doc_type"],
                        "lines": f"{c['start_line']}-{c['end_line']}"
                    } for c in event_chunks]
                )
            self.meta_file.write_text(json.dumps(indexed_meta, ensure_ascii=False, indent=2), encoding="utf-8")

        # Tái tạo BM25 Cache nếu có cập nhật
        if has_updates or not self.bm25_cache_file.exists():
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

    def search(self, query: str, top_k: int = 10, temporal_override: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Truy vấn kết hợp Hybrid Vector + BM25 với cơ chế Nhận Diện Ý Định Thời Gian V6.0:
        - RECENCY: Ưu tiên các chương tập mới nhất
        - ORIGIN: Ưu tiên các chương mở đầu nguyên nhân
        - NEUTRAL: Cân bằng RRF
        """
        count = self.collection.count()
        if count == 0:
            return []

        temporal_intent = temporal_override or detect_temporal_intent(query)

        # 1. Dense Multilingual Vector Search (~0.05s)
        n_dense = min(40, count)
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
                    top_bm25_indices = np.argsort(doc_scores)[::-1][:40]
                    for rank_idx, doc_idx in enumerate(top_bm25_indices, 1):
                        cid = all_ids[doc_idx]
                        score = float(doc_scores[doc_idx])
                        if score > 0:
                            bm25_ranks[cid] = rank_idx
                            bm25_scores_map[cid] = score
            except Exception:
                pass

        if not doc_map:
            all_data = self.collection.get(ids=dense_ids, include=["documents", "metadatas"])
            doc_map = {cid: doc for cid, doc in zip(all_data["ids"], all_data["documents"])}
            meta_map = {cid: meta for cid, meta in zip(all_data["ids"], all_data["metadatas"])}

        # 3. Reciprocal Rank Fusion kết hợp Temporal Weighting V6.0
        all_candidates = set(list(dense_ranks.keys()) + list(bm25_ranks.keys()))
        rrf_list = []

        # Xác định số tập lớn nhất để chuẩn hóa trọng số
        max_ep = max([m.get("chapter", 1) for m in meta_map.values()] or [357])

        for cid in all_candidates:
            if cid not in doc_map:
                continue
            rd = dense_ranks.get(cid, 200)
            rb = bm25_ranks.get(cid, 200)
            base_rrf = (1.0 / (60 + rd)) + (1.0 / (60 + rb))

            meta = meta_map[cid]
            ep = meta.get("chapter", 0)
            doc_type = meta.get("doc_type", "chapter_text")

            # Áp dụng trọng số thời gian (Temporal Weighting)
            temporal_boost = 1.0
            if temporal_intent == "RECENCY" and ep > 0:
                temporal_boost = 1.0 + 0.75 * (ep / max_ep)
            elif temporal_intent == "ORIGIN" and ep > 0:
                temporal_boost = 1.0 + 0.75 * max(0.0, (60 - ep) / 60.0)
            
            # Thưởng điểm neo (Anchor Bonus) cho các mốc sự kiện chính thức
            if doc_type in ("event_milestone", "relationship_milestone"):
                temporal_boost *= 1.25

            final_score = base_rrf * temporal_boost
            rrf_list.append((cid, final_score, base_rrf, doc_type, ep))

        rrf_list.sort(key=lambda x: x[1], reverse=True)

        output = []
        for cid, final_score, base_rrf, doc_type, ep in rrf_list[:top_k]:
            meta = meta_map[cid]
            doc = doc_map[cid]
            output.append({
                "chapter": meta["chapter"],
                "file_name": meta["file_name"],
                "doc_type": doc_type,
                "lines": meta.get("lines", "1-50"),
                "text": doc,
                "relevance_score": round(final_score, 5),
                "temporal_intent": temporal_intent
            })

        return output

def search_lore_hybrid(novel_dir: Path, query: str, top_k: int = 10, temporal_override: Optional[str] = None) -> List[Dict[str, Any]]:
    """Cổng kết nối tiêu chuẩn tra cứu Lore Master V6.0."""
    try:
        engine = ChromaNovelSearch(novel_dir)
        return engine.search(query, top_k=top_k, temporal_override=temporal_override)
    except Exception as e:
        return []

def sync_lore_database(novel_dir: Path, force: bool = False):
    """Hàm đồng bộ database độc lập sau khi xuất bản chương mới."""
    try:
        engine = ChromaNovelSearch(novel_dir)
        engine.sync_index(force=force)
    except Exception:
        pass
