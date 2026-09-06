# -*- coding: utf-8 -*-
"""
NOVEL STUDIO BACKEND SERVER (aiohttp.web)
Máy chủ API nội bộ cung cấp dịch vụ cho Giao diện Đồ họa Novel Studio (LinguaGacha style).
Hỗ trợ SSE (Server-Sent Events) đẩy tiến độ thời gian thực, log console, và điều phối tác vụ.
"""
import sys
import os
from pathlib import Path

# Redirect stdout/stderr to log file if running under pythonw or windowless
log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
server_log_file = open(log_dir / "studio_server.log", "a", encoding="utf-8", buffering=1)

if sys.stdout is None:
    sys.stdout = server_log_file
else:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

if sys.stderr is None:
    sys.stderr = server_log_file
else:
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import re
import json
import time
import asyncio
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

from aiohttp import web

# Add workspace to sys.path
WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from tools.src.core.paths import PROJECTS_DIR, WEB_DIR, TOOLS_DIR
from tools.src.core.config import load_config, save_config, fetch_llmgate_models
from tools.src.core.novel_context import NovelContext, discover_novels
from tools.src.core.ai_client import AIClient
from tools.src.services.syosetu_scraper import SyosetuNovel, extract_novel_code, clean_filename
from tools.src.services.translator import translate_chapter, generate_anime_illustration
from tools.src.services.deep_editor import edit_single_chapter
from tools.src.services.glossary_miner import auto_sync_glossary_from_translated
from tools.src.services.diff_studio import generate_diff_data

class StudioState:
    def __init__(self):
        self.novels: List[NovelContext] = discover_novels()
        self.active_novel: Optional[NovelContext] = self.novels[0] if self.novels else None
        self.cfg: Dict[str, Any] = load_config()
        self.ai: AIClient = AIClient(self.cfg)
        self.sse_queues: Set[asyncio.Queue] = set()
        self.current_task: Optional[asyncio.Task] = None
        self.is_task_running: bool = False
        self.task_info: Dict[str, Any] = {"name": "", "progress": 0, "total": 0, "status": "idle"}

    def refresh_novels(self):
        self.novels = discover_novels()
        if self.novels:
            if not self.active_novel or not any(n.name == self.active_novel.name for n in self.novels):
                self.active_novel = self.novels[0]

    async def broadcast(self, event_type: str, data: Any):
        payload = json.dumps({"event": event_type, "data": data, "timestamp": time.time()}, ensure_ascii=False)
        dead = []
        for q in list(self.sse_queues):
            try:
                await q.put(payload)
            except Exception:
                dead.append(q)
        for d in dead:
            self.sse_queues.discard(d)

    async def log(self, message: str, level: str = "info"):
        print(f"[{level.upper()}] {message}")
        await self.broadcast("log", {"message": message, "level": level})

state = StudioState()

# ----------------- SSE STREAM -----------------
async def sse_handler(request: web.Request) -> web.StreamResponse:
    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )
    await response.prepare(request)
    q: asyncio.Queue = asyncio.Queue()
    state.sse_queues.add(q)
    try:
        # Send initial status
        init_data = json.dumps({"event": "status", "data": state.task_info}, ensure_ascii=False)
        await response.write(f"data: {init_data}\n\n".encode('utf-8'))

        while True:
            data = await q.get()
            await response.write(f"data: {data}\n\n".encode('utf-8'))
    except (asyncio.CancelledError, ConnectionResetError, Exception):
        pass
    finally:
        state.sse_queues.discard(q)
    return response

# ----------------- NOVEL MANAGEMENT API -----------------
async def get_novels(request: web.Request) -> web.Response:
    state.refresh_novels()
    res = []
    for n in state.novels:
        raws = n.list_raw_chapters()
        trans = n.list_translated_chapters()
        res.append({
            "name": n.name,
            "raw_count": len(raws),
            "translated_count": len(trans),
            "has_characters": (n.glossary_dir / "characters.md").exists(),
            "has_terms": (n.glossary_dir / "terms.md").exists(),
            "is_active": (state.active_novel and state.active_novel.name == n.name)
        })
    return web.json_response({"novels": res, "active": state.active_novel.name if state.active_novel else None})

