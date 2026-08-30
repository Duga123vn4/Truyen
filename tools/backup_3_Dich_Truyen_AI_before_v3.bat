@echo off & chcp 65001 >nul & set "PYTHONIOENCODING=utf-8" & set "PYTHONUTF8=1" & for %%P in (python.exe "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%LOCALAPPDATA%\Programs\Python\Python311\python.exe") do @(%%P -x -X utf8 "%~f0" %* && exit /b 0)
"""
Universal Multi-Novel Gemini AI Translator (Dịch Truyện AI Thông Minh Đa Năng)
Hỗ trợ:
  - Đa dự án Light Novel (Universal Multi-Project)
  - Tự động phát hiện & phân loại vào 5 Nhóm Danh Mục Glossary Chuẩn (Cách A - Realtime)
  - Tự động Sinh Ảnh Minh Họa Từng Chương bằng FLUX Anime (Không giới hạn) & Quản lý Gallery
  - Trợ lý Tra cứu Cốt truyện & Nhân vật AI (Lore & Story Chatbot)
  - Đổi Thuật ngữ / Sửa tên Nhân vật hàng loạt toàn bộ truyện (Global Term Refactor)
  - Bộ đếm lượt gọi API trực quan & Giao tiếp tinh chỉnh bản dịch tương tác
"""

import sys
import os
import re
import json
import time
import asyncio
import urllib.parse
import shutil
import base64
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any


import io

def ensure_utf8_console():
    """Bảo đảm terminal luôn giữ chuẩn UTF-8 và ANSI màu sắc, không bao giờ bị lệnh ngoài làm hỏng."""
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
    import httpx
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn, TimeElapsedColumn
    from rich.panel import Panel
    from rich.prompt import Prompt, IntPrompt, Confirm
    from rich.markdown import Markdown
    from bs4 import BeautifulSoup
except ImportError:
    print("[!] Dang thieu thu vien, vui long chay: pip install httpx rich")
    sys.exit(1)

# Ép luồng xuất ra chuẩn UTF-8 toàn diện để không bao giờ bị lỗi dấu tiếng Việt (?) trên Windows
utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
console = Console(file=utf8_stdout, force_terminal=True, legacy_windows=False)

ROOT_DIR = Path(__file__).resolve().parent.parent
TOOLS_DIR = Path(__file__).resolve().parent
CONFIG_FILE = TOOLS_DIR / "config.json"

def sync_web_reader(project_name: str = "", silent: bool = False):
    """Đồng bộ Web Đọc Truyện ngầm cho dự án cụ thể mà không làm ảnh hưởng hay phá vỡ encoding của Console."""
    build_script = TOOLS_DIR / "build_chapters_js.ps1"
    if not build_script.exists():
        return
    import subprocess
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(build_script)]
    if project_name:
        cmd.extend(["-ProjectName", project_name])

    try:
        creation_flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            creationflags=creation_flags
        )
        if not silent and res.stdout:
            for line in res.stdout.splitlines():
                if "Da dong bo" in line:
                    console.print(f"[bold green]✓ {line.strip()}[/bold green]")
    except Exception as e:
        if not silent:
            console.print(f"[dim red]Lỗi khi đồng bộ web: {e}[/dim red]")
    finally:
        ensure_utf8_console()

def ask_yes_no(prompt_text: str, default_yes: bool = True) -> bool:
    """Hỏi người dùng với lựa chọn số: [1] Có / [2] Không thay vì [y/n]. Chấp nhận cả 1, 2, y, n."""
    def_str = "1" if default_yes else "2"
    console.print(f"\n{prompt_text}")
    console.print(f"  [1] [bold green]Có (Đồng ý)[/bold green]" + (" [dim](Mặc định)[/dim]" if default_yes else ""))
    console.print(f"  [2] [bold red]Không (Bỏ qua)[/bold red]" + (" [dim](Mặc định)[/dim]" if not default_yes else ""))
    ans = Prompt.ask("[bold yellow]Lựa chọn của bạn[/bold yellow]", choices=["1", "2", "y", "n", "c", "k"], default=def_str).strip().lower()
    return ans in ["1", "y", "c", "yes", "co", "có"]

AVAILABLE_GEMINI_MODELS = [
    ("gemini-2.5-flash", "Gemini 2.5 Flash (Google Free: Tốc độ siêu tốc, 1.500 lượt/ngày - Khuyên dùng #1)"),
    ("gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite (Google Free: Phản hồi tức thì, mượt mà)"),
    ("gemini-2.0-flash", "Gemini 2.0 Flash (Google Free: Ổn định cao)"),
    ("gemini-flash-latest", "Gemini Flash Latest (Google Free: Bản cập nhật tự động)"),
]

AVAILABLE_RELAY_MODELS = [
    ("gemini-3.7-flash", "Gemini 3.7 Flash (LLMGate: Siêu tốc 8.5s, chất lượng dịch đỉnh cao 9.8/10 - Khuyên dùng #1)"),
    ("gemini-3-flash", "Gemini 3 Flash (LLMGate: Ngân sách tiết kiệm, ~12đ/chương, văn phong 9.4/10 - Khuyên dùng #2)"),
    ("gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite (LLMGate: Siêu tốc 3.4s, ~6đ/chương, rẻ nhất)"),
    ("deepseek-v4-flash-0731", "DeepSeek v4 Flash 0731 (LLMGate: Văn phong Hán-Nhật 9.5/10)"),
    ("deepseek-v4-pro-0813", "DeepSeek v4 Pro 0813 (LLMGate: Văn phong Dark Fantasy sâu sắc)"),
    ("gpt-5.6-luna", "GPT 5.6 Luna (LLMGate: OpenAI siêu tiết kiệm)"),
    ("gpt-5.4-mini", "GPT 5.4 Mini (LLMGate: OpenAI rõ ràng, mạch lạc)"),
    ("claude-sonnet-5", "Claude Sonnet 5 (LLMGate: Vua văn học xuất bản đỉnh cao 10/10)"),
]

AVAILABLE_IMAGE_MODELS = [
    ("gemini-3.1-flash-image", "Gemini 3.1 Flash Image (Google Imagen 3: 5.4s, ~0.5đ/ảnh, Đẹp nhất - Khuyên dùng #1)"),
    ("nano-banana-2", "Nano Banana 2 (Alias Imagen 3: 5.4s, ~0.5đ/ảnh - Khuyên dùng #2)"),
    ("gpt-image-2", "GPT Image 2 (OpenAI DALL-E 2: ~0.25đ/ảnh)"),
    ("dall-e-3", "DALL-E 3 (OpenAI HD: ~40đ/ảnh)"),
]

AVAILABLE_MODELS = AVAILABLE_GEMINI_MODELS

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "engine": "gemini",
        "gemini_api_key": "",
        "selected_model": "gemini-3.5-flash",
        "relay_base_url": "",
        "relay_api_key": "",
        "relay_model": "gemini-3-flash",
        "image_model": "gemini-3.1-flash-image",
        "daily_requests": {}
    }

def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

DAILY_LIMIT = 1500

def get_today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def get_current_request_count() -> int:
    cfg = load_config()
    today = get_today_str()
    if "daily_requests" in cfg and today in cfg["daily_requests"]:
        return cfg["daily_requests"][today]
    if cfg.get("last_usage_date") == today:
        return cfg.get("requests_today", 0)
    return 0

def get_remaining_requests() -> Tuple[int, int]:
    """Trả về (số lượt còn lại hôm nay, tổng hạn mức 1500)."""
    cfg = load_config()
    engine = cfg.get("engine", "gemini")
    if engine == "relay":
        return 999999, 999999  # Không giới hạn đối với API trả phí
    used = get_current_request_count()
    remaining = max(0, DAILY_LIMIT - used)
    return remaining, DAILY_LIMIT

def increment_request_count() -> Tuple[int, int]:
    """Tăng số lượt đã dùng và trả về (còn lại, tổng hạn mức)."""
    cfg = load_config()
    today = get_today_str()
    count = get_current_request_count() + 1
    
    if "daily_requests" not in cfg:
        cfg["daily_requests"] = {}
    cfg["daily_requests"][today] = count
    cfg["requests_today"] = count
    cfg["last_usage_date"] = today
    save_config(cfg)
    
    engine = cfg.get("engine", "gemini")
    if engine == "relay":
        return 999999, 999999
    remaining = max(0, DAILY_LIMIT - count)
    return remaining, DAILY_LIMIT

def ensure_api_key(cfg: dict) -> Tuple[str, str, str]:
    """Trả về (engine, api_key, model)."""
    engine = cfg.get("engine", "gemini")
    
    if engine == "relay":
        api_key = cfg.get("relay_api_key", "").strip()
        base_url = cfg.get("relay_base_url", "").strip()
        model = cfg.get("relay_model", "gemini-3-flash").strip()
        
        if not api_key or not base_url:
            console.print(Panel(
                "[bold yellow]🔑 CHƯA CẤU HÌNH API RELAY / TRẢ PHÍ[/bold yellow]\n"
                "Vui lòng nhập Base URL và API Key của nhà cung cấp Relay.",
                border_style="yellow"
            ))
            if not base_url:
                base_url = Prompt.ask("[bold cyan]Nhập Base URL của Relay (Ví dụ: https://api.openai.com/v1 hoặc link bên bán cấp)[/bold cyan]").strip()
                cfg["relay_base_url"] = base_url
            if not api_key:
                api_key = Prompt.ask("[bold cyan]Nhập Relay API Key (sk-...)[/bold cyan]").strip()
                cfg["relay_api_key"] = api_key
            save_config(cfg)
            console.print("[bold green]✅ Đã lưu cấu hình Relay thành công![/bold green]\n")
        return "relay", api_key, model
    else:
        api_key = cfg.get("gemini_api_key", "").strip()
        model = cfg.get("selected_model", "gemini-3.5-flash").strip()
        if not api_key:
            console.print(Panel(
                "[bold yellow]🔑 CHƯA CẤU HÌNH GEMINI API KEY[/bold yellow]\n"
                "Vui lòng truy cập [link=https://aistudio.google.com/]https://aistudio.google.com/[/link] để lấy API Key miễn phí.",
                border_style="yellow"
            ))
            api_key = Prompt.ask("[bold cyan]Nhập Gemini API Key của bạn[/bold cyan]").strip()
            if api_key:
                cfg["gemini_api_key"] = api_key
                save_config(cfg)
                console.print("[bold green]✅ Đã lưu API Key thành công![/bold green]\n")
            else:
                console.print("[bold red]❌ Không có API Key, không thể tiếp tục.[/bold red]")
                sys.exit(1)
        return "gemini", api_key, model

