from __future__ import annotations

from typing import List, Literal

import re
import uuid
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


from fastapi.middleware.cors import CORSMiddleware
import os

from agent.modules.fiaetutor import analyze_problem
from agent.modules.fiae_analysis import generate_weakness_report
from agent.modules.planner import Task, Importance, Urgency, prioritize
from agent.modules.career import suggest_path
from agent.memory.memory import init_db, get_recent_fiae_logs
from agent.utils.logger import api_logger





app = FastAPI(title="Barakzai Personal Agent API", version="0.1.0")

cors_env = os.getenv("CORS_ORIGINS", "")
origins = [o.strip() for o in cors_env.split(",") if o.strip()] or [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://localhost:5173",
    ],
    allow_origin_regex=r"^https://(.*\.)?barakzai\.cloud$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],  # Allow frontend to read this header
)


# Request ID middleware for tracking
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    # Get or generate request ID
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    
    # Store in request state for access in endpoints
    request.state.request_id = request_id
    
    # Log request start
    start_time = time.time()
    api_logger.info(
        f"{request.method} {request.url.path} - START",
        extra={
            "request_id": request_id,
            "extra": {
                "method": request.method,
                "path": str(request.url.path),
                "client": request.client.host if request.client else None,
            }
        }
    )
    
    # Process request
    response = await call_next(request)
    
    # Log request completion
    duration = time.time() - start_time
    api_logger.info(
        f"{request.method} {request.url.path} - COMPLETED",
        extra={
            "request_id": request_id,
            "extra": {
                "method": request.method,
                "path": str(request.url.path),
                "duration_seconds": round(duration, 3),
                "status_code": response.status_code,
            }
        }
    )
    
    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id
    
    return response





@app.on_event("startup")
def startup_event() -> None:
    init_db()


# ---------- Schemas ----------

class FiaeRequest(BaseModel):
    problem: str
    lang: Literal["de", "fa"] = "de"


class AnalyzeRequest(BaseModel):
    message: str
    language: Literal["de", "fa", "en"] = "de"
    mode: str | None = None


class AnalyzeMeta(BaseModel):
    type: Literal["ok", "error", "quota"]
    lang: Literal["de", "fa", "en"]
    mode: Literal["fiae_algorithms", "general_it", "wiso", "planner", "unknown"]
    model: str
    cached: bool
    retry_after_seconds: int | None
    request_id: str | None = None  # Track request across frontend-backend


class AnalyzeResult(BaseModel):
    summary: str
    steps: List[str]
    example: str | None
    pseudocode: str | None
    visual: str | None
    meta: AnalyzeMeta




class PlannerTaskInput(BaseModel):
    name: str
    importance: Literal["high", "low"]
    urgency: Literal["high", "low"]


class PlannerRequest(BaseModel):
    tasks: List[PlannerTaskInput]


class CareerRequest(BaseModel):
    skills: List[str]
    goals: str


def _get_pseudocode_block(topic: str, lang: str) -> str | None:
    topic_lower = (topic or "").lower()
    selection_keywords = [
        "selection sort",
        "selection-sort",
        "selection sort algorithmus",
        "sortierverfahren selection",
    ]
    if any(keyword in topic_lower for keyword in selection_keywords):
        header = (
            "\u0634\u0628\u0647\u200c\u06a9\u062f (\u0628\u0647 \u0633\u0628\u06a9 IHK\u060c \u0628\u0647 \u0632\u0628\u0627\u0646 \u0622\u0644\u0645\u0627\u0646\u06cc):"
            if lang == "fa"
            else "Pseudocode (IHK-Stil):"
        )
        return (
            f"{header}\n\n"
            "funktion selectionSort(feld: Array von ganzzahl)\n"
            "    n \u2190 l\u00e4nge(feld)\n"
            "    f\u00fcr i \u2190 0 bis n - 2\n"
            "        minIndex \u2190 i\n"
            "        f\u00fcr j \u2190 i + 1 bis n - 1\n"
            "            wenn feld[j] < feld[minIndex] dann\n"
            "                minIndex \u2190 j\n"
            "            ende-wenn\n"
            "        ende-f\u00fcr\n"
            "        wenn minIndex \u2260 i dann\n"
            "            tausche feld[i] mit feld[minIndex]\n"
            "        ende-wenn\n"
            "    ende-f\u00fcr\n"
            "ende-funktion"
        )
    return None


