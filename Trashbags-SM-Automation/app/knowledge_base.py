"""Loads your friend's product info so the AI can write on-brand replies (Req 3).

Edit data/product_info.md with the real business details — the AI only knows
what's written there.
"""

from functools import lru_cache
from pathlib import Path

KB_PATH = Path(__file__).resolve().parent.parent / "data" / "product_info.md"


@lru_cache
def load_product_info() -> str:
    try:
        return KB_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "No product information has been provided yet."
