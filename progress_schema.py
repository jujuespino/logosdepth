"""Server-side validation of synced progress.

Mirrors `Progress.validate` in static/js/progress.js: anything that does not fit the schema is dropped,
so the server never stores (or hands back) data the app could not read. Merging happens in the client
(`Progress.mergeData`); the server only stores the result.
"""
import re

APP_ID = "logosdepth"
SCHEMA_VERSION = 1
MAX_CARDS = 2000
MAX_BYTES = 512 * 1024

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FORBIDDEN_KEYS = {"__proto__", "constructor", "prototype"}


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_date(v) -> bool:
    return isinstance(v, str) and bool(_DATE.match(v))


def _clean_card(c):
    if not isinstance(c, dict):
        return None
    if not _is_int(c.get("stage")) or not -1 <= c["stage"] <= 20:
        return None
    if not _is_date(c.get("due")):
        return None
    days = c.get("days")
    if not isinstance(days, list) or not all(_is_date(d) for d in days):
        return None
    last = c.get("lastDate")
    lapses = c.get("lapses")
    out = {
        "stage": c["stage"],
        "due": c["due"],
        "days": sorted(set(days)),
        "lapses": lapses if _is_int(lapses) and lapses >= 0 else 0,
        "lastDate": last if _is_date(last) else None,
    }
    slips = _clean_slips(c.get("slips"))
    if slips:
        out["slips"] = slips
    return out


def _clean_slips(raw):
    """Trouble-spot words for one verse: at most 12 short words with counts from 1 to 9; anything else is dropped."""
    if not isinstance(raw, dict):
        return None
    out = {}
    for word, n in raw.items():
        if len(out) >= 12:
            break
        if isinstance(word, str) and 0 < len(word) <= 40 and word.isalnum() and _is_int(n) and 1 <= n <= 9:
            out[word] = n
    return out


def clean_progress(obj):
    """Return (data, error). `data` is the sanitized {srs, xp, streak, settings} dict, or None on error."""
    if not isinstance(obj, dict) or obj.get("app") != APP_ID:
        return None, "Not LogosDepth progress data."
    version = obj.get("schemaVersion")
    if not _is_int(version) or version < 1:
        return None, "Unrecognized data version."
    if version > SCHEMA_VERSION:
        return None, "This data was made by a newer version of the app."
    d = obj.get("data")
    if not isinstance(d, dict) or not isinstance(d.get("srs"), dict):
        return None, "No progress data."
    if len(d["srs"]) > MAX_CARDS:
        return None, "Too many verses."

    srs = {}
    for key, card in d["srs"].items():
        if not isinstance(key, str) or len(key) > 80 or key in _FORBIDDEN_KEYS:
            continue
        clean = _clean_card(card)
        if clean:
            srs[key] = clean

    xp = d.get("xp")
    st = d.get("streak") if isinstance(d.get("streak"), dict) else {}
    count = st.get("count")
    settings_in = d.get("settings") if isinstance(d.get("settings"), dict) else {}
    settings = {}
    if settings_in.get("translation") in ("kjv", "web"):
        settings["translation"] = settings_in["translation"]
    pack = settings_in.get("pack")
    if isinstance(pack, str) and len(pack) <= 40:
        settings["pack"] = pack

    return {
        "srs": srs,
        "xp": xp if _is_int(xp) and xp >= 0 else 0,
        "streak": {
            "last": st["last"] if _is_date(st.get("last")) else "",
            "count": count if _is_int(count) and count >= 0 else 0,
        },
        "settings": settings,
    }, None
