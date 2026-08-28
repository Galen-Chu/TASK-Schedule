"""Glyph-map regression: every emoji that reaches a PDF must map to a glyph
the static Noto TC subset actually contains — unmapped codepoints render as
.notdef ☒ boxes (the 2026-08-28 🌙 case on Spiritual P7). Coverage was
verified against fonts/NotoSansTC-{Regular,Bold}.ttf via fontTools.
"""
from core.pdf_engine import _map_emoji, _EMOJI_MAP


def test_moon_maps_to_covered_yin_yang():
    # ☯ (U+262F) is present in both static weights; ☾ ✦ ✧ are NOT.
    assert _map_emoji("🌙 靈性資訊速讀").startswith("☯")


def test_trend_and_books_emoji_mapped():
    assert _map_emoji("🆕 新增").startswith("◆")     # Global trend table
    assert _map_emoji("📚 編輯精選").startswith("▤")  # editorial-picks note


def test_map_targets_contain_no_emoji():
    for target in _EMOJI_MAP.values():
        for ch in target:
            assert ord(ch) < 0x1F000, f"map target still holds emoji: {ch!r}"
