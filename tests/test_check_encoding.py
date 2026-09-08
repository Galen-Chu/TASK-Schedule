"""Encoding guard (2026-09-08 地雷 10)：U+FFFD 傳輸損毀的自動防線。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from check_encoding import scan_file, main  # noqa: E402


def test_scan_file_detects_replacement_char(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("good = 1\nbroken = '權'\n", encoding="utf-8")
    bad.write_bytes(b"good = 1\nbroken = '\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd'\n")
    hits = scan_file(str(bad))
    assert hits and hits[0][0] == 2


def test_scan_file_clean(tmp_path):
    clean = tmp_path / "clean.py"
    clean.write_text("權 = '貪狼化權'\n", encoding="utf-8")
    assert scan_file(str(clean)) == []


def test_main_exit_codes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("check_encoding.target_files",
                        lambda staged=False: ["clean.py", "bad.py"])
    clean = tmp_path / "clean.py"
    clean.write_text("ok\n", encoding="utf-8")
    bad = tmp_path / "bad.py"
    bad.write_bytes("x = '\xef\xbf\xbd'\n", encoding="utf-8", errors="ignore") \
       if False else bad.write_bytes(b"x = '\xef\xbf\xbd'\n")
    import check_encoding
    monkeypatch.setattr(check_encoding, "_REPO", str(tmp_path))
    assert main(staged_only=False) == 1
    err = capsys.readouterr().err
    assert "bad.py:1" in err
