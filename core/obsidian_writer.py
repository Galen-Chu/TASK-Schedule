"""Generic Obsidian markdown + JSON digest writer.

Each report builds its full markdown (frontmatter + body) and a curated
digest dict, then hands them here; this module only owns directory creation
+ file writing, so the path handling is identical across reports.

The JSON digest is the machine-readable twin of the markdown note — the
artifact downstream consumers (AI agents, the future social pipeline, the
Obsidian_Library vault import) read instead of parsing PDFs. Contract:

  {"meta": {schema_version, report_id, date, generated_at, producer,
            source_chain},
   <report-specific sections>}

Missing live values stay JSON ``null`` (never the stale sample) — the same
fail-visible doctrine as the PDF's 「數據待補」.
"""
import datetime
import json
import os

try:
    from zoneinfo import ZoneInfo
    _TAIPEI = ZoneInfo("Asia/Taipei")
except Exception:  # noqa: BLE001 — Py<3.9 or missing TZDB -> fixed +08:00
    _TAIPEI = datetime.timezone(datetime.timedelta(hours=8))


def write_note(output_dir, filename, content):
    """Write ``content`` to ``output_dir/filename``. Returns the full path."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def write_json_note(output_dir, filename, payload):
    """Write ``payload`` as UTF-8 JSON (readable CJK, no \\u escapes)."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        f.write("\n")
    return path


def digest_meta(report_id, date_str, source_chain=None):
    """Shared envelope for every report's JSON digest.

    ``schema_version`` lets downstream consumers gate on the format; bump it
    whenever a section is renamed or its meaning changes (additive new keys
    are fine without a bump). ``source_chain`` mirrors the report's ``_source``
    trace (e.g. ``live+Treasury+Gemini``).
    """
    now = datetime.datetime.now(_TAIPEI)
    return {
        "schema_version": 1,
        "report_id": report_id,
        "date": date_str,
        "generated_at": now.isoformat(timespec="seconds"),
        "producer": "TASK-Schedule",
        "source_chain": source_chain or "",
    }
