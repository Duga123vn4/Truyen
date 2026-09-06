# -*- coding: utf-8 -*-
"""
CONTINUOUS TRANSLATION & GITHUB AUTO-SYNC SERVICE:
Quét các chương chưa dịch, dịch tuần tự từng chương bằng AI,
sau mỗi chương tự động build Web Reader và git commit/push lên GitHub.
"""

import os
import sys
import time
import subprocess
import asyncio
from pathlib import Path

WORKSPACE_DIR = Path(r"d:\Novel")
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from tools.src.core.config import load_config
from tools.src.core.novel_context import NovelContext
from tools.src.core.ai_client import AIClient
from tools.src.services.translator import translate_chapter
from tools.src.services.web_builder import build_web_chapters

LOG_DIR = WORKSPACE_DIR / "tools" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "continuous_translate.log"


def log(msg: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def push_chapter_to_github(ep: int, novel_dir: Path):
    try:
        # 1. git add
        subprocess.run(
            ["git", "add", str(novel_dir / "translated"), "web/chapters.js", "web/index.html", "web/api_usage_log.json"],
            cwd=str(WORKSPACE_DIR),
            check=True,
            capture_output=True,
            text=True
        )
        # 2. git commit
        commit_msg = f"feat(chapter): add chapter {ep} and update web reader"
        res_commit = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=str(WORKSPACE_DIR),
            capture_output=True,
            text=True
        )
        if res_commit.returncode != 0 and "nothing to commit" in res_commit.stdout:
            log(f"[Git] Không có thay đổi mới để commit cho tập {ep}.")
            return True

        # 3. git push
        res_push = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=str(WORKSPACE_DIR),
            check=True,
            capture_output=True,
            text=True
        )
        log(f"[Git] ĐÃ PUSH LÊN GITHUB THÀNH CÔNG cho Tập {ep}!")
        return True
    except Exception as e:
        log(f"[Git LỖI] Không thể push Tập {ep} lên GitHub: {e}")
        return False


async def run_continuous_pipeline(start_ep: int = 491, max_chapters: int = None, novel_name: str = "Chu_Thuat_Su_Dung_Gia"):
    cfg = load_config()
    ai = AIClient(cfg)
    novel_dir = WORKSPACE_DIR / "projects" / novel_name
    novel = NovelContext(novel_dir)
    sem = asyncio.Semaphore(1)

    # Quét danh sách chưa dịch
    import re
    raw_files = {}
    for f in novel.raw_dir.glob("*.txt"):
        m = re.search(r"chuong_(\d+)", f.stem)
        if m:
            raw_files[int(m.group(1))] = f

    trans_eps = set()
    for f in novel.translated_dir.iterdir():
        if f.is_file() and f.suffix.lower() in [".md", ".txt", ".docx"] and f.name != "README.md":
            m = re.search(r"chuong_(\d+)", f.stem)
            if m:
                trans_eps.add(int(m.group(1)))

    untrans = sorted([ep for ep in raw_files.keys() if ep >= start_ep and ep not in trans_eps])
    if max_chapters:
        queue = untrans[:max_chapters]
    else:
        queue = untrans

    total = len(queue)
    log(f"=== BẮT ĐẦU DỊCH LIÊN TỤC & ĐỒNG BỘ GITHUB ({total} TẬP) ===")
    log(f"Mô hình: {ai.provider} ({ai.model}) | Truyện: {novel_name}")
    log(f"Danh sách hàng đợi ({total} tập): {queue[:15]}{'...' if total > 15 else ''}")

    success_total = 0
    fail_total = 0

    for idx, ep in enumerate(queue, 1):
        raw_file = raw_files.get(ep)
        if not raw_file or not raw_file.exists():
            log(f"[{idx}/{total}] [Tập {ep}] Bỏ qua: Không thấy file raw.")
            fail_total += 1
            continue

        raw_size = raw_file.stat().st_size
        log(f"[{idx}/{total}] [Tập {ep}] Đang dịch: {raw_file.name} ({raw_size:,} bytes)...")
        t0 = time.time()

        success = False
        out_path = ""
        msg = ""

        # Thử tối đa 2 lần nếu có lỗi mạng/rate limit
        for attempt in range(1, 3):
            try:
                success, ep_num, out_path, msg = await translate_chapter(raw_file, novel, ai, ep, sem)
                if success:
                    break
                else:
                    log(f"       -> Lần {attempt} thất bại: {msg}. Đang thử lại...")
                    await asyncio.sleep(5)
            except Exception as e:
                log(f"       -> Lần {attempt} lỗi ngoại lệ: {e}. Đang thử lại...")
                await asyncio.sleep(5)

        elapsed = round(time.time() - t0, 1)

        if success:
            success_total += 1
            log(f"[{idx}/{total}] [Tập {ep}] DỊCH XONG ({elapsed}s) -> {Path(out_path).name}")

            # 1. Cập nhật Web Reader
            build_res = build_web_chapters(novel_name)
            active_chaps = build_res.get("active_chapters", 0)
            log(f"       -> Web Reader biên dịch xong: {active_chaps} tập hoạt động.")

            # 2. Đẩy lên GitHub
            push_chapter_to_github(ep, novel_dir)
        else:
            fail_total += 1
            log(f"[{idx}/{total}] [Tập {ep}] THẤT BÀI ({elapsed}s): {msg}")

        # Nghỉ ngắn giữa các tập để prompt cache và rate limit giữ phong độ tốt nhất
        await asyncio.sleep(2)

    log(f"\n=== HOÀN TẤT TIẾN TRÌNH: {success_total}/{total} thành công, {fail_total} thất bại ===")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Continuous Novel Translator and GitHub Sync")
    parser.add_argument("--start", type=int, default=491, help="Tập bắt đầu")
    parser.add_argument("--max", type=int, default=None, help="Số tập tối đa dịch (mặc định dịch hết)")
    parser.add_argument("--novel", type=str, default="Chu_Thuat_Su_Dung_Gia", help="Tên thư mục tiểu thuyết")
    args = parser.parse_args()

    asyncio.run(run_continuous_pipeline(start_ep=args.start, max_chapters=args.max, novel_name=args.novel))