async def select_novel(request: web.Request) -> web.Response:
    data = await request.json()
    name = data.get("name")
    for n in state.novels:
        if n.name == name:
            state.active_novel = n
            await state.log(f"Đã chuyển sang bộ truyện: {name}", "info")
            await state.broadcast("novel_changed", {"name": name})
            return web.json_response({"success": True, "active": name})
    return web.json_response({"success": False, "error": "Không tìm thấy truyện"}, status=404)

async def create_novel(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        raw_name = data.get("name", "").strip()
        title = data.get("title", "").strip() or raw_name
        author = data.get("author", "").strip() or "Chưa rõ"
        syosetu_code = extract_novel_code(data.get("syosetu_code", "").strip())
        description = data.get("description", "").strip()
        tags = data.get("tags", "").strip()

        if not raw_name:
            return web.json_response({"success": False, "error": "Vui lòng nhập tên bộ truyện / tên thư mục!"}, status=400)

        # Sanitize folder name for Windows
        clean_name = re.sub(r'[\\/*?:"<>|]', '_', raw_name).strip()
        clean_name = re.sub(r'\s+', '_', clean_name)
        if not clean_name:
            return web.json_response({"success": False, "error": "Tên thư mục không hợp lệ trên Windows!"}, status=400)

        target_dir = PROJECTS_DIR / clean_name
        if target_dir.exists():
            return web.json_response({"success": False, "error": f"Bộ truyện hoặc thư mục '{clean_name}' đã tồn tại!"}, status=400)

        # Create standard directory tree
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "raw").mkdir(parents=True, exist_ok=True)
        (target_dir / "translated").mkdir(parents=True, exist_ok=True)
        (target_dir / "images").mkdir(parents=True, exist_ok=True)
        (target_dir / "glossary").mkdir(parents=True, exist_ok=True)
        (target_dir / "backups" / "truoc_bien_tap").mkdir(parents=True, exist_ok=True)
        (target_dir / "backups" / "truoc_chuan_hoa").mkdir(parents=True, exist_ok=True)
        (target_dir / "backups" / "glossary").mkdir(parents=True, exist_ok=True)

        # If syosetu_code provided, try to fetch info
        if syosetu_code:
            try:
                import httpx
                syosetu = SyosetuNovel(syosetu_code)
                async with httpx.AsyncClient(timeout=8.0) as client:
                    ok = await syosetu.fetch_novel_info_and_toc(client)
                    if ok:
                        if not title or title == raw_name:
                            title = syosetu.title or title
                        if not author or author == "Chưa rõ":
                            author = syosetu.author or author
            except Exception:
                pass

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. README.md
        readme_content = f"""# 📖 {title}
- **Tên thư mục dự án:** `{clean_name}`
- **Tác giả:** {author}
- **Thể loại:** {tags or 'Light Novel, Chuyển sinh, Fantasy'}
- **Nguồn raw Syosetu:** {f'https://ncode.syosetu.com/{syosetu_code}/' if syosetu_code else 'Nguồn thủ công'}
- **Mô tả:** {description or 'Dự án dịch Light Novel chất lượng cao qua NovelStudio AI Suite.'}
- **Ngày khởi tạo:** `{now_str}`
"""
        (target_dir / "README.md").write_text(readme_content, encoding="utf-8")

        # 2. glossary/characters.md
        chars_content = f"""# 👥 DANH SÁCH NHÂN VẬT & MA TRẬN XƯNG HÔ
*Bộ truyện: {title}*

## [CHAR] 『Nhân vật chính』
- **Vai trò:** Nhân vật chính
- **Xưng hô:** tôi - cậu / ta - ngươi
- **Đặc điểm:** Khởi tạo mặc định
"""
        (target_dir / "glossary" / "characters.md").write_text(chars_content, encoding="utf-8")

        # 3. glossary/terms.md
        terms_content = f"""# 📖 TỪ ĐIỂN THUẬT NGỮ & CANON DATABASE
*Bộ truyện: {title}*
*Quy chuẩn: Giữ nguyên ngoặc góc 『...』 cho kỹ năng, bảo vật, thiên chức.*

## [TERM] 『Thuật ngữ mẫu』 (Sample Term)
- **Ý nghĩa:** Định nghĩa mẫu khởi tạo cho bộ truyện
"""
        (target_dir / "glossary" / "terms.md").write_text(terms_content, encoding="utf-8")

        # 4. glossary/ENTITY_INDEX.md
        entity_content = f"""# 📑 MỤC LỤC THỰC THỂ TOÀN BỘ (ENTITY INDEX)
*Bộ truyện: {title}*
*Tự động đồng bộ và nạp vào Context Cache*
"""
        (target_dir / "glossary" / "ENTITY_INDEX.md").write_text(entity_content, encoding="utf-8")

        # 5. style_guide.md
        style_content = f"""# 🎨 QUY CHUẨN PHONG CÁCH RIÊNG ({title})
*Kế thừa toàn bộ từ Master Style Guide toàn cục*
- Giọng điệu chủ đạo: Sắc bén, dứt khoát chuẩn Light Novel.
- Đại từ xưng hô đặc thù:
"""
        (target_dir / "style_guide.md").write_text(style_content, encoding="utf-8")

        # 6. CHANGELOG.md
        changelog_content = f"""# 📜 NHẬT KÝ THAY ĐỔI & BIÊN TẬP DỰ ÁN

| Thời gian | Danh mục | Nội dung chi tiết |
| :--- | :--- | :--- |
| `{now_str}` | **Khởi tạo** | Khởi tạo dự án truyện `{clean_name}` ({title}) qua NovelStudio UI |
"""
        (target_dir / "CHANGELOG.md").write_text(changelog_content, encoding="utf-8")

        # Refresh state and activate the newly created novel
        state.refresh_novels()
        for n in state.novels:
            if n.name == clean_name:
                state.active_novel = n
                break

        await state.log(f"🎉 Đã khởi tạo thành công bộ truyện mới: {title} ({clean_name})!", "success")
        await state.broadcast("novel_changed", {"name": clean_name})

        return web.json_response({
            "success": True,
            "novel": clean_name,
            "title": title,
            "folder": str(target_dir),
            "syosetu_code": syosetu_code
        })
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def get_novel_info(request: web.Request) -> web.Response:
    if not state.active_novel:
        return web.json_response({"error": "Chưa chọn bộ truyện"}, status=400)

    n = state.active_novel
    raws = n.list_raw_chapters()
    trans = n.list_translated_chapters()

    raw_nums = set(ep for ep, _ in raws)
    trans_nums = set(ep for ep, _ in trans)
    untranslated = sorted(list(raw_nums - trans_nums))

    return web.json_response({
        "name": n.name,
        "folder": str(n.folder),
        "raw_count": len(raws),
        "translated_count": len(trans),
        "raw_min": raws[0][0] if raws else 0,
        "raw_max": raws[-1][0] if raws else 0,
        "trans_min": trans[0][0] if trans else 0,
        "trans_max": trans[-1][0] if trans else 0,
        "untranslated_count": len(untranslated),
        "untranslated_episodes": untranslated[:50]
    })

