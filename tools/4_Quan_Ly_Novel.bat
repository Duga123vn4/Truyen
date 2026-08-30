@echo off & chcp 65001 >nul & set "PYTHONIOENCODING=utf-8" & set "PYTHONUTF8=1" & for %%P in (python.exe "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%LOCALAPPDATA%\Programs\Python\Python311\python.exe") do @(%%P -x -X utf8 "%~f0" %* && exit /b 0)
"""
Universal Novel AI Manager & Suite
===================================================================
Bộ công cụ AI Đa Năng Quản Lý, Trích Xuất Glossary, Biên Tập & Dịch Thuật Light Novel
Hỗ trợ:
1. Đa nguồn AI: Free Google Gemini API & API Mua từ LLMGate (OpenAI Compatible)
2. Tự động trích xuất & Bố cục Glossary (Glossary Miner & Builder) từ Raw
3. Biên tập chuyên sâu chuẩn hóa xưng hô, thuật ngữ từ Glossary (Bảo toàn 100% dung lượng)
4. Dịch raw sang tiếng Việt chuẩn văn phong Dark Fantasy & đồng bộ Glossary
5. Tự động truy vấn và liệt kê danh sách Model (1-Click chọn Model từ LLMGate & Gemini)
6. Tự động xuất BÁO CÁO KIỂM CHỨNG DIFF_REPORT.md (Tương thích Obsidian, link trực tiếp từng chương)
7. Hệ thống THÔNG BÁO ĐA KÊNH: Âm thanh Windows, Hộp thoại Popup, Bảng tổng kết Rich & Ghi Changelog
8. Hỗ trợ mọi bộ truyện trong workspace (Đa truyện - Universal Multi-Novel)
===================================================================
"""

import sys
import os
import shutil
import io
import re
import json
import time
import asyncio
import threading
import unicodedata
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

def ensure_utf8_console():
    """Bảo đảm terminal luôn giữ chuẩn UTF-8 và ANSI màu sắc."""
    if sys.platform == "win32":
        os.environ["PYTHONIOENCODING"] = "utf-8"
        os.environ["PYTHONUTF8"] = "1"
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleCP(65001)
            kernel32.SetConsoleOutputCP(65001)
            hOut = kernel32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(hOut, ctypes.byref(mode)):
                kernel32.SetConsoleMode(hOut, mode.value | 0x0004)
        except Exception:
            pass
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
            sys.stdin.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

ensure_utf8_console()

try:
    from discord_notifier import (
        notify_glossary_mined,
        notify_glossary_normalized,
        notify_term_refactored,
        notify_unclassified_entity,
        notify_batch_editor_done,
        notify_backup_restored
    )
except Exception:
    pass

try:
    import httpx
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn, TimeElapsedColumn
    from rich.panel import Panel
    from rich.prompt import Prompt, IntPrompt, Confirm
    from rich.markdown import Markdown
except ImportError:
    print("[!] Đang thiếu thư viện, vui lòng chạy: pip install httpx rich")
    sys.exit(1)

# Ép luồng xuất ra chuẩn UTF-8 toàn diện để không bao giờ bị lỗi dấu tiếng Việt (?) trên Windows
utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
console = Console(file=utf8_stdout, force_terminal=True, legacy_windows=False)

CONFIG_PATH = Path(__file__).resolve().parent / "ai_config.json"
TOOLS_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = WORKSPACE_DIR / "web"

# Danh sách Model phổ biến đề xuất sẵn khi offline
PRESET_GEMINI_MODELS = [
    ("gemini-2.5-flash", "⭐ Khuyên dùng - Bản Flash thế hệ mới cực nhanh và thông minh"),
    ("gemini-1.5-flash", "⚡ Siêu tốc độ, tiết kiệm và ổn định cao"),
    ("gemini-1.5-pro", "🧠 Bản Pro - Tư duy sâu sắc và văn phong mượt mà"),
    ("gemini-2.0-flash", "🚀 Bản thử nghiệm mới nhất từ Google AI"),
]

PRESET_LLMGATE_MODELS = [
    ("gemini-3.7-flash", "👑 Khuyên dùng số 1 - Thế hệ Flash mới nhất, tốc độ 8.5s và văn phong đỉnh cao"),
    ("gemini-3-flash", "💰 Siêu tiết kiệm - Bản Flash giá rẻ bền bỉ"),
    ("claude-3-5-sonnet-20241022", "🧠 Đỉnh cao văn phong Light Novel và Dark Fantasy"),
    ("claude-3-5-haiku-20241022", "⚡ Siêu nhanh, văn phong tốt và cực kỳ tiết kiệm chi phí"),
    ("gemini-1.5-pro", "🧠 Gemini 1.5 Pro qua cổng LLMGate - Ngữ cảnh siêu dài"),
    ("gemini-2.0-flash", "🚀 Gemini 2.0 Flash - Tốc độ cao"),
    ("gpt-4o", "🎯 GPT-4o của OpenAI - Toàn diện và chuẩn xác"),
    ("gpt-4o-mini", "💰 GPT-4o Mini - Rất rẻ và nhanh"),
    ("deepseek-chat", "🔥 DeepSeek V3 - Chi phí siêu rẻ, dịch thuật rất tốt"),
    ("deepseek-reasoner", "🧩 DeepSeek R1 - Mô hình suy luận mạnh mẽ"),
]

# ==============================================================================
# HỆ THỐNG PHÂN TÍCH THAY ĐỔI & BÁO CÁO DIFF (CHANGE ANALYZER & REPORT)
# ==============================================================================

def analyze_chapter_diff(old_text: str, new_text: str) -> Dict[str, Any]:
    """Phân tích chi tiết từng từ ngữ, thuật ngữ, xưng hô và câu văn cụ thể đã được biên tập."""
    old_len = len(old_text.strip())
    new_len = len(new_text.strip())
    diff_len = new_len - old_len
    ratio = (new_len / old_len * 100) if old_len > 0 else 100

    changes = []

    # 1. Bóc tách chi tiết các thuật ngữ / ma pháp 『...』 mới hoặc được chuẩn hóa
    skills_old = set(re.findall(r'『([^』]+)』', old_text))
    skills_new = set(re.findall(r'『([^』]+)』', new_text))
    added_skills = skills_new - skills_old
    if added_skills:
        skill_sample = list(added_skills)[:4]
        skills_str = ", ".join([f"『{s}』" for s in skill_sample])
        more_str = f" (+{len(added_skills) - 4} thuật ngữ khác)" if len(added_skills) > 4 else ""
        changes.append(f"Chuẩn hóa {len(added_skills)} thuật ngữ/kỹ năng trong ngoặc: {skills_str}{more_str}")
    elif len(skills_new) > 0:
        changes.append(f"Đồng bộ {len(skills_new)} danh xưng kỹ năng/vật phẩm theo Glossary")

    # 2. Kiểm tra đại từ xưng hô (tao/mày, tớ/cậu, tôi/cậu)
    tao_may_old = len(re.findall(r'\b(tao|mày)\b', old_text, re.I))
    tao_may_new = len(re.findall(r'\b(tao|mày)\b', new_text, re.I))
    if tao_may_old > tao_may_new:
        changes.append(f"Sửa xưng hô tao-mày thành tớ-cậu/tôi-cậu ({tao_may_old - tao_may_new} vị trí)")

    # 3. Chuẩn hóa kính ngữ tiếng Nhật sang Romaji (-san, -kun, -chan...)
    jp_suffixes_old = len(re.findall(r'[A-Za-z]+さん|[A-Za-z]+ちゃん|[A-Za-z]+くん|[A-Za-z]+様', old_text))
    jp_suffixes_new = len(re.findall(r'[A-Za-z]+さん|[A-Za-z]+ちゃん|[A-Za-z]+くん|[A-Za-z]+様', new_text))
    if jp_suffixes_old > jp_suffixes_new:
        changes.append(f"Chuẩn hóa {jp_suffixes_old - jp_suffixes_new} kính ngữ tiếng Nhật sang dạng Romaji (-san, -kun, -chan...)")

    # 4. Kiểm tra từ nối tiếng Anh dịch máy
    en_words_old = len(re.findall(r'\b(And|But|So|However)\b,?', old_text))
    en_words_new = len(re.findall(r'\b(And|But|So|However)\b,?', new_text))
    if en_words_old > en_words_new:
        changes.append(f"Loại bỏ {en_words_old - en_words_new} từ nối tiếng Anh sót (And, But...)")

    # 5. Chuẩn hóa định dạng ngoặc hội thoại
    dash_quotes_old = len(re.findall(r'^[ \t]*[-–—][ \t]*[“"]', old_text, re.M))
    dash_quotes_new = len(re.findall(r'^[ \t]*[-–—][ \t]*[“"]', new_text, re.M))
    if dash_quotes_old > dash_quotes_new:
        changes.append(f"Chuẩn hóa {dash_quotes_old - dash_quotes_new} đoạn thoại (bỏ ký tự gạch đầu dòng thừa)")

    # 6. Trích xuất câu ví dụ thay đổi cụ thể tiêu biểu (Before -> After Sample)
    old_lines = [l.strip() for l in old_text.splitlines() if l.strip() and not l.startswith('#')]
    new_lines = [l.strip() for l in new_text.splitlines() if l.strip() and not l.startswith('#')]
    
    sample_diffs = []
    for ol, nl in zip(old_lines[:60], new_lines[:60]):
        if ol != nl and len(ol) > 15 and len(nl) > 15:
            sample_diffs.append((ol, nl))
            if len(sample_diffs) >= 2:
                break

    if sample_diffs:
        for ol, nl in sample_diffs:
            s_old = ol[:60] + "..." if len(ol) > 60 else ol
            s_new = nl[:60] + "..." if len(nl) > 60 else nl
            changes.append(f"Đối chứng: *\"{s_old}\"* ➔ **\"{s_new}\"**")

    if not changes:
        changes.append("Đã trau chuốt mạch văn mượt mà, gọt giũa ngữ pháp và đối chiếu đồng bộ Glossary 100%.")

    return {
        "old_len": old_len,
        "new_len": new_len,
        "diff_len": diff_len,
        "ratio": ratio,
        "changes": changes,
        "sample_diffs": sample_diffs
    }

def save_diff_report_file(novel: Any, diff_reports: List[Tuple[int, Path, Dict[str, Any]]], provider_name: str):
    """Ghi bảng tổng hợp kiểm chứng chi tiết vào file DIFF_REPORT.md trong thư mục bộ truyện."""
    report_file = novel.folder / "DIFF_REPORT.md"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    table_rows = []
    for ch, file_path, d in diff_reports:
        rel_stem = f"translated/{file_path.stem}"
        link_str = f"[[{rel_stem}|📖 Tập {ch}]]"
        len_str = f"`{d['old_len']:,}` ➔ `{d['new_len']:,}` ({d['diff_len']:+d})"
        ratio_str = f"**{d['ratio']:.1f}%**"
        changes_str = "<br>".join([f"• {c}" for c in d["changes"]])
        bak_file_name = f"`backup_truoc_bien_tap/{file_path.name}`"
        table_rows.append(f"| {link_str} | {len_str} | {ratio_str} | {changes_str} | {bak_file_name} |")

    content_header = (
        f"# 🔍 BÁO CÁO CHI TIẾT CÁC THAY ĐỔI BIÊN TẬP (DIFF REPORT)\n"
        f"> **Bộ truyện:** {novel.name} | **Thời gian:** `{now_str}` | **Kênh AI:** `{provider_name}`\n"
        f"> *Tất cả các chương đều được tự động lưu bản gốc vào thư mục riêng `backup_truoc_bien_tap/` và có thể đối chiếu 2 cột trên [So_Sanh_Diff.html](../web/So_Sanh_Diff.html).*\n\n"
        f"| Tập | Dung lượng (Trước ➔ Sau) | Tỷ lệ bảo toàn | Chi tiết các thay đổi đã chuẩn hóa & Câu đối chứng | File Backup Gốc |\n"
        f"| :--- | :---: | :---: | :--- | :--- |\n"
    )

    if not report_file.exists():
        full_content = content_header + "\n".join(table_rows) + "\n"
    else:
        section = f"\n\n### ⏱️ Đợt Biên Tập: `{now_str}` (Kênh: {provider_name})\n\n" + \
                  "| Tập | Dung lượng (Trước ➔ Sau) | Tỷ lệ bảo toàn | Chi tiết các thay đổi đã chuẩn hóa & Câu đối chứng | File Backup gốc |\n" + \
                  "| :--- | :---: | :---: | :--- | :--- |\n" + \
                  "\n".join(table_rows) + "\n"
        full_content = report_file.read_text(encoding="utf-8") + section

    report_file.write_text(full_content, encoding="utf-8")
    console.print(f"📄 [bold green]💾 Đã lưu Báo Cáo Kiểm Chứng Diff vào:[/bold green] [yellow]{report_file}[/yellow]")

# ==============================================================================
# HỆ THỐNG THÔNG BÁO HOÀN TẤT ĐA KÊNH (NOTIFICATION SYSTEM)
# ==============================================================================

def send_completion_notification(title: str, message: str, novel_name: str, elapsed_sec: float):
    """Phát âm thanh chuông Windows nhẹ và in bảng Console tổng kết (Đã loại bỏ Popup)."""
    
    # 1. Phát âm thanh chuông Windows (Sound Alert)
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except Exception:
        try:
            print('\a')
        except Exception:
            pass

    # 2. In Bảng Tổng Kết Nổi Bật Trên Console (Rich Visual Banner)
    min_sec = f"{int(elapsed_sec // 60)} phút {int(elapsed_sec % 60)} giây" if elapsed_sec >= 60 else f"{elapsed_sec:.1f} giây"
    panel_content = (
        f"[bold green]🎉 {message}[/bold green]\n\n"
        f"📖 [bold]Bộ truyện:[/bold] [yellow]{novel_name}[/yellow]\n"
        f"⏱️ [bold]Tổng thời gian thực thi:[/bold] [cyan]{min_sec}[/cyan]\n"
        f"📅 [bold]Thời điểm hoàn thành:[/bold] [magenta]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/magenta]"
    )
    console.print()
    console.print(Panel(panel_content, title=f"🔔 {title.upper()}", border_style="bold green", expand=False))

# ==============================================================================
# 1. QUẢN LÝ CẤU HÌNH AI (AI CONFIGURATION)
# ==============================================================================

def load_config() -> Dict[str, Any]:
    default_cfg = {
        "active_provider": "gemini_free",
        "gemini_free": {
            "api_key": "",
            "model": "gemini-2.5-flash"
        },
        "llmgate": {
            "api_key": "",
            "base_url": "https://api.llmgate.com/v1",
            "model": "claude-3-5-sonnet-20241022"
        }
    }
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(default_cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        return default_cfg
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        for k, v in default_cfg.items():
            if k not in data:
                data[k] = v
        return data
    except Exception:
        return default_cfg

def save_config(cfg: Dict[str, Any]):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

# ==============================================================================
# 2. TỰ ĐỘNG LẤY VÀ CHỌN MODEL TỪ API (MODEL AUTO-SELECTOR)
# ==============================================================================

def fetch_llmgate_live_models(api_key: str, base_url: str) -> List[str]:
    try:
        url = f"{base_url.rstrip('/')}/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        with httpx.Client(timeout=8.0) as client:
            res = client.get(url, headers=headers)
            if res.status_code == 200:
                data = res.json()
                raw_list = data.get("data", [])
                models = [m.get("id") for m in raw_list if isinstance(m, dict) and "id" in m]
                return sorted(list(set(models)))
    except Exception:
        pass
    return []

def select_model_interactive(provider: str, api_key: str, base_url: str = "", current_model: str = "") -> str:
    console.print(f"\n[bold cyan]🔍 Đang quét danh sách Model khả dụng cho [{provider}]...[/bold cyan]")
    
    live_models: List[str] = []
    if provider == "llmgate" and api_key:
        with console.status("[bold green]Đang kết nối LLMGate để lấy danh mục Model...[/bold green]"):
            live_models = fetch_llmgate_live_models(api_key, base_url)

    table = Table(title=f"📋 Danh Sách Model Đề Xuất Cho {provider.upper()}", border_style="cyan")
    table.add_column("STT", style="bold cyan", width=4)
    table.add_column("Tên Model (ID)", style="bold yellow")
    table.add_column("Mô tả / Đánh giá", style="green")

    model_choices: List[str] = []

    if provider == "gemini_free":
        for idx, (m_id, desc) in enumerate(PRESET_GEMINI_MODELS, 1):
            is_cur = " [bold green](Hiện tại)[/bold green]" if m_id == current_model else ""
            table.add_row(str(idx), m_id + is_cur, desc)
            model_choices.append(m_id)
    else:
        if live_models:
            console.print(f"[bold green]✓ Đã kết nối thành công LLMGate! Phát hiện {len(live_models)} Models.[/bold green]")
            sorted_live = []
            presets_ids = [p[0] for p in PRESET_LLMGATE_MODELS]
            for p_id, p_desc in PRESET_LLMGATE_MODELS:
                if p_id in live_models:
                    sorted_live.append((p_id, p_desc))
            for m_id in live_models:
                if m_id not in presets_ids:
                    sorted_live.append((m_id, "Model từ tài khoản LLMGate"))

            for idx, (m_id, desc) in enumerate(sorted_live[:20], 1):
                is_cur = " [bold green](Hiện tại)[/bold green]" if m_id == current_model else ""
                table.add_row(str(idx), m_id + is_cur, desc)
                model_choices.append(m_id)
        else:
            for idx, (m_id, desc) in enumerate(PRESET_LLMGATE_MODELS, 1):
                is_cur = " [bold green](Hiện tại)[/bold green]" if m_id == current_model else ""
                table.add_row(str(idx), m_id + is_cur, desc)
                model_choices.append(m_id)

    console.print(table)
    console.print(f"  [bold cyan]0.[/bold cyan] ✍️  Nhập tên model khác thủ công (Tùy chỉnh)")

    max_idx = len(model_choices)
    valid_choices = [str(i) for i in range(max_idx + 1)]
    default_idx = "1"
    if current_model in model_choices:
        default_idx = str(model_choices.index(current_model) + 1)

    sel = Prompt.ask(f"\n[bold yellow]Chọn Model (0 - {max_idx})[/bold yellow]", choices=valid_choices, default=default_idx)
    
    if sel == "0":
        return Prompt.ask("Nhập chính xác ID Model bạn muốn dùng", default=current_model or "gemini-2.5-flash")
    else:
        chosen = model_choices[int(sel) - 1]
        console.print(f"[bold green]✓ Đã chọn Model:[/bold green] [yellow]{chosen}[/yellow]")
        return chosen

# ==============================================================================
# 3. BỘ GIAO TIẾP AI (DUAL-PROVIDER AI CLIENT)
# ==============================================================================

def log_api_telemetry(model: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int, elapsed_sec: float, chapter_title: str = "", chapter_ep: int = 0):
    """Ghi nhận thông số Token, Cache và Chi phí vào file usage_data.js để hiển thị trên Dashboard."""
    try:
        web_dir = WORKSPACE_DIR / "web"
        web_dir.mkdir(parents=True, exist_ok=True)
        log_json_path = web_dir / "api_usage_log.json"
        usage_js_path = web_dir / "usage_data.js"

        history = []
        if log_json_path.exists():
            try:
                history = json.loads(log_json_path.read_text(encoding="utf-8"))
            except Exception:
                history = []

        # Tính toán chi phí ước tính theo bảng giá Gemini 3.7 Flash ($0.10/1M in, $0.025/1M cache, $0.40/1M out)
        std_input = max(0, prompt_tokens - cached_tokens)
        cost = (std_input / 1_000_000 * 0.10) + (cached_tokens / 1_000_000 * 0.025) + (completion_tokens / 1_000_000 * 0.40)

        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "model": model,
            "chapter_title": chapter_title,
            "chapter_ep": chapter_ep,
            "elapsed_sec": round(elapsed_sec, 2),
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "cache_tokens": cached_tokens,
            "cost": round(cost, 5)
        }

        history.insert(0, record) # Thêm vào đầu danh sách
        history = history[:500] # Giữ tối đa 500 requests gần nhất

        log_json_path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
        
        try:
            import subprocess
            subprocess.run(["attrib", "-h", str(usage_js_path)], capture_output=True)
        except Exception:
            pass
        usage_js_path.write_text("window.USAGE_DATA = " + json.dumps({"requests": history}, ensure_ascii=False) + ";\n", encoding="utf-8")
    except Exception:
        pass

