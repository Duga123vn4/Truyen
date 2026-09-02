# -*- coding: utf-8 -*-
"""
Trợ Lý AI Lore Master & Điều Tra Viên Cốt Truyện V5.0:
- Truy vết bằng chứng cốt truyện đa ngôn ngữ (Hybrid Vector + BM25)
- Đối thoại trả lời câu hỏi cốt truyện với dẫn chứng chính xác từng chương
"""
import sys
import re
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Tuple
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel

from tools.src.core.paths import TOOLS_DIR
from tools.src.core.novel_context import NovelContext
from tools.src.core.ai_client import AIClient

console = Console()

# Tích hợp vector_lore_search
try:
    sys.path.insert(0, str(TOOLS_DIR))
    from vector_lore_search import search_lore_hybrid
    HAS_VECTOR_LORE = True
except Exception:
    HAS_VECTOR_LORE = False

def detect_scene_boundaries(text: str, hit_line_idx: int, max_before: int = 40, max_after: int = 50) -> Tuple[int, int, str]:
    """Cắt trọn vẹn phân cảnh tự nhiên xung quanh dòng tìm thấy."""
    lines = text.splitlines()
    total = len(lines)
    if hit_line_idx < 0 or hit_line_idx >= total:
        return 0, total, text[:2500]

    start_idx = max(0, hit_line_idx - max_before)
    end_idx = min(total, hit_line_idx + max_after)
    return start_idx + 1, end_idx, "\n".join(lines[start_idx:end_idx])

def extract_lore_evidence(novel: NovelContext, query: str) -> List[Dict[str, Any]]:
    """Truy vết bằng chứng từ translated/ và glossary/."""
    evidence = []
    if HAS_VECTOR_LORE:
        try:
            v_res = search_lore_hybrid(novel.folder, query, top_k=6)
            if v_res:
                evidence.extend(v_res)
        except Exception:
            pass

    # Tìm kiếm từ khóa bổ sung nếu vector search ít kết quả
    if len(evidence) < 3:
        q_words = [w.strip() for w in query.lower().split() if len(w.strip()) >= 2]
        for ep, fpath in novel.list_translated_chapters()[-50:]:  # Quét 50 chương gần nhất
            txt = fpath.read_text(encoding="utf-8")
            txt_lower = txt.lower()
            if any(w in txt_lower for w in q_words):
                for line_idx, line in enumerate(txt.splitlines()):
                    if any(w in line.lower() for w in q_words):
                        s, e, snippet = detect_scene_boundaries(txt, line_idx)
                        evidence.append({
                            "chapter": ep,
                            "file_name": fpath.name,
                            "text": snippet,
                            "start_line": s,
                            "end_line": e
                        })
                        break
            if len(evidence) >= 8:
                break

    return evidence

async def run_lore_master(novel: NovelContext, ai: AIClient):
    """Giao diện hội thoại tương tác với AI Lore Master."""
    console.print(Panel.fit(
        f"[bold cyan]🧠 AI LORE MASTER V5.0 — TRỢ LÝ CỐT TRUYỆN DỰ ÁN[/bold cyan]\n"
        f"[bold yellow]Bộ truyện:[/bold yellow] {novel.name} • [bold green]Engine:[/bold green] Hybrid Vector & BM25 Evidence\n"
        "[dim]Nhập câu hỏi cốt truyện hoặc '0' để quay lại menu chính[/dim]",
        border_style="cyan"
    ))

    while True:
        query = Prompt.ask("\n[bold yellow]👉 Nhập câu hỏi cốt truyện[/bold yellow]").strip()
        if not query or query == "0":
            break

        with console.status(f"[bold green]Đang truy vết bằng chứng cốt truyện cho '{query}'...[/bold green]"):
            evidence = extract_lore_evidence(novel, query)

        if not evidence:
            console.print("[yellow]Không tìm thấy đoạn văn bản trực tiếp nào liên quan trong kho lưu trữ.[/yellow]")

        evidence_text = "\n\n".join([
            f"--- BẰNG CHỨNG {idx} (Tập {e.get('chapter', '?')} - Dòng {e.get('start_line', '?')}-{e.get('end_line', '?')} trong {e.get('file_name', '')}) ---\n{e.get('text', '')}"
            for idx, e in enumerate(evidence[:5], 1)
        ])

        system_instruction = (
            "Bạn là AI Lore Master & Điều Tra Viên Cốt Truyện Cao Cấp của bộ Light Novel này.\n"
            "Nhiệm vụ của bạn là giải đáp câu hỏi của người dùng dựa TRÊN BẰNG CHỨNG XÁC THỰC CỐT TRUYỆN được cung cấp.\n"
            "QUY TẮC:\n"
            "1. Luôn trích dẫn chính xác Tập xuất hiện và số dòng làm bằng chứng.\n"
            "2. Phân tích logic tâm lý, quan hệ nhân vật, dòng thời gian sự kiện.\n"
            "3. Không bịa đặt hay suy diễn vượt quá bằng chứng văn bản."
        )

        user_prompt = (
            f"DƯỚI ĐÂY LÀ CÁC ĐOẠN BẰNG CHỨNG VĂN BẢN TRÍCH XUẤT ĐƯỢC:\n\n{evidence_text}\n\n"
            f"CÂU HỎI CỐT TRUYỆN: {query}\n\n"
            "Hãy trả lời chi tiết, mạch lạc và có trích dẫn bằng chứng cụ thể."
        )

        with console.status("[bold cyan]AI đang tổng hợp và phân tích câu trả lời...[/bold cyan]"):
            ans = await ai.generate(system_instruction, user_prompt, temperature=0.2)

        console.print(Panel(ans, title=f"🔍 Giải Đáp: {query}", border_style="green"))
