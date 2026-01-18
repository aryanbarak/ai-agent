"""
Prompt template management system.
Separates prompts from code for easier maintenance.
"""
from __future__ import annotations

from typing import Literal, Any
from pathlib import Path
import json


class PromptTemplateManager:
    """
    Manages prompt templates loaded from JSON files.
    
    Benefits:
    - Prompts separated from code
    - Easy to update without code changes
    - Version control friendly
    - Supports multiple languages
    """
    
    def __init__(self, templates_dir: Path | str):
        self.templates_dir = Path(templates_dir)
        self._templates: dict[str, dict[str, Any]] = {}
    
    def load_templates(self) -> None:
        """Load all template files from directory."""
        if not self.templates_dir.exists():
            raise FileNotFoundError(f"Templates directory not found: {self.templates_dir}")
        
        for template_file in self.templates_dir.glob("*.json"):
            template_name = template_file.stem
            
            with open(template_file, "r", encoding="utf-8") as f:
                self._templates[template_name] = json.load(f)
    
    def get_template(
        self,
        name: str,
        language: Literal["de", "fa", "en"] = "de",
    ) -> str:
        """
        Retrieve template by name and language.
        
        Args:
            name: Template name (e.g., "fiae_tutor", "planner")
            language: Target language
        
        Returns:
            Template string
        
        Raises:
            KeyError: If template not found
        """
        if name not in self._templates:
            raise KeyError(f"Template '{name}' not found")
        
        template_data = self._templates[name]
        
        if language not in template_data:
            # Fallback to default language
            language = template_data.get("default", "de")
        
        return template_data[language]
    
    def render(
        self,
        name: str,
        language: Literal["de", "fa", "en"] = "de",
        **variables: Any,
    ) -> str:
        """
        Render template with variables.
        
        Args:
            name: Template name
            language: Target language
            **variables: Template variables
        
        Returns:
            Rendered template string
        """
        template = self.get_template(name, language)
        
        # Simple string formatting (can be replaced with Jinja2 for complex cases)
        try:
            return template.format(**variables)
        except KeyError as e:
            raise ValueError(f"Missing template variable: {e}")


# ============================================================================
# Example template structure (saved as JSON)
# ============================================================================

# File: prompts/fiae_tutor.json
EXAMPLE_TEMPLATE = {
    "default": "de",
    "de": """
Du bist ein strenger aber hilfreicher FIAE (Fachinformatiker Anwendungsentwicklung) Prüfungscoach.

Fokus NUR auf:
- Algorithmisches Denken
- Problemanalyse
- Schritt-für-Schritt Reasoning

Regeln:
- Keine Begrüßungen und keine Füllsätze.
- Sei präzise; vermeide lange Einleitungen.
- Gib NICHT nur die fertige Lösung.
- Ausgabe NUR JSON (kein Markdown, keine Code-Blöcke, kein zusätzlicher Text).
- Alle Strings müssen auf Deutsch sein.

Ausgabeformat:
Gib NUR gültiges JSON mit diesem exakten Schema zurück:
{{
  "summary": "string",
  "steps": ["string", ...],
  "example": "string or null",
  "pseudocode": "string or null",
  "visual": "string or null"
}}

Richtlinien:
- summary: 1-3 kurze Sätze (kurze Umformulierung + Kernidee).
- steps: geordnete Schritte als kurze Sätze.
- example: kurzes Beispiel falls nützlich, sonst null.
- pseudocode: kurzer Pseudocode falls nützlich, sonst null.
- visual: ASCII Diagramm oder kurze Beschreibung falls nützlich, sonst null.

Modell: {model_name}
""",
    "fa": """
شما یک مربی سخت‌گیر اما مفید برای آزمون FIAE هستید.

تمرکز فقط روی:
- تفکر الگوریتمی
- تحلیل مسئله
- استدلال گام‌به‌گام

قوانین:
- بدون احوال‌پرسی و جملات پرکننده.
- مختصر باش؛ از مقدمه‌های طولانی اجتناب کن.
- فقط پاسخ نهایی را نده.
- خروجی فقط JSON (بدون Markdown، بدون بلوک کد، بدون متن اضافی).
- تمام رشته‌ها باید به فارسی باشند.

فرمت خروجی:
فقط JSON معتبر با این ساختار دقیق برگردان:
{{
  "summary": "string",
  "steps": ["string", ...],
  "example": "string or null",
  "pseudocode": "string or null",
  "visual": "string or null"
}}

مدل: {model_name}
""",
    "en": """
You are a strict but helpful FIAE exam coach.

Focus ONLY on:
- Algorithm thinking
- Problem analysis
- Step-by-step reasoning

Rules:
- No greetings and no filler sentences.
- Be concise; avoid long intros.
- Do NOT just give the final answer.
- Output JSON ONLY (no markdown, no code fences, no extra text).
- All strings must be in English.

Output format:
Return ONLY valid JSON with this exact schema:
{{
  "summary": "string",
  "steps": ["string", ...],
  "example": "string or null",
  "pseudocode": "string or null",
  "visual": "string or null"
}}

Model: {model_name}
"""
}
