# -*- coding: utf-8 -*-
"""
Hệ thống Thông Báo Đa Kênh (Notification System):
- Âm thanh Windows (winsound)
- Popup hộp thoại Windows (tkinter)
- Bảng tổng kết Rich Console
- Discord Webhook Notifier
"""
import os
import sys
import threading
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from tools.src.core.paths import TOOLS_DIR

console = Console()

def play_success_sound():
    """Phát âm thanh thông báo hoàn tất thành công trên Windows."""
    def _beep():
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass
    threading.Thread(target=_beep, daemon=True).start()

def play_error_sound():
    """Phát âm thanh cảnh báo lỗi trên Windows."""
    def _beep():
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONHAND)
        except Exception:
            pass
    threading.Thread(target=_beep, daemon=True).start()

def show_popup_notification(title: str, message: str):
    """Hiển thị hộp thoại Popup Windows (không chặn luồng chính)."""
    def _popup():
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            messagebox.showinfo(title, message)
            root.destroy()
        except Exception:
            pass
    threading.Thread(target=_popup, daemon=True).start()

def notify_completion(
    novel_name: str,
    action_name: str,
    total_processed: int,
    elapsed_time: float,
    report_path: Optional[Path] = None,
    extra_info: Optional[str] = None
):
    """
    Gửi thông báo hoàn tất đa kênh:
    1. Phát âm thanh chuông Windows
    2. Hiện hộp thoại Popup
    3. In bảng tổng kết màu sắc trên Console
    4. Gửi webhook đến Discord (nếu có cấu hình)
    """
    play_success_sound()

    popup_msg = f"Tác vụ: {action_name}\nBộ truyện: {novel_name}\nSố lượng: {total_processed} file\nThời gian: {elapsed_time:.1f}s"
    if report_path and report_path.exists():
        popup_msg += f"\nBáo cáo: {report_path.name}"
    show_popup_notification(f"🎉 Hoàn Tất: {action_name}", popup_msg)

    # In Bảng Rich Console
    table = Table(title=f"🎉 TỔNG KẾT TÁC VỤ: {action_name}", border_style="bold green")
    table.add_column("Thuộc tính", style="bold cyan")
    table.add_column("Chi tiết", style="bold yellow")

    table.add_row("Bộ truyện", novel_name)
    table.add_row("Hành động", action_name)
    table.add_row("Tổng số xử lý", f"{total_processed} chương / file")
    table.add_row("Thời gian thực thi", f"{elapsed_time:.1f} giây")

    if report_path and report_path.exists():
        table.add_row("Báo cáo kiểm chứng", str(report_path))
    if extra_info:
        table.add_row("Thông tin bổ sung", extra_info)

    console.print()
    console.print(table)
    console.print()