# ----------------- CONFIG API -----------------
async def get_config(request: web.Request) -> web.Response:
    state.cfg = load_config()
    safe_cfg = json.loads(json.dumps(state.cfg))
    return web.json_response(safe_cfg)

async def update_config(request: web.Request) -> web.Response:
    data = await request.json()
    cur_cfg = load_config()
    for k, v in data.items():
        if isinstance(v, dict) and k in cur_cfg and isinstance(cur_cfg[k], dict):
            cur_cfg[k].update(v)
        else:
            cur_cfg[k] = v
    save_config(cur_cfg)
    state.cfg = load_config()
    state.ai = AIClient(state.cfg)
    await state.log(f"Đã cập nhật cấu hình AI thành công ({state.ai.provider} - {state.ai.model})!", "success")
    return web.json_response({"success": True, "config": state.cfg})

async def test_config(request: web.Request) -> web.Response:
    try:
        data = {}
        if request.can_read_body:
            try:
                data = await request.json()
            except Exception:
                data = {}

        if data and "provider" in data:
            test_provider = data["provider"]
            test_cfg = load_config()
            test_cfg["active_provider"] = test_provider
            if test_provider == "gemini_free":
                if "api_key" in data and data["api_key"]:
                    test_cfg["gemini_free"]["api_key"] = data["api_key"]
                if "model" in data and data["model"]:
                    test_cfg["gemini_free"]["model"] = data["model"]
            elif test_provider == "llmgate":
                if "api_key" in data and data["api_key"]:
                    test_cfg["llmgate"]["api_key"] = data["api_key"]
                if "base_url" in data and data["base_url"]:
                    test_cfg["llmgate"]["base_url"] = data["base_url"]
                if "model" in data and data["model"]:
                    test_cfg["llmgate"]["model"] = data["model"]
            client = AIClient(test_cfg)
        else:
            client = state.ai

        provider = client.provider
        model = client.model
        t0 = time.time()
        res = await client.generate(
            system_instruction="Bạn là trợ lý kiểm tra kết nối AI của NovelStudio.",
            user_prompt="Xin chào! Hãy phản hồi đúng một từ duy nhất: 'OK'."
        )
        elapsed = time.time() - t0
        return web.json_response({
            "success": True,
            "provider": provider,
            "model": model,
            "response": res.strip(),
            "elapsed_seconds": round(elapsed, 2)
        })
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def get_llmgate_models(request: web.Request) -> web.Response:
    try:
        cfg = load_config()
        api_key = request.query.get("api_key", "").strip() or cfg.get("llmgate", {}).get("api_key", "")
        base_url = request.query.get("base_url", "").strip() or cfg.get("llmgate", {}).get("base_url", "https://llmgate.app/v1")
        if not api_key:
            return web.json_response({"success": False, "error": "Chưa có LLMGate API Key"}, status=400)
        models = await fetch_llmgate_models(api_key, base_url)
        return web.json_response({"success": True, "models": models})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)

