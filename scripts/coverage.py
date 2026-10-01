"""Compares DataTool's unlock list with what is on disk in each hero folder made by extract-hero.ps1,
so missing items stand out. Names are matched loosely because DataTool strips characters such as ? and :
from folder names.

    python coverage.py Genji Doomfist --root E:\\OW_Extracts
"""
import argparse
import collections
import json
import os
import unicodedata

ap = argparse.ArgumentParser()
ap.add_argument("heroes", nargs="+")
ap.add_argument("--root", default=r"E:\OW_Extracts")
args = ap.parse_args()
root = args.root.replace("\\", "/").rstrip("/")

TYPE_DIR = {"Skin": "Skin", "Emote": "Emote", "VictoryPose": "VictoryPose", "HighlightIntro": "HighlightIntro",
            "Spray": "Spray", "Icon": "Icon", "VoiceLine": "VoiceLine", "NameCard": "NameCard", "WeaponSkin": "WeaponSkin"}


def norm(s):
    s = unicodedata.normalize("NFC", s).strip().lower()
    return "".join(ch for ch in s if ch.isalnum())


def items(o, out):
    if isinstance(o, dict):
        if o.get("Type") and o.get("Name"):
            out.append(o)
        for v in o.values():
            items(v, out)
    elif isinstance(o, list):
        for v in o:
            items(v, out)


for hero in args.heroes:
    unlocks_path = f"{root}/{hero}/_logs/unlocks.json"
    if not os.path.exists(unlocks_path):
        print(f"===== {hero}: no _logs/unlocks.json (run extract-hero.ps1 first)")
        continue
    data = json.load(open(unlocks_path, encoding="utf-8-sig"))
    if hero not in data:
        print(f"===== {hero}: not in unlocks.json")
        continue
    allit = []
    items(data[hero], allit)
    base = f"{root}/{hero}/Heroes/{hero}"
    ondisk = collections.defaultdict(set)
    for t, sub in TYPE_DIR.items():
        p = os.path.join(base, sub)
        if not os.path.isdir(p):
            continue
        def disk_name(entry):  # folders keep their full name ("R.I.P"); files lose their extension
            return norm(entry.name if entry.is_dir() else os.path.splitext(entry.name)[0])
        for a in os.scandir(p):
            ondisk[t].add(disk_name(a))
            if a.is_dir():
                for b in os.scandir(a.path):
                    ondisk[t].add(disk_name(b))
    print(f"===== {hero}")
    bytype = collections.defaultdict(list)
    for it in allit:
        bytype[it["Type"]].append(it)
    for t, lst in sorted(bytype.items()):
        names = sorted({it["Name"] for it in lst})
        if t not in TYPE_DIR:
            print(f"{t:15} listed={len(lst):4} unique={len(names):4} (no own folder; extracted with skins)")
            continue
        miss = [n for n in names if norm(n) not in ondisk[t]]
        print(f"{t:15} listed={len(lst):4} unique={len(names):4} missing={len(miss)}" + (f"  -> {miss[:25]}" if miss else ""))
