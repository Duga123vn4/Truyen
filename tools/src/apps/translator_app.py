# -*- coding: utf-8 -*-
"""
BỘ DỊCH THUẬT NOVEL AI THÔNG MINH ĐA NĂNG (TRANSLATOR STUDIO):
Ứng dụng CLI chính điều phối cào Syosetu, dịch thuật và sinh ảnh Anime FLUX.
"""
import sys
import os
import asyncio
import httpx
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt

from tools.src.core.config import load_config
from tools.src.core.ai_client import AIClient
from tools.src.core.novel_context import NovelContext, discover_novels
from tools.src.core.notifications import notify_completion
from tools.src.services.syosetu_scraper import SyosetuNovel, extract_novel_code, clean_filename
from tools.src.services.translator import translate_chapter, generate_anime_illustration

console = Console()

async def run_syosetu_scraping(novel: NovelContext):
    """Cào chương raw từ Syosetu vào thư mục raw/."""
    code_or_url = Prompt.ask("\n[bold cyan]Nhập mã truyện Syosetu hoặc URL (Ví dụ: n1234xx hoặc https://ncode.syosetu.com/...)[/bold cyan]").strip()
    novel_code = extract_novel_code(code_or_url)
    if not novel_code:
        console.print("[red]Mã truyện không hợp lệ.[/red]")
        return

    syosetu = SyosetuNovel(novel_code)
    async with httpx.AsyncClient() as client:
        ok = await syosetu.fetch_novel_info_and_toc(client)
        if not ok:
            console.print("[red]Không thể lấy dữ liệu truyện từ Syosetu.[/red]")
            return

        console.print(f"\n[bold green]Tìm thấy truyện:[/bold green] [yellow]{syosetu.title}[/yellow] (Tác giả: {syosetu.author})")
        console.print(f"Tổng số tập trên Syosetu: {len(syosetu.episodes)}")

        start_ep = IntPrompt.ask("Tập bắt đầu tải", default=1)
        end_ep = IntPrompt.ask("Tập kết thúc tải", default=len(syosetu.episodes))

        to_download = [ep for ep in syosetu.episodes if start_ep <= ep["ep"] <= end_ep]
        for item in to_download:
            ep = item["ep"]
            fname = f"chuong_{ep:03d}_{clean_filename(item['title'])}.txt"
            fpath = novel.raw_dir / fname
            if fpath.exists():
                continue

            content = await syosetu.fetch_chapter_content(client, ep)
            if content:
                fpath.write_text(f"# {item['title']}\n\n{content}", encoding="utf-8")
                console.print(f"  [green]✓ Tải xong Tập {ep}:[/green] {item['title']}")
            await asyncio.sleep(0.5)

    console.print("\n[bold green]🎉 Đã hoàn tất tải các chương raw về thư mục raw/![/bold green]")

async def run_batch_translation(novel: NovelContext, ai: AIClient):
    """Dịch các chương từ raw/ sang translated/."""
    raws = novel.list_raw_chapters()
    if not raws:
        console.print("[red]Thư mục raw/ rỗng. Hãy tải raw trước.[/red]")
        return

    console.print(f"\n[bold cyan]📖 DỊCH RAW SANG TIẾNG VIỆT — BỘ TRUYỆN: {novel.name}[/bold cyan]")
    console.print(f"Tổng số tập raw: {len(raws)} (Tập {raws[0][0]} đến Tập {raws[-1][0]})")

    start_ep = IntPrompt.ask("Nhập tập BẮT ĐẦU dịch", default=raws[0][0])
    end_ep = IntPrompt.ask("Nhập tập KẾT THÚC dịch", default=raws[-1][0])

    selected = [(ep, p) for ep, p in raws if start_ep <= ep <= end_ep]
    sem = asyncio.Semaphore(2)

    console.print(f"\n🚀 Đang dịch {len(selected)} tập qua {ai.model}...")
    import time
    t0 = time.time()

    tasks = [translate_chapter(p, novel, ai, ep, sem) for ep, p in selected]
    for fut in asyncio.as_completed(tasks):
        success, ep, fpath, msg = await fut
        if success:
            console.print(f"  [bold green]✅ [Tập {ep}][/bold green] {msg}")
        else:
            console.print(f"  [bold red]❌ [Tập {ep}][/bold red] Lỗi: {msg}")

    elapsed = time.time() - t0
    notify_completion(novel.name, "Dịch Raw AI", len(selected), elapsed)

