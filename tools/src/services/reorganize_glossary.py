# -*- coding: utf-8 -*-
"""
Dịch vụ Quy Hoạch & Tối Ưu Hóa Glossary (Glossary Reorganizer V3.5)
- Lọc từ rác, trùng lặp trong terms.md
- Định dạng lại thẻ gọn nhẹ Compact Card (2-3 dòng thay vì 15 dòng)
- Phân luồng các phe phái sang factions_orgs.md
- Tự động tái tạo ENTITY_INDEX.md chính xác 100%
"""
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

NOISE_WORDS = {
    "đối thoại", "xóa", "sửa", "hệ thống", "thông báo", "xe", "người", "tập", "chương",
    "bản dịch", "raw", "chuẩn hóa", "ghi chú", "tác giả", "dịch giả", "mô tả",
    "ống phun", "bình thường", "không", "có", "được", "bị", "phải", "này", "kìa",
    "xin chào", "cảm ơn", "tài khoản", "giao diện", "nhật ký"
}

def is_noise_term(term: str) -> bool:
    t_clean = term.strip().lower()
    if len(t_clean) < 2 or len(t_clean) > 40:
        return True
    if t_clean in NOISE_WORDS:
        return True
    if t_clean.isdigit():
        return True
    return False

def reorganize_novel_glossary(novel_folder: Path) -> Dict[str, int]:
    glossary_dir = novel_folder / "glossary"
    if not glossary_dir.exists():
        return {"error": 1}

    terms_file = glossary_dir / "terms.md"
    factions_file = glossary_dir / "factions_orgs.md"
    chars_file = glossary_dir / "characters.md"

    # Read existing content
    terms_text = terms_file.read_text(encoding="utf-8") if terms_file.exists() else ""
    factions_text = factions_file.read_text(encoding="utf-8") if factions_file.exists() else ""
    chars_text = chars_file.read_text(encoding="utf-8") if chars_file.exists() else ""

    seen_names = set()

    # Pre-populate seen_names from characters.md and factions_orgs.md to avoid duplication
    for m in re.finditer(r'『([^』]+)』', chars_text + factions_text):
        seen_names.add(m.group(1).strip().lower())

    cards = re.split(r'\n---\n', terms_text)
    
    skill_list = []
    item_list = []
    faction_list = []
    term_list = []
    monster_list = []

    for card in cards:
        m = re.search(r'##\s*\[([^\]]+)\]\s*『([^』]+)』\s*(?:\(([^)]+)\))?', card)
        if not m:
            continue
        tag = m.group(1).strip()
        name = m.group(2).strip()
        raw = (m.group(3) or "").strip()

        if is_noise_term(name):
            continue

        name_lower = name.lower()
        if name_lower in seen_names:
            continue
        seen_names.add(name_lower)

        # Extract desc if available
        desc = ""
        m_desc = re.search(r'-\s*\*\*mô_tả:\*\*\s*(.*)', card)
        if m_desc:
            desc = m_desc.group(1).strip()
            if "phát hiện tự động" in desc:
                desc = ""

        # Route by tag or keyword
        tag_upper = tag.upper()
        if "FACTION" in tag_upper or any(k in name_lower for k in ["giáo hội", "đoàn", "hiệp hội", "liên minh", "đế quốc", "vương quốc", "bang"]):
            faction_list.append((tag, name, raw, desc))
        elif "SKILL" in tag_upper:
            skill_list.append((tag, name, raw, desc))
        elif "ITEM" in tag_upper:
            item_list.append((tag, name, raw, desc))
        elif "MONSTER" in tag_upper:
            monster_list.append((tag, name, raw, desc))
        else:
            term_list.append((tag, name, raw, desc))

    # Re-build clean compact terms.md
    new_terms_lines = [
        "# ⚔️ THUẬT NGỮ, KỸ NĂNG, VẬT PHẨM & QUÁI VẬT (CANON V3.5)",
        f"> **Bộ truyện:** {novel_folder.name}",
        "> **Quy chuẩn:** Compact Entity Cards (Tối ưu dung lượng, phân loại rành mạch)",
        "",
        "---",
        "",
        "### 1. ⚔️ KỸ NĂNG & MA PHÁP (SKILLS)",
        ""
    ]

    for idx, (tag, name, raw, desc) in enumerate(skill_list, 1):
        eid = f"SKILL-{idx:03d}"
        raw_str = f" ({raw})" if raw else ""
        desc_str = f"\n- **mô_tả:** {desc}" if desc else ""
        new_terms_lines.append(f"## [{eid}] 『{name}』{raw_str}\n- **tên_chuẩn:** 『{name}』{desc_str}\n")

    new_terms_lines.extend(["---", "", "### 2. 🛡️ VẬT PHẨM & TRANG BỊ (ITEMS)", ""])
    for idx, (tag, name, raw, desc) in enumerate(item_list, 1):
        eid = f"ITEM-{idx:03d}"
        raw_str = f" ({raw})" if raw else ""
        desc_str = f"\n- **mô_tả:** {desc}" if desc else ""
        new_terms_lines.append(f"## [{eid}] 『{name}』{raw_str}\n- **tên_chuẩn:** 『{name}』{desc_str}\n")

    new_terms_lines.extend(["---", "", "### 3. 👹 MA THÚ & SINH VẬT (MONSTERS)", ""])
    for idx, (tag, name, raw, desc) in enumerate(monster_list, 1):
        eid = f"MONSTER-{idx:03d}"
        raw_str = f" ({raw})" if raw else ""
        desc_str = f"\n- **mô_tả:** {desc}" if desc else ""
        new_terms_lines.append(f"## [{eid}] 『{name}』{raw_str}\n- **tên_chuẩn:** 『{name}』{desc_str}\n")

    new_terms_lines.extend(["---", "", "### 4. 🌐 THUẬT NGỮ THẾ GIỚI (TERMS)", ""])
    for idx, (tag, name, raw, desc) in enumerate(term_list, 1):
        eid = f"TERM-{idx:03d}"
        raw_str = f" ({raw})" if raw else ""
        desc_str = f"\n- **mô_tả:** {desc}" if desc else ""
        new_terms_lines.append(f"## [{eid}] 『{name}』{raw_str}\n- **tên_chuẩn:** 『{name}』{desc_str}\n")

    terms_file.write_text("\n".join(new_terms_lines), encoding="utf-8")

    # Update factions_orgs.md if new factions exist
    if faction_list:
        faction_append = ["\n\n---", "", "### 🏰 THỰC THỂ TỔ CHỨC & PHE PHÁI MỚI", ""]
        for idx, (tag, name, raw, desc) in enumerate(faction_list, 1):
            eid = f"FACTION-{idx:03d}"
            raw_str = f" ({raw})" if raw else ""
            desc_str = f"\n- **mô_tả:** {desc}" if desc else ""
            faction_append.append(f"## [{eid}] 『{name}』{raw_str}\n- **tên_chuẩn:** 『{name}』{desc_str}\n")
        
        factions_file.write_text(factions_text.rstrip() + "\n".join(faction_append), encoding="utf-8")

    # Re-build ENTITY_INDEX.md
    rebuild_entity_index(novel_folder)

    return {
        "skills": len(skill_list),
        "items": len(item_list),
        "monsters": len(monster_list),
        "factions": len(faction_list),
        "terms": len(term_list)
    }

def rebuild_entity_index(novel_folder: Path):
    glossary_dir = novel_folder / "glossary"
    index_file = glossary_dir / "ENTITY_INDEX.md"

    index_lines = [
        "# 🗂️ MỤC LỤC THỰC THỂ CANON DATABASE (V3.5)",
        f"> **Bộ truyện:** {novel_folder.name}",
        "> **Quy chuẩn:** Bảng tra cứu định danh nhanh (Quick Lookup Index - Auto Generated)",
        "",
        "---",
        ""
    ]

    for fname in ["characters.md", "factions_orgs.md", "terms.md"]:
        fpath = glossary_dir / fname
        if not fpath.exists():
            continue

        category_title = fname.replace(".md", "").upper()
        index_lines.append(f"### 📌 {category_title}")
        
        content = fpath.read_text(encoding="utf-8")
        matches = re.findall(r'##\s*\[([^\]]+)\]\s*(.*)', content)
        for tag, title in matches:
            index_lines.append(f"* `[{tag}]` {title.strip()}")
        index_lines.append("")

    index_file.write_text("\n".join(index_lines), encoding="utf-8")
