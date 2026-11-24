"""gym_kit.py - stdlib-only helpers for building a gym in any project.

    python gym_kit.py --selftest

Import it (copy the file next to your gym, or put this folder on sys.path) and use what you need:

    Series            resumable {"meta": {...}, "points": [...]} file; atomic utf-8 writes; every point gets an epoch ts;
                      fresh=True MOVES the old file aside (never deletes evidence)
    compass_search    derivative-free pattern search over a dict of floats inside bounds
    multi_restart     restart 0 = the shipped seed, later restarts jittered across the bounds; stops on a plateau
                      (patience restarts without gaining eps); reports the seed's own score as the before-bar
    paired_bootstrap  CI on the mean paired delta, resampling distinct UNITS (a unit seen in several cycles is averaged
                      first) - never rows or cycles
    discordant        (b, c) counts from binary paired outcomes: b = only the candidate right, c = only the incumbent
    sign_test         exact two-sided binomial p on (b, c) = exact McNemar on discordant pairs
    power_n           units needed to shrink a CI half-width from h (measured at n units) to b
    median, frac_under  robust summaries for heavy-tailed ratios
    decide            maps n / CI / bar / void reasons to a verdict word and a reason
    write_chart       self-contained HTML line chart (inline SVG, no CDN) with a dashed before-bar, KPI tiles and notes
"""
from __future__ import annotations

import html
import json
import math
import os
import random
import statistics
import sys
import tempfile
import time
from collections import defaultdict

WORDS = ("PASS", "MARGINAL", "FAIL", "MEASURING", "STARVED", "VOID", "SATURATED")


# ----------------------------------------------------------------------------------------------- persistence

def atomic_write_json(path, obj):
    """Write JSON through a temp file in the same directory + os.replace, always utf-8."""
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=1, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


class Series:
    """A gym's series file. Resumes by default; fresh=True moves the old file to <path>.archived-<stamp>."""

    def __init__(self, path, fresh=False, meta=None):
        self.path = path
        self.archived = None
        self.data = {"meta": dict(meta or {}), "points": []}
        if os.path.exists(path):
            if fresh:
                self.archived = "%s.archived-%s" % (path, time.strftime("%Y%m%d-%H%M%S"))
                os.replace(path, self.archived)
            else:
                with open(path, encoding="utf-8") as f:
                    self.data = json.load(f)
                self.data.setdefault("points", [])
                self.data.setdefault("meta", {})
                if meta:
                    old = {k: self.data["meta"].get(k) for k in meta}
                    if old != dict(meta):
                        # a different grader / world / bank is a different instrument: never pool silently
                        raise ValueError("series %s was written under meta %r, asked to resume under %r - "
                                         "start fresh (the old file is archived, not deleted)" % (path, old, meta))

    @property
    def points(self):
        return self.data["points"]

    def append(self, point, save=True):
        p = dict(point)
        p.setdefault("ts", time.time())
        self.points.append(p)
        if save:
            self.save()
        return p

    def save(self):
        atomic_write_json(self.path, self.data)

    def window(self, t0, t1=None):
        """Points with t0 <= ts (< t1). Window on epoch ts, never on a clock string or on file order."""
        return [p for p in self.points if p.get("ts") is not None and p["ts"] >= t0 and (t1 is None or p["ts"] < t1)]

    def keys(self):
        """Union of keys over all points (points[0] can carry an obsolete schema)."""
        out = set()
        for p in self.points:
            out.update(p)
        return out


# ----------------------------------------------------------------------------------------------- search

