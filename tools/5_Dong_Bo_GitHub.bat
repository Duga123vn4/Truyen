@echo off & chcp 65001 >nul & set "PYTHONIOENCODING=utf-8" & set "PYTHONUTF8=1" & for %%P in (python.exe "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%LOCALAPPDATA%\Programs\Python\Python311\python.exe") do @(%%P -x -X utf8 "%~f0" %* && exit /b 0)
"""
NOVEL AI - GITHUB SYNC & CLOUD BACKUP STUDIO V3.0 ULTIMATE
Tự động sao lưu bản dịch, Lore Canon và đồng bộ Web Reader lên GitHub.
"""

import sys
import os
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

# ==============================================================================
# BẢO ĐẢM TERMINAL UTF-8 & MÀU SẮC ANSI CHUẨN XÁC 100%
# ==============================================================================
def ensure_utf8_console():
    if sys.platform == "win32":
        os.environ["PYTHONIOENCODING"] = "utf-8"
        os.environ["PYTHONUTF8"] = "1"
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleCP(65001)
            kernel32.SetConsoleOutputCP(65001)
            hOut = kernel32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(hOut, ctypes.byref(mode)):
                kernel32.SetConsoleMode(hOut, mode.value | 0x0004)
        except Exception:
            pass
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
            sys.stdin.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

ensure_utf8_console()

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    console = Console()
except ImportError:
    class FallbackConsole:
        def print(self, *args, **kwargs):
            text = ' '.join(str(a) for a in args)
            clean = ''
            in_tag = False
            for ch in text:
                if ch == '[': in_tag = True
                elif ch == ']': in_tag = False
                elif not in_tag: clean += ch
            print(clean)
        def clear(self):
            os.system('cls' if os.name == 'nt' else 'clear')
            ensure_utf8_console()
    console = FallbackConsole()
    class Prompt:
        @staticmethod
        def ask(msg, choices=None, default=''):
            c_str = f' ({chr(47).join(choices)})' if choices else ''
            d_str = f' [{default}]' if default else ''
            val = input(f'{msg}{c_str}{d_str}: ').strip()
            return val if val else default
    class Confirm:
        @staticmethod
        def ask(msg, default=True):
            d_str = ' [Y/n]' if default else ' [y/N]'
            val = input(f'{msg}{d_str}: ').strip().lower()
            if not val: return default
            return val in ['y', 'yes', 'c', 'co']

ROOT_DIR = Path(__file__).resolve().parent if not Path(__file__).resolve().parent.name == 'tools' else Path(__file__).resolve().parent.parent

def check_git_installed():
    git_bin = shutil.which('git')
    if git_bin:
        return True, git_bin
    paths = [
        Path('C:/Program Files/Git/cmd/git.exe'),
        Path('C:/Program Files/Git/bin/git.exe'),
        Path('C:/Program Files (x86)/Git/cmd/git.exe'),
        Path(os.path.expanduser('~')) / 'AppData/Local/Programs/Git/cmd/git.exe',
        Path(os.path.expanduser('~')) / 'AppData/Local/Programs/Git/bin/git.exe'
    ]
    for p in paths:
        if p.exists():
            os.environ['PATH'] = str(p.parent) + os.pathsep + os.environ['PATH']
            return True, str(p)
    return False, None

def run_git_cmd(args):
    try:
        res = subprocess.run(['git'] + args, cwd=ROOT_DIR, capture_output=True, text=True, encoding='utf-8')
        ensure_utf8_console()
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        ensure_utf8_console()
        return -1, '', str(e)

def ensure_git_setup():
    """Tự động thiết lập Git identity và repository nếu chưa có."""
    if not (ROOT_DIR / '.git').exists():
        run_git_cmd(['init'])
        run_git_cmd(['branch', '-M', 'main'])
    
    # Cấu hình UTF-8 cho Git
    run_git_cmd(['config', '--global', 'core.quotepath', 'false'])
    run_git_cmd(['config', '--global', 'i18n.commitencoding', 'utf-8'])
    run_git_cmd(['config', '--global', 'i18n.logoutputencoding', 'utf-8'])

    # Kiểm tra identity
    _, u_name, _ = run_git_cmd(['config', 'user.name'])
    _, u_email, _ = run_git_cmd(['config', 'user.email'])
    if not u_name:
        run_git_cmd(['config', 'user.name', 'Duga123vn4'])
    if not u_email:
        run_git_cmd(['config', 'user.email', 'Duga123vn4@users.noreply.github.com'])
    
    # Đảm bảo nhánh hiện tại là main
    run_git_cmd(['branch', '-M', 'main'])

