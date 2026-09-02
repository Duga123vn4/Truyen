# -*- coding: utf-8 -*-
"""
Hệ thống định vị đường dẫn thư mục trung tâm của Novel AI Suite.
"""
from pathlib import Path

# Thư mục tools/
TOOLS_DIR = Path(__file__).resolve().parent.parent.parent

# Thư mục gốc Workspace (d:\Novel)
WORKSPACE_DIR = TOOLS_DIR.parent

# Thư mục chứa các bộ truyện
PROJECTS_DIR = WORKSPACE_DIR / "projects"

# Thư mục Web Reader & Diff Studio
WEB_DIR = WORKSPACE_DIR / "web"

# File cấu hình AI
CONFIG_FILE = TOOLS_DIR / "ai_config.json"
LEGACY_CONFIG_FILE = TOOLS_DIR / "config.json"

# Quy tắc phong cách toàn cục
MASTER_STYLE_GUIDE_FILE = TOOLS_DIR / "MASTER_STYLE_GUIDE.md"

# Thư mục Prompts chuyên biệt
PROMPTS_DIR = TOOLS_DIR / "prompts"
DEEP_EDITOR_PROMPT_FILE = PROMPTS_DIR / "deep_editor_system.md"
TRANSLATOR_PROMPT_FILE = PROMPTS_DIR / "translator_system.md"
LORE_MASTER_PROMPT_FILE = PROMPTS_DIR / "lore_master_system.md"
