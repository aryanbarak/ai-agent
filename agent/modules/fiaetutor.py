import asyncio
import copy
import json
import os
import re
import time
from typing import Any

from openai import AsyncOpenAI
from agent.utils.logger import fiae_logger, cache_logger

# Client for Gemini via OpenAI-compatible endpoint
# API key is read from environment variable GEMINI_API_KEY
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is not set. Please set it as an environment variable."
    )

client = AsyncOpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

MODEL_NAME = "gemini-2.5-flash"

# Thread-safe async cache with TTL
class AsyncCache:
    def __init__(self, ttl_seconds: int = 3600):
        self._cache: dict[tuple[str, str, str], tuple[dict[str, object], float]] = {}
        self._lock = asyncio.Lock()
        self._ttl = ttl_seconds
    
    async def get(self, key: tuple[str, str, str]) -> dict[str, object] | None:
        async with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                # Check if expired
                if time.time() - timestamp < self._ttl:
                    cache_logger.debug(
                        "Cache HIT",
                        extra={"extra": {"key_hash": hash(key), "age_seconds": int(time.time() - timestamp)}}
                    )
                    return copy.deepcopy(value)
                else:
                    # Remove expired entry
                    cache_logger.debug(
                        "Cache entry expired",
                        extra={"extra": {"key_hash": hash(key), "age_seconds": int(time.time() - timestamp)}}
                    )
                    del self._cache[key]
            cache_logger.debug("Cache MISS", extra={"extra": {"key_hash": hash(key)}})
            return None
    
    async def set(self, key: tuple[str, str, str], value: dict[str, object]) -> None:
        async with self._lock:
            self._cache[key] = (copy.deepcopy(value), time.time())
            cache_logger.debug(
                "Cache SET",
                extra={"extra": {"key_hash": hash(key), "cache_size": len(self._cache)}}
            )
    
    async def clear_expired(self) -> int:
        """Remove all expired entries and return count of removed items"""
        async with self._lock:
            current_time = time.time()
            expired_keys = [
                k for k, (_, timestamp) in self._cache.items()
                if current_time - timestamp >= self._ttl
            ]
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                cache_logger.info(
                    f"Cleared {len(expired_keys)} expired cache entries",
                    extra={"extra": {"expired_count": len(expired_keys), "remaining": len(self._cache)}}
                )
            
            return len(expired_keys)

_CACHE = AsyncCache(ttl_seconds=3600)  # 1 hour TTL


def _normalize_lang(lang: str) -> str:
    normalized = (lang or "").strip().lower()
    if normalized == "fa":
        return "fa"
    if normalized == "en":
        return "en"
    return "de"


def _build_meta(
    *,
    language: str,
    mode: str | None,
    cached: bool,
    meta_type: str = "ok",
    retry_after_seconds: int | None = None,
) -> dict[str, object]:
    return {
        "type": meta_type,
        "lang": language,
        "mode": mode or "unknown",
        "model": MODEL_NAME,
        "cached": cached,
        "retry_after_seconds": retry_after_seconds,
    }


def _empty_result(summary: str, meta: dict[str, object]) -> dict[str, object]:
    return {
        "summary": summary,
        "steps": [],
        "example": None,
        "pseudocode": None,
        "visual": None,
        "meta": meta,
    }


def _coerce_result(
    data: Any, fallback_summary: str, meta: dict[str, object]
) -> dict[str, object]:
    result = _empty_result(fallback_summary, meta)
    if not isinstance(data, dict):
        return result

    summary = data.get("summary")
    if isinstance(summary, str) and summary.strip():
        result["summary"] = summary.strip()

    steps = data.get("steps")
    if isinstance(steps, list):
        cleaned_steps: list[str] = []
        for item in steps:
            text = item.strip() if isinstance(item, str) else str(item).strip()
            if text:
                cleaned_steps.append(text)
        result["steps"] = cleaned_steps

    for key in ("example", "pseudocode", "visual"):
        value = data.get(key)
        if isinstance(value, str):
            value = value.strip()
            result[key] = value or None
        elif value is None:
            result[key] = None

    return result


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if char == "\\" and not escape:
            escape = True
            continue
        if char == '"' and not escape:
            in_string = not in_string
        escape = False
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _parse_json(content: str) -> Any | None:
    if not content:
        return None
    fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", content, re.IGNORECASE)
    if fence_match:
        content = fence_match.group(1).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        candidate = _extract_first_json_object(content)
        if not candidate:
            return None
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None