class RawChapterInfo:
    """Quản lý thông tin chương raw: Số tập cốt truyện thực tế và số file URL."""
    def __init__(self, file_path: Path):
        self.path = file_path
        self.file_ep = self._parse_file_number(file_path.name)
        self.story_ep, self.raw_title = self._parse_story_chapter(file_path)

    def _parse_file_number(self, filename: str) -> int:
        m = re.search(r"chuong_(\d+)_raw", filename, re.IGNORECASE)
        return int(m.group(1)) if m else 0

    def _parse_story_chapter(self, file_path: Path) -> Tuple[int, str]:
        """Đọc dòng đầu để trích xuất số tập thực tế (第XXX話) và tiêu đề tiếng Nhật."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for _ in range(5):
                    line = f.readline().strip()
                    if not line:
                        continue
                    m = re.search(r"第\s*([0-9０-９]+)\s*話\s*(.*)", line)
                    if m:
                        num_str = m.group(1)
                        fullwidth_map = str.maketrans('０１２３４５６７８９', '0123456789')
                        num_str = num_str.translate(fullwidth_map)
                        ep_num = int(num_str)
                        title = m.group(2).strip()
                        return ep_num, title
                    break
        except Exception:
            pass
        return self.file_ep, ""


# ==============================================================================
# 📥 MODULE CÀO RAW SYOSETU NỘI BỘ (INTEGRATED SYOSETU SCRAPER ENGINE)
# ==============================================================================
SCRAPER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8,vi;q=0.7",
    "Cookie": "over18=yes; lineheight=0; fontsize=0; novellayout=0;",
}

def clean_filename(name: str) -> str:
    """Làm sạch tên file/thư mục hợp lệ trên Windows."""
    name = re.sub(r'[\\/*?:"<>|]', '', name)
    name = name.strip().replace(' ', '_')
    return name or "Novel_Raw"

def extract_novel_code(input_str: str) -> str:
    """Trích xuất mã truyện Syosetu từ URL hoặc mã nhập trực tiếp."""
    input_str = input_str.strip().lower()
    match = re.search(r'syosetu\.com/([a-z0-9]+)', input_str)
    if match:
        return match.group(1)
    return re.sub(r'[^a-z0-9]', '', input_str)

class SyosetuNovel:
    def __init__(self, novel_code: str):
        self.novel_code = novel_code
        self.base_url = f"https://ncode.syosetu.com/{novel_code}/"
        self.title = ""
        self.author = ""
        self.synopsis = ""
        self.episodes: List[Dict] = []
        self.root_dir = ROOT_DIR

    async def fetch_novel_info_and_toc(self, client: httpx.AsyncClient) -> bool:
        """Tải thông tin tổng quan và toàn bộ mục lục (TOC) của truyện."""
        import unicodedata
        page = 1
        self.episodes = []
        
        with console.status(f"[bold cyan]Đang quét mục lục truyện ({self.novel_code}) từ Syosetu...[/bold cyan]"):
            while True:
                url = self.base_url if page == 1 else f"{self.base_url}?p={page}"
                try:
                    res = await client.get(url, headers=SCRAPER_HEADERS, timeout=15.0)
                    if res.status_code != 200:
                        break
                    
                    soup = BeautifulSoup(res.text, "html.parser")
                    
                    if page == 1:
                        title_el = soup.select_one(".p-novel__title, p.novel_title, h1")
                        if title_el:
                            self.title = title_el.get_text(strip=True)
                        
                        author_el = soup.select_one(".p-novel__author, .novel_writername")
                        if author_el:
                            self.author = author_el.get_text(strip=True)
                            
                        synopsis_el = soup.select_one("#novel_ex")
                        if synopsis_el:
                            self.synopsis = synopsis_el.get_text(strip=True)

                    found_in_page = 0
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        match = re.search(rf"/{self.novel_code}/(\d+)/", href)
                        if match:
                            ep_num = int(match.group(1))
                            ep_title = a.get_text(strip=True)
                            
                            if not any(e["ep"] == ep_num for e in self.episodes):
                                ch_num = ep_num
                                m_ch = re.search(r"第([0-9０-９]+)話", ep_title)
                                if m_ch:
                                    raw_digit = m_ch.group(1)
                                    converted = unicodedata.normalize('NFKC', raw_digit)
                                    if converted.isdigit():
                                        ch_num = int(converted)

                                self.episodes.append({
                                    "ep": ep_num,
                                    "ch": ch_num,
                                    "title": ep_title,
                                    "url": f"https://ncode.syosetu.com/{self.novel_code}/{ep_num}/"
                                })
                                found_in_page += 1

                    if found_in_page == 0:
                        break
                    page += 1
                except Exception as e:
                    break

        return len(self.episodes) > 0

    def get_existing_chapters(self, output_dir: Path) -> List[int]:
        """Quét danh sách các chương đã tải sẵn trong thư mục raw."""
        existing = []
        if not output_dir.exists():
            return existing
        
        for f in output_dir.glob("chuong_*_raw.txt"):
            try:
                if f.stat().st_size > 50:
                    m = re.search(r"chuong_(\d+)_raw\.txt", f.name)
                    if m:
                        existing.append(int(m.group(1)))
            except Exception:
                pass
        return sorted(existing)

async def scrape_single_episode(client: httpx.AsyncClient, ep_info: Dict, sem: asyncio.Semaphore) -> Tuple[bool, int, str, str]:
    """Tải và bóc tách nội dung 1 episode từ Syosetu."""
    async with sem:
        url = ep_info["url"]
        ep_num = ep_info["ep"]
        for attempt in range(3):
            try:
                res = await client.get(url, headers=SCRAPER_HEADERS, timeout=12.0)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, "html.parser")
                    title_el = soup.select_one(".p-novel__title, .novel_subtitle, h1")
                    title = title_el.get_text(strip=True) if title_el else ep_info["title"]
                    
                    lines = []
                    honbun = soup.select("#novel_honbun p, .p-novel__body p, p[id^='L']")
                    if honbun:
                        for p in honbun:
                            for rt in p.select("rt, rp"):
                                rt.decompose()
                            txt = p.get_text(strip=True)
                            if txt:
                                lines.append(txt)
                    else:
                        body_el = soup.select_one("#novel_honbun, .p-novel__body")
                        if body_el:
                            for rt in body_el.select("rt, rp"):
                                rt.decompose()
                            lines = [l.strip() for l in body_el.get_text().split("\n") if l.strip()]

                    if lines:
                        full_content = f"{title}\n\n" + "\n\n".join(lines)
                        return (True, ep_num, title, full_content)
                await asyncio.sleep(0.5)
            except Exception:
                await asyncio.sleep(0.8)

        return (False, ep_num, ep_info["title"], "")

async def run_batch_scrape(novel: SyosetuNovel, target_episodes: List[Dict], output_dir: Path, max_concurrency: int = 8, combine_all: bool = False):
    """Chạy cào raw bất đồng bộ đa luồng siêu tốc."""
    sem = asyncio.Semaphore(max_concurrency)
    total = len(target_episodes)
    
    console.print(f"\n[bold green]🚀 Bắt đầu tải {total} chương với {max_concurrency} luồng song song...[/bold green]")
    
    combined_texts = []
    success_count = 0
    output_dir.mkdir(parents=True, exist_ok=True)
    
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        tasks = [scrape_single_episode(client, ep_info, sem) for ep_info in target_episodes]
        
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
            task_id = progress.add_task("Đang tải dữ liệu...", total=total)
            
            for future in asyncio.as_completed(tasks):
                success, ep_num, title, content = await future
                if success:
                    success_count += 1
                    out_file = output_dir / f"chuong_{ep_num}_raw.txt"
                    out_file.write_text(content, encoding="utf-8")
                    if combine_all:
                        combined_texts.append((ep_num, title, content))
                progress.advance(task_id)

    if combine_all and combined_texts:
        combined_texts.sort(key=lambda x: x[0])
        all_file = output_dir / "TOAN_BO_TRUYEN_RAW.txt"
        merged_body = "\n\n" + ("=" * 50) + "\n\n"
        all_content = merged_body.join([c[2] for c in combined_texts])
        all_file.write_text(all_content, encoding="utf-8")
        console.print(f"[bold green]💾 Đã tạo file gộp toàn bộ nội dung:[/bold green] [yellow]{all_file}[/yellow]")

    console.print(f"\n[bold green]✅ HOÀN TẤT: Đã tải thành công {success_count}/{total} chương vào thư mục:[/bold green] [yellow]{output_dir}[/yellow]\n")


async def translate_novel_title_free(jp_title: str) -> str:
    """Dịch tiêu đề truyện tiếng Nhật sang tiếng Việt có dấu hoàn toàn MIỄN PHÍ bằng Google Gemini Free Tier."""
    if not jp_title:
        return ""
    cfg = load_config()
    free_key = cfg.get("gemini_api_key", "")
    sys_p = "Bạn là dịch giả Light Novel tiếng Nhật sang tiếng Việt hàng đầu. Hãy dịch tiêu đề Light Novel sau sang tiếng Việt chuẩn mực, mượt mà, hay và tự nhiên (chỉ trả về đúng tiêu đề tiếng Việt có dấu đầy đủ, không kèm ngoặc kép, không thêm lời dẫn hay giải thích):"

    # 1. Ưu tiên gọi Google Free API trực tiếp (gemini-2.5-flash / gemini_api_key) - Chi phí 0 ĐỒNG
    if free_key and free_key != "YOUR_GEMINI_API_KEY_HERE":
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={free_key}"
            body = {
                "contents": [{"parts": [{"text": f"{sys_p}\n\n{jp_title}"}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 100}
            }
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                res = await client.post(url, json=body)
                if res.status_code == 200:
                    data = res.json()
                    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                    text = text.strip('"“”\'').split("\n")[0].strip()
                    clean = re.sub(r'[\\/*?:"<>|]', '', text).strip()
                    if clean:
                        return clean
        except Exception:
            pass

    # 2. Fallback sang Relay/Model hiện tại nếu key free gặp sự cố
    try:
        _, api_k, cur_m = ensure_api_key(cfg)
        text = await call_gemini_api(api_k, cur_m, sys_p, [{"role": "user", "content": jp_title}])
        text = text.strip().strip('"“”\'').split("\n")[0].strip()
        return re.sub(r'[\\/*?:"<>|]', '', text).strip()
    except Exception:
        return ""

class NovelProject:
    """Đại diện cho một bộ Light Novel trong workspace."""
    def __init__(self, folder_path: Path, genre: str = "1"):
        self.path = folder_path
        self.name = folder_path.name
        self.raw_dir = folder_path / "raw"
        self.trans_dir = folder_path / "translated"
        self.glossary_dir = folder_path / "glossary"
        self.images_dir = folder_path / "images"
        self.backups_dir = folder_path / "backups"
        self.gallery_file = folder_path / "gallery.json"
        self.style_guide_file = folder_path / "style_guide.md"
        self.log_file = folder_path / "CHANGELOG.md"

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.trans_dir.mkdir(parents=True, exist_ok=True)
        self.glossary_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_default_templates(genre=genre)

    def append_project_log(self, category: str, message: str):
        """Ghi nhật ký thay đổi chi tiết của bộ truyện vào file CHANGELOG.md."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not self.log_file.exists():
            header = (
                f"# 📜 Nhật Ký Hoạt Động & Thay Đổi (Changelog) - {self.name}\n"
                f"*Tự động ghi lại toàn bộ tiến độ Dịch, Raw, cập nhật Glossary, Style Guide và Refactor.*\n\n"
                f"| Thời gian | Danh mục | Chi tiết thay đổi |\n"
                f"| :--- | :--- | :--- |\n"
            )
            self.log_file.write_text(header, encoding="utf-8")
        
        entry = f"| `{now_str}` | **{category}** | {message} |\n"
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass

    def _ensure_default_templates(self, genre: str = "1"):
        """Khởi tạo cấu trúc Canon Database V3.0 chuẩn Compact Entity Card cho bất kỳ bộ Novel mới nào."""
        self.glossary_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)

        index_file = self.glossary_dir / "ENTITY_INDEX.md"
        if not index_file.exists():
            content = (
                f"# 📇 MỤC LỤC THỰC THỂ CANON (ENTITY INDEX)\n"
                f"> **Tác phẩm:** {self.name}\n"
                f"> **Quy chuẩn:** Canon Database V3.0\n\n"
                f"---\n\n"
                f"| Mã ID | Tên Chuẩn Hóa | Tên Gốc (JP/Romaji) | Phân Loại | Trạng Thái | Mốc Xuất Hiện |\n"
                f"| :--- | :--- | :--- | :---: | :---: | :---: |\n"
            )
            index_file.write_text(content, encoding="utf-8")

        char_file = self.glossary_dir / "characters.md"
        if not char_file.exists():
            content = (
                f"# 👥 HỒ SƠ NHÂN VẬT (CHARACTER DATABASE)\n"
                f"> **Bộ truyện:** {self.name}\n"
                f"> **Quy chuẩn:** Compact Entity Cards (Thuần Việt 100%)\n\n"
                f"---\n\n"
            )
            char_file.write_text(content, encoding="utf-8")

        terms_file = self.glossary_dir / "terms.md"
        if not terms_file.exists():
            content = (
                f"# ⚔️ THUẬT NGỮ, KỸ NĂNG, MA PHÁP & BẢO KHÍ (TERMS & SKILLS)\n"
                f"> **Bộ truyện:** {self.name}\n"
                f"> **Quy tắc:** Kỹ năng, ma pháp, bảo khí chuẩn hóa theo cặp ngoặc 『...』\n\n"
                f"---\n\n"
            )
            terms_file.write_text(content, encoding="utf-8")

        rel_file = self.glossary_dir / "relationship_timeline.md"
        if not rel_file.exists():
            content = (
                f"# 💬 LỊCH SỬ QUAN HỆ & MA TRẬN XƯNG HÔ (RELATIONSHIP TIMELINE)\n"
                f"> **Bộ truyện:** {self.name}\n"
                f"> *Ghi nhận mọi biến chuyển quan hệ và xưng hô động theo tiến trình cốt truyện.*\n\n"
                f"---\n\n"
            )
            rel_file.write_text(content, encoding="utf-8")

        audit_file = self.glossary_dir / "GLOSSARY_AUDIT_LOG.md"
        if not audit_file.exists():
            content = (
                f"# 📜 SỔ CÁI NHẬT KÝ KIỂM TOÁN GLOSSARY (GLOSSARY AUDIT LOG)\n"
                f"> **Bộ truyện:** {self.name}\n"
                f"> *Tự động ghi vết mọi biến động: [MỚI], [CẬP NHẬT], [THAY ĐỔI], [ĐỔI XƯNG HÔ], [XUNG ĐỘT], [ĐÍNH CHÍNH TÁC GIẢ] theo thời gian thực.*\n\n"
                f"---\n\n"
            )
            audit_file.write_text(content, encoding="utf-8")

        events_file = self.glossary_dir / "events.md"
        if not events_file.exists():
            content = (
                f"# DÒNG THỜI GIAN & BIÊN NIÊN SỰ KIỆN (TIMELINE & EVENTS)\n"
                f"> **Bộ truyện:** {self.name}\n\n"
                f"---\n\n"
                f"| Tập | Tóm Tắt Diễn Biến Cốt Truyện Trọng Tâm | Nhân Vật Trọng Tâm | Địa Điểm / Bối Cảnh |\n"
                f"| :---: | :--- | :--- | :--- |\n"
            )
            events_file.write_text(content, encoding="utf-8")

        if not self.style_guide_file.exists():
            content = (
                f"# 📖 QUY TẮC VĂN PHONG & ĐẶC TRƯNG TÁC PHẨM (STYLE GUIDE)\n"
                f"> **Tác phẩm:** {self.name}\n\n"
                f"---\n\n"
                f"## 1. TONE & GIỌNG ĐIỆU CHỦ ĐẠO\n"
                f"- Giữ vững văn phong mượt mà, cảm xúc, không lạm dụng từ Hán Việt cổ xưa.\n\n"
                f"## 2. QUY TẮC XƯNG HÔ ĐẶC TRÙ\n"
                f"- Tuân thủ nghiêm ngặt Master Style Guide 2.1.\n"
            )
            self.style_guide_file.write_text(content, encoding="utf-8")

        if not self.log_file.exists():
            content = (
                f"# 📜 TIẾN ĐỘ DỰ ÁN & NHẬT KÝ BẢN DỊCH (PROJECT CHANGELOG)\n"
                f"**Tác phẩm:** {self.name}\n\n"
                f"---\n\n"
                f"> [!INFO] 📊 BẢNG TỔNG QUAN TIẾN ĐỘ\n"
                f"> * **📚 Trạng thái:** Đang tiến hành\n"
                f"> * **📝 Hệ thống:** Canon Database V3.0 & Web Hub\n"
            )
            self.log_file.write_text(content, encoding="utf-8")

    def get_style_guide_content(self) -> str:
        if self.style_guide_file.exists():
            return self.style_guide_file.read_text(encoding="utf-8").strip()
        return ""

    def get_glossary_content(self) -> str:
        glossary_texts = []
        if self.glossary_dir.exists():
            for f in sorted(self.glossary_dir.glob("*.md")):
                try:
                    txt = f.read_text(encoding="utf-8").strip()
                    if txt:
                        glossary_texts.append(f"### File: {f.name}\n{txt}")
                except Exception:
                    pass
        return "\n\n".join(glossary_texts)

    def get_targeted_glossary_for_chapter(self, raw_text: str) -> str:
        """Quét nhanh raw_text và trích xuất các thực thể từ ENTITY_INDEX và Canon V3 xuất hiện trong chương."""
        if not raw_text:
            return ""

        index_file = self.glossary_dir / "ENTITY_INDEX.md"
        matched_items = []
        seen = set()

        if index_file.exists():
            for line in index_file.read_text(encoding="utf-8").splitlines():
                if not line.startswith("|") or "Mã ID" in line or ":---" in line:
                    continue
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) >= 4:
                    eid = parts[0].replace("`", "").strip()
                    vi_name = parts[1].replace("**", "").strip()
                    orig_name = parts[2].strip()
                    itype = parts[3].strip()

                    if vi_name and orig_name and vi_name not in seen:
                        orig_parts = [p.strip() for p in orig_name.split("/") if p.strip()]
                        for op in orig_parts:
                            if len(op) >= 2 and op in raw_text:
                                seen.add(vi_name)
                                matched_items.append(f"- **{op}** ({itype}) ➔ **{vi_name}** [`{eid}`]")
                                break

        if matched_items:
            lines_str = "\n".join(matched_items[:35])
            return f"### ⚠️ DANH SÁCH THỰC THỂ TRỌNG TÂM XUẤT HIỆN TRONG CHƯƠNG NÀY (BẮT BUỘC DÙNG ĐÚNG 100%):\n{lines_str}"
        return ""

    def sanitize_translation_text(self, text: str) -> str:
        """Bộ lọc hậu kỳ Đa Truyện (Universal): Dọn sạch kính ngữ tiếng Nhật ngoài thoại & chuẩn hóa thuật ngữ động từ Glossary."""
        if not text:
            return ""

        term_replacements = []
        seen_aliases = set()
        terms_file = self.glossary_dir / "terms.md"

        # 1. Trích xuất thuật ngữ động từ terms.md của bộ truyện hiện tại
        if terms_file.exists():
            for line in terms_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                vi_name, orig_name = "", ""
                m_tab = re.search(r'\|\s*\**\d+\**\s*\|\s*\**([^*|]+)\**\s*\|\s*([^|]+)\s*\|', line)
                if m_tab:
                    vi_name = m_tab.group(1).strip()
                    orig_name = m_tab.group(2).strip()
                else:
                    m_list = re.search(r'-\s*\**([^(:\*]+)\s*\(([^)]+)\)\**\s*:', line)
                    if m_list:
                        vi_name = m_list.group(1).strip()
                        orig_name = m_list.group(2).strip()

                if vi_name and orig_name and vi_name not in ["Tên Thuật Ngữ / Vũ Khí", "Sinh Vật / Quái Vật", "Tên Nhân Vật"]:
                    clean_vi = re.sub(r'\s*\([^)]*\)', '', vi_name).strip() or vi_name
                    for alias in orig_name.split("/"):
                        alias = alias.strip()
                        if alias and len(alias) >= 2 and alias.lower() != clean_vi.lower() and alias not in seen_aliases:
                            seen_aliases.add(alias)
                            term_replacements.append((alias, clean_vi))

        # Sắp xếp từ dài nhất lên trước để tránh đè chuỗi con
        term_replacements.sort(key=lambda x: len(x[0]), reverse=True)

        # 2. Quy tắc ma pháp nguyên tố tổng quát
        elemental_types = ["Thổ", "Băng", "Hỏa", "Phong", "Lôi", "Quang", "Ám", "Thủy", "Hắc", "Bạch", "Kim", "Mộc"]
        for elem in elemental_types:
            term_replacements.append((f"{elem} ma pháp", f"{elem} ma thuật"))

        # Lọc nhanh các alias thực sự xuất hiện trong toàn bộ văn bản chương
        active_reps = [(alias, repl) for alias, repl in term_replacements if alias in text]

        lines = text.splitlines()
        cleaned_lines = []
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

        for line in lines:
            l = line
            # 1. Chuẩn hóa thuật ngữ động
            for alias, repl in active_reps:
                if alias in l:
                    l = l.replace(alias, repl)

            # 2. Chuẩn hóa kính ngữ tiếng Nhật sang Romaji (-san, -kun, -chan...)
            for jp_suf, romaji_suf in jp_kanji_suffixes:
                if jp_suf in l:
                    l = l.replace(jp_suf, romaji_suf)

            cleaned_lines.append(l)

        return "\n".join(cleaned_lines)

    def sync_all_translated_with_glossary(self) -> int:
        """Quét và chuẩn hóa toàn bộ các chương đã dịch trong translated/ theo Glossary và bộ lọc hậu kỳ."""
        trans_files = list(self.trans_dir.glob("chuong_*.*"))
        if not trans_files:
            return 0

        modified_count = 0
        for f in trans_files:
            try:
                raw_text = f.read_text(encoding="utf-8")
                cleaned = self.sanitize_translation_text(raw_text)
                if cleaned != raw_text:
                    f.write_text(cleaned, encoding="utf-8")
                    modified_count += 1
            except Exception:
                pass
        return modified_count

    def add_term_to_glossary(self, original_term: str, translated_term: str, category: str = "skills", note: str = ""):
        """Thêm một thuật ngữ vào đúng mục trong terms.md."""
        terms_file = self.glossary_dir / "terms.md"
        entry = f"- **{translated_term} ({original_term}):** {note if note else 'Thuật ngữ'}"
        return self._insert_into_terms_section(terms_file, category, entry)

    def _insert_into_terms_section(self, terms_file: Path, category: str, line_entry: str) -> bool:
        """Chèn mục mới vào đúng tiêu đề danh mục chuẩn trong terms.md."""
        if not terms_file.exists():
            self._ensure_default_templates()
        
        content = terms_file.read_text(encoding="utf-8")
        
        # Ánh xạ từ khóa danh mục sang tiêu đề
        cat_map = {
            "classes": "## 1. Hệ Thống, Cấp Bậc & Chức Nghiệp",
            "skills": "## 2. Kỹ Năng, Ma Pháp & Chiêu Thức",
            "items": "## 3. Trang Bị, Vật Phẩm & Bảo Vật",
            "monsters": "## 4. Sinh Vật, Quái Vật & Tộc Loài",
            "locations": "## 5. Địa Danh, Tổ Chức & Thế Giới"
        }
        
        target_header = cat_map.get(category.lower(), "## 2. Kỹ Năng, Ma Pháp & Chiêu Thức")
        
        # Nếu chưa có tiêu đề, tạo thêm
        if target_header not in content:
            for h in cat_map.values():
                if h in content:
                    target_header = h
                    break
        
        if target_header in content:
            pattern = re.escape(target_header) + r"([\s\S]*?)(?=\n## |\Z)"
            match = re.search(pattern, content)
            if match:
                sec_body = match.group(1).rstrip()
                new_sec_body = sec_body + f"\n{line_entry}\n"
                new_content = content[:match.start(1)] + new_sec_body + content[match.end(1):]
                terms_file.write_text(new_content, encoding="utf-8")
                return True

        # Fallback chèn cuối file
        terms_file.write_text(content.rstrip() + f"\n{line_entry}\n", encoding="utf-8")
        return True

    def auto_update_glossary(self, extracted_data: Dict, chapter_num: int) -> Dict[str, int]:
        """Canon DB V2: Conflict Resolver + Evidence Log. Ghi Canon có chọn lọc theo do_tin_cay và loai_bang_chung."""
        counts = {"characters": 0, "terms": 0, "events": 0, "style_rules": 0, "relations": 0, "review_queue": 0}
        if not extracted_data or not isinstance(extracted_data, dict):
            return counts

        index_file = self.glossary_dir / "ENTITY_INDEX.md"
        index_txt = index_file.read_text(encoding="utf-8") if index_file.exists() else ""
        if not index_txt:
            index_txt = f"# 📇 MỤC LỤC THỰC THỂ CANON (ENTITY INDEX)\n> **Tác phẩm:** {self.name}\n> **Quy chuẩn:** Canon Database V3.0\n\n---\n\n| Mã ID | Tên Chuẩn Hóa | Tên Gốc (JP/Romaji) | Phân Loại | Trạng Thái | Mốc Xuất Hiện |\n| :--- | :--- | :--- | :---: | :---: | :---: |\n"

        char_count = len(re.findall(r'CHAR-\d+', index_txt)) + 1
        animal_count = len(re.findall(r'ANIMAL-\d+', index_txt)) + 1
        god_count = len(re.findall(r'GOD-\d+', index_txt)) + 1
        skill_count = len(re.findall(r'SKILL-\d+', index_txt)) + 1
        item_count = len(re.findall(r'ITEM-\d+', index_txt)) + 1
        org_count = len(re.findall(r'ORG-\d+', index_txt)) + 1
        place_count = len(re.findall(r'PLACE-\d+', index_txt)) + 1
        event_count = len(re.findall(r'EVENT-\d+', index_txt)) + 1
        term_count = len(re.findall(r'TERM-\d+', index_txt)) + 1

        char_file = self.glossary_dir / "characters.md"
        terms_file = self.glossary_dir / "terms.md"
        animals_file = self.glossary_dir / "animals.md"
        gods_file = self.glossary_dir / "gods_entities.md"
        orgs_file = self.glossary_dir / "factions_orgs.md"
        places_file = self.glossary_dir / "locations.md"
        events_file = self.glossary_dir / "events.md"
        audit_file = self.glossary_dir / "GLOSSARY_AUDIT_LOG.md"
        evidence_log_file = self.glossary_dir / "evidence_log.jsonl"
        review_queue_file = self.glossary_dir / "review_queue.jsonl"

        new_index_rows = []
        audit_entries = []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        evidence_entries = []
        review_entries = []

        # Loại bằng chứng yếu — chỉ ghi Evidence Log, không ghi Canon
        WEAK_CONTEXT = {"NHẮC ĐẾN", "TƯỞNG TƯỢNG", "GIẤC MƠ"}
        # Loại bằng chứng trung bình — ghi Canon nếu XÁC NHẬN, còn lại vào review_queue
        SOFT_CONTEXT = {"LỜI KỂ", "HỒI TƯỞNG", "THƯ TỪ", "SUY LUẬN"}

        def should_write_canon(item: dict) -> str:
            """Trả về 'CANON', 'REVIEW', hoặc 'LOG_ONLY'."""
            do_tin_cay = item.get("do_tin_cay", "CHƯA XÁC NHẬN")
            loai = item.get("loai_bang_chung", "TRỰC TIẾP")
            trang_thai = item.get("trang_thai", "BÌNH THƯỜNG")

            if loai in WEAK_CONTEXT:
                return "LOG_ONLY"
            if trang_thai == "XUNG ĐỘT":
                return "REVIEW"
            if do_tin_cay == "XÁC NHẬN" and loai == "TRỰC TIẾP":
                return "CANON"
            if do_tin_cay == "XÁC NHẬN" and loai in SOFT_CONTEXT:
                return "CANON"  # Ghi Canon quá khứ nếu pham_vi_thoi_gian = QUÁ KHỨ
            if do_tin_cay == "SUY ĐOÁN":
                return "REVIEW"
            return "REVIEW"

        # 1. Xử lý Nhân vật mới — Schema V2: nhan_vat_moi (backward-compat: new_characters)
        new_chars_v2 = extracted_data.get("nhan_vat_moi", [])
        new_chars_v1 = extracted_data.get("new_characters", [])
        new_chars = new_chars_v2 if new_chars_v2 else [
            {"ten_vi": c.get("name_vi",""), "ten_goc": c.get("name_orig",""),
             "vai_tro": c.get("role",""), "thien_chuc": c.get("job",""),
             "trang_thai": "BÌNH THƯỜNG", "ghi_chu": c.get("note",""),
             "bang_chung": "", "loai_bang_chung": "TRỰC TIẾP", "do_tin_cay": "SUY ĐOÁN",
             "hieu_luc_tu_chuong": None, "hieu_luc_den_chuong": None}
            for c in new_chars_v1
        ]

        if new_chars:
            cur_chars = char_file.read_text(encoding="utf-8") if char_file.exists() else "# 👥 HỒ SƠ NHÂN VẬT\n"
            for c in new_chars:
                name_vi = (c.get("ten_vi") or "").strip()
                name_orig = (c.get("ten_goc") or "").strip()
                if not name_vi and not name_orig:
                    continue

                # Ghi Evidence Log (LUÔN LUÔN)
                evidence_entries.append({
                    "loai": "nhan_vat", "ten_vi": name_vi, "ten_goc": name_orig,
                    "chuong": chapter_num, "thoi_gian": now_str,
                    "bang_chung": c.get("bang_chung",""),
                    "loai_bang_chung": c.get("loai_bang_chung","TRỰC TIẾP"),
                    "do_tin_cay": c.get("do_tin_cay","CHƯA XÁC NHẬN"),
                    "trang_thai": c.get("trang_thai","BÌNH THƯỜNG")
                })

                check = name_orig if name_orig else name_vi
                quyet_dinh = should_write_canon(c)

                if check.lower() in index_txt.lower() or check.lower() in cur_chars.lower():
                    # Entity đã tồn tại — chỉ ghi nếu có thay đổi và bằng chứng mạnh
                    if c.get("trang_thai") in ("ĐÃ THAY ĐỔI", "XUNG ĐỘT"):
                        review_entries.append({**c, "loai": "nhan_vat_conflict", "chuong": chapter_num, "thoi_gian": now_str})
                        counts["review_queue"] += 1
                        audit_entries.append(f"• 🟡 **[XUNG ĐỘT]** **{name_vi}** ({name_orig}): {c.get('trang_thai')} — Cần review (Tập {chapter_num})")
                    continue

                if quyet_dinh == "LOG_ONLY":
                    audit_entries.append(f"• 🔵 **[LOG]** **{name_vi}** ({name_orig}): {c.get('loai_bang_chung')} — Chỉ ghi Evidence Log (Tập {chapter_num})")
                    continue
                if quyet_dinh == "REVIEW":
                    review_entries.append({**c, "loai": "nhan_vat_moi", "chuong": chapter_num, "thoi_gian": now_str})
                    counts["review_queue"] += 1
                    audit_entries.append(f"• 🟡 **[REVIEW]** **{name_vi}** ({name_orig}): Cần xem lại (do_tin_cay={c.get('do_tin_cay')}) (Tập {chapter_num})")
                    continue

                # quyet_dinh == "CANON" → Ghi vào Canon
                role = c.get("vai_tro") or "Nhân vật mới"
                job = c.get("thien_chuc") or "Chưa rõ"
                status = c.get("trang_thai") or "CÒN SỐNG"
                note = c.get("ghi_chu") or ""
                bang_chung = c.get("bang_chung") or ""
                do_tin_cay = c.get("do_tin_cay") or "XÁC NHẬN"

                all_check = (role + " " + job + " " + name_vi).lower()
                if any(w in all_check for w in ["thần", "nữ thần", "thực thể", "god", "deity"]):
                    eid = f"GOD-{god_count:03d}"; god_count += 1; target_f = gods_file; itype = "Thần linh"
                elif any(w in all_check for w in ["thú", "động vật", "quái thú", "chó", "mèo", "animal", "pet", "tinh linh thú"]):
                    eid = f"ANIMAL-{animal_count:03d}"; animal_count += 1; target_f = animals_file; itype = "Động vật"
                else:
                    eid = f"CHAR-{char_count:03d}"; char_count += 1; target_f = char_file; itype = "Nhân vật"

                card = (f"\n---\n\n## [{eid}] {name_vi}\n\n"
                        f"- **id:** {eid}\n- **loại:** {itype.upper()}\n"
                        f"- **tên_chuẩn:** {name_vi}\n- **tên_gốc:** {name_orig}\n"
                        f"- **trạng_thái:** ĐÃ XÁC NHẬN\n- **canon:** CHÍNH THỨC\n"
                        f"- **độ_tin_cậy:** {do_tin_cay}\n- **khóa_bảo_vệ:** CÓ\n"
                        f"- **trạng_thái_nhân_vật:** {status} (Cập nhật Tập {chapter_num})\n"
                        f"- **thân_phận:** {role}\n- **thiên_chức:** {job}\n"
                        f"- **nguồn:** Tập {chapter_num}\n"
                        f"- **bằng_chứng:** {bang_chung}\n"
                        f"- **mô_tả:** {note}\n")
                cur_tf = target_f.read_text(encoding="utf-8") if target_f.exists() else f"# HỒ SƠ {itype.upper()}\n"
                target_f.write_text(cur_tf.rstrip() + "\n" + card, encoding="utf-8")

                new_index_rows.append(f"| `{eid}` | **{name_vi}** | {name_orig} | {itype} | `{status}` | Tập {chapter_num} |")
                audit_entries.append(f"• 🟢 **[CANON]** `{eid}` **{name_vi}** ({name_orig}): {role} [{c.get('do_tin_cay')}] (Tập {chapter_num})")
                counts["characters"] += 1


        # 2. Xử lý Thuật ngữ mới (6 nhánh: ORG / PLACE / EVENT / ITEM / SKILL / TERM)
        new_terms = extracted_data.get("new_terms", [])
        if new_terms:
            cur_terms = terms_file.read_text(encoding="utf-8") if terms_file.exists() else "# ⚔️ THUẬT NGỮ & KỸ NĂNG\n"
            for t in new_terms:
                term_vi = (t.get("term_vi") or "").strip()
                term_orig = (t.get("term_orig") or "").strip()
                if not term_vi and not term_orig:
                    continue
                check = term_orig if term_orig else term_vi
                if check.lower() in index_txt.lower() or check.lower() in cur_terms.lower():
                    continue

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

                card = f"\n---\n\n## [{eid}] {term_vi}\n\n- **id:** {eid}\n- **loại:** {itype.upper()}\n- **tên_chuẩn:** {term_vi}\n- **tên_gốc:** {term_orig}\n- **trạng_thái:** ĐÃ XÁC NHẬN\n- **canon:** CHÍNH THỨC\n- **độ_tin_cậy:** TUYỆT ĐỐI\n- **khóa_bảo_vệ:** CÓ\n- **nguồn:** Tập {chapter_num}\n- **mô_tả:** {desc}\n"
                cur_tf = target_f.read_text(encoding="utf-8") if target_f.exists() else f"# HỒ SƠ {itype.upper()}\n"
                target_f.write_text(cur_tf.rstrip() + "\n" + card, encoding="utf-8")

                new_index_rows.append(f"| `{eid}` | **{term_vi}** | {term_orig} | {itype} | `CHÍNH THỨC` | Tập {chapter_num} |")
                audit_entries.append(f"• 🔮 **[MỚI]** `{eid}` **{term_vi}** ({term_orig}): {desc} (Tập {chapter_num})")
                counts["terms"] += 1

        # Cập nhật Index
        if new_index_rows:
            index_file.write_text(index_txt.rstrip() + "\n" + "\n".join(new_index_rows) + "\n", encoding="utf-8")

        # 3. Cập nhật Sự kiện cốt truyện — Schema V2: su_kien_chinh (backward-compat: key_events)
        su_kien_v2 = extracted_data.get("su_kien_chinh", [])
        key_events_v1 = extracted_data.get("key_events", [])
        all_events = su_kien_v2 if su_kien_v2 else [
            {"su_kien": ev if isinstance(ev, str) else ev.get("event",""),
             "bang_chung": "", "loai_bang_chung": "TRỰC TIẾP", "do_tin_cay": "XÁC NHẬN"}
            for ev in key_events_v1
        ]
        if all_events:
            cur_ev = events_file.read_text(encoding="utf-8") if events_file.exists() else "# DÒNG THỜI GIAN & SỰ KIỆN\n"
            ev_lines = []
            for ev in all_events:
                su_kien = ev.get("su_kien","") if isinstance(ev, dict) else str(ev)
                bang_chung = ev.get("bang_chung","") if isinstance(ev, dict) else ""
                do_tin_cay = ev.get("do_tin_cay","XÁC NHẬN") if isinstance(ev, dict) else "XÁC NHẬN"
                ev_lines.append(f"| Tập {chapter_num} | {su_kien} | {do_tin_cay} | {bang_chung[:80] if bang_chung else 'Không có'} |")
            events_file.write_text(cur_ev.rstrip() + "\n" + "\n".join(ev_lines) + "\n", encoding="utf-8")
            counts["events"] += len(ev_lines)

        # 4. Ghi Audit Log
        if audit_entries:
            cur_audit = audit_file.read_text(encoding="utf-8") if audit_file.exists() else "# 📜 SỔ CÁI NHẬT KÝ KIỂM TOÁN GLOSSARY\n"
            log_block = (f"\n### ⏱️ ĐỢT CẬP NHẬT TẬP {chapter_num}: `{now_str}` (Dịch AI — Canon DB V2)\n"
                         + "\n".join(audit_entries) + "\n")
            audit_file.write_text(cur_audit.rstrip() + "\n" + log_block, encoding="utf-8")

        # 5. Cập nhật Quy tắc Văn phong — Schema V2: quy_tac_van_phong (backward-compat: new_style_rules)
        style_v2 = extracted_data.get("quy_tac_van_phong", [])
        style_v1 = extracted_data.get("new_style_rules", [])
        all_style = style_v2 if style_v2 else [
            {"doi_tuong": r.get("target",""), "quy_tac": r.get("rule",""),
             "bang_chung": "", "do_tin_cay": "SUY ĐOÁN", "trang_thai": "BÌNH THƯỜNG"}
            for r in style_v1
        ]
        if all_style and self.style_guide_file.exists():
            style_txt = self.style_guide_file.read_text(encoding="utf-8")
            added_rules = []
            for r in all_style:
                target_r = (r.get("doi_tuong") or "").strip()
                rule = (r.get("quy_tac") or "").strip()
                bang_chung = (r.get("bang_chung") or "").strip()
                if not target_r or not rule:
                    continue
                # Chỉ ghi Style Rule nếu bằng chứng đủ mạnh
                if r.get("do_tin_cay") in ("XÁC NHẬN",) and r.get("loai_bang_chung","TRỰC TIẾP") not in ("TƯỞNG TƯỢNG","GIẤC MƠ"):
                    if rule.lower() not in style_txt.lower() and target_r.lower() not in style_txt.lower():
                        evidence_note = f' [Bằng chứng: "{bang_chung[:60]}..."]' if bang_chung else ""
                        added_rules.append(f"- **{target_r}:** {rule}{evidence_note} *(Tự động học từ Tập {chapter_num})*")
                        counts["style_rules"] += 1
            if added_rules:
                self.style_guide_file.write_text(
                    style_txt.rstrip() + "\n\n### Quy tắc mới từ Tập " + str(chapter_num) + ":\n" + "\n".join(added_rules) + "\n",
                    encoding="utf-8"
                )

        # 6. Ghi Evidence Log (APPEND-ONLY — KHÔNG BAO GIỜ XÓA)
        if evidence_entries:
            with open(evidence_log_file, "a", encoding="utf-8") as ef:
                for entry in evidence_entries:
                    ef.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # 7. Ghi Review Queue (các thực thể cần người dùng xem lại)
        if review_entries:
            with open(review_queue_file, "a", encoding="utf-8") as rf:
                for entry in review_entries:
                    rf.write(json.dumps(entry, ensure_ascii=False) + "\n")
            # Thông báo cho người dùng biết có mục cần review
            console.print(f"  [bold yellow]⚠️ {len(review_entries)} thực thể chưa đủ bằng chứng → Đưa vào hàng chờ review ({review_queue_file.name})[/bold yellow]")

        if counts["characters"] > 0:
            names = [c.get("ten_vi", c.get("name_vi", "")) for c in new_chars if c.get("ten_vi") or c.get("name_vi")]
            self.append_project_log("Canon Database V2", f"Tập {chapter_num}: Thêm mới {counts['characters']} nhân vật ({', '.join(names[:3])})")
        if counts["terms"] > 0:
            new_terms_list = extracted_data.get("thuat_ngu_moi", extracted_data.get("new_terms", []))
            terms_names = [t.get("ten_vi", t.get("term_vi", "")) for t in new_terms_list if t.get("ten_vi") or t.get("term_vi")]
            self.append_project_log("Canon Database V2", f"Tập {chapter_num}: Thêm mới {counts['terms']} thực thể ({', '.join(terms_names[:3])})")
        if counts["review_queue"] > 0:
            self.append_project_log("Canon Review Queue", f"Tập {chapter_num}: {counts['review_queue']} thực thể đưa vào hàng chờ review")

        return counts


    def reconcile_batch_glossary(self, targets: List[RawChapterInfo]) -> int:
        """Pha 2: Tự động quét và chuẩn hóa toàn bộ các tập vừa dịch theo Bảng Glossary Hợp Nhất."""
        terms_file = self.glossary_dir / "terms.md"
        chars_file = self.glossary_dir / "characters.md"
        
        mapping = []
        
        # 1. Trích xuất cặp từ characters.md
        if chars_file.exists():
            for line in chars_file.read_text(encoding="utf-8").splitlines():
                m = re.search(r"^-\s*\*\*([^(]+)\s*\(([^)]+)\)\s*\*\*", line)
                if m:
                    vi = m.group(1).strip()
                    orig = m.group(2).strip()
                    if vi and orig and vi != orig and len(orig) >= 2:
                        mapping.append((orig, vi))

        # 2. Trích xuất cặp từ terms.md
        if terms_file.exists():
            for line in terms_file.read_text(encoding="utf-8").splitlines():
                m = re.search(r"^-\s*\*\*([^(]+)\s*\(([^)]+)\)\s*\*\*", line)
                if m:
                    vi = m.group(1).strip()
                    aliases_str = m.group(2).strip()
                    for alias in aliases_str.split("/"):
                        alias = alias.strip()
                        if vi and alias and vi != alias and len(alias) >= 2:
                            mapping.append((alias, vi))

        if not mapping:
            return 0

        # Sắp xếp từ dài nhất lên trước để tránh thay thế chuỗi con
        mapping = sorted(list(set(mapping)), key=lambda x: len(x[0]), reverse=True)

        reconciled_count = 0
        ep_set = {t.story_ep for t in targets}

        for trans_file in self.trans_dir.glob("chuong_*.*"):
            m = re.search(r"chuong_(\d+)", trans_file.name)
            if not m:
                continue
            ep = int(m.group(1))
            if ep not in ep_set:
                continue

            try:
                content = trans_file.read_text(encoding="utf-8")
                raw_file = next((t.path for t in targets if t.story_ep == ep), None)
                if not raw_file or not raw_file.exists():
                    continue
                raw_txt = raw_file.read_text(encoding="utf-8")

                new_content = content
                changed = False

                for orig, canonical_vi in mapping:
                    if orig in raw_txt and orig in new_content:
                        new_content = new_content.replace(orig, canonical_vi)
                        changed = True
                        reconciled_count += 1

                if changed and new_content != content:
                    trans_file.write_text(new_content, encoding="utf-8")
            except Exception:
                pass

        return reconciled_count

    def list_raw_chapters(self) -> List[RawChapterInfo]:
        chaps = []
        for f in self.raw_dir.glob("chuong_*_raw.txt"):
            if f.stat().st_size > 50:
                chaps.append(RawChapterInfo(f))
        return sorted(chaps, key=lambda x: (x.story_ep, x.file_ep))

    def list_translated_chapters(self) -> List[int]:
        chaps = []
        for f in self.trans_dir.glob("chuong_*.*"):
            m = re.search(r"chuong_(\d+)(?:_.*)?\.(md|txt|docx)$", f.name, re.IGNORECASE)
            if m and f.stat().st_size > 50:
                chaps.append(int(m.group(1)))
        return sorted(list(set(chaps)))

