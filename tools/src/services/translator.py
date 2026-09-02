# -*- coding: utf-8 -*-
"""
Dịch vụ Dịch Thuật AI & Sinh Ảnh Minh Họa:
- Dịch Raw (tiếng Nhật / convert) sang tiếng Việt văn phong Light Novel
- Đồng bộ Glossary tự động trong quá trình dịch
- Sinh ảnh minh họa Anime FLUX/Imagen cho từng chương
"""
import re
import asyncio
import httpx
import urllib.parse
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List
from rich.console import Console

from tools.src.core.paths import MASTER_STYLE_GUIDE_FILE
from tools.src.core.novel_context import NovelContext
from tools.src.core.ai_client import AIClient
from tools.src.services.smart_filter import extract_relevant_glossary

console = Console()

def build_translation_system_prompt(novel: NovelContext, raw_text: str, glossary_mode: str = "full_cache") -> str:
    """Xây dựng System Prompt dịch thuật chuẩn chỉ nạp Canon Database."""
    master_rules = MASTER_STYLE_GUIDE_FILE.read_text(encoding="utf-8") if MASTER_STYLE_GUIDE_FILE.exists() else (
        "QUY TẮC DỊCH THUẬT BẮT BUỘC: Dịch tự nhiên sang tiếng Việt, bảo toàn 100% tình tiết, tuân thủ Glossary."
    )
    style_ctx = novel.get_style_guide_text()

    if glossary_mode == "full_cache":
        full_canon = novel.get_full_canon_text()
        return (
            "Bạn là Chuyên gia Dịch thuật Cao cấp chuyên chuyển ngữ Light Novel tiếng Nhật sang tiếng Việt.\n\n"
            f"{master_rules}\n\n"
            "================================================================================\n"
            "DƯỚI ĐÂY LÀ TOÀN BỘ CANON DATABASE V3.0 CỦA TÁC PHẨM NÀY:\n"
            "================================================================================\n\n"
            f"{full_canon}\n\n"
            f"--- ĐỊNH HƯỚNG PHONG CÁCH RIÊNG CỦA BỘ TRUYỆN ---\n{style_ctx}\n"
        )
    else:
        filtered_chars, filtered_terms = extract_relevant_glossary(raw_text, novel.get_characters_text(), novel.get_terms_text())
        return (
            "Bạn là Chuyên gia Dịch thuật Cao cấp chuyên chuyển ngữ Light Novel tiếng Nhật sang tiếng Việt.\n\n"
            f"{master_rules}\n\n"
            "================================================================================\n"
            "DƯỚI ĐÂY LÀ TỪ ĐIỂN GLOSSARY TINH GỌN CỦA CHƯƠNG NÀY:\n"
            "================================================================================\n\n"
            f"--- TỪ ĐIỂN NHÂN VẬT & XƯNG HÔ ---\n{filtered_chars}\n\n"
            f"--- TỪ ĐIỂN THUẬT NGỮ & KỸ NĂNG ---\n{filtered_terms}\n\n"
            f"--- PHONG CÁCH VĂN PHONG ---\n{style_ctx}\n"
        )

async def translate_chapter(
    raw_path: Path,
    novel: NovelContext,
    ai: AIClient,
    chapter_num: int,
    sem: asyncio.Semaphore
) -> Tuple[bool, int, Path, str]:
    """Dịch 1 chương raw sang tiếng Việt."""
    async with sem:
        try:
            raw_text = raw_path.read_text(encoding="utf-8").strip()
            if not raw_text:
                return (False, chapter_num, raw_path, "File raw rỗng")

            glossary_mode = ai.config.get("glossary_mode", "full_cache")
            sys_prompt = build_translation_system_prompt(novel, raw_text, glossary_mode)
            user_prompt = f"Dưới đây là nội dung chương {chapter_num} (raw) cần dịch sang tiếng Việt:\n\n{raw_text}"

            for attempt in range(2):
                translated = await ai.generate(
                    sys_prompt,
                    user_prompt,
                    temperature=0.3,
                    chapter_title=f"Tập {chapter_num}",
                    chapter_ep=chapter_num
                )
                if not translated:
                    await asyncio.sleep(1.5)
                    continue

                translated = translated.strip()
                translated = re.sub(r'^(?:dưới đây là|đây là bản|bản dịch)[^\n]*\n+', '', translated, flags=re.IGNORECASE).strip()
                
                # Lưu file dịch
                out_name = f"chuong_{chapter_num}_{raw_path.stem}.md" if not raw_path.name.startswith("chuong_") else raw_path.name
                out_path = novel.translated_dir / out_name
                out_path.write_text(translated, encoding="utf-8")
                return (True, chapter_num, out_path, f"Dịch thành công ({len(translated)} ký tự)")

            return (False, chapter_num, raw_path, "Không nhận được bản dịch hợp lệ từ AI")
        except Exception as e:
            return (False, chapter_num, raw_path, str(e))

async def generate_anime_illustration(prompt: str, out_path: Path, width: int = 768, height: int = 1024) -> bool:
    """Sinh ảnh minh họa anime phong cách Light Novel bằng Pollinations FLUX Engine (Miễn phí 100%)."""
    clean_p = urllib.parse.quote(f"masterpiece, anime artwork, high quality, light novel illustration, {prompt}")
    url = f"https://image.pollinations.ai/prompt/{clean_p}?width={width}&height={height}&model=flux&nologo=true&seed=42"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.get(url)
            if res.status_code == 200:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(res.content)
                return True
    except Exception:
        pass
    return False