def _get_exam_pitfalls(topic: str, lang: str) -> str | None:
    topic_lower = (topic or "").lower()
    selection_keywords = [
        "selection sort",
        "selection-sort",
        "selection sort algorithmus",
        "sortierverfahren selection",
    ]
    if any(keyword in topic_lower for keyword in selection_keywords):
        if lang == "fa":
            return (
                "\u062f\u0627\u0645\u200c\u0647\u0627\u06cc \u0645\u062a\u062f\u0627\u0648\u0644 \u0627\u0645\u062a\u062d\u0627\u0646 (IHK GA2):\n\n"
                "- \u0634\u0631\u0648\u0639 \u0627\u0634\u062a\u0628\u0627\u0647 \u062d\u0644\u0642\u0647 \u062f\u0627\u062e\u0644\u06cc: `j` \u0628\u0627\u06cc\u062f \u0627\u0632 `i + 1` \u0634\u0631\u0648\u0639 \u0634\u0648\u062f\u060c \u0646\u0647 \u0627\u0632 `0`.\n"
                "- \u062c\u0627\u0628\u062c\u0627\u06cc\u06cc `i` \u0648 `j` \u062f\u0631 \u0634\u0631\u0637\u200c\u0647\u0627 (`feld[j] < feld[minIndex]`).\n"
                "- \u062d\u062f\u0627\u0642\u0644 \u0631\u0627 \u0641\u0642\u0637 \u067e\u06cc\u062f\u0627 \u06a9\u0631\u062f\u0646 \u0627\u0645\u0627 \u062f\u0631 \u067e\u0627\u06cc\u0627\u0646 \u062f\u0648\u0631 \u0628\u0627 `feld[i]` \u062c\u0627\u0628\u062c\u0627 \u0646\u06a9\u0631\u062f\u0646.\n"
                "- \u0627\u0634\u062a\u0628\u0627\u0647 \u062f\u0631 \u0632\u0645\u0627\u0646\u200c\u067e\u06cc\u0686\u06cc\u062f\u06af\u06cc: \u062f\u0631\u0633\u062a O(n\u00b2) \u062f\u0631 Best/Average/Worst-\u0642\u06cc\u0633\u062a.\n"
                "- \u0641\u0631\u0627\u0645\u0648\u0634 \u06a9\u0631\u062f\u0646 \u0627\u06cc\u0646\u06a9\u0647 Selection Sort **\u067e\u0627\u06cc\u062f\u0627\u0631 \u0646\u06cc\u0633\u062a** (\u0645\u0642\u0627\u062f\u06cc\u0631 \u0628\u0631\u0627\u0628\u0631 \u0645\u0645\u06a9\u0646 \u0627\u0633\u062a \u062c\u0627\u0628\u062c\u0627 \u0634\u0648\u0646\u062f)."
            )
        return (
            "Typische Pr\u00fcfungsfallen (IHK GA2):\n\n"
            "- Innerer Schleifenstart falsch: `j` muss bei `i + 1` beginnen, nicht bei `0`.\n"
            "- Vertauschen von `i` und `j` in den Bedingungen (`feld[j] < feld[minIndex]`).\n"
            "- Minimum nur suchen, aber am Ende des Durchlaufs kein Tausch mit `feld[i]`.\n"
            "- Zeitkomplexit\u00e4t falsch angeben: richtig ist O(n\u00b2) im Best-, Average- und Worst-Case.\n"
            "- Vergessen, dass Selection Sort **nicht stabil** ist (gleiche Werte k\u00f6nnen ihre Reihenfolge \u00e4ndern)."
        )
    return None


def _get_german_keywords(topic: str) -> str | None:
    topic_lower = (topic or "").lower()
    selection_keywords = [
        "selection sort",
        "selection-sort",
        "selection sort algorithmus",
        "sortierverfahren selection",
    ]
    if any(keyword in topic_lower for keyword in selection_keywords):
        return "Stichworte (DE): Selection Sort, O(n\u00b2), nicht stabil, In-Place."
    return None