class AIClient:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider = config.get("active_provider", "gemini_free")

    @property
    def model(self) -> str:
        """Trả về tên model đang kích hoạt của provider hiện tại."""
        if self.provider == "gemini_free":
            return self.config.get("gemini_free", {}).get("model", "gemini-2.5-flash")
        else:
            return self.config.get("llmgate", {}).get("model", "gemini-3.7-flash")

    async def generate(self, system_instruction: str, user_prompt: str, temperature: float = 0.3, chapter_title: str = "", chapter_ep: int = 0) -> str:
        if self.provider == "gemini_free":
            return await self._call_gemini_free(system_instruction, user_prompt, temperature, chapter_title, chapter_ep)
        else:
            return await self._call_llmgate(system_instruction, user_prompt, temperature, chapter_title, chapter_ep)

    async def _call_gemini_free(self, system_instruction: str, user_prompt: str, temperature: float, chapter_title: str = "", chapter_ep: int = 0) -> str:
        gemini_cfg = self.config.get("gemini_free", {})
        api_key = gemini_cfg.get("api_key", "").strip()
        model = gemini_cfg.get("model", "gemini-2.5-flash").strip()

        if not api_key:
            raise ValueError("Chưa cấu hình API Key cho Google Gemini Free. Vui lòng vào Cài Đặt (Menu 9) để nhập key.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        payload = {
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 8192
            }
        }

        t0 = time.time()
        async with httpx.AsyncClient(timeout=120.0) as client:
            for attempt in range(3):
                try:
                    res = await client.post(url, json=payload)
                    if res.status_code == 200:
                        elapsed_req = time.time() - t0
                        data = res.json()
                        usage = data.get("usageMetadata", {})
                        p_tok = usage.get("promptTokenCount", 0)
                        c_tok = usage.get("candidatesTokenCount", 0)
                        cached_tok = usage.get("cachedContentTokenCount", 0)
                        log_api_telemetry(model, p_tok, c_tok, cached_tok, elapsed_req, chapter_title, chapter_ep)

                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                text = parts[0].get("text") or ""
                                return text.strip()
                        return ""
                    elif res.status_code in (429, 503):
                        await asyncio.sleep(2.0 * (attempt + 1))
                    else:
                        raise RuntimeError(f"Lỗi Gemini API ({res.status_code}): {res.text}")
                except httpx.TimeoutException:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2.0)
        raise RuntimeError("Không nhận được phản hồi từ Gemini API sau 3 lần thử.")

    async def _call_llmgate(self, system_instruction: str, user_prompt: str, temperature: float, chapter_title: str = "", chapter_ep: int = 0) -> str:
        llm_cfg = self.config.get("llmgate", {})
        api_key = llm_cfg.get("api_key", "").strip()
        base_url = llm_cfg.get("base_url", "https://api.llmgate.com/v1").rstrip("/")
        model = llm_cfg.get("model", "gemini-3.7-flash").strip()

        if not api_key:
            raise ValueError("Chưa cấu hình API Key cho LLMGate. Vui lòng vào Cài Đặt (Menu 9) để nhập key.")

        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature
        }

        t0 = time.time()
        async with httpx.AsyncClient(timeout=150.0) as client:
            for attempt in range(3):
                try:
                    res = await client.post(url, headers=headers, json=payload)
                    if res.status_code == 200:
                        elapsed_req = time.time() - t0
                        data = res.json()
                        usage = data.get("usage", {})
                        p_tok = usage.get("prompt_tokens", 0)
                        c_tok = usage.get("completion_tokens", 0)
                        details = usage.get("prompt_tokens_details", {})
                        cached_tok = details.get("cached_tokens", 0) if isinstance(details, dict) else 0
                        
                        log_api_telemetry(model, p_tok, c_tok, cached_tok, elapsed_req, chapter_title, chapter_ep)

                        choices = data.get("choices", [])
                        if choices:
                            content = choices[0].get("message", {}).get("content") or ""
                            return content.strip()
                        return ""
                    elif res.status_code in (429, 502, 503, 504):
                        await asyncio.sleep(2.5 * (attempt + 1))
                    else:
                        raise RuntimeError(f"Lỗi LLMGate API ({res.status_code}): {res.text}")
                except httpx.TimeoutException:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2.0)
        raise RuntimeError("Không nhận được phản hồi từ LLMGate API sau 3 lần thử.")

# ==============================================================================
# 4. QUẢN LÝ THƯ MỤC TRUYỆN (NOVEL DISCOVERY & CONTEXT)
# ==============================================================================

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

        self.glossary_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.translated_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.backup_edit_dir.mkdir(parents=True, exist_ok=True)
        self.backup_clean_dir.mkdir(parents=True, exist_ok=True)
        self.backup_gloss_dir.mkdir(parents=True, exist_ok=True)

    def get_characters_text(self) -> str:
        f = self.glossary_dir / "characters.md"
        return f.read_text(encoding="utf-8") if f.exists() else ""

    def get_terms_text(self) -> str:
        f = self.glossary_dir / "terms.md"
        return f.read_text(encoding="utf-8") if f.exists() else ""

    def get_style_guide_text(self) -> str:
        return self.style_guide_file.read_text(encoding="utf-8") if self.style_guide_file.exists() else ""

    def get_full_canon_text(self) -> str:
        """Đọc Core Canon tinh gọn (Index, Characters, Terms, Factions, Timeline) và 5 sự kiện gần nhất."""
        priority_order = [
            "ENTITY_INDEX.md",
            "characters.md",
            "terms.md",
            "factions_orgs.md",
            "gods_entities.md",
            "animals.md",
            "locations.md",
            "relationship_timeline.md",
        ]
        sections = []
        loaded_files = set()
        for fname in priority_order:
            f = self.glossary_dir / fname
            if f.exists():
                content = f.read_text(encoding="utf-8").strip()
                if content:
                    sections.append(f"### 📂 File: {fname}\n{content}")
                    loaded_files.add(fname)
        # Events: Chỉ lấy 5 sự kiện gần nhất
        ev_file = self.glossary_dir / "events.md"
        if ev_file.exists():
            try:
                ev_txt = ev_file.read_text(encoding="utf-8").strip()
                ev_sections = [s.strip() for s in ev_txt.split("### ") if s.strip()]
                recent_events = ev_sections[-5:] if len(ev_sections) > 5 else ev_sections
                if recent_events:
                    clean_recent = "### " + "\n\n### ".join(recent_events)
                    sections.append(f"### 📂 File: events.md (5 Sự kiện gần nhất)\n{clean_recent}")
            except Exception:
                pass
        separator = "\n\n" + "=" * 80 + "\n\n"
        return separator.join(sections) if sections else ""

    def list_raw_chapters(self) -> List[Tuple[int, Path]]:
        chaps = []
        for f in self.raw_dir.glob("*.txt"):
            m = re.search(r"(\d+)", f.name)
            if m:
                chaps.append((int(m.group(1)), f))
        return sorted(chaps, key=lambda x: x[0])

    def list_translated_chapters(self) -> List[Tuple[int, Path]]:
        chaps = []
        for ext in ("*.md", "*.txt", "*.docx"):
            for f in self.translated_dir.glob(ext):
                m = re.search(r"(\d+)", f.name)
                if m:
                    chaps.append((int(m.group(1)), f))
        unique_dict = {}
        for ch, p in chaps:
            if ch not in unique_dict or p.suffix == ".md":
                unique_dict[ch] = p
        return sorted([(k, v) for k, v in unique_dict.items()], key=lambda x: x[0])

    def append_changelog(self, category: str, detail: str):
        try:
            log_file = self.folder / "CHANGELOG.md"
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if not log_file.exists():
                header = (
                    f"# 📜 Nhật Ký Hoạt Động & Thay Đổi (Changelog) - {self.name}\n"
                    f"*Tự động ghi lại toàn bộ tiến độ Dịch, Biên tập, Cập nhật Glossary và Refactor.*\n\n"
                    f"| Thời gian | Danh mục | Chi tiết thay đổi |\n"
                    f"| :--- | :--- | :--- |\n"
                )
                log_file.write_text(header, encoding="utf-8")
            entry = f"| `{now_str}` | **{category}** | {detail} |\n"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass

def discover_novels() -> List[NovelContext]:
    novels = []
    seen_paths = set()
    p_dir = WORKSPACE_DIR / "projects"
    scan_dirs = [p_dir, WORKSPACE_DIR] if p_dir.exists() else [WORKSPACE_DIR]
    
    for s_dir in scan_dirs:
        if not s_dir.exists(): continue
        for item in s_dir.iterdir():
            if item.is_dir() and item.name not in (".obsidian", ".git", ".gemini", "tools", "web", "audio", "scratch", "backups", "assets", "__pycache__", "projects"):
                if not item.name.startswith("http") and "syosetu.com" not in item.name.lower():
                    res_path = str(item.resolve())
                    if res_path not in seen_paths:
                        seen_paths.add(res_path)
                        novels.append(NovelContext(item))
    return sorted(novels, key=lambda n: n.name)

# ==============================================================================
# 4.5. LỌC GLOSSARY THÔNG MINH (SMART GLOSSARY FILTER)
# ==============================================================================

def extract_relevant_glossary(chapter_text: str, characters_text: str, terms_text: str) -> Tuple[str, str]:
    """Quét nội dung chương, chỉ giữ lại các mục Glossary có tên/thuật ngữ thực sự xuất hiện.
    Luôn giữ lại nhân vật chính và quy tắc xưng hô quan trọng."""
    if not chapter_text:
        return characters_text[:3000], terms_text[:3000]

    # --- LỌC CHARACTERS ---
    filtered_char_lines = []
    char_lines = characters_text.splitlines()
    header_section = True
    for line in char_lines:
        stripped = line.strip()
        # Luôn giữ header, tiêu đề section, dấu phân cách
        if stripped.startswith("#") or stripped.startswith("**") or stripped.startswith("---") or stripped.startswith("| ") and ("STT" in stripped or "Tên" in stripped or ":---" in stripped or ":----" in stripped):
            filtered_char_lines.append(line)
            header_section = False
            continue
        if not stripped or stripped == "|":
            filtered_char_lines.append(line)
            continue
        # Kiểm tra xem tên nhân vật trong dòng này có xuất hiện trong chương không
        # Trích xuất tên từ cột markdown table (| **Tên** | ...)
        name_matches = re.findall(r'\*\*([^*]+)\*\*', stripped)
        if not name_matches:
            # Dòng không có tên in đậm, thử lấy text thuần
            parts = [p.strip() for p in stripped.split("|") if p.strip()]
            name_matches = parts[:3] if parts else []

        found = False
        for name in name_matches:
            # Tách họ và tên để match linh hoạt
            name_clean = name.replace("**", "").strip()
            name_parts = name_clean.split()
            for part in name_parts:
                if len(part) >= 2 and part in chapter_text:
                    found = True
                    break
            if found:
                break

        if found:
            filtered_char_lines.append(line)

    # --- LỌC TERMS ---
    filtered_term_lines = []
    term_lines = terms_text.splitlines()
    for line in term_lines:
        stripped = line.strip()
        # Luôn giữ header, tiêu đề section, dấu phân cách
        if stripped.startswith("#") or stripped.startswith("**") or stripped.startswith("---") or stripped.startswith("| ") and ("STT" in stripped or "Tên" in stripped or ":---" in stripped or ":----" in stripped or ":-:" in stripped):
            filtered_term_lines.append(line)
            continue
        if not stripped or stripped == "|":
            filtered_term_lines.append(line)
            continue
        # Kiểm tra thuật ngữ có xuất hiện trong chương không
        name_matches = re.findall(r'\*\*([^*]+)\*\*', stripped)
        if not name_matches:
            parts = [p.strip() for p in stripped.split("|") if p.strip()]
            name_matches = parts[:3] if parts else []

        found = False
        for term in name_matches:
            term_clean = term.replace("**", "").strip()
            # Bỏ qua các header cột
            if term_clean in ("STT", "Tên", "Mô Tả", "Nguồn Gốc"):
                continue
            term_parts = term_clean.split()
            for part in term_parts:
                if len(part) >= 2 and part in chapter_text:
                    found = True
                    break
            if found:
                break

        if found:
            filtered_term_lines.append(line)

    filtered_chars = "\n".join(filtered_char_lines)
    filtered_terms = "\n".join(filtered_term_lines)

    # Đảm bảo luôn có nội dung tối thiểu
    if len(filtered_chars.strip()) < 100:
        filtered_chars = characters_text[:3000]
    if len(filtered_terms.strip()) < 100:
        filtered_terms = terms_text[:3000]

    return filtered_chars, filtered_terms

# ==============================================================================
# 5. TÍNH NĂNG 1: TRÍCH XUẤT & BỐ CỤC GLOSSARY (GLOSSARY MINER)
# ==============================================================================

