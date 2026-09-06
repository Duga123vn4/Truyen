# -*- coding: utf-8 -*-
"""
Module Cào Raw Syosetu Nội Bộ (Integrated Syosetu Scraper Engine):
- Tải mục lục (TOC) và siêu dữ liệu (tiêu đề, tác giả, tóm tắt)
- Tải nội dung từng chương raw từ Syosetu
"""
import re
import asyncio
import httpx
from bs4 import BeautifulSoup
from pathlib import Path
from typing import List, Dict, Optional
from rich.console import Console

console = Console()

SCRAPER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8,vi;q=0.7",
    "Cookie": "over18=yes; lineheight=0; fontsize=0; novellayout=0;",
}

def clean_filename(name: str) -> str:
    """Làm sạch tên file/thư mục hợp lệ trên Windows."""
    name = re.sub(r'[\\/*?:"<>|\r\n\t]', '', name)
    name = name.strip().replace(' ', '_')
    if len(name) > 60:
        name = name[:60].rstrip('._')
    return name or "Novel_Raw"

def extract_novel_code(input_str: str) -> str:
    """Trích xuất mã truyện Syosetu từ URL hoặc chuỗi nhập."""
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

    async def fetch_novel_info_and_toc(self, client: httpx.AsyncClient) -> bool:
        """Tải thông tin tổng quan và toàn bộ mục lục của truyện."""
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
                        synopsis_el = soup.select_one("#novel_ex, .p-novel__summary, .p-novel__description")
                        if synopsis_el:
                            self.synopsis = synopsis_el.get_text(strip=True)

                    page_found = False
                    # Extract episode links (supporting both new Syosetu layout: a.p-eplist__subtitle and legacy)
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        m = re.search(rf'/{self.novel_code}/(\d+)/', href)
                        if m:
                            ep_num = int(m.group(1))
                            ep_title = a.get_text(strip=True)
                            if not any(e["ep"] == ep_num for e in self.episodes):
                                self.episodes.append({
                                    "ep": ep_num,
                                    "title": ep_title or f"Tập {ep_num}",
                                    "url": f"https://ncode.syosetu.com/{self.novel_code}/{ep_num}/"
                                })
                                page_found = True

                    # Fallback for short stories (短編) that have no episode list
                    if page == 1 and not self.episodes:
                        body_el = soup.select_one(".p-novel__body, #novel_honbun, .js-novel-text")
                        if body_el:
                            self.episodes.append({
                                "ep": 1,
                                "title": self.title or "Toàn văn",
                                "url": self.base_url
                            })
                            break

                    if not page_found:
                        break

                    next_link = soup.select_one(".c-pager__item--next, a[rel='next'], a.c-pager__next")
                    if not next_link:
                        break
                    page += 1
                    await asyncio.sleep(0.2)
                except Exception as e:
                    console.print(f"[yellow]⚠️ Lỗi khi tải trang {page}: {e}[/yellow]")
                    break

        return len(self.episodes) > 0

    async def fetch_chapter_content(self, client: httpx.AsyncClient, ep_num: int) -> Optional[str]:
        """Tải toàn bộ nội dung thô của một chương."""
        url = None
        for ep in self.episodes:
            if ep.get("ep") == ep_num:
                url = ep.get("url")
                break
        if not url:
            url = f"https://ncode.syosetu.com/{self.novel_code}/{ep_num}/"

        try:
            res = await client.get(url, headers=SCRAPER_HEADERS, timeout=15.0)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                body = soup.select_one(".p-novel__body, #novel_honbun, .js-novel-text")
                if body:
                    p_tags = body.find_all("p")
                    if p_tags:
                        lines = [p.get_text() for p in p_tags]
                    else:
                        lines = [p.get_text() for p in body.find_all(["p", "div"])]
                    if not lines:
                        lines = body.get_text().splitlines()
                    return "\n".join(lines).strip()
        except Exception:
            pass
        return None
