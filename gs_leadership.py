#!/usr/bin/env python3
"""gs_leadership.py — Deterministic co-leadership resolution for Golden Stack.

Single source of truth shared by the transformation (``update_db.process_group``)
and the local dashboard (``app.py`` / ``app_fetched.py``) for the question:

    "Which brand(s) hold the best (minimum) average rank for this
     batch × prompt × motor group?"

Why this module exists
----------------------
The legacy transformation iterated a Python ``set`` of brands and kept the
first brand achieving the strict minimum (``rank_avg < best``). Iteration order
of a ``set`` depends on string hashing, so on identical input the winner changed
with ``PYTHONHASHSEED`` whenever two brands shared the same minimum average
(verified on the real historical corpus: 23 of 201 groups flip between seeds
1↔2, 16 between 1↔3). That is non-determinism, not a business rule.

Policy implemented here
-----------------------
* **Ties are co-leadership.** Every brand whose average rank equals the minimum
  is a co-leader; none is discarded by an alphabetical or hash tie-break.
* **Comparison is exact.** The average rank used to pick the winner(s) is an
  exact rational (``sum(ranks) / count`` as :class:`fractions.Fraction`), never
  the 2-dp rounded value. Rounding two distinct averages to 2 dp can collide and
  manufacture a *false tie*; exact comparison cannot. The number *displayed* on
  the dashboard (``brand_rank_avg``, rounded to 2 dp) is unchanged.
* **Order is stable.** Leader names are sorted by Unicode code point, so the
  label is identical regardless of seed, dict insertion order or platform.
* **The label is not a brand.** The tie label ``"Empate: A y B"`` is a UI
  string. Downstream code must parse it (:func:`parse_top_brand_label`) and must
  never look it up in a brand→color map, an aggregation key, or a filter.
* **No schema change.** ``top_brand`` stays a text column; ``is_top_brand`` is
  TRUE for every co-leader; ``top_brand_rank`` remains the minimum average.

Historical rows
---------------
The dashboard can recompute co-leaders from ``marcas`` rows
(``brand_ranks_by_rep``) for batches written before this policy, so old
single-winner flags do not hide a genuine tie on screen.

This module is intentionally pure stdlib (no pandas / dash / plotly), so it can
be imported by the transform and by component builders alike.
"""
from __future__ import annotations

import json
import re
from fractions import Fraction

# ── label grammar ───────────────────────────────────────────────────────────
TIE_PREFIX = "Empate: "
TIE_CONJUNCTION = " y "
TIE_LIST_SEP = ", "

# Neutral color for a co-leadership badge. Deliberately NOT a brand color:
# the tie label must never be resolved against the brand palette.
TIE_COLOR = "#94A3B8"

# UI label for a group with ranked brands but none ranked in a majority of
# replicates. Like the tie label, it is NOT a brand (never stored in DB:
# metricas.top_brand stays NULL in that case).
NO_LEADER_LABEL = "Sin líder consistente"
DEFAULT_LEADER_COLOR = "#64748B"

_TIE_SPLIT_RE = re.compile(r"\s*,\s*|\s+y\s+")


def _truthy(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "t", "yes", "y")
    return bool(value)


def _parse_ranks(raw):
    """Return a list[int] of per-replicate ranks, or [] when unavailable.

    Accepts a list/tuple of numbers, or a JSON-encoded string (as stored in the
    ``brand_ranks_by_rep`` column). Never raises.
    """
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        seq = raw
    elif isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        try:
            seq = json.loads(s)
        except Exception:
            return []
        if not isinstance(seq, (list, tuple)):
            return []
    else:
        return []
    out = []
    for x in seq:
        if x is None:
            continue
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            return []
    return out


def exact_rank_avg(ranks):
    """Exact rational mean of a non-empty rank sequence, else ``None``.

    ``exact_rank_avg([1, 3]) == Fraction(2, 1)``.
    """
    ranks = [int(r) for r in ranks]
    if not ranks:
        return None
    return Fraction(sum(ranks), len(ranks))


def min_support(n_success):
    """Réplicas con posición exigidas para competir por liderazgo: mayoría.

    3 → 2, 2 → 2, 1 → 1, 0/None → 0 (sin filtro).
    """
    try:
        n = int(n_success)
    except (TypeError, ValueError):
        return 0
    return n // 2 + 1 if n > 0 else 0


def supported_scores(ranks_by_brand, n_success):
    """``{brand: exact avg}`` solo para marcas con posición en la mayoría de réplicas."""
    need = min_support(n_success)
    return {b: exact_rank_avg(r) for b, r in ranks_by_brand.items()
            if r and len(r) >= need}


def _infer_n_success(rows, ranks_key="brand_ranks_by_rep"):
    """Réplicas exitosas del grupo a partir de filas ``marcas`` (sin metricas).

    brand_presence_pct = brand_mentions_total / num_success * 100 tanto en filas
    nuevas como históricas, así que num_success = mentions * 100 / presence.
    Devuelve None si no se puede inferir (entonces no se aplica el filtro).
    """
    best = None
    for r in rows:
        try:
            mentions = float(r.get("brand_mentions_total"))
            presence = float(r.get("brand_presence_pct"))
        except (TypeError, ValueError):
            continue
        if presence > 0 and mentions > 0 and presence == presence:
            n = int(round(mentions * 100.0 / presence))
            best = n if best is None else max(best, n)
    return best


def resolve_co_leaders(scores):
    """Resolve the co-leader set from ``{brand: exact Fraction | None}``.

    Returns ``(leaders, min_score)`` where ``leaders`` is a tuple of brand names
    (sorted) sharing the exact minimum, and ``min_score`` is that minimum
    (:class:`Fraction`) or ``None`` when there is no score.
    """
    valid = {str(b): s for b, s in scores.items() if s is not None}
    if not valid:
        return (), None
    minimum = min(valid.values())
    leaders = tuple(sorted(b for b, s in valid.items() if s == minimum))
    return leaders, minimum