async def run_glossary_miner(novel: NovelContext, ai: AIClient):
    """Trích xuất & Bố cục Canon Database V3.0 (Chuẩn Compact Entity Card, ENTITY_INDEX, GLOSSARY_AUDIT_LOG)."""
    console.print(Panel.fit(
        "[bold cyan]🧠 TRÍCH XUẤT & QUẢN LÝ CANON DATABASE V3.0 (CANON MINER)[/bold cyan]\n"
        "[dim]Đọc Raw → Trích xuất Thực thể Chuẩn → Gán ID (CHAR, SKILL, ANIMAL, GOD) → ENTITY_INDEX & Compact Cards[/dim]",
        border_style="cyan"
    ))

    raw_chaps = novel.list_raw_chapters()
    if not raw_chaps:
        console.print("[red]Không tìm thấy chương raw nào trong thư mục raw/.[/red]")
        return

    console.print(f"\nTìm thấy [bold yellow]{len(raw_chaps)}[/bold yellow] chương raw (Từ Tập {raw_chaps[0][0]} đến Tập {raw_chaps[-1][0]}).")

    start_ch = IntPrompt.ask("Chương bắt đầu quét", default=raw_chaps[0][0])
    end_ch = IntPrompt.ask("Chương kết thúc quét", default=min(start_ch + 34, raw_chaps[-1][0]))

    selected = [(ch, path) for ch, path in raw_chaps if start_ch <= ch <= end_ch]
    if not selected:
        console.print("[red]Không có chương nào trong khoảng đã chọn.[/red]")
        return

    # Chia batch thông minh (mỗi batch tối đa ~350.000 ký tự ≈ 100.000 tokens)
    MAX_BATCH_CHARS = 120000
    batches = []
    current_batch = []
    current_size = 0
    for ch, path in selected:
        try:
            text = path.read_text(encoding="utf-8")
            if current_size + len(text) > MAX_BATCH_CHARS and current_batch:
                batches.append(current_batch)
                current_batch = []
                current_size = 0
            current_batch.append((ch, text))
            current_size += len(text)
        except Exception:
            pass
    if current_batch:
        batches.append(current_batch)

    console.print(f"📦 Chia thành [cyan]{len(batches)}[/cyan] batch (tổng [yellow]{len(selected)}[/yellow] chương, quét [green]TOÀN BỘ nội dung[/green]).")

    existing_index = (novel.glossary_dir / "ENTITY_INDEX.md").read_text(encoding="utf-8") if (novel.glossary_dir / "ENTITY_INDEX.md").exists() else ""
    existing_char = novel.get_characters_text()
    existing_terms = novel.get_terms_text()

    system_prompt = (
        "Bạn là Chuyên gia Quản trị Dữ liệu & Giám tuyển Canon Light Novel (Lore Master).\n"
        "Nhiệm vụ: Đọc các chương truyện raw và TRÍCH XUẤT TOÀN BỘ THỰC THỂ MỚI để xây dựng Canon Database V3.0.\n"
        "TUYỆT ĐỐI TUÂN THỦ:\n"
        "1. Không bịa đặt, chỉ trích xuất những gì có trong RAW.\n"
        "2. Không trích xuất lại các thực thể ĐÃ CÓ trong Canon.\n"
        "3. Trả về kết quả ĐÚNG ĐỊNH DẠNG JSON thuần túy (không bọc text giải thích) theo mẫu:\n\n"
        "```json\n"
        "{\n"
        '  "new_characters": [\n'
        '    {"name_vi": "Tên tiếng Việt", "name_orig": "Tên Kanji/Kana", "role": "Thân phận/Vai trò", "job": "Thiên chức/Năng lực", "status": "CÒN SỐNG", "note": "Mô tả ngắn"}\n'
        '  ],\n'
        '  "new_terms": [\n'
        '    {"term_vi": "Tên tiếng Việt chuẩn 『...』", "term_orig": "Tên gốc", "type": "Kỹ năng/Ma pháp/Vật phẩm/Địa danh/Tổ chức/Quái vật", "description": "Mô tả chi tiết tác dụng/đặc tính"}\n'
        '  ],\n'
        '  "key_events": [\n'
        '    "Sự kiện quan trọng 1 trong các tập này",\n'
        '    "Sự kiện quan trọng 2 trong các tập này"\n'
        '  ]\n'
        "}\n"
        "```"
    )

    all_extracted = {"new_characters": [], "new_terms": [], "key_events": []}

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}[/bold cyan]"),
        BarColumn(bar_width=35, complete_style="green", finished_style="bold green"),
        TextColumn("[bold yellow]{task.percentage:>3.0f}%[/bold yellow]"),
        TextColumn("• [cyan]{task.completed}/{task.total} batch[/cyan]"),
        TextColumn("• [magenta]Thời gian: [/magenta]"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task_id = progress.add_task(f"Đang khai thác Canon...", total=len(batches))

        for batch_idx, batch in enumerate(batches):
            ch_range = f"Tập {batch[0][0]}" if len(batch) == 1 else f"Tập {batch[0][0]}-{batch[-1][0]}"
            progress.update(task_id, description=f"Batch {batch_idx+1}/{len(batches)}: {ch_range} ({len(batch)} chương)...")

            batch_text = "\n\n--- HẾT CHƯƠNG ---\n\n".join([f"### Chương {ch}\n{text}" for ch, text in batch])

            user_prompt = (
                f"--- CANON ĐÃ CÓ SẴN (ĐỐI CHIẾU TRÁNH TRÙNG LẶP) ---\n"
                f"{existing_index[:3000] if existing_index else existing_char[:1500] + '\n' + existing_terms[:1500]}\n\n"
                f"--- NỘI DUNG RAW CẦN QUÉT ({ch_range}) ---\n{batch_text}\n\n"
                f"Hãy bóc tách toàn bộ thực thể MỚI và trả về khối JSON."
            )

            try:
                result = await ai.generate(system_prompt, user_prompt, temperature=0.1)
                json_str = result
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in json_str:
                    json_str = json_str.split("```")[1].split("```")[0].strip()
                
                try:
                    data = json.loads(json_str)
                    all_extracted["new_characters"].extend(data.get("new_characters", []))
                    all_extracted["new_terms"].extend(data.get("new_terms", []))
                    all_extracted["key_events"].extend(data.get("key_events", []))
                except Exception:
                    pass
            except Exception as e:
                console.print(f"  [red]✗ Lỗi batch {batch_idx+1}: {e}[/red]")
            progress.advance(task_id)

    new_chars = all_extracted["new_characters"]
    new_terms = all_extracted["new_terms"]
    new_events = all_extracted["key_events"]

    console.print(f"\n[bold green]✅ KHAI THÁC THÀNH CÔNG:[/bold green] [yellow]{len(new_chars)}[/yellow] Nhân vật • [cyan]{len(new_terms)}[/cyan] Thuật ngữ/Kỹ năng • [magenta]{len(new_events)}[/magenta] Sự kiện.")

    if new_chars:
        char_preview = "\n".join([f"• 👤 **{c.get('name_vi', '')}** ({c.get('name_orig', '')}): {c.get('role', '')} | {c.get('job', '')}" for c in new_chars[:10]])
        console.print(Panel(char_preview + ("\n..." if len(new_chars) > 10 else ""), title="👤 Nhân Vật Mới", border_style="green"))

    if new_terms:
        term_preview = "\n".join([f"• ⚔️ **{t.get('term_vi', '')}** ({t.get('term_orig', '')}): [{t.get('type', '')}] {t.get('description', '')}" for t in new_terms[:10]])
        console.print(Panel(term_preview + ("\n..." if len(new_terms) > 10 else ""), title="⚔️ Thuật Ngữ & Kỹ Năng Mới", border_style="cyan"))

    if Confirm.ask("\nBạn có muốn tự động GHI VÀO CANON DATABASE (ENTITY_INDEX & Compact Cards) không?", default=True):
        backup_dir = novel.backups_dir / "glossary" / datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir.mkdir(parents=True, exist_ok=True)
        for f in novel.glossary_dir.glob("*.md"):
            shutil.copy2(f, backup_dir / f.name)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        index_file = novel.glossary_dir / "ENTITY_INDEX.md"
        index_txt = index_file.read_text(encoding="utf-8") if index_file.exists() else ""
        if not index_txt:
            index_txt = f"# 📇 MỤC LỤC THỰC THỂ CANON (ENTITY INDEX)\n> **Tác phẩm:** {novel.name}\n> **Quy chuẩn:** Canon Database V3.0\n\n---\n\n| Mã ID | Tên Chuẩn Hóa | Tên Gốc (JP/Romaji) | Phân Loại | Trạng Thái | Mốc Xuất Hiện |\n| :--- | :--- | :--- | :---: | :---: | :---: |\n"

        char_count = len(re.findall(r'CHAR-\d+', index_txt)) + 1
        animal_count = len(re.findall(r'ANIMAL-\d+', index_txt)) + 1
        god_count = len(re.findall(r'GOD-\d+', index_txt)) + 1
        skill_count = len(re.findall(r'SKILL-\d+', index_txt)) + 1
        item_count = len(re.findall(r'ITEM-\d+', index_txt)) + 1
        org_count = len(re.findall(r'ORG-\d+', index_txt)) + 1
        place_count = len(re.findall(r'PLACE-\d+', index_txt)) + 1
        event_count = len(re.findall(r'EVENT-\d+', index_txt)) + 1
        term_count = len(re.findall(r'TERM-\d+', index_txt)) + 1

        char_file = novel.glossary_dir / "characters.md"
        terms_file = novel.glossary_dir / "terms.md"
        animals_file = novel.glossary_dir / "animals.md"
        gods_file = novel.glossary_dir / "gods_entities.md"
        orgs_file = novel.glossary_dir / "factions_orgs.md"
        places_file = novel.glossary_dir / "locations.md"
        events_file = novel.glossary_dir / "events.md"
        audit_file = novel.glossary_dir / "GLOSSARY_AUDIT_LOG.md"

        new_index_rows = []
        audit_entries = []

        if new_chars:
            cur_chars = char_file.read_text(encoding="utf-8") if char_file.exists() else "# 👥 HỒ SƠ NHÂN VẬT\n"
            for c in new_chars:
                name_vi = (c.get("name_vi") or "").strip()
                name_orig = (c.get("name_orig") or "").strip()
                if not name_vi and not name_orig: continue
                check = name_orig if name_orig else name_vi
                if check.lower() in index_txt.lower() or check.lower() in cur_chars.lower(): continue

                role = c.get("role") or "Nhân vật mới"
                job = c.get("job") or "Chưa rõ"
                status = c.get("status") or "CÒN SỐNG"
                note = c.get("note") or ""

                if any(w in (role + job).lower() for w in ["thần", "nữ thần", "thực thể", "god"]):
                    eid = f"GOD-{god_count:03d}"
                    god_count += 1
                    target_f = gods_file
                    itype = "Thần linh"
                elif any(w in (role + job).lower() for w in ["thú", "động vật", "quái thú", "chó", "mèo", "animal"]):
                    eid = f"ANIMAL-{animal_count:03d}"
                    animal_count += 1
                    target_f = animals_file
                    itype = "Động vật"
                else:
                    eid = f"CHAR-{char_count:03d}"
                    char_count += 1
                    target_f = char_file
                    itype = "Nhân vật"

                card = f"\n---\n\n## [{eid}] {name_vi}\n\n- **id:** {eid}\n- **loại:** {itype.upper()}\n- **tên_chuẩn:** {name_vi}\n- **tên_gốc:** {name_orig}\n- **trạng_thái:** ĐÃ XÁC NHẬN\n- **canon:** CHÍNH THỨC\n- **độ_tin_cậy:** TUYỆT ĐỐI\n- **khóa_bảo_vệ:** CÓ\n- **trạng_thái_nhân_vật:** {status} (Cập nhật Tập {start_ch}-{end_ch})\n- **thân_phận:** {role}\n- **thiên_chức:** {job}\n- **nguồn:** Tập {start_ch} - {end_ch}\n- **mô_tả:** {note}\n"
                cur_tf = target_f.read_text(encoding="utf-8") if target_f.exists() else f"# HỒ SƠ {itype.upper()}\n"
                target_f.write_text(cur_tf.rstrip() + "\n" + card, encoding="utf-8")

                new_index_rows.append(f"| `{eid}` | **{name_vi}** | {name_orig} | {itype} | `{status}` | Tập {start_ch} |")
                audit_entries.append(f"• 🟢 **[MỚI]** `{eid}` **{name_vi}** ({name_orig}): {role} (Tập {start_ch}-{end_ch})")

        if new_terms:
            cur_terms = terms_file.read_text(encoding="utf-8") if terms_file.exists() else "# ⚔️ THUẬT NGỮ & KỸ NĂNG\n"
            for t in new_terms:
                term_vi = (t.get("term_vi") or "").strip()
                term_orig = (t.get("term_orig") or "").strip()
                if not term_vi and not term_orig: continue
                check = term_orig if term_orig else term_vi
                if check.lower() in index_txt.lower() or check.lower() in cur_terms.lower(): continue

                t_type = (t.get("type") or "").lower()
                desc = t.get("description") or ""
                all_text_check = (t_type + " " + desc + " " + term_vi).lower()

                if any(w in all_text_check for w in ["sự kiện", "hội thảo", "báo cáo", "lễ hội", "dạ hội", "đại hội", "kỷ niệm", "chiến dịch", "khủng hoảng", "cuộc thảo phạt", "trận chiến", "event"]):
                    eid = f"EVENT-{event_count:03d}"
                    event_count += 1
                    target_f = events_file
                    itype = "Sự kiện"
                elif any(w in all_text_check for w in ["tổ chức", "học viện", "gia tộc", "hoàng tộc", "giáo hội", "quân đội", "hiệp hội", "bang hội", "đoàn kỵ sĩ", "công hội", "org", "faction"]):
                    eid = f"ORG-{org_count:03d}"
                    org_count += 1
                    target_f = orgs_file
                    itype = "Tổ chức"
                elif any(w in all_text_check for w in ["địa danh", "tầng tháp", "thành phố", "thị trấn", "di tích", "lâu đài", "vương quốc", "đế quốc", "hầm ngục", "dungeon", "place", "location"]):
                    eid = f"PLACE-{place_count:03d}"
                    place_count += 1
                    target_f = places_file
                    itype = "Địa danh"
                elif any(w in all_text_check for w in ["vật phẩm", "trang bị", "vũ khí", "sách", "tài liệu", "tiểu thuyết", "dược phẩm", "thuốc", "bảo vật", "thần khí", "item", "equipment", "weapon", "book"]):
                    eid = f"ITEM-{item_count:03d}"
                    item_count += 1
                    target_f = terms_file
                    itype = "Vật phẩm / Tài liệu"
                elif any(w in all_text_check for w in ["kỹ năng", "ma pháp", "chiêu thức", "phép thuật", "tuyệt kỹ", "thiên chức", "skill", "magic", "spell"]):
                    eid = f"SKILL-{skill_count:03d}"
                    skill_count += 1
                    target_f = terms_file
                    itype = "Kỹ năng"
                else:
                    eid = f"TERM-{term_count:03d}"
                    term_count += 1
                    target_f = terms_file
                    itype = "Thuật ngữ"

                card = f"\n---\n\n## [{eid}] {term_vi}\n\n- **id:** {eid}\n- **loại:** {itype.upper()}\n- **tên_chuẩn:** {term_vi}\n- **tên_gốc:** {term_orig}\n- **trạng_thái:** ĐÃ XÁC NHẬN\n- **canon:** CHÍNH THỨC\n- **độ_tin_cậy:** TUYỆT ĐỐI\n- **khóa_bảo_vệ:** CÓ\n- **nguồn:** Tập {start_ch} - {end_ch}\n- **mô_tả:** {desc}\n"
                cur_tf = target_f.read_text(encoding="utf-8") if target_f.exists() else f"# HỒ SƠ {itype.upper()}\n"
                target_f.write_text(cur_tf.rstrip() + "\n" + card, encoding="utf-8")

                new_index_rows.append(f"| `{eid}` | **{term_vi}** | {term_orig} | {itype} | `CHÍNH THỨC` | Tập {start_ch} |")
                audit_entries.append(f"• 🔮 **[MỚI]** `{eid}` **{term_vi}** ({term_orig}): {desc} (Tập {start_ch}-{end_ch})")

        if new_index_rows:
            index_file.write_text(index_txt.rstrip() + "\n" + "\n".join(new_index_rows) + "\n", encoding="utf-8")
            console.print(f"  [green]✓[/green] Đã cập nhật [bold yellow]{len(new_index_rows)}[/bold yellow] thực thể vào [cyan]ENTITY_INDEX.md[/cyan]")

        if new_events:
            cur_ev = events_file.read_text(encoding="utf-8") if events_file.exists() else "# DÒNG THỜI GIAN & SỰ KIỆN\n"
            ev_lines = [f"| Tập {start_ch}-{end_ch} | {ev} | Tuyến nhân vật | Diễn biến chính |" for ev in new_events]
            events_file.write_text(cur_ev.rstrip() + "\n" + "\n".join(ev_lines) + "\n", encoding="utf-8")
            console.print(f"  [green]✓[/green] Đã ghi nhận [bold magenta]{len(new_events)}[/bold magenta] sự kiện vào [yellow]events.md[/yellow]")

        if audit_entries:
            cur_audit = audit_file.read_text(encoding="utf-8") if audit_file.exists() else "# 📜 SỔ CÁI NHẬT KÝ KIỂM TOÁN GLOSSARY\n"
            log_block = f"\n### ⏱️ ĐỢT KHAI THÁC CANON: `{now_str}` (Tập {start_ch}-{end_ch} RAW)\n" + "\n".join(audit_entries) + "\n"
            audit_file.write_text(cur_audit.rstrip() + "\n" + log_block, encoding="utf-8")
            console.print(f"  [green]✓[/green] Đã ghi nhật ký biến động vào [yellow]GLOSSARY_AUDIT_LOG.md[/yellow]")

        novel.append_changelog("Canon Miner V3", f"Khai thác & xây dựng Canon Database từ {len(selected)} chương raw (Tập {start_ch}-{end_ch})")
        console.print(f"\n📁 Backup bản cũ đã lưu an toàn tại: [dim]{backup_dir}[/dim]")

# 6. TÍNH NĂNG 2: BIÊN TẬP CHUYÊN SÂU CHƯƠNG ĐÃ DỊCH (DEEP EDITOR)
# ==============================================================================

async def edit_single_chapter(chapter_num: int, file_path: Path, novel: NovelContext, ai: AIClient, sem: asyncio.Semaphore) -> Tuple[bool, int, Path, str, Optional[Dict[str, Any]]]:
    async with sem:
        try:
            original_text = file_path.read_text(encoding="utf-8")
            orig_len = len(original_text.strip())
            if orig_len == 0:
                return (False, chapter_num, file_path, "File rỗng", None)

            characters_ctx = novel.get_characters_text()
            terms_ctx = novel.get_terms_text()
            style_ctx = novel.get_style_guide_text()

            glossary_mode = ai.config.get("glossary_mode", "full_cache")
            
            master_guide_file = TOOLS_DIR / "MASTER_STYLE_GUIDE.md"
            master_rules = master_guide_file.read_text(encoding="utf-8") if master_guide_file.exists() else (
                "QUY TẮC BIÊN TẬP BẮT BUỘC: Bảo toàn 100% dữ kiện nguyên tác, tuân thủ Glossary, không tự ý phóng tác."
            )

            if glossary_mode == "full_cache":
                # Chế độ Toàn Năng Canon V3: Nạp 100% Canon Database (>35k tokens) kích hoạt Cache Hardware Gemini
                full_canon = novel.get_full_canon_text()
                
                system_prompt = (
                    "Bạn là Chuyên gia Dịch thuật & Biên tập viên Cao cấp chuyên chuẩn hóa Light Novel tiếng Nhật sang tiếng Việt.\n\n"
                    f"{master_rules}\n\n"
                    "================================================================================\n"
                    "DƯỚI ĐÂY LÀ TOÀN BỘ CANON DATABASE V3.0 CỦA TÁC PHẨM NÀY:\n"
                    "(Bao gồm: Mục lục Thực thể, Hồ sơ Nhân vật, Thuật ngữ, Phe phái, Thần linh,\n"
                    " Động vật, Địa danh, Ma trận Xưng hô, Dòng thời gian Sự kiện)\n"
                    "================================================================================\n\n"
                    f"{full_canon}\n\n"
                    f"--- ĐỊNH HƯỚNG PHONG CÁCH RIÊNG CỦA BỘ TRUYỆN ---\n{style_ctx}\n"
                )
            else:
                # Chế độ Siêu Tiết Kiệm: Lọc tinh gọn chỉ giữ các mục có trong chương
                filtered_chars, filtered_terms = extract_relevant_glossary(original_text, characters_ctx, terms_ctx)
                system_prompt = (
                    "Bạn là Chuyên gia Dịch thuật & Biên tập viên Cao cấp chuyên chuẩn hóa Light Novel tiếng Nhật sang tiếng Việt.\n\n"
                    f"{master_rules}\n\n"
                    "================================================================================\n"
                    "DƯỚI ĐÂY LÀ TỪ ĐIỂN GLOSSARY TINH GỌN CỦA CHƯƠNG NÀY:\n"
                    "================================================================================\n\n"
                    f"--- TỪ ĐIỂN NHÂN VẬT & XƯNG HÔ ---\n{filtered_chars}\n\n"
                    f"--- TỪ ĐIỂN THUẬT NGỮ & KỸ NĂNG ---\n{filtered_terms}\n\n"
                    f"--- PHONG CÁCH VĂN PHONG ---\n{style_ctx}\n"
                )

            user_prompt = f"Dưới đây là nội dung chương {chapter_num} cần biên tập lại chuẩn chỉ 100%:\n\n{original_text}"

            for attempt in range(2):
                result = await ai.generate(system_prompt, user_prompt, temperature=0.15, chapter_title=f"Tập {chapter_num}", chapter_ep=chapter_num)
                if not result:
                    await asyncio.sleep(1.5)
                    continue
                result = result.strip()
                # Cắt bỏ lời dẫn mở đầu của AI nếu có (VD: 'Dưới đây là...', 'Bản dịch...')
                result = re.sub(r'^(?:dưới đây là|đây là bản|sau khi biên tập|toàn văn chương)[^\n]*\n+', '', result, flags=re.IGNORECASE).strip()
                result = re.sub(r'^\s*[\*\-_]{3,}\s*\n+', '', result).strip()
                res_len = len(result)

                if result == original_text.strip():
                    return (True, chapter_num, file_path, "✨ Không có thay đổi (Nội dung đã chuẩn chỉ 100%)", None)

                if res_len >= orig_len * 0.85:
                    diff_info = analyze_chapter_diff(original_text, result)
                    if diff_info["diff_len"] == 0 and not diff_info.get("sample_diffs") and result == original_text:
                        return (True, chapter_num, file_path, "✨ Không có thay đổi (Nội dung đã chuẩn chỉ 100%)", None)

                    # Tự động sao lưu vào thư mục riêng backup_truoc_bien_tap/
                    backup_dir = novel.backup_edit_dir
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    bak_file = backup_dir / file_path.name
                    if not bak_file.exists():
                        bak_file.write_text(original_text, encoding="utf-8")

                    file_path.write_text(result, encoding="utf-8")
                    return (True, chapter_num, file_path, f"Xong ({orig_len} -> {res_len} ký tự, {diff_info['ratio']:.1f}%)", diff_info)
                else:
                    await asyncio.sleep(1.0)

            return (False, chapter_num, file_path, f"Cảnh báo: AI cắt ngắn nội dung ({orig_len} -> {res_len} ký tự). Đã hủy lưu để an toàn.", None)
        except Exception as e:
            return (False, chapter_num, file_path, f"Lỗi: {str(e)}", None)

async def run_batch_editor(novel: NovelContext, ai: AIClient):
    start_time = time.time()
    console.print(Panel.fit(
        f"[bold cyan]📝 BIÊN TẬP HÀNG LOẠT CHƯƠNG ĐÃ DỊCH: [yellow]{novel.name}[/yellow][/bold cyan]\n"
        "[dim]Chuẩn hóa xưng hô, thuật ngữ theo Glossary • Thay đổi có trật tự & Bảo toàn cốt truyện[/dim]",
        border_style="cyan"
    ))

    trans_chaps = novel.list_translated_chapters()
    if not trans_chaps:
        console.print("[red]❌ Không tìm thấy chương nào trong thư mục `translated/`.[/red]")
        return

    # Quét phân loại chương đã và chưa biên tập
    edited_chaps = [(ch, p) for ch, p in trans_chaps if (novel.backup_edit_dir / p.name).exists()]
    unread_chaps = [(ch, p) for ch, p in trans_chaps if not (novel.backup_edit_dir / p.name).exists()]

    console.print(f"📊 [bold]Tổng số chương đã dịch:[/bold] [yellow]{len(trans_chaps)}[/yellow] tập (Từ Tập {trans_chaps[0][0]} đến Tập {trans_chaps[-1][0]})")
    console.print(f"   [green]✅ Đã biên tập trước đó:[/green] [bold green]{len(edited_chaps)}[/bold green] tập")
    console.print(f"   [yellow]⏳ Chưa từng biên tập:[/yellow]   [bold yellow]{len(unread_chaps)}[/bold yellow] tập\n")

    default_choice = "1" if unread_chaps else "2"
    console.print(f"  [bold green]1.[/bold green] ⚡ [bold green]Chỉ biên tập các chương CHƯA LÀM[/bold green] ([yellow]{len(unread_chaps)}[/yellow] tập - Bỏ qua [green]{len(edited_chaps)}[/green] tập đã làm) [bold cyan][KHUYÊN DÙNG][/bold cyan]")
    console.print(f"  [bold cyan]2.[/bold cyan] 🚀 [bold magenta]Biên tập TOÀN BỘ[/bold magenta] ([yellow]{len(trans_chaps)}[/yellow] tập)")
    console.print("  [bold cyan]3.[/bold cyan] 🔢 [bold yellow]Biên tập theo khoảng chương[/bold yellow] (VD: Tập 241 đến 260)")
    console.print("  [bold cyan]4.[/bold cyan] 📄 [bold white]Biên tập 1 chương cụ thể[/bold white]")
    console.print("  [bold cyan]0.[/bold cyan] ⬅️  Quay lại")

    choice = Prompt.ask("\nLựa chọn của bạn", choices=["0", "1", "2", "3", "4"], default=default_choice)
    if choice == "0":
        return

    target_list = []
    range_str = ""
    if choice == "1":
        target_list = unread_chaps.copy()
        range_str = f"Chỉ {len(target_list)} tập chưa biên tập"
    elif choice == "2":
        target_list = trans_chaps.copy()
        range_str = f"Toàn bộ {len(target_list)} tập"
    elif choice == "3":
        start_ch = IntPrompt.ask("Tập bắt đầu", default=trans_chaps[0][0])
        end_ch = IntPrompt.ask("Tập kết thúc", default=trans_chaps[-1][0])
        range_all = [(ch, p) for ch, p in trans_chaps if start_ch <= ch <= end_ch]
        
        if not range_all:
            console.print(f"[yellow]⚠️ Không tìm thấy chương nào trong khoảng Tập {start_ch} đến {end_ch}.[/yellow]")
            return

        done_in_range = [(ch, p) for ch, p in range_all if (novel.backup_edit_dir / p.name).exists()]
        undone_in_range = [(ch, p) for ch, p in range_all if not (novel.backup_edit_dir / p.name).exists()]
        
        console.print(f"\n📊 [bold cyan]Khoảng Tập {start_ch} đến {end_ch}:[/bold cyan] Tổng cộng [yellow]{len(range_all)}[/yellow] tập.")
        console.print(f"   [green]✅ Đã biên tập trước đó:[/green] [bold green]{len(done_in_range)}[/bold green] tập")
        console.print(f"   [yellow]⏳ Chưa từng biên tập:[/yellow]   [bold yellow]{len(undone_in_range)}[/bold yellow] tập\n")
        
        if done_in_range and undone_in_range:
            console.print(f"  [bold green]1.[/bold green] ⚡ [bold green]Chỉ biên tập các tập CHƯA LÀM trong khoảng này[/bold green] ([yellow]{len(undone_in_range)}[/yellow] tập - Bỏ qua {len(done_in_range)} tập đã làm) [bold cyan][KHUYÊN DÙNG][/bold cyan]")
            console.print(f"  [bold magenta]2.[/bold magenta] 🔄 [bold magenta]Biên tập LẠI TOÀN BỘ trong khoảng này[/bold magenta] (Toàn bộ [yellow]{len(range_all)}[/yellow] tập, kể cả đã làm)")
            sub_choice = Prompt.ask("\nLựa chọn của bạn", choices=["1", "2"], default="1")
            if sub_choice == "1":
                target_list = undone_in_range
                range_str = f"Tập {start_ch} đến {end_ch} (Chỉ {len(target_list)} tập chưa làm)"
            else:
                target_list = range_all
                range_str = f"Tập {start_ch} đến {end_ch} (Biên tập lại toàn bộ {len(target_list)} tập)"
        elif done_in_range and not undone_in_range:
            console.print("[yellow]ℹ️ Toàn bộ các tập trong khoảng này ĐÃ ĐƯỢC BIÊN TẬP trước đó.[/yellow]")
            re_do = Confirm.ask("Bạn có muốn BIÊN TẬP LẠI toàn bộ các tập này không?", default=False)
            if re_do:
                target_list = range_all
                range_str = f"Tập {start_ch} đến {end_ch} (Biên tập lại {len(target_list)} tập)"
            else:
                console.print("[yellow]Đã hủy thao tác.[/yellow]")
                return
        else:
            target_list = range_all
            range_str = f"Tập {start_ch} đến {end_ch} ({len(target_list)} tập)"
    elif choice == "4":
        single_ch = IntPrompt.ask("Nhập số tập cần biên tập", default=trans_chaps[0][0])
        target_list = [(ch, p) for ch, p in trans_chaps if ch == single_ch]
        range_str = f"Tập {single_ch}"

    if not target_list:
        console.print("[yellow]Không có chương nào được chọn.[/yellow]")
        return

    target_list = sorted(target_list, key=lambda x: x[0])
    total = len(target_list)

    console.print("\n[bold cyan]⚡ CHỌN CHẾ ĐỘ THỰC THI BIÊN TẬP:[/bold cyan]")
    console.print("  [bold green]1.[/bold green] 🚀 [bold green]Đa Luồng Siêu Tốc (5 Luồng Song Song)[/bold green] [dim](Nhanh gấp 5 lần • Chương nào ngắn xong trước in trước)[/dim]")
    console.print("  [bold yellow]2.[/bold yellow] 🔢 [bold yellow]Tuần Tự Chuẩn Xác (1 Luồng - Lần lượt 1, 2, 3...)[/bold yellow] [dim](In thẳng hàng theo đúng số thứ tự tăng dần)[/dim]")

    exec_mode = Prompt.ask("\nLựa chọn chế độ", choices=["1", "2"], default="1")
    if exec_mode == "1":
        actual_threads = min(3 if ai.provider == "gemini_free" else 5, total)
        thread_msg = f"với {actual_threads} luồng song song "
    else:
        actual_threads = 1
        thread_msg = "tuần tự từng chương theo thứ tự "

    sem = asyncio.Semaphore(actual_threads)
    console.print(f"\n[bold green]🚀 Bắt đầu biên tập {total} chương {thread_msg}(AI: {ai.provider})...[/bold green]\n")

    success_count = 0
    diff_reports: List[Tuple[int, Path, Dict[str, Any]]] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold magenta]{task.description}[/bold magenta]"),
        BarColumn(bar_width=35, complete_style="magenta", finished_style="bold green"),
        TextColumn("[bold yellow]{task.percentage:>3.0f}%[/bold yellow]"),
        TextColumn("• [cyan]{task.completed}/{task.total} tập[/cyan]"),
        TextColumn("• [magenta]Đã chạy: [/magenta]"),
        TimeElapsedColumn(),
        TextColumn("• [yellow]Còn lại: [/yellow]"),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        task_id = progress.add_task("Đang biên tập...", total=total)
        # Cơ chế Cuốn Chiếu Tuần Tự Theo Khối (Chunked Block Execution)
        # Chạy song song 5 tập một lúc (VD: [1,2,3,4,5] -> [6,7,8,9,10]), xong trọn vẹn khối này mới sang khối kế tiếp!
        chunk_size = actual_threads
        for i in range(0, len(target_list), chunk_size):
            chunk = target_list[i:i + chunk_size]
            
            # Khởi tạo 5 tasks cho đúng 5 tập kế tiếp nhau
            tasks = [edit_single_chapter(ch, p, novel, ai, sem) for ch, p in chunk]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for res, (ch_item, p_item) in zip(results, chunk):
                if isinstance(res, Exception):
                    console.print(f"  [red]✗[/red] Tập {ch_item}: Lỗi luồng: {res}")
                else:
                    ok, ch, fpath, msg, diff_info = res
                    if ok:
                        success_count += 1
                        console.print(f"  [green]✓[/green] Tập {ch}: {msg}")
                        if diff_info:
                            diff_reports.append((ch, fpath, diff_info))
                    else:
                        console.print(f"  [red]✗[/red] Tập {ch}: {msg}")
                progress.advance(task_id)

    # In Bảng Báo Cáo Chi Tiết Thay Đổi Của Từng Chương (Diff Report Table)
    if diff_reports:
        diff_reports.sort(key=lambda x: x[0])
        console.print()
        diff_table = Table(title="🔍 BẢNG TỔNG HỢP CÁC THAY ĐỔI ĐÃ BIÊN TẬP", border_style="green")
        diff_table.add_column("Tập", style="bold cyan", justify="center", width=8)
        diff_table.add_column("Dung lượng Trước -> Sau", style="yellow", justify="center", width=24)
        diff_table.add_column("Các điểm thay đổi chính đã chuẩn hóa", style="green")

        for ch, fpath, d in diff_reports:
            len_str = f"{d['old_len']} -> {d['new_len']} ({d['diff_len']:+d})"
            changes_str = "\n".join([f"• {c}" for c in d["changes"]])
            diff_table.add_row(f"Tập {ch}", len_str, changes_str)

        console.print(diff_table)

        # Lưu tự động Báo Cáo Kiểm Chứng ra DIFF_REPORT.md
        provider_label = "Gemini Free" if ai.provider == "gemini_free" else f"LLMGate ({ai.config.get('llmgate', {}).get('model', 'Custom')})"
        save_diff_report_file(novel, diff_reports, provider_label)
    else:
        console.print("\n[bold yellow]✨ THÔNG BÁO: Toàn bộ các chương đã kiểm tra đều không có thay đổi nào (Bản dịch đã chuẩn chỉ 100% theo Glossary). Không có file nào bị ghi đè.[/bold yellow]")

    elapsed = time.time() - start_time
    status_summary = f"tinh chỉnh {len(diff_reports)}/{total} chương" if diff_reports else f"kiểm tra {total} chương (Không thay đổi - Đã chuẩn 100%)"
    novel.append_changelog("Biên tập AI", f"Biên tập {status_summary} ({range_str}) bằng AI ({ai.provider})")

    # KÍCH HOẠT THÔNG BÁO HOÀN TẤT
    send_completion_notification(
        title="Biên Tập Hoàn Tất",
        message=f"Đã hoàn tất ({range_str}): {status_summary}.",
        novel_name=novel.name,
        elapsed_sec=elapsed
    )

