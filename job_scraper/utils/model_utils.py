import re
from dataclasses import asdict


def to_dict(obj):
    return asdict(obj)


def short_reason(reason: str) -> str:
    """Return up to two sentences for concise logging."""
    if not reason:
        return "No reason provided"
    sentences = re.split(r"(?<=[.!?])\s+", reason.strip())
    joined = " ".join(sentences[:2]).strip()
    return joined or reason.strip()[:240]
