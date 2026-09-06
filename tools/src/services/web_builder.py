# -*- coding: utf-8 -*-
"""
WEB BUILDER SERVICE:
Tự động quét toàn bộ bản dịch, khử trùng lặp tập, nạp Canon/Glossary
và xuất ra web/chapters.js kèm Cache-Busting cho Web Đọc Truyện.
"""

import os
import sys
import re
import json
import time
from pathlib import Path
from typing import Dict, Any, List

WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from tools.src.core.paths import PROJECTS_DIR, TOOLS_DIR


WEB_DIR = WORKSPACE_DIR / "web"
OUTPUT_FILE = WEB_DIR / "chapters.js"
INDEX_FILE = WEB_DIR / "index.html"


def get_file_content(path: Path) -> str:
    """Đọc nội dung file text hoặc docx."""
    if path.suffix.lower() == ".docx":
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            with zipfile.ZipFile(path) as z:
                xml_content = z.read("word/document.xml")
            tree = ET.fromstring(xml_content)
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            lines = []
            for p in tree.iterfind(".//w:p", ns):
                texts = [node.text for node in p.iterfind(".//w:t", ns) if node.text]
                p_text = "".join(texts).strip()
                if p_text:
                    lines.append(p_text)
            return "\n".join(lines)
        except Exception:
            return ""
    else:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""


def format_chapter_title(ep_num: int, raw_title: str, stem: str) -> str:
    """Chuẩn hóa tiêu đề chương đảm bảo luôn có 'Tập {ep_num}: ' và giữ số Hồi của tác giả nếu có."""
    t = raw_title.strip()
    t = re.sub(r"^#+\s*", "", t).strip()

    if not t:
        clean_name = re.sub(r"^chuong_\d+_?", "", stem)
        clean_name = clean_name.replace("_", " ").strip().title()
        t = clean_name

    if ep_num <= 0:
        return t or stem

    m_tap = re.match(r"^Tập\s+(\d+)[:\s\-\.]*(.*)$", t, re.IGNORECASE)
    if m_tap:
        found_ep = int(m_tap.group(1))
        sub_title = m_tap.group(2).lstrip(":- ").strip()
        if found_ep == ep_num:
            return f"Tập {ep_num}: {sub_title}" if sub_title else f"Tập {ep_num}"
        else:
            return f"Tập {ep_num}: [Hồi {found_ep}] {sub_title}" if sub_title else f"Tập {ep_num}: [Hồi {found_ep}]"

    m_chuong = re.match(r"^(?:Chương|Hồi)\s+(\d+)[:\s\-\.]*(.*)$", t, re.IGNORECASE)
    if m_chuong:
        found_chap = int(m_chuong.group(1))
        sub_title = m_chuong.group(2).lstrip(":- ").strip()
        if found_chap == ep_num:
            return f"Tập {ep_num}: {sub_title}" if sub_title else f"Tập {ep_num}"
        else:
            return f"Tập {ep_num}: [Hồi {found_chap}] {sub_title}" if sub_title else f"Tập {ep_num}: [Hồi {found_chap}]"

    return f"Tập {ep_num}: {t}" if t else f"Tập {ep_num}"


