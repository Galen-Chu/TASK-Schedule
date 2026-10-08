"""JSON digest builders — the machine-readable twin of each Obsidian note.

Contract under test (core.obsidian_writer.digest_meta):
  * every digest carries meta {schema_version, report_id, date, generated_at,
    producer, source_chain}
  * verdict-style inputs stay null when the live fetch failed (fail-visible;
    consumers must never fall back to a sample value)
  * external text is sanitized + trimmed before it lands in the digest
    (RSS summaries are raw HTML — landmine #8)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.obsidian_writer import digest_meta, write_json_note
from Financial_Intelligence.obsidian_writer import build_digest as fin_digest
from Global_Intelligence.obsidian_writer import build_digest as glob_digest
from Spiritual_Intelligence.obsidian_writer import build_digest as spir_digest


def _roundtrip(payload):
    """Serialize + parse back — proves JSON-clean (no stray objects)."""
    text = json.dumps(payload, ensure_ascii=False, default=str)
    return json.loads(text)


def test_financial_digest_null_passthrough_and_meta():
    data = {
        "date": "2026-09-30",
        "signal_score": 58,
        "signal_rating": "🟡 觀望",
        "vix": None, "dxy": None, "spread_10y2y": None,   # live fetch failed
        "gold": 2650.5, "tw_margin_balance": 9_100_000,
        "_live_keys": ["gold", "twii"],
        "_source": "sample+Yahoo",
        "market_intel": [{
            "title": "<b>Fed</b> holds rates", "summary": "<p>HTML 殘骸</p>" * 40,
            "source": "https://cnbc.com/rss", "link": "https://x/y", "published": "x",
        }],
    }
    d = _roundtrip(fin_digest(data, "2026-09-30"))
    assert d["meta"]["report_id"] == "financial"
    assert d["meta"]["schema_version"] == 1
    assert d["meta"]["date"] == "2026-09-30"
    assert d["meta"]["source_chain"] == "sample+Yahoo"
    assert d["signal"] == {"score": 58, "rating": "🟡 觀望"}
    # Fail-visible: missing verdict inputs stay null, sample values don't leak
    assert d["indicators"]["vix"] is None
    assert d["indicators"]["spread_10y2y"] is None
    assert d["indicators"]["gold"] == 2650.5
    assert d["live_keys"] == ["gold", "twii"]
    # External text sanitized + trimmed
    item = d["market_intel"][0]
    assert "<" not in item["title"] and "Fed" in item["title"]
    assert len(item["summary"]) <= 301 and "<" not in item["summary"]


def test_global_digest_llm_absent_is_null():
    data = {
        "date": "2026-09-30",
        "retrieval": {"geopolitics": [{
            "title": "Summit <i>ends</i>",
            "summary": "raw html summary",
            "source": "https://bbc.co.uk/rss", "link": "https://bbc/x",
            "published": "2026-09-29",
        }]},
        "rss_items": [{"title": "live one"}],
        "trends": {"domains": {"geopolitics": {"this_week": 3, "last_week": 1,
                                                "change_pct": 200.0}},
                   "keywords": [["chips", 5], ["ai", 3]]},
        # no llm_digest — LLM layer unavailable
    }
    d = _roundtrip(glob_digest("2026-09-30", data))
    assert d["meta"]["report_id"] == "global"
    assert d["llm_digest"] is None          # the signal consumers react to
    assert d["domains"]["geopolitics"][0]["title"] == "Summit ends"
    assert d["domains"]["geopolitics"][0]["published"] == "2026-09-29"
    assert d["live_rss"][0]["title"] == "live one"
    assert d["trends"]["keywords"] == [["chips", 5], ["ai", 3]]


def test_spiritual_digest_serializes_rendered_systems():
    rendered = [{
        "id": "SYS_HD", "title": "人類圖", "subtitle": "流日",
        "spotlight": "閘 41 啟動", "system_data_summary": "5/1 生產者",
        "dimensions": [("維度A", "AI 內容"), ("維度B", "AI 內容B")],
        "what": "w", "why": "y", "action": ["1. a", "2. b"],
        "harmony_note": "h", "content_source": "AI",
    }]
    data = {
        "date": "2026-09-30",
        "_systems_rendered": rendered,
        "_render_location": "澎湖縣",
        "daily_classic": {"SYS_HD": "經典一句"},
        "transitions": ["◆ 太陽換座"],
        "motto_keywords": {"SYS_HD": "啟動"},
        "natal_section": {"SYS_HD": {"params": "1995-04-15", "compare": "對照"}},
    }
    d = _roundtrip(spir_digest("2026-09-30", data))
    assert d["meta"]["report_id"] == "spiritual"
    sys_hd = d["systems"][0]
    assert sys_hd["content_source"] == "AI"
    assert sys_hd["dimensions"] == [{"title": "維度A", "text": "AI 內容"},
                                    {"title": "維度B", "text": "AI 內容B"}]
    assert d["base"]["location"] == "澎湖縣"
    assert d["daily_classic"]["SYS_HD"] == "經典一句"
    assert d["transitions"] == ["◆ 太陽換座"]


def test_write_json_note_readable_cjk(tmp_path):
    path = write_json_note(str(tmp_path), "t.json", {"meta": digest_meta("x", "d")})
    raw = open(path, encoding="utf-8").read()
    assert "report_id" in raw
    # ensure_ascii=False keeps CJK readable instead of \uXXXX escapes
    payload = {"system": "人類圖・紫微"}
    write_json_note(str(tmp_path), "zh.json", payload)
    assert "人類圖・紫微" in open(os.path.join(str(tmp_path), "zh.json"),
                                 encoding="utf-8").read()


def test_spiritual_detail_note_uses_rendered_systems(tmp_path):
    """The markdown detail note must follow the PDF-rendered overlay (live
    spotlights + content_source), not the static SYSTEMS_CONFIG (2026-10-08)."""
    from Spiritual_Intelligence.obsidian_writer import ObsidianVaultWriter
    writer = ObsidianVaultWriter(vault_path=str(tmp_path))
    rendered = [{
        "id": "SYS_HD", "title": "人類圖", "spotlight": "📍 閘 41 XYZTEST 啟動",
        "system_data_summary": "5/1 生產者", "what": "即時覺察內容",
        "content_source": "AI",
    }]
    path = writer.write_awareness_detail_note("2026-10-08", system_data=rendered)
    live = open(path, encoding="utf-8").read()
    assert "閘 41 XYZTEST 啟動" in live
    assert "AI（流日×本命）" in live

    static = writer.write_awareness_detail_note("2026-10-07")
    static_text = open(static, encoding="utf-8").read()
    assert "閘 41 XYZTEST 啟動" not in static_text
    assert "編輯樣板" in static_text
