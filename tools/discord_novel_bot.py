# -*- coding: utf-8 -*-
"""
🤖 NOVEL AI DISCORD BOT V3.0 ULTIMATE
- Đọc truyện Light Novel bằng Discord Embeds & Pagination
- Phát Radio Audio TTS (Giọng Hoài My / Nam Minh) trong Voice Channel
- Tra cứu Bách khoa Lore Canon (Nhân vật, Thuật ngữ, Phe phái)
- Quản lý danh sách & tiến độ 3 bộ truyện
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import os
import re
import json
import asyncio
import tempfile
import random
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
import edge_tts
import imageio_ffmpeg

TOOLS_DIR = Path(__file__).resolve().parent
ROOT_DIR = TOOLS_DIR.parent
PROJECTS_DIR = ROOT_DIR / "projects"
CONFIG_FILE = TOOLS_DIR / "discord_bot_config.json"
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

if CONFIG_FILE.exists():
    try:
        BOT_CONFIG = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        BOT_CONFIG = {}
else:
    BOT_CONFIG = {}

TOKEN = BOT_CONFIG.get("bot_token", "")
DEFAULT_NOVEL = BOT_CONFIG.get("default_novel", "Chu_Thuat_Su_Dung_Gia")
VOICES = BOT_CONFIG.get("voice_options", {
    "nu": "vi-VN-HoaiMyNeural",
    "nam": "vi-VN-NamMinhNeural"
})

intents = discord.Intents.default()
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

def get_all_novels():
    novels = {}
    if not PROJECTS_DIR.exists():
        return novels
    for d in PROJECTS_DIR.iterdir():
        if d.is_dir() and not d.name.startswith("."):
            title = d.name.replace("_", " ")
            meta_f = d / "meta.json"
            if meta_f.exists():
                try:
                    m = json.loads(meta_f.read_text(encoding="utf-8"))
                    title = m.get("title", title)
                except Exception:
                    pass
            
            trans_dir = d / "translated"
            chap_count = 0
            if trans_dir.exists():
                chap_count = len([f for f in trans_dir.glob("*") if f.is_file() and f.suffix in [".md", ".txt", ".docx"] and f.name != "README.md"])

            novels[d.name] = {
                "key": d.name,
                "title": title,
                "dir": d,
                "chapters_count": chap_count
            }
    return novels

def load_chapter_content(novel_key, chapter_num):
    novels = get_all_novels()
    if novel_key not in novels:
        novel_key = DEFAULT_NOVEL
    
    n_dir = novels.get(novel_key, {}).get("dir")
    if not n_dir:
        return None, "Không tìm thấy bộ truyện!"

    trans_dir = n_dir / "translated"
    if not trans_dir.exists():
        return None, "Chưa có chương dịch nào!"

    files = [f for f in trans_dir.glob("*") if f.is_file() and f.suffix in [".md", ".txt"] and f.name != "README.md"]
    target_file = None
    
    for f in files:
        m = re.search(r'(\d+)', f.name)
        if m and int(m.group(1)) == int(chapter_num):
            target_file = f
            break

    if not target_file and files:
        if 0 <= chapter_num - 1 < len(files):
            sorted_files = sorted(files, key=lambda x: int(re.search(r'(\d+)', x.name).group(1)) if re.search(r'(\d+)', x.name) else 0)
            target_file = sorted_files[chapter_num - 1]

    if not target_file:
        return None, f"Không tìm thấy tập {chapter_num} trong bộ {novels[novel_key]['title']}!"

    text = target_file.read_text(encoding="utf-8")
    return target_file.stem, text

def search_lore(novel_key, query):
    novels = get_all_novels()
    n_dir = novels.get(novel_key, {}).get("dir")
    if not n_dir:
        n_dir = PROJECTS_DIR / DEFAULT_NOVEL

    glossary_dir = n_dir / "glossary"
    chars_file = glossary_dir / "characters.md"
    terms_file = glossary_dir / "terms.md"

    results = []

    if chars_file.exists():
        content = chars_file.read_text(encoding="utf-8")
        sections = re.split(r'\n(?=##\s+\[CHAR-\d+\])', content)
        for sec in sections:
            if re.search(re.escape(query), sec, re.IGNORECASE):
                name_m = re.search(r'##\s+\[(CHAR-\d+)\]\s+([^\n]+)', sec)
                role_m = re.search(r'-\s+\*\*thiên_chức:\*\*\s*([^\n]+)', sec)
                status_m = re.search(r'-\s+\*\*trạng_thái_nhân_vật:\*\*\s*([^\n]+)', sec)
                desc_m = re.search(r'-\s+\*\*mô_tả:\*\*\s*([^\n]+)', sec)
                
                if name_m:
                    results.append({
                        "type": "NHÂN VẬT",
                        "id": name_m.group(1),
                        "name": name_m.group(2).strip(),
                        "role": role_m.group(1).strip() if role_m else "Chưa rõ",
                        "status": status_m.group(1).strip() if status_m else "Bình thường",
                        "desc": desc_m.group(1).strip() if desc_m else sec[:200]
                    })

    if terms_file.exists():
        content = terms_file.read_text(encoding="utf-8")
        sections = re.split(r'\n(?=##\s+\[TERM-\d+\])', content)
        for sec in sections:
            if re.search(re.escape(query), sec, re.IGNORECASE):
                name_m = re.search(r'##\s+\[(TERM-\d+)\]\s+([^\n]+)', sec)
                desc_m = re.search(r'-\s+\*\*mô_tả:\*\*\s*([^\n]+)', sec)
                if name_m:
                    results.append({
                        "type": "THUẬT NGỮ",
                        "id": name_m.group(1),
                        "name": name_m.group(2).strip(),
                        "role": "Thuật ngữ / Kỹ năng",
                        "status": "Canon",
                        "desc": desc_m.group(1).strip() if desc_m else sec[:200]
                    })

    return results

class ChapterPaginationView(discord.ui.View):
    def __init__(self, title, pages, novel_key):
        super().__init__(timeout=300)
        self.title = title
        self.pages = pages
        self.novel_key = novel_key
        self.current_page = 0
        
        # Thêm nút Link mở Web
        self.add_item(discord.ui.Button(label="🌐 Đọc Trên Web", style=discord.ButtonStyle.link, url="https://duga123vn4.github.io/Truyen/"))
        self.update_buttons()

    def update_buttons(self):
        self.prev_btn.disabled = (self.current_page == 0)
        self.next_btn.disabled = (self.current_page >= len(self.pages) - 1)
        self.page_indicator.label = f"Trang {self.current_page + 1}/{len(self.pages)}"

    def get_embed(self):
        embed = discord.Embed(
            title=f"📖 {self.title}",
            description=self.pages[self.current_page],
            color=0x8b5cf6
        )
        embed.set_footer(text=f"Novel AI Studio • Bộ: {self.novel_key} • Trang {self.current_page + 1}/{len(self.pages)}")
        return embed

    @discord.ui.button(label="◀ Trước", style=discord.ButtonStyle.secondary, custom_id="prev_btn")
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Trang 1/1", style=discord.ButtonStyle.primary, disabled=True, custom_id="page_indicator")
    async def page_indicator(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="Sau ▶", style=discord.ButtonStyle.secondary, custom_id="next_btn")
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

@bot.event
async def on_ready():
    print(f"🎉 DISCORD BOT ĐÃ ĐĂNG NHẬP THÀNH CÔNG: {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"⚡ Đã đồng bộ {len(synced)} Slash Commands thành công!")
    except Exception as e:
        print(f"Lỗi đồng bộ lệnh: {e}")
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="/doc | /play radio 🎙️"
        )
    )

@bot.tree.command(name="help", description="📖 Hướng dẫn sử dụng toàn bộ lệnh của Novel AI Bot")
async def cmd_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 NOVEL AI DISCORD STUDIO — HƯỚNG DẪN LỆNH",
        description="Chào mừng bạn đến với Trạm Radio & Thư Viện Light Novel AI!",
        color=0x38bdf8
    )
    embed.add_field(name="📚 /truyen", value="Xem danh sách 3 bộ truyện & tiến độ dịch hiện tại.", inline=False)
    embed.add_field(name="📖 /doc <chuong> [truyen]", value="Đọc chương truyện trực tiếp dạng Embeds có phân trang.", inline=False)
    embed.add_field(name="🎙️ /play <chuong> [giong] [truyen]", value="Phát Radio Audio giọng đọc (Hoài My / Nam Minh) trong Voice Channel.", inline=False)
    embed.add_field(name="⏹️ /stop", value="Dừng phát audio và rời khỏi Voice Channel.", inline=False)
    embed.add_field(name="⏸️ /pause | /resume", value="Tạm dừng hoặc tiếp tục nghe đọc audio.", inline=False)
    embed.add_field(name="🧠 /lore <tu_khoa> [truyen]", value="Tra cứu thông tin nhân vật, thiên chức, phe phái từ Canon Glossary.", inline=False)
    embed.add_field(name="🎲 /random", value="Trích dẫn ngẫu nhiên một câu nói ấn tượng trong truyện.", inline=False)
    embed.set_footer(text="Novel AI Studio V3.0 • Phát triển bởi DeepMind Agent")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="truyen", description="📚 Xem danh sách các bộ truyện và tiến độ dịch")
async def cmd_truyen(interaction: discord.Interaction):
    novels = get_all_novels()
    embed = discord.Embed(
        title="📚 DANH SÁCH BỘ TRUYỆN TRONG THƯ VIỆN",
        description=f"Tổng số bộ truyện đang quản lý: **{len(novels)} tác phẩm**",
        color=0x10b981
    )
    for k, v in novels.items():
        embed.add_field(
            name=f"📖 {v['title']}",
            value=f"• **Mã bộ:** `{k}`\n• **Số chương đã dịch:** `{v['chapters_count']}` tập\n• **Trạng thái:** 🟢 Đang hoạt động",
            inline=False
        )
    embed.set_footer(text="Mẹo: Gõ /doc chuong:1 để bắt đầu đọc tập đầu tiên!")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="doc", description="📖 Đọc một chương Light Novel trực tiếp trong Discord")
@app_commands.describe(chuong="Số thứ tự tập/chương cần đọc (VD: 294)", truyen="Mã bộ truyện (mặc định: Chu_Thuat_Su_Dung_Gia)")
async def cmd_doc(interaction: discord.Interaction, chuong: int, truyen: str = DEFAULT_NOVEL):
    title, content = load_chapter_content(truyen, chuong)
    if not title:
        await interaction.response.send_message(f"❌ {content}", ephemeral=True)
        return

    paragraphs = content.split("\n\n")
    pages = []
    current_chunk = ""

    for p in paragraphs:
        if len(current_chunk) + len(p) < 1600:
            current_chunk += p + "\n\n"
        else:
            if current_chunk.strip():
                pages.append(current_chunk.strip())
            current_chunk = p + "\n\n"
    if current_chunk.strip():
        pages.append(current_chunk.strip())

    if not pages:
        pages = ["Nội dung chương trống!"]

    view = ChapterPaginationView(title, pages, truyen)
    await interaction.response.send_message(embed=view.get_embed(), view=view)

@bot.tree.command(name="play", description="🎙️ Phát Radio Audio chương truyện trong phòng Voice Channel")
@app_commands.describe(chuong="Số thứ tự tập cần đọc (VD: 294)", giong="Giọng đọc: nu (Hoài My) hoặc nam (Nam Minh)", truyen="Mã bộ truyện")
@app_commands.choices(giong=[
    app_commands.Choice(name="Nữ truyền cảm (Hoài My)", value="nu"),
    app_commands.Choice(name="Nam trầm ấm (Nam Minh)", value="nam")
])
async def cmd_play(interaction: discord.Interaction, chuong: int, giong: app_commands.Choice[str] = None, truyen: str = DEFAULT_NOVEL):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("❌ Bạn cần tham gia vào một **Phòng Voice (Voice Channel)** trước khi gõ lệnh này!", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    title, content = load_chapter_content(truyen, chuong)
    if not title:
        await interaction.followup.send(f"❌ {content}")
        return

    voice_key = giong.value if giong else "nu"
    voice_name = VOICES.get(voice_key, "vi-VN-HoaiMyNeural")
    voice_label = "Hoài My (Nữ)" if voice_key == "nu" else "Nam Minh (Nam)"

    clean_text = re.sub(r'#+\s*', '', content)
    clean_text = re.sub(r'\*+', '', clean_text)
    clean_text = re.sub(r'`+', '', clean_text)
    clean_text = f"Đang phát {title}. Giọng đọc {voice_label}. " + clean_text

    if len(clean_text) > 10000:
        clean_text = clean_text[:10000] + "... Nội dung chương còn tiếp tục trên web reader."

    temp_mp3 = Path(tempfile.gettempdir()) / f"novel_voice_{chuong}_{voice_key}.mp3"
    try:
        communicate = edge_tts.Communicate(clean_text, voice_name)
        await communicate.save(str(temp_mp3))
    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi sinh giọng đọc Edge-TTS: {e}")
        return

    voice_channel = interaction.user.voice.channel
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)

    if voice_client and voice_client.is_connected():
        if voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)
    else:
        try:
            voice_client = await voice_channel.connect()
        except Exception as e:
            await interaction.followup.send(f"❌ Không thể kết nối vào Voice Channel: {e}")
            return

    if voice_client.is_playing():
        voice_client.stop()

    audio_source = discord.FFmpegPCMAudio(str(temp_mp3), executable=FFMPEG_PATH)
    voice_client.play(audio_source)

    embed = discord.Embed(
        title="🎙️ ĐANG PHÁT RADIO AUDIO TRUYỆN TRONG VOICE",
        description=f"📖 **{title}**\n\n🔊 **Kênh:** `{voice_channel.name}`\n🗣️ **Giọng đọc:** `{voice_label}`\n📚 **Bộ truyện:** `{truyen}`",
        color=0xec4899
    )
    embed.set_footer(text="Gõ /stop để dừng phát • /pause để tạm dừng")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="stop", description="⏹️ Dừng phát audio và rời phòng Voice")
async def cmd_stop(interaction: discord.Interaction):
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if voice_client and voice_client.is_connected():
        if voice_client.is_playing():
            voice_client.stop()
        await voice_client.disconnect()
        await interaction.response.send_message("⏹️ Đã dừng phát và rời khỏi phòng Voice!")
    else:
        await interaction.response.send_message("⚠️ Bot hiện không ở trong phòng Voice nào!", ephemeral=True)

@bot.tree.command(name="pause", description="⏸️ Tạm dừng phát audio trong Voice")
async def cmd_pause(interaction: discord.Interaction):
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await interaction.response.send_message("⏸️ Đã tạm dừng đọc truyện!")
    else:
        await interaction.response.send_message("⚠️ Không có âm thanh nào đang phát để tạm dừng!", ephemeral=True)

@bot.tree.command(name="resume", description="▶️ Tiếp tục phát audio trong Voice")
async def cmd_resume(interaction: discord.Interaction):
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await interaction.response.send_message("▶️ Đang tiếp tục phát audio!")
    else:
        await interaction.response.send_message("⚠️ Bot không ở trạng thái tạm dừng!", ephemeral=True)

@bot.tree.command(name="lore", description="🧠 Tra cứu Bách khoa Lore Canon (Nhân vật & Thuật ngữ)")
@app_commands.describe(tu_khoa="Tên nhân vật hoặc thuật ngữ cần tra (VD: Momokawa, Souma, Ruinhilde)", truyen="Bộ truyện")
async def cmd_lore(interaction: discord.Interaction, tu_khoa: str, truyen: str = DEFAULT_NOVEL):
    results = search_lore(truyen, tu_khoa)
    if not results:
        await interaction.response.send_message(f"🔍 Không tìm thấy thông tin nào khớp với từ khóa **'{tu_khoa}'** trong bộ `{truyen}`!", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"🧠 TRA CỨU CANON LORE: '{tu_khoa}'",
        description=f"Tìm thấy **{len(results)} kết quả** trong Bách khoa toàn thư:",
        color=0x8b5cf6
    )

    for item in results[:5]:
        embed.add_field(
            name=f"[{item['type']}] {item['name']} ({item['id']})",
            value=f"• **Thiên chức / Loại:** {item['role']}\n• **Trạng thái:** `{item['status']}`\n• **Mô tả:** {item['desc'][:200]}...",
            inline=False
        )
    embed.set_footer(text="Dữ liệu đồng bộ trực tiếp từ kho Canon Engine V3.0")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="random", description="🎲 Nhận một câu trích dẫn hoặc sự kiện ngẫu nhiên trong truyện")
async def cmd_random(interaction: discord.Interaction):
    quotes = [
        ("Momokawa Kotarou", "『Ngươi nghĩ Chú thuật sư là kẻ yếu ớt sao? Khi ngươi nhận ra sự tồn tại của nguyền rủa, cái chết đã cận kề rồi.』", "Tập 52"),
        ("Futaba Meiko", "『Dù cả thế giới coi Kotarou-kun là kẻ thù, tớ vẫn sẽ luôn đứng về phía cậu.』", "Tập 180"),
        ("Souma Yuuto", "『Ta là Dũng Giả được Thánh Kiếm lựa chọn. Ta sẽ bảo vệ tất cả mọi người!』", "Tập 15"),
        ("Tendou Ryuuichi", "『Kẻ có thực lực mới có quyền định đoạt trật tự tại ngọn Tháp này.』", "Tập 88"),
        ("Aurelia Rosenberg", "『Hủy hôn ước sao? Tốt thôi, cuối cùng ta cũng được tận hưởng cuộc sống tự do và đồ ngọt rồi!』", "Tập 1")
    ]
    char, quote, ep = random.choice(quotes)
    embed = discord.Embed(
        title="🎲 TRÍCH DẪN NOVEL ẤN TƯỢNG",
        description=f"> *{quote}*",
        color=0xf59e0b
    )
    embed.add_field(name="🗣️ Nhân vật", value=f"**{char}**", inline=True)
    embed.add_field(name="📖 Xuất hiện", value=f"`{ep}`", inline=True)
    await interaction.response.send_message(embed=embed)

if __name__ == "__main__":
    if not TOKEN:
        print("❌ LỖI: Chưa có Discord Bot Token trong discord_bot_config.json!")
        sys.exit(1)
    
    print("🚀 Đang khởi động Discord Novel AI Studio Bot...")
    bot.run(TOKEN)