def compass_search(score_fn, seed, bounds, step0=None, tol=None, max_evals=2000, direction="max"):
    """Derivative-free compass search. score_fn(params: dict) -> float. bounds = {name: (lo, hi)}.

    Returns {"best", "score", "evals", "trace"}; trace = [(evals, score)] at each improvement.
    """
    sign = 1.0 if direction == "max" else -1.0
    names = list(bounds)

    def clamp(p):
        return {k: min(max(float(p[k]), bounds[k][0]), bounds[k][1]) for k in names}

    step = {k: float((step0 or {}).get(k, (bounds[k][1] - bounds[k][0]) / 4.0)) for k in names}
    tl = {k: float((tol or {}).get(k, (bounds[k][1] - bounds[k][0]) * 1e-3)) for k in names}
    cur = clamp(seed)
    best = sign * score_fn(cur)
    evals = 1
    trace = [(evals, sign * best)]
    while evals < max_evals and any(step[k] > tl[k] for k in names):
        improved = False
        for k in names:
            if step[k] <= tl[k]:
                continue
            for d in (1.0, -1.0):
                cand = dict(cur)
                cand[k] = cur[k] + d * step[k]
                cand = clamp(cand)
                if cand[k] == cur[k]:
                    continue
                s = sign * score_fn(cand)
                evals += 1
                if s > best:
                    cur, best, improved = cand, s, True
                    trace.append((evals, sign * best))
                    break
                if evals >= max_evals:
                    break
        if not improved:
            for k in names:
                step[k] /= 2.0
    return {"best": cur, "score": sign * best, "evals": evals, "trace": trace}


def multi_restart(score_fn, seed, bounds, restarts=8, patience=3, eps=1e-6, rng_seed=0, jitter=0.5,
                  direction="max", **kw):
    """Restart 0 starts at the shipped seed; restart r > 0 starts at seed + uniform(-jitter, jitter) x range.

    Stops after `patience` consecutive restarts that fail to beat the best by more than eps.
    Returns {"best", "score", "seed_score", "gain", "evals", "runs"}; seed_score is the before-bar.
    """
    rng = random.Random(rng_seed)
    better = (lambda a, b: a > b + eps) if direction == "max" else (lambda a, b: a < b - eps)
    seed_score = score_fn({k: float(seed[k]) for k in bounds})
    runs, best, since, evals = [], None, 0, 1
    for r in range(restarts):
        if r == 0:
            start = {k: float(seed[k]) for k in bounds}
        else:
            start = {k: min(max(float(seed[k]) + rng.uniform(-jitter, jitter) * (hi - lo), lo), hi)
                     for k, (lo, hi) in bounds.items()}
        res = compass_search(score_fn, start, bounds, direction=direction, **kw)
        res["restart"], res["start"] = r, start
        runs.append(res)
        evals += res["evals"]
        if best is None or better(res["score"], best["score"]):
            best, since = res, 0
        else:
            since += 1
            if since >= patience:
                break
    gain = best["score"] - seed_score if direction == "max" else seed_score - best["score"]
    return {"best": best["best"], "score": best["score"], "seed_score": seed_score, "gain": gain,
            "evals": evals, "runs": runs}


# ----------------------------------------------------------------------------------------------- statistics

def median(values):
    v = [x for x in values if x is not None]
    return statistics.median(v) if v else None


def frac_under(values, bar, below=True):
    """Share of values under (or over, below=False) the bar. Pair with the median for heavy-tailed ratios."""
    v = [x for x in values if x is not None]
    if not v:
        return None
    return sum(1 for x in v if (x < bar if below else x > bar)) / len(v)


def paired_bootstrap(pairs, B=2000, seed=0, alpha=0.05):
    """pairs = iterable of (unit_id, a, b) with delta = b - a.

    Rows of the same unit are averaged first, then distinct units are resampled. Resampling rows or cycles when a unit
    repeats measures the repetition (one real lane read CI [16.67, 16.67] that way vs [-16.0, 46.3] by question).
    """
    by = defaultdict(list)
    for u, a, b in pairs:
        if a is None or b is None:
            continue
        by[u].append(float(b) - float(a))
    per = [sum(by[u]) / len(by[u]) for u in sorted(by, key=str)]
    n = len(per)
    if n == 0:
        return {"n_units": 0, "n_rows": 0, "mean": None, "lo": None, "hi": None, "half_width": None}
    rng = random.Random(seed)
    means = sorted(sum(per[rng.randrange(n)] for _ in range(n)) / n for _ in range(B))
    lo = means[int(alpha / 2 * B)]
    hi = means[min(B - 1, int((1 - alpha / 2) * B))]
    return {"n_units": n, "n_rows": sum(len(v) for v in by.values()), "mean": sum(per) / n,
            "lo": lo, "hi": hi, "half_width": (hi - lo) / 2}