# ----------------- SYOSETU SCRAPER API -----------------
async def syosetu_info(request: web.Request) -> web.Response:
    url_or_code = request.query.get("query", "").strip()
    code = extract_novel_code(url_or_code)
    if not code:
        return web.json_response({"success": False, "error": "Mã truyện hoặc URL không hợp lệ"}, status=400)

    try:
        syosetu = SyosetuNovel(code)
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            ok = await syosetu.fetch_novel_info_and_toc(client)
            if not ok:
                return web.json_response({"success": False, "error": "Không thể lấy thông tin từ Syosetu"}, status=500)

            return web.json_response({
                "success": True,
                "code": code,
                "title": syosetu.title,
                "author": syosetu.author,
                "total_episodes": len(syosetu.episodes)
            })
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def syosetu_scrape(request: web.Request) -> web.Response:
    if state.is_task_running:
        return web.json_response({"success": False, "error": "Đang có tác vụ khác đang chạy"}, status=400)

    data = await request.json()
    code = extract_novel_code(data.get("code", "").strip())
    start_ep = int(data.get("start", 1))
    end_ep = int(data.get("end", 1))

    if not state.active_novel:
        return web.json_response({"success": False, "error": "Chưa chọn bộ truyện"}, status=400)

    novel = state.active_novel

    async def run_scrape():
        state.is_task_running = True
        try:
            await state.log(f"Bắt đầu cào raw Syosetu ({code}) từ tập {start_ep} đến {end_ep}...", "info")
            syosetu = SyosetuNovel(code)
            import httpx
            async with httpx.AsyncClient(timeout=20.0) as client:
                ok = await syosetu.fetch_novel_info_and_toc(client)
                if not ok:
                    await state.log("Lỗi: Không thể kết nối tới Syosetu", "error")
                    return

                to_dl = [ep for ep in syosetu.episodes if start_ep <= ep["ep"] <= end_ep]
                total = len(to_dl)
                for idx, item in enumerate(to_dl, 1):
                    ep = item["ep"]
                    fname = f"chuong_{ep:03d}_{clean_filename(item['title'])}.txt"
                    fpath = novel.raw_dir / fname
                    if not fpath.exists():
                        content = await syosetu.fetch_chapter_content(client, ep)
                        if content:
                            fpath.write_text(f"# {item['title']}\n\n{content}", encoding="utf-8")
                            await state.log(f"✓ Đã tải Tập {ep}: {item['title']}", "success")
                        else:
                            await state.log(f"⚠️ Không thể tải nội dung Tập {ep}", "warning")
                    else:
                        await state.log(f"⏩ Tập {ep} đã tồn tại trong raw/, bỏ qua.", "info")

                    pct = int((idx / total) * 100)
                    state.task_info = {"name": "Cào Raw Syosetu", "progress": idx, "total": total, "status": "running"}
                    await state.broadcast("progress", {"pct": pct, "current": idx, "total": total, "title": item['title']})
                    await asyncio.sleep(0.3)

            await state.log(f"🎉 Hoàn tất cào {total} chương về thư mục raw/!", "success")
        except Exception as e:
            await state.log(f"Lỗi khi cào raw: {e}", "error")
        finally:
            state.is_task_running = False
            state.task_info = {"name": "", "progress": 0, "total": 0, "status": "idle"}
            await state.broadcast("task_finished", {"task": "scrape"})

    state.current_task = asyncio.create_task(run_scrape())
    return web.json_response({"success": True, "message": "Đã khởi động tiến trình cào raw!"})

