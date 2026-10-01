"""Local web menu for DataTool (OWLib).

Runs on http://127.0.0.1:<port>, reads the unlock list that DataTool produces,
lets you tick what you want per hero, and runs DataTool for you in a queue.
Standard library only. Start with:  python server.py
"""
import ctypes
import json
import os
import re
import subprocess
import sys
import threading
import time
import unicodedata
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
CACHE_DIR = os.path.join(HERE, "cache")
CACHE_PATH = os.path.join(CACHE_DIR, "unlocks.json")
CACHE_META = os.path.join(CACHE_DIR, "meta.json")

DEFAULTS = {
    "datatool": r"E:\OW Mods\tools\datatool\DataTool.exe",
    "overwatch": r"C:\Games\Overwatch",
    "default_out": r"E:\OW_Extracts",
    "port": 8765,
}

# (Type in list-unlocks JSON, query name for extract-unlocks, label shown in the menu)
UNLOCK_TYPES = [
    ("Skin", "skin", "Skins"),
    ("WeaponSkin", "weaponskin", "Weapon Skins"),
    ("Emote", "emote", "Emotes"),
    ("VictoryPose", "victorypose", "Victory Poses"),
    ("HighlightIntro", "highlightintro", "Highlight Intros"),
    ("Spray", "spray", "Sprays"),
    ("Icon", "icon", "Player Icons"),
    ("VoiceLine", "voiceline", "Voice Line Unlocks"),
    ("NameCard", "namecard", "Name Cards"),
]
TYPE_BY_QUERY = {q: t for t, q, _ in UNLOCK_TYPES}
LABEL_BY_QUERY = {q: l for _, q, l in UNLOCK_TYPES}
# Listed by DataTool but not selectable on their own; they ride along with skins.
INFO_TYPES = {
    "SkinComponent": "Mythic skin components (extracted with the Mythic skin)",
    "WeaponVariant": "Weapon variants such as Golden and Jade (extracted with skins)",
}
# DataTool's query parser splits on , | = ( ) and Program.Main refuses any argument containing a double quote,
# so such names cannot be passed one at a time. * and a leading ! are query operators.
UNSAFE_NAME = re.compile(r'[,|=()"\u201d*]|^!')
BLOCKED_CHARS = "name contains , | = ( ) \" or *, which DataTool cannot take on the command line; use All for this category"
BLOCKED_COMMON_WEAPON = "DataTool skips common-rarity weapon skins"
TEXTURE_TYPES = ("png", "dds", "tif")
# DataTool exits 0 for these, so the log has to be read to know the step did nothing.
FAIL_MARKERS = (
    "Found nothing matching your query",
    "The tool cannot interpret your command",
    "Unknown type:",
    "Unknown tag:",
    "Error initializing CASC",
    "is not supported",
    "Unhandled exception",
    "Unhandled Exception",
)
MAX_LOG_LINES = 50000
MAX_BODY = 2 * 1024 * 1024

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


# ---------------------------------------------------------------- config

def load_config():
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8-sig") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                cfg.update(loaded)
        except (OSError, ValueError) as exc:
            print(f"config.json ignored: {exc}")
    else:
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
    return cfg


CONFIG = load_config()


def datatool_args(*rest):
    return [CONFIG["datatool"], CONFIG["overwatch"], *rest]


def drives():
    out = []
    if os.name != "nt":
        return out
    free = ctypes.c_ulonglong()
    total = ctypes.c_ulonglong()
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        root = f"{letter}:\\"
        if not os.path.exists(root):
            continue
        ok = ctypes.windll.kernel32.GetDiskFreeSpaceExW(root, None, ctypes.byref(total), ctypes.byref(free))
        if ok:
            out.append({"letter": letter, "free_gb": round(free.value / 2**30, 1), "total_gb": round(total.value / 2**30, 1)})
    return out


# ---------------------------------------------------------------- windows job object
# Every DataTool process is put in a job with KILL_ON_JOB_CLOSE, so closing or killing this server
# (console X button, Stop-Process, crash) also ends the extraction instead of orphaning it.