async def main():
    cfg = load_config()
    ai = AIClient(cfg)

    while True:
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]🌐 BỘ DỊCH THUẬT NOVEL AI THÔNG MINH ĐA NĂNG[/bold cyan] [bold magenta]— V3.0 MODULAR[/bold magenta]\n"
            "[bold green]🤖 AI Provider:[/bold green] [bold white]Gemini Free & LLMGate • FLUX Anime Generation • Syosetu Scraper[/bold white]",
            border_style="bright_blue"
        ))

        novels = discover_novels()
        if not novels:
            console.print("[red]Không tìm thấy bộ truyện nào trong projects/.[/red]")
            return

        table = Table(title="📚 Danh Sách Bộ Truyện", border_style="cyan")
        table.add_column("STT", style="bold cyan", width=4)
        table.add_column("Tên Truyện", style="bold yellow")
        table.add_column("Số Raw", justify="right", style="cyan")
        table.add_column("Đã Dịch", justify="right", style="green")

        for idx, n in enumerate(novels, 1):
            table.add_row(str(idx), n.name, str(len(n.list_raw_chapters())), str(len(n.list_translated_chapters())))

        console.print(table)
        console.print(f"\n[bold]Model dịch đang dùng:[/bold] [bold green]{ai.provider.upper()} ({ai.model})[/bold green]")
        console.print("\n  [bold yellow][1 - N][/bold yellow] Chọn bộ truyện để làm việc")
        console.print("  [bold cyan]0.[/bold cyan] ❌ Thoát")

        choice = Prompt.ask(f"\nNhập lựa chọn (0 - {len(novels)})", default="1")
        if choice == "0":
            break

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
                f"[bold cyan]🎯 DỊCH THUẬT & SINH ẢNH — {selected_novel.name}[/bold cyan]\n"
                f"[dim]Kênh AI: {ai.provider} ({ai.model})[/dim]",
                border_style="cyan"
            ))

            console.print("  [bold cyan]1.[/bold cyan] 📥 [bold green]Cào Chương Mới Từ Syosetu[/bold green] [dim](Tự động tải raw vào thư mục raw/)[/dim]")
            console.print("  [bold cyan]2.[/bold cyan] 🌐 [bold yellow]Dịch Raw Sang Tiếng Việt Chuẩn Light Novel[/bold yellow]")
            console.print("  [bold cyan]3.[/bold cyan] 🎨 [bold magenta]Sinh Ảnh Minh Họa Anime Bằng FLUX (Miễn Phí)[/bold magenta]")
            console.print("  [bold cyan]0.[/bold cyan] ⬅️  Quay lại")

            sub_choice = Prompt.ask("\nLựa chọn của bạn", choices=["0", "1", "2", "3"], default="1")
            if sub_choice == "0":
                break

            if sub_choice == "1":
                await run_syosetu_scraping(selected_novel)
            elif sub_choice == "2":
                await run_batch_translation(selected_novel, ai)
            elif sub_choice == "3":
                ep = IntPrompt.ask("Nhập số tập cần vẽ ảnh minh họa", default=1)
                p = Prompt.ask("Mô tả nhân vật / bối cảnh (Tiếng Anh hoặc Việt)").strip()
                out_img = selected_novel.images_dir / f"chuong_{ep:03d}_illustration.jpg"
                with console.status("[magenta]Đang vẽ ảnh anime qua FLUX Engine...[/magenta]"):
                    ok = await generate_anime_illustration(p, out_img)
                if ok:
                    console.print(f"[bold green]✅ Đã sinh ảnh thành công tại:[/bold green] {out_img}")
                else:
                    console.print("[red]Không thể sinh ảnh lúc này. Vui lòng thử lại sau.[/red]")

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
