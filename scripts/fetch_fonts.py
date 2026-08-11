#!/usr/bin/env python3
"""Download the open-source CJK (and optional Latin) TrueType fonts the reports
embed, into ``<repo>/fonts/``. Idempotent — skips files already present.

The CJK font (Noto Sans TC, SIL Open Font License) is REQUIRED for Traditional
Chinese rendering. The Latin fonts (Liberation Sans, SIL OFL) are optional;
when absent, Latin runs fall back to the CJK font.

Usage:
    python scripts/fetch_fonts.py
    python scripts/fetch_fonts.py --force

Linux CI alternative (no download needed):
    sudo apt-get install -y fonts-droid-fallback fonts-liberation
"""
import argparse
import os
import sys
import urllib.request

FONTS = [
    {
        "name": "NotoSansTC-Regular.ttf",
        "url": "https://github.com/notofonts/noto-cjk/raw/main/Sans/Variable/TTF/Subset/NotoSansTC-VF.ttf",
        "required": True,
    },
    # Optional Latin fonts (improve Latin/number rendering). If absent, Latin
    # runs fall back to the CJK font, which still renders fine. Drop the TTFs
    # into fonts/ manually if you want them; no reliable auto-URL is bundled.
    {
        "name": "LiberationSans-Regular.ttf",
        "url": "https://github.com/liberationfonts/liberation-fonts/raw/main/src/LiberationSans-Regular.ttf",
        "required": False,
    },
    {
        "name": "LiberationSans-Bold.ttf",
        "url": "https://github.com/liberationfonts/liberation-fonts/raw/main/src/LiberationSans-Bold.ttf",
        "required": False,
    },
]


def repo_fonts_dir():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "fonts")


def download(url, dst):
    req = urllib.request.Request(url, headers={"User-Agent": "SparkSchedule/2.0"})
    with urllib.request.urlopen(req, timeout=180) as resp, open(dst, "wb") as out:
        out.write(resp.read())


def main(argv=None):
    parser = argparse.ArgumentParser(description="下載報告所需的開源字型到 fonts/")
    parser.add_argument("--force", action="store_true", help="重新下載即使檔案已存在")
    args = parser.parse_args(argv)

    fonts_dir = repo_fonts_dir()
    os.makedirs(fonts_dir, exist_ok=True)

    missing_required = False
    for f in FONTS:
        dst = os.path.join(fonts_dir, f["name"])
        if os.path.isfile(dst) and not args.force:
            print(f"[skip] {f['name']} 已存在")
            continue
        try:
            print(f"[get ] {f['name']} ...")
            download(f["url"], dst)
            print(f"[ok  ] {f['name']} ({os.path.getsize(dst):,} bytes)")
        except Exception as exc:  # noqa: BLE001
            print(f"[fail] {f['name']}: {exc}")
            if f["required"]:
                missing_required = True
            if os.path.isfile(dst):
                os.remove(dst)

    if missing_required:
        print("\nCJK 字型下載失敗。在 Linux/CI 可改用："
              " sudo apt-get install -y fonts-droid-fallback", file=sys.stderr)
        return 1
    print(f"\n字型目錄：{fonts_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