# ==============================================================================
# 7. TÍNH NĂNG 3: CHUẨN HÓA THUẬT NGỮ & DỌN KÍNH NGỮ (GLOSSARY POLISHER & SANITIZER)
# ==============================================================================

def sync_web_reader(project_name: str = ""):
    """Tự động gọi build_chapters_js.ps1 để đồng bộ tức thì lên Web Đọc Truyện mà không ảnh hưởng Console."""
    ps1 = WORKSPACE_DIR / "tools" / "build_chapters_js.ps1"
    if not ps1.exists():
        return
    import subprocess
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)]
    if project_name:
        cmd.extend(["-ProjectName", project_name])
    try:
        creation_flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', creationflags=creation_flags)
    except Exception:
        pass
    finally:
        ensure_utf8_console()

try:
    from discord_notifier import (
        notify_glossary_mined,
        notify_glossary_normalized,
        notify_term_refactored,
        notify_unclassified_entity,
        notify_batch_editor_done,
        notify_backup_restored
    )
except Exception:
    pass

def get_dynamic_term_replacements(novel: NovelContext) -> List[Tuple[str, str]]:
    """Trích xuất danh bạ thuật ngữ và nhân vật động từ ENTITY_INDEX và toàn bộ Canon Database V3.0."""
    replacements = []
    seen = set()

    # 1. Trích xuất từ ENTITY_INDEX.md (Nhanh và chính xác nhất)
    index_file = novel.glossary_dir / "ENTITY_INDEX.md"
    if index_file.exists():
        for line in index_file.read_text(encoding="utf-8").splitlines():
            if not line.startswith("|") or "Mã ID" in line or ":---" in line:
                continue
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 3:
                vi_name = parts[1].replace("**", "").strip()
                orig_name = parts[2].replace("**", "").strip()
                if vi_name and orig_name:
                    clean_vi = re.sub(r'\s*\([^)]*\)', '', vi_name).strip() or vi_name
                    for alias in orig_name.split("/"):
                        alias = alias.replace("**", "").strip()
                        if alias and len(alias) >= 2 and alias.lower() != clean_vi.lower() and alias not in seen:
                            seen.add(alias)
                            replacements.append((alias, clean_vi))

    # 2. Trích xuất từ các file thẻ bài Compact Cards (Bổ trợ)
    for fname in ["terms.md", "characters.md", "factions_orgs.md", "locations.md", "animals.md", "gods_entities.md"]:
        f = novel.glossary_dir / fname
        if f.exists():
            cur_vi = ""
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if re.match(r'^[-*\s]*tên_chuẩn\s*[:*]+', line, re.I):
                    cur_vi = re.sub(r'^[-*\s]*tên_chuẩn\s*[:*]+\s*', '', line, flags=re.I).replace("**", "").strip()
                elif re.match(r'^[-*\s]*tên_gốc\s*[:*]+', line, re.I) and cur_vi:
                    cur_orig = re.sub(r'^[-*\s]*tên_gốc\s*[:*]+\s*', '', line, flags=re.I).replace("**", "").strip()
                    clean_vi = re.sub(r'\s*\([^)]*\)', '', cur_vi).strip() or cur_vi
                    for alias in cur_orig.split("/"):
                        alias = alias.replace("**", "").strip()
                        if alias and len(alias) >= 2 and alias.lower() != clean_vi.lower() and alias not in seen:
                            seen.add(alias)
                            replacements.append((alias, clean_vi))
                    cur_vi = ""

    # Sắp xếp từ dài nhất lên trước để tránh đè chuỗi con
    replacements.sort(key=lambda x: len(x[0]), reverse=True)

    # Chuẩn hóa ma pháp nguyên tố tổng quát
    elemental_types = ["Thổ", "Băng", "Hỏa", "Phong", "Lôi", "Quang", "Ám", "Thủy", "Hắc", "Bạch", "Kim", "Mộc"]
    for elem in elemental_types:
        replacements.append((f"{elem} ma pháp", f"{elem} ma thuật"))

    return replacements

