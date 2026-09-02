# -*- coding: utf-8 -*-
"""
Bộ giao tiếp AI Đa Kênh (Dual-Provider AI Client):
- Google Gemini Free API (native endpoint)
- LLMGate (OpenAI Compatible)
- Quản lý Context Caching, Retry và ghi nhật ký Telemetry (api_usage_log.json)
"""
import time
import json
import asyncio
import httpx
from datetime import datetime
from typing import Dict, Any, Optional

from tools.src.core.paths import WEB_DIR

def log_api_telemetry(
    model: str,
    p_tok: int,
    c_tok: int,
    cached_tok: int,
    elapsed_sec: float,
    chapter_title: str = "",
    chapter_ep: int = 0
):
    """Ghi nhật ký sử dụng token và chi phí thực tế vào web/api_usage_log.json."""
    cost = 0.0
    m_lower = model.lower()
    
    # Tính chi phí tham chiếu theo triệu token ($/M tokens)
    if "flash" in m_lower:
        input_price = 0.15 if cached_tok == 0 else 0.0375
        cost = (p_tok * input_price + c_tok * 0.60) / 1_000_000
    elif "sonnet" in m_lower:
        cost = (p_tok * 3.0 + c_tok * 15.0) / 1_000_000
    elif "gpt-4o" in m_lower:
        cost = (p_tok * 2.5 + c_tok * 10.0) / 1_000_000
    else:
        cost = (p_tok * 0.15 + c_tok * 0.60) / 1_000_000

    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": model,
        "chapter_title": chapter_title,
        "chapter_ep": chapter_ep,
        "elapsed_sec": round(elapsed_sec, 2),
        "input_tokens": p_tok,
        "output_tokens": c_tok,
        "cache_tokens": cached_tok,
        "cost": round(cost, 5)
    }

    log_file = WEB_DIR / "api_usage_log.json"
    data = []
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []

    data.insert(0, entry)
    if len(data) > 1000:
        data = data[:1000]

    try:
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class AIClient:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider = config.get("active_provider", "llmgate")

    @property
    def model(self) -> str:
        """Trả về tên model đang kích hoạt của provider hiện tại."""
        if self.provider == "gemini_free":
            return self.config.get("gemini_free", {}).get("model", "gemini-2.5-flash")
        else:
            return self.config.get("llmgate", {}).get("model", "gemini-3.7-flash")

    async def generate(
        self,
        system_instruction: str,
        user_prompt: str,
        temperature: float = 0.2,
        chapter_title: str = "",
        chapter_ep: int = 0
    ) -> str:
        """Gửi prompt tới AI và nhận kết quả văn bản."""
        if self.provider == "gemini_free":
            return await self._call_gemini_free(system_instruction, user_prompt, temperature, chapter_title, chapter_ep)
        else:
            return await self._call_llmgate(system_instruction, user_prompt, temperature, chapter_title, chapter_ep)

    async def _call_gemini_free(
        self,
        system_instruction: str,
        user_prompt: str,
        temperature: float,
        chapter_title: str = "",
        chapter_ep: int = 0
    ) -> str:
        gemini_cfg = self.config.get("gemini_free", {})
        api_key = gemini_cfg.get("api_key", "").strip()
        model = gemini_cfg.get("model", "gemini-2.5-flash").strip()

        if not api_key:
            raise ValueError("Chưa cấu hình API Key cho Google Gemini Free. Vui lòng vào Cài Đặt (Menu 9) để nhập key.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        payload = {
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 8192
            }
        }

        t0 = time.time()
        async with httpx.AsyncClient(timeout=120.0) as client:
            for attempt in range(3):
                try:
                    res = await client.post(url, json=payload)
                    if res.status_code == 200:
                        elapsed_req = time.time() - t0
                        data = res.json()
                        usage = data.get("usageMetadata", {})
                        p_tok = usage.get("promptTokenCount", 0)
                        c_tok = usage.get("candidatesTokenCount", 0)
                        cached_tok = usage.get("cachedContentTokenCount", 0)
                        log_api_telemetry(model, p_tok, c_tok, cached_tok, elapsed_req, chapter_title, chapter_ep)

                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                text = parts[0].get("text") or ""
                                return text.strip()
                        return ""
                    elif res.status_code in (429, 503):
                        await asyncio.sleep(2.0 * (attempt + 1))
                    else:
                        raise RuntimeError(f"Lỗi Gemini API ({res.status_code}): {res.text}")
                except httpx.TimeoutException:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2.0)
        raise RuntimeError("Không nhận được phản hồi từ Gemini API sau 3 lần thử.")

    async def _call_llmgate(
        self,
        system_instruction: str,
        user_prompt: str,
        temperature: float,
        chapter_title: str = "",
        chapter_ep: int = 0
    ) -> str:
        llm_cfg = self.config.get("llmgate", {})
        api_key = llm_cfg.get("api_key", "").strip()
        base_url = llm_cfg.get("base_url", "https://api.llmgate.com/v1").rstrip("/")
        model = llm_cfg.get("model", "gemini-3.7-flash").strip()

        if not api_key:
            raise ValueError("Chưa cấu hình API Key cho LLMGate. Vui lòng vào Cài Đặt (Menu 9) để nhập key.")

        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature
        }

        t0 = time.time()
        async with httpx.AsyncClient(timeout=150.0) as client:
            for attempt in range(3):
                try:
                    res = await client.post(url, headers=headers, json=payload)
                    if res.status_code == 200:
                        elapsed_req = time.time() - t0
                        data = res.json()
                        usage = data.get("usage", {})
                        p_tok = usage.get("prompt_tokens", 0)
                        c_tok = usage.get("completion_tokens", 0)
                        details = usage.get("prompt_tokens_details", {})
                        cached_tok = details.get("cached_tokens", 0) if isinstance(details, dict) else 0
                        
                        log_api_telemetry(model, p_tok, c_tok, cached_tok, elapsed_req, chapter_title, chapter_ep)

                        choices = data.get("choices", [])
                        if choices:
                            content = choices[0].get("message", {}).get("content") or ""
                            return content.strip()
                        return ""
                    elif res.status_code in (429, 502, 503, 504):
                        await asyncio.sleep(2.5 * (attempt + 1))
                    else:
                        raise RuntimeError(f"Lỗi LLMGate API ({res.status_code}): {res.text}")
                except httpx.TimeoutException:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2.0)
        raise RuntimeError("Không nhận được phản hồi từ LLMGate API sau 3 lần thử.")
