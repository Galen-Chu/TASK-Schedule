"""Unit tests for the optional Drive / Gmail / LLM dispatch (no-op paths).

Without credentials/keys configured, every dispatch surface must degrade to a
safe no-op (return None) rather than raise.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dispatch import drive_uploader, gmail_dispatcher
from core import llm


def test_drive_noop_without_creds(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    # force a fresh probe
    monkeypatch.setattr(drive_uploader, "_tried_init", False)
    monkeypatch.setattr(drive_uploader, "_service", None)
    assert drive_uploader.is_configured() is False
    assert drive_uploader.upload_to_drive("/nonexistent.pdf") is None


def test_gmail_noop_without_creds(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    assert gmail_dispatcher.send_digest("a@b.c", "s", "b") is None


def test_llm_noop_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(llm, "_AVAILABLE", False)
    assert llm.is_available() is False
    assert llm.generate("anything") is None
    assert llm.summarize_news_what_why_sowhat([{"title": "x"}]) is None
