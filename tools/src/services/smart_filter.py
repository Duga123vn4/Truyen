# -*- coding: utf-8 -*-
"""
Bộ lọc Glossary Thông Minh (Smart Glossary Filter):
Chỉ trích xuất các nhân vật và thuật ngữ có xuất hiện trong chương để tiết kiệm token khi cần.
"""
import re
from typing import Tuple

def extract_relevant_glossary(chapter_text: str, characters_ctx: str, terms_ctx: str) -> Tuple[str, str]:
    """Lọc các mục trong characters.md và terms.md thực sự xuất hiện trong nội dung chương."""
    text_lower = chapter_text.lower()

    # Lọc Nhân vật
    char_blocks = re.split(r'\n(?=## |\n---|\n### )', characters_ctx)
    relevant_chars = []
    for blk in char_blocks:
        lines = blk.strip().splitlines()
        if not lines:
            continue
        first_line = lines[0].lower()
        # Tìm các tên khả dĩ trong tiêu đề
        names = re.findall(r'[\w\s\-\'\.]+', first_line)
        matched = False
        for n in names:
            n_clean = n.strip()
            if len(n_clean) >= 2 and n_clean in text_lower:
                matched = True
                break
        if matched or "nhân vật chính" in blk.lower():
            relevant_chars.append(blk.strip())

    # Lọc Thuật ngữ
    term_blocks = re.split(r'\n(?=## |\n---|\n### )', terms_ctx)
    relevant_terms = []
    for blk in term_blocks:
        lines = blk.strip().splitlines()
        if not lines:
            continue
        first_line = lines[0].lower()
        words = re.findall(r'[\w\s\-\'\.]+', first_line)
        matched = False
        for w in words:
            w_clean = w.strip()
            if len(w_clean) >= 2 and w_clean in text_lower:
                matched = True
                break
        if matched:
            relevant_terms.append(blk.strip())

    return ("\n\n---\n\n".join(relevant_chars), "\n\n---\n\n".join(relevant_terms))