def scan_all_projects() -> List[NovelProject]:
    projects = []
    for item in ROOT_DIR.iterdir():
        if item.is_dir() and not item.name.startswith(".") and item.name not in ["tools", "audio", "scratch"]:
            if not item.name.startswith("http") and "syosetu.com" not in item.name.lower():
                projects.append(NovelProject(item))
    return sorted(projects, key=lambda p: p.name)

def build_system_prompt(project: NovelProject, raw_text: str = "") -> str:
    master_guide_file = TOOLS_DIR / "MASTER_STYLE_GUIDE.md"
    master_rules = master_guide_file.read_text(encoding="utf-8") if master_guide_file.exists() else ""
    
    style_guide = project.get_style_guide_content()
    glossary = project.get_glossary_content()
    targeted_glossary = project.get_targeted_glossary_for_chapter(raw_text) if raw_text else ""

    base_prompt = f"""Bạn là một Dịch Giả & Nhà Phân Tích Lore Light Novel tiếng Nhật sang tiếng Việt hàng đầu.
Nhiệm vụ của bạn gồm HAI phần độc lập:

【PHẦN 1 — DỊCH THUẬT】
Dịch chương truyện tiếng Nhật sang tiếng Việt với chất lượng văn học xuất sắc, mượt mà và cảm xúc nhất.

【PHẦN 2 — KHAI THÁC LORE】
Phân tích chương và trích xuất thực thể, quan hệ, sự kiện vào JSON Schema V2 với đầy đủ bằng chứng, độ tin cậy và loại ngữ cảnh.

================================================================================
BỘ QUY CHUẨN DỊCH THUẬT & BIÊN TẬP TỐI CAO (MASTER RULESET):
================================================================================
{master_rules}

================================================================================
LUẬT PHÂN BIỆT NGỮ CẢNH XUẤT HIỆN (BẮT BUỘC TUÂN THỦ):
================================================================================
RAW là nguồn dữ liệu nguyên tác. Việc một tên/thuật ngữ xuất hiện trong RAW KHÔNG có nghĩa là thực thể đó thực sự xuất hiện hoặc thực hiện hành động trong hiện tại. Phải xác định loại ngữ cảnh (loai_bang_chung) cho mỗi bằng chứng:

- TRỰC TIẾP    : Nhân vật đang hành động trong scene hiện tại → pham_vi_thoi_gian: HIỆN TẠI
- LỜI KỂ       : Nhân vật A kể về B cho C nghe → diễn giải theo người kể
- HỒI TƯỞNG   : Flashback, ký ức → pham_vi_thoi_gian: QUÁ KHỨ (CÓ THỂ ghi Canon quá khứ nhưng KHÔNG ghi trạng thái hiện tại)
- THƯ TỪ       : Nội dung thư, nhật ký, tài liệu → pham_vi_thoi_gian theo thời điểm viết
- SUY LUẬN     : AI suy ra từ ngữ cảnh, không có câu rõ ràng → chỉ ghi do_tin_cay: SUY ĐOÁN
- NHẮC ĐẾN     : Tên được đề cập nhưng không có chi tiết → KHÔNG ghi vào Canon chính
- TƯỞNG TƯỢNG  : Nhân vật tưởng tượng kịch bản giả định → BỎ QUA hoàn toàn
- GIẤC MƠ      : Cảnh trong mơ → BỎ QUA hoàn toàn

Ví dụ đúng:
  "Felix nhớ lại hình ảnh Elsa cầm chiếc trâm..." → loai_bang_chung: HỒI TƯỞNG, pham_vi_thoi_gian: QUÁ KHỨ
  KHÔNG suy ra Elsa đang xuất hiện hoặc đang sở hữu trâm ở chương này.

================================================================================
QUY TẮC SỬ DỤNG CANON HIỆN TẠI:
================================================================================
Canon hiện tại là TRẠNG THÁI ƯU TIÊN MẶC ĐỊNH — không phải chân lý tuyệt đối.
- Nếu RAW chương này NHẤT QUÁN với Canon → Dùng Canon, không ghi gì thêm.
- Nếu RAW chương này cung cấp bằng chứng TRỰC TIẾP mâu thuẫn Canon cũ → Ghi nhận trang_thai: XUNG ĐỘT, cung cấp bang_chung rõ ràng, KHÔNG tự ý ép diễn giải theo Canon cũ.
- Nếu RAW cho thấy quan hệ/trạng thái đã THAY ĐỔI (ví dụ: bạn → kẻ thù) → Ghi trang_thai: ĐÃ THAY ĐỔI với hieu_luc_tu_chuong là chương hiện tại.

### 📦 CẤU TRÚC ĐẦU RA BẮT BUỘC (OUTPUT FORMAT — CANON DB V2):
Bạn PHẢI trả về kết quả theo đúng 2 phần được ngăn cách bằng `=== EXTRACTED_GLOSSARY ===`:

[Toàn bộ nội dung bản dịch tiếng Việt hoàn chỉnh của chương]

=== EXTRACTED_GLOSSARY ===
```json
{{
  "nhan_vat_moi": [
    {{
      "ten_vi": "Tên tiếng Việt",
      "ten_goc": "Tên gốc Kanji/Kana",
      "vai_tro": "Vai trò/Phe phái",
      "thien_chuc": "Thiên chức/Năng lực",
      "trang_thai": "BÌNH THƯỜNG",
      "ghi_chu": "Ghi chú ngắn",
      "bang_chung": "Câu/đoạn trong chương làm căn cứ (PHẢI có, không được để trống)",
      "loai_bang_chung": "TRỰC TIẾP",
      "do_tin_cay": "XÁC NHẬN",
      "hieu_luc_tu_chuong": null,
      "hieu_luc_den_chuong": null
    }}
  ],
  "thuat_ngu_moi": [
    {{
      "ten_vi": "Tên tiếng Việt",
      "ten_goc": "Tên gốc",
      "loai": "Kỹ năng/Sinh vật/Vật phẩm/Địa danh/Thiên chức/Tổ chức",
      "mo_ta": "Mô tả tác dụng/đặc tính",
      "bang_chung": "Câu/đoạn trong chương làm căn cứ",
      "loai_bang_chung": "TRỰC TIẾP",
      "do_tin_cay": "XÁC NHẬN",
      "hieu_luc_tu_chuong": null,
      "hieu_luc_den_chuong": null
    }}
  ],
  "quan_he": [
    {{
      "nguon": "Tên hoặc ID nhân vật/thực thể nguồn",
      "loai_quan_he": "SỞ HỮU / BẠN / ĐỒNG MINH / KẺ THÙ / PHỤC VỤ / GIA ĐÌNH / TÌNH CẢM / ...",
      "dich": "Tên hoặc ID nhân vật/thực thể đích",
      "pham_vi_thoi_gian": "HIỆN TẠI",
      "bang_chung": "Câu/đoạn trong chương làm căn cứ (PHẢI có)",
      "loai_bang_chung": "TRỰC TIẾP",
      "do_tin_cay": "XÁC NHẬN",
      "trang_thai": "BÌNH THƯỜNG",
      "hieu_luc_tu_chuong": null,
      "hieu_luc_den_chuong": null
    }}
  ],
  "quy_tac_van_phong": [
    {{
      "doi_tuong": "Tên Nhân vật hoặc Cặp đối thoại (A ↔ B)",
      "quy_tac": "Quy tắc xưng hô/tính cách đặc biệt",
      "bang_chung": "Câu thoại minh họa trong chương",
      "loai_bang_chung": "TRỰC TIẾP",
      "do_tin_cay": "XÁC NHẬN",
      "trang_thai": "BÌNH THƯỜNG",
      "hieu_luc_tu_chuong": null,
      "hieu_luc_den_chuong": null
    }}
  ],
  "su_kien_chinh": [
    {{
      "su_kien": "Mô tả sự kiện quan trọng",
      "bang_chung": "Câu/đoạn trong chương làm căn cứ",
      "loai_bang_chung": "TRỰC TIẾP",
      "do_tin_cay": "XÁC NHẬN"
    }}
  ]
}}
```

QUAN TRỌNG — QUY TẮC BẰNG CHỨNG:
- Trường "bang_chung" KHÔNG ĐƯỢC để trống nếu do_tin_cay là "XÁC NHẬN". Nếu không tìm được câu cụ thể, hạ xuống "SUY ĐOÁN".
- Giá trị hợp lệ cho do_tin_cay: "XÁC NHẬN" / "SUY ĐOÁN" / "CHƯA XÁC NHẬN"
- Giá trị hợp lệ cho trang_thai: "BÌNH THƯỜNG" / "XUNG ĐỘT" / "ĐÃ THAY ĐỔI" / "ĐÃ LOẠI BỎ"
- Giá trị hợp lệ cho loai_bang_chung: "TRỰC TIẾP" / "LỜI KỂ" / "HỒI TƯỞNG" / "THƯ TỪ" / "SUY LUẬN" / "NHẮC ĐẾN" / "TƯỞNG TƯỢNG" / "GIẤC MƠ"
- Giá trị hợp lệ cho pham_vi_thoi_gian: "HIỆN TẠI" / "QUÁ KHỨ" / "TƯƠNG LAI"
"""
    if targeted_glossary:
        base_prompt += f"\n\n{targeted_glossary}\n"

    if style_guide:
        base_prompt += f"\n\n### 📖 QUY TẮC VĂN PHONG RIÊNG CỦA BỘ TRUYỆN ({project.name}):\n{style_guide}\n"

    if glossary:
        base_prompt += f"\n\n### 📚 CANON HIỆN TẠI — TRẠNG THÁI ƯU TIÊN MẶC ĐỊNH (xem quy tắc Canon bên trên):\n{glossary}\n"

    return base_prompt

