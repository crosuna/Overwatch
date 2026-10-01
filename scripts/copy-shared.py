"""Copies one hero's slice of the all-hero extracts (<root>/_shared, made by extract-shared.ps1)
into <root>/<Hero>/Shared: abilities, perks, hero icons and lore text that mentions the hero.

    python copy-shared.py Genji Doomfist --root E:\\OW_Extracts --lore Doomfist=akande
"""
import argparse
import os
import re
import shutil

ap = argparse.ArgumentParser()
ap.add_argument("heroes", nargs="+")
ap.add_argument("--root", default=r"E:\OW_Extracts")
ap.add_argument("--lore", action="append", default=[], help="extra lore search term as Hero=term (repeatable)")
args = ap.parse_args()
ROOT = args.root.replace("\\", "/").rstrip("/")
SH = f"{ROOT}/_shared"
LORE_TERMS = {h: [h.lower()] for h in args.heroes}
for spec in args.lore:
    hero, _, term = spec.partition("=")
    LORE_TERMS.setdefault(hero, []).append(term.lower())


def hero_block(hero):
    lines = open(f"{SH}/_logs/list-heroes.log", encoding="utf-8", errors="replace").read().splitlines()
    start = lines.index(hero)
    # the next hero starts at an unindented line whose following line is an indented hero field
    end = next((i for i in range(start + 1, len(lines) - 1)
                if lines[i] and not lines[i][0].isspace() and re.match(r"^ {4}(Description|Gender):", lines[i + 1])), len(lines))
    return lines[start:end]


def loadout(hero):
    abilities, perks, section = [], [], None
    for ln in hero_block(hero):
        if ln.strip() in ("Loadouts:", "Perks:"):
            section = ln.strip()
            continue
        m = re.match(r"^ {8}(\S.*?): (\w+)$", ln)
        if m and section == "Loadouts:" and m.group(2) not in ("HeroStats", "Subrole") and not m.group(1).startswith("Role:"):
            abilities.append(m.group(1))
        elif m and section == "Perks:":
            perks.append(m.group(1))
    return abilities, perks


def key(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.isdir(src):
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)


for hero in args.heroes:
    out = f"{ROOT}/{hero}/Shared"
    log = []
    abilities, perks = loadout(hero)

    ab_dirs = {key(n): n for n in os.listdir(f"{SH}/Abilities")}
    for a in abilities:
        hit = ab_dirs.get(key(a))
        log.append(f"Ability  {a!r:40} -> {hit or 'NOT FOUND'}")
        if hit:
            copy(f"{SH}/Abilities/{hit}", f"{out}/Abilities/{hit}")

    talents = os.listdir(f"{SH}/Talents")
    for p in perks:
        ab = ab_dirs.get(key(p))
        if ab:
            copy(f"{SH}/Abilities/{ab}", f"{out}/Perks/{ab}")
        icons = [t for t in talents if key(re.sub(r"\.\d+\.\w+$", "", t)) == key(p)]
        for t in icons:
            copy(f"{SH}/Talents/{t}", f"{out}/Perks/{t}")
        log.append(f"Perk     {p!r:40} -> {ab or 'no ability folder'}; icons {icons}")

    if os.path.isdir(f"{SH}/HeroIcons/{hero}"):
        copy(f"{SH}/HeroIcons/{hero}", f"{out}/HeroIcons")
        log.append(f"HeroIcons: {len(os.listdir(f'{SH}/HeroIcons/{hero}'))} files")

    for f in sorted(os.listdir(f"{SH}/IntelDatabase/Text")):
        txt = open(f"{SH}/IntelDatabase/Text/{f}", encoding="utf-8", errors="replace").read().lower()
        if any(t in f.lower() or t in txt for t in LORE_TERMS[hero]):
            copy(f"{SH}/IntelDatabase/Text/{f}", f"{out}/Lore/{f}")
            log.append(f"Lore     {f}")

    os.makedirs(out, exist_ok=True)
    open(f"{out}/_mapping.txt", "w", encoding="utf-8").write("\n".join(log) + "\n")
    print(f"===== {hero}")
    print("\n".join(log))
