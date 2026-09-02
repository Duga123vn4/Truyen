# -*- coding: utf-8 -*-
"""
Dịch vụ Biên Tập Chuyên Sâu Bằng AI (Deep Editor Engine):
- Nạp đầy đủ Canon Database V3.0 kích hoạt Prompt Caching
- Chuốt văn phong thuần Light Novel, bảo toàn 100% cốt truyện
- Tự động sao lưu bản gốc vào backups/truoc_bien_tap/
- Xuất báo cáo kiểm chứng DIFF_REPORT.md
"""
import re
import time
import asyncio
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List
from rich.console import Console
from rich.prompt import Prompt, Confirm

from tools.src.core.paths import MASTER_STYLE_GUIDE_FILE, DEEP_EDITOR_PROMPT_FILE
from tools.src.core.ai_client import AIClient
from tools.src.core.novel_context import NovelContext
from tools.src.core.notifications import notify_completion
from tools.src.services.smart_filter import extract_relevant_glossary
from tools.src.services.diff_studio import analyze_chapter_diff, generate_diff_report, generate_diff_data

console = Console()

async def edit_single_chapter(
    chapter_num: int,
    file_path: Path,
    novel: NovelContext,
    ai: AIClient,
    sem: asyncio.Semaphore
) -> Tuple[bool, int, Path, str, Optional[Dict[str, Any]]]:
    """Biên tập chuyên sâu 1 chương truyện độc lập bằng AI."""
    async with sem:
        try:
            original_text = file_path.read_text(encoding="utf-8")
            orig_len = len(original_text.strip())
            if orig_len == 0:
                return (False, chapter_num, file_path, "File rỗng", None)

            characters_ctx = novel.get_characters_text()
            terms_ctx = novel.get_terms_text()
            style_ctx = novel.get_style_guide_text()

            glossary_mode = ai.config.get("glossary_mode", "full_cache")
            master_rules = MASTER_STYLE_GUIDE_FILE.read_text(encoding="utf-8") if MASTER_STYLE_GUIDE_FILE.exists() else (
                "QUY TẮC BIÊN TẬP BẮT BUỘC: Bảo toàn 100% dữ kiện nguyên tác, tuân thủ Glossary, không tự ý phóng tác."
            )

            if glossary_mode == "full_cache":
                canon_text = novel.get_full_canon_text()
            else:
                filtered_chars, filtered_terms = extract_relevant_glossary(original_text, characters_ctx, terms_ctx)
                canon_text = f"--- TỪ ĐIỂN NHÂN VẬT & XƯNG HÔ ---\n{filtered_chars}\n\n--- TỪ ĐIỂN THUẬT NGỮ & KỸ NĂNG ---\n{filtered_terms}"

            if DEEP_EDITOR_PROMPT_FILE.exists():
                template = DEEP_EDITOR_PROMPT_FILE.read_text(encoding="utf-8")
                system_prompt = template.replace("{{MASTER_RULES}}", master_rules)
                system_prompt = system_prompt.replace("{{CANON_DATABASE}}", canon_text)
                system_prompt = system_prompt.replace("{{STYLE_GUIDE}}", style_ctx)
            else:
                system_prompt = (
                    "Bạn là Chuyên gia Dịch thuật & Biên tập viên Cao cấp chuyên chuẩn hóa Light Novel tiếng Nhật sang tiếng Việt.\n\n"
                    f"{master_rules}\n\n"
                    "================================================================================\n"
                    "DƯỚI ĐÂY LÀ TOÀN BỘ CANON DATABASE V3.0 CỦA TÁC PHẨM NÀY:\n"
                    "================================================================================\n\n"
                    f"{canon_text}\n\n"
                    f"--- ĐỊNH HƯỚNG PHONG CÁCH RIÊNG CỦA BỘ TRUYỆN ---\n{style_ctx}\n"
                )

            user_prompt = f"Dưới đây là nội dung chương {chapter_num} cần biên tập lại chuẩn chỉ 100%:\n\n{original_text}"

            for attempt in range(2):
                result = await ai.generate(
                    system_prompt,
                    user_prompt,
                    temperature=0.15,
                    chapter_title=f"Tập {chapter_num}",
                    chapter_ep=chapter_num
                )
                if not result:
                    await asyncio.sleep(1.5)
                    continue
                result = result.strip()
                result = re.sub(r'^(?:dưới đây là|đây là bản|sau khi biên tập|toàn văn chương)[^\n]*\n+', '', result, flags=re.IGNORECASE).strip()
                result = re.sub(r'^\s*[\*\-_]{3,}\s*\n+', '', result).strip()
                res_len = len(result)

                if result == original_text.strip():
                    return (True, chapter_num, file_path, "✨ Không có thay đổi (Nội dung đã chuẩn chỉ 100%)", None)

                if res_len >= orig_len * 0.85:
                    diff_info = analyze_chapter_diff(original_text, result)
                    if diff_info["diff_len"] == 0 and not diff_info.get("sample_diffs") and result == original_text:
                        return (True, chapter_num, file_path, "✨ Không có thay đổi (Nội dung đã chuẩn chỉ 100%)", None)

                    # Sao lưu tự động
                    novel.backup_edit_dir.mkdir(parents=True, exist_ok=True)
                    bak_file = novel.backup_edit_dir / file_path.name
                    if not bak_file.exists():
                        bak_file.write_text(original_text, encoding="utf-8")

                    file_path.write_text(result, encoding="utf-8")
                    return (True, chapter_num, file_path, f"Xong ({orig_len} -> {res_len} ký tự, {diff_info['ratio']:.1f}%)", diff_info)

            return (False, chapter_num, file_path, "Nội dung phản hồi bị ngắn bất thường", None)
        except Exception as e:
            return (False, chapter_num, file_path, str(e), None)