import random

ACTIVE_PROGRESS = None

async def live_countdown(seconds: float, label: str = "Hồi phục hạn mức 15 RPM"):
    """Đếm ngược thời gian thực từng giây, hòa nhập 100% với Rich Progress mà không bị đè dòng."""
    global ACTIVE_PROGRESS
    total_sec = max(1, int(seconds))
    
    if ACTIVE_PROGRESS is not None:
        try:
            cd_task = ACTIVE_PROGRESS.add_task(f"[bold yellow]⏳ {label} (Còn {total_sec}s)[/bold yellow]", total=total_sec)
            for passed in range(1, total_sec + 1):
                rem = total_sec - passed
                ACTIVE_PROGRESS.update(cd_task, completed=passed, description=f"[bold yellow]⏳ {label} (Còn {rem}s)[/bold yellow]")
                await asyncio.sleep(1.0)
            ACTIVE_PROGRESS.remove_task(cd_task)
            ACTIVE_PROGRESS.console.print(f"  [bold green]✅ [{label}]: Hồi phục hoàn tất! Đang gửi tiếp...[/bold green]")
            return
        except Exception:
            pass

    for remaining in range(total_sec, 0, -1):
        console.print(f"\r  [bold yellow]⏳ [{label}]: Còn lại {remaining:02d}s trước khi gửi tiếp...[/bold yellow]   ", end="")
        await asyncio.sleep(1.0)
    console.print(f"\r  [bold green]✅ [{label}]: Đã hoàn tất hồi phục! Đang tiếp tục dịch...[/bold green]          \n")

class GeminiRateLimiter:
    """Bộ điều phối nhịp độ toàn cục đảm bảo an toàn cho Gemini Free, bỏ hãm tốc độ cho Relay."""
    def __init__(self, min_interval: float = 3.5):
        self.min_interval = min_interval
        self._lock = asyncio.Lock()
        self._last_call_time = 0.0
        self.cooldown_until = 0.0

    async def acquire(self, is_relay: bool = False):
        if is_relay:
            return  # Tối ưu siêu tốc: Bỏ hãm tốc độ hoàn toàn cho Relay trả phí
        async with self._lock:
            now = time.time()
            if now < self.cooldown_until:
                sleep_dur = (self.cooldown_until - now) + random.uniform(0.5, 2.0)
                await live_countdown(sleep_dur, "Đang chờ hồi phục hạn mức")
                now = time.time()

            elapsed = now - self._last_call_time
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            
            self._last_call_time = time.time()

    def set_cooldown(self, seconds: float):
        """Đặt lệnh tạm dừng toàn cục cho tất cả các luồng để tránh Thundering Herd."""
        self.cooldown_until = max(self.cooldown_until, time.time() + seconds)

