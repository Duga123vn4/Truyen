# -*- coding: utf-8 -*-
"""
TRUNG TÂM QUẢN LÝ DỰ ÁN NOVEL & GLOSSARY STUDIO (V3.0 ULTIMATE):
Ứng dụng CLI chính điều phối toàn bộ dịch vụ Quản lý Novel.
"""
import sys
import os
import asyncio
from pathlib import Path
from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt

from tools.src.core.paths import WORKSPACE_DIR, TOOLS_DIR
from tools.src.core.config import load_config, save_config, fetch_llmgate_models, fetch_gemini_models
from tools.src.core.ai_client import AIClient
from tools.src.core.novel_context import NovelContext, discover_novels
from tools.src.core.notifications import notify_completion
from tools.src.services.diff_studio import generate_diff_data, open_diff_studio, generate_diff_report
from tools.src.services.deep_editor import edit_single_chapter
from tools.src.services.polisher import run_glossary_polisher_and_normalizer
from tools.src.services.glossary_miner import auto_sync_glossary_from_translated
from tools.src.services.lore_master import run_lore_master

console = Console()

def configure_ai_menu(cfg: dict):
    """Menu tương tác cài đặt AI và API Keys."""
    while True:
        console.clear()
        active = cfg.get("active_provider", "llmgate")
        g_cfg = cfg.get("gemini_free", {})
        l_cfg = cfg.get("llmgate", {})
        g_mode = cfg.get("glossary_mode", "full_cache")

        console.print(Panel.fit(
            "[bold cyan]⚙️  CẤU HÌNH AI & MÔ HÌNH DỊCH THUẬT / BIÊN TẬP[/bold cyan]\n"
            f"1. Nhà cung cấp đang chọn: [bold green]{active.upper()}[/bold green]\n"
            f"2. Gemini Free Key: [yellow]{g_cfg.get('api_key', '')[:8]}...[/yellow] | Model: [cyan]{g_cfg.get('model')}[/cyan]\n"
            f"3. LLMGate Key: [yellow]{l_cfg.get('api_key', '')[:8]}...[/yellow] | Model: [magenta]{l_cfg.get('model')}[/magenta]\n"
            f"4. Chế độ nạp Glossary: [bold white]{g_mode}[/bold white] (full_cache = nạp 100% Canon, tiết kiệm chi phí)\n"
            "0. 🔙 Lưu và quay lại Menu chính",
            border_style="yellow"
        ))

        choice = Prompt.ask("Chọn cài đặt", choices=["0", "1", "2", "3", "4"], default="0")
        if choice == "0":
            save_config(cfg)
            break
        elif choice == "1":
            new_p = Prompt.ask("Chọn kênh hoạt động", choices=["gemini_free", "llmgate"], default=active)
            cfg["active_provider"] = new_p
        elif choice == "2":
            key = Prompt.ask("Nhập Gemini Free API Key (Bỏ trống nếu giữ nguyên)", default="")
            if key.strip():
                cfg.setdefault("gemini_free", {})["api_key"] = key.strip()
            mod = Prompt.ask("Nhập tên model Gemini Free", default=g_cfg.get("model", "gemini-2.5-flash"))
            cfg.setdefault("gemini_free", {})["model"] = mod.strip()
        elif choice == "3":
            key = Prompt.ask("Nhập LLMGate API Key (Bỏ trống nếu giữ nguyên)", default="")
            if key.strip():
                cfg.setdefault("llmgate", {})["api_key"] = key.strip()
            mod = Prompt.ask("Nhập tên model LLMGate", default=l_cfg.get("model", "gemini-3.7-flash"))
            cfg.setdefault("llmgate", {})["model"] = mod.strip()
        elif choice == "4":
            new_m = Prompt.ask("Chọn chế độ Glossary", choices=["full_cache", "smart_filter"], default=g_mode)
            cfg["glossary_mode"] = new_m

async def run_batch_editor_cli(novel: NovelContext, ai: AIClient):
    """Giao diện CLI chạy biên tập theo khoảng chương."""
    trans = novel.list_translated_chapters()
    if not trans:
        console.print("[red]Thư mục translated/ rỗng.[/red]")
        return

    console.print(f"\n[bold cyan]📝 BIÊN TẬP CHUYÊN SÂU BẰNG AI — BỘ TRUYỆN: {novel.name}[/bold cyan]")
    console.print(f"Tổng số chương hiện có: {len(trans)} (Tập {trans[0][0]} đến Tập {trans[-1][0]})")
    console.print(f"Model đang dùng: [bold green]{ai.model}[/bold green] | Glossary Mode: [bold]{ai.config.get('glossary_mode')}[/bold]")

    start_ep = IntPrompt.ask("Nhập số tập BẮT ĐẦU", default=trans[0][0])
    end_ep = IntPrompt.ask("Nhập số tập KẾT THÚC", default=trans[-1][0])

    selected_files = [(ep, p) for ep, p in trans if start_ep <= ep <= end_ep]
    if not selected_files:
        console.print("[yellow]Không tìm thấy chương nào trong khoảng đã chọn.[/yellow]")
        return

    max_concurrent = 2
    sem = asyncio.Semaphore(max_concurrent)

    console.print(f"\n🚀 Chuẩn bị biên tập {len(selected_files)} tập. Đang chạy...")
    import time
    t0 = time.time()
    diff_results = []

    tasks = [edit_single_chapter(ep, p, novel, ai, sem) for ep, p in selected_files]
    for fut in asyncio.as_completed(tasks):
        success, ep, fpath, msg, diff_info = await fut
        if success:
            console.print(f"  [bold green]✅ [Tập {ep}][/bold green] {msg}")
            if diff_info:
                diff_results.append({"chapter": ep, "filename": fpath.name, "diff": diff_info})
        else:
            console.print(f"  [bold red]❌ [Tập {ep}][/bold red] Lỗi: {msg}")

    elapsed = time.time() - t0
    report_file = generate_diff_report(novel, diff_results) if diff_results else None
    generate_diff_data(novel)
    auto_sync_glossary_from_translated(novel)
    notify_completion(novel.name, "Biên Tập AI Chuyên Sâu", len(selected_files), elapsed, report_file)

