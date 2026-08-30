# -*- coding: utf-8 -*-
"""
🔔 NOVEL AI — COMPREHENSIVE DISCORD WEBHOOK NOTIFIER V3.0 ULTIMATE
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

def notify_batch_summary_with_errors(novel_title: str, start_ch: int, end_ch: int, success_list: list, failed_dict: dict, total_elapsed_min: float = 0.0):
    """Gửi thông báo tổng kết batch dịch khi có chương thành công và chương bị lỗi."""
    total_requested = len(success_list) + len(failed_dict)
    
    if not failed_dict:
        color = 0x10b981  # Xanh lá hoàn hảo
        title = f"🎉 HOÀN THÀNH 100% BATCH DỊCH ({len(success_list)}/{total_requested} CHƯƠNG)"
        status_desc = "Tất cả các chương trong dải đã được dịch thành công mỹ mãn!"
    elif success_list:
        color = 0xf59e0b  # Vàng cam cảnh báo một phần
        title = f"⚠️ BATCH DỊCH HOÀN TẤT VỚI MỘT SỐ CHƯƠNG LỖI ({len(success_list)}/{total_requested} THÀNH CÔNG)"
        status_desc = "Hệ thống đã bỏ qua các chương lỗi để tiếp tục dịch hết các chương còn lại."
    else:
        color = 0xdc2626  # Đỏ thất bại hoàn toàn
        title = f"❌ BATCH DỊCH THẤT BẠI (0/{total_requested} CHƯƠNG)"
        status_desc = "Toàn bộ các chương trong dải đều gặp sự cố API hoặc mất kết nối."

    fields = [
        {"name": "📖 Bộ truyện", "value": f"`{novel_title}`", "inline": True},
        {"name": "🔢 Dải yêu cầu", "value": f"`Tập {start_ch} ➔ Tập {end_ch}`", "inline": True},
        {"name": "⏳ Tổng thời gian", "value": f"`{total_elapsed_min:.1f} phút`", "inline": True},
    ]

    if success_list:
        succ_preview = f"**{len(success_list)} tập:** " + ", ".join([f"`{c}`" for c in success_list[:8]]) + (f" *(+{len(success_list)-8} tập)*" if len(success_list) > 8 else "")
        fields.append({"name": "✅ Các tập dịch thành công", "value": succ_preview, "inline": False})

    if failed_dict:
        fail_lines = []
        for ch_num, err in list(failed_dict.items())[:5]:
            fail_lines.append(f"• **Tập {ch_num}:** `{err[:80]}`")
        if len(failed_dict) > 5:
            fail_lines.append(f"• *Và {len(failed_dict)-5} chương khác...*")
        fields.append({"name": "❌ Các tập bị lỗi cần dịch lại", "value": "\n".join(fail_lines), "inline": False})
        fields.append({"name": "💡 Hướng xử lý", "value": "Chỉ cần mở `3_Dich_Truyen_AI.bat` và chọn dịch lại các tập lỗi ở trên.", "inline": False})

    fields.append({"name": "🌐 Xem Web Reader", "value": "[https://duga123vn4.github.io/Truyen/](https://duga123vn4.github.io/Truyen/)", "inline": False})

    return send_embed(
        title=title,
        description=status_desc,
        color=color,
        fields=fields
    )

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
        color=0x10b981,
        fields=fields
    )

def notify_glossary_mined(novel_title: str, new_entities: dict, chapter_range_str: str = ""):
    fields = [{"name": "📖 Bộ truyện", "value": f"`{novel_title}`", "inline": True}]
    if chapter_range_str:
        fields.append({"name": "🔍 Phạm vi Raw", "value": f"`{chapter_range_str}`", "inline": True})
    category_labels = {
        "characters": "👥 Nhân vật mới", "terms": "📚 Thuật ngữ / Kỹ năng",
        "monsters": "🐉 Quái vật / Ma thú", "items": "🗡️ Vật phẩm / Trang bị",
        "skills": "⚡ Tuyệt chiêu / Pháp thuật", "races": "🧝 Chủng tộc",
        "factions": "🏰 Phe phái / Tổ chức", "locations": "📍 Địa danh / Bản đồ"
    }
    summary_lines = []
    for cat, items in new_entities.items():
        if items:
            lbl = category_labels.get(cat, f"📌 {cat}")
            names_preview = ", ".join([f"**{it}**" for it in items[:4]]) + (f" *(+{len(items)-4} mục)*" if len(items) > 4 else "")
            summary_lines.append(f"• {lbl} ({len(items)}): {names_preview}")
    desc = "Đã khai phá và cập nhật các thực thể mới vào kho Canon Lore:\n\n" + ("\n".join(summary_lines) if summary_lines else "• Không phát hiện thực thể mới.")
    return send_embed(
        title="📚 KHAI PHÁ GLOSSARY THÀNH CÔNG!",
        description=desc,
        color=0x38bdf8,
        fields=fields
    )

def notify_glossary_normalized(novel_title: str, total_terms: int, replaced_count: int, chapters_count: int):
    fields = [
        {"name": "📖 Bộ truyện", "value": f"`{novel_title}`", "inline": True},
        {"name": "📑 Số chương đã quét", "value": f"`{chapters_count} tập`", "inline": True},
        {"name": "📚 Từ điển áp dụng", "value": f"`{total_terms} thuật ngữ`", "inline": True},
        {"name": "✨ Vị trí đã chuẩn hóa", "value": f"`{replaced_count:,} lần`", "inline": True},
    ]
    return send_embed(
        title="⚡ CHUẨN HÓA THUẬT NGỮ & DỌN KÍNH NGỮ HOÀN TẤT!",
        description="Toàn bộ văn bản đã được đồng bộ chuẩn hóa theo từ điển **Canon Database V3.0**.",
        color=0x10b981,
        fields=fields
    )

def notify_term_refactored(novel_title: str, old_name: str, new_name: str, affected_files_count: int):
    fields = [
        {"name": "📖 Bộ truyện", "value": f"`{novel_title}`", "inline": True},
        {"name": "📁 Số file bị ảnh hưởng", "value": f"`{affected_files_count} tệp`", "inline": True},
        {"name": "🔄 Chuyển đổi tên", "value": f"**`{old_name}`**  ➔  **`{new_name}`**", "inline": False}
    ]
    return send_embed(
        title="🔄 ĐỔI THUẬT NGỮ TOÀN CỤC THÀNH CÔNG!",
        description="Đã tự động tìm và thay thế tên thực thể trên toàn bộ các chương dịch và hồ sơ Glossary.",
        color=0xf59e0b,
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
        title="🚨 CẢNH BÁO: PHÁT HIỆN THỰC THỂ LẠ CHƯA PHÂN LOẠI",
        description=f"Thực thể **{raw_name}** có danh mục `{raw_category}` chưa được map vào 8 danh mục Canon chuẩn. Đã lưu vào `unclassified_entities.jsonl`.",
        color=0xef4444,
        fields=fields
    )

def notify_git_synced(repo_url: str, pages_url: str, commit_msg: str, file_count: int = 0):
    fields = [
        {"name": "🐙 GitHub Repo", "value": f"[{repo_url}]({repo_url})", "inline": False},
        {"name": "🌐 Web Reader Live", "value": f"[{pages_url}]({pages_url})", "inline": False},
        {"name": "📝 Nội dung Commit", "value": f"`{commit_msg}`", "inline": False}
    ]
    return send_embed(
        title="☁️ ĐỒNG BỘ GITHUB PAGES THÀNH CÔNG!",
        description="Toàn bộ chương dịch mới, thư viện và dữ liệu đã được đẩy lên Cloud và cập nhật trang Web Reader Online!",
        color=0x38bdf8,
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
        description="Đã xảy ra lỗi trong quá trình kết nối với AI Provider. Đang thử lại hoặc tạm dừng.",
        color=0xdc2626,
        fields=fields
    )