# ----------------- TRANSLATION & EDITING API -----------------
async def start_translation(request: web.Request) -> web.Response:
    if state.is_task_running:
        return web.json_response({"success": False, "error": "Đang có tác vụ khác đang chạy"}, status=400)

    data = await request.json()
    start_ep = int(data.get("start", 1))
    end_ep = int(data.get("end", 1))
    concurrency = int(data.get("concurrency", 1))

    if not state.active_novel:
        return web.json_response({"success": False, "error": "Chưa chọn bộ truyện"}, status=400)

    novel = state.active_novel
    raws = novel.list_raw_chapters()
    selected = [(ep, p) for ep, p in raws if start_ep <= ep <= end_ep]

    if not selected:
        return web.json_response({"success": False, "error": "Không tìm thấy chương raw nào trong khoảng đã chọn"}, status=400)

    async def run_trans():
        state.is_task_running = True
        try:
            total = len(selected)
            sem = asyncio.Semaphore(concurrency)
            await state.log(f"🚀 Khởi chạy dịch {total} tập qua {state.ai.provider} ({state.ai.model})...", "info")

            done_count = 0
            tasks = [translate_chapter(p, novel, state.ai, ep, sem) for ep, p in selected]
            for fut in asyncio.as_completed(tasks):
                success, ep, fpath, msg = await fut
                done_count += 1
                pct = int((done_count / total) * 100)
                if success:
                    await state.log(f"✅ [Tập {ep}] Dịch thành công: {msg}", "success")
                else:
                    await state.log(f"❌ [Tập {ep}] Lỗi: {msg}", "error")

                state.task_info = {"name": "Dịch Raw AI", "progress": done_count, "total": total, "status": "running"}
                await state.broadcast("progress", {"pct": pct, "current": done_count, "total": total, "ep": ep})

            await state.log(f"🎉 Hoàn tất dịch thuật {done_count}/{total} tập!", "success")
        except Exception as e:
            await state.log(f"Lỗi trong quá trình dịch: {e}", "error")
        finally:
            state.is_task_running = False
            state.task_info = {"name": "", "progress": 0, "total": 0, "status": "idle"}
            await state.broadcast("task_finished", {"task": "translate"})

    state.current_task = asyncio.create_task(run_trans())
    return web.json_response({"success": True, "message": f"Đã bắt đầu dịch {len(selected)} chương"})