async def main():
    cfg = load_config()

    while True:
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]📚 TRUNG TÂM QUẢN LÝ DỰ ÁN NOVEL & GLOSSARY STUDIO[/bold cyan] [bold magenta]— V3.0 MODULAR[/bold magenta]\n"
            "[bold green]🏛️ Kiến trúc:[/bold green] [bold white]Canon Database V3.0 • Atomic Claims • Anti-Hallucination Validator[/bold white]\n"
            "[dim]Quản lý Đa Truyện • Khai thác Canon Miner • Chuẩn hóa Kính ngữ • Biên tập Diff Report[/dim]",
            border_style="bright_blue"
        ))

        novels = discover_novels()
        if not novels:
            console.print("[red]❌ Không tìm thấy thư mục truyện nào trong projects/.[/red]")
            return

        active_p = cfg.get("active_provider", "llmgate")
        ai = AIClient(cfg)
        console.print(f"🤖 [bold]Kênh AI đang dùng:[/bold] [bold green]{ai.provider.upper()} ({ai.model})[/bold green]\n")

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
            table.add_row(str(idx), n.name, str(raw_c), str(trans_c), f"Char: {has_char} | Term: {has_term}")

        console.print(table)

        console.print("\n[bold cyan]Hành động:[/bold cyan]")
        console.print(f"  [bold yellow][1 - {len(novels)}][/bold yellow] 📖 Chọn bộ truyện để làm việc")
        console.print("  [bold cyan]9.[/bold cyan] ⚙️  Cấu hình AI & API Keys (Gemini Free / LLMGate)")
        console.print("  [bold cyan]0.[/bold cyan] ❌ Thoát")

        choice = Prompt.ask(f"\nNhập lựa chọn (0 - {len(novels)} hoặc 9)", default="1")
        if choice == "0":
            break
        elif choice == "9":
            configure_ai_menu(cfg)
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
                f"[bold cyan]🚀 TRUNG TÂM QUẢN TRỊ CANON & GLOSSARY STUDIO[/bold cyan]\n"
                f"[bold green]📖 Đang làm việc với:[/bold green] [bold yellow]{selected_novel.name}[/bold yellow]\n"
                f"[dim]Kênh AI: {ai.provider} ({ai.model}) • Thư mục: {selected_novel.folder}[/dim]",
                border_style="bright_blue"
            ))

            console.print("  [bold cyan]1.[/bold cyan] ⚡ [bold green]Chuẩn Hóa Thuật Ngữ & Dọn Kính Ngữ[/bold green] [dim](Dọn rác text thô)[/dim]")
            console.print("  [bold cyan]2.[/bold cyan] 🔍 [bold yellow]Tự Động Bổ Sung Thực Thể Vào Glossary (Auto-Sync)[/bold yellow]")
            console.print("  [bold cyan]3.[/bold cyan] 📝 [bold magenta]Biên tập chuyên sâu bằng AI[/bold magenta] [dim](Xuất DIFF_REPORT.md)[/dim]")
            console.print("  [bold cyan]4.[/bold cyan] 🔬 [bold cyan]Cập nhật Dữ liệu So Sánh Đối Chiếu (Diff Studio)[/bold cyan]")
            console.print("  [bold cyan]5.[/bold cyan] 🧠 [bold bright_green]Trợ Lý AI Lore Master (Hỏi Đáp & Tra Cứu Cốt Truyện)[/bold bright_green]")
            console.print("  [bold cyan]0.[/bold cyan] ⬅️  Quay lại danh sách truyện")

            sub_choice = Prompt.ask("\nLựa chọn của bạn (0-5)", choices=["0", "1", "2", "3", "4", "5"], default="1")
            if sub_choice == "0":
                break

            if sub_choice == "1":
                run_glossary_polisher_and_normalizer(selected_novel)
            elif sub_choice == "2":
                added = auto_sync_glossary_from_translated(selected_novel)
                if added == 0:
                    console.print("[bold green]✅ Toàn bộ thuật ngữ trong bản dịch đã đồng bộ hoàn hảo với terms.md![/bold green]")
            elif sub_choice == "3":
                await run_batch_editor_cli(selected_novel, ai)
            elif sub_choice == "4":
                generate_diff_data(selected_novel)
                console.print("[bold green]✅ Đã cập nhật xong web/diff_data.js![/bold green]")
            elif sub_choice == "5":
                await run_lore_master(selected_novel, ai)

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