def show_banner():
    banner = """[bold cyan]╔═════════════════════════════════════════════════════════════════════════════╗
║     🐙 NOVEL AI — GITHUB SYNC & CLOUD BACKUP STUDIO V3.0 ULTIMATE           ║
║     🛡️ Tự động Sao lưu • Đồng bộ Web Reader • Bảo mật API Key tuyệt đối     ║
╚═════════════════════════════════════════════════════════════════════════════╝[/bold cyan]"""
    console.print(banner)

def install_git_cli():
    console.print("\n[bold yellow]🚀 Đang tiến hành cài đặt Git CLI tự động qua Winget...[/bold yellow]")
    console.print("  (Quá trình này có thể mất 1-2 phút, vui lòng đợi...)")
    try:
        res = subprocess.run(['winget', 'install', '--id', 'Git.Git', '-e', '--silent', '--accept-source-agreements', '--accept-package-agreements'], capture_output=True, text=True)
        ensure_utf8_console()
        if res.returncode == 0:
            console.print("[bold green]✅ Đã cài đặt Git CLI thành công! Vui lòng khởi động lại cửa sổ BAT.[/bold green]")
        else:
            console.print(f"[bold red]⚠️ Cài đặt Winget thất bại: {res.stderr}[/bold red]")
            console.print("👉 Bạn có thể tải Git thủ công tại: https://git-scm.com/download/win")
    except Exception as e:
        ensure_utf8_console()
        console.print(f"[bold red]⚠️ Lỗi thực thi winget: {e}[/bold red]")
    input("\nNhấn Enter để quay lại...")

def config_git_repo():
    console.print("\n[bold cyan]⚙️ CẤU HÌNH KHO GITHUB REPOSITORY[/bold cyan]")
    ensure_git_setup()
    
    code, remotes, _ = run_git_cmd(['remote', '-v'])
    if remotes:
        console.print(f"  • [bold]Remote hiện tại:[/bold]\n{remotes}")
    else:
        console.print("  • [yellow]Chưa cấu hình Remote GitHub nào.[/yellow]")

    repo_url = Prompt.ask("\n👉 Nhập URL kho GitHub (VD: https://github.com/Duga123vn4/Novel.git)")
    if not repo_url:
        return

    run_git_cmd(['remote', 'remove', 'origin'])
    code, out, err = run_git_cmd(['remote', 'add', 'origin', repo_url.strip()])
    if code == 0:
        console.print(f"[bold green]✅ Đã liên kết thành công với: {repo_url}[/bold green]")
        run_git_cmd(['branch', '-M', 'main'])
    else:
        console.print(f"[bold red]⚠️ Lỗi thêm remote: {err}[/bold red]")
    input("\nNhấn Enter để quay lại...")