async def start_editing(request: web.Request) -> web.Response:
    if state.is_task_running:
        return web.json_response({"success": False, "error": "Đang có tác vụ khác đang chạy"}, status=400)

    data = await request.json()
    start_ep = int(data.get("start", 1))
    end_ep = int(data.get("end", 1))
    concurrency = int(data.get("concurrency", 1))

    if not state.active_novel:
        return web.json_response({"success": False, "error": "Chưa chọn bộ truyện"}, status=400)

    novel = state.active_novel
    trans = novel.list_translated_chapters()
    selected = [(ep, p) for ep, p in trans if start_ep <= ep <= end_ep]

    if not selected:
        return web.json_response({"success": False, "error": "Không tìm thấy chương đã dịch nào trong khoảng đã chọn"}, status=400)

    async def run_edit():
        state.is_task_running = True
        try:
            total = len(selected)
            sem = asyncio.Semaphore(concurrency)
            await state.log(f"✍️ Khởi chạy Đại Biên Tập V6.0 cho {total} tập qua {state.ai.provider} ({state.ai.model})...", "info")

            done_count = 0
            tasks = [edit_single_chapter(ep, p, novel, state.ai, sem) for ep, p in selected]
            for fut in asyncio.as_completed(tasks):
                success, ep, fpath, msg, diff = await fut
                done_count += 1
                pct = int((done_count / total) * 100)
                if success:
                    await state.log(f"✨ [Tập {ep}] Biên tập hoàn tất: {msg}", "success")
                else:
                    await state.log(f"⚠️ [Tập {ep}] {msg}", "error")

                state.task_info = {"name": "Biên Tập V6.0", "progress": done_count, "total": total, "status": "running"}
                await state.broadcast("progress", {"pct": pct, "current": done_count, "total": total, "ep": ep})

            await state.log(f"🎉 Hoàn tất biên tập {done_count}/{total} tập!", "success")
        except Exception as e:
            await state.log(f"Lỗi trong quá trình biên tập: {e}", "error")
        finally:
            state.is_task_running = False
            state.task_info = {"name": "", "progress": 0, "total": 0, "status": "idle"}
            await state.broadcast("task_finished", {"task": "edit"})

    state.current_task = asyncio.create_task(run_edit())
    return web.json_response({"success": True, "message": f"Đã bắt đầu biên tập {len(selected)} chương"})

async def stop_task(request: web.Request) -> web.Response:
    if state.current_task and not state.current_task.done():
        state.current_task.cancel()
        state.is_task_running = False
        state.task_info = {"name": "", "progress": 0, "total": 0, "status": "idle"}
        await state.log("⏹️ Đã dừng tác vụ đang chạy theo yêu cầu người dùng.", "warn")
        await state.broadcast("task_cancelled", {})
        return web.json_response({"success": True, "message": "Đã dừng tác vụ"})
    return web.json_response({"success": False, "message": "Không có tác vụ nào đang chạy"})

# ----------------- GLOSSARY API (LINGUAGACHA TABLE STYLE) -----------------
async def get_glossary(request: web.Request) -> web.Response:
    if not state.active_novel:
        return web.json_response({"terms": [], "characters": []})

    novel = state.active_novel
    terms_file = novel.glossary_dir / "terms.md"
    chars_file = novel.glossary_dir / "characters.md"
    terms = []

    # Parse characters
    if chars_file.exists():
        content = chars_file.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines():
            m = re.match(r'^##\s*\[([^\]]+)\]\s*(.*)', line.strip())
            if m:
                tag = m.group(1).strip()
                full_name = m.group(2).strip()
                terms.append({
                    "tag": tag,
                    "name": full_name,
                    "source": "Nhân vật",
                    "current": full_name,
                    "proposed": full_name,
                    "category": "Nhân vật",
                    "status": "approved",
                    "note": "Hồ sơ nhân vật chính thức"
                })

    # Parse terms
    if terms_file.exists():
        content = terms_file.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines():
            m = re.match(r'^##\s*\[([^\]]+)\]\s*(.*)', line.strip())
            if m:
                tag = m.group(1).strip()
                full_name = m.group(2).strip()
                name = full_name
                source = ""
                mb = re.search(r'『([^』]+)』', full_name)
                if mb: name = mb.group(1)
                ms = re.search(r'\(([^)]+)\)', full_name)
                if ms: source = ms.group(1)

                cat = "Kỹ năng / Vật phẩm"
                if "SKILL" in tag: cat = "Kỹ năng"
                elif "ITEM" in tag: cat = "Vật phẩm"
                elif "MONSTER" in tag: cat = "Ma thú"
                elif "FACTION" in tag: cat = "Tổ chức"
                elif "TERM" in tag: cat = "Thuật ngữ"

                terms.append({
                    "tag": tag,
                    "name": name,
                    "source": source or "Canon",
                    "current": name,
                    "proposed": f"『{name}』",
                    "category": cat,
                    "status": "approved",
                    "note": full_name
                })

    return web.json_response({
        "novel": novel.name,
        "total_terms": len(terms),
        "terms": terms[:2000]
    })

