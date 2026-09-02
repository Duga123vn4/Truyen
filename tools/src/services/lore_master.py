# -*- coding: utf-8 -*-
"""
Trợ Lý AI Lore Master & Điều Tra Viên Cốt Truyện V6.0 (Enterprise):
- Hệ thống Dual-Index: Biên niên sự kiện chính thức (events.md, timeline) + Phân cảnh chương dịch
- Nhận thức dòng thời gian (Chronological / Recency-Aware Weighting)
- Trả lời câu hỏi cốt truyện với dẫn chứng chính xác từng mốc sự kiện và phân cảnh
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
    from vector_lore_search import search_lore_hybrid, detect_temporal_intent
    HAS_VECTOR_LORE = True
except Exception:
    HAS_VECTOR_LORE = False

def extract_lore_evidence(novel: NovelContext, query: str) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Truy vết bằng chứng 2 tầng từ Dual-Index V6.0:
    - Trả về (temporal_intent, list_milestones, list_scene_chunks)
    """
    milestones = []
    scenes = []
    intent = detect_temporal_intent(query) if HAS_VECTOR_LORE else "NEUTRAL"

    if HAS_VECTOR_LORE:
        try:
            raw_results = search_lore_hybrid(novel.folder, query, top_k=12)
            for r in raw_results:
                dtype = r.get("doc_type", "chapter_text")
                if dtype in ("event_milestone", "relationship_milestone"):
                    milestones.append(r)
                else:
                    scenes.append(r)
        except Exception:
            pass

    return intent, milestones[:4], scenes[:5]

async def run_lore_master(novel: NovelContext, ai: AIClient):
    """Giao diện hội thoại tương tác với AI Lore Master V6.0."""
    console.print(Panel.fit(
        f"[bold cyan]🧠 AI LORE MASTER V6.0 (ENTERPRISE) — HỌC GIẢ BÁCH KHOA TOÀN THƯ NOVEL[/bold cyan]\n"
        f"[bold yellow]Bộ truyện:[/bold yellow] {novel.name} • [bold green]Engine:[/bold green] Dual-Index (Milestones + Scenes) & Temporal Reasoning\n"
        "[dim]Nhập câu hỏi cốt truyện hoặc '0' để quay lại menu chính[/dim]",
        border_style="cyan"
    ))

    while True:
        query = Prompt.ask("\n[bold yellow]👉 Nhập câu hỏi cốt truyện[/bold yellow]").strip()
        if not query or query == "0":
            break

        with console.status(f"[bold green]Đang truy vết bằng chứng cốt truyện cho '{query}'...[/bold green]"):
            intent, milestones, scenes = extract_lore_evidence(novel, query)

        # Hiển thị huy hiệu ý định thời gian
        intent_map = {
            "RECENCY": "⏱️ RECENCY (Ưu tiên các tập mới nhất & trạng thái hiện tại)",
            "ORIGIN": "⏳ ORIGIN (Ưu tiên các tập mở đầu & nguồn gốc ban đầu)",
            "NEUTRAL": "⚖️ CHRONOLOGICAL (Phân tích toàn diện dòng thời gian)"
        }
        console.print(f"  [bold magenta]{intent_map.get(intent, intent)}[/bold magenta]")

        if not milestones and not scenes:
            console.print("[yellow]Không tìm thấy đoạn văn bản trực tiếp nào liên quan trong kho lưu trữ.[/yellow]")

        # 1. Bằng chứng mốc sự kiện
        milestone_text = ""
        if milestones:
            milestone_text = "📌 TẦNG 1: CÁC MỐC BIÊN NIÊN SỰ KIỆN CHÍNH THỨC (CANON MILESTONES):\n" + "\n\n".join([
                f"* [Tập {m.get('chapter', 0)} - {m.get('file_name', '')}] (Độ tin cậy: {m.get('relevance_score', 0):.4f}):\n{m.get('text', '').strip()}"
                for m in milestones
            ])

        # 2. Bằng chứng phân cảnh văn bản
        scene_text = ""
        if scenes:
            scene_text = "📖 TẦNG 2: PHÂN CẢNH VĂN BẢN TRÍCH ĐOẠN CHI TIẾT (SCENE EVIDENCE):\n" + "\n\n".join([
                f"* [Tập {s.get('chapter', 0)} - Dòng {s.get('lines', '')} trong {s.get('file_name', '')}] (Điểm: {s.get('relevance_score', 0):.4f}):\n{s.get('text', '').strip()}"
                for s in scenes
            ])

        combined_evidence = f"{milestone_text}\n\n{scene_text}".strip()

        system_instruction = (
            "Bạn là AI Lore Master & Học Giả Cốt Truyện Tối Cao của bộ Light Novel này.\n"
            "Nhiệm vụ của bạn là giải đáp câu hỏi của người dùng dựa TRÊN 2 TẦNG BẰNG CHỨNG XÁC THỰC CỐT TRUYỆN được cung cấp:\n"
            "- Tầng 1: Các mốc biên niên sự kiện chính thức (Canon Milestones)\n"
            "- Tầng 2: Các trích đoạn phân cảnh thực tế trong các chương truyện\n\n"
            "QUY TẮC PHÂN TÍCH:\n"
            "1. TÔN TRỌNG DÒNG THỜI GIAN: Phân biệt rõ sự phát triển tâm lý, quan hệ hoặc kế hoạch của nhân vật qua từng Arc (không nhầm lẫn trạng thái quá khứ với hiện tại).\n"
            "2. TRÍCH DẪN RÕ RÀNG: Luôn ghi rõ thông tin dựa trên Tập số mấy làm bằng chứng cụ thể.\n"
            "3. BẢO TOÀN SỰ THẬT NGUYÊN TÁC: Tuyệt đối không suy diễn vượt quá bằng chứng văn bản."
        )

        user_prompt = (
            f"DƯỚI ĐÂY LÀ DỮ LIỆU TRUY VẾT BẰNG CHỨNG CỐT TRUYỆN:\n\n{combined_evidence}\n\n"
            f"CÂU HỎI CỐT TRUYỆN: {query}\n\n"
            "Hãy trả lời chi tiết, mạch lạc, phân tích chiều sâu cốt truyện và có trích dẫn mốc tập cụ thể."
        )

        with console.status("[bold cyan]AI đang tổng hợp và phân tích câu trả lời chuyên sâu...[/bold cyan]"):
            ans = await ai.generate(system_instruction, user_prompt, temperature=0.2)

        console.print(Panel(ans, title=f"🔍 Giải Đáp: {query}", border_style="green"))
