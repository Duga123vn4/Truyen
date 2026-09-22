# -*- coding: utf-8 -*-
"""
Module Cào Raw Kakuyomu Nội Bộ (Integrated Kakuyomu Scraper Engine):
- Tải mục lục (TOC) và siêu dữ liệu (tiêu đề, tác giả, tóm tắt)
- Tải nội dung từng chương raw từ Kakuyomu (kakuyomu.jp)
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
}

def clean_filename(name: str) -> str:
    """Làm sạch tên file/thư mục hợp lệ trên Windows."""
    name = re.sub(r'[\\/*?:"<>|\r\n\t]', '', name)
    name = name.strip().replace(' ', '_')
    if len(name) > 60:
        name = name[:60].rstrip('._')
    return name or "Kakuyomu_Raw"

def extract_kakuyomu_code(input_str: str) -> str:
    """Trích xuất mã truyện Kakuyomu (work ID) từ URL hoặc chuỗi nhập."""
    input_str = input_str.strip()
    match = re.search(r'kakuyomu\.jp/works/(\d+)', input_str)
    if match:
        return match.group(1)
    match_digits = re.search(r'(\d{10,20})', input_str)
    if match_digits:
        return match_digits.group(1)
    return input_str

class KakuyomuNovel:
    def __init__(self, work_id: str):
        self.work_id = work_id
        self.base_url = f"https://kakuyomu.jp/works/{work_id}"
        self.title = ""
        self.author = ""
        self.synopsis = ""
        self.episodes: List[Dict] = []

    async def fetch_novel_info_and_toc(self, client: httpx.AsyncClient) -> bool:
        """Tải thông tin tổng quan và toàn bộ mục lục của truyện Kakuyomu."""
        self.episodes = []

        with console.status(f"[bold cyan]Đang quét mục lục truyện Kakuyomu ({self.work_id})...[/bold cyan]"):
            try:
                res = await client.get(self.base_url, headers=SCRAPER_HEADERS, timeout=15.0, follow_redirects=True)
                if res.status_code != 200:
                    return False

                soup = BeautifulSoup(res.text, "html.parser")

                # Parse Title (supporting new and legacy Kakuyomu layouts)
                h1_el = soup.find("h1")
                if h1_el:
                    self.title = h1_el.get_text(strip=True)
                else:
                    title_el = soup.select_one("#workTitle a, #workTitle, .widget-workCard-title a, .widget-workCard-title")
                    if title_el:
                        self.title = title_el.get_text(strip=True)

                if not self.title:
                    og_title = soup.find("meta", property="og:title")
                    if og_title and og_title.get("content"):
                        self.title = og_title["content"].split("（")[0].replace(" - カクヨム", "").strip()

                # Parse Author
                user_links = [a.get_text(strip=True) for a in soup.find_all("a") if "href" in a.attrs and "/users/" in a["href"]]
                if user_links:
                    self.author = user_links[0]
                else:
                    author_el = soup.select_one("#workAuthor-activityName a, #workAuthor-activityName, .widget-workCard-authorLabel a")
                    if author_el:
                        self.author = author_el.get_text(strip=True)

                # Parse Synopsis / Description
                synopsis_el = soup.select_one("#introduction, #catchphrase, .widget-workCard-introduction, .description")
                if synopsis_el:
                    self.synopsis = synopsis_el.get_text(strip=True)

                # Parse Episode List
                ep_links = soup.select("a.widget-toc-episode-episodeTitle, .widget-toc-episode a, a[href*='/episodes/']")
                if not ep_links:
                    # Fallback find all a tags with /episodes/
                    ep_links = [a for a in soup.find_all("a") if "href" in a.attrs and "/episodes/" in a["href"]]

                ep_counter = 1
                seen_urls = set()

                for a in ep_links:
                    href = a.get("href", "")
                    m = re.search(r'/episodes/(\d+)', href)
                    if m:
                        ep_id = m.group(1)
                        full_url = f"https://kakuyomu.jp/works/{self.work_id}/episodes/{ep_id}"
                        if full_url in seen_urls:
                            continue
                        seen_urls.add(full_url)

                        # Extract episode title
                        title_span = a.select_one(".widget-toc-episode-titleLabel")
                        ep_title = title_span.get_text(strip=True) if title_span else a.get_text(strip=True)

                        self.episodes.append({
                            "ep": ep_counter,
                            "ep_id": ep_id,
                            "title": ep_title or f"Chương {ep_counter}",
                            "url": full_url
                        })
                        ep_counter += 1

                return len(self.episodes) > 0
            except Exception as e:
                console.print(f"[yellow]⚠️ Lỗi khi lấy mục lục Kakuyomu ({self.work_id}): {e}[/yellow]")
                return False

    async def fetch_chapter_content(self, client: httpx.AsyncClient, ep_num: int) -> Optional[str]:
        """Tải toàn bộ nội dung thô của một chương Kakuyomu."""
        target_ep = None
        for ep in self.episodes:
            if ep.get("ep") == ep_num:
                target_ep = ep
                break

        if not target_ep:
            return None

        url = target_ep.get("url")
        try:
            res = await client.get(url, headers=SCRAPER_HEADERS, timeout=15.0, follow_redirects=True)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                body = soup.select_one(".widget-episodeBody, .js-episode-body")
                if body:
                    p_tags = body.select("p.widget-episodeBody-element, p")
                    lines = []
                    for p in p_tags:
                        text = p.get_text()
                        lines.append(text)

                    if not lines:
                        lines = body.get_text().splitlines()

                    return "\n".join(lines).strip()
        except Exception as e:
            console.print(f"[yellow]⚠️ Lỗi tải chương {ep_num} Kakuyomu: {e}[/yellow]")

        return None
