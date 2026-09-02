# -*- coding: utf-8 -*-
"""
Hệ thống So Sánh Đối Chiếu & Báo Cáo Diff:
- Phân tích độ lệch ký tự, tỷ lệ tương đồng
- Sinh báo cáo kiểm chứng DIFF_REPORT.md
- Đóng gói dữ liệu đồ họa vào web/diff_data.js (loại bỏ thư mục rác)
"""
import difflib
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from tools.src.core.paths import WEB_DIR, PROJECTS_DIR
from tools.src.core.novel_context import NovelContext, discover_novels

def analyze_chapter_diff(original_text: str, modified_text: str) -> Dict[str, Any]:
    """Phân tích mức độ thay đổi chi tiết giữa bản gốc và bản mới."""
    orig_clean = original_text.strip()
    mod_clean = modified_text.strip()

    orig_len = len(orig_clean)
    mod_len = len(mod_clean)
    diff_len = mod_len - orig_len
    ratio = (mod_len / orig_len * 100) if orig_len > 0 else 100.0

    orig_lines = orig_clean.splitlines()
    mod_lines = mod_clean.splitlines()

    differ = difflib.Differ()
    diff = list(differ.compare(orig_lines, mod_lines))

    additions = sum(1 for line in diff if line.startswith('+ '))
    deletions = sum(1 for line in diff if line.startswith('- '))
    modifications = min(additions, deletions)

    sample_diffs = []
    i = 0
    while i < len(diff):
        line = diff[i]
        if line.startswith('- '):
            orig_snippet = line[2:].strip()
            mod_snippet = ""
            if i + 1 < len(diff) and diff[i+1].startswith('+ '):
                mod_snippet = diff[i+1][2:].strip()
                i += 1
            if orig_snippet and mod_snippet and orig_snippet != mod_snippet:
                sample_diffs.append({
                    "before": orig_snippet,
                    "after": mod_snippet
                })
        i += 1

    return {
        "orig_len": orig_len,
        "mod_len": mod_len,
        "diff_len": diff_len,
        "ratio": ratio,
        "additions": additions,
        "deletions": deletions,
        "modifications": modifications,
        "sample_diffs": sample_diffs[:5]
    }

def generate_diff_report(novel: NovelContext, diff_results: List[Dict[str, Any]]) -> Path:
    """Tạo báo cáo Markdown kiểm chứng DIFF_REPORT.md tương thích Obsidian."""
    report_file = novel.folder / "DIFF_REPORT.md"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md = [
        f"# 📊 BÁO CÁO KIỂM CHỨNG & SO SÁNH BIÊN TẬP (DIFF REPORT)",
        f"> **Bộ truyện:** {novel.name}  ",
        f"> **Thời gian xuất:** {now_str}  ",
        f"> **Tổng số chương đã kiểm tra:** {len(diff_results)}  \n",
        "---",
        "## 📈 1. BẢNG TỔNG QUAN THAY ĐỔI THEO TỪNG CHƯƠNG\n",
        "| Tập | Tên File | Độ dài Gốc | Độ dài Mới | Chênh lệch | Tỷ lệ | Thay đổi dòng |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |"
    ]

    for r in diff_results:
        ch = r["chapter"]
        fname = r["filename"]
        d = r["diff"]
        diff_sign = f"+{d['diff_len']}" if d['diff_len'] > 0 else str(d['diff_len'])
        row = f"| Tập {ch} | [{fname}](translated/{fname}) | {d['orig_len']} | {d['mod_len']} | {diff_sign} | {d['ratio']:.1f}% | +{d['additions']}/-{d['deletions']} |"
        md.append(row)

    md.extend([
        "\n---",
        "## 🔍 2. CHI TIẾT CÁC CÂU SỬA TIÊU BIỂU\n"
    ])

    for r in diff_results:
        ch = r["chapter"]
        d = r["diff"]
        if d.get("sample_diffs"):
            md.append(f"### 📖 Tập {ch}: {r['filename']}")
            for idx, s in enumerate(d["sample_diffs"], 1):
                md.append(f"**Thay đổi {idx}:**")
                md.append(f"- 🔴 *Gốc:* `{s['before']}`")
                md.append(f"- 🟢 *Sau sửa:* `{s['after']}`\n")

    report_content = "\n".join(md)
    report_file.write_text(report_content, encoding="utf-8")
    return report_file

def generate_diff_data(active_novel: NovelContext) -> Path:
    """Quét thư mục translated/ và backups/ để xuất dữ liệu vào web/diff_data.js cho So_Sanh_Diff.html."""
    out_file = WEB_DIR / "diff_data.js"
    all_novels = discover_novels()
    
    # Lọc bỏ thư mục rác (.obsidian, thư mục ẩn)
    all_novels = [n for n in all_novels if not n.name.startswith(".")]

    all_diff_data = {}

    for novel in all_novels:
        novel_chapters = []
        trans_files = {f.name: f for f in novel.translated_dir.glob("chuong_*.*")}
        backup_files = {}

        # Gom backup từ truoc_bien_tap hoặc truoc_chuan_hoa
        for bdir in [novel.backup_edit_dir, novel.backup_clean_dir]:
            if bdir.exists():
                for bf in bdir.glob("chuong_*.*"):
                    if bf.name not in backup_files:
                        backup_files[bf.name] = bf

        common_keys = sorted(
            list(set(trans_files.keys()) & set(backup_files.keys())),
            key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)]
        )

        for fname in common_keys:
            m = re.search(r'chuong_(\d+)', fname)
            ch_num = int(m.group(1)) if m else 0

            cur_content = trans_files[fname].read_text(encoding="utf-8")
            bak_content = backup_files[fname].read_text(encoding="utf-8")

            title_m = re.search(r'^#\s*(.*?)$', cur_content, re.MULTILINE)
            ch_title = title_m.group(1) if title_m else f"Tập {ch_num}"

            diff_info = analyze_chapter_diff(bak_content, cur_content)

            novel_chapters.append({
                "chapter_ep": ch_num,
                "title": ch_title,
                "filename": fname,
                "original_text": bak_content,
                "cleaned_text": cur_content,
                "diff_info": diff_info
            })

        all_diff_data[novel.name] = {
            "novel_key": novel.name,
            "novel_name": novel.name,
            "chapters": novel_chapters
        }

    active_data = all_diff_data.get(active_novel.name, {"novel_key": active_novel.name, "novel_name": active_novel.name, "chapters": []})
    
    js_content = f"window.DIFF_DATA = {json.dumps(active_data, ensure_ascii=False)};\n"
    js_content += f"window.DIFF_CHAPTERS = window.DIFF_DATA.chapters;\n\n"
    js_content += f"window.ALL_DIFF_DATA = {json.dumps(all_diff_data, ensure_ascii=False)};\n"

    out_file.write_text(js_content, encoding="utf-8")
    return out_file

def open_diff_studio(active_novel: NovelContext):
    """Cập nhật dữ liệu và mở Diff Studio trên trình duyệt web mặc định."""
    import webbrowser
    generate_diff_data(active_novel)
    diff_html = WEB_DIR / "So_Sanh_Diff.html"
    if diff_html.exists():
        webbrowser.open(diff_html.as_uri())

