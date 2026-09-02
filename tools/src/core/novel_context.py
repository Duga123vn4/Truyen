# -*- coding: utf-8 -*-
"""
Quản lý Dự án Truyện (Novel Discovery & Context):
- Khám phá danh sách các bộ truyện trong projects/
- Quản lý các thư mục: raw/, translated/, glossary/, backups/, images/
- Nạp đầy đủ Canon Database V3.0 (ENTITY_INDEX, characters, terms, events, timeline, factions)
"""
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from tools.src.core.paths import PROJECTS_DIR, MASTER_STYLE_GUIDE_FILE

class NovelContext:
    def __init__(self, folder_path: Path):
        self.folder = folder_path
        self.name = folder_path.name
        self.glossary_dir = folder_path / "glossary"
        self.raw_dir = folder_path / "raw"
        self.translated_dir = folder_path / "translated"
        self.images_dir = folder_path / "images"
        self.backups_dir = folder_path / "backups"
        self.backup_edit_dir = self.backups_dir / "truoc_bien_tap"
        self.backup_clean_dir = self.backups_dir / "truoc_chuan_hoa"
        self.backup_gloss_dir = self.backups_dir / "glossary"
        self.style_guide_file = folder_path / "style_guide.md"
        self.changelog_file = folder_path / "CHANGELOG.md"

        self.glossary_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.translated_dir.mkdir(parents=True, exist_ok=True)
        self.backup_edit_dir.mkdir(parents=True, exist_ok=True)
        self.backup_clean_dir.mkdir(parents=True, exist_ok=True)
        self.backup_gloss_dir.mkdir(parents=True, exist_ok=True)

    def list_raw_chapters(self) -> List[Tuple[int, Path]]:
        """Trả về danh sách các chương raw được sắp xếp theo số thứ tự (chương, path)."""
        res = []
        for f in sorted(self.raw_dir.glob("chuong_*.*")):
            m = re.search(r"chuong_(\d+)", f.name)
            if m:
                res.append((int(m.group(1)), f))
        return sorted(res, key=lambda x: x[0])

    def list_translated_chapters(self) -> List[Tuple[int, Path]]:
        """Trả về danh sách các chương translated được sắp xếp theo số thứ tự (chương, path)."""
        res = []
        for f in sorted(self.translated_dir.glob("chuong_*.*")):
            m = re.search(r"chuong_(\d+)", f.name)
            if m:
                res.append((int(m.group(1)), f))
        return sorted(res, key=lambda x: x[0])

    def get_characters_text(self) -> str:
        f = self.glossary_dir / "characters.md"
        return f.read_text(encoding="utf-8") if f.exists() else ""

    def get_terms_text(self) -> str:
        f = self.glossary_dir / "terms.md"
        return f.read_text(encoding="utf-8") if f.exists() else ""

    def get_style_guide_text(self) -> str:
        parts = []
        if MASTER_STYLE_GUIDE_FILE.exists():
            parts.append(MASTER_STYLE_GUIDE_FILE.read_text(encoding="utf-8"))
        if self.style_guide_file.exists():
            parts.append(self.style_guide_file.read_text(encoding="utf-8"))
        return "\n\n".join(parts)

    def get_full_canon_text(self) -> str:
        """Nạp 100% tài liệu từ glossary/ tạo ngữ cảnh Canon hoàn hảo (>30k tokens)."""
        canon_order = [
            ("MỤC LỤC THỰC THỂ TOÀN BỘ (ENTITY INDEX)", "ENTITY_INDEX.md"),
            ("HỒ SƠ NHÂN VẬT & MA TRẬN XƯNG HÔ", "characters.md"),
            ("TỪ ĐIỂN THUẬT NGỮ, KỸ NĂNG, VẬT PHẨM & QUÁI VẬT", "terms.md"),
            ("PHE PHÁI & TỔ CHỨC", "factions_orgs.md"),
            ("THẦN LINH & HỆ THỐNG TÍN NGƯỠNG", "deities_religions.md"),
            ("SINH VẬT & MA THÚ", "animals.md"),
            ("ĐỊA DANH & KHU VỰC MÊ CUNG", "locations.md"),
            ("MA TRẬN QUAN HỆ NHÂN VẬT & TIẾN TRÌNH", "relationship_timeline.md"),
            ("DÒNG THỜI GIAN SỰ KIỆN TOÀN CỐT TRUYỆN (CHRONOLOGY)", "events.md"),
        ]

        full_parts = []
        for title, fname in canon_order:
            fpath = self.glossary_dir / fname
            if fpath.exists():
                content = fpath.read_text(encoding="utf-8").strip()
                if content:
                    full_parts.append(f"=== {title} ===\n{content}")

        # Nạp thêm bất kỳ file .md nào khác trong glossary nếu chưa có
        loaded_names = {item[1] for item in canon_order}
        for f in sorted(self.glossary_dir.glob("*.md")):
            if f.name not in loaded_names and not f.name.startswith("GLOSSARY_AUDIT"):
                txt = f.read_text(encoding="utf-8").strip()
                if txt:
                    full_parts.append(f"=== {f.stem.upper().replace('_', ' ')} ===\n{txt}")

        return "\n\n".join(full_parts)

    def append_changelog(self, category: str, detail: str) -> None:
        """Ghi nhận sự kiện thay đổi vào file CHANGELOG.md của bộ truyện."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"| `{now_str}` | **{category}** | {detail} |\n"
        if not self.changelog_file.exists():
            header = "# 📜 NHẬT KÝ THAY ĐỔI & BIÊN TẬP DỰ ÁN\n\n| Thời gian | Danh mục | Nội dung chi tiết |\n| :--- | :--- | :--- |\n"
            self.changelog_file.write_text(header + entry, encoding="utf-8")
        else:
            with open(self.changelog_file, "a", encoding="utf-8") as f:
                f.write(entry)


def discover_novels() -> List[NovelContext]:
    """Tự động quét và phát hiện các thư mục truyện hợp lệ trong projects/."""
    novels = []
    if PROJECTS_DIR.exists():
        for p in sorted(PROJECTS_DIR.iterdir()):
            if p.is_dir() and not p.name.startswith(".") and not p.name.startswith("_"):
                novels.append(NovelContext(p))
    return novels