def _format_analysis_answer(result: object, lang: str, topic: str) -> str:
    if not isinstance(result, dict):
        return str(result)

    parts: list[str] = []
    summary = result.get("summary")
    if isinstance(summary, str) and summary.strip():
        parts.append(summary.strip())

    steps = result.get("steps")
    if isinstance(steps, list):
        cleaned_steps = [str(step).strip() for step in steps if str(step).strip()]
        if cleaned_steps:
            if lang == "fa":
                header = "\u06af\u0627\u0645\u200c\u0647\u0627:"
            elif lang == "en":
                header = "Steps:"
            else:
                header = "Schritte:"
            parts.append(header)
            parts.extend([f"{idx}. {step}" for idx, step in enumerate(cleaned_steps, start=1)])

    example = result.get("example")
    if isinstance(example, str) and example.strip():
        if lang == "fa":
            header = "\u0645\u062b\u0627\u0644:"
        elif lang == "en":
            header = "Example:"
        else:
            header = "Beispiel:"
        parts.append(header)
        parts.append(example.strip())

    pseudocode = result.get("pseudocode")
    if isinstance(pseudocode, str) and pseudocode.strip():
        if lang == "fa":
            header = "\u0634\u0628\u0647\u200c\u06a9\u062f:"
        elif lang == "en":
            header = "Pseudocode:"
        else:
            header = "Pseudocode:"
        parts.append(header)
        parts.append(pseudocode.strip())

    visual = result.get("visual")
    if isinstance(visual, str) and visual.strip():
        if lang == "fa":
            header = "\u0646\u0645\u0627\u06cc\u0634:"
        elif lang == "en":
            header = "Visual:"
        else:
            header = "Visual:"
        parts.append(header)
        parts.append(visual.strip())

    if lang in ("de", "fa"):
        pseudocode_block = _get_pseudocode_block(topic, lang)
        if pseudocode_block:
            parts.append("")
            parts.append(pseudocode_block)

        pitfalls = _get_exam_pitfalls(topic, lang)
        if pitfalls:
            parts.append("")
            parts.append(pitfalls)

        if lang == "fa":
            keywords = _get_german_keywords(topic)
            if keywords:
                parts.append("")
                parts.append("---")
                parts.append(keywords)

    return "\n".join(parts).strip()


# ---------- Routes ----------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"status": "ok", "message": "API is running"}

@app.get("/api/status")
def api_status():
    """Check API key and service status"""
    import os
    gemini_key = os.environ.get("GEMINI_API_KEY")
    
    return {
        "status": "ok" if gemini_key else "missing_api_key",
        "api_key_configured": bool(gemini_key),
        "api_key_preview": f"{gemini_key[:10]}...{gemini_key[-4:]}" if gemini_key else None,
        "message": "API is ready" if gemini_key else "GEMINI_API_KEY environment variable is not set"
    }