def discordant(outcomes):
    """outcomes = iterable of (a_ok, b_ok) booleans per paired unit. Returns (b, c):
    b = units only the candidate (b) got right, c = units only the incumbent (a) got right."""
    b = c = 0
    for a_ok, b_ok in outcomes:
        if b_ok and not a_ok:
            b += 1
        elif a_ok and not b_ok:
            c += 1
    return b, c


def sign_test(b, c):
    """Exact two-sided binomial p for b of n = b + c at p = 0.5 (exact McNemar on discordant pairs)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2.0 ** n
    return min(1.0, 2.0 * tail)


def power_n(n, half_width, target_half_width):
    """Units needed for a CI half-width of target_half_width, given half_width measured at n units (CI ~ 1/sqrt(n))."""
    return int(math.ceil(n * (float(half_width) / float(target_half_width)) ** 2))


def decide(n, min_n, lo=None, hi=None, bar=0.0, direction="up", void=None, starved=False, saturated=False,
           guards_failed=None):
    """Map a measurement to (word, why).

    lo/hi = the CI on the headline (or on the paired delta); bar = the pre-registered threshold; direction "up" means
    higher is better. void = list of reasons the instrument broke; guards_failed = list of guard bars that failed.
    """
    if void:
        return "VOID", "instrument void: %s (n reported as 0)" % "; ".join(map(str, void))
    if n < min_n:
        return ("STARVED" if starved else "MEASURING"), "%d of %d units" % (n, min_n)
    if saturated:
        return "SATURATED", "pinned at the maximum - the test is too easy; build a harder grader"
    if guards_failed:
        return "FAIL", "guard bar failed: %s" % "; ".join(map(str, guards_failed))
    if lo is None or hi is None:
        return "MEASURING", "no CI yet"
    up = direction == "up"
    if (lo > bar) if up else (hi < bar):
        return "PASS", "CI [%.4g, %.4g] clears the bar %.4g at n=%d" % (lo, hi, bar, n)
    if (hi < bar) if up else (lo > bar):
        return "FAIL", "CI [%.4g, %.4g] misses the bar %.4g at n=%d" % (lo, hi, bar, n)
    return "MARGINAL", "CI [%.4g, %.4g] straddles the bar %.4g at n=%d" % (lo, hi, bar, n)


# ----------------------------------------------------------------------------------------------- chart

_PALETTE = ("#2b7bb9", "#d9822b", "#3a9e5f", "#c0392b", "#8e5ea2", "#7f8c8d")


def write_chart(path, title, x, series, before=None, kpis=None, notes=None, subtitle="", y_label=""):
    """Write a self-contained HTML chart.

    x = list of x values (cycle numbers or labels); series = [{"label", "data", "color"?, "dash"?}] with None for gaps;
    before = a number (or {"label", "value"}) drawn dashed across the whole run; kpis = {name: value or (value, sub)}.
    """
    W, H, L, R, T, Bm = 900, 360, 56, 16, 16, 40
    vals = [v for s in series for v in s["data"] if v is not None]
    bval = before.get("value") if isinstance(before, dict) else before
    blab = before.get("label", "before") if isinstance(before, dict) else "before"
    if bval is not None:
        vals.append(bval)
    lo, hi = (min(vals), max(vals)) if vals else (0.0, 1.0)
    if hi == lo:
        lo, hi = lo - 1.0, hi + 1.0
    pad = (hi - lo) * 0.06
    lo, hi = lo - pad, hi + pad
    nx = max(1, len(x) - 1)

    def px(i):
        return L + (W - L - R) * i / nx

    def py(v):
        return T + (H - T - Bm) * (1 - (v - lo) / (hi - lo))

    parts = ['<svg viewBox="0 0 %d %d" role="img" aria-label="%s">' % (W, H, html.escape(title))]
    for g in range(5):
        v = lo + (hi - lo) * g / 4
        parts.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" class="grid"/>' % (L, W - R, py(v), py(v)))
        parts.append('<text x="%d" y="%.1f" class="tick" text-anchor="end">%.4g</text>' % (L - 6, py(v) + 4, v))
    for i in sorted(set([0, len(x) - 1] + list(range(0, len(x), max(1, len(x) // 8))))):
        if 0 <= i < len(x):
            parts.append('<text x="%.1f" y="%d" class="tick" text-anchor="middle">%s</text>'
                         % (px(i), H - Bm + 16, html.escape(str(x[i]))))
    if bval is not None:
        parts.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" class="before"/>' % (L, W - R, py(bval), py(bval)))
    legend = []
    for si, s in enumerate(series):
        color = s.get("color") or _PALETTE[si % len(_PALETTE)]
        dash = ' stroke-dasharray="%s"' % ",".join(map(str, s["dash"])) if s.get("dash") else ""
        run = []
        for i, v in enumerate(s["data"]):
            if v is None:
                if len(run) > 1:
                    parts.append('<polyline fill="none" stroke="%s" stroke-width="2"%s points="%s"/>'
                                 % (color, dash, " ".join(run)))
                run = []
                continue
            run.append("%.1f,%.1f" % (px(i), py(v)))
        if len(run) > 1:
            parts.append('<polyline fill="none" stroke="%s" stroke-width="2"%s points="%s"/>'
                         % (color, dash, " ".join(run)))
        elif len(run) == 1:
            cx, cy = run[0].split(",")
            parts.append('<circle cx="%s" cy="%s" r="3" fill="%s"/>' % (cx, cy, color))
        legend.append('<span><i style="background:%s"></i>%s</span>' % (color, html.escape(s["label"])))
    if bval is not None:
        legend.append('<span><i class="dashed"></i>%s %.4g</span>' % (html.escape(blab), bval))
    parts.append("</svg>")

    tiles = []
    for k, v in (kpis or {}).items():
        val, sub = (v if isinstance(v, (tuple, list)) else (v, ""))
        tiles.append('<div class="tile"><div class="cap">%s</div><div class="val">%s</div><div class="sub">%s</div>'
                     '</div>' % (html.escape(str(k)), html.escape(str(val)), html.escape(str(sub))))
    notes_html = "".join("<li>%s</li>" % html.escape(str(n)) for n in (notes or []))
    doc = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>%s</title>
<style>
:root{--bg:#fbfbfa;--fg:#1d1d1b;--mute:#6b6b66;--grid:#e3e3df;--card:#ffffff}
@media (prefers-color-scheme: dark){:root{--bg:#171716;--fg:#ecece8;--mute:#9a9a94;--grid:#2c2c2a;--card:#20201f}}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif}
h1{font-size:18px;margin:0 0 2px}.subt{color:var(--mute);margin:0 0 12px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin-bottom:12px}
.tile{background:var(--card);border:1px solid var(--grid);border-radius:8px;padding:8px 10px}
.cap{color:var(--mute);font-size:12px}.val{font-size:20px;font-variant-numeric:tabular-nums}.sub{color:var(--mute);font-size:12px}
svg{width:100%%;height:auto;background:var(--card);border:1px solid var(--grid);border-radius:8px}
.grid{stroke:var(--grid)}.tick{fill:var(--mute);font-size:11px}.before{stroke:var(--mute);stroke-dasharray:6,4;stroke-width:1.5}
.legend{display:flex;flex-wrap:wrap;gap:14px;margin:8px 0;color:var(--mute)}
.legend i{display:inline-block;width:14px;height:3px;margin-right:6px;vertical-align:middle}
.legend i.dashed{background:none;border-top:2px dashed var(--mute);height:0}
ul{color:var(--mute);padding-left:18px}
</style></head><body>
<h1>%s</h1><p class="subt">%s</p><div class="tiles">%s</div>%s<div class="legend">%s</div>
<p class="subt">%s</p><ul>%s</ul></body></html>
""" % (html.escape(title), html.escape(title), html.escape(subtitle), "".join(tiles), "".join(parts),
       "".join(legend), html.escape(y_label), notes_html)
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".html", dir=d)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(doc)
    os.replace(tmp, path)
    return path