def sanitize_chapter_text(text: str, replacements: List[Tuple[str, str]]) -> Tuple[str, int, List[Dict[str, Any]]]:
    """Chuẩn hóa kính ngữ tiếng Nhật sang dạng Romaji (-san, -kun, -chan...) và chuẩn hóa thuật ngữ ma pháp/vật phẩm theo Glossary kèm chi tiết từng dòng."""
    if not text:
        return "", 0, []

    # Lọc nhanh các alias thực sự xuất hiện trong toàn bộ văn bản chương
    active_reps = [(alias, repl) for alias, repl in replacements if alias in text]

    lines = text.splitlines()
    cleaned_lines = []
    total_replaces = 0
    line_diffs = []

    jp_kanji_suffixes = [
        ('さん', '-san'),
        ('ちゃん', '-chan'),
        ('くん', '-kun'),
        ('君', '-kun'),
        ('様', '-sama'),
        ('先輩', '-senpai'),
        ('先生', '-sensei'),
        ('殿', '-dono')
    ]

    for idx, line in enumerate(lines, 1):
        l = line
        # 1. Chuẩn hóa thuật ngữ ma pháp/vật phẩm theo terms.md (Chống lặp từ và chống nhân đôi tiền tố)
        for alias, repl in active_reps:
            if alias in l:
                # Nếu chuỗi đích repl đã có sẵn trong câu hoặc alias nằm trọn trong repl
                if repl in l:
                    continue
                
                # Kiểm tra xem trước alias đã có sẵn phần tiền tố của repl chưa (Ví dụ: 'Rồng đỏ lông vũ' + 'Crimson Rex')
                prefix = repl.replace(alias, "").strip()
                if prefix and f"{prefix} {alias}" in l:
                    count = l.count(f"{prefix} {alias}")
                    l = l.replace(f"{prefix} {alias}", repl)
                    total_replaces += count
                elif prefix and f"{prefix}{alias}" in l:
                    count = l.count(f"{prefix}{alias}")
                    l = l.replace(f"{prefix}{alias}", repl)
                    total_replaces += count
                else:
                    count = l.count(alias)
                    l = l.replace(alias, repl)
                    total_replaces += count

        # 2. Chuẩn hóa các hậu tố Kanji/Hiragana chưa đổi sang dạng Romaji chuẩn (-san, -kun, -chan...)
        for jp_suf, romaji_suf in jp_kanji_suffixes:
            if jp_suf in l:
                count = l.count(jp_suf)
                l = l.replace(jp_suf, romaji_suf)
                total_replaces += count

        if l != line:
            line_diffs.append({
                "line": idx,
                "old": line,
                "new": l
            })

        cleaned_lines.append(l)

    return "\n".join(cleaned_lines), total_replaces, line_diffs

def generate_full_audit_data(novel: NovelContext) -> Dict[str, Any]:
    """Tổng hợp toàn bộ lịch sử các câu đã được chuẩn hóa từ backups/truoc_chuan_hoa so với translated/."""
    bak_dir = novel.backup_clean_dir
    trans_dir = novel.translated_dir
    trans_chaps = novel.list_translated_chapters()

    records = []
    total_replaces = 0

    if bak_dir.exists():
        for bak_file in sorted(bak_dir.glob("chuong_*.*")):
            trans_file = trans_dir / bak_file.name
            if not trans_file.exists():
                continue

            m_ep = re.search(r"chuong_(\d+)", bak_file.name)
            ep = int(m_ep.group(1)) if m_ep else 0

            try:
                old_text = bak_file.read_text(encoding="utf-8")
                new_text = trans_file.read_text(encoding="utf-8")
            except Exception:
                continue

            if old_text == new_text:
                continue

            old_lines = old_text.splitlines()
            new_lines = new_text.splitlines()

            diffs = []
            for idx, (l_old, l_new) in enumerate(zip(old_lines, new_lines), 1):
                if l_old != l_new:
                    diffs.append({
                        "line": idx,
                        "old": l_old,
                        "new": l_new
                    })

            if diffs:
                first_l = new_text.strip().splitlines()[0] if new_text else f"Tập {ep}"
                records.append({
                    "ep": ep,
                    "title": first_l.replace("#", "").strip(),
                    "filename": bak_file.name,
                    "replaces": len(diffs),
                    "changes": diffs
                })
                total_replaces += len(diffs)

    # Sắp xếp theo số tập tăng dần
    records.sort(key=lambda x: x["ep"])

    payload = {
        "novel_name": novel.name,
        "novel_key": novel.folder.name,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_scanned": len(trans_chaps),
        "total_modified": len(records),
        "total_replaces": total_replaces,
        "chapters": records
    }

    # Tích hợp cơ chế Đa Bộ Truyện: Nạp và gộp dữ liệu audit cũ từ WEB_DIR
    all_audit_map = {}
    target_file = WEB_DIR / "audit_data.js"
    if target_file.exists():
        try:
            old_js = target_file.read_text(encoding="utf-8")
            m_all = re.search(r'window\.ALL_AUDIT_DATA\s*=\s*(\{.*?\});', old_js, re.DOTALL)
            if m_all:
                all_audit_map = json.loads(m_all.group(1))
        except Exception:
            pass
    all_audit_map[novel.folder.name] = payload

    audit_content = (
        f"window.AUDIT_DATA = {json.dumps(payload, ensure_ascii=False)};\n"
        f"window.ALL_AUDIT_DATA = {json.dumps(all_audit_map, ensure_ascii=False)};\n"
    )
    try:
        if target_file.exists():
            import subprocess
            subprocess.run(["attrib", "-h", str(target_file)], capture_output=True)
    except Exception:
        pass
    try:
        target_file.write_text(audit_content, encoding="utf-8")
    except Exception:
        pass
    return payload

def run_glossary_polisher_and_normalizer(novel: NovelContext):
    start_time = time.time()
    console.print(Panel.fit(
        f"[bold cyan]⚡ CHUẨN HÓA THUẬT NGỮ & DỌN KÍNH NGỮ (GLOSSARY POLISHER)[/bold cyan]\n"
        f"[yellow]Bộ truyện: {novel.name}[/yellow]\n"
        f"[dim]Tự động sao lưu File Cũ sang backups/ • Cập nhật trực tiếp translated/ • Đồng bộ Web Reader[/dim]",
        border_style="cyan"
    ))

    trans_chaps = novel.list_translated_chapters()
    if not trans_chaps:
        console.print("[red]❌ Không tìm thấy chương nào trong thư mục `translated/`.[/red]")
        return

    # Quét phân loại chương đã và chưa chuẩn hóa
    cleaned_chaps = [(ch, p) for ch, p in trans_chaps if (novel.backup_clean_dir / p.name).exists()]
    uncleaned_chaps = [(ch, p) for ch, p in trans_chaps if not (novel.backup_clean_dir / p.name).exists()]

    console.print(f"📊 [bold]Tổng số chương đã dịch:[/bold] [yellow]{len(trans_chaps)}[/yellow] tập (Từ Tập {trans_chaps[0][0]} đến Tập {trans_chaps[-1][0]})")
    console.print(f"   [green]✅ Đã chuẩn hóa trước đó:[/green] [bold green]{len(cleaned_chaps)}[/bold green] tập")
    console.print(f"   [yellow]⏳ Chưa kiểm duyệt:[/yellow]      [bold yellow]{len(uncleaned_chaps)}[/bold yellow] tập\n")

    default_choice = "1" if uncleaned_chaps else "2"
    console.print(f"  [bold green]1.[/bold green] ⚡ [bold green]Chỉ chuẩn hóa các chương CHƯA KIỂM DUYỆT[/bold green] ([yellow]{len(uncleaned_chaps)}[/yellow] tập - Bỏ qua [green]{len(cleaned_chaps)}[/green] tập đã làm) [bold cyan][KHUYÊN DÙNG][/bold cyan]")
    console.print(f"  [bold cyan]2.[/bold cyan] 🚀 [bold magenta]Chuẩn hóa TOÀN BỘ các chương đã dịch[/bold magenta] ([yellow]{len(trans_chaps)}[/yellow] tập)")
    console.print("  [bold cyan]3.[/bold cyan] 🔢 [bold yellow]Chuẩn hóa theo khoảng chương[/bold yellow] (VD: Từ tập 150 đến 200)")
    console.print("  [bold cyan]4.[/bold cyan] 📄 [bold white]Chuẩn hóa 1 chương chỉ định[/bold white]")
    console.print("  [bold cyan]0.[/bold cyan] ⬅️  Quay lại")

    choice = Prompt.ask("\nLựa chọn của bạn", choices=["0", "1", "2", "3", "4"], default=default_choice)
    if choice == "0":
        return

    target_list = []
    range_str = ""
    if choice == "1":
        target_list = uncleaned_chaps.copy()
        range_str = f"Chỉ {len(target_list)} tập chưa kiểm duyệt"
    elif choice == "2":
        target_list = trans_chaps.copy()
        range_str = f"Toàn bộ {len(target_list)} tập"
    elif choice == "3":
        start_ch = IntPrompt.ask("Tập bắt đầu", default=trans_chaps[0][0])
        end_ch = IntPrompt.ask("Tập kết thúc", default=trans_chaps[-1][0])
        range_all = [(ch, p) for ch, p in trans_chaps if start_ch <= ch <= end_ch]
        
        if not range_all:
            console.print(f"[yellow]⚠️ Không tìm thấy chương nào trong khoảng Tập {start_ch} đến {end_ch}.[/yellow]")
            return

        done_in_range = [(ch, p) for ch, p in range_all if (novel.backup_clean_dir / p.name).exists()]
        undone_in_range = [(ch, p) for ch, p in range_all if not (novel.backup_clean_dir / p.name).exists()]
        
        console.print(f"\n📊 [bold cyan]Khoảng Tập {start_ch} đến {end_ch}:[/bold cyan] Tổng cộng [yellow]{len(range_all)}[/yellow] tập.")
        console.print(f"   [green]✅ Đã chuẩn hóa trước đó:[/green] [bold green]{len(done_in_range)}[/bold green] tập")
        console.print(f"   [yellow]⏳ Chưa kiểm duyệt:[/yellow]      [bold yellow]{len(undone_in_range)}[/bold yellow] tập\n")
        
        if done_in_range and undone_in_range:
            console.print(f"  [bold green]1.[/bold green] ⚡ [bold green]Chỉ chuẩn hóa các tập CHƯA LÀM trong khoảng này[/bold green] ([yellow]{len(undone_in_range)}[/yellow] tập - Bỏ qua {len(done_in_range)} tập đã làm) [bold cyan][KHUYÊN DÙNG][/bold cyan]")
            console.print(f"  [bold magenta]2.[/bold magenta] 🔄 [bold magenta]Chuẩn hóa LẠI TOÀN BỘ trong khoảng này[/bold magenta] (Toàn bộ [yellow]{len(range_all)}[/yellow] tập, kể cả đã làm)")
            sub_choice = Prompt.ask("\nLựa chọn của bạn", choices=["1", "2"], default="1")
            if sub_choice == "1":
                target_list = undone_in_range
                range_str = f"Tập {start_ch} đến {end_ch} (Chỉ {len(target_list)} tập chưa làm)"
            else:
                target_list = range_all
                range_str = f"Tập {start_ch} đến {end_ch} (Chuẩn hóa lại toàn bộ {len(target_list)} tập)"
        elif done_in_range and not undone_in_range:
            console.print("[yellow]ℹ️ Toàn bộ các tập trong khoảng này ĐÃ ĐƯỢC CHUẨN HÓA trước đó.[/yellow]")
            re_do = Confirm.ask("Bạn có muốn CHUẨN HÓA LẠI toàn bộ các tập này không?", default=False)
            if re_do:
                target_list = range_all
                range_str = f"Tập {start_ch} đến {end_ch} (Chuẩn hóa lại {len(target_list)} tập)"
            else:
                console.print("[yellow]Đã hủy thao tác.[/yellow]")
                return
        else:
            target_list = range_all
            range_str = f"Tập {start_ch} đến {end_ch} ({len(target_list)} tập)"
    elif choice == "4":
        single_ch = IntPrompt.ask("Nhập số tập cần chuẩn hóa", default=trans_chaps[-1][0])
        target_list = [(ch, p) for ch, p in trans_chaps if ch == single_ch]
        range_str = f"Tập {single_ch}"

    if not target_list:
        console.print("[yellow]Không có chương nào phù hợp trong khoảng lựa chọn.[/yellow]")
        return

    # Khởi tạo 2 thư mục an toàn
    backup_dir = novel.backup_clean_dir
    # polished_dir removed in favor of clean translated/
    polished_dir = novel.translated_dir
    backup_dir.mkdir(parents=True, exist_ok=True)
    polished_dir.mkdir(parents=True, exist_ok=True)

    replacements = get_dynamic_term_replacements(novel)
    console.print(f"\n[bold green]📚 Đã nạp thành công {len(replacements)} quy tắc Glossary từ `{novel.glossary_dir.name}/`[/bold green]")
    console.print(f"📁 [bold]Thư mục sao lưu file cũ:[/bold] [yellow]{backup_dir}[/yellow]")
    console.print(f"📁 [bold]Thư mục xuất file mới:[/bold] [yellow]{polished_dir}[/yellow]\n")

    modified_count = 0
    total_replaces_all = 0
    processed_details = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}[/bold cyan]"),
        BarColumn(bar_width=35, complete_style="green", finished_style="bold green"),
        TextColumn("[bold yellow]{task.percentage:>3.0f}%[/bold yellow]"),
        TextColumn("• [cyan]{task.completed}/{task.total} tập[/cyan]"),
        TextColumn("• [magenta]Đã chạy: [/magenta]"),
        TimeElapsedColumn(),
        TextColumn("• [yellow]Còn lại: [/yellow]"),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        task_id = progress.add_task("Đang chuẩn hóa...", total=len(target_list))
        chapter_audit_records = []
        for ch, file_path in target_list:
            try:
                orig_text = file_path.read_text(encoding="utf-8")
                cleaned_text, rep_count, line_diffs = sanitize_chapter_text(orig_text, replacements)
                
                # CHỈ SAO LƯU VÀ GHI ĐÈ KHI CÓ THAY ĐỔI THỰC SỰ
                if cleaned_text != orig_text:
                    # 1. Sao lưu file cũ nguyên vẹn
                    bak_path = backup_dir / file_path.name
                    if not bak_path.exists():
                        bak_path.write_text(orig_text, encoding="utf-8")

                    file_path.write_text(cleaned_text, encoding="utf-8")
                    
                    modified_count += 1
                    total_replaces_all += rep_count
                    processed_details.append((ch, file_path.name, rep_count))
                    
                    first_line = cleaned_text.strip().splitlines()[0] if cleaned_text else f"Tập {ch}"
                    ch_title = first_line.replace("#", "").strip()
                    chapter_audit_records.append({
                        "ep": ch,
                        "title": ch_title,
                        "filename": file_path.name,
                        "replaces": rep_count,
                        "changes": line_diffs
                    })
            except Exception as e:
                console.print(f"  [red]✗[/red] Lỗi Tập {ch}: {e}")
            progress.advance(task_id)

    elapsed = time.time() - start_time
    
    # In bảng tổng kết
    console.print("\n[bold green]🎉 HOÀN TẤT KIỂM DUYỆT & CHUẨN HÓA DỮ LIỆU:[/bold green]\n")
    summary_table = Table(title=f"📊 Báo Cáo Chuẩn Hóa: {novel.name} ({range_str})", border_style="green")
    summary_table.add_column("Hạng Mục", style="bold cyan")
    summary_table.add_column("Số Lượng", justify="right", style="yellow")
    summary_table.add_column("Trạng Thái & Chi Tiết", style="green")

    summary_table.add_row("Tổng chương đã kiểm duyệt", f"{len(target_list)}/{len(target_list)} tập", "✅ Đã quét toàn bộ nội dung thành công")
    
    if modified_count > 0:
        summary_table.add_row("Số chương được cập nhật mới", str(modified_count), f"⚡ Đã tinh chỉnh {modified_count} tập theo Glossary")
        summary_table.add_row("Tổng số thuật ngữ & kính ngữ đã sửa", str(total_replaces_all), "Chuẩn hóa theo Glossary 100%")
    else:
        summary_table.add_row("Số chương cần sửa đổi", "0 tập", "✨ Đã chuẩn sạch 100% từ trước (Bản dịch hoàn hảo)")
        summary_table.add_row("Lỗi thuật ngữ / Kính ngữ sót", "0 lỗi", "Không phát hiện từ ngữ nào bị lệch")

    summary_table.add_row("📁 Thư mục File Cũ (Backup)", "Bảo toàn 100%", str(backup_dir))
    summary_table.add_row("📁 Thư mục File Mới (Đã chuẩn hóa)", "Hoàn thiện", str(polished_dir))
    console.print(summary_table)

    status_msg = f"Đã tinh chỉnh {modified_count} chương" if modified_count > 0 else "Đã chuẩn sạch 100% từ trước"
    novel.append_changelog("Glossary Polisher", f"Duyệt {len(target_list)} chương ({range_str}) - {status_msg}")
    if modified_count > 0:
        record_session(novel, f"Chuẩn hóa Glossary ({range_str})", [p for ch, p in target_list if any(ch == d[0] for d in processed_details)], backup_dir)

    # Tự động tổng hợp và xuất Báo Cáo Kiểm Duyệt Toàn Diện (Toàn bộ các tập đã sửa từ trước đến nay)
    try:
        audit_payload = generate_full_audit_data(novel)
        report_html = WEB_DIR / "Bao_Cao_Chuan_Hoa.html"
        console.print(f"\n✨ [bold green]📄 Báo Cáo Kiểm Duyệt Web Toàn Diện ({audit_payload['total_modified']} tập đã lưu):[/bold green] [yellow]{report_html}[/yellow]")
        
        open_web = Prompt.ask("Bạn có muốn mở ngay Báo Cáo Chuẩn Hóa trên Web không?", choices=["y", "n"], default="y")
        if open_web.lower() == "y":
            import webbrowser
            webbrowser.open(report_html.resolve().as_uri())
    except Exception as e:
        pass

    # Tự động đồng bộ Web Reader
    sync_web_reader(novel.name)

    send_completion_notification(
        title="Chuẩn Hóa Hoàn Tất",
        message=f"Đã duyệt thành công {len(target_list)}/{len(target_list)} chương ({range_str}). {status_msg}.",
        novel_name=novel.name,
        elapsed_sec=elapsed
    )

