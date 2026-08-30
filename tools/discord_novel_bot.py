# -*- coding: utf-8 -*-
"""
🤖 NOVEL AI DISCORD BOT V3.0 ULTIMATE (DUAL-MODE HYBRID)
- Hỗ trợ cả lệnh Slash (/) và lệnh gõ nhanh (!help, !doc, !play, !lore, !truyen)
- Tự động đồng bộ lệnh tức thì cho tất cả Server Discord
- Phát Radio Audio TTS (Giọng Hoài My / Nam Minh) trong Voice Channel
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
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ==============================================================================
# HÀM TRỢ GIÚP DỮ LIỆU NOVEL
# ==============================================================================
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

# ==============================================================================
# UI COMPONENTS (PAGINATION VIEW)
# ==============================================================================
class ChapterPaginationView(discord.ui.View):
    def __init__(self, title, pages, novel_key):
        super().__init__(timeout=300)
        self.title = title
        self.pages = pages
        self.novel_key = novel_key
        self.current_page = 0
        
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

# ==============================================================================
# DISCORD EVENTS & SYNC
# ==============================================================================
@bot.event
async def on_ready():
    print(f"🎉 DISCORD BOT ĐÃ ĐĂNG NHẬP: {bot.user} (ID: {bot.user.id})")
    
    # Đồng bộ Slash Commands cho từng Guild trực tiếp để có hiệu lực TỨC THÌ
    for guild in bot.guilds:
        try:
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"⚡ Đã đồng bộ {len(synced)} Slash Commands tức thì cho Server: {guild.name}")
        except Exception as e:
            print(f"⚠️ Lỗi đồng bộ Server {guild.name}: {e}")

    try:
        global_synced = await bot.tree.sync()
        print(f"🌍 Đã đồng bộ {len(global_synced)} Global Commands!")
    except Exception as e:
        print(f"⚠️ Global sync: {e}")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="!help | !doc | !play 🎙️"
        )
    )
    print("🟢 BOT ĐÃ SẴN SÀNG 100% ĐỂ NHẬN LỆNH!")

# ==============================================================================
# LỆNH TIỆN ÍCH DUAL-MODE (CẢ ! VÀ /)
# ==============================================================================

# 1. HELP COMMAND
def make_help_embed():
    embed = discord.Embed(
        title="🤖 NOVEL AI DISCORD STUDIO — HƯỚNG DẪN LỆNH",
        description="Chào mừng bạn đến với Trạm Radio & Thư Viện Light Novel AI!\n*Hỗ trợ cả lệnh gõ **`!`** và lệnh Slash **`/`**!*",
        color=0x38bdf8
    )
    embed.add_field(name="📚 !truyen (hoặc /truyen)", value="Xem danh sách 3 bộ truyện & số chương đã dịch.", inline=False)
    embed.add_field(name="📖 !doc <số_chương> (hoặc /doc)", value="Đọc chương truyện dạng Embeds có nút lật trang `◀ Trước` / `Sau ▶`.", inline=False)
    embed.add_field(name="🎙️ !play <số_chương> (hoặc /play)", value="Phát Radio Audio giọng đọc (Hoài My / Nam Minh) trong phòng Voice.", inline=False)
    embed.add_field(name="⏹️ !stop (hoặc /stop)", value="Dừng phát audio và rời khỏi phòng Voice.", inline=False)
    embed.add_field(name="⏸️ !pause | !resume", value="Tạm dừng hoặc tiếp tục nghe đọc audio.", inline=False)
    embed.add_field(name="🧠 !lore <tên> (hoặc /lore)", value="Tra cứu thông tin nhân vật, thiên chức, phe phái từ Canon Glossary.", inline=False)
    embed.add_field(name="🎲 !random (hoặc /random)", value="Trích dẫn ngẫu nhiên một câu nói ấn tượng trong truyện.", inline=False)
    embed.set_footer(text="Novel AI Studio V3.0 • Phát triển bởi DeepMind Agent")
    return embed

@bot.tree.command(name="help", description="📖 Hướng dẫn sử dụng toàn bộ lệnh của Novel AI Bot")
async def slash_help(interaction: discord.Interaction):
    await interaction.response.send_message(embed=make_help_embed())

@bot.command(name="help")
async def prefix_help(ctx):
    await ctx.send(embed=make_help_embed())

# 2. TRUYEN COMMAND
def make_truyen_embed():
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
    embed.set_footer(text="Mẹo: Gõ !doc 1 để bắt đầu đọc tập đầu tiên!")
    return embed

@bot.tree.command(name="truyen", description="📚 Xem danh sách các bộ truyện và tiến độ dịch")
async def slash_truyen(interaction: discord.Interaction):
    await interaction.response.send_message(embed=make_truyen_embed())

@bot.command(name="truyen")
async def prefix_truyen(ctx):
    await ctx.send(embed=make_truyen_embed())

# 3. DOC COMMAND
@bot.tree.command(name="doc", description="📖 Đọc một chương Light Novel trực tiếp trong Discord")
@app_commands.describe(chuong="Số thứ tự tập/chương cần đọc (VD: 294)", truyen="Mã bộ truyện")
async def slash_doc(interaction: discord.Interaction, chuong: int, truyen: str = DEFAULT_NOVEL):
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
            if current_chunk.strip(): pages.append(current_chunk.strip())
            current_chunk = p + "\n\n"
    if current_chunk.strip(): pages.append(current_chunk.strip())
    if not pages: pages = ["Nội dung chương trống!"]

    view = ChapterPaginationView(title, pages, truyen)
    await interaction.response.send_message(embed=view.get_embed(), view=view)

@bot.command(name="doc")
async def prefix_doc(ctx, chuong: int = 1, truyen: str = DEFAULT_NOVEL):
    title, content = load_chapter_content(truyen, chuong)
    if not title:
        await ctx.send(f"❌ {content}")
        return

    paragraphs = content.split("\n\n")
    pages = []
    current_chunk = ""
    for p in paragraphs:
        if len(current_chunk) + len(p) < 1600:
            current_chunk += p + "\n\n"
        else:
            if current_chunk.strip(): pages.append(current_chunk.strip())
            current_chunk = p + "\n\n"
    if current_chunk.strip(): pages.append(current_chunk.strip())
    if not pages: pages = ["Nội dung chương trống!"]

    view = ChapterPaginationView(title, pages, truyen)
    await ctx.send(embed=view.get_embed(), view=view)

# 4. PLAY COMMAND (VOICE RADIO TTS)
async def handle_play(channel, user_voice_channel, guild, chuong, giong_key, truyen, send_func):
    if not user_voice_channel:
        await send_func("❌ Bạn cần tham gia vào một **Phòng Voice (Voice Channel)** trước khi dùng lệnh này!")
        return

    title, content = load_chapter_content(truyen, chuong)
    if not title:
        await send_func(f"❌ {content}")
        return

    voice_name = VOICES.get(giong_key, "vi-VN-HoaiMyNeural")
    voice_label = "Hoài My (Nữ)" if giong_key == "nu" else "Nam Minh (Nam)"

    clean_text = re.sub(r'#+\s*', '', content)
    clean_text = re.sub(r'\*+', '', clean_text)
    clean_text = re.sub(r'`+', '', clean_text)
    clean_text = f"Đang phát {title}. Giọng đọc {voice_label}. " + clean_text

    if len(clean_text) > 10000:
        clean_text = clean_text[:10000] + "... Nội dung chương còn tiếp tục trên web reader."

    temp_mp3 = Path(tempfile.gettempdir()) / f"novel_voice_{chuong}_{giong_key}.mp3"
    try:
        communicate = edge_tts.Communicate(clean_text, voice_name)
        await communicate.save(str(temp_mp3))
    except Exception as e:
        await send_func(f"❌ Lỗi sinh giọng đọc Edge-TTS: {e}")
        return

    voice_client = discord.utils.get(bot.voice_clients, guild=guild)
    if voice_client and voice_client.is_connected():
        if voice_client.channel != user_voice_channel:
            await voice_client.move_to(user_voice_channel)
    else:
        try:
            voice_client = await user_voice_channel.connect()
        except Exception as e:
            await send_func(f"❌ Không thể kết nối vào Voice Channel: {e}")
            return

    if voice_client.is_playing():
        voice_client.stop()

    audio_source = discord.FFmpegPCMAudio(str(temp_mp3), executable=FFMPEG_PATH)
    voice_client.play(audio_source)

    embed = discord.Embed(
        title="🎙️ ĐANG PHÁT RADIO AUDIO TRUYỆN TRONG VOICE",
        description=f"📖 **{title}**\n\n🔊 **Kênh:** `{user_voice_channel.name}`\n🗣️ **Giọng đọc:** `{voice_label}`\n📚 **Bộ truyện:** `{truyen}`",
        color=0xec4899
    )
    embed.set_footer(text="Gõ !stop để dừng phát • !pause để tạm dừng")
    await send_func(embed=embed)

@bot.tree.command(name="play", description="🎙️ Phát Radio Audio chương truyện trong phòng Voice Channel")
@app_commands.describe(chuong="Số thứ tự tập cần đọc (VD: 294)", giong="Giọng đọc: nu (Hoài My) hoặc nam (Nam Minh)", truyen="Mã bộ truyện")
@app_commands.choices(giong=[
    app_commands.Choice(name="Nữ truyền cảm (Hoài My)", value="nu"),
    app_commands.Choice(name="Nam trầm ấm (Nam Minh)", value="nam")
])
async def slash_play(interaction: discord.Interaction, chuong: int, giong: app_commands.Choice[str] = None, truyen: str = DEFAULT_NOVEL):
    user_vc = interaction.user.voice.channel if interaction.user.voice else None
    await interaction.response.defer(thinking=True)
    giong_val = giong.value if giong else "nu"
    await handle_play(interaction.channel, user_vc, interaction.guild, chuong, giong_val, truyen, interaction.followup.send)

@bot.command(name="play")
async def prefix_play(ctx, chuong: int = 1, giong: str = "nu", truyen: str = DEFAULT_NOVEL):
    user_vc = ctx.author.voice.channel if ctx.author.voice else None
    await handle_play(ctx.channel, user_vc, ctx.guild, chuong, giong, truyen, ctx.send)

# 5. STOP / PAUSE / RESUME
@bot.tree.command(name="stop", description="⏹️ Dừng phát audio và rời phòng Voice")
async def slash_stop(interaction: discord.Interaction):
    vc = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if vc and vc.is_connected():
        if vc.is_playing(): vc.stop()
        await vc.disconnect()
        await interaction.response.send_message("⏹️ Đã dừng phát và rời khỏi phòng Voice!")
    else:
        await interaction.response.send_message("⚠️ Bot hiện không ở trong phòng Voice nào!", ephemeral=True)

@bot.command(name="stop")
async def prefix_stop(ctx):
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if vc and vc.is_connected():
        if vc.is_playing(): vc.stop()
        await vc.disconnect()
        await ctx.send("⏹️ Đã dừng phát và rời khỏi phòng Voice!")
    else:
        await ctx.send("⚠️ Bot hiện không ở trong phòng Voice nào!")

@bot.command(name="pause")
async def prefix_pause(ctx):
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if vc and vc.is_playing():
        vc.pause()
        await ctx.send("⏸️ Đã tạm dừng đọc truyện!")
    else:
        await ctx.send("⚠️ Không có âm thanh nào đang phát!")

@bot.command(name="resume")
async def prefix_resume(ctx):
    vc = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if vc and vc.is_paused():
        vc.resume()
        await ctx.send("▶️ Đang tiếp tục phát audio!")
    else:
        await ctx.send("⚠️ Bot không ở trạng thái tạm dừng!")

# 6. LORE COMMAND
def make_lore_embed(tu_khoa, truyen):
    results = search_lore(truyen, tu_khoa)
    if not results:
        return None
    embed = discord.Embed(
        title=f"🧠 TRA CỨU CANON LORE: '{tu_khoa}'",
        description=f"Tìm thấy **{len(results)} kết quả** trong Bách khoa toàn thư bộ `{truyen}`:",
        color=0x8b5cf6
    )
    for item in results[:5]:
        embed.add_field(
            name=f"[{item['type']}] {item['name']} ({item['id']})",
            value=f"• **Thiên chức / Loại:** {item['role']}\n• **Trạng thái:** `{item['status']}`\n• **Mô tả:** {item['desc'][:200]}...",
            inline=False
        )
    embed.set_footer(text="Dữ liệu đồng bộ trực tiếp từ kho Canon Engine V3.0")
    return embed

@bot.tree.command(name="lore", description="🧠 Tra cứu Bách khoa Lore Canon (Nhân vật & Thuật ngữ)")
@app_commands.describe(tu_khoa="Tên nhân vật hoặc thuật ngữ cần tra (VD: Momokawa, Souma, Ruinhilde)", truyen="Bộ truyện")
async def slash_lore(interaction: discord.Interaction, tu_khoa: str, truyen: str = DEFAULT_NOVEL):
    embed = make_lore_embed(tu_khoa, truyen)
    if not embed:
        await interaction.response.send_message(f"🔍 Không tìm thấy thông tin nào khớp với từ khóa **'{tu_khoa}'** trong bộ `{truyen}`!", ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed)

@bot.command(name="lore")
async def prefix_lore(ctx, tu_khoa: str = "", truyen: str = DEFAULT_NOVEL):
    if not tu_khoa:
        await ctx.send("⚠️ Vui lòng nhập từ khóa cần tra cứu! (VD: `!lore Momokawa`)")
        return
    embed = make_lore_embed(tu_khoa, truyen)
    if not embed:
        await ctx.send(f"🔍 Không tìm thấy thông tin nào khớp với từ khóa **'{tu_khoa}'** trong bộ `{truyen}`!")
    else:
        await ctx.send(embed=embed)

# 7. RANDOM COMMAND
def make_random_embed():
    quotes = [
        ("Momokawa Kotarou", "『Ngươi nghĩ Chú thuật sư là kẻ yếu ớt sao? Khi ngươi nhận ra sự tồn tại của nguyền rủa, cái chết đã cận kề rồi.』", "Tập 52"),
        ("Futaba Meiko", "『Dù cả thế giới coi Kotarou-kun là kẻ thù, tớ vẫn sẽ luôn đứng về phía cậu.』", "Tập 180"),
        ("Souma Yuuto", "『Ta là Dũng Giả được Thánh Kiếm lựa chọn. Ta sẽ bảo vệ tất cả mọi người!』", "Tập 15"),
        ("Tendou Ryuuichi", "『Kẻ có thực lực mới có quyền định đoạt trật tự tại ngọn Tháp này.』", "Tập 88"),
        ("Aurelia Rosenberg", "『Hủy hôn ước sao? Tốt thôi, cuối cùng ta cũng được tận hưởng cuộc sống tự do và đồ ngọt rồi!』", "Tập 1")
    ]
    char, quote, ep = random.choice(quotes)
    embed = discord.Embed(
        title="🎲 TRÍCH DẪN NOVEL AI ẤN TƯỢNG",
        description=f"> *{quote}*",
        color=0xf59e0b
    )
    embed.add_field(name="🗣️ Nhân vật", value=f"**{char}**", inline=True)
    embed.add_field(name="📖 Xuất hiện", value=f"`{ep}`", inline=True)
    return embed

@bot.tree.command(name="random", description="🎲 Nhận một câu trích dẫn hoặc sự kiện ngẫu nhiên trong truyện")
async def slash_random(interaction: discord.Interaction):
    await interaction.response.send_message(embed=make_random_embed())

@bot.command(name="random")
async def prefix_random(ctx):
    await ctx.send(embed=make_random_embed())

if __name__ == "__main__":
    if not TOKEN:
        print("❌ LỖI: Chưa có Discord Bot Token trong discord_bot_config.json!")
        sys.exit(1)
    
    print("🚀 Đang khởi động Discord Novel AI Studio Bot (Dual-Mode)...")
    bot.run(TOKEN)
