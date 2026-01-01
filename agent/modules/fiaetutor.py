import json
import os
import re
from typing import Any

from openai import OpenAI

# Client for Gemini via OpenAI-compatible endpoint
# API key is read from environment variable GEMINI_API_KEY
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is not set. Please set it as an environment variable."
    )

client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)


def _normalize_lang(lang: str) -> str:
    return "fa" if (lang or "").strip().lower() == "fa" else "de"


def _empty_result(summary: str) -> dict[str, object]:
    return {
        "summary": summary,
        "steps": [],
        "example": None,
        "pseudocode": None,
        "visual": None,
    }


def _coerce_result(data: Any, fallback_summary: str) -> dict[str, object]:
    result = _empty_result(fallback_summary)
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


def _parse_json(content: str) -> Any | None:
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        return None


def analyze_problem(problem_text: str, lang: str = "de") -> dict[str, object]:
    text = (problem_text or "").strip()
    normalized_lang = _normalize_lang(lang)

    if not text:
        empty_summary = "متنی برای تحلیل دریافت نشد." if normalized_lang == "fa" else "Kein Problemtext erhalten."
        return _empty_result(empty_summary)

    if normalized_lang == "fa":
        lang_instruction = "Antworte in Persisch (Farsi)."
        parse_fail_summary = "پاسخ قابل ساختاردهی نبود."
        error_summary = "خطا در ماژول FIAE (Gemini):"
    else:
        lang_instruction = "Antworte auf Deutsch."
        parse_fail_summary = "Antwort konnte nicht strukturiert werden."
        error_summary = "Fehler beim FIAE-Modul (Gemini):"

    system_prompt = f"""
You are a strict but helpful FIAE (Fachinformatiker Anwendungsentwicklung) exam coach.
Focus ONLY on:
- Algorithm thinking
- Problem analysis
- Step-by-step reasoning

Rules:
- No greetings (no "Guten Tag") and no filler sentences.
- Be concise; avoid long intros.
- Do NOT just give the final answer.

Output format:
Return ONLY valid JSON with this exact schema:
{{
  "summary": "string",
  "steps": ["string", ...],
  "example": "string or null",
  "pseudocode": "string or null",
  "visual": "string or null"
}}

Guidelines:
- summary: 1-3 short sentences (short restatement + core idea).
- steps: ordered steps as short sentences.
- example: short example if useful, otherwise null.
- pseudocode: short pseudocode if useful, otherwise null.
- visual: ASCII diagram or short description if useful, otherwise null.

{lang_instruction}
"""

    try:
        completion = client.chat.completions.create(
            model="gemini-2.5-flash",
            temperature=0.3,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
        )

        content = completion.choices[0].message.content or ""
        parsed = _parse_json(content)
        if parsed is None:
            return _empty_result(parse_fail_summary)
        return _coerce_result(parsed, parse_fail_summary)
    except Exception as e:
        return _empty_result(f"{error_summary} {e}")