async def auto_sync_glossary(request: web.Request) -> web.Response:
    if not state.active_novel:
        return web.json_response({"success": False, "error": "Chưa chọn truyện"}, status=400)

    try:
        novel = state.active_novel
        count = auto_sync_glossary_from_translated(novel)
        await state.log(f"🔍 Auto-Sync đã quét và bổ sung {count} thực thể mới vào Glossary!", "success")
        return web.json_response({"success": True, "count": count})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def add_glossary_term(request: web.Request) -> web.Response:
    if not state.active_novel:
        return web.json_response({"success": False, "error": "Chưa chọn truyện"}, status=400)

    try:
        data = await request.json()
        tag = data.get("tag", "TERM").strip().upper()
        vi_name = data.get("vi_name", "").strip()
        raw_name = data.get("raw_name", "").strip()
        note = data.get("note", "").strip()
        if not vi_name:
            return web.json_response({"success": False, "error": "Tên tiếng Việt không được để trống"}, status=400)

        terms_file = state.active_novel.terms_file
        entry = f"\n## [{tag}] 『{vi_name}』 ({raw_name})\n- {note or 'Thêm thủ công qua NovelStudio UI'}\n"
        with open(terms_file, "a", encoding="utf-8") as f:
            f.write(entry)

        await state.log(f"✅ Đã thêm thuật ngữ mới: 『{vi_name}』 [{tag}]", "success")
        return web.json_response({"success": True})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)

# ----------------- EXTERNAL APPS / FOLDER OPENER -----------------
async def open_external(request: web.Request) -> web.Response:
    target = request.query.get("target", "")
    novel_name = request.query.get("novel", "")

    try:
        if target == "web_reader":
            webbrowser.open("http://localhost:8765/web/index.html")
        elif target == "diff_studio":
            webbrowser.open("http://localhost:8765/web/So_Sanh_Diff.html")
        elif target == "folder":
            if novel_name:
                p = PROJECTS_DIR / novel_name
            elif state.active_novel:
                p = state.active_novel.folder
            else:
                p = WORKSPACE_DIR
            if p.exists():
                os.startfile(str(p))
        elif target == "workspace":
            os.startfile(str(WORKSPACE_DIR))
        return web.json_response({"success": True})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)

# ----------------- FLUX ANIME ART API -----------------
async def generate_art(request: web.Request) -> web.Response:
    if not state.active_novel:
        return web.json_response({"success": False, "error": "Chưa chọn truyện"}, status=400)

    data = await request.json()
    prompt = data.get("prompt", "").strip()
    chapter = int(data.get("chapter", 1))
    preset = data.get("preset", "")

    if preset == "dark_fantasy":
        prompt = f"dark fantasy anime light novel, cinematic lighting, epic battle atmosphere, masterwork, {prompt}"
    elif preset == "anime_cute":
        prompt = f"cute anime light novel style, highly detailed, vibrant colors, charming expression, {prompt}"
    elif preset == "action_battle":
        prompt = f"high-octane anime action scene, dynamic perspective, magic aura sparks, impact frame, {prompt}"
    elif preset == "maid_school":
        prompt = f"school AU, cute maid cafe uniform, cheerful anime aesthetic, Kyoto Animation style, {prompt}"

    novel = state.active_novel
    novel.images_dir.mkdir(parents=True, exist_ok=True)
    out_img = novel.images_dir / f"chuong_{chapter:03d}_illustration.jpg"

    await state.log(f"🎨 Đang vẽ ảnh minh họa Tập {chapter} qua FLUX Engine...", "info")
    ok = await generate_anime_illustration(prompt, out_img)

    if ok:
        await state.log(f"✅ Đã vẽ ảnh thành công: {out_img.name}!", "success")
        rel_path = f"/projects/{novel.name}/images/{out_img.name}"
        return web.json_response({"success": True, "image_url": rel_path, "filename": out_img.name})
    else:
        await state.log("❌ Không thể sinh ảnh lúc này. Vui lòng thử lại.", "error")
        return web.json_response({"success": False, "error": "Lỗi sinh ảnh FLUX"}, status=500)

