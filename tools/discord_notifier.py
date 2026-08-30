# -*- coding: utf-8 -*-
"""
🔔 NOVEL AI — DISCORD WEBHOOK NOTIFIER V3.0
Tự động gửi thông báo thời gian thực về kênh Discord khi:
1. Dịch xong 1 chương (kèm số token, thời gian, model)
2. Hoàn tất dải dịch hàng loạt (Batch translation)
3. Phát hiện thực thể lạ rơi vào unclassified_entities.jsonl
4. Đồng bộ GitHub Pages thành công
5. Cảnh báo lỗi API / Timeout
"""

import sys
import os
import json
import urllib.request
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
CONFIG_PATH = TOOLS_DIR / "ai_config.json"

def get_webhook_url():
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return cfg.get("discord_webhook_url", "").strip()
        except Exception:
            return ""
    return ""

def send_embed(title: str, description: str, color: int = 0x10b981, fields: list = None, image_url: str = None):
    url = get_webhook_url()
    if not url:
        return False

    payload = {
        "username": "Novel AI Studio",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/3500/3500833.png",
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "fields": fields or [],
            "footer": {"text": "Novel AI Studio V3.0 • Realtime Alert"}
        }]
    }

    if image_url:
        payload["embeds"][0]["image"] = {"url": image_url}

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "NovelAI-Webhook/3.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status in [200, 204]
    except Exception as e:
        print(f"⚠️ [Discord Webhook] Không thể gửi thông báo: {e}")
        return False

def notify_chapter_done(novel_title: str, chapter_num: int, chapter_title: str, token_count: int = 0, elapsed_sec: float = 0.0, model_name: str = ""):
    fields = [
        {"name": "📖 Bộ truyện", "value": f"`{novel_title}`", "inline": True},
        {"name": "⏱️ Thời gian dịch", "value": f"`{elapsed_sec:.1f}s`", "inline": True},
    ]
    if token_count > 0:
        fields.append({"name": "📊 Chi phí Token", "value": f"`{token_count:,} tokens`", "inline": True})
    if model_name:
        fields.append({"name": "🤖 Model AI", "value": f"`{model_name}`", "inline": True})

    fields.append({"name": "🌐 Đọc ngay Online", "value": "[Mở Trình Đọc Web](https://duga123vn4.github.io/Truyen/)", "inline": False})

    return send_embed(
        title=f"✅ ĐÃ DỊCH XONG TẬP {chapter_num}: {chapter_title}",
        description=f"Chương **Tập {chapter_num}** đã được dịch và đồng bộ vào thư viện thành công!",
        color=0x10b981,  # Xanh lá
        fields=fields
    )

def notify_batch_done(novel_title: str, start_ch: int, end_ch: int, total_count: int, elapsed_min: float = 0.0):
    fields = [
        {"name": "📖 Bộ truyện", "value": f"`{novel_title}`", "inline": True},
        {"name": "🔢 Dải chương", "value": f"`Tập {start_ch} ➔ Tập {end_ch}`", "inline": True},
        {"name": "📚 Tổng số chương", "value": f"`{total_count} tập`", "inline": True},
        {"name": "⏳ Tổng thời gian", "value": f"`{elapsed_min:.1f} phút`", "inline": True},
        {"name": "🌐 Đọc trên Web", "value": "[https://duga123vn4.github.io/Truyen/](https://duga123vn4.github.io/Truyen/)", "inline": False}
    ]
    return send_embed(
        title=f"🎉 HOÀN TẤT DỊCH BATCH HÀNG LOẠT ({total_count} CHƯƠNG)",
        description=f"Hệ thống đã hoàn thành dịch toàn bộ dải chương từ **Tập {start_ch}** đến **Tập {end_ch}**!",
        color=0x8b5cf6,  # Tím
        fields=fields
    )

def notify_unclassified_entity(novel_title: str, raw_name: str, raw_category: str, context: str = ""):
    fields = [
        {"name": "📖 Bộ truyện", "value": f"`{novel_title}`", "inline": True},
        {"name": "❓ Danh mục lạ", "value": f"`{raw_category}`", "inline": True},
        {"name": "📌 Tên thực thể", "value": f"**{raw_name}**", "inline": False}
    ]
    if context:
        fields.append({"name": "📝 Bối cảnh xuất hiện", "value": f"> *{context[:250]}*", "inline": False})
    fields.append({"name": "💡 Hướng xử lý", "value": "Mở `4_Quan_Ly_Novel.bat` để duyệt và gán thực thể vào Canon.", "inline": False})

    return send_embed(
        title=f"🚨 CẢNH BÁO: PHÁT HIỆN THỰC THỂ LẠ CHƯA PHÂN LOẠI",
        description=f"Thực thể **{raw_name}** có danh mục `{raw_category}` chưa được map vào 8 danh mục Canon chuẩn. Đã lưu vào `unclassified_entities.jsonl`.",
        color=0xef4444,  # Đỏ
        fields=fields
    )

def notify_git_synced(repo_url: str, pages_url: str, commit_msg: str, file_count: int = 0):
    fields = [
        {"name": "🐙 GitHub Repo", "value": f"[{repo_url}]({repo_url})", "inline": False},
        {"name": "🌐 Web Reader Live", "value": f"[{pages_url}]({pages_url})", "inline": False},
        {"name": "📝 Nội dung Commit", "value": f"`{commit_msg}`", "inline": False}
    ]
    if file_count > 0:
        fields.append({"name": "📦 Số file cập nhật", "value": f"`{file_count} files`", "inline": True})

    return send_embed(
        title="☁️ ĐỒNG BỘ GITHUB PAGES THÀNH CÔNG!",
        description="Toàn bộ chương dịch mới, thư viện và dữ liệu đã được đẩy lên Cloud và cập nhật trang Web Reader Online!",
        color=0x38bdf8,  # Xanh cyan
        fields=fields
    )

def notify_api_error(novel_title: str, chapter_num: int, error_msg: str):
    fields = [
        {"name": "📖 Bộ truyện", "value": f"`{novel_title}`", "inline": True},
        {"name": "🔢 Tập bị lỗi", "value": f"`Tập {chapter_num}`", "inline": True},
        {"name": "❌ Chi tiết lỗi", "value": f"```{error_msg[:400]}```", "inline": False}
    ]
    return send_embed(
        title=f"❌ LỖI GỌI API DỊCH THUẬT (TẬP {chapter_num})",
        description="Đã xảy ra lỗi trong quá trình kết nối với AI Provider. Tiến trình dịch đang tạm dừng.",
        color=0xdc2626,  # Đỏ đậm
        fields=fields
    )

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "test":
            send_embed("🔔 KIỂM TRA WEBHOOK", "Đây là thông báo thử nghiệm từ Novel AI Notifier CLI.", 0x10b981)
        elif cmd == "git_sync":
            repo = sys.argv[2] if len(sys.argv) > 2 else "https://github.com/Duga123vn4/Truyen"
            pages = sys.argv[3] if len(sys.argv) > 3 else "https://duga123vn4.github.io/Truyen/"
            msg = sys.argv[4] if len(sys.argv) > 4 else "Đồng bộ tự động"
            notify_git_synced(repo, pages, msg)
