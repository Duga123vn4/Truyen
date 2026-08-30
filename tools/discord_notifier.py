# -*- coding: utf-8 -*-
"""
🔔 NOVEL AI — COMPREHENSIVE DISCORD WEBHOOK NOTIFIER V3.0 ULTIMATE
Tự động gửi thông báo thời gian thực về kênh Discord cho MỌI sự kiện trong hệ sinh thái:
1. 📚 CẬP NHẬT GLOSSARY & KHAI PHÁ THỰC THỂ (Glossary Miner / Canon Engine)
2. ⚡ CHUẨN HÓA THUẬT NGỮ & DỌN KÍNH NGỮ (Glossary Normalizer)
3. 🔄 ĐỔI THUẬT NGỮ / SỬA TÊN NHÂN VẬT TOÀN CỤC (Global Term Refactor)
4. 📝 BIÊN TẬP CHUYÊN SÂU BẰNG AI (Batch Editor)
5. ✅ DỊCH XONG 1 CHƯƠNG / HOÀN TẤT BATCH DỊCH (Translator)
6. 🚨 CẢNH BÁO THỰC THỂ LẠ (Unclassified Entity Alert)
7. 🎙️ XUẤT AUDIO MP3 (TTS Audio Exporter)
8. ☁️ ĐỒNG BỘ GITHUB PAGES (Git Sync)
9. ⏪ HOÀN TÁC & KHÔI PHỤC SAO LƯU (Undo / Restore)
10. ❌ CẢNH BÁO LỖI API / TIMEOUT
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
            "footer": {"text": "Novel AI Studio V3.0 • Realtime Event Monitor"}
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
        print(f"⚠️ [Discord Webhook] Lỗi gửi thông báo: {e}")
        return False

# ==============================================================================
# 1. NHÓM SỰ KIỆN GLOSSARY & CANON LORE
# ==============================================================================
def notify_glossary_mined(novel_title: str, new_entities: dict, chapter_range_str: str = ""):
    """Thông báo khi trích xuất / khai phá xong thực thể mới từ Raw vào Glossary."""
    fields = [
        {"name": "📖 Bộ truyện", "value": f"`{novel_title}`", "inline": True},
    ]
    if chapter_range_str:
        fields.append({"name": "🔍 Phạm vi Raw", "value": f"`{chapter_range_str}`", "inline": True})

    summary_lines = []
    category_labels = {
        "characters": "👥 Nhân vật mới",
        "terms": "📚 Thuật ngữ / Kỹ năng",
        "monsters": "🐉 Quái vật / Ma thú",
        "items": "🗡️ Vật phẩm / Trang bị",
        "skills": "⚡ Tuyệt chiêu / Pháp thuật",
        "races": "🧝 Chủng tộc",
        "factions": "🏰 Phe phái / Tổ chức",
        "locations": "📍 Địa danh / Bản đồ"
    }

    for cat, items in new_entities.items():
        if items:
            lbl = category_labels.get(cat, f"📌 {cat}")
            names_preview = ", ".join([f"**{it}**" for it in items[:4]]) + (f" *(+{len(items)-4} mục)*" if len(items) > 4 else "")
            summary_lines.append(f"• {lbl} ({len(items)}): {names_preview}")

    desc = "Đã khai phá và cập nhật các thực thể mới vào kho Canon Lore:\n\n" + ("\n".join(summary_lines) if summary_lines else "• Không phát hiện thực thể mới.")

    return send_embed(
        title="📚 KHAI PHÁ GLOSSARY THÀNH CÔNG!",
        description=desc,
        color=0x38bdf8,  # Xanh cyan
        fields=fields
    )

def notify_glossary_normalized(novel_title: str, total_terms: int, replaced_count: int, chapters_count: int):
    """Thông báo khi chạy Chuẩn hóa thuật ngữ & Dọn kính ngữ."""
    fields = [
        {"name": "📖 Bộ truyện", "value": f"`{novel_title}`", "inline": True},
        {"name": "📑 Số chương đã quét", "value": f"`{chapters_count} tập`", "inline": True},
        {"name": "📚 Từ điển áp dụng", "value": f"`{total_terms} thuật ngữ`", "inline": True},
        {"name": "✨ Vị trí đã chuẩn hóa", "value": f"`{replaced_count:,} lần`", "inline": True},
        {"name": "📂 Nơi xuất bản", "value": "`projects/.../translated/` & `web/`", "inline": False}
    ]
    return send_embed(
        title="⚡ CHUẨN HÓA THUẬT NGỮ & DỌN KÍNH NGỮ HOÀN TẤT!",
        description=f"Toàn bộ văn bản đã được đồng bộ chuẩn hóa theo từ điển **Canon Database V3.0** (loại bỏ kính ngữ thừa -san, -kun, -sama và gán chuẩn xưng hô).",
        color=0x10b981,  # Xanh lá
        fields=fields
    )

def notify_term_refactored(novel_title: str, old_name: str, new_name: str, affected_files_count: int):
    """Thông báo khi Đổi thuật ngữ / Sửa tên nhân vật toàn cục."""
    fields = [
        {"name": "📖 Bộ truyện", "value": f"`{novel_title}`", "inline": True},
        {"name": "📁 Số file bị ảnh hưởng", "value": f"`{affected_files_count} tệp`", "inline": True},
        {"name": "🔄 Chuyển đổi tên", "value": f"**`{old_name}`**  ➔  **`{new_name}`**", "inline": False}
    ]
    return send_embed(
        title="🔄 ĐỔI THUẬT NGỮ TOÀN CỤC THÀNH CÔNG!",
        description=f"Đã tự động tìm và thay thế tên thực thể trên toàn bộ các chương dịch và hồ sơ Glossary.",
        color=0xf59e0b,  # Vàng cam
        fields=fields
    )

def notify_unclassified_entity(novel_title: str, raw_name: str, raw_category: str, context: str = ""):
    """Cảnh báo khi phát hiện thực thể lạ chưa map vào Canon."""
    fields = [
        {"name": "📖 Bộ truyện", "value": f"`{novel_title}`", "inline": True},
        {"name": "❓ Danh mục lạ", "value": f"`{raw_category}`", "inline": True},
        {"name": "📌 Tên thực thể", "value": f"**{raw_name}**", "inline": False}
    ]
    if context:
        fields.append({"name": "📝 Bối cảnh xuất hiện", "value": f"> *{context[:250]}*", "inline": False})
    fields.append({"name": "💡 Hướng xử lý", "value": "Mở `4_Quan_Ly_Novel.bat` để duyệt và gán thực thể vào Canon.", "inline": False})

    return send_embed(
        title="🚨 CẢNH BÁO: PHÁT HIỆN THỰC THỂ LẠ CHƯA PHÂN LOẠI",
        description=f"Thực thể **{raw_name}** có danh mục `{raw_category}` chưa được map vào 8 danh mục Canon chuẩn. Đã lưu vào `unclassified_entities.jsonl`.",
        color=0xef4444,  # Đỏ
        fields=fields
    )

# ==============================================================================
# 2. NHÓM SỰ KIỆN DỊCH THUẬT & BIÊN TẬP AI
# ==============================================================================
def notify_chapter_done(novel_title: str, chapter_num: int, chapter_title: str, token_count: int = 0, elapsed_sec: float = 0.0, model_name: str = ""):
    """Thông báo khi dịch xong 1 chương."""
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
        color=0x10b981,
        fields=fields
    )

def notify_batch_done(novel_title: str, start_ch: int, end_ch: int, total_count: int, elapsed_min: float = 0.0):
    """Thông báo khi hoàn tất dải dịch hàng loạt."""
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

def notify_batch_editor_done(novel_title: str, start_ch: int, end_ch: int, total_fixes: int):
    """Thông báo khi Biên tập chuyên sâu bằng AI hoàn tất."""
    fields = [
        {"name": "📖 Bộ truyện", "value": f"`{novel_title}`", "inline": True},
        {"name": "🔢 Dải chương biên tập", "value": f"`Tập {start_ch} ➔ Tập {end_ch}`", "inline": True},
        {"name": "✍️ Số câu đã trau chuốt", "value": f"`{total_fixes:,} câu`", "inline": True},
        {"name": "📑 Báo cáo chi tiết", "value": "`DIFF_REPORT.md`", "inline": True}
    ]
    return send_embed(
        title="📝 BIÊN TẬP VĂN PHONG CHUYÊN SÂU HOÀN TẤT!",
        description=f"AI đã trau chuốt văn phong Dark Fantasy và chuẩn hóa toàn bộ xưng hô nhân vật.",
        color=0xa855f7,  # Tím sáng
        fields=fields
    )

# ==============================================================================
# 3. NHÓM SỰ KIỆN AUDIO & GITHUB & HỆ THỐNG
# ==============================================================================
def notify_audio_exported(novel_title: str, chapter_num: int, file_size_mb: float, voice_name: str = "Hoài My (Nữ)"):
    """Thông báo khi xuất xong file Audio MP3."""
    fields = [
        {"name": "📖 Bộ truyện", "value": f"`{novel_title}`", "inline": True},
        {"name": "🔢 Tập truyện", "value": f"`Tập {chapter_num}`", "inline": True},
        {"name": "🗣️ Giọng đọc TTS", "value": f"`{voice_name}`", "inline": True},
        {"name": "📦 Dung lượng MP3", "value": f"`{file_size_mb:.1f} MB`", "inline": True}
    ]
    return send_embed(
        title=f"🎙️ XUẤT AUDIO MP3 TẬP {chapter_num} THÀNH CÔNG!",
        description=f"File âm thanh đã được lưu vào thư mục `audio/` và sẵn sàng để phát trên Web Reader!",
        color=0xec4899,  # Hồng
        fields=fields
    )

def notify_git_synced(repo_url: str, pages_url: str, commit_msg: str, file_count: int = 0):
    """Thông báo khi đồng bộ GitHub thành công."""
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

def notify_backup_restored(novel_title: str, backup_date_str: str, file_count: int):
    """Thông báo khi khôi phục bản sao lưu."""
    fields = [
        {"name": "📖 Bộ truyện", "value": f"`{novel_title}`", "inline": True},
        {"name": "📅 Mốc sao lưu", "value": f"`{backup_date_str}`", "inline": True},
        {"name": "📦 Số file đã khôi phục", "value": f"`{file_count} tệp`", "inline": True}
    ]
    return send_embed(
        title="⏪ HOÀN TÁC & KHÔI PHỤC SAO LƯU THÀNH CÔNG!",
        description=f"Dữ liệu bản dịch và Glossary đã được khôi phục về trạng thái an toàn.",
        color=0xf59e0b,  # Vàng
        fields=fields
    )

def notify_api_error(novel_title: str, chapter_num: int, error_msg: str):
    """Cảnh báo lỗi API / Timeout."""
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