# ----------------- GIT SYNC API -----------------
async def git_sync(request: web.Request) -> web.Response:
    try:
        await state.log("☁️ Đang đồng bộ toàn bộ lên GitHub...", "info")
        # Build chapters.js
        ps_script = TOOLS_DIR / "build_chapters_js.ps1"
        if ps_script.exists():
            subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps_script)], capture_output=True)

        subprocess.run(["git", "add", "-A"], cwd=str(WORKSPACE_DIR), capture_output=True)
        subprocess.run(["git", "commit", "-m", "Novel Studio: Auto-Sync changes to GitHub"], cwd=str(WORKSPACE_DIR), capture_output=True)
        res = subprocess.run(["git", "push", "origin", "main"], cwd=str(WORKSPACE_DIR), capture_output=True, text=True)

        await state.log("✅ Đã đồng bộ thành công lên GitHub!", "success")
        return web.json_response({"success": True, "output": res.stdout})
    except Exception as e:
        await state.log(f"❌ Lỗi Git Sync: {e}", "error")
        return web.json_response({"success": False, "error": str(e)}, status=500)

# ----------------- HTML APP ROUTE -----------------
async def index_handler(request: web.Request) -> web.Response:
    studio_file = WEB_DIR / "studio.html"
    if studio_file.exists():
        return web.FileResponse(studio_file)
    return web.Response(text="<h1>Novel Studio UI is loading...</h1>", content_type="text/html")

async def on_startup(app: web.Application):
    async def _launch():
        await asyncio.sleep(1.0)
        edge_1 = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        edge_2 = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        chrome_1 = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        chrome_2 = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
        url = "http://localhost:8765/studio"

        for b in [edge_1, edge_2, chrome_1, chrome_2]:
            if os.path.exists(b):
                try:
                    subprocess.Popen([b, f"--app={url}", "--window-size=1280,840"])
                    return
                except Exception:
                    pass
        import webbrowser
        webbrowser.open(url)

    asyncio.create_task(_launch())

def make_app() -> web.Application:
    app = web.Application()
    app.on_startup.append(on_startup)
    app.router.add_get("/", index_handler)
    app.router.add_get("/studio", index_handler)
    app.router.add_get("/api/stream", sse_handler)

    app.router.add_get("/api/novels", get_novels)
    app.router.add_post("/api/novel/select", select_novel)
    app.router.add_post("/api/novel/create", create_novel)
    app.router.add_get("/api/novel/info", get_novel_info)

    app.router.add_get("/api/config", get_config)
    app.router.add_post("/api/config", update_config)
    app.router.add_post("/api/config/test", test_config)
    app.router.add_get("/api/models/llmgate", get_llmgate_models)

    app.router.add_post("/api/open/external", open_external)
    app.router.add_get("/api/open/external", open_external)

    app.router.add_get("/api/syosetu/info", syosetu_info)
    app.router.add_post("/api/syosetu/scrape", syosetu_scrape)

    app.router.add_post("/api/translate/start", start_translation)
    app.router.add_post("/api/edit/start", start_editing)
    app.router.add_post("/api/task/stop", stop_task)

    app.router.add_get("/api/glossary", get_glossary)
    app.router.add_post("/api/glossary/auto-sync", auto_sync_glossary)
    app.router.add_post("/api/glossary/term/add", add_glossary_term)

    app.router.add_post("/api/art/generate", generate_art)
    app.router.add_post("/api/git/sync", git_sync)

    # Static routes
    app.router.add_static("/web", WEB_DIR, show_index=False)
    app.router.add_static("/projects", PROJECTS_DIR, show_index=False)

    return app

if __name__ == "__main__":
    app = make_app()
    port = 8765
    print(f"\n=======================================================")
    print(f"🌟 NOVEL STUDIO SERVER (LinguaGacha Minimalist Engine)")
    print(f"🚀 Đang chạy tại: http://localhost:{port}/studio")
    print(f"👉 Đang tự động mở cửa sổ giao diện Desktop...")
    print(f"(Giữ cửa sổ này hoạt động, nhấn Ctrl+C để dừng khi thoát)")
    print(f"=======================================================\n")
    web.run_app(app, host="127.0.0.1", port=port)
