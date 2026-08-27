#!/usr/bin/env python3
"""Download the open-source CJK (and optional Latin) TrueType fonts the reports
embed, into ``<repo>/fonts/``. Idempotent — skips files already present.

The CJK font (Noto Sans TC, SIL Open Font License) is REQUIRED for Traditional
Chinese rendering. The upstream file is a VARIABLE font; ReportLab cannot use
variable axes and embeds the default instance — which for this VF is the Thin
weight, making small white text (link badges) nearly invisible. This script
therefore instantiates STATIC Regular (wght=400) and Bold (wght=700) faces
with fonttools after downloading.

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

_VF_URL = "https://github.com/notofonts/noto-cjk/raw/main/Sans/Variable/TTF/Subset/NotoSansTC-VF.ttf"

STATIC_OUTPUTS = {
    # output name -> (wght axis value, role)
    "NotoSansTC-Regular.ttf": (400, "required"),
    "NotoSansTC-Bold.ttf": (700, "recommended"),
}

# Optional Latin fonts (improve Latin/number rendering). If absent, Latin
# runs fall back to the CJK font, which still renders fine.
FONTS = [
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


def instantiate_statics(fonts_dir):
    """Download the Noto TC variable font once, emit static Regular/Bold."""
    from fontTools import varLib
    from fontTools.varLib.instancer import instantiateVariableFont
    from fontTools.ttLib import TTFont as FTFont

    vf_path = os.path.join(fonts_dir, "NotoSansTC-VF.ttf")
    print("[get ] Noto Sans TC variable font ...")
    download(_VF_URL, vf_path)
    for out_name, (wght, role) in STATIC_OUTPUTS.items():
        dst = os.path.join(fonts_dir, out_name)
        print(f"[inst] wght={wght} -> {out_name} ({role})")
        f = FTFont(vf_path)
        instantiateVariableFont(f, {"wght": wght}, inplace=True)
        # Pin the name table so the embedded font is identifiable
        for nid, val in ((1, f"Noto Sans TC {wght}"), (4, f"Noto Sans TC {wght}"),
                         (6, f"NotoSansTC-{wght}")):
            if f["name"].getDebugName(nid):
                f["name"].setName(val, nid, 3, 1, 0x409)
        f.save(dst)
    os.remove(vf_path)


def download(url, dst):
    req = urllib.request.Request(url, headers={"User-Agent": "SparkSchedule/2.0"})
    with urllib.request.urlopen(req, timeout=180) as resp, open(dst, "wb") as out:
        out.write(resp.read())


def repo_fonts_dir():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "fonts")


def main(argv=None):
    parser = argparse.ArgumentParser(description="下載報告所需的開源字型到 fonts/")
    parser.add_argument("--force", action="store_true", help="重新下載即使檔案已存在")
    args = parser.parse_args(argv)

    fonts_dir = repo_fonts_dir()
    os.makedirs(fonts_dir, exist_ok=True)

    # CJK statics: skip when both already exist (unless --force)
    if args.force or not all(os.path.isfile(os.path.join(fonts_dir, n))
                             for n in STATIC_OUTPUTS):
        try:
            instantiate_statics(fonts_dir)
        except ImportError:
            print("[fail] 需要 fonttools 才能產生靜態字重（pip install fonttools）",
                  file=sys.stderr)
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"[fail] CJK 字型實例化失敗: {exc}", file=sys.stderr)
            return 1
    else:
        print("[skip] NotoSansTC statics 已存在")

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
