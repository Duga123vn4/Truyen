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
from tools.src.services.reorganize_glossary import is_noise_term, rebuild_entity_index

console = Console()

def auto_sync_glossary_from_translated(novel: NovelContext) -> int:
    """Tự động quét các thuật ngữ trong ngoặc 『...』 trong translated/ để phát hiện từ còn thiếu trong terms.md."""
    terms_file = novel.glossary_dir / "terms.md"
    factions_file = novel.glossary_dir / "factions_orgs.md"
    chars_file = novel.glossary_dir / "characters.md"

    if not terms_file.exists():
        return 0

    existing_terms_text = terms_file.read_text(encoding="utf-8")
    existing_factions_text = factions_file.read_text(encoding="utf-8") if factions_file.exists() else ""
    existing_chars_text = chars_file.read_text(encoding="utf-8") if chars_file.exists() else ""

    all_existing_text = (existing_terms_text + existing_factions_text + existing_chars_text).lower()

    found_bracketed = set()
    for ch_num, fpath in novel.list_translated_chapters():
        text = fpath.read_text(encoding="utf-8")
        matches = re.findall(r'『([^』]+)』', text)
        for m in matches:
            m_clean = m.strip()
            if not is_noise_term(m_clean):
                found_bracketed.add(m_clean)

    added_count = 0
    new_terms_cards = []
    new_chars_cards = []
    new_factions_cards = []

    for term in sorted(found_bracketed):
        if term.lower() not in all_existing_text:
            t_lower = term.lower()
            if any(k in t_lower for k in ["dũng giả", "ma vương", "thánh nữ", "công chúa", "hiền giả", "hoàng tử", "quân vương", "kiếm hào", "hầu gái", "nữ vương", "thần", "nữ thần"]):
                cat_id = "CHAR"
                card_count = len(re.findall(r'\[CHAR-\d+\]', existing_chars_text + "\n".join(new_chars_cards))) + 1
                eid = f"CHAR-{card_count:03d}"
                card = f"## [{eid}] 『{term}』\n- **tên_chuẩn:** 『{term}』\n- **loại:** NHÂN VẬT\n"
                new_chars_cards.append(card)
            elif any(k in t_lower for k in ["giáo hội", "đoàn", "hiệp hội", "liên minh", "đế quốc", "vương quốc", "bang"]):
                cat_id = "FACTION"
                card_count = len(re.findall(r'\[FACTION-\d+\]', existing_factions_text + "\n".join(new_factions_cards))) + 1
                eid = f"FACTION-{card_count:03d}"
                card = f"## [{eid}] 『{term}』\n- **tên_chuẩn:** 『{term}』\n- **loại:** PHE PHÁI / TỔ CHỨC\n"
                new_factions_cards.append(card)
            else:
                if any(k in t_lower for k in ["chú", "thuật", "pháp", "kỹ", "trảm", "kiếm", "bước", "hóa"]):
                    cat_id = "SKILL"
                elif any(k in t_lower for k in ["kiếm", "đao", "thương", "cọc", "bom", "thuốc", "bình", "giáp", "xe"]):
                    cat_id = "ITEM"
                else:
                    cat_id = "TERM"

                card_count = len(re.findall(rf'\[{cat_id}-\d+\]', existing_terms_text + "\n".join(new_terms_cards))) + 1
                eid = f"{cat_id}-{card_count:03d}"
                card = f"## [{eid}] 『{term}』\n- **tên_chuẩn:** 『{term}』\n"
                new_terms_cards.append(card)

            added_count += 1
            all_existing_text += " " + term.lower()

    if new_terms_cards:
        updated_terms = existing_terms_text.rstrip() + "\n\n" + "\n".join(new_terms_cards)
        terms_file.write_text(updated_terms, encoding="utf-8")

    if new_chars_cards:
        updated_chars = existing_chars_text.rstrip() + "\n\n" + "\n".join(new_chars_cards)
        chars_file.write_text(updated_chars, encoding="utf-8")

    if new_factions_cards:
        updated_factions = existing_factions_text.rstrip() + "\n\n" + "\n".join(new_factions_cards)
        factions_file.write_text(updated_factions, encoding="utf-8")

    if added_count > 0:
        rebuild_entity_index(novel.folder)
        try:
            console.print(f"[bold green]✨ Đã tự động phát hiện và bổ sung {added_count} thực thể mới vào Glossary![/bold green]")
        except Exception:
            pass

    return added_count
