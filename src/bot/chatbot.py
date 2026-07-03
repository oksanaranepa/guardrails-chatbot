"""Оркестратор диалога с guardrails."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.bot.llm_client import LLMClient
from src.guardrails.input_guard import InputGuard
from src.guardrails.output_guard import OutputGuard
from src.guardrails.policies import GuardrailPolicy
from src.logging.session_logger import SessionLogger


@dataclass
class TurnResult:
    user_message: str
    assistant_message: str
    blocked: bool
    block_stage: str | None  # "input" | "output" | None
    input_guard: dict[str, Any]
    output_guard: dict[str, Any] | None
    fact_check: dict[str, Any] | None
    llm_meta: dict[str, Any] | None
    session_id: str


@dataclass
class ChatSession:
    session_id: str
    history: list[dict[str, str]] = field(default_factory=list)
    turns: list[TurnResult] = field(default_factory=list)


class GuardedChatbot:
    """Чат-бот с проверкой ввода/вывода и структурированным логированием."""

    def __init__(
        self,
        policy: GuardrailPolicy | None = None,
        logger: SessionLogger | None = None,
        llm: LLMClient | None = None,
    ):
        self.policy = policy or GuardrailPolicy()
        self.input_guard = InputGuard(self.policy)
        self.output_guard = OutputGuard(self.policy)
        self.llm = llm or LLMClient()
        self.logger = logger or SessionLogger()

    def create_session(self) -> ChatSession:
        session_id = self.logger.new_session_id()
        session = ChatSession(session_id=session_id)
        self.logger.log_event(session_id, "session_created", {"policy": self._policy_snapshot()})
        return session

    def chat(self, session: ChatSession, user_message: str) -> TurnResult:
        self.logger.log_event(
            session.session_id,
            "user_message_received",
            {"text_length": len(user_message), "preview": user_message[:120]},
        )

        input_result = self.input_guard.check(user_message)
        input_meta = {
            "allowed": input_result.allowed,
            "violations": [v.value for v in input_result.violations],
            "details": input_result.details,
        }
        self.logger.log_event(session.session_id, "input_guard", input_meta)

        if not input_result.allowed:
            assistant = input_result.block_message
            turn = TurnResult(
                user_message=user_message,
                assistant_message=assistant,
                blocked=True,
                block_stage="input",
                input_guard=input_meta,
                output_guard=None,
                fact_check=None,
                llm_meta=None,
                session_id=session.session_id,
            )
            session.turns.append(turn)
            self.logger.log_event(session.session_id, "turn_blocked_input", {"response": assistant})
            return turn

        messages = self.llm.build_messages(session.history, user_message)
        llm_response = self.llm.generate(messages)
        llm_meta = {
            "model": llm_response.model,
            "mode": llm_response.mode,
            "raw_length": len(llm_response.text),
        }
        self.logger.log_event(session.session_id, "llm_response", llm_meta)

        output_result = self.output_guard.check(llm_response.text, user_question=user_message)
        output_meta = {
            "allowed": output_result.allowed,
            "violations": [v.value for v in output_result.violations],
            "details": output_result.details,
            "fact_check": output_result.fact_check,
        }
        self.logger.log_event(session.session_id, "output_guard", output_meta)

        final_text = output_result.sanitized_text or output_result.fallback_message
        blocked_output = not output_result.allowed and any(
            v.value in ("harmful_in_output", "system_prompt_leak", "empty_output", "ungrounded_fact")
            for v in output_result.violations
        )
        if blocked_output:
            final_text = output_result.fallback_message

        session.history.append({"role": "user", "content": user_message})
        session.history.append({"role": "assistant", "content": final_text})

        turn = TurnResult(
            user_message=user_message,
            assistant_message=final_text,
            blocked=blocked_output,
            block_stage="output" if blocked_output else None,
            input_guard=input_meta,
            output_guard=output_meta,
            fact_check=output_result.fact_check,
            llm_meta=llm_meta,
            session_id=session.session_id,
        )
        session.turns.append(turn)
        self.logger.log_event(
            session.session_id,
            "turn_completed",
            {"blocked": turn.blocked, "response_preview": final_text[:200]},
        )
        return turn

    def _policy_snapshot(self) -> dict[str, Any]:
        return {
            "max_input_chars": self.policy.max_input_chars,
            "max_output_chars": self.policy.max_output_chars,
            "block_prompt_injection": self.policy.block_prompt_injection,
            "block_harmful_requests": self.policy.block_harmful_requests,
            "block_pii_in_input": self.policy.block_pii_in_input,
            "block_off_topic": self.policy.block_off_topic,
        }
