# -*- coding: utf-8 -*-
"""
Bộ lọc Glossary Thông Minh (Smart Glossary Filter):
Chỉ trích xuất các nhân vật và thuật ngữ có xuất hiện trong chương để tiết kiệm token tối đa (giảm 95% chi phí API).
"""
import re
from typing import Tuple

def _extract_keywords_from_block(block: str) -> list:
    """Trích xuất các từ khóa (tên tiếng Việt, tiếng Nhật, biệt danh) từ một block markdown."""
    keywords = []
    lines = block.strip().splitlines()
    if not lines:
        return keywords
    
    first_line = lines[0]
    bracket_content = re.findall(r'[『「\("“](.*?)[』」\)"”]', first_line)
    keywords.extend(bracket_content)
    
    clean_header = re.sub(r'#+|\[.*?\]', '', first_line).strip()
    keywords.append(clean_header)

    for line in lines[1:]:
        if ":" in line or "：" in line:
            parts = re.split(r'[:：]', line, maxsplit=1)
            if len(parts) == 2:
                val = parts[1].strip()
                sub_vals = re.split(r'[,/|;]', val)
                for sv in sub_vals:
                    sv_clean = re.sub(r'\*+|\(.*?\)|\[.*?\]', '', sv).strip()
                    if len(sv_clean) >= 2:
                        keywords.append(sv_clean)

    final_kw = []
    for kw in keywords:
        kw_clean = kw.strip()
        if len(kw_clean) >= 2 and not kw_clean.startswith("http"):
            final_kw.append(kw_clean.lower())
    return list(set(final_kw))

def extract_relevant_glossary(chapter_text: str, characters_ctx: str, terms_ctx: str) -> Tuple[str, str]:
    """Lọc các mục trong characters.md và terms.md thực sự xuất hiện trong nội dung chương."""
    text_lower = chapter_text.lower()

    # Lọc Nhân vật
    char_blocks = re.split(r'\n(?=## |\n---|\n### )', characters_ctx)
    relevant_chars = []
    for blk in char_blocks:
        if not blk.strip():
            continue
        if "nhân vật chính" in blk.lower() or "ma trận xưng hô" in blk.lower() or "chú thích" in blk.lower():
            relevant_chars.append(blk.strip())
            continue

        kws = _extract_keywords_from_block(blk)
        matched = any(kw in text_lower for kw in kws)
        if matched:
            relevant_chars.append(blk.strip())

    # Lọc Thuật ngữ
    term_blocks = re.split(r'\n(?=## |\n---|\n### )', terms_ctx)
    relevant_terms = []
    for blk in term_blocks:
        if not blk.strip():
            continue
        if "quy tắc" in blk.lower() or "hướng dẫn" in blk.lower():
            relevant_terms.append(blk.strip())
            continue

        kws = _extract_keywords_from_block(blk)
        matched = any(kw in text_lower for kw in kws)
        if matched:
            relevant_terms.append(blk.strip())

    return ("\n\n---\n\n".join(relevant_chars), "\n\n---\n\n".join(relevant_terms))