def build_web_chapters(active_novel_name: str = None) -> Dict[str, Any]:
    """
    Biên dịch toàn bộ tiểu thuyết trong projects/ thành web/chapters.js.
    Tự động khử trùng lặp (lấy file mới nhất cho mỗi tập) và gắn cache-busting.
    """
    novel_dirs = []
    if PROJECTS_DIR.exists():
        for d in sorted(PROJECTS_DIR.iterdir()):
            if d.is_dir() and d.name not in ["web", "tools", ".git", "scratch", "audio"]:
                novel_dirs.append(d)

    if not novel_dirs:
        return {"success": False, "error": "Không tìm thấy thư mục truyện nào trong projects/"}

    # Xác định novel active
    active_dir = None
    if active_novel_name:
        for d in novel_dirs:
            if d.name == active_novel_name:
                active_dir = d
                break
    if not active_dir:
        for d in novel_dirs:
            if d.name == "Chu_Thuat_Su_Dung_Gia":
                active_dir = d
                break
    if not active_dir:
        active_dir = novel_dirs[0]

    all_novels_data = {}
    total_chapters_count = 0

    for d in novel_dirs:
        n_key = d.name
        n_title = d.name.replace("_", " ")

        # Đọc meta.json nếu có
        meta_file = d / "meta.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                if meta.get("title"):
                    n_title = meta["title"]
            except Exception:
                pass

        chapters_list = []
        trans_dir = d / "translated"
        if trans_dir.exists():
            # Quét tất cả file và gom nhóm theo số tập để khử trùng lặp
            files_by_ep = {}
            for f in trans_dir.iterdir():
                if f.is_file() and f.suffix.lower() in [".md", ".txt", ".docx"] and f.name != "README.md":
                    m = re.search(r"chuong_(\d+)", f.stem)
                    if m:
                        ep_num = int(m.group(1))
                    else:
                        m2 = re.search(r"(\d+)", f.stem)
                        ep_num = int(m2.group(1)) if m2 else 0

                    mtime = f.stat().st_mtime
                    if ep_num not in files_by_ep or mtime > files_by_ep[ep_num]["mtime"]:
                        files_by_ep[ep_num] = {"path": f, "mtime": mtime, "ep": ep_num}

            # Sắp xếp theo số tập tăng dần
            for ep_num in sorted(files_by_ep.keys()):
                item = files_by_ep[ep_num]
                f = item["path"]
                raw_content = get_file_content(f)
                if not raw_content.strip():
                    continue

                # Trích xuất tiêu đề từ dòng # đầu tiên
                extracted_title = ""
                for line in raw_content.splitlines():
                    line_s = line.strip()
                    if line_s.startswith("# "):
                        extracted_title = line_s[2:].strip()
                        break

                final_title = format_chapter_title(ep_num, extracted_title, f.stem)

                chapters_list.append({
                    "id": f"ep_{ep_num}",
                    "ep": ep_num,
                    "title": final_title,
                    "content": raw_content
                })

        # Đọc gallery
        gallery_data = []
        gallery_file = d / "gallery.json"
        if gallery_file.exists():
            try:
                gallery_data = json.loads(gallery_file.read_text(encoding="utf-8"))
            except Exception:
                gallery_data = []

        # Đọc glossary
        glossary_dir = d / "glossary"
        glossary_terms = ""
        glossary_chars = ""
        glossary_events = ""
        style_guide = ""

        if (glossary_dir / "terms.md").exists():
            glossary_terms = (glossary_dir / "terms.md").read_text(encoding="utf-8", errors="ignore")
        if (glossary_dir / "characters.md").exists():
            glossary_chars = (glossary_dir / "characters.md").read_text(encoding="utf-8", errors="ignore")
        if (glossary_dir / "events.md").exists():
            glossary_events = (glossary_dir / "events.md").read_text(encoding="utf-8", errors="ignore")
        if (d / "style_guide.md").exists():
            style_guide = (d / "style_guide.md").read_text(encoding="utf-8", errors="ignore")

        all_novels_data[n_key] = {
            "title": n_title,
            "chapters": chapters_list,
            "gallery": gallery_data,
            "glossary": {
                "terms": glossary_terms,
                "characters": glossary_chars,
                "events": glossary_events,
                "style_guide": style_guide
            }
        }
        total_chapters_count += len(chapters_list)

    # Đọc cấu hình sanitized
    cfg_file = TOOLS_DIR / "config.json"
    sanitized_cfg = {}
    if cfg_file.exists():
        try:
            cfg_obj = json.loads(cfg_file.read_text(encoding="utf-8"))
            cfg_obj["gemini_api_key"] = ""
            cfg_obj["relay_api_key"] = ""
            cfg_obj["api_key"] = ""
            sanitized_cfg = cfg_obj
        except Exception:
            pass

    js_lines = [
        "// Auto-generated by Novel Studio Web Builder",
        f"// Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"window.ALL_NOVELS = {json.dumps(all_novels_data, ensure_ascii=False, indent=2)};",
        "",
        f'window.ACTIVE_NOVEL_KEY = "{active_dir.name}";',
        "window.NOVEL_DATA = window.ALL_NOVELS[window.ACTIVE_NOVEL_KEY] || Object.values(window.ALL_NOVELS)[0];",
        "",
        f"window.APP_CONFIG = {json.dumps(sanitized_cfg, ensure_ascii=False)};",
        ""
    ]

    WEB_DIR.mkdir(parents=True, exist_ok=True)
    content_to_write = "\n".join(js_lines)
    for attempt in range(5):
        try:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                f.write(content_to_write)
            break
        except OSError:
            if attempt == 4:
                raise
            time.sleep(0.5)

    timestamp = int(time.time())
    if INDEX_FILE.exists():
        try:
            index_content = INDEX_FILE.read_text(encoding="utf-8")
            updated_index = re.sub(
                r'src="chapters\.js(?:\?[^"]*)?"',
                f'src="chapters.js?v={timestamp}"',
                index_content
            )
            INDEX_FILE.write_text(updated_index, encoding="utf-8")
        except Exception:
            pass

    return {
        "success": True,
        "total_novels": len(all_novels_data),
        "total_chapters": total_chapters_count,
        "active_novel": active_dir.name,
        "active_chapters": len(all_novels_data.get(active_dir.name, {}).get("chapters", [])),
        "timestamp": timestamp,
        "size_mb": round(OUTPUT_FILE.stat().st_size / (1024 * 1024), 2)
    }

if __name__ == "__main__":
    res = build_web_chapters()
    print("Build result:", res)
