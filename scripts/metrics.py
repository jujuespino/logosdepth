#!/usr/bin/env python3
"""Beta metrics from the opt-in events table, plus the feedback inbox.

  python3 scripts/metrics.py [--db instance/logosdepth.db] [--feedback] [--json]

Everything is computed over installs that opted in, so treat the numbers as a sample of the
people who agreed to share usage, not of all users.
"""
import argparse
import json
import sqlite3
import sys
from datetime import date, timedelta

FUNNEL = [
    ("opened the app", "app_open", None),
    ("finished the intro", "onboarding_done", None),
    ("started a verse", "verse_started", None),
    ("typed a verse from memory", "typed_attempt", None),
    ("recalled a verse perfectly", "typed_attempt", "perfect"),
    ("started a daily review", "review_started", None),
    ("finished a daily review", "review_finished", None),
]
RETENTION_DAYS = (1, 3, 7, 14, 30)


def _installs(conn, name, prop=None):
    q = "SELECT COUNT(DISTINCT install_id) FROM events WHERE name = ?"
    args = [name]
    if prop is not None:
        q += " AND prop = ?"
        args.append(prop)
    return conn.execute(q, args).fetchone()[0]


def compute(conn, today=None):
    today = today or date.today()
    total = conn.execute("SELECT COUNT(DISTINCT install_id) FROM events").fetchone()[0]

    first_day = {r[0]: date.fromisoformat(r[1]) for r in conn.execute(
        "SELECT install_id, MIN(day) FROM events GROUP BY install_id")}
    active = {}
    for install, day in conn.execute("SELECT DISTINCT install_id, day FROM events"):
        active.setdefault(install, set()).add(date.fromisoformat(day))

    retention = {}
    for n in RETENTION_DAYS:
        # Only installs old enough to have had a chance to come back on day n.
        eligible = [i for i, d in first_day.items() if d + timedelta(days=n) <= today]
        back = [i for i in eligible if first_day[i] + timedelta(days=n) in active[i]]
        retention[f"day{n}"] = {
            "eligible": len(eligible), "returned": len(back),
            "rate": round(len(back) / len(eligible), 3) if eligible else None,
        }

    daily = []
    for k in range(13, -1, -1):
        d = today - timedelta(days=k)
        daily.append({"day": d.isoformat(), "active": sum(1 for s in active.values() if d in s)})

    funnel = []
    for label, name, prop in FUNNEL:
        n = _installs(conn, name, prop)
        funnel.append({"step": label, "installs": n, "of_total": round(n / total, 3) if total else None})

    outcomes = {r[0]: r[1] for r in conn.execute(
        "SELECT COALESCE(prop, 'unknown'), COUNT(*) FROM events WHERE name = 'typed_attempt' GROUP BY prop")}
    feedback = {r[0]: r[1] for r in conn.execute("SELECT kind, COUNT(*) FROM feedback GROUP BY kind")}

    return {
        "as_of": today.isoformat(), "installs_opted_in": total, "retention": retention,
        "daily_active": daily, "funnel": funnel, "typed_attempt_outcomes": outcomes, "feedback_by_kind": feedback,
    }


def feedback_rows(conn, limit=50):
    return [dict(r) for r in conn.execute(
        "SELECT id, datetime(created_at, 'unixepoch') AS at, kind, message, contact, context "
        "FROM feedback ORDER BY id DESC LIMIT ?", (limit,))]


def render(report):
    out = [
        f"LogosDepth beta metrics as of {report['as_of']}",
        f"Installs that opted in to usage sharing: {report['installs_opted_in']}",
        "",
        "Retention (returned exactly N days after first use)",
    ]
    for k, v in report["retention"].items():
        rate = "n/a" if v["rate"] is None else f"{v['rate'] * 100:.0f}%"
        out.append(f"  {k:6} {rate:>5}   ({v['returned']} of {v['eligible']} eligible)")
    out += ["", "Funnel (installs that ever did this)"]
    for f in report["funnel"]:
        pct = "n/a" if f["of_total"] is None else f"{f['of_total'] * 100:.0f}%"
        out.append(f"  {f['step']:30} {f['installs']:>4}  {pct:>5}")
    outcomes = ", ".join(f"{k}={v}" for k, v in report["typed_attempt_outcomes"].items()) or "none"
    feedback = ", ".join(f"{k}={v}" for k, v in report["feedback_by_kind"].items()) or "none"
    out += ["", f"Typed attempts by outcome: {outcomes}", f"Feedback by kind: {feedback}", "",
            "Active installs per day (last 14 days)"]
    out += [f"  {d['day']}  {'#' * d['active']} {d['active']}" for d in report["daily_active"]]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="instance/logosdepth.db")
    ap.add_argument("--feedback", action="store_true", help="print the feedback inbox instead of metrics")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        data = feedback_rows(conn) if args.feedback else compute(conn)
    except sqlite3.OperationalError as e:
        sys.exit(f"Could not read {args.db}: {e}")
    if args.json:
        print(json.dumps(data, indent=2))
    elif args.feedback:
        for r in data:
            print(f"#{r['id']} {r['at']} [{r['kind']}] {r['contact'] or '(no contact)'}\n    {r['message']}\n")
    else:
        print(render(data))


if __name__ == "__main__":
    main()
