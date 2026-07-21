import re

from app.ingestion import IngestionError

INJECTION_PATTERNS = (
    r"\bignore\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above)\s+instructions?\b",
    r"\b(?:reveal|show|print|exfiltrate)\b.{0,80}\b(?:system prompt|developer message|api key|credential|secret)\b",
    r"\b(?:system prompt|developer message|jailbreak)\b",
)


def reject_prompt_injection(text: str) -> None:
    if any(re.search(pattern, text, re.IGNORECASE | re.DOTALL) for pattern in INJECTION_PATTERNS):
        raise IngestionError("prompt_injection_detected", "Request was blocked by AI safety guardrails.")