# ----------------------------------------------------------------------------------------------- selftest

def _selftest():
    checks = []

    def ok(cond, what):
        checks.append((bool(cond), what))
        print(("  ok   " if cond else "  FAIL ") + what)

    # compass search finds an interior optimum
    f = lambda p: -((p["x"] - 0.3) ** 2) - ((p["y"] + 0.2) ** 2)
    r = compass_search(f, {"x": 0.9, "y": 0.9}, {"x": (-1, 1), "y": (-1, 1)})
    ok(abs(r["best"]["x"] - 0.3) < 0.01 and abs(r["best"]["y"] + 0.2) < 0.01,
       "compass_search reaches (0.3, -0.2): got (%.4f, %.4f) in %d evals" % (r["best"]["x"], r["best"]["y"], r["evals"]))
    r = compass_search(lambda p: (p["x"] - 0.3) ** 2, {"x": 0.9}, {"x": (-1, 1)}, direction="min")
    ok(abs(r["best"]["x"] - 0.3) < 0.01, "compass_search direction=min works")

    # multi_restart: restart 0 is the seed's basin, a jittered restart finds the better basin
    two = lambda p: max(0.5 - 10 * (p["x"] - 0.2) ** 2, 1.0 - 10 * (p["x"] - 0.8) ** 2)
    m = multi_restart(two, {"x": 0.2}, {"x": (0.0, 1.0)}, restarts=10, patience=10, jitter=1.0, rng_seed=0)
    ok(m["runs"][0]["start"] == {"x": 0.2} and abs(m["runs"][0]["score"] - 0.5) < 1e-6,
       "multi_restart restart 0 = the shipped seed, stuck in its basin (0.5)")
    ok(m["score"] > 0.99 and abs(m["seed_score"] - 0.5) < 1e-9 and m["gain"] > 0.49,
       "multi_restart escapes the seed basin: best %.4f, seed %.4f, gain %.4f" % (m["score"], m["seed_score"], m["gain"]))

    # paired bootstrap resamples UNITS; repeated rows of a unit do not narrow the CI
    rng = random.Random(1)
    base = [(u, 0.0, 5.0 + rng.gauss(0, 8)) for u in range(100)]
    pb = paired_bootstrap(base)
    ok(pb["n_units"] == 100 and pb["lo"] < 5.0 < pb["hi"] and pb["lo"] > 0,
       "paired_bootstrap: mean %.2f CI [%.2f, %.2f] holds 5, excludes 0" % (pb["mean"], pb["lo"], pb["hi"]))
    rep = paired_bootstrap([row for row in base for _ in range(6)])
    ok(rep["n_units"] == 100 and rep["n_rows"] == 600 and abs(rep["half_width"] - pb["half_width"]) < 1e-9,
       "paired_bootstrap: 6 repeats per unit leave the CI unchanged (unit = question, not cycle)")
    ok(paired_bootstrap([])["mean"] is None, "paired_bootstrap: no pairs -> None, never 0.0")

    # discordant pairs, exact sign test, power
    ok(discordant([(0, 1), (0, 1), (1, 0), (1, 1), (0, 0)]) == (2, 1), "discordant counts (b only, a only)")
    ok(abs(sign_test(10, 0) - 2 / 1024) < 1e-12 and sign_test(5, 5) == 1.0 and sign_test(0, 0) == 1.0,
       "sign_test exact: (10,0) p=%.5f, (5,5) p=1, (0,0) p=1" % sign_test(10, 0))
    ok(power_n(843, 3.0, 2.0) == 1897, "power_n(843, 3.0 -> 2.0) = 1897 (a real paraphrase power call)")

    # robust summaries
    ok(median([1, None, 3, 2]) == 2 and frac_under([0.8, 0.95, 1.1, None], 0.9) == 1 / 3,
       "median / frac_under skip None")

    # verdict words
    ok(decide(500, 200, void=["grader self-check failed"])[0] == "VOID", "decide: VOID beats everything")
    ok(decide(50, 200)[0] == "MEASURING" and decide(50, 200, starved=True)[0] == "STARVED", "decide: MEASURING / STARVED")
    ok(decide(300, 200, lo=1.0, hi=6.0, bar=0.0)[0] == "PASS", "decide: PASS when the CI clears the bar")
    ok(decide(300, 200, lo=-1.0, hi=6.0, bar=0.0)[0] == "MARGINAL", "decide: MARGINAL when the CI straddles")
    ok(decide(300, 200, lo=-6.0, hi=-1.0, bar=0.0)[0] == "FAIL", "decide: FAIL when the CI misses")
    ok(decide(300, 200, lo=1.0, hi=6.0, guards_failed=["ungrounded > 0.022"])[0] == "FAIL",
       "decide: a failed guard is a FAIL even when the headline clears")
    ok(decide(300, 200, lo=0.1, hi=0.3, bar=0.9, direction="down")[0] == "PASS", "decide: direction=down")
    ok(decide(300, 200, saturated=True)[0] == "SATURATED", "decide: SATURATED")

    # series: resume, meta guard, fresh archives instead of deleting, window on ts, key union
    tmpd = tempfile.mkdtemp(prefix="gymkit-")
    sp = os.path.join(tmpd, "gym_x_series.json")
    s = Series(sp, meta={"grader": "v1"})
    s.append({"ts": 100.0, "score": 1})
    s.append({"ts": 200.0, "score": 2})
    s.append({"ts": 300.0, "score": 3, "new_key": 1})
    s2 = Series(sp, meta={"grader": "v1"})
    ok(len(s2.points) == 3 and [p["score"] for p in s2.window(150, 300)] == [2], "Series resumes and windows on ts")
    ok("new_key" in s2.keys() and "new_key" not in s2.points[0], "Series.keys() = union (points[0] is not the schema)")
    try:
        Series(sp, meta={"grader": "v2"})
        ok(False, "Series refuses to resume under a different grader version")
    except ValueError:
        ok(True, "Series refuses to resume under a different grader version")
    s3 = Series(sp, fresh=True, meta={"grader": "v2"})
    ok(s3.archived and os.path.exists(s3.archived) and not s3.points, "Series(fresh=True) moves the old file aside")

    # chart
    cp = write_chart(os.path.join(tmpd, "report.html"), "Test gym", list(range(6)),
                     [{"label": "score", "data": [1, 2, None, 3, 3.5, 3.6]}, {"label": "null", "data": [1] * 6}],
                     before=1.5, kpis={"Headline": ("3.6", "before 1.5"), "n": 6}, notes=["regression = below 1.5"])
    with open(cp, encoding="utf-8") as fh:
        doc = fh.read()
    ok("<svg" in doc and "stroke-dasharray" in doc and "Test gym" in doc and "regression = below 1.5" in doc,
       "write_chart writes a self-contained page with a dashed before-bar")

    n_ok = sum(1 for c, _ in checks if c)
    print("selftest: %d/%d ok  (temp files in %s)" % (n_ok, len(checks), tmpd))
    return 0 if n_ok == len(checks) else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    print(__doc__)