GLOBAL_RATE_LIMITER = GeminiRateLimiter(min_interval=3.5)

async def call_gemini_api(api_key: str, model: str, system_prompt: str, messages: List[Dict], max_retries: int = 5) -> str:
    cfg = load_config()
    engine = cfg.get("engine", "gemini")
    
    if engine == "relay":
        base_url = cfg.get("relay_base_url", "").strip().rstrip("/")
        if not base_url.endswith("/v1") and not "/chat/completions" in base_url:
            chat_url = f"{base_url}/v1/chat/completions" if "/v1" not in base_url else f"{base_url}/chat/completions"
        elif base_url.endswith("/v1"):
            chat_url = f"{base_url}/chat/completions"
        else:
            chat_url = base_url

        chat_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            chat_messages.append({"role": msg["role"], "content": msg["content"]})

        payload = {
            "model": model,
            "messages": chat_messages,
            "temperature": 0.35,
            "max_tokens": 8192
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    res = await client.post(chat_url, json=payload, headers=headers)
                    if res.status_code == 429:
                        if attempt < max_retries:
                            wait_sec = 10.0 + attempt * 5.0
                            await live_countdown(wait_sec, f"Relay Rate Limit - Thử lại {attempt+1}/{max_retries}")
                            continue
                        raise Exception(f"Relay API Error (429): Quá tải hạn mức. Chi tiết: {res.text}")

                    if res.status_code != 200:
                        raise Exception(f"Relay API Error ({res.status_code}): {res.text}")

                    data = res.json()
                    choices = data.get("choices", [])
                    if not choices or "message" not in choices[0]:
                        raise Exception("Không nhận được nội dung trả về từ Relay API.")
                    
                    return choices[0]["message"].get("content", "").strip()
            except httpx.RequestError as e:
                if attempt < max_retries:
                    await asyncio.sleep(3.0)
                    continue
                raise Exception(f"Lỗi kết nối tới Relay API: {e}")

    # ===== ENGINE: GOOGLE GEMINI TRỰC TIẾP =====
    current_model = model
    fallback_models = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest"]

    for attempt in range(max_retries + 1):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={api_key}"
        
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })

        payload = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "temperature": 0.35,
                "topP": 0.95,
                "maxOutputTokens": 8192,
                "thinkingConfig": {
                    "thinkingBudget": 0
                }
            }
        }

        await GLOBAL_RATE_LIMITER.acquire()
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                res = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
                if res.status_code == 429:
                    err_data = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
                    err_msg = err_data.get("error", {}).get("message", res.text)

                    # Tự động Auto-Failover sang Flash Lite nếu Model chính chạm giới hạn 20 req preview
                    if current_model == "gemini-3.5-flash" and fallback_models:
                        next_model = fallback_models.pop(0)
                        console.print(f"\n[bold yellow]⚡ Model [{current_model}] chạm hạn mức Free, tự động chuyển sang [{next_model}] ngay lập tức...[/bold yellow]")
                        current_model = next_model
                        continue

                    if attempt < max_retries:
                        m = re.search(r"retry in (\d+(?:\.\d+)?)s", err_msg, re.IGNORECASE)
                        base_wait = float(m.group(1)) if m else (25.0 + attempt * 5.0)
                        jitter = random.uniform(1.5, 3.5)
                        wait_sec = base_wait + jitter
                        GLOBAL_RATE_LIMITER.set_cooldown(wait_sec)
                        await live_countdown(wait_sec, f"Hạn mức 15 RPM - Thử lại {attempt+1}/{max_retries}")
                        continue
                    else:
                        raise Exception(f"Gemini API Error (429): Vượt quá hạn mức yêu cầu Google. Chi tiết: {err_msg}")

                if res.status_code != 200:
                    err_data = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
                    err_msg = err_data.get("error", {}).get("message", res.text)
                    raise Exception(f"Gemini API Error ({res.status_code}): {err_msg}")

                data = res.json()
                candidates = data.get("candidates", [])
                if not candidates or "content" not in candidates[0]:
                    raise Exception("Không nhận được nội dung trả về từ Gemini.")
                
                parts = candidates[0]["content"].get("parts", [])
                text_parts = [p.get("text", "") for p in parts if "text" in p]
                return "\n".join(text_parts).strip()
        except httpx.RequestError as e:
            if attempt < max_retries:
                await asyncio.sleep(3.0)
                continue
            raise Exception(f"Lỗi mạng khi kết nối Gemini: {e}")

def parse_ai_response(response_text: str) -> Tuple[str, Dict]:
    if "=== EXTRACTED_GLOSSARY ===" in response_text:
        parts = response_text.split("=== EXTRACTED_GLOSSARY ===", 1)
        trans_text = parts[0].strip()
        glossary_part = parts[1].strip()
        
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", glossary_part)
        raw_json = json_match.group(1) if json_match else glossary_part
        
        try:
            extracted_json = json.loads(raw_json)

            # === CANON DB V2: Validate & Normalize ===
            # 1. Tự động hạ do_tin_cay: XÁC NHẬN → SUY ĐOÁN nếu bang_chung trống
            for section_key in ["nhan_vat_moi", "thuat_ngu_moi", "quan_he", "quy_tac_van_phong", "su_kien_chinh"]:
                for item in extracted_json.get(section_key, []):
                    if isinstance(item, dict):
                        if item.get("do_tin_cay") == "XÁC NHẬN" and not (item.get("bang_chung") or "").strip():
                            item["do_tin_cay"] = "SUY ĐOÁN"
                        # Đặt giá trị mặc định nếu thiếu
                        item.setdefault("trang_thai", "BÌNH THƯỜNG")
                        item.setdefault("loai_bang_chung", "TRỰC TIẾP")
                        item.setdefault("do_tin_cay", "CHƯA XÁC NHẬN")
                        item.setdefault("pham_vi_thoi_gian", "HIỆN TẠI")
                        item.setdefault("hieu_luc_tu_chuong", None)
                        item.setdefault("hieu_luc_den_chuong", None)

            # 2. Backward-compat: Map schema cũ → schema V2 nếu AI vẫn dùng tên cũ
            if "new_characters" in extracted_json and "nhan_vat_moi" not in extracted_json:
                extracted_json["nhan_vat_moi"] = [
                    {"ten_vi": c.get("name_vi",""), "ten_goc": c.get("name_orig",""),
                     "vai_tro": c.get("role",""), "thien_chuc": c.get("job",""),
                     "trang_thai": "BÌNH THƯỜNG", "ghi_chu": c.get("note",""),
                     "bang_chung": "", "loai_bang_chung": "TRỰC TIẾP",
                     "do_tin_cay": "SUY ĐOÁN",  # Không có bằng chứng → SUY ĐOÁN
                     "hieu_luc_tu_chuong": None, "hieu_luc_den_chuong": None}
                    for c in extracted_json.get("new_characters", [])
                ]
            if "new_terms" in extracted_json and "thuat_ngu_moi" not in extracted_json:
                extracted_json["thuat_ngu_moi"] = [
                    {"ten_vi": t.get("term_vi",""), "ten_goc": t.get("term_orig",""),
                     "loai": t.get("type",""), "mo_ta": t.get("description",""),
                     "bang_chung": "", "loai_bang_chung": "TRỰC TIẾP",
                     "do_tin_cay": "SUY ĐOÁN",
                     "hieu_luc_tu_chuong": None, "hieu_luc_den_chuong": None}
                    for t in extracted_json.get("new_terms", [])
                ]
            if "new_style_rules" in extracted_json and "quy_tac_van_phong" not in extracted_json:
                extracted_json["quy_tac_van_phong"] = [
                    {"doi_tuong": r.get("target",""), "quy_tac": r.get("rule",""),
                     "bang_chung": "", "loai_bang_chung": "TRỰC TIẾP",
                     "do_tin_cay": "SUY ĐOÁN", "trang_thai": "BÌNH THƯỜNG",
                     "hieu_luc_tu_chuong": None, "hieu_luc_den_chuong": None}
                    for r in extracted_json.get("new_style_rules", [])
                ]
            if "key_events" in extracted_json and "su_kien_chinh" not in extracted_json:
                extracted_json["su_kien_chinh"] = [
                    {"su_kien": ev if isinstance(ev, str) else ev.get("event",""),
                     "bang_chung": ev.get("evidence","") if isinstance(ev, dict) else "",
                     "loai_bang_chung": "TRỰC TIẾP", "do_tin_cay": "XÁC NHẬN" if isinstance(ev, dict) and ev.get("evidence") else "SUY ĐOÁN"}
                    for ev in extracted_json.get("key_events", [])
                ]

            return trans_text, extracted_json
        except Exception:
            return trans_text, {}
    
    return response_text.strip(), {}


def get_clean_slug(trans_text: str, ep_num: int) -> str:
    import unicodedata
    first_line = trans_text.strip().splitlines()[0] if trans_text else ""
    m = re.search(r"#\s*Tập\s*\d+\s*[:：\-—]\s*(.*)", first_line, re.IGNORECASE)
    if m:
        sub_title = m.group(1).strip()
    else:
        sub_title = re.sub(r"^#+\s*", "", first_line).strip()
    
    s1 = unicodedata.normalize('NFD', sub_title)
    s1 = ''.join(c for c in s1 if unicodedata.category(c) != 'Mn')
    s1 = s1.replace('đ', 'd').replace('Đ', 'D')
    slug = re.sub(r'[^a-zA-Z0-9]+', '_', s1).strip('_').lower()
    slug = slug[:50].rstrip('_')
    if slug:
        return f"chuong_{ep_num}_{slug}.md"
    return f"chuong_{ep_num}.md"

async def generate_chapter_illustration(project: NovelProject, ep_num: int, chapter_text: str, api_key: str, model: str) -> Optional[Path]:
    """Tự động phân tích cảnh cao trào trong chương và sinh tranh minh họa Anime bằng AI Image Generation."""
    console.print(f"\n[bold magenta]🎨 Đang phân tích và khởi tạo tranh minh họa cho Tập {ep_num}...[/bold magenta]")
    
    # Rút trích cảnh ấn tượng nhất bằng AI
    scene_prompt = f"""Hãy đọc trích đoạn chương {ep_num} sau và chọn ra MỘT PHÂN CẢNH ẤN TƯỢNG / CAO TRÀO NHẤT để vẽ tranh minh họa Light Novel.
Trả về định dạng JSON thuần túy:
```json
{{
  "scene_title": "Tên phân cảnh ngắn gọn tiếng Việt",
  "scene_context": "Mô tả bối cảnh và cảm xúc nhân vật trong phân cảnh (khoảng 2-3 câu tiếng Việt)",
  "characters": ["Tên nhân vật 1", "Tên nhân vật 2"],
  "english_image_prompt": "Chi tiết prompt tiếng Anh mô tả nhân vật, trang phục, góc nhìn, ánh sáng, anime light novel illustration style, masterpiece, highly detailed"
}}
```

Trích đoạn chương:
{chapter_text[:3500]}
"""
    try:
        raw_res = await call_gemini_api(api_key, model, "Bạn là Giám đốc Nghệ thuật Light Novel (Art Director).", [{"role": "user", "content": scene_prompt}])
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_res)
        scene_json = json.loads(json_match.group(1) if json_match else raw_res)
    except Exception as e:
        console.print(f"[dim red]Không thể trích xuất phân cảnh AI: {e}[/dim red]")
        return None

    scene_title = scene_json.get("scene_title", f"Phân cảnh Tập {ep_num}")
    scene_context = scene_json.get("scene_context", "")
    chars = scene_json.get("characters", [])
    eng_prompt = scene_json.get("english_image_prompt", "")
    
    if not eng_prompt:
        eng_prompt = f"anime light novel master illustration, dark fantasy, dramatic lighting, detailed scene from chapter {ep_num}"
    
    # Bổ sung style Anime chuẩn chất lượng cao
    final_prompt = f"{eng_prompt}, masterpiece, highly detailed anime visual, light novel color illustration, Makoto Shinkai style lighting, 8k resolution"

    console.print(f"  [bold yellow]🖼️ Phân cảnh được chọn:[/bold yellow] [green]{scene_title}[/green]")
    if scene_context:
        console.print(f"  [dim]💭 {scene_context}[/dim]")

    img_filename = f"tap_{ep_num}_scene.jpg"
    img_path = project.images_dir / img_filename

    cfg = load_config()
    engine = cfg.get("engine", "gemini")
    image_bytes = None

    # 1. Tạo ảnh bằng API Relay Key (gemini-3.1-flash-image - 0.5 credits ~ 5.4s)
    if engine == "relay" and cfg.get("relay_api_key"):
        relay_key = cfg.get("relay_api_key", "").strip()
        base_url = cfg.get("relay_base_url", "https://api.openai.com/v1").strip().rstrip("/")
        if not base_url.endswith("/v1") and not "/images/generations" in base_url:
            img_api_url = f"{base_url}/v1/images/generations" if "/v1" not in base_url else f"{base_url}/images/generations"
        elif base_url.endswith("/v1"):
            img_api_url = f"{base_url}/images/generations"
        img_model = cfg.get("image_model", "gemini-3.1-flash-image")
        payload = {
            "model": img_model,
            "prompt": final_prompt,
            "n": 1,
            "size": "1024x1024"
        }
        headers = {
            "Authorization": f"Bearer {relay_key}",
            "Content-Type": "application/json"
        }

        with console.status(f"[bold cyan]Đang sinh tranh Anime với {img_model} (API Key)...[/bold cyan]", spinner="dots"):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(img_api_url, json=payload, headers=headers)
                    if resp.status_code == 200:
                        res_json = resp.json()
                        data_arr = res_json.get("data", [])
                        if data_arr:
                            item = data_arr[0]
                            if "b64_json" in item and item["b64_json"]:
                                image_bytes = base64.b64decode(item["b64_json"])
                            elif "url" in item and item["url"]:
                                img_fetch = await client.get(item["url"], timeout=30.0)
                                if img_fetch.status_code == 200:
                                    image_bytes = img_fetch.content
            except Exception as e:
                console.print(f"[dim yellow]Lưu ý: Không gọi được endpoint Relay images/generations ({e}), chuyển sang fallback...[/dim yellow]")

    # 2. Fallback sang Pollinations nếu chưa có ảnh
    if not image_bytes:
        encoded_p = urllib.parse.quote(final_prompt)
        seed = int(time.time()) % 1000000
        fallback_url = f"https://image.pollinations.ai/prompt/{encoded_p}?model=flux-anime&width=768&height=1024&nologo=true&seed={seed}"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(fallback_url)
                if resp.status_code == 200 and len(resp.content) > 5000:
                    image_bytes = resp.content
        except Exception:
            pass

    if image_bytes and len(image_bytes) > 2000:
        img_path.write_bytes(image_bytes)
        console.print(f"  [bold green]✓ Đã tạo & lưu tranh minh họa thành công vào: {img_filename}[/bold green]")
        
        # Cập nhật vào gallery.json
        gallery_data = []
        if project.gallery_file.exists():
            try:
                gallery_data = json.loads(project.gallery_file.read_text(encoding="utf-8"))
            except Exception:
                gallery_data = []
        
        # Xóa mục cũ của tập này nếu có
        gallery_data = [item for item in gallery_data if item.get("chapterId") != f"chuong_{ep_num}"]
        
        gallery_data.insert(0, {
            "id": f"art_tap_{ep_num}_{int(time.time())}",
            "chapterId": f"chuong_{ep_num}",
            "badge": f"Tập {ep_num}",
            "title": scene_title,
            "image": f"../{project.name}/images/{img_filename}",
            "context": scene_context,
            "characters": chars,
            "prompt": eng_prompt
        })
        
        project.gallery_file.write_text(json.dumps(gallery_data, indent=2, ensure_ascii=False), encoding="utf-8")
        return img_path
    else:
        console.print(f"  [dim red]Không thể tạo tranh minh họa cho Tập {ep_num}.[/dim red]")
        return None

