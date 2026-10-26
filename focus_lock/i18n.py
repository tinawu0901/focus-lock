"""Explicit UI translations. User-authored text is never translated."""
from .translations import EN

_language = "zh_TW"


def set_language(language):
    global _language
    _language = language if language in ("zh_TW", "en") else "zh_TW"


def get_language():
    return _language


def tr(text):
    return EN.get(text, text) if _language == "en" else text
