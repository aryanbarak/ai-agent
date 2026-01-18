"""
FIAE Analysis Service - Clean business logic layer.

This service orchestrates:
- LLM interactions
- Caching
- Response validation
- Database logging
"""
from __future__ import annotations

import json
import re
from typing import Literal, Any

from refactoring_examples.core.exceptions import (
    LLMValidationError,
    LLMLanguageMismatchError,
    ValidationError,
)
from refactoring_examples.domain.protocols import (
    LLMProvider,
    CacheProvider,
    FIAERepository,
    LLMMessage,
)
from refactoring_examples.infrastructure.llm.cache import SemanticCache


class FIAEAnalysisService:
    """
    Service for analyzing FIAE problems using LLM.
    
    Responsibilities:
    - Validate input
    - Check cache
    - Call LLM with proper prompts
    - Validate response
    - Store results
    """
    
    def __init__(
        self,
        llm_provider: LLMProvider,
        cache: SemanticCache,
        repository: FIAERepository,
        system_prompt_template: str,
    ):
        self.llm = llm_provider
        self.cache = cache
        self.repository = repository
        self.system_prompt = system_prompt_template
    
    async def analyze_problem(
        self,
        problem_text: str,
        language: Literal["de", "fa", "en"] = "de",
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """
        Analyze FIAE problem and return structured response.
        
        Args:
            problem_text: The problem to analyze
            language: Target language for response
            temperature: LLM temperature (0.0-1.0)
        
        Returns:
            Structured analysis result
        
        Raises:
            ValidationError: If input is invalid
            LLMValidationError: If LLM response is invalid
        """
        # 1. Validate input
        text = (problem_text or "").strip()
        if not text:
            raise ValidationError("Problem text cannot be empty")
        
        if len(text) > 5000:
            raise ValidationError("Problem text too long (max 5000 characters)")
        
        # 2. Build messages
        system_prompt = self.system_prompt.format(
            lang=language,
            model_name=self.llm.get_model_name(),
        )
        
        messages: list[LLMMessage] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]
        
        # 3. Check cache
        cached_response = await self.cache.get_response(
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            temperature=temperature,
            model=self.llm.get_model_name(),
        )
        
        if cached_response:
            # Mark as cached
            result = cached_response.copy()
            result["meta"]["cached"] = True
            return result
        
        # 4. Call LLM
        llm_response = await self.llm.complete(
            messages=messages,
            temperature=temperature,
        )
        
        # 5. Parse and validate response
        parsed = self._parse_json_response(llm_response["content"])
        
        if not parsed:
            raise LLMValidationError(
                "LLM returned invalid JSON",
                response=llm_response["content"],
            )
        
        # 6. Validate language
        if not self._validate_language(parsed, language):
            # Retry with stronger prompt
            retry_prompt = system_prompt + f"\n\nCRITICAL: You MUST respond in {language} ONLY!"
            
            retry_messages: list[LLMMessage] = [
                {"role": "system", "content": retry_prompt},
                {"role": "user", "content": text},
            ]
            
            retry_response = await self.llm.complete(
                messages=retry_messages,
                temperature=temperature,
            )
            
            retry_parsed = self._parse_json_response(retry_response["content"])
            
            if retry_parsed and self._validate_language(retry_parsed, language):
                parsed = retry_parsed
                llm_response = retry_response
            else:
                raise LLMLanguageMismatchError(
                    expected=language,
                    response=llm_response["content"],
                )
        
        # 7. Build final result
        result = self._build_result(
            parsed,
            language=language,
            model=llm_response["model"],
            cached=False,
        )
        
        # 8. Cache response
        await self.cache.set_response(
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            temperature=temperature,
            model=self.llm.get_model_name(),
            response=result,
            ttl=3600,  # 1 hour
        )
        
        # 9. Log to database (async, don't block on failure)
        try:
            await self.repository.save(
                problem=text,
                answer=json.dumps(result, ensure_ascii=False),
                language=language,
            )
        except Exception as e:
            # Log error but don't fail the request
            print(f"[WARNING] Failed to save to database: {e}")
        
        return result
    
    def _parse_json_response(self, content: str) -> dict[str, Any] | None:
        """
        Parse JSON from LLM response.
        
        Handles:
        - JSON in code fences
        - Unwrapped JSON
        - Malformed JSON
        """
        if not content:
            return None
        
        # Try to extract from code fence
        fence_match = re.search(
            r"```(?:json)?\s*([\s\S]+?)\s*```",
            content,
            re.IGNORECASE,
        )
        
        if fence_match:
            content = fence_match.group(1).strip()
        
        # Try direct parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Try to find first JSON object
        start = content.find("{")
        if start == -1:
            return None
        
        depth = 0
        in_string = False
        escape = False
        
        for i in range(start, len(content)):
            char = content[i]
            
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
                    try:
                        return json.loads(content[start : i + 1])
                    except json.JSONDecodeError:
                        return None
        
        return None
    
    def _validate_language(
        self,
        data: dict[str, Any],
        expected_lang: Literal["de", "fa", "en"],
    ) -> bool:
        """
        Validate that response is in expected language.
        """
        # Collect all text from response
        text_parts = []
        
        for key in ("summary", "example", "pseudocode", "visual"):
            value = data.get(key)
            if isinstance(value, str):
                text_parts.append(value)
        
        steps = data.get("steps", [])
        if isinstance(steps, list):
            text_parts.extend([str(s) for s in steps if s])
        
        full_text = " ".join(text_parts)
        
        # Check language
        if expected_lang == "fa":
            # Must contain Persian characters
            return bool(re.search(r"[\u0600-\u06FF]", full_text))
        else:
            # Must NOT contain Persian characters
            return not re.search(r"[\u0600-\u06FF]", full_text)
    
    def _build_result(
        self,
        parsed: dict[str, Any],
        language: str,
        model: str,
        cached: bool,
    ) -> dict[str, Any]:
        """Build standardized result structure."""
        return {
            "summary": parsed.get("summary", ""),
            "steps": parsed.get("steps", []),
            "example": parsed.get("example"),
            "pseudocode": parsed.get("pseudocode"),
            "visual": parsed.get("visual"),
            "meta": {
                "type": "ok",
                "lang": language,
                "mode": "fiae_algorithms",
                "model": model,
                "cached": cached,
                "retry_after_seconds": None,
            },
        }
