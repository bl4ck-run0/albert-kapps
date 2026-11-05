"""
KRunner-style application launcher for Albert.

Replaces the built-in applications plugin for people who want krunner-like
subsequence matching instead of Albert's strict per-word prefix matcher.
"""

import os
import shlex
import unicodedata
from configparser import ConfigParser
from pathlib import Path

md_iid = "5.0"
md_version = "1.0"
md_name = "KRunner-style Apps"
md_description = "Launch applications with krunner-like fuzzy matching"
md_license = "MIT"
md_url = "https://github.com/bl4ck-run0/albert-kapps"
md_authors = ["@bl4ck-run0"]

# ---------------------------------------------------------------------------
# Pure matching logic (no albert dependency, testable standalone)
# ---------------------------------------------------------------------------

def _norm(s):
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def is_subseq(query, target):
    it = iter(target)
    return all(ch in it for ch in query)


def match_score(query, target):
    """krunner-like score in [0,1]: substring > prefix-of-word > subsequence."""
    q = _norm(query).strip()
    t = _norm(target).strip()
    if not q or not t:
        return 0.0
    if q in t:
        idx = t.find(q)
        base = 0.82
        if idx == 0 or t[idx - 1].isspace():
            base += 0.15
        return min(1.0, base + 0.05 * min(4, len(q)))
    if is_subseq(q, t):
        return 0.45 + 0.10 * min(3.0, len(q) / max(1.0, len(t)))
    return 0.0


# ---------------------------------------------------------------------------
# Desktop entry scanning (stdlib only)
# ---------------------------------------------------------------------------

def app_directories():
    dirs = []
    home = Path.home()
    if home:
        dirs.append(home / ".local/share/applications")
    for root in ("/usr/local/share", "/usr/share"):
        dirs.append(Path(root) / "applications")
    data_dirs = os.environ.get("XDG_DATA_DIRS", "")
    for d in data_dirs.split(":"):
        if d:
            dirs.append(Path(d) / "applications")
    seen = set()
    out = []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def parse_desktop(path):
    try:
        cp = ConfigParser(interpolation=None, strict=False)
        cp.optionxform = str
        cp.read(path, encoding="utf-8")
    except Exception:
        return None
    if not cp.has_section("Desktop Entry"):
        return None
    sec = cp["Desktop Entry"]
    if sec.get("Type", "Application") != "Application":
        return None
    if sec.getboolean("NoDisplay", False) or sec.getboolean("Hidden", False):
        return None
    name = sec.get("Name") or sec.get("GenericName")
    exec_raw = sec.get("Exec")
    if not name or not exec_raw:
        return None
    try:
        exec_list = shlex.split(exec_raw)
    except ValueError:
        return None
    if not exec_list:
        return None
    icon = sec.get("Icon", "")
    terminal = sec.getboolean("Terminal", False)
    generic = sec.get("GenericName", "")
    keywords = [k.strip() for k in sec.get("Keywords", "").split(";") if k.strip()]
    comment = sec.get("Comment", "")
    workdir = sec.get("Path", "")
    exec_base = Path(exec_list[0]).name
    return {
        "id": path.name,
        "path": str(path),
        "name": name,
        "generic": generic,
        "comment": comment,
        "keywords": keywords,
        "exec": exec_list,
        "exec_base": exec_base,
        "icon": icon,
        "terminal": terminal,
        "workdir": workdir,
        "search": " ".join(
            k for k in (name, generic, " ".join(keywords), exec_base, path.stem) if k
        ),
        "fields": [f for f in (name, generic, exec_base) if f] + keywords,
    }


def scan_apps():
    apps = []
    for d in app_directories():
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.desktop")):
            app = parse_desktop(p)
            if app:
                apps.append(app)
    return apps


# ---------------------------------------------------------------------------
# Albert plugin
# ---------------------------------------------------------------------------

try:
    from albert import (
        Action,
        GlobalQueryHandler,
        Icon,
        PluginInstance,
        RankItem,
        StandardItem,
        openFile,
        runDetachedProcess,
        runTerminal,
    )
    _ALBERT_OK = True
except ImportError:
    Action = GlobalQueryHandler = Icon = PluginInstance = None
    RankItem = StandardItem = None
    openFile = runDetachedProcess = runTerminal = None
    _ALBERT_OK = False


if _ALBERT_OK:

    class AppHandler(GlobalQueryHandler):
        def __init__(self, apps):
            GlobalQueryHandler.__init__(self)
            self.apps = apps

        def id(self):
            return "kapps"

        def name(self):
            return "KRunner-style Apps"

        def description(self):
            return "Launch applications with krunner-like fuzzy matching"

        def defaultTrigger(self):
            return ""

        def allowTriggerRemap(self):
            return False

        def _best_score(self, query, app):
            best = match_score(query, app["search"])
            for f in app["fields"]:
                s = match_score(query, f)
                if s > best:
                    best = s
            return best

        def _expand_exec(self, app):
            out = []
            for token in app["exec"]:
                if token == "%%":
                    out.append("%")
                elif token in ("%U", "%u", "%F", "%f"):
                    continue
                elif token == "%c":
                    out.append(app["name"])
                else:
                    out.append(token)
            return out

        def _launch(self, app):
            cmd = self._expand_exec(app)
            if app["terminal"]:
                runTerminal(" ".join(shlex.quote(c) for c in cmd))
            else:
                runDetachedProcess(cmd, app["workdir"])

        def _open(self, app):
            openFile(app["path"])

        def _icon(self, app):
            icon = app["icon"]
            if icon:
                if Path(icon).is_absolute():
                    return Icon.image(icon)
                return Icon.theme(icon)
            return Icon.theme("system-run")

        def _item(self, app):
            subtext = app["comment"] or app["generic"] or "Application"
            actions = [
                Action("launch", "Launch", lambda a=app: self._launch(a)),
                Action("open", "Open desktop entry", lambda a=app: self._open(a)),
            ]
            return StandardItem(
                id=app["id"],
                text=app["name"],
                subtext=subtext,
                icon_factory=lambda a=app: self._icon(a),
                actions=actions,
            )

        def rankItems(self, context):
            query = context.query.strip()
            if not query:
                return []
            results = []
            for app in self.apps:
                score = self._best_score(query, app)
                if score > 0.0:
                    results.append(RankItem(item=self._item(app), score=score))
            return results

    class Plugin(PluginInstance):
        def __init__(self):
            PluginInstance.__init__(self)
            self._handler = AppHandler(scan_apps())

        def extensions(self):
            return [self._handler]


# ---------------------------------------------------------------------------
# Standalone self-check: python3 kapps.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # empty / whitespace queries never match
    assert all(match_score(q, t) == 0 for q in ["", " "] for t in ["", " ", "xyz"])

    # exact match is perfect
    assert match_score("xyz", "xyz") == 1.0

    # substring scores higher than a loose subsequence
    assert match_score("abc", "abcd") > 0.8
    assert match_score("abc", "axbyc") > 0.4
    assert match_score("abc", "abcd") > match_score("abc", "axbyc")

    # subsequence semantics
    assert is_subseq("abc", "axbyc")
    assert not is_subseq("abc", "xy")

    print("kapps matcher self-check OK")