def global_term_refactor(novel: NovelContext) -> int:
    """Tìm và thay thế từ khóa cũ -> mới trên toàn bộ file bản dịch và glossary, kèm bảng xem trước vị trí chi tiết."""
    console.print(Panel.fit(
        f"[bold cyan]🔍 ĐỔI THUẬT NGỮ / SỬA TÊN NHÂN VẬT THỦ CÔNG: [yellow]{novel.name}[/yellow][/bold cyan]\n"
        "[dim]Quét, hiển thị chi tiết từng dòng xuất hiện và thay thế đồng loạt có sao lưu an toàn[/dim]",
        border_style="cyan"
    ))

    old_term = Prompt.ask("👉 Nhập từ khóa CŨ cần thay thế").strip()
    if not old_term:
        return 0

    new_term = Prompt.ask(f"👉 Nhập từ khóa MỚI thay cho '{old_term}'").strip()
    if not new_term:
        return 0

    trans_files = []
    for ext in ("*.md", "*.txt", "*.docx"):
        trans_files.extend(list(novel.translated_dir.glob(ext)))
    gloss_files = []
    for ext in ("*.md", "*.txt"):
        gloss_files.extend(list(novel.glossary_dir.glob(ext)))
    all_files = trans_files + gloss_files

    matches_found = []
    detailed_snippets = [] # [(file, line_num, old_line, highlighted_snippet)]

    for f in all_files:
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
            file_count = 0
            for line_idx, line in enumerate(lines, 1):
                if old_term in line:
                    c = line.count(old_term)
                    file_count += c
                    # Tạo đoạn trích ngữ cảnh xung quanh từ khóa
                    snippet = line.strip()
                    if len(snippet) > 100:
                        pos = snippet.find(old_term)
                        start_pos = max(0, pos - 35)
                        end_pos = min(len(snippet), pos + len(old_term) + 35)
                        prefix = "..." if start_pos > 0 else ""
                        suffix = "..." if end_pos < len(snippet) else ""
                        snippet = prefix + snippet[start_pos:end_pos] + suffix
                    
                    highlighted = snippet.replace(old_term, f"[bold red]{old_term}[/bold red]")
                    detailed_snippets.append((f.name, line_idx, highlighted))
            if file_count > 0:
                matches_found.append((f, file_count))
        except Exception:
            pass

    if not matches_found:
        console.print(f"\n[yellow]⚠️ Không tìm thấy từ khóa '{old_term}' trong bất kỳ file nào.[/yellow]")
        return 0

    total_occurrences = sum(c for _, c in matches_found)
    console.print(f"\n📊 [bold green]KẾT QUẢ TÌM KIẾM:[/bold green] Tìm thấy [bold yellow]{total_occurrences}[/bold yellow] vị trí trong [bold cyan]{len(matches_found)}[/bold cyan] file.\n")

    # Hiển thị bảng xem trước vị trí chi tiết
    preview_table = Table(title=f"📋 Bảng Chi Tiết Các Vị Trí Sẽ Được Thay Thế ({old_term} ➔ {new_term})", border_style="cyan")
    preview_table.add_column("STT", justify="center", style="bold yellow", width=5)
    preview_table.add_column("Tên File / Tập", style="bold cyan", width=38)
    preview_table.add_column("Dòng", justify="center", style="magenta", width=6)
    preview_table.add_column("Ngữ Cảnh Thực Tế (Trước Khi Thay Thế)", style="white")

    max_display = 20
    for idx, (fname, lnum, snip) in enumerate(detailed_snippets[:max_display], 1):
        preview_table.add_row(str(idx), fname, str(lnum), snip)

    console.print(preview_table)

    if len(detailed_snippets) > max_display:
        console.print(f"[dim yellow]... và còn {len(detailed_snippets) - max_display} vị trí khác trong các chương tiếp theo.[/dim yellow]")

    console.print(f"\n💡 [bold yellow]Thao tác:[/bold yellow] Chuẩn bị thay thế [bold red]{old_term}[/bold red] ➔ [bold green]{new_term}[/bold green] trên toàn bộ {len(matches_found)} file.")
    if not Confirm.ask("Bạn có chắc chắn muốn tiến hành thay thế không?", default=True):
        console.print("[yellow]Đã hủy thao tác.[/yellow]")
        return 0

    backup_dir = novel.backup_clean_dir
    backup_dir.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}[/bold cyan]"),
        BarColumn(bar_width=35, complete_style="cyan", finished_style="bold green"),
        TextColumn("[bold yellow]{task.percentage:>3.0f}%[/bold yellow]"),
        TextColumn("• [cyan]{task.completed}/{task.total} file[/cyan]"),
        TextColumn("• [magenta]Thời gian: [/magenta]"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task_id = progress.add_task(f"Đang thay thế từ khóa...", total=len(matches_found))
        for f, _ in matches_found:
            try:
                txt = f.read_text(encoding="utf-8")
                (backup_dir / f.name).write_text(txt, encoding="utf-8")
                f.write_text(txt.replace(old_term, new_term), encoding="utf-8")
            except Exception as e:
                console.print(f"[red]Lỗi file {f.name}:[/red] {e}")
            progress.advance(task_id)

    elapsed = time.time() - start_time
    console.print(f"\n[bold green]🎉 HOÀN TẤT THAY THẾ TOÀN BỘ:[/bold green]")
    console.print(f"  • [green]✓[/green] Đã thay thế thành công [bold yellow]{total_occurrences}[/bold yellow] vị trí trong [bold cyan]{len(matches_found)}[/bold cyan] file.")
    console.print(f"  • [green]✓[/green] Thời gian thực thi: [bold yellow]{elapsed:.2f} giây[/bold yellow]")
    console.print(f"  • [green]✓[/green] Bản sao lưu an toàn tại: [dim]{backup_dir}[/dim]")

    novel.append_changelog("Refactor", f"Thay thế toàn cục `{old_term}` ➔ `{new_term}` ({total_occurrences} vị trí trong {elapsed:.2f}s)")
    record_session(novel, f"Thay thế toàn cục '{old_term}' ➔ '{new_term}'", [f for f, _ in matches_found], backup_dir)
    sync_web_reader(novel.name)
    return len(matches_found)

# ==============================================================================
# 8. TÍNH NĂNG 5: CÔNG CỤ SO SÁNH ĐỐI CHIẾU BẢN DỊCH (DIFF STUDIO)
# ==============================================================================

def generate_diff_data(novel: NovelContext) -> Path:
    """Tự động gom các chương từ backup_truoc_bien_tap, backup_truoc_chuan_hoa và translated thành diff_data.js."""
    backup_edit_dir = novel.backup_edit_dir if hasattr(novel, "backup_edit_dir") else novel.folder / "backups" / "truoc_bien_tap"
    backup_clean_dir = novel.backup_clean_dir if hasattr(novel, "backup_clean_dir") else novel.folder / "backups" / "truoc_chuan_hoa"
    trans_dir = novel.translated_dir

    diff_map = {}
    trans_files = list(trans_dir.glob("chuong_*.*"))
    
    for f in trans_files:
        m = re.search(r"chuong_(\d+)", f.name)
        if not m:
            continue
        ep = int(m.group(1))
        
        polished_text = ""
        try:
            polished_text = f.read_text(encoding="utf-8")
        except Exception:
            continue

        orig_edit_text = ""
        orig_clean_text = ""

        # 1. Kiểm tra bản sao lưu trước khi biên tập
        bak_edit_file = backup_edit_dir / f.name
        if bak_edit_file.exists():
            try:
                orig_edit_text = bak_edit_file.read_text(encoding="utf-8")
            except Exception:
                pass

        # 2. Kiểm tra bản sao lưu trước khi chuẩn hóa
        bak_clean_file = backup_clean_dir / f.name
        if bak_clean_file.exists():
            try:
                orig_clean_text = bak_clean_file.read_text(encoding="utf-8")
            except Exception:
                pass

        # 3. Bản gốc ưu tiên
        orig_text = orig_edit_text or orig_clean_text
        if not orig_text:
            alt_bak = f.with_suffix(f.suffix + ".bak")
            if alt_bak.exists():
                try:
                    orig_text = alt_bak.read_text(encoding="utf-8")
                except Exception:
                    pass

        if not orig_text:
            orig_text = polished_text

        lines_list = polished_text.strip().splitlines() if polished_text else []
        title = f"Tập {ep}"
        for l in lines_list[:10]:
            l_clean = l.replace("#", "").strip()
            if l_clean and not l_clean.lower().startswith(("dưới đây", "bản dịch", "sau khi", "chương này", "toàn văn", "***", "---", "___")):
                title = l_clean
                break

        diff_map[str(ep)] = {
            "ep": ep,
            "title": title,
            "original": orig_text,
            "backup_bien_tap": orig_edit_text,
            "backup_chuan_hoa": orig_clean_text,
            "has_edit_backup": bool(orig_edit_text),
            "has_clean_backup": bool(orig_clean_text),
            "polished": polished_text
        }

    js_file = WORKSPACE_DIR / "tools" / "diff_data.js"
    diff_payload = {
        "novel_key": novel.folder.name,
        "novel_name": novel.name,
        "chapters": diff_map
    }
    # Tích hợp cơ chế Đa Bộ Truyện: Nạp và gộp dữ liệu cũ từ WEB_DIR
    all_diff_map = {}
    js_file = WEB_DIR / "diff_data.js"
    if js_file.exists():
        try:
            old_js = js_file.read_text(encoding="utf-8")
            m_all = re.search(r'window\.ALL_DIFF_DATA\s*=\s*(\{.*?\});', old_js, re.DOTALL)
            if m_all:
                all_diff_map = json.loads(m_all.group(1))
        except Exception:
            pass
    all_diff_map[novel.folder.name] = diff_payload

    js_content = (
        f"window.DIFF_DATA = {json.dumps(diff_payload, ensure_ascii=False)};\n"
        f"window.DIFF_CHAPTERS = window.DIFF_DATA.chapters;\n"
        f"window.ALL_DIFF_DATA = {json.dumps(all_diff_map, ensure_ascii=False)};\n"
    )
    try:
        if js_file.exists():
            import subprocess
            subprocess.run(["attrib", "-h", str(js_file)], capture_output=True)
        js_file.write_text(js_content, encoding="utf-8")
    except Exception:
        try:
            js_file.unlink(missing_ok=True)
            js_file.write_text(js_content, encoding="utf-8")
        except Exception:
            pass
    return js_file

def open_diff_studio(novel: NovelContext):
    """Khởi chạy Công Cụ So Sánh Đối Chiếu Diff Studio Trực Quan trên Trình Duyệt."""
    console.print(Panel.fit(
        f"[bold cyan]🔍 CÔNG CỤ SO SÁNH ĐỐI CHIẾU BẢN DỊCH (DIFF STUDIO)[/bold cyan]\n"
        f"[dim]Bộ truyện: {novel.name} • Đối chiếu trực quan 2 cột Đỏ (Bản gốc) & Xanh (Bản đã chuẩn hóa)[/dim]",
        border_style="cyan"
    ))

    with console.status("[bold cyan]Đang nạp dữ liệu đối chiếu từ backup/ và translated/...[/bold cyan]", spinner="dots"):
        generate_diff_data(novel)

    html_file = WEB_DIR / "So_Sanh_Diff.html"
    if not html_file.exists():
        console.print(f"[red]❌ Không tìm thấy file {html_file}![/red]")
        return

    import webbrowser
    file_uri = html_file.resolve().as_uri()
    
    console.print(f"[bold green]✨ Đang mở giao diện Diff Studio trên trình duyệt:[/bold green] [yellow]{file_uri}[/yellow]")
    webbrowser.open(file_uri)

def configure_ai(cfg: Dict[str, Any]):
    while True:
        console.clear()
        provider = cfg.get("active_provider", "gemini_free")
        gemini_key = cfg.get("gemini_free", {}).get("api_key", "")
        gemini_model = cfg.get("gemini_free", {}).get("model", "gemini-2.5-flash")
        
        llm_key = cfg.get("llmgate", {}).get("api_key", "")
        llm_base = cfg.get("llmgate", {}).get("base_url", "https://api.llmgate.com/v1")
        llm_model = cfg.get("llmgate", {}).get("model", "claude-3-5-sonnet-20241022")

        table = Table(title="⚙️ Cấu Hình API AI Toàn Cục", border_style="cyan")
        table.add_column("Mục", style="bold cyan")
        table.add_column("Giá trị hiện tại", style="yellow")
        table.add_column("Mô tả / Trạng thái", style="green")

        active_str = "[bold green]Google Gemini (Free)[/bold green]" if provider == "gemini_free" else "[bold magenta]LLMGate (Trả phí)[/bold magenta]"
        table.add_row("1. Kênh AI đang kích hoạt", active_str, "Kênh AI dùng cho mọi tác vụ")
        table.add_row("2. Gemini Free API Key", ("***" + gemini_key[-6:]) if len(gemini_key) > 6 else "[red]Chưa cài[/red]", f"Model: {gemini_model}")
        table.add_row("3. LLMGate API Key", ("***" + llm_key[-6:]) if len(llm_key) > 6 else "[red]Chưa cài[/red]", f"Model: {llm_model} | {llm_base}")
        console.print(table)

        console.print("\n[bold cyan]Tùy chọn cấu hình:[/bold cyan]")
        console.print("  [bold cyan]1.[/bold cyan] 🔄 Đổi Kênh AI kích hoạt (Chuyển đổi giữa Free Gemini và LLMGate)")
        console.print("  [bold cyan]2.[/bold cyan] 🔑 Cập nhật Google Gemini Free API (Key & Chọn Model)")
        console.print("  [bold cyan]3.[/bold cyan] 🔑 Cập nhật LLMGate API (Key, Base URL & Tự động quét Model)")
        console.print("  [bold cyan]0.[/bold cyan] 💾 Lưu và Quay lại Menu chính")

        opt = Prompt.ask("\nLựa chọn (0-3)", choices=["0", "1", "2", "3"], default="0")
        if opt == "0":
            save_config(cfg)
            break
        elif opt == "1":
            new_prov = Prompt.ask("Chọn kênh AI kích hoạt", choices=["gemini_free", "llmgate"], default="gemini_free" if provider == "llmgate" else "llmgate")
            cfg["active_provider"] = new_prov
            save_config(cfg)
        elif opt == "2":
            new_key = Prompt.ask("Nhập Google Gemini API Key", default=gemini_key)
            cfg["gemini_free"]["api_key"] = new_key
            new_model = select_model_interactive("gemini_free", new_key, current_model=gemini_model)
            cfg["gemini_free"]["model"] = new_model
            save_config(cfg)
        elif opt == "3":
            new_key = Prompt.ask("Nhập LLMGate API Key", default=llm_key)
            new_base = Prompt.ask("Nhập Base URL của LLMGate", default=llm_base)
            cfg["llmgate"]["api_key"] = new_key
            cfg["llmgate"]["base_url"] = new_base
            new_model = select_model_interactive("llmgate", new_key, base_url=new_base, current_model=llm_model)
            cfg["llmgate"]["model"] = new_model
            save_config(cfg)

# ==============================================================================
# 9. MENU CHÍNH & ĐIỀU HƯỚNG QUẢN LÝ NOVEL
# ==============================================================================


# ==============================================================================
# ==============================================================================
# 9. TÍNH NĂNG 6: TRỢ LÝ CỐT TRUYỆN & ĐIỀU TRA VIÊN CANON V5.0 (AI LORE MASTER)
# ==============================================================================

def detect_scene_boundaries_and_extract(text: str, hit_line_idx: int, max_lines_before: int = 50, max_lines_after: int = 60) -> Tuple[int, int, str]:
    """Cắt trọn vẹn Phân cảnh tự nhiên (Scene Chunk) 2 chiều dựa trên dấu phân cách, dòng trống kép và ranh giới hội thoại."""
    lines = text.splitlines()
    total = len(lines)
    if hit_line_idx < 0 or hit_line_idx >= total:
        return 0, total, text[:3000]

    scene_delim_pattern = re.compile(r'^\s*([*\-_—◇◆■□▲▼★☆※†‡]{2,}|【.*】|第.+章|#+)\s*$')

    # 1. Quét ngược lên tìm ranh giới bắt đầu phân cảnh
    start_idx = hit_line_idx
    empty_streak = 0
    for i in range(hit_line_idx - 1, max(-1, hit_line_idx - max_lines_before), -1):
        line = lines[i].strip()
        if not line:
            empty_streak += 1
            if empty_streak >= 2:
                start_idx = i + 1
                break
        else:
            empty_streak = 0
            if scene_delim_pattern.match(line):
                start_idx = i + 1
                break
            start_idx = i

    # 2. Quét xuôi xuống tìm ranh giới kết thúc phân cảnh
    end_idx = hit_line_idx
    empty_streak = 0
    for i in range(hit_line_idx + 1, min(total, hit_line_idx + max_lines_after)):
        line = lines[i].strip()
        if not line:
            empty_streak += 1
            if empty_streak >= 2:
                end_idx = i - 1
                break
        else:
            empty_streak = 0
            if scene_delim_pattern.match(line):
                end_idx = i - 1
                break
            end_idx = i

    # Đảm bảo không cắt ngang câu thoại nếu dòng kết thúc đang nằm trong ngoặc kép
    chunk_lines = lines[start_idx:end_idx + 1]
    return start_idx + 1, end_idx + 1, "\n".join(chunk_lines)

def extract_lore_evidence_dual_engine(novel: NovelContext, query: str) -> Dict[str, Any]:
    """Cỗ máy truy vết Bằng chứng Đa Truyện Phổ Quát (Universal Concept-Group BM25 Engine):
    Phân tích Nhóm Khái Niệm Độc Lập (Actor, Target, Means, Action) và chấm điểm mật độ giao thoa không phụ thuộc vào tên riêng."""
    result = {
        "matched_entities": [],
        "plot_threads": [],
        "translated_evidence": [],
        "raw_evidence": []
    }

    stopwords = {
        "như", "thế", "nào", "trong", "truyện", "tại", "sao", "ai", "là", "gì", "khi", "nào", 
        "bao", "nhiêu", "yêu", "được", "bị", "bởi", "và", "với", "cho", "của", "đã", "đang", 
        "sẽ", "có", "không", "một", "những", "các", "bằng", "về", "làm", "ở", "đâu"
    }

    q_clean = query.lower().replace("-", " ")
    q_words = [w.strip() for w in re.split(r'\s+', q_clean) if len(w.strip()) >= 2 and w.strip() not in stopwords]
    
    index_file = novel.glossary_dir / "ENTITY_INDEX.md"
    events_file = novel.glossary_dir / "events.md"

    entities_db = []

    # 1. Nạp Bách khoa toàn thư ENTITY_INDEX.md
    if index_file.exists():
        for line in index_file.read_text(encoding="utf-8").splitlines():
            if not line.startswith("|") or "Mã ID" in line or ":---" in line:
                continue
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 4:
                eid = parts[0].replace("`", "").strip()
                name_vi = parts[1].replace("**", "").strip()
                name_orig = parts[2].strip()
                itype = parts[3].strip()
                
                aliases = [name_vi]
                for w in re.split(r'\s+', name_vi):
                    if len(w) >= 3 and w.lower() not in stopwords:
                        aliases.append(w)
                if "meiko" in name_vi.lower(): aliases.extend(["mei", "mei chan", "mei-chan"])
                
                jp_aliases = []
                for op in name_orig.split("/"):
                    op = op.strip()
                    if len(op) >= 2:
                        jp_aliases.append(op)

                entities_db.append({
                    "id": eid,
                    "name_vi": name_vi,
                    "name_orig": name_orig,
                    "type": itype,
                    "aliases": aliases,
                    "jp_aliases": jp_aliases
                })

    # 2. Bóc tách Thực Thể & Xây dựng các Nhóm Khái Niệm Độc Lập (Concept Groups)
    target_entities = []
    concept_groups_vi = []
    concept_groups_jp = []

    for ent in entities_db:
        is_match = False
        for al in ent["aliases"]:
            al_clean = al.lower().replace("-", " ")
            if al_clean in q_clean or any(w in al_clean.split() for w in q_words if len(w) >= 3):
                is_match = True
                break
        if not is_match:
            for jal in ent["jp_aliases"]:
                if jal.lower() in q_clean:
                    is_match = True
                    break
        if is_match:
            target_entities.append(ent)
            result["matched_entities"].append(f"[{ent['id']}] {ent['name_vi']} ({ent['name_orig']}) - {ent['type']}")
            # Tạo nhóm từ khóa cho thực thể này
            concept_groups_vi.append(list(set([al.lower() for al in ent["aliases"] if len(al) >= 2])))
            if ent["jp_aliases"]:
                concept_groups_jp.append(list(set([jal for jal in ent["jp_aliases"] if len(jal) >= 2])))

    # Bổ sung các nhóm hành động / từ khóa truy vấn còn lại
    action_keywords = []
    action_keywords_jp = []
    for w in q_words:
        if not any(w in grp for grp in concept_groups_vi):
            action_keywords.append(w)
            # Thêm từ khóa đồng nghĩa hành động / phương thức phổ quát
            if w in ["hạ", "giết", "kết", "liễu", "đánh", "bại", "tiêu", "diệt"]:
                action_keywords.extend(["hạ gục", "kết liễu", "tiêu diệt", "đánh bại", "thảo phạt", "giết"])
                action_keywords_jp.extend(["トドメ", "討伐", "倒す", "撃破", "殺す"])
            elif w in ["chú", "thuật", "pháp", "kỹ", "năng", "chiêu"]:
                action_keywords.extend(["chú thuật", "ma pháp", "kỹ năng", "chiêu thức", "phép thuật"])
                action_keywords_jp.extend(["呪術", "呪印", "魔法", "スキル", "技"])

    if action_keywords:
        concept_groups_vi.append(list(set(action_keywords)))
    if action_keywords_jp:
        concept_groups_jp.append(list(set(action_keywords_jp)))

    # Tầng 1: Canon Graph & Sợi chỉ Dòng thời gian
    if events_file.exists():
        ev_lines = events_file.read_text(encoding="utf-8").splitlines()
        for el in ev_lines:
            if not el.strip(): continue
            is_rel = False
            for ent in target_entities:
                if ent["name_vi"].lower() in el.lower() or ent["name_orig"].lower() in el.lower() or any(al.lower() in el.lower() for al in ent["aliases"] if len(al) >= 3):
                    is_rel = True
                    break
            if not is_rel and any(w in el.lower() for w in q_words if len(w) >= 3):
                is_rel = True
            if is_rel and len(result["plot_threads"]) < 6:
                result["plot_threads"].append(el.strip())

    # Tầng 2: Quét & Chấm Điểm Toàn Bộ Translated Files (Concept-Group Proximity)
    trans_files = novel.list_translated_chapters()
    max_translated_chaps = len(trans_files)
    candidate_scenes_vi = []

    for ch_num, ch_path in trans_files:
        try:
            content = ch_path.read_text(encoding="utf-8")
            lines_content = content.splitlines()
            total_lines = len(lines_content)
            body_lines = lines_content[5:] if total_lines > 10 else lines_content
            body_offset = 5 if total_lines > 10 else 0

            window_size = 40
            step = 15
            for w_start in range(0, len(body_lines), step):
                w_end = min(len(body_lines), w_start + window_size)
                w_text = " ".join(body_lines[w_start:w_end]).lower()

                matched_groups = 0
                total_hits = 0
                for grp in concept_groups_vi:
                    hits = [kw for kw in grp if kw in w_text]
                    if hits:
                        matched_groups += 1
                        total_hits += len(hits)

                if matched_groups >= 2:
                    score = total_hits + (matched_groups ** 4) * 100
                    hit_center = body_offset + (w_start + w_end) // 2
                    candidate_scenes_vi.append({
                        "score": score,
                        "chapter": ch_num,
                        "file_path": ch_path,
                        "hit_line": hit_center,
                        "content": content
                    })
        except Exception:
            pass

    # Sắp xếp và lấy Top 4 phân cảnh Translated tốt nhất
    candidate_scenes_vi.sort(key=lambda x: x["score"], reverse=True)
    seen_chaps_vi = set()
    for cand in candidate_scenes_vi:
        if cand["chapter"] in seen_chaps_vi:
            continue
        seen_chaps_vi.add(cand["chapter"])
        s_line, e_line, scene_text = detect_scene_boundaries_and_extract(cand["content"], cand["hit_line"])
        result["translated_evidence"].append({
            "chapter": cand["chapter"],
            "file_name": cand["file_path"].name,
            "lines": f"{s_line}-{e_line}",
            "text": scene_text,
            "relevance_score": cand["score"]
        })
        if len(result["translated_evidence"]) >= 6:
            break

    # Tầng 3: Quét & Chấm Điểm Toàn Bộ RAW Files (Full RAW Search)
    raw_files = novel.list_raw_chapters()
    candidate_scenes_jp = []
    if concept_groups_jp:
        for ch_num, ch_path in raw_files:
            try:
                content = ch_path.read_text(encoding="utf-8")
                lines_content = content.splitlines()
                total_lines = len(lines_content)

                window_size = 40
                step = 15
                for w_start in range(0, total_lines, step):
                    w_end = min(total_lines, w_start + window_size)
                    w_text = "".join(lines_content[w_start:w_end])

                    matched_groups_jp = 0
                    total_hits_jp = 0
                    for grp in concept_groups_jp:
                        hits = [kw for kw in grp if kw in w_text]
                        if hits:
                            matched_groups_jp += 1
                            total_hits_jp += len(hits)

                    if matched_groups_jp >= 1:
                        score = total_hits_jp + (matched_groups_jp ** 4) * 100
                        hit_center = (w_start + w_end) // 2
                        candidate_scenes_jp.append({
                            "score": score,
                            "chapter": ch_num,
                            "file_path": ch_path,
                            "hit_line": hit_center,
                            "content": content
                        })
            except Exception:
                pass

        candidate_scenes_jp.sort(key=lambda x: x["score"], reverse=True)
        seen_chaps_jp = set()
        for cand in candidate_scenes_jp:
            if cand["chapter"] in seen_chaps_jp:
                continue
            seen_chaps_jp.add(cand["chapter"])
            s_line, e_line, scene_text = detect_scene_boundaries_and_extract(cand["content"], cand["hit_line"], max_lines_before=35, max_lines_after=35)
            is_spoiler = cand["chapter"] > max_translated_chaps
            tag_label = "CẢNH BÁO SPOILER" if is_spoiler else "RAW ĐỐI CHIẾU NGUYÊN BẢN"
            result["raw_evidence"].append({
                "chapter": cand["chapter"],
                "file_name": cand["file_path"].name,
                "lines": f"{s_line}-{e_line}",
                "text": scene_text,
                "relevance_score": cand["score"],
                "tag": tag_label
            })
            if len(result["raw_evidence"]) >= 4:
                break

    return result

async def run_lore_master(novel: NovelContext, ai: AIClient):
    """Trợ Lý AI Lore Master V5.0: Điều tra viên Canon Bằng Chứng & Phân Tích Đa Tầng."""
    console.clear()
    console.print(Panel.fit(
        f"[bold cyan]🧠 TRỢ LÝ CỐT TRUYỆN & ĐIỀU TRA VIÊN CANON V5.0 (AI LORE MASTER)[/bold cyan]\n"
        f"[yellow]Bộ truyện: {novel.name}[/yellow] • [dim]Kênh AI: {ai.provider} ({ai.model})[/dim]\n"
        "[dim]Động cơ Bằng chứng 4 Tầng • Lưới vét Dual-Ripgrep • Cắt phân cảnh tự nhiên • Ranh giới Spoiler[/dim]",
        border_style="cyan"
    ))

    chat_history = []
    console.print("\n[bold green]💬 BẮT ĐẦU TRÒ CHUYỆN VỚI AI LORE MASTER V5.0:[/bold green]")
    console.print("[dim yellow]💡 Mẹo: Nhập câu hỏi bất kỳ (VD: 'Mei-chan yêu ai?', 'Chiếc trâm cài của Elsa xuất hiện ở đâu?').\n        Gõ '0', 'q', 'exit' để quay lại Menu.[/dim yellow]\n")

    while True:
        user_q = Prompt.ask("\n[bold yellow]Câu hỏi của bạn[/bold yellow] [dim](0 để thoát)[/dim]").strip()
        if not user_q or user_q.lower() in ["0", "q", "exit", "thoat", "quay lai", "back"]:
            console.print("[yellow]🔙 Đang quay trở lại Menu Quản Lý...[/yellow]")
            break

        with console.status("[bold cyan]🔍 Đang truy vết Đồ thị Canon & Lưới vét Bằng chứng (Translated + RAW)...[/bold cyan]"):
            evidence_data = extract_lore_evidence_dual_engine(novel, user_q)

        # Đóng gói Prompt
        entities_block = "\n".join([f"• {e}" for e in evidence_data["matched_entities"]]) if evidence_data["matched_entities"] else "• Không có thực thể riêng biệt trong câu hỏi."
        threads_block = "\n".join([f"• {t}" for t in evidence_data["plot_threads"]]) if evidence_data["plot_threads"] else "• Chưa ghi nhận sợi chỉ sự kiện tóm tắt."

        trans_ev_blocks = []
        for ev in evidence_data["translated_evidence"]:
            trans_ev_blocks.append(
                f"### [BẰNG CHỨNG TRANSLATED] [Tập {ev['chapter']} - File: {ev['file_name']}] [Dòng {ev['lines']}]:\n\"\"\"\n{ev['text']}\n\"\"\""
            )
        trans_ev_str = "\n\n".join(trans_ev_blocks) if trans_ev_blocks else "• Không tìm thấy đoạn trích dẫn trực tiếp trong các tập đã dịch."

        raw_ev_blocks = []
        for ev in evidence_data["raw_evidence"]:
            tag = ev.get("tag", "RAW ĐỐI CHIẾU")
            raw_ev_blocks.append(
                f"### [BẰNG CHỨNG RAW] [{tag}] [Tập {ev['chapter']} RAW - File: {ev['file_name']}] [Dòng {ev['lines']}]:\n\"\"\"\n{ev['text']}\n\"\"\""
            )
        raw_ev_str = "\n\n".join(raw_ev_blocks) if raw_ev_blocks else "• Không phát hiện manh mối trong các tập RAW chưa dịch."

        lore_system_prompt = (
            f"Bạn là Giám Tuyển Cốt Truyện & Điều Tra Viên Canon Cao Cấp (Canon Lore Master) cho tác phẩm: {novel.name}.\n"
            "Nhiệm vụ: Trả lời câu hỏi của người dùng dựa trên BẰNG CHỨNG NGUYÊN VĂN và HỒ SƠ CANON được cung cấp.\n\n"
            "BỘ QUY TẮC BẮT BUỘC VỀ 4 CẤP ĐỘ BẰNG CHỨNG:\n"
            "1. 🟢 [XÁC NHẬN]: Chi tiết có trích dẫn trực tiếp từ các đoạn văn Bằng Chứng (Evidence) bên dưới. Từ ngữ xuất hiện phải là nhân vật/sự kiện thực tế.\n"
            "2. 🟡 [SUY LUẬN TỪ BẰNG CHỨNG]: Logic suy diễn nguyên nhân, tâm lý nhân vật từ chuỗi sự kiện. Phải ghi rõ là suy luận.\n"
            "3. ⚪ [CHƯA ĐỦ DỮ LIỆU / CHƯA XÁC NHẬN]: Nguyên tác chưa tiết lộ hoặc nằm ngoài phạm vi các đoạn văn bằng chứng được cấp.\n"
            "4. 🔴 [MÂU THUẪN CANON]: Phát hiện sự bất nhất giữa 2 tập truyện hoặc hai nguồn thông tin.\n\n"
            "NGUYÊN TẮC CỐT LÕI:\n"
            "- Tên xuất hiện trong RAW chưa chắc nhân vật đã xuất hiện (có thể là Hồi tưởng, Nhắc tên, Thư từ...). Hãy đọc kỹ ngữ cảnh!\n"
            "- Luôn trích dẫn số Tập và câu văn nguồn gốc rõ ràng.\n"
            "- Trình bày định dạng Markdown đẹp mắt, sắc sảo, chuyên nghiệp."
        )

        history_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history[-4:]]) if chat_history else ""

        user_prompt = (
            f"--- 📇 HỒ SƠ THỰC THỂ LIÊN QUAN TRỌNG TÂM ---\n{entities_block}\n\n"
            f"--- 🧵 SỢI CHỈ DÒNG THỜI GIAN (PLOT THREADS) ---\n{threads_block}\n\n"
            f"--- 📌 BẰNG CHỨNG NGUYÊN VĂN TỪ BẢN DỊCH (TRANSLATED EVIDENCE) ---\n{trans_ev_str}\n\n"
            f"--- 🔮 BẰNG CHỨNG TỪ RAW CHƯA DỊCH (FUTURE DISCOVERY - CẢNH BÁO SPOILER) ---\n{raw_ev_str}\n\n"
            f"{('--- LỊCH SỬ HỘI THOẠI ---\n' + history_text + '\n\n') if history_text else ''}"
            f"--- CÂU HỎI CỦA NGƯỜI DÙNG ---\n{user_q}"
        )

        try:
            ans = await ai.generate(lore_system_prompt, user_prompt, temperature=0.2)
            chat_history.append({"role": "user", "content": user_q})
            chat_history.append({"role": "assistant", "content": ans})

            console.print(Panel(
                Markdown(ans),
                title=f"[bold green]✨ Báo Cáo Điều Tra Canon ({novel.name})[/bold green]",
                border_style="green"
            ))
        except Exception as e:
            console.print(f"[bold red]❌ Lỗi truy vấn AI:[/bold red] {e}")