@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics including size and clear expired entries"""
    from agent.modules.fiaetutor import _CACHE
    
    # Clear expired entries first
    expired_count = await _CACHE.clear_expired()
    
    # Get current cache size
    async with _CACHE._lock:
        current_size = len(_CACHE._cache)
    
    return {
        "cache_size": current_size,
        "expired_cleared": expired_count,
        "ttl_seconds": _CACHE._ttl,
    }

@app.post("/analyze", response_model=AnalyzeResult)
async def analyze(req: AnalyzeRequest, request: Request):
    # Get request ID from middleware
    request_id = getattr(request.state, "request_id", None)
    
    # Call AI service (now async)
    result = await analyze_problem(req.message, language=req.language, mode=req.mode)
    
    # Add request_id to meta
    if "meta" in result and isinstance(result["meta"], dict):
        result["meta"]["request_id"] = request_id
    
    return AnalyzeResult(**result)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "error": "invalid_request",
            "message": "Ung\u00fcltige Anfrage-Daten. Bitte frage den Lerncoach nochmal.",
            "details": exc.errors(),
        },
    )


@app.get("/languages")
def languages():
    return {"languages": ["de", "fa", "en"], "default": "de"}


EXAM_KEYWORDS_DE = [
    "pr\u00fcfung",
    "pr\u00fcfungsvorbereitung",
    "klausur",
    "ihk",
    "abschluss",
    "ga2",
    "ga 2",
    "wiso",
    "wirtschaft",
    "wi.so",
    "sozialkunde",
    "projekt",
    "projektarbeit",
    "abschlussprojekt",
    "exam",
    "test",
]
EXAM_KEYWORDS_FA = [
    "\u0627\u0645\u062a\u062d\u0627\u0646",
    "\u0622\u0632\u0645\u0648\u0646",
    "\u067e\u0631\u0648\u0698\u0647",
    "\u0622\u0632\u0645\u0648\u0646 \u0646\u0647\u0627\u06cc\u06cc",
    "\u0641\u0627\u06cc\u0646\u0627\u0644",
    "\u0648\u06cc\u0632\u0648",
    "\u06a9\u0646\u062a\u0631\u0644",
    "\u062f\u0631\u0633",
    "\u0622\u0645\u0648\u0632\u0634",
]

URGENCY_KEYWORDS_DE = ["heute", "jetzt", "sofort", "today", "morgen", "bis morgen", "diese woche"]
URGENCY_KEYWORDS_FA = ["\u0627\u0645\u0631\u0648\u0632", "\u0627\u0644\u0627\u0646", "\u0641\u0648\u0631\u06cc", "\u0641\u0631\u062f\u0627", "\u0627\u06cc\u0646 \u0647\u0641\u062a\u0647"]



def has_any(text: str, keywords: list[str]) -> bool:
    t = text.lower()
    return any(k in t for k in keywords)


def extract_minutes(text: str) -> int | None:
    """
    Try to extract a duration in minutes from the task name.
    Examples:
      'Java 30 Minuten'  -> 30
      'WISO 1h'          -> 60
      'Python 1h30'      -> 90
    If nothing is found, return None.
    """
    t = text.lower()
    m = re.search(r"(\d+)\s*(min|minute|minuten|\u062f\u0642\u06cc\u0642\u0647)", t)
    if m:
        return int(m.group(1))
    h = re.search(r"(\d+)\s*h", t)
    if h:
        hours = int(h.group(1))
        m2 = re.search(r"\d+\s*h\s*(\d+)", t)
        extra = int(m2.group(1)) if m2 else 0
        return hours * 60 + extra
    return None


def compute_importance_urgency(name: str) -> tuple[str, str]:
    minutes = extract_minutes(name)
    t = name.lower()

    important = False
    has_exam_keyword = has_any(t, EXAM_KEYWORDS_DE) or has_any(t, EXAM_KEYWORDS_FA)
    if has_exam_keyword:
        important = True
    if minutes is not None and minutes >= 60:
        important = True
    if minutes is not None and minutes >= 90:
        important = True

    urgent = False
    if has_any(t, URGENCY_KEYWORDS_DE) or has_any(t, URGENCY_KEYWORDS_FA):
        urgent = True
    if minutes is not None and minutes <= 30:
        urgent = True

    # Additional rule-based overrides before final categorization
    if has_any(t, ["heute", "jetzt", "sofort", "today", "pr\u00fcfung", "abgabe", "deadline", "\u0627\u0645\u0631\u0648\u0632", "\u0627\u0644\u0627\u0646", "\u0641\u0648\u0631\u06cc"]):
        urgent = True
    if has_any(
        t,
        [
            "lernen",
            "ga2",
            "ga 2",
            "wiso",
            "wirtschaft",
            "wi.so",
            "sozialkunde",
            "karriere",
            "portfolio",
            "bewerbung",
            "\u0648\u06cc\u0632\u0648",
            "\u0622\u0632\u0645\u0648\u0646",
            "\u0627\u0645\u062a\u062d\u0627\u0646",
            "\u06a9\u0646\u062a\u0631\u0644",
            "\u062f\u0631\u0633",
            "\u0622\u0645\u0648\u0632\u0634",
        ],
    ):
        important = True
    if has_any(t, ["morgen", "sp\u00e4ter", "irgendwann", "\u0641\u0631\u062f\u0627", "\u0628\u0639\u062f\u0627", "\u0647\u0631 \u0648\u0642\u062a"]) and not important:
        urgent = False
    if has_any(t, ["vielleicht", "wenn ich zeit habe"]):
        important = False
    if has_any(t, ["sp\u00e4ter", "irgendwann", "wenn ich zeit habe", "\u0628\u0639\u062f\u0627\u064b", "\u0647\u0631 \u0648\u0642\u062a \u0648\u0642\u062a \u062f\u0627\u0634\u062a\u0645"]) and not has_exam_keyword and (minutes is None or minutes < 90):
        important = False

    importance = "high" if important else "low"
    urgency = "high" if urgent else "low"

    return importance, urgency


def normalize_value(v: str) -> str:
    v = v.strip().lower()
    mapping = {
        # English (already valid)
        "high": "high",
        "low": "low",

        # German
        "hoch": "high",
        "niedrig": "low",

        # Farsi / Persian
        "\u0628\u0627\u0644\u0627": "high",
        "\u0632\u06cc\u0627\u062f": "high",
        "\u06a9\u0645": "low",
        "\u067e\u0627\u06cc\u06cc\u0646": "low",
    }
    # default fallback: treat unknown as "low"
    return mapping.get(v, "low")


def build_day_schedule(result: dict) -> list[dict]:
    start_hour = 9
    start_minute = 0

    def safe_minutes(task: dict) -> int:
        minutes = task.get("minutes")
        if isinstance(minutes, int) and minutes > 0:
            return minutes
        extracted = extract_minutes(task.get("name", ""))
        if extracted is not None and extracted > 0:
            return extracted
        return 30  # default

    entries: list[dict] = []

    ordered_categories = [
        ("do_now", result.get("do_now", [])),
        ("schedule", result.get("schedule", [])),
    ]

    for category, tasks in ordered_categories:
        for t in tasks:
            duration = safe_minutes(t)

            start_str = f"{start_hour:02d}:{start_minute:02d}"

            total = start_hour * 60 + start_minute + duration
            end_hour = total // 60
            end_minute = total % 60
            end_str = f"{end_hour:02d}:{end_minute:02d}"

            entries.append(
                {
                    "name": t.get("name", ""),
                    "start": start_str,
                    "end": end_str,
                    "category": category,
                }
            )

            start_hour = end_hour
            start_minute = end_minute

    later_tasks = [
        t
        for t in result.get("delete", [])
        if re.search(r"\bspäter\b|\blater\b", t.get("name", ""), re.IGNORECASE)
    ]
    for t in later_tasks:
        duration = safe_minutes(t)

        start_str = f"{start_hour:02d}:{start_minute:02d}"

        total = start_hour * 60 + start_minute + duration
        end_hour = total // 60
        end_minute = total % 60
        end_str = f"{end_hour:02d}:{end_minute:02d}"

        entries.append(
            {
                "name": t.get("name", ""),
                "start": start_str,
                "end": end_str,
                "category": "later",
            }
        )

        start_hour = end_hour
        start_minute = end_minute

    return entries


@app.post("/api/fiae/analyze")
def fiae_analyze(req: FiaeRequest):
    result = analyze_problem(req.problem, lang=req.lang)
    return JSONResponse(content=result)


@app.get("/api/fiae/history")
def fiae_history(limit: int = 10):
    logs = get_recent_fiae_logs(limit=limit)
    items = []
    for created_at, problem, answer in logs:
        items.append(
            {
                "created_at": created_at,
                "problem": problem,
                "answer": answer,
            }
        )
    return {"items": items}


@app.get("/api/fiae/analysis")
def fiae_analysis():
    report = generate_weakness_report()
    return {"report": report}


@app.post("/api/planner/prioritize")
def planner_prioritize(req: PlannerRequest):
    result = {
        "do_now": [],
        "schedule": [],
        "delegate": [],
        "delete": [],
    }

    for incoming in req.tasks:
        importance, urgency = compute_importance_urgency(incoming.name)
        minutes = extract_minutes(incoming.name)

        if minutes is None or minutes <= 90:
            tasks = [
                {
                    "name": incoming.name,
                    "importance": importance,
                    "urgency": urgency,
                    "minutes": minutes,
                }
            ]
        else:
            chunks: list[int] = []
            remaining = minutes
            while remaining > 90:
                chunks.append(45)
                remaining -= 45
            chunks.append(remaining)
            tasks = [
                {
                    "name": f"{incoming.name} (Block {i + 1})",
                    "importance": importance,
                    "urgency": urgency,
                    "minutes": chunk,
                }
                for i, chunk in enumerate(chunks)
            ]

        for task in tasks:
            if importance == "high" and urgency == "high":
                result["do_now"].append(task)
            elif importance == "high" and urgency == "low":
                result["schedule"].append(task)
            elif importance == "low" and urgency == "high":
                result["delegate"].append(task)
            else:
                result["delete"].append(task)

    if len(result["do_now"]) > 2:
        def sort_key(item: dict[str, str]):
            minutes = item.get("minutes")
            if minutes is not None:
                return (0, minutes)
            return (1, item["name"].lower())

        result["do_now"] = sorted(result["do_now"], key=sort_key)

    day_schedule = build_day_schedule(result)
    result["day_schedule"] = day_schedule
    return result


@app.post("/api/career/suggest")
def career_suggest(req: CareerRequest):
    plan = suggest_path(req.skills, req.goals)
    return {"plan": plan}