def global_term_refactor(project: NovelProject):
    console.print(Panel(
        f"[bold yellow]🔄 CÔNG CỤ ĐỔI THUẬT NGỮ / SỬA TÊN NHÂN VẬT TOÀN BỘ TRUYỆN[/bold yellow]\n"
        f"[dim]Bộ truyện: {project.name} • Tự động quét và thay thế chính xác trong tất cả file translated/ và glossary/[/dim]",
        border_style="yellow"
    ))

    console.print("[dim]Ví dụ: Đổi 'Koutarou' thành 'Kotarou', hoặc 'Lôi Đình Kiếm' thành 'Tử Lôi Ma Kiếm'[/dim]")
    old_term = Prompt.ask("\n👉 [bold red]Nhập thuật ngữ / tên cũ cần thay thế (hoặc '0' để quay lại)[/bold red]").strip()
    if not old_term or old_term in ["0", "q"]:
        return 0

    new_term = Prompt.ask(f"👉 [bold green]Nhập thuật ngữ / tên mới thay thế cho '{old_term}'[/bold green]").strip()
    if not new_term:
        console.print("[yellow]Từ khóa mới rỗng, đã hủy thao tác.[/yellow]")
        return 0

    all_files = list(project.trans_dir.glob("chuong_*.*"))
    if project.glossary_dir.exists():
        all_files.extend(list(project.glossary_dir.glob("*.md")))
    if project.style_guide_file.exists():
        all_files.append(project.style_guide_file)

    match_count = 0
    files_to_modify = []

    for f in all_files:
        try:
            content = f.read_text(encoding="utf-8")
            c = content.count(old_term)
            if c > 0:
                match_count += c
                files_to_modify.append((f, content, c))
        except Exception:
            pass

    if match_count == 0:
        console.print(f"\n[yellow]🔍 Không tìm thấy bất kỳ sự xuất hiện nào của '{old_term}' trong các file của bộ truyện.[/yellow]")
        return 0

    console.print(f"\n🔍 [bold yellow]Tìm thấy {match_count} lần xuất hiện của '{old_term}' trong {len(files_to_modify)} file.[/bold yellow]")
    confirm = ask_yes_no(f"Bạn có chắc chắn muốn thay thế toàn bộ thành '{new_term}' không?", default_yes=True)
    if not confirm:
        console.print("[yellow]Đã hủy thao tác thay thế.[/yellow]")
        return 0

    modified_files_count = 0
    for f, content, c in files_to_modify:
        new_content = content.replace(old_term, new_term)
        f.write_text(new_content, encoding="utf-8")
        modified_files_count += 1

    console.print(f"\n[bold green]✅ ĐÃ HOÀN TẤT: Đã thay thế thành công {match_count} vị trí trong {modified_files_count} file![/bold green]\n")
    project.append_project_log("Refactor", f"Thay thế toàn cục `{old_term}` ➔ `{new_term}` ({match_count} vị trí trong {modified_files_count} file)")
    return modified_files_count

async def translate_chapter_interactive(project: NovelProject, raw_item: RawChapterInfo, api_key: str, model: str):
    ep_num = raw_item.story_ep
    raw_path = raw_item.path

    console.print(Panel(
        f"[bold green]📖 ĐANG DỊCH TẬP {ep_num}: {raw_item.raw_title}[/bold green]\n"
        f"[dim]File raw: {raw_path.name} • Model: {model} • Dự án: {project.name}[/dim]",
        border_style="green"
    ))

    raw_content = raw_path.read_text(encoding="utf-8").strip()
    system_prompt = build_system_prompt(project, raw_content)

    messages = [
        {"role": "user", "content": f"Dịch chương Light Novel sau sang tiếng Việt chuẩn văn học, mượt mà và trích xuất thực thể mới:\n\n{raw_content}"}
    ]

    with console.status(f"[bold cyan]Đang gửi yêu cầu dịch Tập {ep_num} tới Gemini AI...[/bold cyan]", spinner="dots"):
        start_time = time.time()
        try:
            full_response = await call_gemini_api(api_key, model, system_prompt, messages)
            translated_text, extracted_data = parse_ai_response(full_response)
            translated_text = project.sanitize_translation_text(translated_text)
            duration = time.time() - start_time
            rem, total_lim = increment_request_count()
            console.print(f"[bold green]✅ Đã dịch xong! (Thời gian: {duration:.1f}s | Còn lại: {rem}/{total_lim} lượt)[/bold green]")
        except Exception as e:
            console.print(f"[bold red]❌ Lỗi: {e}[/bold red]")
            return

    # Cập nhật glossary
    project.auto_update_glossary(extracted_data, ep_num)
    messages.append({"role": "model", "content": translated_text})

    while True:
        console.print(Panel(translated_text[:1000] + "\n[dim]... (Xem trước 1000 ký tự) ...[/dim]", title="Bản dịch"))
        console.print("\n[bold yellow]TÙY CHỌN:[/bold yellow] [1] Lưu & Thoát [2] Lưu & Tạo Tranh AI [3] Yêu cầu chỉnh sửa [4] Thêm Glossary [5] Dịch lại [0] Hủy")
        choice = Prompt.ask("Chọn", choices=["0", "1", "2", "3", "4", "5"], default="1")

        if choice in ["1", "2"]:
            filename = get_clean_slug(translated_text, ep_num)
            out_file = project.trans_dir / filename
            out_file.write_text(translated_text, encoding="utf-8")
            project.append_project_log("Translated", f"Dịch hoàn tất **Tập {ep_num}** ({len(translated_text.split())} từ ➔ `{filename}`)")
            console.print(f"[bold green]🎉 Đã lưu bản dịch thành công vào: {out_file.name}[/bold green]")

            if choice == "2":
                await generate_chapter_illustration(project, ep_num, translated_text, api_key, model)
            break

        elif choice == "3":
            feedback = Prompt.ask("\n👉 [bold cyan]Nhập yêu cầu tinh chỉnh (Ví dụ: 'Hãy đổi xưng hô Momokawa thành tôi - cậu, dịch mượt mà hơn')[/bold cyan]")
            if not feedback.strip():
                continue
            
            messages.append({"role": "user", "content": f"Hãy chỉnh sửa lại bản dịch trên theo yêu cầu sau:\n{feedback}\n\nĐảm bảo vẫn giữ nguyên định dạng và phân cách === EXTRACTED_GLOSSARY === nếu có thực thể mới."})
            
            with console.status("[bold cyan]Gemini đang tinh chỉnh lại bản dịch theo góp ý của bạn...[/bold cyan]", spinner="dots"):
                try:
                    full_response = await call_gemini_api(api_key, model, system_prompt, messages)
                    translated_text, extracted_data = parse_ai_response(full_response)
                    rem, total_lim = increment_request_count()
                    project.auto_update_glossary(extracted_data, ep_num)
                    console.print(f"[bold green]✅ Đã tinh chỉnh xong bản thảo mới![/bold green] (Còn lại: {rem}/{total_lim} lượt)")
                except Exception as e:
                    console.print(f"[bold red]❌ Lỗi: {e}[/bold red]")

        elif choice == "4":
            orig = Prompt.ask("Nhập từ gốc tiếng Nhật").strip()
            trans = Prompt.ask("Nhập bản dịch tiếng Việt").strip()
            note = Prompt.ask("Ghi chú (tùy chọn)", default="").strip()
            if orig and trans:
                project.add_term_to_glossary(orig, trans, note=note)
                project.append_project_log("Glossary (Thủ Công)", f"Thêm thuật ngữ: `{trans}` (`{orig}`)")
                console.print(f"[bold green]✅ Đã thêm '{trans} ({orig})' vào terms.md![/bold green]")
                system_prompt = build_system_prompt(project)

        elif choice == "5":
            messages = [
                {"role": "user", "content": f"Dịch lại chương Light Novel sau sang tiếng Việt chuẩn văn học, mượt mà:\n\n{raw_content}"}
            ]
            with console.status("[bold cyan]Đang dịch lại từ đầu...[/bold cyan]", spinner="dots"):
                full_response = await call_gemini_api(api_key, model, system_prompt, messages)
                translated_text, extracted_data = parse_ai_response(full_response)
                rem, total_lim = increment_request_count()
                console.print(f"[bold green]✅ Đã dịch lại xong![/bold green] (Còn lại: {rem}/{total_lim} lượt)")

        elif choice == "0":
            console.print(f"[yellow]Đã bỏ qua chương {ep_num}.[/yellow]")
            break

async def translate_batch_fast(
    project: NovelProject, 
    targets: List[RawChapterInfo], 
    api_key: str, 
    model: str, 
    auto_gen_art: bool = False,
    concurrency: int = 2
):
    total = len(targets)
    console.print(f"\n[bold green]🚀 Bắt đầu dịch siêu tốc {total} chương cho bộ [{project.name}] với {concurrency} luồng song song...[/bold green]\n")

    semaphore = asyncio.Semaphore(concurrency)
    glossary_lock = asyncio.Lock()
    
    success_count = 0
    total_new_chars = 0
    total_new_terms = 0
    total_new_rules = 0

    global ACTIVE_PROGRESS
    with Progress(
        TextColumn("[bold cyan]⚡ {task.description}[/bold cyan]"),
        BarColumn(bar_width=30, style="cyan", complete_style="bold green", finished_style="bold green"),
        TextColumn("[bold yellow]{task.percentage:>3.0f}%[/bold yellow]"),
        TextColumn("• [dim]({task.completed}/{task.total} tập)[/dim]"),
        TextColumn("• [magenta]Đã chạy: [/magenta]"),
        TimeElapsedColumn(),
        TextColumn("• [yellow]Còn lại: [/yellow]"),
        TimeRemainingColumn(),
        console=console,
        transient=False
    ) as progress:
        ACTIVE_PROGRESS = progress
        try:
            main_task = progress.add_task(f"Dịch {project.name}", total=total)

            async def translate_worker(raw_item: RawChapterInfo, index: int):
                nonlocal success_count, total_new_chars, total_new_terms, total_new_rules
                ep_num = raw_item.story_ep
                raw_path = raw_item.path

                # Giãn cách thông minh giữa các luồng để không dồn cục gây quá tải 15 RPM
                if index > 0 and concurrency > 1:
                    await asyncio.sleep(min(index * 2.0, 4.0))

                async with semaphore:
                    try:
                        raw_content = raw_path.read_text(encoding="utf-8").strip()
                        
                        async with glossary_lock:
                            system_prompt = build_system_prompt(project, raw_content)
                        
                        messages = [
                            {"role": "user", "content": f"Dịch chương Light Novel sau sang tiếng Việt chuẩn văn học, mượt mà và trích xuất thực thể mới:\n\n{raw_content}"}
                        ]

                        start_t = time.time()
                        full_response = await call_gemini_api(api_key, model, system_prompt, messages)
                        trans_text, extracted_data = parse_ai_response(full_response)
                        trans_text = project.sanitize_translation_text(trans_text)
                        duration = time.time() - start_t

                        # Lưu file bản dịch
                        filename = get_clean_slug(trans_text, ep_num)
                        out_file = project.trans_dir / filename
                        out_file.write_text(trans_text, encoding="utf-8")
                        project.append_project_log("Translated", f"Dịch hoàn tất **Tập {ep_num}** ({len(trans_text.split())} từ ➔ `{filename}`)")

                        # Ghi glossary & style guide với Lock an toàn
                        async with glossary_lock:
                            counts = project.auto_update_glossary(extracted_data, ep_num)
                            total_new_chars += counts.get("characters", 0)
                            total_new_terms += counts.get("terms", 0)
                            total_new_rules += counts.get("style_rules", 0)
                            rem, total_lim = increment_request_count()
                            success_count += 1

                        addons = []
                        if counts.get("characters", 0) > 0: addons.append(f"+{counts['characters']} nhân vật")
                        if counts.get("terms", 0) > 0: addons.append(f"+{counts['terms']} thuật ngữ")
                        if counts.get("style_rules", 0) > 0: addons.append(f"+{counts['style_rules']} style")
                        addon_str = f" [magenta][{', '.join(addons)}][/magenta]" if addons else ""

                        progress.console.print(
                            f"  [bold green]✓ Tập {ep_num}[/bold green] ({duration:.1f}s | {len(trans_text.split())} từ | Còn: {rem}/{total_lim}){addon_str}"
                        )

                        if auto_gen_art:
                            await generate_chapter_illustration(project, ep_num, trans_text, api_key, model)

                    except Exception as e:
                        progress.console.print(f"  [bold red]✗ Lỗi Tập {ep_num}: {e}[/bold red]")
                    finally:
                        progress.advance(main_task)

            tasks = [translate_worker(item, i) for i, item in enumerate(targets)]
            await asyncio.gather(*tasks)
        finally:
            ACTIVE_PROGRESS = None

    ensure_utf8_console()
    console.print(f"\n[bold green]🎉 HOÀN TẤT PHA 1: Đã dịch thành công {success_count}/{total} chương![/bold green]")
    console.print(f"📊 [dim]Tự động học được: +{total_new_chars} Nhân vật, +{total_new_terms} Thuật ngữ, +{total_new_rules} Quy tắc xưng hô[/dim]")

    # PHA 2: TỰ ĐỘNG SO SÁNH & CHUẨN HÓA THUẬT NGỮ (AUTO-RECONCILE)
    with console.status("[bold cyan]🔄 Pha 2: Đang tự động rà soát & đồng bộ Glossary cho các tập vừa dịch...[/bold cyan]", spinner="dots"):
        reconciled = project.reconcile_batch_glossary(targets)

    if reconciled > 0:
        console.print(f"✨ [bold yellow]Đã tự động rà soát & chuẩn hóa {reconciled} vị trí thuật ngữ để khớp 100% với Glossary![/bold yellow]\n")
    else:
        console.print(f"✨ [bold green]Độ đồng nhất thuật ngữ & nhân vật đạt 100% hoàn hảo![/bold green]\n")

# ==============================================================================
# MENU & GIAO DIỆN CHÍNH
# ==============================================================================