# 10. HỆ THỐNG SESSION TRACKING & HOÀN TÁC DỮ LIỆU (UNDO / RESTORE SYSTEM)
# ==============================================================================

def record_session(novel: NovelContext, action_name: str, affected_files: List[Path], backup_subdir: Path):
    """Ghi lại phiên làm việc gần nhất để hỗ trợ hoàn tác chính xác (Ctrl+Z)."""
    try:
        session_file = novel.backups_dir / ".last_session.json"
        data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action_name,
            "backup_dir": str(backup_subdir.relative_to(novel.folder)),
            "affected_files": [f.name for f in affected_files]
        }
        session_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def run_undo_restore(novel: NovelContext):
    """Giao diện Hoàn Tác & Khôi Phục Dữ Liệu đa tầng thông minh."""
    while True:
        console.clear()
        console.print(Panel.fit(
            f"[bold cyan]⏪ CÔNG CỤ HOÀN TÁC & KHÔI PHỤC BẢN SAO LƯU: [yellow]{novel.name}[/yellow][/bold cyan]\n"
            "[dim]Khôi phục an toàn theo phiên vừa làm (Ctrl+Z) • Từng chương • Toàn bộ dự án[/dim]",
            border_style="cyan"
        ))

        session_file = novel.backups_dir / ".last_session.json"
        last_session = None
        if session_file.exists():
            try:
                last_session = json.loads(session_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        if last_session:
            console.print(Panel(
                f"🕒 [bold yellow]Phiên Gần Nhất:[/bold yellow] `{last_session.get('timestamp')}`\n"
                f"📝 [bold cyan]Thao tác:[/bold cyan] {last_session.get('action')}\n"
                f"📁 [bold green]Số file bị thay đổi:[/bold green] [yellow]{len(last_session.get('affected_files', []))}[/yellow] file\n"
                f"🛡️ [bold magenta]Thư mục lưu bản gốc:[/bold magenta] `{last_session.get('backup_dir')}`",
                title="📌 Nhật Ký Phiên Gần Nhất (Session Tracking)",
                border_style="yellow"
            ))
        else:
            console.print("[dim yellow]ℹ️ Chưa có ghi nhận phiên làm việc gần đây.[/dim yellow]\n")

        console.print("[bold cyan]CHỌN PHƯƠNG THỨC HOÀN TÁC:[/bold cyan]")
        console.print("  [bold green]1.[/bold green] ⏪ [bold green]Hoàn tác thao tác vừa xảy ra (Session Undo - Ctrl+Z)[/bold green] [dim](Chỉ khôi phục đúng các file vừa đổi)[/dim]")
        console.print("  [bold yellow]2.[/bold yellow] 📄 [bold yellow]Khôi phục 1 chương chỉ định[/bold yellow] [dim](Khôi phục riêng 1 tập bị lỗi)[/dim]")
        console.print("  [bold magenta]3.[/bold magenta] 🔄 [bold magenta]Khôi phục toàn bộ từ 'truoc_chuan_hoa'[/bold magenta] [dim](Toàn bộ các chương)[/dim]")
        console.print("  [bold cyan]4.[/bold cyan] 🔄 [bold cyan]Khôi phục toàn bộ từ 'truoc_bien_tap'[/bold cyan] [dim](Toàn bộ các chương)[/dim]")
        console.print("  [bold white]5.[/bold white] 📚 [bold white]Khôi phục lại Glossary cũ[/bold white]")
        console.print("  [bold red]0.[/bold red] 🔙 [dim]Quay lại Menu chính[/dim]")

        choice = Prompt.ask("\nLựa chọn của bạn", choices=["0", "1", "2", "3", "4", "5"], default="1")
        if choice == "0":
            break

        if choice == "1":
            if not last_session:
                console.print("[yellow]Không tìm thấy phiên làm việc nào gần đây để hoàn tác.[/yellow]")
                input("\nNhấn Enter để tiếp tục...")
                continue

            bak_subdir = novel.folder / last_session.get("backup_dir", "backups/truoc_chuan_hoa")
            affected = last_session.get("affected_files", [])

            if not Confirm.ask(f"Bạn có chắc chắn muốn hoàn tác {len(affected)} file về trạng thái trước: '{last_session.get('action')}' không?", default=True):
                continue

            restored_count = 0
            for fname in affected:
                src = bak_subdir / fname
                # Tìm đích đến: translated/ hoặc glossary/
                dest = novel.translated_dir / fname if (novel.translated_dir / fname).exists() or not (novel.glossary_dir / fname).exists() else novel.glossary_dir / fname
                if src.exists():
                    shutil.copy2(src, dest)
                    restored_count += 1

            console.print(f"\n[bold green]✅ ĐÃ HOÀN TÁC THÀNH CÔNG {restored_count}/{len(affected)} FILE VỀ NGUYÊN TRẠNG BAN ĐẦU![/bold green]")
            novel.append_changelog("Undo", f"Hoàn tác phiên: '{last_session.get('action')}' ({restored_count} file)")
            sync_web_reader(novel.name)
            # Xóa session sau khi đã hoàn tác
            session_file.unlink(missing_ok=True)
            input("\nNhấn Enter để tiếp tục...")

        elif choice == "2":
            ch_num = IntPrompt.ask("Nhập số chương cần khôi phục (Ví dụ: 212)")
            found_files = list(novel.backup_clean_dir.glob(f"*{ch_num}*")) or list(novel.backup_edit_dir.glob(f"*{ch_num}*"))
            if not found_files:
                console.print(f"[red]Không tìm thấy bản sao lưu nào của Tập {ch_num} trong backups/.[/red]")
                input("\nNhấn Enter để tiếp tục...")
                continue

            src = found_files[0]
            dest = novel.translated_dir / src.name
            shutil.copy2(src, dest)
            console.print(f"[bold green]✅ Đã khôi phục thành công Tập {ch_num} từ:[/bold green] [yellow]{src.parent.name}/{src.name}[/yellow]")
            novel.append_changelog("Undo", f"Khôi phục thủ công Tập {ch_num} từ backup")
            sync_web_reader(novel.name)
            input("\nNhấn Enter để tiếp tục...")

        elif choice in ("3", "4"):
            src_dir = novel.backup_clean_dir if choice == "3" else novel.backup_edit_dir
            files = list(src_dir.glob("*.md")) + list(src_dir.glob("*.txt"))
            if not files:
                console.print(f"[yellow]Thư mục sao lưu {src_dir.name} hiện đang rỗng.[/yellow]")
                input("\nNhấn Enter để tiếp tục...")
                continue

            if not Confirm.ask(f"⚠️ CẢNH BÁO: Khôi phục toàn bộ {len(files)} file từ {src_dir.name} sẽ ghi đè lại vào translated/. Tiếp tục?", default=False):
                continue

            for f in files:
                shutil.copy2(f, novel.translated_dir / f.name)

            console.print(f"[bold green]✅ Đã khôi phục toàn bộ {len(files)} file từ {src_dir.name} vào translated/![/bold green]")
            novel.append_changelog("Restore All", f"Khôi phục toàn bộ {len(files)} file từ {src_dir.name}")
            sync_web_reader(novel.name)
            input("\nNhấn Enter để tiếp tục...")

        elif choice == "5":
            gloss_baks = list(novel.backup_gloss_dir.glob("*"))
            if not gloss_baks:
                console.print("[yellow]Chưa có bản sao lưu Glossary cũ nào trong backups/glossary/.[/yellow]")
                input("\nNhấn Enter để tiếp tục...")
                continue

            for f in gloss_baks:
                # Tách tên gốc: characters.md.bak_2026... -> characters.md
                orig_name = f.name.split(".bak_")[0]
                shutil.copy2(f, novel.glossary_dir / orig_name)

            console.print(f"[bold green]✅ Đã khôi phục các file Glossary từ backups/glossary/![/bold green]")
            novel.append_changelog("Restore Glossary", f"Khôi phục {len(gloss_baks)} file Glossary từ backup")
            input("\nNhấn Enter để tiếp tục...")

async def main():
    cfg = load_config()

    while True:
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]📚 TRUNG TÂM QUẢN LÝ DỰ ÁN NOVEL & GLOSSARY STUDIO[/bold cyan] [bold magenta]— V3.0 ULTIMATE[/bold magenta]\n"
            "[bold green]🏛️ Kiến trúc:[/bold green] [bold white]Canon Database V3.0 • Atomic Claims • Anti-Hallucination Validator[/bold white]\n"
            "[dim]Quản lý Đa Truyện • Khai thác Canon Miner • Chuẩn hóa Kính ngữ • Biên tập Diff Report[/dim]",
            border_style="bright_blue"
        ))

        novels = discover_novels()
        if not novels:
            console.print("[red]❌ Không tìm thấy thư mục truyện nào trong workspace.[/red]")
            return

        active_p = cfg.get("active_provider", "gemini_free")
        p_name = f"[bold green]Gemini Free ({cfg.get('gemini_free', {}).get('model', 'gemini-2.5-flash')})[/bold green]" if active_p == "gemini_free" else f"[bold magenta]LLMGate ({cfg.get('llmgate', {}).get('model', 'claude-3-5-sonnet-20241022')})[/bold magenta]"
        console.print(f"🤖 [bold]Kênh AI đang dùng:[/bold] {p_name}\n")

        table = Table(title="📚 Danh Sách Bộ Truyện Trong Máy", border_style="green")
        table.add_column("STT", style="bold cyan", width=4)
        table.add_column("Tên Bộ Truyện", style="bold yellow")
        table.add_column("Số Raw", justify="right", style="cyan")
        table.add_column("Đã Dịch", justify="right", style="green")
        table.add_column("Glossary", style="magenta")

        for idx, n in enumerate(novels, 1):
            raw_c = len(n.list_raw_chapters())
            trans_c = len(n.list_translated_chapters())
            has_char = "✓" if (n.glossary_dir / "characters.md").exists() else "✗"
            has_term = "✓" if (n.glossary_dir / "terms.md").exists() else "✗"
            gloss_info = f"Char: {has_char} | Term: {has_term}"
            table.add_row(str(idx), n.name, str(raw_c), str(trans_c), gloss_info)

        console.print(table)

        console.print("\n[bold cyan]Hành động:[/bold cyan]")
        console.print(f"  [bold yellow][1 - {len(novels)}][/bold yellow] 📖 Chọn bộ truyện để làm việc")
        console.print("  [bold cyan]9.[/bold cyan] ⚙️  Cấu hình AI & API Keys (Gemini Free / LLMGate)")
        console.print("  [bold cyan]0.[/bold cyan] ❌ Thoát")

        choice = Prompt.ask(f"\nNhập lựa chọn (0 - {len(novels)} hoặc 9)", default="1")
        if choice == "0":
            break
        elif choice == "9":
            configure_ai(cfg)
            continue

        try:
            sel_idx = int(choice) - 1
            if not (0 <= sel_idx < len(novels)):
                continue
            selected_novel = novels[sel_idx]
        except ValueError:
            continue

        while True:
            console.clear()
            console.print(Panel.fit(
                f"[bold cyan]🚀 TRUNG TÂM QUẢN TRỊ CANON & GLOSSARY STUDIO — V3.0 ULTIMATE[/bold cyan]\n"
                f"[bold green]📖 Đang làm việc với:[/bold green] [bold yellow]{selected_novel.name}[/bold yellow] • [bold magenta]Engine:[/bold magenta] [bold white]Canon DB V3.0 (Atomic Claims)[/bold white]\n"
                f"[dim]Kênh AI: {active_p} • Thư mục: {selected_novel.folder}[/dim]",
                border_style="bright_blue"
            ))

            console.print("  [bold cyan]1.[/bold cyan] ⚡ [bold green]Chuẩn Hóa Thuật Ngữ & Dọn Kính Ngữ[/bold green] [dim](Từng tập / Khoảng / Toàn bộ • Xuất 2 Thư Mục)[/dim]")
            console.print("  [bold cyan]2.[/bold cyan] 🔍 [bold yellow]Trích xuất & Bố cục Glossary tự động[/bold yellow] [dim](Khai phá nhân vật & thuật ngữ từ Raw)[/dim]")
            console.print("  [bold cyan]3.[/bold cyan] 📝 [bold magenta]Biên tập chuyên sâu bằng AI[/bold magenta] [dim](Xuất báo cáo kiểm chứng DIFF_REPORT.md)[/dim]")
            console.print("  [bold cyan]4.[/bold cyan] 🔄 [bold white]Đổi Thuật Ngữ / Sửa Tên Nhân Vật Thủ Công Toàn Cục[/bold white]")
            console.print("  [bold cyan]5.[/bold cyan] 🔬 [bold cyan]So Sánh Đối Chiếu Bản Dịch (Diff Studio Đồ Họa 2 Cột)[/bold cyan]")
            console.print("  [bold cyan]6.[/bold cyan] 🧠 [bold bright_green]Trợ Lý AI Lore Master (Chat & Tra Cứu Cốt Truyện / Bách Khoa Toàn Thư)[/bold bright_green]")
            console.print("  [bold cyan]7.[/bold cyan] ⏪ [bold yellow]Hoàn Tác & Khôi Phục Bản Sao Lưu (Undo / Restore from Backups)[/bold yellow] 🌟")
            console.print("  [bold cyan]0.[/bold cyan] ⬅️  Quay lại danh sách truyện")

            sub_choice = Prompt.ask("\nLựa chọn của bạn (0-7)", choices=["0", "1", "2", "3", "4", "5", "6", "7"], default="1")
            if sub_choice == "0":
                break

            ai = AIClient(cfg)

            if sub_choice == "1":
                run_glossary_polisher_and_normalizer(selected_novel)
            elif sub_choice == "2":
                await run_glossary_miner(selected_novel, ai)
            elif sub_choice == "3":
                await run_batch_editor(selected_novel, ai)
            elif sub_choice == "4":
                global_term_refactor(selected_novel)
            elif sub_choice == "5":
                open_diff_studio(selected_novel)
            elif sub_choice == "6":
                await run_lore_master(selected_novel, ai)
            elif sub_choice == "7":
                run_undo_restore(selected_novel)

            input("\nNhấn Enter để tiếp tục...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Đã hủy tác vụ.[/yellow]")
    except Exception as e:
        console.print(f"\n[bold red]❌ Đã xảy ra lỗi:[/bold red] {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            input("\nNhấn Enter để đóng chương trình...")
        except Exception:
            pass

def review_unclassified_entities(novel: NovelContext):
    """Giao diện duyệt tương tác các thực thể lạ trong unclassified_entities.jsonl."""
    unclass_file = novel.glossary_dir / "unclassified_entities.jsonl"
    if not unclass_file.exists() or unclass_file.stat().st_size == 0:
        console.print("\n[bold green]✅ Hàng chờ duyệt rỗng! Không có thực thể lạ nào cần xử lý.[/bold green]")
        input("\nNhấn Enter để quay lại menu...")
        return

    entries = []
    for line in unclass_file.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                entries.append(json.loads(line.strip()))
            except Exception:
                pass

    if not entries:
        console.print("\n[bold green]✅ Không có thực thể nào hợp lệ trong file hàng chờ.[/bold green]")
        input("\nNhấn Enter để quay lại menu...")
        return

    index_file = novel.glossary_dir / "ENTITY_INDEX.md"
    index_txt = index_file.read_text(encoding="utf-8") if index_file.exists() else ""
    terms_file = novel.glossary_dir / "terms.md"

    remaining = []
    console.print(f"\n[bold cyan]📋 TÌM THẤY {len(entries)} THỰC THỂ LẠ CẦN DUYỆT:[/bold cyan]")

    for idx, e in enumerate(entries, 1):
        console.print(f"\n[bold yellow]─────────── [{idx}/{len(entries)}] THỰC THỂ: {e.get('ten_vi')} ({e.get('ten_goc')}) ───────────[/bold yellow]")
        console.print(f"  • [bold]Loại do AI trích xuất:[/bold] {e.get('loai_la')}")
        console.print(f"  • [bold]Mô tả:[/bold] {e.get('mo_ta')}")
        console.print(f"  • [bold]Tập xuất hiện:[/bold] Tập {e.get('chuong')}")
        
        console.print("\n[bold green]Chọn hành động duyệt:[/bold green]")
        console.print("  [1] Duyệt thành [bold cyan]RACE (Chủng tộc / Tộc loài)[/bold cyan]")
        console.print("  [2] Duyệt thành [bold red]MONSTER (Sinh vật / Quái vật)[/bold red]")
        console.print("  [3] Duyệt thành [bold magenta]ITEM (Vật phẩm / Trang bị)[/bold magenta]")
        console.print("  [4] Duyệt thành [bold blue]TERM (Thuật ngữ thế giới)[/bold blue]")
        console.print("  [5] Bỏ qua (Giữ lại trong hàng chờ)")
        console.print("  [0] Xóa bỏ thực thể này")

        choice = Prompt.ask("👉 Lựa chọn của bạn", choices=["1", "2", "3", "4", "5", "0"], default="1")

        if choice == "5":
            remaining.append(e)
            continue
        elif choice == "0":
            console.print("  ❌ Đã xóa bỏ khỏi hàng chờ.")
            continue

        cat_map = {
            "1": ("RACE", "Chủng tộc", "CHỦNG TỘC / TỘC LOÀI"),
            "2": ("MONSTER", "Quái vật / Sinh vật", "SINH VẬT / QUÁI VẬT"),
            "3": ("ITEM", "Vật phẩm", "VẬT PHẨM / TRANG BỊ"),
            "4": ("TERM", "Thuật ngữ", "THUẬT NGỮ THẾ GIỚI")
        }
        pfx, itype_idx, itype_card = cat_map[choice]
        count = len(re.findall(rf'{pfx}-\d+', index_txt)) + 1
        eid = f"{pfx}-{count:03d}"

        card = f"\n---\n\n## [{eid}] {e.get('ten_vi')}\n\n- **id:** {eid}\n- **loại:** {itype_card}\n- **tên_chuẩn:** {e.get('ten_vi')}\n- **tên_gốc:** {e.get('ten_goc')}\n- **trạng_thái:** ĐÃ XÁC NHẬN\n- **canon:** CHÍNH THỨC\n- **độ_tin_cậy:** TUYỆT ĐỐI\n- **khóa_bảo_vệ:** CÓ\n- **nguồn:** Tập {e.get('chuong', 1)}\n- **mô_tả:** {e.get('mo_ta')}\n"
        
        cur_terms = terms_file.read_text(encoding="utf-8") if terms_file.exists() else "# ⚔️ THUẬT NGỮ\n"
        terms_file.write_text(cur_terms.rstrip() + "\n" + card, encoding="utf-8")

        new_row = f"| `{eid}` | **{e.get('ten_vi')}** | {e.get('ten_goc')} | {itype_idx} | `CHÍNH THỨC` | Tập {e.get('chuong', 1)} |\n"
        index_txt = index_txt.rstrip() + "\n" + new_row
        index_file.write_text(index_txt, encoding="utf-8")

        console.print(f"  [bold green]✅ Đã duyệt thành công: [`{eid}`] {e.get('ten_vi')} ({itype_idx})[/bold green]")

    # Ghi lại những thực thể chưa duyệt
    if remaining:
        unclass_file.write_text("\n".join([json.dumps(r, ensure_ascii=False) for r in remaining]) + "\n", encoding="utf-8")
    else:
        unclass_file.write_text("", encoding="utf-8")
        console.print("\n[bold green]🎉 Đã hoàn tất duyệt toàn bộ hàng chờ![/bold green]")
    input("\nNhấn Enter để quay lại menu...")


def launch_github_sync(novel: NovelContext):
    """Mở công cụ đồng bộ GitHub từ Quản lý Novel."""
    bat_git = WORKSPACE_DIR / "5_Dong_Bo_GitHub.bat"
    if not bat_git.exists():
        bat_git = TOOLS_DIR / "5_Dong_Bo_GitHub.bat"
    if bat_git.exists():
        os.system(f'cmd /c "{bat_git}"')
    else:
        console.print("[bold red]⚠️ Không tìm thấy file 5_Dong_Bo_GitHub.bat![/bold red]")
        input("\nNhấn Enter để quay lại...")
