import re
from dataclasses import asdict


def to_dict(obj):
    try:
        result = asdict(obj)
        return result
    except Exception as exc:
        import logging

        logging.getLogger(__name__).error(f"Error converting to dict: {exc}")
        return {}


def short_reason(reason: str) -> str:
    """Return up to two sentences for concise logging."""
    import logging

    logger = logging.getLogger(__name__)
    if not reason:
        logger.debug("No reason provided to short_reason")
        return "No reason provided"
    try:
        sentences = re.split(r"(?<=[.!?])\s+", reason.strip())
        joined = " ".join(sentences[:2]).strip()
        return joined or reason.strip()[:240]
    except Exception as exc:
        logger.error(f"Error in short_reason: {exc}")
        return reason.strip()[:240]