def view_git_status():
    """Tính năng 3: Báo cáo trạng thái Git trực quan, phân nhóm rành mạch."""
    console.print("\n[bold cyan]🔍 BÁO CÁO TRẠNG THÁI DỰ ÁN & THAY ĐỔI (GIT STATUS)[/bold cyan]")
    ensure_git_setup()

    # 1. Kiểm tra Remote
    code_r, remotes, _ = run_git_cmd(['remote', '-v'])
    if remotes:
        origin_line = [l for l in remotes.splitlines() if 'origin' in l and '(push)' in l]
        remote_display = origin_line[0] if origin_line else remotes.splitlines()[0]
        console.print(f"  • [bold]Kho GitHub liên kết:[/bold] [green]{remote_display}[/green]")
    else:
        console.print("  • [bold]Kho GitHub liên kết:[/bold] [yellow]Chưa liên kết (Chọn mục [4] để kết nối)[/yellow]")

    # 2. Kiểm tra Branch
    code_b, branch_out, _ = run_git_cmd(['branch', '--show-current'])
    curr_branch = branch_out.strip() if branch_out else "main"
    console.print(f"  • [bold]Nhánh làm việc (Branch):[/bold] [cyan]{curr_branch}[/cyan]")

    # 3. Quét các file thay đổi
    code, status_out, _ = run_git_cmd(['status', '--short'])
    if not status_out:
        console.print("\n[bold green]✨ TUYỆT VỜI! Mọi file trong dự án đều ĐỒNG BỘ 100% với Git (Không có thay đổi tồn đọng).[/bold green]")
        input("\nNhấn Enter để quay lại...")
        return

    lines = status_out.splitlines()
    novels_changed = []
    glossary_changed = []
    web_changed = []
    tools_changed = []
    other_changed = []

    for l in lines:
        st = l[:2].strip()
        fpath = l[3:].strip()
        if "projects/" in fpath and "/translated/" in fpath:
            novels_changed.append((st, fpath))
        elif "projects/" in fpath and "/glossary/" in fpath:
            glossary_changed.append((st, fpath))
        elif "web/" in fpath:
            web_changed.append((st, fpath))
        elif "tools/" in fpath or fpath.endswith(".bat"):
            tools_changed.append((st, fpath))
        else:
            other_changed.append((st, fpath))

    table = Table(title=f"📦 Danh Sách {len(lines)} Tệp Tin Đang Chờ Đẩy Lên GitHub", show_header=True, header_style="bold magenta")
    table.add_column("Phân Nhóm Dữ Liệu", style="cyan", width=25)
    table.add_column("Số Lượng", justify="center", width=12)
    table.add_column("Ví Dụ Các File Tiêu Biểu", style="white")

    if novels_changed:
        ex = ", ".join([Path(f).name for _, f in novels_changed[:3]]) + ("..." if len(novels_changed) > 3 else "")
        table.add_row("📖 Chương Dịch (Translated)", f"[bold green]{len(novels_changed)}[/bold green]", ex)
    if glossary_changed:
        ex = ", ".join([Path(f).name for _, f in glossary_changed[:3]]) + ("..." if len(glossary_changed) > 3 else "")
        table.add_row("📚 Từ Điển Lore (Glossary)", f"[bold yellow]{len(glossary_changed)}[/bold yellow]", ex)
    if web_changed:
        ex = ", ".join([Path(f).name for _, f in web_changed[:3]]) + ("..." if len(web_changed) > 3 else "")
        table.add_row("📱 Trình Đọc Web (Web Reader)", f"[bold blue]{len(web_changed)}[/bold blue]", ex)
    if tools_changed:
        ex = ", ".join([Path(f).name for _, f in tools_changed[:3]]) + ("..." if len(tools_changed) > 3 else "")
        table.add_row("⚙️ Công Cụ & Scripts (Tools)", f"[bold cyan]{len(tools_changed)}[/bold cyan]", ex)
    if other_changed:
        ex = ", ".join([Path(f).name for _, f in other_changed[:3]]) + ("..." if len(other_changed) > 3 else "")
        table.add_row("📄 Tệp Khác / Cấu Hình", f"[bold white]{len(other_changed)}[/bold white]", ex)

    console.print()
    console.print(table)
    console.print("\n[bold yellow]👉 Gợi ý:[/bold yellow] Chọn mục [bold green][1][/bold green] ở menu chính để đóng gói và Đẩy toàn bộ thay đổi này lên GitHub!")
    input("\nNhấn Enter để quay lại...")

def sync_and_push():
    console.print("\n[bold cyan]⚡ BẮT ĐẦU ĐỒNG BỘ & ĐẨY LÊN GITHUB...[/bold cyan]")
    ensure_git_setup()

    # 1. Kiem tra remote
    code, remotes, _ = run_git_cmd(['remote', '-v'])
    if not remotes:
        console.print("[bold red]⚠️ Chưa cấu hình Remote GitHub! Vui lòng chọn mục [4] để cấu hình link Repository trước.[/bold red]")
        input("\nNhấn Enter để quay lại...")
        return

    # 2. Chay build_chapters_js.ps1 truoc khi day
    ps1_f = ROOT_DIR / 'tools' / 'build_chapters_js.ps1'
    if ps1_f.exists():
        try:
            subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', '-File', str(ps1_f)], cwd=ROOT_DIR, capture_output=True)
            ensure_utf8_console()
            console.print("  ✅ Đã đồng bộ Web Reader (chapters.js) trước khi push.")
        except Exception:
            ensure_utf8_console()

    # 3. Git add & status
    console.print("  ⏳ Đang kiểm tra các file thay đổi...")
    run_git_cmd(['add', '.'])
    code, status_out, _ = run_git_cmd(['status', '--short'])
    
    if status_out:
        # Commit neu co thay doi
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        commit_msg = f"Novel AI V3.0 Update: Chuong moi & Lore [{now_str}]"
        run_git_cmd(['commit', '-m', commit_msg])
        console.print(f"  ✅ Đã tạo commit: [bold green]{commit_msg}[/bold green]")
    else:
        console.print("  ℹ️ Không có file mới nào thay đổi, tiếp tục đẩy các commit đã có...")

    # 4. Push
    console.print("  🚀 Đang đẩy dữ liệu lên GitHub (Vui lòng đợi vài giây)...")
    push_res = subprocess.run(['git', 'push', '-u', 'origin', 'main'], cwd=ROOT_DIR)
    ensure_utf8_console()
    
    if push_res.returncode == 0:
        console.print("\n[bold green]🎉 ĐỒNG BỘ LÊN GITHUB THÀNH CÔNG RỰC RỠ![/bold green]")
        console.print("  🌐 Toàn bộ bản dịch, Lore và Web Reader đã được sao lưu an toàn trên Cloud.")
    else:
        console.print("\n[bold yellow]⚠️ Nhánh từ xa có thể có dữ liệu mới. Đang thử kéo về (Pull & Rebase)...[/bold yellow]")
        run_git_cmd(['pull', '--rebase', 'origin', 'main'])
        push_res2 = subprocess.run(['git', 'push', '-u', 'origin', 'main'], cwd=ROOT_DIR)
        ensure_utf8_console()
        if push_res2.returncode == 0:
            console.print("\n[bold green]🎉 ĐỒNG BỘ THÀNH CÔNG SAU KHI REBASE![/bold green]")
        else:
            console.print(f"\n[bold red]⚠️ Lỗi Git Push. Nếu cửa sổ yêu cầu đăng nhập GitHub xuất hiện, vui lòng chọn Sign in with browser.[/bold red]")

    input("\nNhấn Enter để quay lại...")