def _extract_retry_after_seconds(text: str) -> int | None:
    if not text:
        return None
    patterns = [
        r"retry[- ]after[:\s]+(\d+)",
        r"Retry-After:\s*(\d+)",
        r"in\s+(\d+)\s*seconds",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
    return None


def _looks_like_quota_error(text: str) -> bool:
    lowered = text.lower()
    return (
        "resource_exhausted" in lowered
        or "quota" in lowered
        or "429" in lowered
    )


def _fallback_summary(lang: str) -> str:
    if lang == "fa":
        return "متاسفانه پاسخ معتبر تولید نشد."
    if lang == "en":
        return "A valid response could not be produced."
    return "Es konnte keine gueltige Antwort erzeugt werden."


def _empty_summary(lang: str) -> str:
    if lang == "fa":
        return "متن مسئله دریافت نشد."
    if lang == "en":
        return "No problem text received."
    return "Kein Problemtext erhalten."


def _language_mismatch_summary(lang: str) -> str:
    if lang == "fa":
        return "عدم تطابق زبان پاسخ. لطفا دوباره تلاش کنید."
    if lang == "en":
        return "Language mismatch: the response was not in English."
    return "Sprachfehler: Die Antwort war nicht auf Deutsch."


def _quota_summary(lang: str) -> str:
    if lang == "fa":
        return "سهمیه تمام شده است. لطفا بعدا دوباره تلاش کنید."
    if lang == "en":
        return "Quota exceeded. Please try again later."
    return "Kontingent aufgebraucht. Bitte spaeter erneut versuchen."


def _error_summary(lang: str) -> str:
    if lang == "fa":
        return "خطایی رخ داد. لطفا دوباره تلاش کنید."
    if lang == "en":
        return "An error occurred. Please try again."
    return "Ein Fehler ist aufgetreten. Bitte erneut versuchen."


def _collect_text(data: dict[str, object]) -> str:
    parts: list[str] = []
    for key in ("summary", "example", "pseudocode", "visual"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    steps = data.get("steps")
    if isinstance(steps, list):
        parts.extend([str(step).strip() for step in steps if str(step).strip()])
    return " ".join(parts)


def _contains_persian(text: str) -> bool:
    return re.search(r"[\u0600-\u06FF]", text or "") is not None


def _contains_latin(text: str) -> bool:
    return re.search(r"[A-Za-z]", text or "") is not None


def _language_ok(data: dict[str, object], lang: str) -> bool:
    text = _collect_text(data)
    if lang == "fa":
        # Persian answers may include Latin terms like "Bubble Sort", "O(n^2)" etc.
        # Relaxed validation: accept any response that has some Persian content
        # or is a valid technical response (even if mostly Latin)
        has_persian = _contains_persian(text)
        has_content = len(text.strip()) > 10
        # Accept if it has Persian OR if it's substantial content (technical terms)
        return has_persian or has_content
    if lang in ("de", "en"):
        # For German/English, just ensure no Persian characters
        return not _contains_persian(text)
    return True



def _build_system_prompt(lang: str, strong: bool = False) -> str:
    # Map language codes to full names for better model understanding
    lang_map = {
        "de": "German (Deutsch)",
        "en": "English",
        "fa": "Persian (Farsi/فارسی)"
    }
    lang_name = lang_map.get(lang, lang)
    
    extra_rule = ""
    if strong:
        extra_rule = (
            f"- The response MUST be in {lang_name} ONLY.\n"
            "- Do NOT mix languages or use any other language.\n"
            "- For Persian responses, use Persian script (فارسی) for all text.\n"
            "- Output JSON ONLY with the exact schema.\n"
        )
    
    return f"""
You are a strict but helpful FIAE (Fachinformatiker Anwendungsentwicklung) exam coach.
Focus ONLY on:
- Algorithm thinking
- Problem analysis
- Step-by-step reasoning

Rules:
- No greetings and no filler sentences.
- Be concise; avoid long intros.
- Do NOT just give the final answer.
- Output JSON ONLY (no markdown, no code fences, no extra text).
- All strings must be in {lang_name}.
{extra_rule}

Output format:
Return ONLY valid JSON with this exact schema:
{{
  "summary": "string",
  "steps": ["string", ...],
  "example": "string or null",
  "pseudocode": "string or null",
  "visual": "string or null",
  "meta": {{
    "type": "ok",
    "lang": "{lang}",
    "mode": "fiae_algorithms|general_it|wiso|planner|unknown",
    "model": "{MODEL_NAME}",
    "cached": false,
    "retry_after_seconds": null
  }}
}}

Guidelines:
- summary: 1-3 short sentences (short restatement + core idea) in {lang_name}.
- steps: ordered steps as short sentences in {lang_name}.
- example: short example if useful (in {lang_name}), otherwise null.
- pseudocode: short pseudocode if useful (in {lang_name}), otherwise null.
- visual: ASCII diagram or short description if useful (in {lang_name}), otherwise null.
"""


async def _call_model(messages: list[dict[str, str]]) -> str:
    completion = await client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0.2,
        messages=messages,
    )
    return completion.choices[0].message.content or ""


async def analyze_problem(
    problem_text: str,
    lang: str | None = None,
    *,
    language: str | None = None,
    mode: str | None = None,
) -> dict[str, object]:
    text = (problem_text or "").strip()
    normalized_lang = _normalize_lang(language or lang or "de")
    normalized_mode = mode or "unknown"

    fiae_logger.debug(
        "Analyzing problem",
        extra={"extra": {"language": normalized_lang, "mode": normalized_mode, "text_length": len(text)}}
    )

    if not text:
        meta = _build_meta(
            language=normalized_lang,
            mode=normalized_mode,
            cached=False,
        )
        return _empty_result(_empty_summary(normalized_lang), meta)

    cache_key = (text, normalized_lang, normalized_mode)
    cached_result = await _CACHE.get(cache_key)
    if cached_result is not None:
        fiae_logger.info("Returning cached result")
        cached_meta = _build_meta(
            language=normalized_lang,
            mode=normalized_mode,
            cached=True,
        )
        cached_result["meta"] = cached_meta
        return cached_result

    system_prompt = _build_system_prompt(normalized_lang)

    try:
        content = await _call_model(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ]
        )
        parsed = _parse_json(content)
        base_meta = _build_meta(
            language=normalized_lang,
            mode=normalized_mode,
            cached=False,
        )

        if parsed is None or not isinstance(parsed, dict):
            summary = content.strip() or _fallback_summary(normalized_lang)
            return _empty_result(summary, base_meta)

        result = _coerce_result(parsed, _fallback_summary(normalized_lang), base_meta)

        if not _language_ok(result, normalized_lang):
            strong_prompt = _build_system_prompt(normalized_lang, strong=True)
            retry_content = await _call_model(
                [
                    {"role": "system", "content": strong_prompt},
                    {"role": "user", "content": text},
                ]
            )
            retry_parsed = _parse_json(retry_content)
            if isinstance(retry_parsed, dict):
                retry_result = _coerce_result(
                    retry_parsed,
                    _fallback_summary(normalized_lang),
                    base_meta,
                )
                if _language_ok(retry_result, normalized_lang):
                    await _CACHE.set(cache_key, retry_result)
                    return retry_result

            error_meta = _build_meta(
                language=normalized_lang,
                mode=normalized_mode,
                cached=False,
                meta_type="error",
            )
            return _empty_result(_language_mismatch_summary(normalized_lang), error_meta)

        await _CACHE.set(cache_key, result)
        return result
    except Exception as e:
        message = str(e)
        fiae_logger.error(
            f"Error analyzing problem: {message}",
            extra={"extra": {"language": normalized_lang, "mode": normalized_mode}},
            exc_info=True
        )
        retry_after_seconds = _extract_retry_after_seconds(message)
        if _looks_like_quota_error(message):
            fiae_logger.warning("Quota error detected", extra={"extra": {"retry_after": retry_after_seconds}})
            meta = _build_meta(
                language=normalized_lang,
                mode=normalized_mode,
                cached=False,
                meta_type="quota",
                retry_after_seconds=retry_after_seconds,
            )
            return _empty_result(_quota_summary(normalized_lang), meta)

        meta = _build_meta(
            language=normalized_lang,
            mode=normalized_mode,
            cached=False,
            meta_type="error",
            retry_after_seconds=retry_after_seconds,
        )
        return _empty_result(_error_summary(normalized_lang), meta)