def resolve_group_leaders(rows, flag_key: str = "is_top_brand",
                          avg_key: str = "brand_rank_avg",
                          ranks_key: str = "brand_ranks_by_rep",
                          n_success=None):
    """Resolve co-leaders from aggregated ``marcas`` rows (dashboard path).

    Priority:
      1. exact rational average rebuilt from ``ranks_key`` per-replicate ranks,
         only for brands ranked in a majority of successful replicates
         (``n_success`` given or inferred from presence; see :func:`min_support`).
         If ranks exist but no brand has majority support → ``()`` (no leader);
      2. rounded-minimum equality on ``avg_key`` (rows without ranks);
      3. the legacy single-winner ``flag_key``.

    Returns a sorted tuple of brand names (possibly empty).
    """
    rows = list(rows or [])
    if not rows:
        return ()

    ranks_by_brand = {}
    for r in rows:
        ranks = _parse_ranks(r.get(ranks_key))
        name = str(r.get("brand_name"))
        if name and ranks:
            ranks_by_brand[name] = ranks
    if ranks_by_brand:
        if n_success is None:
            n_success = _infer_n_success(rows, ranks_key)
        leaders, _ = resolve_co_leaders(supported_scores(ranks_by_brand, n_success))
        return leaders

    pairs = [(str(r.get("brand_name")), r.get(avg_key))
             for r in rows if r.get("brand_name") is not None and r.get(avg_key) is not None]
    if pairs:
        minimum = min(v for _, v in pairs)
        return tuple(sorted(b for b, v in pairs if v == minimum))

    flagged = sorted(str(r.get("brand_name")) for r in rows
                     if r.get("brand_name") is not None and _truthy(r.get(flag_key)))
    return tuple(flagged)


def format_top_brand_label(leaders):
    """Render the ``top_brand`` label for a leader set.

    >>> format_top_brand_label(("Alegra",))
    'Alegra'
    >>> format_top_brand_label(("Siigo", "Alegra"))
    'Empate: Alegra y Siigo'
    >>> format_top_brand_label(())
    """
    names = sorted(str(x) for x in (leaders or ()) if x not in (None, ""))
    if not names:
        return None
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return TIE_PREFIX + names[0] + TIE_CONJUNCTION + names[1]
    return TIE_PREFIX + TIE_LIST_SEP.join(names[:-1]) + TIE_CONJUNCTION + names[-1]


def is_tie_label(label) -> bool:
    """True when ``label`` is a co-leadership label rather than a single brand."""
    return isinstance(label, str) and label.startswith(TIE_PREFIX)


def parse_top_brand_label(label):
    """Inverse of :func:`format_top_brand_label`; tolerant of NaN/None/''.

    Returns a tuple of brand names (empty for missing/blank labels).
    """
    if not isinstance(label, str):
        return ()
    label = label.strip()
    if not label or label == NO_LEADER_LABEL:
        return ()
    if not label.startswith(TIE_PREFIX):
        return (label,)
    body = label[len(TIE_PREFIX):].strip()
    parts = tuple(p for p in (s.strip() for s in _TIE_SPLIT_RE.split(body)) if p)
    return parts


def leader_badge_color(label, palette, default: str = DEFAULT_LEADER_COLOR,
                       tie_color: str = TIE_COLOR) -> str:
    """Badge color for a leader label.

    A co-leadership label (or a missing label) maps to a neutral color and is
    NEVER looked up in ``palette`` — the tie label is not a brand.
    """
    if not isinstance(label, str) or not label.strip():
        return tie_color
    if label.startswith(TIE_PREFIX) or label == NO_LEADER_LABEL:
        return tie_color
    return palette.get(label, default)


def segment_leader_names(labels):
    """Flatten an iterable of ``top_brand`` labels into unique co-leader names.

    Used by insight/segment summaries so a tie contributes both names instead of
    a pseudo brand such as ``"Empate: Alegra y Siigo"``.
    """
    names = set()
    for label in labels:
        names.update(parse_top_brand_label(label))
    return tuple(sorted(names))


def combo_leader_labels(rows, key_fields=("batch_id", "prompt_id", "model_source"),
                        flag_key: str = "is_top_brand",
                        avg_key: str = "brand_rank_avg",
                        ranks_key: str = "brand_ranks_by_rep"):
    """Map ``tuple(key_fields) -> deterministic leader label`` from marcas rows.

    Pure-stdlib so both Dash apps can call it with ``mar_df.to_dict("records")``.
    """
    groups = {}
    for r in rows or []:
        key = tuple(r.get(f) for f in key_fields)
        groups.setdefault(key, []).append(r)
    return {k: group_leader_label(v, flag_key, avg_key, ranks_key) for k, v in groups.items()}


def group_leader_label(rows, flag_key: str = "is_top_brand",
                       avg_key: str = "brand_rank_avg",
                       ranks_key: str = "brand_ranks_by_rep", n_success=None):
    """Leader label for one group's ``marcas`` rows.

    Returns the brand / 'Empate: …' label; :data:`NO_LEADER_LABEL` when the group
    has per-replicate ranks but no brand reaches majority support (callers must
    NOT fall back to a stored legacy top_brand then); ``None`` when nothing
    can be resolved.
    """
    rows = list(rows or [])
    label = format_top_brand_label(
        resolve_group_leaders(rows, flag_key, avg_key, ranks_key, n_success))
    if label is None and any(_parse_ranks(r.get(ranks_key)) for r in rows):
        return NO_LEADER_LABEL
    return label