async def select_project(projects: List[NovelProject], force_menu: bool = False) -> Optional[NovelProject]:
    while True:
        projects = scan_all_projects()
        if not projects:
            p = NovelProject(ROOT_DIR / "Chu_Thuat_Su_Dung_Gia")
            projects = [p]

        console.print("\n[bold cyan]📂 QUẢN LÝ DỰ ÁN NOVEL & HỆ THỐNG AI (HUB):[/bold cyan]")
        console.print("  [[bold green]1[/bold green]] 📚 [bold yellow]Danh Sách Bộ Novel[/bold yellow] [dim](Chọn bộ truyện đang có trong máy)[/dim]")
        console.print("  [[bold green]2[/bold green]] ➕ [bold green]Tạo dự án Novel mới[/bold green]")
        console.print("  [[bold green]3[/bold green]] 🗑️ [bold red]Xóa một bộ Novel khỏi máy[/bold red]")
        console.print("  [[bold green]4[/bold green]] 🌐 [bold magenta]Dịch Lấy Từ API (LLMGate Relay / Gemini AI)[/bold magenta]")
        console.print("  [[bold white]0[/bold white]] 🔙 [dim]Vào bộ truyện mặc định / Tiếp tục[/dim]")

        hub_choice = Prompt.ask("\n[bold yellow]Chọn chức năng (1: Danh sách truyện | 2: Tạo mới | 3: Xóa | 4: Dịch API | 0: Tiếp tục)[/bold yellow]", default="1").strip()

        if hub_choice == "1":
            console.print("\n[bold cyan]📚 DANH SÁCH BỘ NOVEL TRONG MÁY:[/bold cyan]")
            for i, p in enumerate(projects, 1):
                raw_count = len(p.list_raw_chapters())
                trans_count = len(p.list_translated_chapters())
                console.print(f"  [[bold green]{i}[/bold green]] [yellow]{p.name}[/yellow] (Raw: {raw_count} | Đã dịch: {trans_count})")
            console.print("  [[bold white]0[/bold white]] 🔙 [dim]Quay lại[/dim]")

            sel_idx = Prompt.ask("\n[bold yellow]Chọn bộ truyện muốn làm việc[/bold yellow]", choices=[str(i) for i in range(len(projects) + 1)], default="1")
            if sel_idx == "0":
                continue
            return projects[int(sel_idx) - 1]

        elif hub_choice == "2":
            user_input = Prompt.ask("\n👉 [bold cyan]Dán link Syosetu/Kakuyomu (hoặc nhập tên thư mục truyện mới)[/bold cyan]").strip()
            if not user_input or user_input in ["0", "q", "exit"]:
                continue

            is_url = "syosetu.com" in user_input or "kakuyomu.jp" in user_input or re.match(r"^n\d{4}[a-z]{1,2}$", user_input.lower())

            if is_url:
                novel_code = extract_novel_code(user_input)
                syosetu_novel = SyosetuNovel(novel_code)
                ok = False
                with console.status(f"[bold cyan]🔍 Đang kết nối Syosetu lấy thông tin truyện [{novel_code}]...[/bold cyan]", spinner="dots"):
                    try:
                        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                            ok = await syosetu_novel.fetch_novel_info_and_toc(client)
                    except Exception as e:
                        console.print(f"[bold red]❌ Lỗi kết nối Syosetu: {e}[/bold red]")
                        ok = False

                if ok and syosetu_novel.episodes:
                    with console.status("[bold cyan]🤖 AI đang dịch tiêu đề truyện sang tiếng Việt (Model Free 0đ)...[/bold cyan]", spinner="dots"):
                        vi_title = await translate_novel_title_free(syosetu_novel.title)
                    
                    default_folder = vi_title or clean_filename(syosetu_novel.title) or f"Novel_{novel_code}"

                    console.print(f"\n[bold green]📖 Tên gốc (JP):[/bold green] [dim]{syosetu_novel.title}[/dim]")
                    if vi_title:
                        console.print(f"🇻🇳 [bold green]Tên tiếng Việt (AI dịch):[/bold green] [bold yellow]{vi_title}[/bold yellow]")
                    console.print(f"✍️ [bold cyan]Tác giả:[/bold cyan] {syosetu_novel.author or 'Chưa rõ'}")
                    console.print(f"📊 [bold magenta]Tổng số tập trên mạng:[/bold magenta] {len(syosetu_novel.episodes)} tập")

                    folder_name = Prompt.ask("\n📁 [bold yellow]Tên thư mục dự án (Tiếng Việt có dấu - Nhấn Enter để đồng ý)[/bold yellow]", default=default_folder).strip()
                    folder_name = re.sub(r'[\\/*?:"<>|]', '', folder_name).strip()
                    if not folder_name:
                        folder_name = f"Novel_{novel_code}"
                    
                    new_path = ROOT_DIR / folder_name
                    new_proj = NovelProject(new_path)

                    console.print(f"\n[bold green]🎉 Đã khởi tạo dự án: [yellow]{folder_name}[/yellow] (Tự động áp dụng Master Ruleset V2.1)![/bold green]")

                    # Hỏi tải toàn bộ raw về luôn
                    ask_scrape = ask_yes_no(f"🚀 Bạn có muốn TỰ ĐỘNG TẢI TOÀN BỘ {len(syosetu_novel.episodes)} tập raw về máy ngay không?", default_yes=True)
                    if ask_scrape:
                        threads = IntPrompt.ask("⚡ Số luồng tải song song (1 đến 16 luồng)", default=8)
                        threads = max(1, min(16, threads))
                        await run_batch_scrape(syosetu_novel, syosetu_novel.episodes, new_proj.raw_dir, max_concurrency=threads)
                    
                    return new_proj
                else:
                    # TUYỆT ĐỐI KHÔNG DÙNG LINK LÀM TÊN THƯ MỤC!
                    console.print(f"[bold yellow]⚠️ Không thể tự động cào thông tin từ link này.[/bold yellow]")
                    folder_name = Prompt.ask("\n👉 [bold cyan]Vui lòng nhập Tên Tiếng Việt cho bộ truyện mới này[/bold cyan]", default=f"Novel_{novel_code}").strip()
                    folder_name = re.sub(r'[\\/*?:"<>|]', '', folder_name).strip() or f"Novel_{novel_code}"
                    new_path = ROOT_DIR / folder_name
                    new_proj = NovelProject(new_path)
                    console.print(f"\n[bold green]🎉 Đã khởi tạo dự án: [yellow]{folder_name}[/yellow]![/bold green]")
                    return new_proj
            else:
                folder_name = re.sub(r'[\\/*?:"<>|]', '', user_input).strip()
                new_path = ROOT_DIR / folder_name
                new_proj = NovelProject(new_path)
                console.print(f"\n[bold green]🎉 Đã khởi tạo thành công dự án mới: [yellow]{folder_name}[/yellow] (Chuẩn Master Ruleset V2.1)![/bold green]")
                return new_proj

        elif hub_choice == "3":
            console.print("\n[bold red]🗑️ CHỌN BỘ NOVEL CẦN XÓA:[/bold red]")
            for i, p in enumerate(projects, 1):
                console.print(f"  [[bold red]{i}[/bold red]] [yellow]{p.name}[/yellow] ({p.path})")
            console.print(f"  [[bold white]0[/bold white]] [dim]Hủy bỏ, không xóa[/dim]")
            
            del_choice = Prompt.ask("Nhập số thứ tự bộ truyện muốn xóa", default="0").strip()
            if del_choice in ["0", "q", "exit"]:
                continue
            
            try:
                del_idx = int(del_choice) - 1
                if 0 <= del_idx < len(projects):
                    target_p = projects[del_idx]
                    confirm_del = ask_yes_no(
                        f"⚠️ [bold red]CẢNH BÁO NGUY HIỂM:[/bold red] Bạn có CHẮC CHẮN muốn XÓA VĨNH VIỄN toàn bộ dự án '[yellow]{target_p.name}[/yellow]'?\n"
                        f"(Toàn bộ file raw, bản dịch và glossary trong {target_p.path} sẽ bị xóa sạch!)",
                        default_yes=False
                    )
                    
                    if confirm_del:
                        shutil.rmtree(target_p.path, ignore_errors=True)
                        console.print(f"\n[bold green]✅ Đã xóa vĩnh viễn dự án: {target_p.name}![/bold green]")
                        sync_web_reader("")
                    else:
                        console.print("\n[yellow]Đã hủy thao tác xóa.[/yellow]")
            except Exception as e:
                console.print(f"[bold red]❌ Lỗi khi xóa: {e}[/bold red]")
            
            continue

        elif hub_choice == "4":
            cfg = load_config()
            engine = cfg.get("engine", "gemini")
            model = cfg.get("relay_model" if engine == "relay" else "selected_model", "gemini-3-flash")
            
            console.print("\n[bold cyan]🌐 DỊCH LẤY TỪ API / CÀI ĐẶT NHÀ CUNG CẤP:[/bold cyan]")
            console.print("  [1] ⚡ [bold green]Dịch nhanh một đoạn văn bản (Quick API Translate)[/bold green]")
            console.print(f"  [2] ⚙️ [bold yellow]Cài đặt Nhà Cung Cấp & API Key[/bold yellow] [dim](Hiện tại: {engine.upper()} - {model})[/dim]")
            console.print("  [0] 🔙 [dim]Quay lại[/dim]")
            
            sub_api = Prompt.ask("Lựa chọn", choices=["0", "1", "2"], default="1")
            if sub_api == "1":
                console.print("\n[bold yellow]✍️ Dán văn bản tiếng Nhật cần dịch (hoặc gõ 'q' để hủy):[/bold yellow]")
                console.print("[dim](Dán xong nhấn Enter 2 lần để bắt đầu dịch)[/dim]")
                lines = []
                while True:
                    try:
                        line = input()
                        if line.strip().lower() == "q" and not lines:
                            break
                        if not line and lines and lines[-1] == "":
                            break
                        lines.append(line)
                    except EOFError:
                        break
                
                raw_input_text = "\n".join(lines).strip()
                if raw_input_text and raw_input_text.lower() != "q":
                    _, api_k, cur_m = ensure_api_key(cfg)
                    with console.status(f"[bold cyan]Đang gọi API ({engine.upper()}: {cur_m}) dịch thuật...[/bold cyan]", spinner="dots"):
                        try:
                            sys_p = "Bạn là dịch giả Light Novel tiếng Nhật sang tiếng Việt hàng đầu. Hãy dịch chính xác, mượt mà và tự nhiên."
                            res_text = await call_gemini_api(api_k, cur_m, sys_p, [{"role": "user", "content": "Hãy dịch đoạn văn sau sang tiếng Việt:\n\n" + raw_input_text}])
                            console.print("\n[bold green]🇻🇳 KẾT QUẢ BẢN DỊCH TỪ API:[/bold green]")
                            console.print(Panel(res_text, border_style="green"))
                        except Exception as e:
                            console.print(f"[bold red]❌ Lỗi khi gọi API: {e}[/bold red]")
                    pause_before_menu()
            elif sub_api == "2":
                console.print("\n[bold cyan]CÀI ĐẶT NHÀ CUNG CẤP & API KEY:[/bold cyan]")
                console.print("  [1] 🤖 Google Gemini Trực Tiếp (Free Tier)")
                console.print("  [2] 🌐 API Relay Trả Phí (LLMGate Relay, DeepSeek, Gemini 3 Flash...)")
                console.print("  [3] 📝 Đổi Model Dịch Thuật")
                console.print("  [0] 🔙 Quay lại")
                e_sel = Prompt.ask("Chọn", choices=["0", "1", "2", "3"], default="1" if engine == "gemini" else "2")
                if e_sel == "1":
                    cfg["engine"] = "gemini"
                    save_config(cfg)
                    console.print("[bold green]✅ Đã chuyển sang Google Gemini Free![/bold green]")
                elif e_sel == "2":
                    cfg["engine"] = "relay"
                    new_base = Prompt.ask("Nhập Base URL của Relay", default=cfg.get("relay_base_url", "https://llmgate.app/v1")).strip()
                    cfg["relay_base_url"] = new_base
                    new_k = Prompt.ask("Nhập Relay API Key (sk-...)", default=cfg.get("relay_api_key", "")).strip()
                    cfg["relay_api_key"] = new_k
                    save_config(cfg)
                    console.print("[bold green]✅ Đã lưu cấu hình Relay API thành công![/bold green]")
                elif e_sel == "3":
                    if engine == "relay":
                        console.print("\n[bold cyan]Chọn Model Dịch Relay (LLMGate):[/bold cyan]")
                        for i, (m_id, m_name) in enumerate(AVAILABLE_RELAY_MODELS, 1):
                            console.print(f"  [{i}] {m_name}")
                        m_choice = Prompt.ask("Chọn model", choices=[str(i) for i in range(1, len(AVAILABLE_RELAY_MODELS) + 1)], default="1")
                        selected_m = AVAILABLE_RELAY_MODELS[int(m_choice) - 1][0]
                        cfg["relay_model"] = selected_m
                    else:
                        console.print("\n[bold cyan]Chọn Model Gemini Dịch Thuật:[/bold cyan]")
                        for i, (m_id, m_name) in enumerate(AVAILABLE_GEMINI_MODELS, 1):
                            console.print(f"  [{i}] {m_name}")
                        m_choice = Prompt.ask("Chọn model", choices=[str(i) for i in range(1, len(AVAILABLE_GEMINI_MODELS) + 1)], default="1")
                        selected_m = AVAILABLE_GEMINI_MODELS[int(m_choice) - 1][0]
                        cfg["selected_model"] = selected_m
                    save_config(cfg)
                    console.print(f"[bold green]✅ Đã đổi Model Dịch sang: {selected_m}[/bold green]")
                pause_before_menu()
            continue

        elif hub_choice == "0":
            return projects[0] if projects else None

async def interactive_raw_downloader(project: NovelProject, all_projects: List[NovelProject], api_key: str, model: str) -> Optional[NovelProject]:
    """Tích hợp cào raw Syosetu / Web Novel trực tiếp vào Studio (Bộ cào nội bộ)."""
    console.print("\n[bold cyan]📥 CÔNG CỤ TẢI RAW TIẾNG NHẬT TỰ ĐỘNG (SYOSETU / KAKUYOMU):[/bold cyan]")
    console.print(f"  [1] 🔄 [bold green]Cập nhật chương mới nhất cho bộ hiện tại[/bold green] ([yellow]{project.name}[/yellow])")
    console.print(f"  [2] ➕ [bold yellow]Tải bộ Light Novel mới hoàn toàn[/bold yellow] (Từ Link hoặc Mã truyện)")
    console.print(f"  [0] 🔙 [dim]Quay lại Menu chính[/dim]")

    sub_choice = Prompt.ask("\nLựa chọn của bạn", choices=["0", "1", "2"], default="1")
    if sub_choice == "0":
        return None

    target_novel_code = ""
    target_project = project

    if sub_choice == "1":
        default_code = "n1132dk" if "chu_thuat" in project.name.lower() else ""
        target_novel_code = Prompt.ask("Nhập Mã truyện Syosetu hoặc URL (Ví dụ: n1132dk hoặc https://ncode.syosetu.com/n1132dk/)", default=default_code or "n1132dk").strip()
    else:
        url_in = Prompt.ask("Nhập URL hoặc Mã truyện Syosetu (Ví dụ: https://ncode.syosetu.com/n1132dk/ hoặc n1132dk)").strip()
        target_novel_code = extract_novel_code(url_in)
        if not target_novel_code:
            console.print("[bold red]❌ Mã truyện hoặc URL không hợp lệ![/bold red]")
            return None

    novel_code = extract_novel_code(target_novel_code)
    novel = SyosetuNovel(novel_code)

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        ok = await novel.fetch_novel_info_and_toc(client)
        if not ok or not novel.episodes:
            console.print(f"[bold red]❌ Không thể lấy mục lục truyện ({novel_code}) từ Syosetu![/bold red]")
            return None

    console.print(f"\n[bold green]📖 Tên truyện:[/bold green] [yellow]{novel.title or novel_code}[/yellow]")
    console.print(f"✍️ [bold cyan]Tác giả:[/bold cyan] {novel.author or 'Chưa rõ'}")
    console.print(f"📊 [bold magenta]Tổng số tập trên Syosetu:[/bold magenta] {len(novel.episodes)} tập")

    # Xác định thư mục lưu raw
    if sub_choice == "1":
        output_dir = project.raw_dir
    else:
        with console.status("[bold cyan]🤖 AI đang dịch tiêu đề truyện sang tiếng Việt (Model Free 0đ)...[/bold cyan]", spinner="dots"):
            vi_title = await translate_novel_title_free(novel.title)

        default_folder = vi_title or clean_filename(novel.title) or f"Novel_{novel_code}"
        if vi_title:
            console.print(f"🇻🇳 [bold green]Tên tiếng Việt (AI dịch):[/bold green] [bold yellow]{vi_title}[/bold yellow]")

        folder_name = Prompt.ask("\n📁 [bold yellow]Tên thư mục dự án (Tiếng Việt có dấu - Nhấn Enter để đồng ý)[/bold yellow]", default=default_folder).strip()
        folder_name = re.sub(r'[\\/*?:"<>|]', '', folder_name).strip()
        new_path = ROOT_DIR / folder_name
        target_project = NovelProject(new_path)
        output_dir = target_project.raw_dir
        if not any(p.name == target_project.name for p in all_projects):
            all_projects.append(target_project)

    output_dir.mkdir(parents=True, exist_ok=True)
    existing_eps = novel.get_existing_chapters(output_dir)

    unscraped = [e for e in novel.episodes if e["ep"] not in existing_eps]

    if not unscraped:
        console.print(f"\n[bold green]🎉 Tất cả {len(novel.episodes)} chương trên Syosetu đã được tải về đầy đủ trong {output_dir}![/bold green]")
        return target_project

    console.print(f"\n📁 Đã có sẵn: [cyan]{len(existing_eps)}[/cyan] tập. Còn thiếu: [bold yellow]{len(unscraped)}[/bold yellow] tập mới.")
    
    console.print("\nChọn phạm vi tải:")
    console.print(f"  [1] ⚡ [bold green]Tải toàn bộ {len(unscraped)} tập còn thiếu[/bold green] (Khuyên dùng)")
    console.print(f"  [2] 🔢 [bold cyan]Tải theo khoảng tập chỉ định[/bold cyan]")
    
    range_choice = Prompt.ask("Lựa chọn", choices=["1", "2"], default="1")
    
    if range_choice == "1":
        targets = unscraped
    else:
        st = IntPrompt.ask("Tập bắt đầu", default=unscraped[0]["ep"])
        en = IntPrompt.ask("Tập kết thúc", default=unscraped[-1]["ep"])
        targets = [e for e in unscraped if st <= e["ep"] <= en]

    if not targets:
        console.print("[yellow]Không có tập nào để tải.[/yellow]")
        return target_project

    threads = IntPrompt.ask("⚡ Số luồng tải song song", default=8)
    threads = max(1, min(16, threads))

    await run_batch_scrape(novel, targets, output_dir, max_concurrency=threads)

    # Hỏi người dùng có muốn dịch luôn các tập vừa tải không
    ask_trans = ask_yes_no(f"🚀 Bạn có muốn bắt đầu Dịch Tự Động {len(targets)} tập vừa tải về ngay không?", default_yes=True)
    if ask_trans:
        raw_items = [c for c in target_project.list_raw_chapters() if any(t["ep"] == c.story_ep or t["ep"] == c.file_ep for t in targets)]
        if raw_items:
            default_conc = 4 if cfg.get("engine") == "relay" else 2
            conc = IntPrompt.ask(f"⚡ Số luồng dịch AI song song (1 đến 8 luồng) (Khuyên dùng: {default_conc})", default=default_conc)
            conc = max(1, min(10, conc))
            auto_art = ask_yes_no("🎨 Tạo tranh minh họa AI luôn không?", default_yes=False)
            await translate_batch_fast(target_project, raw_items, api_key, model, auto_gen_art=auto_art, concurrency=conc)
            sync_web_reader(target_project.name)

    return target_project

def pause_before_menu(message: str = "👉 Nhấn phím Enter để quay lại Menu chính..."):
    """Dừng màn hình để người dùng xem trọn vẹn kết quả, chống trôi phím Enter tự động."""
    ensure_utf8_console()
    try:
        if sys.platform == "win32":
            import msvcrt
            while msvcrt.kbhit():
                msvcrt.getch()
    except Exception:
        pass
    
    console.print(f"\n[bold cyan]{message}[/bold cyan]")
    try:
        input()
    except Exception:
        pass

