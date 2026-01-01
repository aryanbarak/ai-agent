from __future__ import annotations

from typing import List

from agent.modules.fiaetutor import client  # reuse the existing Gemini client


SYSTEM_PROMPT_CAREER = """
Du bist ein erfahrener Karriere- und Lerncoach für IT, speziell für
Fachinformatiker Anwendungsentwicklung (FIAE) in Deutschland.

Aufgabe:
- Du bekommst die aktuellen Skills, Interessen und Ziele des Nutzers.
- Erstelle einen realistischen Lern- und Karriereplan.

Regeln:
- Antworte in einfachem, klaren Deutsch.
- Keine leeren Motivationssätze, sondern konkrete Schritte.
- Struktur:

  1. Kurzprofil (2–3 Sätze, was du aus den Angaben ableitest)
  2. Nächste 30 Tage (konkrete Lernziele und Aktivitäten, Bulletpoints)
  3. Nächste 90 Tage (gröbere Ziele, z.B. Zertifikate, Bewerbungsstrategie)
  4. Konkrete Vorschläge für Projekte oder GitHub-Ideen
  5. Hinweise, welche Skills für Cloud/AI/DevOps/FIAE-Prüfung besonders wichtig sind

- Sei ehrlich: Wenn das Ziel zu groß ist für 90 Tage, sag es klar.
"""


def suggest_path(current_skills: List[str], goals: str) -> str:
    """Generate a career & learning roadmap based on skills + goals."""
    skills_text = ", ".join(s.strip() for s in current_skills if s.strip()) or "keine Angaben"

    user_content = f"""
Aktuelle Skills: {skills_text}
Ziele / Situation: {goals}
"""

    try:
        completion = client.chat.completions.create(
            model="gemini-2.5-flash",
            temperature=0.35,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_CAREER},
                {"role": "user", "content": user_content},
            ],
        )
        message = completion.choices[0].message
        content = getattr(message, "content", None)
        return content or "Leere Antwort vom Karriere-Modell erhalten."
    except Exception as e:
        return f"Fehler im Karriere-Modul: {e}"
