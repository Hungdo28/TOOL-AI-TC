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
        import threading
        self.base_url = settings.ai_api_url.rstrip("/")
        self.api_key = settings.ai_api_key
        self.default_model = settings.ai_model or "DeepSeek-V4.1-Flash"
        self._lock = threading.Lock()
        self._task_usage: dict[str, dict[str, int]] = {}
        self._global_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def reset_task_usage(self, task_name: str) -> None:
        with self._lock:
            self._task_usage[task_name] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def get_task_usage(self, task_name: str) -> dict[str, int]:
        with self._lock:
            return dict(self._task_usage.get(task_name, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}))

    def record_usage(self, task_name: str | None, usage: dict[str, int]) -> None:
        inp = usage.get("input_tokens", 0)
        out = usage.get("output_tokens", 0)
        tot = usage.get("total_tokens", inp + out)
        with self._lock:
            self._global_usage["input_tokens"] += inp
            self._global_usage["output_tokens"] += out
            self._global_usage["total_tokens"] += tot
            if task_name:
                cur = self._task_usage.setdefault(task_name, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
                cur["input_tokens"] += inp
                cur["output_tokens"] += out
                cur["total_tokens"] += tot

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
        task_name: str | None = None,
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
                    task_name=task_name,
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
        task_name: str | None = None,
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
                text_out = self._extract_text(data)
                usage = self._extract_usage(data, prompt=prompt, text_out=text_out)
                self.record_usage(task_name, usage)
                LOGGER.info(
                    "[AI Token] (%s) Model: %s | In: %s | Out: %s | Lần gọi này: %s tokens",
                    task_name or "General",
                    model,
                    f"{usage['input_tokens']:,}",
                    f"{usage['output_tokens']:,}",
                    f"{usage['total_tokens']:,}",
                )
                return text_out
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code} từ AI API: {err_body[:500]}") from e

    @staticmethod
    def _extract_usage(data: Any, prompt: str = "", text_out: str = "") -> dict[str, int]:
        if isinstance(data, dict):
            usage = data.get("usage")
            if isinstance(usage, dict):
                input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
                output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
                total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))
                if total_tokens > 0:
                    return {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens,
                    }
        # Ước lượng dự phòng (1 token ≈ 4 ký tự)
        inp = max(1, len(prompt) // 4)
        out = max(1, len(text_out) // 4)
        return {
            "input_tokens": inp,
            "output_tokens": out,
            "total_tokens": inp + out,
        }

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