async def main():
    cfg = load_config()
    engine, api_key, model = ensure_api_key(cfg)

    projects = scan_all_projects()
    if not projects:
        p = NovelProject(ROOT_DIR / "Chu_Thuat_Su_Dung_Gia")
        projects = [p]

    project = await select_project(projects)
    if not project:
        project = projects[0]

    while True:
        ensure_utf8_console()
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]🧠 UNIVERSAL MULTI-NOVEL AI TRANSLATOR & ART STUDIO[/bold cyan]\n"
            "[dim]Hỗ trợ Google Gemini & Relay API • Canon Database V3.0 • Sinh Ảnh Anime Tự Động[/dim]",
            border_style="cyan"
        ))

        cfg = load_config()
        engine, api_key, model = ensure_api_key(cfg)
        raw_chapters = project.list_raw_chapters()
        trans_chapters = project.list_translated_chapters()
        rem_today, total_lim = get_remaining_requests()

        img_m = cfg.get("image_model", "gemini-3.1-flash-image")
        engine_label = "🌐 API Relay Trả Phí" if engine == "relay" else "🤖 Google Gemini (Free)"
        lim_str = "Không giới hạn" if engine == "relay" else f"{rem_today}/{total_lim} lượt gọi API hôm nay"

        console.print(f"\n[bold green]📖 Dự án đang chọn:[/bold green] [yellow]{project.name}[/yellow]")
        console.print(f"⚙️ [bold cyan]Hệ thống AI:[/bold cyan] [bold white]{engine_label}[/bold white] • [bold magenta]Dịch:[/bold magenta] [bold yellow]{model}[/bold yellow] • [bold bright_magenta]Tạo Ảnh:[/bold bright_magenta] [bold yellow]{img_m}[/bold yellow] • [dim]{lim_str}[/dim]")
        console.print(f"📊 [dim]Có {len(raw_chapters)} chương raw • Đã dịch {len(trans_chapters)} chương[/dim]")

        if not raw_chapters:
            console.print(f"\n[bold red]⚠️ Thư mục raw của bộ truyện này chưa có file raw nào ({project.raw_dir})![/bold red]")
            console.print("💡 Hãy thả file raw vào thư mục hoặc chọn tính năng [bold yellow][3] Tải Raw Mới[/bold yellow] để tải nhé.")

        # MENU CHÍNH GỌN GÀNG (ĐÃ TẬP TRUNG HOÀN TOÀN VÀO DỊCH THUẬT & MINH HỌA)
        console.print("\n[bold cyan]CHỌN CHỨC NĂNG DỊCH THUẬT & QUẢN LÝ NOVEL:[/bold cyan]")
        console.print("  [bold cyan][1][/bold cyan] 🌐 [bold green]Dịch Truyện AI[/bold green] [dim](Tương tác / Hàng loạt / Theo khoảng tập)[/dim]")
        console.print("  [bold cyan][2][/bold cyan] 🎨 [bold bright_magenta]Tạo Tranh Minh Họa Anime Cho Chương (Gemini Image)[/bold bright_magenta]")
        console.print("  [bold cyan][3][/bold cyan] 📥 [bold green]Tải Raw Mới / Cập Nhật Thêm Chương[/bold green] [dim](Syosetu, Kakuyomu)[/dim]")
        console.print("  [bold cyan][4][/bold cyan] ⚙️ [bold yellow]Cài đặt Hệ Thống AI & Model (Dịch & Tạo Ảnh)[/bold yellow]")
        console.print("  [bold cyan][5][/bold cyan] 📂 [bold yellow]Đổi Bộ Truyện Khác / Quản Lý Dự Án Novel[/bold yellow]")
        console.print("  [bold cyan][0][/bold cyan] ❌ Thoát")

        mode = Prompt.ask("\n[bold yellow]Lựa chọn của bạn[/bold yellow]", choices=["0", "1", "2", "3", "4", "5"], default="1")

        if mode == "0":
            console.print("[yellow]Cảm ơn bạn đã sử dụng chương trình. Tạm biệt![/yellow]")
            break

        elif mode == "1":
            # SUBMENU DỊCH THUẬT AI
            console.print("\n[bold cyan]╔══════════════════════════════════════════════════════════════════════════════╗[/bold cyan]")
            console.print("[bold cyan]║ 🌐 CHỌN CHẾ ĐỘ DỊCH THUẬT AI:                                                ║[/bold cyan]")
            console.print("[bold cyan]╠══════════════════════════════════════════════════════════════════════════════╣[/bold cyan]")
            console.print("  [bold cyan][1][/bold cyan] 💬 [bold green]Dịch Tương Tác & Tinh Chỉnh từng chương[/bold green] [dim](Kèm tùy chọn tạo tranh minh họa)[/dim]")
            console.print("  [bold cyan][2][/bold cyan] 🚀 [bold yellow]Dịch Tự Động Hàng Loạt[/bold yellow] [dim](Dịch liên tục các chương chưa làm & tự cập nhật Canon)[/dim]")
            console.print("  [bold cyan][3][/bold cyan] 🔢 [bold magenta]Dịch Theo Khoảng Chương Chỉ Định[/bold magenta] [dim](Ví dụ: Từ tập 196 đến 205)[/dim]")
            console.print("  [bold cyan][0][/bold cyan] 🔙 [dim]Quay lại Menu Chính[/dim]")
            console.print("[bold cyan]╚══════════════════════════════════════════════════════════════════════════════╝[/bold cyan]")
            
            sub_trans = Prompt.ask("\n[bold yellow]Lựa chọn chế độ dịch[/bold yellow]", choices=["0", "1", "2", "3"], default="1")
            
            if sub_trans == "0":
                continue

            elif sub_trans == "1":
                untranslated = [c for c in raw_chapters if c.story_ep not in trans_chapters]
                default_ep = untranslated[0].story_ep if untranslated else raw_chapters[0].story_ep
                
                target_ep = IntPrompt.ask("\n[bold yellow]Nhập số Tập/Chương muốn dịch (hoặc '0' để quay lại)[/bold yellow]", default=default_ep)
                if target_ep == 0:
                    continue

                target_raw = next((c for c in raw_chapters if c.story_ep == target_ep or c.file_ep == target_ep), None)
                
                if not target_raw:
                    console.print(f"[bold red]❌ Không tìm thấy file raw cho Tập {target_ep} trong {project.raw_dir}![/bold red]")
                    pause_before_menu()
                    continue
                
                if target_raw.story_ep in trans_chapters:
                    console.print(f"[bold yellow]⚠️ Cảnh báo: Tập {target_raw.story_ep} đã có bản dịch sẵn trong thư mục translated/.[/bold yellow]")
                    re_trans = ask_yes_no("Bạn có muốn dịch lại tập này không?", default_yes=True)
                    if not re_trans:
                        continue

                await translate_chapter_interactive(project, target_raw, api_key, model)

                sync = ask_yes_no("Bạn có muốn tự động đồng bộ Web Đọc Truyện ngay không?", default_yes=True)
                if sync:
                    sync_web_reader(project.name)
                pause_before_menu()
                continue

            elif sub_trans == "2":
                untranslated = [c for c in raw_chapters if c.story_ep not in trans_chapters]
                if not untranslated:
                    console.print("[bold green]🎉 Tất cả các file raw trong máy đã được dịch hoàn tất! Không còn tập nào thiếu.[/bold green]")
                    pause_before_menu()
                    continue
                
                console.print(f"🔍 Phát hiện có [bold yellow]{len(untranslated)}[/bold yellow] tập chưa dịch (Từ Tập {untranslated[0].story_ep} đến Tập {untranslated[-1].story_ep}).")
                confirm = ask_yes_no(f"Bạn có muốn dịch toàn bộ {len(untranslated)} tập này ngay không?", default_yes=True)
                if confirm:
                    default_conc = 4 if cfg.get("engine") == "relay" else 2
                    concurrency = IntPrompt.ask(f"⚡ Số luồng dịch song song (1 đến 8 luồng) (Khuyên dùng: {default_conc})", default=default_conc)
                    concurrency = max(1, min(10, concurrency))
                    
                    auto_art = ask_yes_no("🎨 Bạn có muốn tạo luôn Tranh Minh Họa Anime cho từng tập không? (Lưu ý: Thêm ~5s/tập)", default_yes=False)
                    await translate_batch_fast(project, untranslated, api_key, model, auto_gen_art=auto_art, concurrency=concurrency)
                    sync_web_reader(project.name)

                pause_before_menu()
                continue

            elif sub_trans == "3":
                start_ep = IntPrompt.ask("Tập bắt đầu (hoặc '0' để quay lại)", default=raw_chapters[0].story_ep)
                if start_ep == 0:
                    continue
                end_ep = IntPrompt.ask("Tập kết thúc", default=raw_chapters[-1].story_ep)
                targets = [c for c in raw_chapters if start_ep <= c.story_ep <= end_ep]
                
                if not targets:
                    console.print("[yellow]Không tìm thấy tập nào trong khoảng đã chọn.[/yellow]")
                    pause_before_menu()
                    continue
                
                default_conc = 4 if cfg.get("engine") == "relay" else 2
                concurrency = IntPrompt.ask(f"⚡ Số luồng dịch song song (1 đến 8 luồng) (Khuyên dùng: {default_conc})", default=default_conc)
                concurrency = max(1, min(10, concurrency))

                auto_art = ask_yes_no("🎨 Bạn có muốn tạo luôn Tranh Minh Họa Anime cho từng tập không? (Lưu ý: Thêm ~5s/tập)", default_yes=False)
                await translate_batch_fast(project, targets, api_key, model, auto_gen_art=auto_art, concurrency=concurrency)
                sync_web_reader(project.name)

                pause_before_menu()
                continue

        elif mode == "2":
            console.print("\n[bold cyan]🎨 TẠO TRANH MINH HỌA ANIME AI (TAB BỘ SƯU TẬP):[/bold cyan]")
            ep_target = IntPrompt.ask("Nhập số Tập bạn muốn tạo tranh minh họa", default=trans_chapters[-1] if trans_chapters else 196)
            
            trans_file = None
            for f in project.trans_dir.glob(f"chuong_{ep_target}*.md"):
                trans_file = f
                break
            
            if not trans_file:
                console.print(f"[bold red]❌ Không tìm thấy file bản dịch của Tập {ep_target} trong {project.trans_dir}![/bold red]")
                pause_before_menu()
                continue
            
            ch_text = trans_file.read_text(encoding="utf-8")
            await generate_chapter_illustration(project, ep_target, ch_text, api_key, model)
            sync_web_reader(project.name, silent=True)
            pause_before_menu()
            continue

        elif mode == "3":
            new_p = await interactive_raw_downloader(project, projects, api_key, model)
            if new_p:
                project = new_p
            pause_before_menu()
            continue

        elif mode == "4":
            img_m = cfg.get("image_model", "gemini-3.1-flash-image")
            console.print("\n[bold cyan]⚙️ CÀI ĐẶT HỆ THỐNG AI & MÁY CHỦ:[/bold cyan]")
            console.print(f"  [1] 📝 [bold green]Cài đặt Model DỊCH THUẬT[/bold green] [dim](Hiện tại: {model})[/dim]")
            console.print(f"  [2] 🎨 [bold magenta]Cài đặt Model TẠO TRANH MINH HỌA[/bold magenta] [dim](Hiện tại: {img_m})[/dim]")
            console.print("  [3] 🔑 [bold yellow]Cấu hình API Key & Base URL Máy Chủ[/bold yellow]")
            console.print("  [0] 🔙 [dim]Quay lại Menu chính[/dim]")
            
            sub_m8 = Prompt.ask("Lựa chọn của bạn", choices=["0", "1", "2", "3"], default="1")
            
            if sub_m8 == "1":
                console.print("\n[bold cyan]Chọn Nhà Cung Cấp Model Dịch:[/bold cyan]")
                console.print("  [1] 🤖 Google Gemini Trực Tiếp (Free Tier)")
                console.print("  [2] 🌐 API Relay Trả Phí (DeepSeek, Gemini 3 Flash, GPT 5.6, Claude...)")
                p_choice = Prompt.ask("Chọn", choices=["1", "2"], default="1" if engine == "gemini" else "2")
                
                if p_choice == "1":
                    cfg["engine"] = "gemini"
                    console.print("\n[bold cyan]Chọn Model Gemini Dịch Thuật:[/bold cyan]")
                    for i, (m_id, m_name) in enumerate(AVAILABLE_GEMINI_MODELS, 1):
                        console.print(f"  [{i}] {m_name}")
                    m_choice = Prompt.ask("Chọn model", choices=[str(i) for i in range(1, len(AVAILABLE_GEMINI_MODELS) + 1)], default="1")
                    selected_m = AVAILABLE_GEMINI_MODELS[int(m_choice) - 1][0]
                    cfg["selected_model"] = selected_m
                    save_config(cfg)
                    console.print(f"[bold green]✅ Đã đổi Model Dịch sang: {selected_m}[/bold green]")
                else:
                    cfg["engine"] = "relay"
                    console.print("\n[bold cyan]Chọn Model Relay Dịch Thuật:[/bold cyan]")
                    for i, (m_id, m_name) in enumerate(AVAILABLE_RELAY_MODELS, 1):
                        console.print(f"  [{i}] {m_name}")
                    console.print(f"  [{len(AVAILABLE_RELAY_MODELS) + 1}] ✍️ Nhập tên model tùy chỉnh khác...")
                    
                    m_choice = Prompt.ask("Chọn model", choices=[str(i) for i in range(1, len(AVAILABLE_RELAY_MODELS) + 2)], default="1")
                    idx = int(m_choice) - 1
                    if idx < len(AVAILABLE_RELAY_MODELS):
                        selected_m = AVAILABLE_RELAY_MODELS[idx][0]
                    else:
                        selected_m = Prompt.ask("Nhập mã model của bạn (Ví dụ: deepseek-v4-flash-0731)").strip()
                    cfg["relay_model"] = selected_m
                    save_config(cfg)
                    console.print(f"[bold green]✅ Đã đổi Model Dịch sang: {selected_m}[/bold green]")

            elif sub_m8 == "2":
                console.print("\n[bold cyan]🎨 CHỌN MODEL AI TẠO TRANH MINH HỌA:[/bold cyan]")
                for i, (m_id, m_name) in enumerate(AVAILABLE_IMAGE_MODELS, 1):
                    console.print(f"  [{i}] {m_name}")
                console.print(f"  [{len(AVAILABLE_IMAGE_MODELS) + 1}] ✍️ Nhập tên model ảnh tùy chỉnh khác...")
                
                img_choice = Prompt.ask("Chọn model tạo ảnh", choices=[str(i) for i in range(1, len(AVAILABLE_IMAGE_MODELS) + 2)], default="1")
                idx = int(img_choice) - 1
                if idx < len(AVAILABLE_IMAGE_MODELS):
                    sel_img_m = AVAILABLE_IMAGE_MODELS[idx][0]
                else:
                    sel_img_m = Prompt.ask("Nhập mã model tạo ảnh (Ví dụ: gemini-3.1-flash-image)").strip()
                
                cfg["image_model"] = sel_img_m
                save_config(cfg)
                console.print(f"[bold green]✅ Đã đổi Model Tạo Ảnh sang: {sel_img_m}[/bold green]")

            elif sub_m8 == "3":
                console.print("\n[bold cyan]🔑 CẤU HÌNH API KEY & MÁY CHỦ RELAY:[/bold cyan]")
                curr_base = cfg.get("relay_base_url", "")
                new_base = Prompt.ask("Nhập Base URL của Relay", default=curr_base or "https://api.openai.com/v1").strip()
                cfg["relay_base_url"] = new_base

                curr_key = cfg.get("relay_api_key", "")
                new_k = Prompt.ask("Nhập Relay API Key (sk-...)", default=curr_key).strip()
                cfg["relay_api_key"] = new_k

                curr_gemini = cfg.get("gemini_api_key", "")
                change_g = ask_yes_no("Bạn có muốn cập nhật cả Gemini Free API Key không?", default_yes=False)
                if change_g:
                    new_gk = Prompt.ask("Nhập Gemini Free API Key (AIzaSy...)", default=curr_gemini).strip()
                    cfg["gemini_api_key"] = new_gk

                save_config(cfg)
                console.print("[bold green]✅ Đã lưu cấu hình API Key & Máy chủ thành công![/bold green]")

            pause_before_menu()
            continue

        elif mode == "5":
            projects = scan_all_projects()
            selected = await select_project(projects, force_menu=True)
            if selected:
                project = selected
            continue

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Đã hủy tác vụ.[/yellow]")
    except Exception as e:
        console.print(f"\n[bold red]❌ Đã xảy ra lỗi:[/bold red] {e}")
        import traceback
        traceback.print_exc()
        input("\nNhấn Enter để đóng chương trình...")