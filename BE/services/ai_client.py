from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from core.config import Settings

LOGGER = logging.getLogger("autotc-backend")


class AiClient:
    """
    Client gọi trực tiếp Viettel AI / Anthropic Messages API (tương thích hoàn toàn với node
    lmChatAnthropic trên n8n) và hỗ trợ fallback sang OpenAI Chat Completions nếu cần.
    """

    def __init__(self, settings: Settings):
        self.base_url = settings.ai_api_url.rstrip("/")
        self.api_key = settings.ai_api_key
        self.default_model = settings.ai_model or "DeepSeek-V4.1-Flash"

    def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        max_tokens: int = 8000,
        temperature: float = 0.2,
        max_retries: int = 2,
        retry_delay: float = 3.0,
        timeout: int = 180,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("Chưa cấu hình AI_API_KEY trong BE/.env")

        target_model = model or self.default_model
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 2):
            try:
                return self._call_anthropic_messages(
                    prompt=prompt,
                    model=target_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=timeout,
                )
            except Exception as err:
                last_error = err
                LOGGER.warning(
                    "Gọi AI (%s) lần %d/%d thất bại: %s",
                    target_model,
                    attempt,
                    max_retries + 1,
                    err,
                )
                if attempt <= max_retries:
                    time.sleep(retry_delay * attempt)

        raise RuntimeError(f"AI ({target_model}) không phản hồi sau {max_retries + 1} lần thử: {last_error}")

    def _call_anthropic_messages(
        self,
        *,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        timeout: int,
    ) -> str:
        url = (
            self.base_url
            if self.base_url.endswith("/v1/messages")
            else f"{self.base_url}/v1/messages"
        )
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Anthropic/JS 0.27.0",
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw_bytes = resp.read()
                data = json.loads(raw_bytes.decode("utf-8", errors="replace"))
                return self._extract_text(data)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code} từ AI API: {err_body[:500]}") from e

    @staticmethod
    def _extract_text(data: Any) -> str:
        if not isinstance(data, dict):
            return str(data or "")

        # Định dạng Anthropic Messages API: {"content": [{"type": "text", "text": "..."}]}
        content = data.get("content")
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict):
                    btype = block.get("type")
                    if btype == "text" and block.get("text"):
                        parts.append(str(block["text"]))
                    elif not btype and block.get("text"):
                        parts.append(str(block["text"]))
            if parts:
                return "\n".join(parts).strip()

        if isinstance(content, str) and content.strip():
            return content.strip()

        # Định dạng OpenAI Chat Completions fallback: {"choices": [{"message": {"content": "..."}}]}
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(msg, dict) and msg.get("content"):
                return str(msg["content"]).strip()

        if data.get("output"):
            return str(data["output"]).strip()
        if data.get("text"):
            return str(data["text"]).strip()

        return json.dumps(data, ensure_ascii=False)