class _IoCounters(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _BasicLimit(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", ctypes.c_uint32), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_uint32),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_uint32), ("SchedulingClass", ctypes.c_uint32)]


class _ExtendedLimit(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", _BasicLimit), ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


class ChildJob:
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    JobObjectExtendedLimitInformation = 9

    def __init__(self):
        self.handle = None
        if os.name != "nt":
            return
        k32 = ctypes.windll.kernel32
        handle = k32.CreateJobObjectW(None, None)
        if not handle:
            print("Warning: could not create a job object; DataTool may outlive this server.")
            return
        info = _ExtendedLimit()
        info.BasicLimitInformation.LimitFlags = self.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k32.SetInformationJobObject(handle, self.JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)):
            print("Warning: could not configure the job object; DataTool may outlive this server.")
            return
        self.handle = handle

    def adopt(self, proc):
        if self.handle is None:
            return False
        return bool(ctypes.windll.kernel32.AssignProcessToJobObject(self.handle, int(proc._handle)))


CHILD_JOB = ChildJob()


# ---------------------------------------------------------------- unlock cache

CACHE_LOCK = threading.Lock()
REFRESH_LOCK = threading.Lock()
CACHE = {"heroes": {}, "lookup": {}, "meta": {}}


def fold(name):
    """Case- and accent-insensitive key: 'lucio' matches 'Lúcio'."""
    stripped = "".join(ch for ch in unicodedata.normalize("NFKD", name) if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", stripped.casefold())


def hero_items(hero_data):
    items = list(hero_data.get("OtherUnlocks") or []) + list(hero_data.get("UnknownUnlocks") or [])
    for bucket in (hero_data.get("LevelUnlocks") or []) + (hero_data.get("LootBoxesUnlocks") or []):
        items += bucket.get("Unlocks") or []
    seen, out = set(), []
    for it in items:
        guid = it.get("GUID")
        if guid in seen or not it.get("Name"):
            continue
        seen.add(guid)
        out.append(it)
    return out


def blocked_reason(unlock_type, item):
    if UNSAFE_NAME.search(item["Name"]):
        return BLOCKED_CHARS
    if unlock_type == "WeaponSkin" and (item.get("Rarity") or "") == "Common":
        return BLOCKED_COMMON_WEAPON
    return ""


def load_cache():
    if not os.path.exists(CACHE_PATH):
        return False
    with open(CACHE_PATH, "rb") as fh:
        data = json.loads(fh.read().decode("utf-8-sig"))
    meta = {}
    if os.path.exists(CACHE_META):
        with open(CACHE_META, encoding="utf-8-sig") as fh:
            meta = json.load(fh)
    heroes, lookup = {}, {}
    for name, hero_data in data.items():
        if not isinstance(hero_data, dict):
            continue
        by_type = {}
        for it in hero_items(hero_data):
            unlock_type = it.get("Type") or "Unknown"
            entries = by_type.setdefault(unlock_type, {})
            existing = entries.get(it["Name"])
            if existing:  # DataTool matches by name, so same-named unlocks are one choice that extracts both
                existing["count"] += 1
                continue
            entries[it["Name"]] = {
                "name": it["Name"],
                "guid": it.get("GUID"),
                "rarity": it.get("Rarity") or "",
                "event": ", ".join(it.get("Categories") or []),
                "team": it.get("EsportsTeam") or "",
                "count": 1,
                "blocked": blocked_reason(unlock_type, it),
            }
        heroes[name] = {t: sorted(v.values(), key=lambda x: x["name"].lower()) for t, v in by_type.items()}
        lookup[fold(name)] = name
    with CACHE_LOCK:
        CACHE["heroes"] = heroes
        CACHE["lookup"] = lookup
        CACHE["meta"] = meta
    return True


def resolve_hero(name):
    """Returns the canonical hero name for any spelling, or None."""
    if not isinstance(name, str) or not name.strip():
        return None
    with CACHE_LOCK:
        if name in CACHE["heroes"]:
            return name
        return CACHE["lookup"].get(fold(name))


def hero_types(name):
    with CACHE_LOCK:
        return CACHE["heroes"].get(name)


def refresh_cache():
    """Run DataTool list-unlocks and rebuild the cache. Returns (ok, message)."""
    if not REFRESH_LOCK.acquire(blocking=False):
        return False, "A rebuild is already running."
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = os.path.join(CACHE_DIR, "unlocks-new.json")  # DataTool appends .json unless the path already ends in it
        if os.path.exists(tmp):
            os.remove(tmp)
        args = datatool_args("list-unlocks", "--json", f"--out={tmp}")
        try:
            proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=600, creationflags=CREATE_NO_WINDOW)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, f"DataTool could not run: {exc}"
        output = proc.stdout + proc.stderr
        if proc.returncode != 0 or not os.path.exists(tmp) or any(m in output for m in FAIL_MARKERS):
            tail = "\n".join(output.splitlines()[-12:])
            return False, f"DataTool did not produce an unlock list (exit code {proc.returncode})\n{tail}"
        build = re.search(r"Overwatch build (\S+)", output)
        meta = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "build": build.group(1) if build else "unknown"}
        os.replace(tmp, CACHE_PATH)
        with open(CACHE_META, "w", encoding="utf-8") as fh:
            json.dump(meta, fh)
        load_cache()
        return True, f"Unlock list rebuilt for Overwatch build {meta['build']}"
    finally:
        REFRESH_LOCK.release()


def hero_summary():
    with CACHE_LOCK:
        heroes = CACHE["heroes"]
        return [{"name": n, "counts": {t: len(v) for t, v in by_type.items()}}
                for n, by_type in sorted(heroes.items(), key=lambda x: x[0].lower())]


# ---------------------------------------------------------------- jobs

JOBS = []
JOBS_LOCK = threading.Lock()
JOB_EVENT = threading.Event()
NEXT_ID = [1]


class Job:
    def __init__(self, hero, out, commands):
        with JOBS_LOCK:
            self.id = NEXT_ID[0]
            NEXT_ID[0] += 1
        self.hero = hero
        self.out = out
        self.commands = commands
        self.status = "queued"
        self.lock = threading.Lock()
        self.lines = []
        self.base = 0          # number of lines dropped from the front of self.lines
        self.step = 0
        self.created = time.time()
        self.started = None
        self.finished = None
        self.proc = None
        self.cancel_requested = False
        self.log_path = None
        self.problem = ""

    def append(self, line):
        with self.lock:
            self.lines.append(line)
            if len(self.lines) > MAX_LOG_LINES:
                drop = len(self.lines) - MAX_LOG_LINES
                del self.lines[:drop]
                self.base += drop
        if self.log_path:
            try:
                with open(self.log_path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except OSError:
                pass

    def log_slice(self, start):
        with self.lock:
            total = self.base + len(self.lines)
            start = max(self.base, min(start, total))
            return {"from": start, "total": total, "lines": self.lines[start - self.base:], "status": self.status}

    def summary(self):
        with self.lock:
            total = self.base + len(self.lines)
            last = self.lines[-1] if self.lines else ""
        return {
            "id": self.id, "hero": self.hero, "out": self.out, "status": self.status, "problem": self.problem,
            "step": self.step, "steps": [c["label"] for c in self.commands],
            "created": self.created, "started": self.started, "finished": self.finished,
            "lines": total, "last": last, "log_path": self.log_path,
        }


def ps_quote(arg):
    """Quote one argument so the preview can be pasted into PowerShell."""
    if re.fullmatch(r"[A-Za-z0-9_./:\\=+-]+", arg):
        return arg
    return "'" + arg.replace("'", "''") + "'"


def ps_command(args):
    return "& " + " ".join(ps_quote(a) for a in args)


def check_out_path(out):
    """Returns (normalized path, None) or (None, error message)."""
    if not isinstance(out, str) or not out.strip():
        return None, "No output folder given."
    out = out.strip()
    if re.search(r'[\x00-\x1f"<>|?*]', out):
        return None, "Output folder contains characters Windows does not allow in paths."
    if not re.match(r"^[A-Za-z]:\\", out):
        return None, "Output folder must be a full Windows path such as E:\\OW_Extracts\\Genji."
    norm = os.path.normpath(out)
    if len(norm.rstrip("\\")) <= 2:
        return None, "Pick a folder, not the root of a drive."
    low = norm.lower().rstrip("\\")
    protected = [os.path.normpath(CONFIG["overwatch"]), os.environ.get("SystemRoot") or r"C:\Windows",
                 os.environ.get("ProgramFiles") or r"C:\Program Files", os.environ.get("ProgramFiles(x86)") or r"C:\Program Files (x86)"]
    for p in protected:
        p = p.lower().rstrip("\\")
        if low == p or low.startswith(p + "\\"):
            return None, f"Do not extract into {p}."
    return norm, None


def is_true(value):
    return value is True


def build_commands(body):
    hero_in = body.get("hero")
    select = body.get("select") if isinstance(body.get("select"), dict) else {}
    flags = body.get("flags") if isinstance(body.get("flags"), dict) else {}
    errors, dropped = [], []

    hero = resolve_hero(hero_in)
    if hero is None:
        errors.append("No hero selected." if not hero_in else f"Hero '{hero_in}' is not in the unlock list.")
    out, err = check_out_path(body.get("out"))
    if err:
        errors.append(err)

    tex = flags.get("textures", "png")
    if tex not in TEXTURE_TYPES:
        errors.append(f"Texture type must be one of {', '.join(TEXTURE_TYPES)}.")
        tex = "png"

    types = hero_types(hero) or {} if hero else {}
    parts = []
    for _, qname, label in UNLOCK_TYPES:
        value = select.get(qname)
        if not value:
            continue
        if value == "*":
            # DataTool tags every cosmetic with leagueTeam=none by default, so a bare "*" skips esports
            # team unlocks (OWL, World Cup, OWCS). The explicit tag value "*" matches every team and none.
            parts.append(f"{qname}=(leagueTeam=*)")
            continue
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            errors.append(f"Bad selection for {label}.")
            continue
        known = {it["name"]: it for it in types.get(TYPE_BY_QUERY[qname], [])}
        names = []
        for name in dict.fromkeys(v.strip() for v in value):  # dedupe, keep order
            if not name:
                continue
            item = known.get(name)
            if item is None:
                if hero:
                    errors.append(f"'{name}' is not a {hero} {label.lower()[:-1] if label.endswith('s') else label.lower()}.")
                continue
            if item["blocked"]:
                dropped.append(f"{label}: {name} ({item['blocked']})")
                continue
            names.append(name)
        if names:
            parts.append(f"{qname}=" + ",".join(names))

    extra = []
    if is_true(flags.get("raw_sound")):
        extra.append("--raw-sound")
    if is_true(flags.get("subtitles")):
        extra.append("--subtitles-with-sounds")

    commands = []
    if parts and hero and out:
        args = datatool_args("extract-unlocks", out, hero + "|" + "|".join(parts))
        if is_true(flags.get("refpose")):
            args.append("--extract-refpose")
        if is_true(flags.get("all_lods")):
            args.append("--all-lods")
        if tex != "png":
            args.append(f"--convert-textures-type={tex}")
        args += extra
        commands.append({"label": "extract-unlocks", "args": args})
    if is_true(body.get("hero_voice")) and hero and out:
        commands.append({"label": "extract-hero-voice", "args": datatool_args("extract-hero-voice", out, hero) + extra})
    if is_true(body.get("conversations")) and hero and out:
        commands.append({"label": "extract-conversations", "args": datatool_args("extract-conversations", out, hero) + extra})
    if not commands and not errors:
        errors.append("Nothing selected." if not dropped else "Everything you picked has to be extracted with All (see below).")
    return {"hero": hero or "", "out": out or "", "commands": commands,
            "display": [ps_command(c["args"]) for c in commands], "dropped": dropped, "errors": errors}


def run_job(job):
    job.status = "running"
    job.started = time.time()
    try:
        os.makedirs(os.path.join(job.out, "_logs"), exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(job.started))
        safe_hero = re.sub(r"[^A-Za-z0-9]+", "_", job.hero)
        job.log_path = os.path.join(job.out, "_logs", f"menu-{stamp}-{safe_hero}.log")
    except OSError as exc:
        job.append(f"Cannot create output folder: {exc}")
        job.problem = "cannot create output folder"
        job.status = "failed"
        job.finished = time.time()
        return
    for index, cmd in enumerate(job.commands):
        if job.cancel_requested:
            break
        job.step = index
        job.append(f"==> {cmd['label']}: {ps_command(cmd['args'])}")
        try:
            proc = subprocess.Popen(cmd["args"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace", creationflags=CREATE_NO_WINDOW)
        except OSError as exc:
            job.append(f"Could not start DataTool: {exc}")
            job.problem = "could not start DataTool"
            job.status = "failed"
            break
        CHILD_JOB.adopt(proc)
        job.proc = proc
        if job.cancel_requested:  # cancel arrived while the process was starting
            proc.kill()
        marker_hit = ""
        for line in proc.stdout:
            line = line.rstrip("\r\n")
            job.append(line)
            if not marker_hit:
                for marker in FAIL_MARKERS:
                    if marker in line:
                        marker_hit = line.strip()
                        break
        code = proc.wait()
        job.proc = None
        if job.cancel_requested:
            job.append("Cancelled.")
            job.status = "cancelled"
            break
        if code != 0:
            job.append(f"{cmd['label']} exited with code {code}; stopping this job.")
            job.problem = f"{cmd['label']} exited with code {code}"
            job.status = "failed"
            break
        if marker_hit:
            job.append(f"{cmd['label']} reported a problem; stopping this job.")
            job.problem = marker_hit[:200]
            job.status = "failed"
            break
        job.append(f"{cmd['label']} finished.")
    else:
        job.status = "done"
    if job.cancel_requested and job.status != "cancelled":
        job.status = "cancelled"
    job.finished = time.time()


def worker():
    while True:
        JOB_EVENT.wait()
        job = None
        with JOBS_LOCK:
            for candidate in JOBS:
                if candidate.status == "queued":
                    job = candidate
                    break
            if job is None:
                JOB_EVENT.clear()
        if job is not None:
            run_job(job)


def find_job(job_id):
    with JOBS_LOCK:
        for job in JOBS:
            if job.id == job_id:
                return job
    return None


# ---------------------------------------------------------------- http

class BadRequest(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class Handler(BaseHTTPRequestHandler):
    server_version = "DataToolMenu/1.1"

    def log_message(self, fmt, *args):  # keep the console quiet
        pass

    def send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise BadRequest("Bad Content-Length header.")
        if length < 0 or length > MAX_BODY:
            raise BadRequest("Request body too large.", 413)
        raw = self.rfile.read(length) if length else b""
        if not raw.strip():
            return {}
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise BadRequest("Body is not valid JSON.")
        if not isinstance(body, dict):
            raise BadRequest("Body must be a JSON object.")
        return body

    @staticmethod
    def int_param(query, name, default=0):
        raw = (query.get(name) or [str(default)])[0]
        try:
            return int(raw)
        except ValueError:
            raise BadRequest(f"'{name}' must be a whole number.")

    def do_GET(self):
        try:
            self.handle_get()
        except BadRequest as exc:
            self.send_json({"error": str(exc)}, exc.status)

    def do_POST(self):
        try:
            self.handle_post()
        except BadRequest as exc:
            self.send_json({"error": str(exc)}, exc.status)

    def handle_get(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as fh:
                body = fh.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if url.path == "/api/config":
            with CACHE_LOCK:
                meta = dict(CACHE["meta"])
            self.send_json({
                "datatool": CONFIG["datatool"], "overwatch": CONFIG["overwatch"],
                "default_out": CONFIG["default_out"], "drives": drives(), "cache": meta,
                "types": [{"type": t, "query": q, "label": l} for t, q, l in UNLOCK_TYPES],
                "info_types": INFO_TYPES, "textures": TEXTURE_TYPES,
            })
            return
        if url.path == "/api/heroes":
            self.send_json(hero_summary())
            return
        if url.path == "/api/hero":
            name = resolve_hero((query.get("name") or [""])[0])
            data = hero_types(name) if name else None
            if data is None:
                self.send_json({"error": "unknown hero"}, 404)
            else:
                self.send_json({"name": name, "types": data})
            return
        if url.path == "/api/jobs":
            with JOBS_LOCK:
                jobs = list(JOBS)
            self.send_json([j.summary() for j in jobs])
            return
        match = re.match(r"^/api/jobs/(\d+)/log$", url.path)
        if match:
            job = find_job(int(match.group(1)))
            if job is None:
                self.send_json({"error": "no such job"}, 404)
                return
            self.send_json(job.log_slice(self.int_param(query, "from")))
            return
        self.send_json({"error": "not found"}, 404)

    def handle_post(self):
        url = urlparse(self.path)
        body = self.read_json()
        if url.path == "/api/preview":
            self.send_json(build_commands(body))
            return
        if url.path == "/api/jobs":
            plan = build_commands(body)
            if plan["errors"]:
                self.send_json(plan, 400)
                return
            job = Job(plan["hero"], plan["out"], plan["commands"])
            with JOBS_LOCK:
                JOBS.append(job)
            JOB_EVENT.set()
            self.send_json({"job": job.summary(), "dropped": plan["dropped"]})
            return
        match = re.match(r"^/api/jobs/(\d+)/(cancel|remove)$", url.path)
        if match:
            job = find_job(int(match.group(1)))
            if job is None:
                self.send_json({"error": "no such job"}, 404)
                return
            if match.group(2) == "cancel":
                if job.status not in ("queued", "running"):
                    self.send_json({"ok": False, "message": f"Job {job.id} already {job.status}."}, 409)
                    return
                job.cancel_requested = True
                if job.status == "queued":
                    job.status = "cancelled"
                    job.finished = time.time()
                proc = job.proc
                if proc is not None:
                    try:
                        proc.kill()
                    except OSError:
                        pass
                self.send_json({"ok": True})
                return
            if job.status in ("queued", "running"):
                self.send_json({"ok": False, "message": "Cancel the job before removing it."}, 409)
                return
            with JOBS_LOCK:
                JOBS[:] = [j for j in JOBS if j.id != job.id]
            self.send_json({"ok": True})
            return
        if url.path == "/api/refresh":
            ok, message = refresh_cache()
            self.send_json({"ok": ok, "message": message, "heroes": hero_summary()}, 200 if ok else 409)
            return
        if url.path == "/api/open":
            path = body.get("path")
            if os.name == "nt" and isinstance(path, str) and os.path.isdir(path.strip()):
                os.startfile(path.strip())
                self.send_json({"ok": True})
            else:
                self.send_json({"ok": False, "message": "Folder does not exist yet."}, 404)
            return
        self.send_json({"error": "not found"}, 404)


class MenuServer(ThreadingHTTPServer):
    # http.server turns on SO_REUSEADDR, which on Windows lets a second menu bind the same port
    # silently and split the requests between the two. Fail loudly instead.
    allow_reuse_address = False


def main():
    if not os.path.exists(CONFIG["datatool"]):
        print(f"DataTool not found at {CONFIG['datatool']}. Edit {CONFIG_PATH}.")
        sys.exit(1)
    if not load_cache():
        print("No unlock list yet; asking DataTool for it (about 10 seconds)...")
        ok, message = refresh_cache()
        print(message)
        if not ok:
            sys.exit(1)
    port = int(CONFIG.get("port") or DEFAULTS["port"])
    try:
        server = MenuServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        print(f"Port {port} is already in use ({exc.strerror}). Close the other menu, or set \"port\" in {CONFIG_PATH}.")
        sys.exit(1)
    threading.Thread(target=worker, daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    print(f"DataTool menu running at {url}  (Ctrl+C or close this window to stop; running extractions stop with it)")
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        with JOBS_LOCK:
            jobs = list(JOBS)
        for job in jobs:
            proc = job.proc
            if proc is not None:
                try:
                    proc.kill()
                except OSError:
                    pass


if __name__ == "__main__":
    main()
