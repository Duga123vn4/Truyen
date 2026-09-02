# -*- coding: utf-8 -*-
"""
Quản lý cấu hình AI, API Keys và lựa chọn Model tự động:
- Google Gemini Free API
- LLMGate (OpenAI Compatible)
"""
import json
import httpx
from typing import Dict, Any, List
from rich.console import Console
from rich.prompt import Prompt, Confirm

from tools.src.core.paths import CONFIG_FILE, LEGACY_CONFIG_FILE

console = Console()

DEFAULT_CONFIG = {
    "active_provider": "llmgate",
    "glossary_mode": "full_cache",
    "gemini_free": {
        "api_key": "",
        "model": "gemini-2.5-flash"
    },
    "llmgate": {
        "api_key": "",
        "base_url": "https://api.llmgate.com/v1",
        "model": "gemini-3.7-flash"
    }
}

def load_config() -> Dict[str, Any]:
    """Tải cấu hình từ ai_config.json hoặc config.json cũ."""
    cfg = DEFAULT_CONFIG.copy()
    fpath = CONFIG_FILE if CONFIG_FILE.exists() else (LEGACY_CONFIG_FILE if LEGACY_CONFIG_FILE.exists() else None)
    
    if fpath and fpath.exists():
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
                # Cập nhật đệ quy nhẹ
                for k, v in user_cfg.items():
                    if isinstance(v, dict) and k in cfg and isinstance(cfg[k], dict):
                        cfg[k].update(v)
                    else:
                        cfg[k] = v
        except Exception:
            pass
    return cfg

def save_config(cfg: Dict[str, Any]) -> None:
    """Lưu cấu hình vào ai_config.json."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

async def fetch_llmgate_models(api_key: str, base_url: str = "https://api.llmgate.com/v1") -> List[str]:
    """Truy vấn danh sách model khả dụng từ LLMGate API."""
    url = f"{base_url.rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                data = res.json()
                models = [m.get("id") for m in data.get("data", []) if "id" in m]
                # Ưu tiên các model phổ biến
                def sort_key(name):
                    n = name.lower()
                    if "gemini-3.7" in n: return 1
                    if "claude-3-7" in n or "sonnet-3-7" in n: return 2
                    if "gemini-2.5" in n or "flash" in n: return 3
                    if "claude-3-5" in n: return 4
                    if "gpt-4o" in n: return 5
                    return 10
                models.sort(key=sort_key)
                return models
    except Exception as e:
        console.print(f"[yellow]⚠️ Không thể tự động lấy danh sách model LLMGate: {e}[/yellow]")
    return []

async def fetch_gemini_models(api_key: str) -> List[str]:
    """Truy vấn danh sách model khả dụng từ Google Gemini API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(url)
            if res.status_code == 200:
                data = res.json()
                models = []
                for m in data.get("models", []):
                    name = m.get("name", "").replace("models/", "")
                    methods = m.get("supportedGenerationMethods", [])
                    if "generateContent" in methods:
                        models.append(name)
                models.sort(reverse=True)
                return models
    except Exception as e:
        console.print(f"[yellow]⚠️ Không thể tự động lấy danh sách model Gemini: {e}[/yellow]")
    return []
