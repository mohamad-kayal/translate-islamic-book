"""Sacred-content retrieval: Quran + hadith lookup by normalized Arabic text."""
from .quran_lookup import lookup as quran_lookup      # noqa: F401
from .hadith_lookup import match as hadith_match       # noqa: F401

__all__ = ["quran_lookup", "hadith_match"]
