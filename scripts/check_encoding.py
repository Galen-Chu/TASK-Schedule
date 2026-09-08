#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Encoding guard — 攔截「傳輸損毀亂碼」進入 repo（2026-09-08 地雷 10）。

背景：模型工具呼叫的內容在傳輸層偶發單一多位元組中文字元損毀
（U+FFFD 替換字元；一個 3-byte 中文字壞成 3 個 U+FFFD）。損毀後
檔案仍是合法 UTF-8——Python 照常 import、CI 照常綠——唯一後果是
版面/prompt 出現靜默亂碼。本腳本把這個靜默問題變成大聲失敗。

用法：
  python scripts/check_encoding.py            # 掃全部 git 追蹤的文字檔（CI 模式）
  python scripts/check_encoding.py --staged   # 只掃暫存區（pre-commit 模式）

未來擴充：報告資料的字串斷言（如關鍵表格完整性）可掛在同一入口
（見 CLAUDE.md 地雷 10 的說明）。
"""
import os
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_TEXT_EXTS = (".py", ".md", ".yml", ".yaml", ".json", ".txt", ".html", ".toml", ".cfg")
_REPLACEMENT = chr(0xFFFD)          # U+FFFD：解碼器以 errors="replace" 產生的替換字元


def _git(*args):
    out = subprocess.run(["git", *args], capture_output=True, text=True,
                         cwd=_REPO, encoding="utf-8", errors="replace")
    return [l.strip() for l in out.stdout.splitlines() if l.strip()]


def target_files(staged_only=False):
    if staged_only:
        files = _git("diff", "--cached", "--name-only", "--diff-filter=ACM")
    else:
        files = _git("ls-files")
    return [f for f in files if f.endswith(_TEXT_EXTS)]


def scan_file(path):
    """回傳 [(line_no, 該行截斷預覽)]——檔案含 U+FFFD 的位置。"""
    hits = []
    try:
        with open(os.path.join(_REPO, path), encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if _REPLACEMENT in line:
                    hits.append((i, line.strip()[:60]))
    except (OSError, UnicodeDecodeError):
        pass          # 二進位/無法解碼檔案不在此防線範圍
    return hits


def main(staged_only=False):
    bad = []
    for f in target_files(staged_only):
        for line_no, preview in scan_file(f):
            bad.append(f"{f}:{line_no}: {preview}")
    if bad:
        print("ENCODING GUARD FAILED — 發現 U+FFFD 替換字元（傳輸損毀亂碼）：",
              file=sys.stderr)
        for b in bad:
            print("  " + b, file=sys.stderr)
        print("請修復上列字元後再提交（重寫該行即可，語意不變）。",
              file=sys.stderr)
        return 1
    mode = "staged" if staged_only else "tracked"
    print(f"encoding guard: OK（掃描 {mode} 檔案，零 U+FFFD）")
    return 0


if __name__ == "__main__":
    sys.exit(main(staged_only="--staged" in sys.argv))
