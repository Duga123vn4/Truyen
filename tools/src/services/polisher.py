# -*- coding: utf-8 -*-
"""
Dịch vụ Chuẩn Hóa Thuật Ngữ & Dọn Kính Ngữ (Polisher & Sanitizer):
- Chuẩn hóa thuật ngữ hàng loạt theo Glossary
- Dọn dẹp kính ngữ thô (cậu Yamada, bạn Kenzaki -> xưng hô tự nhiên)
- Tự động sao lưu vào backups/truoc_chuan_hoa/
"""
import re
import shutil
from pathlib import Path
from typing import Dict, List, Tuple
from rich.console import Console
from rich.prompt import Prompt, Confirm

from tools.src.core.novel_context import NovelContext
from tools.src.core.notifications import notify_completion
from tools.src.services.diff_studio import generate_diff_data

console = Console()

def sanitize_honorifics_text(text: str) -> Tuple[str, int]:
    """Dọn dẹp kính ngữ máy móc thô cứng sang văn phong tự nhiên."""
    replacements = [
        (r'\bcậu Yamada\b', 'Yamada'),
        (r'\bbạn Kenzaki\b', 'Kenzaki'),
        (r'\bbạn Himeno\b', 'Himeno'),
        (r'\bcậu Momokawa\b', 'Momokawa'),
        (r'\bcậu Ueta\b', 'Ueta'),
        (r'\bbạn Yoshizaki\b', 'Yoshizaki'),
        (r'\bbạn Sakura\b', 'Sakura'),
        (r'\bcậu Souma\b', 'Souma'),
        (r'\bbạn Kisaragi\b', 'Kisaragi'),
        (r'\bGoGame Mastera\b', 'Goma'),
        (r'\bGoGame\b', 'Goma'),
        (r'\bGame Mastera\b', 'Goma'),
        (r'\bTokkan Kouji Mẫu 1\b', 'Cọc Thi Công Thần Tốc Mẫu 1'),
        (r'\bTokkan Kouji Mẫu 2\b', 'Cọc Thi Công Thần Tốc Mẫu 2'),
        (r'\bTokkan Kouji-kun\b', 'Bé Thi Công Thần Tốc'),
    ]
    count = 0
    res = text
    for pat, rep in replacements:
        sub_res, n = re.subn(pat, rep, res)
        if n > 0:
            count += n
            res = sub_res
    return res, count

def run_glossary_polisher_and_normalizer(novel: NovelContext):
    """Giao diện CLI chạy chuẩn hóa thuật ngữ & dọn kính ngữ."""
    console.print("\n[bold cyan]⚡ BẮT ĐẦU CHUẨN HÓA THUẬT NGỮ & DỌN KÍNH NGỮ[/bold cyan]")
    trans_files = novel.list_translated_chapters()
    if not trans_files:
        console.print("[red]Không tìm thấy chương nào trong translated/.[/red]")
        return

    console.print(f"Tìm thấy {len(trans_files)} chương. Đang tiến hành quét và làm sạch...")
    novel.backup_clean_dir.mkdir(parents=True, exist_ok=True)
    
    modified_count = 0
    total_fixes = 0

    for ch_num, fpath in trans_files:
        original = fpath.read_text(encoding="utf-8")
        cleaned, fixes = sanitize_honorifics_text(original)
        if fixes > 0 and cleaned != original:
            bak_file = novel.backup_clean_dir / fpath.name
            if not bak_file.exists():
                bak_file.write_text(original, encoding="utf-8")
            fpath.write_text(cleaned, encoding="utf-8")
            modified_count += 1
            total_fixes += fixes

    console.print(f"\n[bold green]✅ Hoàn tất! Đã làm sạch {total_fixes} vị trí lỗi trên {modified_count} chương.[/bold green]")
    generate_diff_data(novel)
