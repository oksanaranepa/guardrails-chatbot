"""Проверка ответов модели."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from src.guardrails.policies import HARMFUL_PATTERNS, PII_PATTERNS, GuardrailPolicy
from src.guardrails.fact_validator import FactValidator


class OutputViolation(str, Enum):
    TOO_LONG = "output_too_long"
    EMPTY = "empty_output"
    PII_LEAK = "pii_in_output"
    HARMFUL_CONTENT = "harmful_in_output"
    SYSTEM_PROMPT_LEAK = "system_prompt_leak"
    LOW_QUALITY = "low_quality"
    UNGROUNDED_FACT = "ungrounded_fact"


@dataclass
class OutputGuardResult:
    allowed: bool
    violations: list[OutputViolation]
    details: list[str]
    sanitized_text: str | None = None
    fact_check: dict | None = None

    @property
    def fallback_message(self) -> str:
        return (
            "Извините, ответ не прошёл проверку безопасности и был заменён. "
            "Попробуйте переформулировать вопрос."
        )


class OutputGuard:
    """Постобработка и валидация ответов LLM."""

    SYSTEM_LEAK_MARKERS = (
        "system prompt",
        "системный промпт",
        "системные инструкции",
        "you are a helpful",
        "ты — учебный ассистент",
    )

    def __init__(self, policy: GuardrailPolicy | None = None, fact_validator: FactValidator | None = None):
        self.policy = policy or GuardrailPolicy()
        self.fact_validator = fact_validator or FactValidator()

    def check(self, text: str, user_question: str = "") -> OutputGuardResult:
        text = (text or "").strip()
        violations: list[OutputViolation] = []
        details: list[str] = []

        if not text:
            return OutputGuardResult(
                False,
                [OutputViolation.EMPTY],
                ["Пустой ответ модели"],
                sanitized_text=self.fallback_message(),
            )

        if len(text) > self.policy.max_output_chars:
            violations.append(OutputViolation.TOO_LONG)
            details.append(f"Длина {len(text)} > {self.policy.max_output_chars}")
            text = text[: self.policy.max_output_chars] + "…"

        lowered = text.lower()

        if self.policy.block_pii_in_output:
            for name, pattern in PII_PATTERNS.items():
                if re.search(pattern, text):
                    violations.append(OutputViolation.PII_LEAK)
                    details.append(f"Утечка PII: {name}")
                    text = re.sub(pattern, "[СКРЫТО]", text)

        if self.policy.block_harmful_requests:
            for pattern in HARMFUL_PATTERNS:
                if re.search(pattern, lowered, re.IGNORECASE):
                    violations.append(OutputViolation.HARMFUL_CONTENT)
                    details.append("Вредоносный контент в ответе")
                    break

        for marker in self.SYSTEM_LEAK_MARKERS:
            if marker in lowered:
                violations.append(OutputViolation.SYSTEM_PROMPT_LEAK)
                details.append(f"Возможная утечка промпта: {marker}")
                break

        if len(text) < 5 and not violations:
            violations.append(OutputViolation.LOW_QUALITY)
            details.append("Слишком короткий ответ")

        fact_meta = None
        if user_question and not any(
            v in violations
            for v in (OutputViolation.HARMFUL_CONTENT, OutputViolation.EMPTY)
        ):
            fact_result = self.fact_validator.validate(user_question, text)
            fact_meta = {
                "grounded": fact_result.grounded,
                "similarity": round(fact_result.similarity, 4),
                "best_topic": fact_result.best_topic,
                "threshold": fact_result.threshold,
                "details": fact_result.details,
            }
            if not fact_result.grounded:
                violations.append(OutputViolation.UNGROUNDED_FACT)
                details.append(fact_result.details)

        allowed = not any(
            v in violations
            for v in (
                OutputViolation.HARMFUL_CONTENT,
                OutputViolation.SYSTEM_PROMPT_LEAK,
                OutputViolation.EMPTY,
                OutputViolation.UNGROUNDED_FACT,
            )
        )

        return OutputGuardResult(allowed, violations, details, sanitized_text=text, fact_check=fact_meta)

    def fallback_message(self) -> str:
        return OutputGuardResult(False, [], []).fallback_message
