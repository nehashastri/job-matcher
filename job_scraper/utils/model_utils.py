import re
from dataclasses import asdict


def to_dict(obj):
    """
    Convert a dataclass object to a dictionary using asdict.

    Args:
        obj: The dataclass instance to convert.

    Returns:
        dict: Dictionary representation of the dataclass, or empty dict on error.
    """
    try:
        result = asdict(obj)
        return result
    except Exception as exc:
        import logging

        logging.getLogger(__name__).error(f"Error converting to dict: {exc}")
        return {}


def short_reason(reason: str) -> str:
    """
    Return up to two sentences from a reason string for concise logging.

    Args:
        reason: The reason string to summarize.

    Returns:
        str: Concise summary (max two sentences or 240 chars).
    """
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
