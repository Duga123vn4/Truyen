# -*- coding: utf-8 -*-
"""
Dịch vụ Trích Xuất & Đồng Bộ Glossary (Glossary Miner & Auto-Sync):
- Trích xuất nhân vật, quái vật, kỹ năng từ Raw
- Tự động phát hiện thực thể mới từ bản dịch tiếng Việt và bổ sung vào terms.md
"""
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
from rich.console import Console

from tools.src.core.novel_context import NovelContext
from tools.src.core.ai_client import AIClient

console = Console()

def auto_sync_glossary_from_translated(novel: NovelContext) -> int:
    """Tự động quét các thuật ngữ trong ngoặc 『...』 trong translated/ để phát hiện từ còn thiếu trong terms.md."""
    terms_file = novel.glossary_dir / "terms.md"
    index_file = novel.glossary_dir / "ENTITY_INDEX.md"

    if not terms_file.exists():
        return 0

    existing_terms_text = terms_file.read_text(encoding="utf-8")
    existing_index_text = index_file.read_text(encoding="utf-8") if index_file.exists() else ""

    found_bracketed = set()
    for ch_num, fpath in novel.list_translated_chapters():
        text = fpath.read_text(encoding="utf-8")
        matches = re.findall(r'『([^』]+)』', text)
        for m in matches:
            m_clean = m.strip()
            if len(m_clean) >= 2 and len(m_clean) <= 40:
                found_bracketed.add(m_clean)

    added_count = 0
    new_cards = []

    for term in sorted(found_bracketed):
        # Kiểm tra xem thuật ngữ đã có trong terms.md chưa
        if term not in existing_terms_text:
            # Xác định phân loại sơ bộ
            t_lower = term.lower()
            if any(k in t_lower for k in ["chú", "thuật", "pháp", "kỹ", "trảm", "kiếm", "bước", "hóa"]):
                cat_id = "SKILL"
                cat_name = "KỸ NĂNG / MA PHÁP"
            elif any(k in t_lower for k in ["kiếm", "đao", "thương", "cọc", "bom", "thuốc", "bình", "giáp", "xe"]):
                cat_id = "ITEM"
                cat_name = "VẬT PHẨM / TRANG BỊ"
            else:
                cat_id = "TERM"
                cat_name = "THUẬT NGỮ THẾ GIỚI"

            card_count = len(re.findall(rf'\[{cat_id}-\d+\]', existing_terms_text + "\n".join(new_cards))) + 1
            eid = f"{cat_id}-{card_count:03d}"

            card = (
                f"\n---\n\n"
                f"## [{eid}] 『{term}』\n\n"
                f"- **id:** {eid}\n"
                f"- **loại:** {cat_name}\n"
                f"- **tên_chuẩn:** 『{term}』\n"
                f"- **trạng_thái:** TỰ ĐỘNG PHÁT HIỆN\n"
                f"- **canon:** DỰ KIẾN\n"
                f"- **độ_tin_cậy:** CAO\n"
                f"- **khóa_bảo_vệ:** CÓ\n"
                f"- **nguồn:** Toàn văn bản dịch\n"
                f"- **mô_tả:** Thực thể được hệ thống Auto-Sync phát hiện tự động từ văn bản dịch Light Novel.\n"
            )
            new_cards.append(card)
            added_count += 1

    if new_cards:
        updated_terms = existing_terms_text.rstrip() + "\n" + "".join(new_cards)
        terms_file.write_text(updated_terms, encoding="utf-8")
        console.print(f"[bold green]✨ Đã tự động phát hiện và bổ sung {added_count} thẻ thực thể mới vào terms.md![/bold green]")

    return added_count
