"""Walks a hero extract folder: counts files and bytes per extension and top-level folder, finds zero-byte
files and files whose header does not match their extension. Writes <folder>/_logs/integrity.json.
Reads the first bytes of every .ogg/.png/.dds/.wem, so it is slow on big folders.

    python integrity.py Genji --root E:\\OW_Extracts
"""
import argparse
import collections
import json
import os

ap = argparse.ArgumentParser()
ap.add_argument("heroes", nargs="+")
ap.add_argument("--root", default=r"E:\OW_Extracts")
args = ap.parse_args()
root_dir = args.root.replace("\\", "/").rstrip("/")

SIG = {".ogg": b"OggS", ".png": b"\x89PNG", ".dds": b"DDS ", ".wem": b"RIFF"}

for hero in args.heroes:
    root = f"{root_dir}/{hero}"
    n = size = 0
    ext = collections.Counter()
    extsz = collections.Counter()
    top = collections.Counter()
    zero, bad = [], []
    for dp, dirs, files in os.walk(root):
        for f in files:
            p = os.path.join(dp, f)
            st = os.stat(p)
            n += 1
            size += st.st_size
            e = os.path.splitext(f)[1].lower()
            ext[e] += 1
            extsz[e] += st.st_size
            rel = os.path.relpath(p, root).split(os.sep)
            top["/".join(rel[:3]) if rel[0] == "Heroes" else rel[0]] += st.st_size
            if st.st_size == 0:
                zero.append(p)
                continue
            if e in SIG:
                with open(p, "rb") as fh:
                    if fh.read(4) != SIG[e]:
                        bad.append(p)
    res = {
        "hero": hero, "files": n, "gb": round(size / 2**30, 2),
        "ext": {k: [ext[k], round(extsz[k] / 2**20, 1)] for k, _ in ext.most_common(15)},
        "top_gb": {k: round(v / 2**30, 2) for k, v in sorted(top.items(), key=lambda x: -x[1])[:20]},
        "zero": len(zero), "zero_sample": zero[:10], "bad_sig": len(bad), "bad_sample": bad[:10],
    }
    os.makedirs(f"{root}/_logs", exist_ok=True)
    json.dump(res, open(f"{root}/_logs/integrity.json", "w"), indent=1)
    print(json.dumps(res, indent=1))
