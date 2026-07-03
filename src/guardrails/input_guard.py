"""Проверка пользовательского ввода."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from src.guardrails.policies import (
    HARMFUL_PATTERNS,
    INJECTION_PATTERNS,
    OFF_TOPIC_PATTERNS,
    PII_PATTERNS,
    GuardrailPolicy,
)


class InputViolation(str, Enum):
    TOO_LONG = "input_too_long"
    PROMPT_INJECTION = "prompt_injection"
    HARMFUL_REQUEST = "harmful_request"
    PII_DETECTED = "pii_in_input"
    OFF_TOPIC = "off_topic"
    EMPTY = "empty_input"


@dataclass
class InputGuardResult:
    allowed: bool
    violations: list[InputViolation]
    details: list[str]
    sanitized_text: str | None = None

    @property
    def block_message(self) -> str:
        if self.allowed:
            return ""
        messages = {
            InputViolation.TOO_LONG: "Сообщение слишком длинное. Сократите запрос.",
            InputViolation.PROMPT_INJECTION: (
                "Обнаружена попытка изменить поведение ассистента (prompt injection). "
                "Переформулируйте вопрос по учебной теме."
            ),
            InputViolation.HARMFUL_REQUEST: (
                "Запрос отклонён: содержит потенциально вредоносный или неэтичный контент."
            ),
            InputViolation.PII_DETECTED: (
                "В сообщении обнаружены персональные данные (email, телефон и т.д.). "
                "Удалите их перед отправкой."
            ),
            InputViolation.OFF_TOPIC: (
                "Вопрос вне учебной тематики ассистента. "
                "Задайте вопрос по программированию, ML или курсу."
            ),
            InputViolation.EMPTY: "Пустое сообщение.",
        }
        primary = self.violations[0]
        return messages.get(primary, "Сообщение отклонено политикой безопасности.")


class InputGuard:
    """Многоуровневая проверка входящих сообщений."""

    def __init__(self, policy: GuardrailPolicy | None = None):
        self.policy = policy or GuardrailPolicy()

    def check(self, text: str) -> InputGuardResult:
        text = (text or "").strip()
        violations: list[InputViolation] = []
        details: list[str] = []

        if not text:
            return InputGuardResult(False, [InputViolation.EMPTY], ["Пустой ввод"])

        if len(text) > self.policy.max_input_chars:
            violations.append(InputViolation.TOO_LONG)
            details.append(f"Длина {len(text)} > {self.policy.max_input_chars}")

        lowered = text.lower()

        if self.policy.block_prompt_injection:
            for pattern in INJECTION_PATTERNS:
                if re.search(pattern, lowered, re.IGNORECASE):
                    violations.append(InputViolation.PROMPT_INJECTION)
                    details.append(f"Совпадение с injection-паттерном: {pattern[:40]}...")
                    break

        if self.policy.block_harmful_requests:
            for pattern in HARMFUL_PATTERNS:
                if re.search(pattern, lowered, re.IGNORECASE):
                    violations.append(InputViolation.HARMFUL_REQUEST)
                    details.append(f"Совпадение с harmful-паттерном: {pattern[:40]}...")
                    break

        if self.policy.block_pii_in_input:
            for name, pattern in PII_PATTERNS.items():
                if re.search(pattern, text):
                    violations.append(InputViolation.PII_DETECTED)
                    details.append(f"Обнаружен PII: {name}")
                    break

        if self.policy.block_off_topic and not violations:
            for pattern in OFF_TOPIC_PATTERNS:
                if re.search(pattern, lowered, re.IGNORECASE):
                    violations.append(InputViolation.OFF_TOPIC)
                    details.append(f"Off-topic паттерн: {pattern[:40]}...")
                    break
            if not violations and not self._is_on_topic(lowered):
                violations.append(InputViolation.OFF_TOPIC)
                details.append("Нет ключевых слов учебной тематики")

        allowed = len(violations) == 0
        return InputGuardResult(allowed, violations, details, sanitized_text=text if allowed else None)

    def _is_on_topic(self, text: str) -> bool:
        """Эвристика: хотя бы одно ключевое слово или вопросительная форма по учёбе."""
        topic_keywords = self.policy.allowed_topics
        if any(kw in text for kw in topic_keywords):
            return True
        # Короткие приветствия и уточнения в диалоге
        greetings = ("привет", "здравствуй", "спасибо", "помоги", "объясни", "что такое", "как ")
        return any(g in text for g in greetings) and len(text) < 120
