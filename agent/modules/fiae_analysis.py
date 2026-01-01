from __future__ import annotations

from textwrap import shorten

from agent.memory.memory import get_recent_fiae_logs
from agent.modules.fiaetutor import client  # reuse the existing Gemini client


SYSTEM_PROMPT_ANALYSIS = """
You are a strict but supportive FIAE exam coach (Fachinformatiker Anwendungsentwicklung).

You receive a history of the student's FIAE exam questions and the AI's answers.
Your job:

1. Detect patterns:
   - Which topics appear often? (e.g. Schleifen, Arrays/Listen, Bedingungen, Sortieralgorithmen, Suchalgorithmen, Rekursion, Komplexität, Off-by-one-Fehler, etc.)
   - Where does the student likely struggle?

2. Output a compact report in SIMPLE German:
   - Section 1: Kurze Zusammenfassung der Themen (Bulletpoints)
   - Section 2: Vermutete Schwächen (Bulletpoints, sehr konkret)
   - Section 3: Konkreter 7–14 Tage Übungsplan
     - Für jeden Tag 1–3 konkrete Aufgaben-Typen (z.B. "Schreibe einen Algorithmus, der das Maximum in einer Liste findet und erkläre jede Zeile.")
   - Maximal ca. 400–500 Wörter.
"""


def _build_history_text(limit: int = 20) -> str:
    """Build a compact textual representation of recent FIAE logs."""
    logs = get_recent_fiae_logs(limit=limit)
    if not logs:
        return ""

    parts: list[str] = []
    for idx, (created_at, problem, answer) in enumerate(logs, start=1):
        short_answer = shorten(answer.replace("\n", " "), width=500, placeholder=" ...")
        parts.append(
            f"# {idx} | {created_at}\n"
            f"Problem: {problem}\n"
            f"Antwort (gekürzt): {short_answer}\n"
        )
    return "\n\n".join(parts)


def generate_weakness_report() -> str:
    """Analyse recent FIAE history and return a weakness report + training plan."""
    history_text = _build_history_text(limit=20)
    if not history_text:
        return "Noch keine Daten vorhanden, um eine Analyse zu erstellen."

    try:
        completion = client.chat.completions.create(
            model="gemini-2.5-flash",
            temperature=0.3,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_ANALYSIS},
                {"role": "user", "content": history_text},
            ],
        )
        message = completion.choices[0].message
        content = getattr(message, "content", None)

        return content or "Leere Antwort vom Analyse-Modell erhalten."
    except Exception as e:
        return f"Fehler bei der Schwächen-Analyse: {e}"