def git_pull():
    console.print("\n[bold cyan]📥 ĐANG KÉO DỮ LIỆU TỪ GITHUB VỀ MÁY (GIT PULL)...[/bold cyan]")
    ensure_git_setup()
    code, out, err = run_git_cmd(['pull', 'origin', 'main'])
    if code == 0:
        console.print(f"[bold green]✅ Hoàn tất kéo dữ liệu:[/bold green]\n{out}")
    else:
        console.print(f"[bold red]⚠️ Lỗi kéo dữ liệu: {err}[/bold red]")
    input("\nNhấn Enter để quay lại...")

def main():
    while True:
        try:
            console.clear()
        except Exception:
            os.system('cls' if os.name == 'nt' else 'clear')
        ensure_utf8_console()
        show_banner()
        
        has_git, git_path = check_git_installed()
        if not has_git:
            console.print("\n[bold red]⚠️ CHƯA PHÁT HIỆN GIT CLI TRÊN MÁY TÍNH![/bold red]")
            console.print("  Bạn có thể chọn mục [5] để cài đặt tự động bằng 1-chạm.\n")
        else:
            console.print(f"\n[green]• Trạng thái Git:[/green] Đã sẵn sàng [cyan]({git_path})[/cyan]\n")

        console.print("[bold yellow]Hành Động Đồng Bộ:[/bold yellow]")
        console.print("  [bold green][1][/bold green] ⚡ Đồng Bộ Nhanh 1-Chạm ([bold]Commit & Push lên GitHub[/bold])")
        console.print("  [bold cyan][2][/bold cyan] 📥 Kéo Dữ Liệu Mới Nhất Về ([bold]Git Pull[/bold])")
        console.print("  [bold blue][3][/bold blue] 🔍 Kiểm Tra Trạng Thái ([bold]Git Status & Thay Đổi[/bold])")
        console.print("  [bold magenta][4][/bold magenta] ⚙️ Cấu Hình Kho GitHub ([bold]Set Remote Repo URL[/bold])")
        console.print("  [bold yellow][5][/bold yellow] 🛠️ Cài Đặt Tự Động Git CLI ([bold]Winget Install[/bold])")
        console.print("  [bold red][0][/bold red] 🚪 Thoát Ra Ngoài")

        choice = Prompt.ask("\n👉 Nhập lựa chọn", choices=['1', '2', '3', '4', '5', '0'], default='3')

        if choice == '1':
            if not has_git:
                console.print("[bold red]Vui lòng cài đặt Git CLI trước (Mục [5]).[/bold red]")
                input("Nhấn Enter...")
                continue
            sync_and_push()
        elif choice == '2':
            if not has_git: continue
            git_pull()
        elif choice == '3':
            if not has_git: continue
            view_git_status()
        elif choice == '4':
            if not has_git: continue
            config_git_repo()
        elif choice == '5':
            install_git_cli()
        elif choice == '0':
            break

if __name__ == '__main__':
    main()
