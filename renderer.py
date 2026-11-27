from __future__ import annotations

import colorsys
import hashlib
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "board.html"
HTML_TEMPLATE: str = _TEMPLATE_PATH.read_text(encoding="utf-8")

_HEX_COLOR_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"


def _mix_hex(hex_a: str, hex_b: str, weight_a: float) -> str:
    r1, g1, b1 = _hex_to_rgb(hex_a)
    r2, g2, b2 = _hex_to_rgb(hex_b)
    w = max(0.0, min(1.0, weight_a))
    return _rgb_to_hex(
        round(r1 * w + r2 * (1.0 - w)),
        round(g1 * w + g2 * (1.0 - w)),
        round(b1 * w + b2 * (1.0 - w)),
    )


def _normalize_brand_hex(raw_hex: str | None) -> str | None:
    """Clamp an upstream brand hex into a readable lightness range on white backgrounds."""
    if not raw_hex:
        return None
    m = _HEX_COLOR_RE.match(raw_hex.strip())
    if not m:
        return None
    r, g, b = _hex_to_rgb(m.group(1))
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    l = max(0.32, min(0.48, l))
    if s > 0.12:
        s = max(0.42, min(0.78, s))
    nr, ng, nb = colorsys.hls_to_rgb(h, l, s)
    return _rgb_to_hex(round(nr * 255), round(ng * 255), round(nb * 255))


def _derive_palette(accent: str, label: str) -> dict[str, str]:
    """Derive a full progressive fade-to-gray palette from a single vendor brand accent."""
    return {
        "label": label,
        "accent": accent,
        "accent_deep": _mix_hex(accent, "#0f172a", 0.84),
        "accent_xhigh": _mix_hex(accent, "#64748b", 0.76),
        "border": _mix_hex(accent, "#ffffff", 0.45),
        "border_xhigh": _mix_hex(accent, "#cbd5e1", 0.46),
        "border_soft": _mix_hex(accent, "#cbd5e1", 0.26),
        "bg": _mix_hex(accent, "#ffffff", 0.075),
        "bg_xhigh": _mix_hex(accent, "#f8fafc", 0.055),
        "bg_soft": _mix_hex(accent, "#f8fafc", 0.035),
        "pill_bg": _mix_hex(accent, "#ffffff", 0.15),
        "bar_high": _mix_hex(accent, "#94a3b8", 0.70),
        "bar_med": _mix_hex(accent, "#94a3b8", 0.34),
    }


# Authentic, conflict-free vendor brand accents
MAKER_BRAND_ACCENTS: dict[str, tuple[str, str]] = {
    "anthropic": ("Anthropic · Claude", "#cf4a3a"),
    "openai": ("OpenAI · GPT", "#0f9d78"),
    "google": ("Google · Gemini", "#1a73e8"),
    "deepseek": ("DeepSeek", "#3b5bdb"),
    "qwen": ("Alibaba · Qwen", "#7c3aed"),
    "z-ai": ("Z.ai · GLM", "#0e8599"),
    "moonshotai": ("Moonshot · Kimi", "#be347b"),
    "x-ai": ("xAI · Grok", "#334155"),
    "meta": ("Meta · Muse", "#0668e1"),
    "mistralai": ("Mistral", "#e05a1b"),
    "minimax": ("MiniMax", "#d43f60"),
    "tencent": ("Tencent · Hunyuan", "#0077d9"),
    "xiaomi": ("Xiaomi · MiMo", "#e65c19"),
}

MAKER_THEMES: dict[str, dict[str, str]] = {
    maker: _derive_palette(accent, label)
    for maker, (label, accent) in MAKER_BRAND_ACCENTS.items()
}

DEFAULT_THEME: dict[str, str] = _derive_palette("#475569", "Other")


def _resolve_maker_theme(
    maker: str, creator_color: str | None = None
) -> dict[str, str]:
    """Return vendor theme: curated brand color -> clamped AA creator color -> deterministic hue."""
    key = (maker or "other").strip().lower()
    if key in MAKER_THEMES:
        return MAKER_THEMES[key]
    label = key.replace("-", " ").title() if key else "Other"
    clamped = _normalize_brand_hex(creator_color)
    if clamped:
        return _derive_palette(clamped, label)
    digest = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:6], 16)
    hue = (digest % 360) / 360.0
    r, g, b = colorsys.hls_to_rgb(hue, 0.43, 0.58)
    return _derive_palette(_rgb_to_hex(round(r * 255), round(g * 255), round(b * 255)), label)


MAKER_ALIASES: dict[str, str] = {
    "gpt": "openai",
    "openai": "openai",
    "o1": "openai",
    "o3": "openai",
    "o4": "openai",
    "gemini": "google",
    "google": "google",
    "claude": "anthropic",
    "anthropic": "anthropic",
    "deepseek": "deepseek",
    "ds": "deepseek",
    "深度求索": "deepseek",
    "qwen": "qwen",
    "通义": "qwen",
    "千问": "qwen",
    "阿里": "qwen",
    "alibaba": "qwen",
    "glm": "z-ai",
    "zhipu": "z-ai",
    "智谱": "z-ai",
    "z-ai": "z-ai",
    "zai": "z-ai",
    "kimi": "moonshotai",
    "moonshot": "moonshotai",
    "月之暗面": "moonshotai",
    "grok": "x-ai",
    "xai": "x-ai",
    "x-ai": "x-ai",
    "meta": "meta",
    "llama": "meta",
    "muse": "meta",
    "mistral": "mistralai",
    "minimax": "minimax",
    "tencent": "tencent",
    "腾讯": "tencent",
    "混元": "tencent",
    "xiaomi": "xiaomi",
    "小米": "xiaomi",
}

# Future-proof effort ordering (ultra/extreme at the very top)
EFFORT_ORDER: dict[str, int] = {
    "extreme": 0,
    "ultra": 1,
    "max": 2,
    "xhigh": 3,
    "high": 4,
    "medium": 5,
    "low": 6,
    "minimal": 7,
    "reasoning": 8,
    "non-reasoning": 9,
    "": 10,
}

EFFORT_ALIASES: dict[str, str] = {
    "extreme": "extreme",
    "ultra": "ultra",
    "max": "max",
    "xhigh": "xhigh",
    "high": "high",
    "medium": "medium",
    "med": "medium",
    "low": "low",
    "minimal": "minimal",
    "min": "minimal",
    "reasoning": "reasoning",
    "推理": "reasoning",
    "non-reasoning": "non-reasoning",
    "nonreasoning": "non-reasoning",
    "无推理": "non-reasoning",
    "不推理": "non-reasoning",
}

_SOURCE_LABELS: dict[str, str] = {
    "artificial_analysis": "Artificial Analysis 官方实时榜单",
    "artificial_analysis_api": "Artificial Analysis 官方 API v2",
    "llmpricing": "LLM Pricing (AA v5 + Official Pricing)",
    "benchgecko": "Source: BenchGecko (benchgecko.ai, CC BY 4.0)",
    "custom_api": "自定义数据源 API",
    "modelgrep": "Artificial Analysis + OpenRouter (via modelgrep)",
}

# Series eligible for automatic cross-major-generation pruning
# (only triggers once the newer major generation has >= 2 active releases)
_MAJOR_GEN_SERIES = ("gemini", "gpt", "claude", "deepseek", "qwen", "glm", "kimi", "grok")

_DATE_CODE_RE = re.compile(
    r"(?:\b20\d{2}-\d{2}-\d{2}\b|\(\d{4}\)|\b(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\b|\b2[4-9](?:0[1-9]|1[0-2])\b)"
)


def _extract_lineage_info(
    maker: str, release_name: str
) -> tuple[str, tuple[int, ...], int, str | None, int | None]:
    """Parse a release name into (lineage_key, version_tuple, date_code, major_series, major_ver)."""
    clean = release_name.strip().lower()
    clean = re.sub(r"\(free\)|\(preview\)|\bpreview\b", "", clean)
    clean = re.sub(r"[_/]+", " ", clean)

    date_code = 0
    for dm in _DATE_CODE_RE.finditer(clean):
        digits = re.sub(r"\D", "", dm.group(0))
        if digits:
            val = int(digits)
            if val > date_code:
                date_code = val
    no_date = _DATE_CODE_RE.sub(" ", clean)

    tokens_str = re.sub(r"[-]+", " ", no_date)
    tokens_str = re.sub(r"\s+", " ", tokens_str).strip()

    major_series: str | None = None
    for s in _MAJOR_GEN_SERIES:
        if re.search(rf"\b{s}", tokens_str):
            major_series = s
            break

    # Extract primary version (skip parameter sizes like 27b, 120b, 397b, 31b)
    ver_tuple: tuple[int, ...] = (0,)
    major_ver: int | None = None
    ver_match = re.search(
        r"(?:\b(?:gpt|gemini|claude|qwen|glm|grok|deepseek|kimi)\s*|\bv|\bk|\bm|\s)(\d+(?:\.\d+)?)(?=\s|$)",
        tokens_str,
    )
    if ver_match:
        parts = ver_match.group(1).split(".")
        ver_tuple = tuple(int(p) for p in parts)
        major_ver = ver_tuple[0]
        s_idx, e_idx = ver_match.span(1)
        lineage_raw = tokens_str[:s_idx] + " " + tokens_str[e_idx:]
    else:
        lineage_raw = tokens_str

    lineage_raw = re.sub(r"\b[vkm]\b", " ", lineage_raw)
    lineage_key = re.sub(r"\s+", " ", lineage_raw).strip()
    return f"{maker}:{lineage_key}", ver_tuple, date_code, major_series, major_ver


def filter_outdated_models(
    models: list[dict[str, Any]],
    *,
    max_age_days: int = 180,
    keep_free_variants: bool = False,
    now_ts: float | None = None,
) -> list[dict[str, Any]]:
    """Filter out deprecated, ancient, and superseded older-version models.

    Operates at the release level so all reasoning-effort variants of an active release
    are preserved together, while superseded releases are removed completely.
    """
    now = now_ts if now_ts is not None else time.time()
    cutoff_ts = now - max_age_days * 86400 if max_age_days > 0 else 0.0

    releases: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for m in models:
        if m.get("deprecated"):
            continue
        is_free_id = str(m.get("id") or "").endswith(":free")
        if is_free_id and not keep_free_variants:
            continue
        if keep_free_variants:
            pin = m.get("price_in")
            pout = m.get("price_out")
            if (pin is None and pout is None) or (pin or 0) != 0 or (pout or 0) != 0:
                continue
        maker = str(m.get("maker") or "other").lower()
        rel_slug = str(m.get("release_slug") or m.get("id") or "").strip().lower()
        releases[(maker, rel_slug)].append(m)

    active_releases: dict[tuple[str, str], dict[str, Any]] = {}
    for key, variants in releases.items():
        maker, _ = key
        created_values = [v["created_ts"] for v in variants if v.get("created_ts")]
        created_ts = max(created_values) if created_values else None
        if cutoff_ts > 0 and created_ts is not None and created_ts < cutoff_ts:
            continue

        rel_name = str(variants[0].get("release_name") or variants[0].get("name") or "")
        lineage_key, ver_tuple, date_code, major_series, major_ver = _extract_lineage_info(
            maker, rel_name
        )
        best_iq = max(
            (v["iq"] for v in variants if isinstance(v.get("iq"), (int, float))),
            default=-1.0,
        )
        active_releases[key] = {
            "maker": maker,
            "variants": variants,
            "lineage_key": lineage_key,
            "ver_tuple": ver_tuple,
            "date_code": date_code,
            "major_series": major_series,
            "major_ver": major_ver,
            "created_ts": created_ts or 0.0,
            "best_iq": best_iq,
        }

    # Major-generation pruning when >= 2 releases already exist in the newer generation
    series_gen_counts: dict[tuple[str, str], dict[int, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for info in active_releases.values():
        if info["major_series"] and info["major_ver"] is not None:
            series_gen_counts[(info["maker"], info["major_series"])][info["major_ver"]] += 1

    series_min_major: dict[tuple[str, str], int] = {}
    for skey, gen_counts in series_gen_counts.items():
        qualifying = [gen for gen, cnt in gen_counts.items() if cnt >= 2]
        if qualifying:
            series_min_major[skey] = max(qualifying)

    after_gen_prune: dict[tuple[str, str], dict[str, Any]] = {}
    for key, info in active_releases.items():
        if info["major_series"] and info["major_ver"] is not None:
            min_gen = series_min_major.get((info["maker"], info["major_series"]))
            if min_gen is not None and info["major_ver"] < min_gen:
                continue
        after_gen_prune[key] = info

    # Same-lineage version + snapshot-date deduplication
    by_lineage: dict[str, list[tuple[tuple[str, str], dict[str, Any]]]] = defaultdict(list)
    for key, info in after_gen_prune.items():
        by_lineage[info["lineage_key"]].append((key, info))

    kept_keys: set[tuple[str, str]] = set()
    for entries in by_lineage.values():
        if len(entries) == 1:
            kept_keys.add(entries[0][0])
            continue
        best_key, _ = max(
            entries,
            key=lambda item: (
                item[1]["ver_tuple"],
                item[1]["date_code"],
                item[1]["created_ts"],
                item[1]["best_iq"],
            ),
        )
        kept_keys.add(best_key)

    result: list[dict[str, Any]] = []
    for key in kept_keys:
        result.extend(after_gen_prune[key]["variants"])
    return result


def _fmt_num(value: float) -> str:
    if value == 0:
        return "0"
    if value >= 100:
        return f"{value:.0f}"
    s = f"{value:.1f}" if value >= 10 else f"{value:.2f}"
    return s.rstrip("0").rstrip(".")


def _format_price(pin: float | None, pout: float | None) -> str:
    if pin is None and pout is None:
        return "--"
    pin_f = float(pin) if pin is not None else 0.0
    pout_f = float(pout) if pout is not None else 0.0
    if pin_f == 0.0 and pout_f == 0.0:
        return "FREE"
    return f"${_fmt_num(pin_f)} / ${_fmt_num(pout_f)}"


def _format_task_cost(cost: float | None) -> str:
    """Concise task cost without prefix (e.g. $26.5, $4.00, $0.60, $0.005)."""
    if cost is None:
        return ""
    if cost >= 10:
        return f"${_fmt_num(cost)}"
    if cost >= 0.01:
        return f"${cost:.2f}"
    return f"${cost:.3f}"


def _format_perf(tps: float | None, latency_s: float | None) -> str:
    parts: list[str] = []
    if isinstance(tps, (int, float)) and tps > 0:
        parts.append(f"{round(tps)}t/s")
    if isinstance(latency_s, (int, float)) and latency_s > 0:
        if latency_s >= 10.0:
            parts.append(f"{round(latency_s)}s")
        elif latency_s >= 1.0:
            parts.append(f"{latency_s:.1f}s")
        else:
            parts.append(f"{round(latency_s * 1000)}ms")
    return " · ".join(parts) if parts else "--"


def _blended_price(m: dict[str, Any]) -> float | None:
    pin = m.get("price_in")
    pout = m.get("price_out")
    if pin is None and pout is None:
        return None
    pin_f = float(pin) if pin is not None else 0.0
    pout_f = float(pout) if pout is not None else 0.0
    return (3.0 * pin_f + pout_f) / 4.0


def _clean_display_name(m: dict[str, Any]) -> str:
    name = str(m.get("release_name") or m.get("name") or "").strip()
    if ":" in name:
        name = name.split(":", 1)[1].strip()
    return re.sub(r"\s*\(free\)\s*$", "", name, flags=re.I)


def _effort_sort_key(m: dict[str, Any]) -> tuple[int, float]:
    ef = str(m.get("effort") or "").lower()
    order = EFFORT_ORDER.get(ef, 5)
    iq = float(m["iq"]) if isinstance(m.get("iq"), (int, float)) else -1.0
    return (order, -iq)


def _score_pct(val: Any, max_score: float) -> int:
    if not isinstance(val, (int, float)) or max_score <= 0:
        return 0
    return int(round(max(4.0, min(100.0, (float(val) / max_score) * 100.0))))


def _theme_css_vars(theme: dict[str, str]) -> str:
    return (
        f"--accent: {theme['accent']}; "
        f"--accent-deep: {theme['accent_deep']}; "
        f"--accent-xhigh: {theme['accent_xhigh']}; "
        f"--border: {theme['border']}; "
        f"--border-xhigh: {theme['border_xhigh']}; "
        f"--border-soft: {theme['border_soft']}; "
        f"--bg: {theme['bg']}; "
        f"--bg-xhigh: {theme['bg_xhigh']}; "
        f"--bg-soft: {theme['bg_soft']}; "
        f"--pill_bg: {theme['pill_bg']}; "
        f"--bar-high: {theme['bar_high']}; "
        f"--bar-med: {theme['bar_med']};"
    )


def _to_effort_tile(m: dict[str, Any], *, score_key: str, max_score: float) -> dict[str, Any]:
    val = m.get(score_key)
    score_str = f"{float(val):.1f}" if isinstance(val, (int, float)) else "--"
    return {
        "effort": str(m.get("effort_label") or "").strip(),
        "effort_key": str(m.get("effort") or "").lower(),
        "score": score_str,
        "bar_pct": _score_pct(val, max_score),
        "task_cost": _format_task_cost(m.get("cost_per_task")),
        "perf": _format_perf(m.get("tps"), m.get("latency_s")),
    }


def _to_ranking_card(
    m: dict[str, Any],
    *,
    score_key: str,
    max_score: float,
    badge: str = "",
) -> dict[str, Any]:
    maker = str(m.get("maker") or "other").lower()
    theme = _resolve_maker_theme(maker, m.get("creator_color"))
    val = m.get(score_key)
    score_str = f"{float(val):.1f}" if isinstance(val, (int, float)) else "--"
    return {
        "name": _clean_display_name(m),
        "maker_label": theme["label"],
        "effort": str(m.get("effort_label") or "").strip(),
        "effort_key": str(m.get("effort") or "").lower(),
        "score": score_str,
        "bar_pct": _score_pct(val, max_score),
        "price": _format_price(m.get("price_in"), m.get("price_out")),
        "task_cost": _format_task_cost(m.get("cost_per_task")),
        "perf": _format_perf(m.get("tps"), m.get("latency_s")),
        "badge": badge,
        "css_vars": _theme_css_vars(theme),
    }


def _build_ranking_cards(
    items: list[dict[str, Any]],
    *,
    score_key: str,
    limit: int,
    default_max: float = 70.0,
) -> list[dict[str, Any]]:
    top = items[:limit]
    max_sc = max(
        (float(m[score_key]) for m in top if isinstance(m.get(score_key), (int, float))),
        default=default_max,
    )
    return [
        _to_ranking_card(m, score_key=score_key, max_score=max_sc, badge=f"#{i + 1}")
        for i, m in enumerate(top)
    ]


def _build_vendor_section(
    maker: str,
    items: list[dict[str, Any]],
    *,
    max_releases: int | None,
    max_efforts: int | None,
    score_key: str,
    max_score: float,
) -> dict[str, Any] | None:
    by_rel: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for m in items:
        rslug = str(m.get("release_slug") or m.get("id") or "")
        by_rel[rslug].append(m)

    sorted_rels = sorted(
        by_rel.values(),
        key=lambda grp: max(
            (float(x[score_key]) for x in grp if isinstance(x.get(score_key), (int, float))),
            default=-1.0,
        ),
        reverse=True,
    )
    if max_releases is not None:
        sorted_rels = sorted_rels[:max_releases]
    if not sorted_rels:
        return None

    creator_color = next(
        (m.get("creator_color") for m in items if m.get("creator_color")), None
    )
    theme = _resolve_maker_theme(maker, creator_color)
    model_rows: list[dict[str, Any]] = []
    for grp in sorted_rels:
        grp_sorted = sorted(grp, key=_effort_sort_key)
        if max_efforts is not None:
            grp_sorted = grp_sorted[:max_efforts]
        rep = grp_sorted[0]
        price_str = _format_price(rep.get("price_in"), rep.get("price_out"))
        model_rows.append(
            {
                "name": _clean_display_name(rep),
                "price": price_str,
                "is_free": price_str == "FREE",
                "efforts": [
                    _to_effort_tile(m, score_key=score_key, max_score=max_score)
                    for m in grp_sorted
                ],
            }
        )

    return {
        "maker": maker,
        "label": theme["label"],
        "css_vars": _theme_css_vars(theme),
        "models": model_rows,
        "tile_count": sum(len(r["efforts"]) for r in model_rows),
    }


def _parse_query_tokens(query: str) -> tuple[str, str | None, bool]:
    """Parse query into (remaining_query, effort_filter, include_all_flag)."""
    tokens = query.strip().split()
    include_all = False
    effort_filter: str | None = None
    rest: list[str] = []

    for tok in tokens:
        lo = tok.lower()
        if lo in {"all", "--all", "全部", "含旧", "历史"}:
            include_all = True
            continue
        if lo in EFFORT_ALIASES and effort_filter is None:
            effort_filter = EFFORT_ALIASES[lo]
            continue
        rest.append(tok)

    return " ".join(rest).strip(), effort_filter, include_all


def build_view_data(
    models: list[dict[str, Any]],
    query: str,
    default_makers: list[str],
    max_per_maker: int,
    max_ranking_items: int,
    fetched_at: float,
    *,
    source: str = "artificial_analysis",
    is_stale: bool = False,
    is_fallback: bool = False,
    filter_outdated: bool = True,
    hide_non_reasoning: bool = True,
    max_model_age_days: int = 180,
    max_releases_per_maker: int = 5,
) -> dict[str, Any]:
    """Select, filter, sort, and structure models into either Matrix or Ranking view data."""
    raw_q, effort_filter, include_all = _parse_query_tokens(query)
    q_lower = raw_q.lower()

    is_free_mode = q_lower in {"free", "免费", "白嫖"}
    is_gecko_source = source == "benchgecko"
    apply_outdated_filter = filter_outdated and not include_all
    max_efforts = None if include_all else max(1, max_per_maker)

    working = list(models)
    if apply_outdated_filter:
        working = filter_outdated_models(
            working,
            max_age_days=max_model_age_days,
            keep_free_variants=is_free_mode,
        )
    elif not is_free_mode:
        working = [m for m in working if not str(m.get("id") or "").endswith(":free")]

    if hide_non_reasoning and effort_filter != "non-reasoning" and not include_all:
        working = [
            m
            for m in working
            if str(m.get("effort") or "").lower() != "non-reasoning"
        ]

    if effort_filter is not None:
        working = [m for m in working if str(m.get("effort") or "").lower() == effort_filter]

    effort_tag = f" · 推理强度: {effort_filter.upper()}" if effort_filter else ""
    all_tag = " · 含旧代模型" if include_all else ""

    layout = "matrix"
    sections: list[dict[str, Any]] = []
    ranking_cards: list[dict[str, Any]] = []

    title = "AI 模型实时智商榜"
    if is_gecko_source:
        subtitle = (
            f"BenchGecko 多榜综合分（ARC-AGI-2 / FrontierMath / FrontierSWE / GPQA）· API 单价 ($/1M)"
            f"{all_tag}"
        )
    else:
        subtitle = (
            f"大字 AA 智商分 · 格内右上为题均成本 · 左侧为 API 单价 ($/1M) · 底部速度 & 首答延迟"
            f"{effort_tag}{all_tag}"
        )

    if q_lower in {"coding", "code", "编程", "代码"}:
        layout = "ranking"
        title = "AI 模型编程跑分榜 (Coding)"
        subtitle = (
            f"按编程评测综合分降序 · 右上大字为题均成本 · 底部单价 ($/1M) 与速度延迟"
            f"{effort_tag}{all_tag}"
        )
        ranked = sorted(
            (m for m in working if isinstance(m.get("coding"), (int, float))),
            key=lambda m: float(m["coding"]),
            reverse=True,
        )
        ranking_cards = _build_ranking_cards(
            ranked, score_key="coding", limit=max_ranking_items, default_max=100.0
        )

    elif q_lower in {"value", "性价比", "划算", "便宜"}:
        layout = "ranking"
        title = "AI 模型性价比榜"
        has_task_cost = any(
            isinstance(m.get("cost_per_task"), (int, float)) and m["cost_per_task"] > 0
            for m in working
        )
        subtitle = (
            f"按「智商 ÷ {'题均成本' if has_task_cost else '综合单价'}」降序（仅限智商 ≥ 20）"
            f"{effort_tag}{all_tag}"
        )
        candidates: list[tuple[float, dict[str, Any]]] = []
        for m in working:
            iq = m.get("iq")
            if not isinstance(iq, (int, float)) or iq < 20.0:
                continue
            denom = m.get("cost_per_task") if has_task_cost else _blended_price(m)
            if not isinstance(denom, (int, float)) or denom <= 0:
                continue
            candidates.append((float(iq) / float(denom), m))
        candidates.sort(key=lambda x: x[0], reverse=True)
        ranking_cards = _build_ranking_cards(
            [m for _, m in candidates], score_key="iq", limit=max_ranking_items
        )

    elif is_free_mode:
        layout = "ranking"
        title = "免费 AI 模型智商榜 ($0)"
        subtitle = f"输入/输出均为 $0 的带跑分模型 · 按智商降序{effort_tag}{all_tag}"
        free_models = sorted(
            (
                m
                for m in working
                if isinstance(m.get("iq"), (int, float))
                and (m.get("price_in") or 0) == 0
                and (m.get("price_out") or 0) == 0
                and (m.get("price_in") is not None or m.get("price_out") is not None)
            ),
            key=lambda m: float(m["iq"]),
            reverse=True,
        )
        ranking_cards = _build_ranking_cards(
            free_models, score_key="iq", limit=max_ranking_items
        )

    elif q_lower in {"gecko", "benchgecko", "硬核", "多榜"} or (
        is_gecko_source and not q_lower
    ):
        layout = "ranking"
        title = "AI 模型硬核多榜综合排名 (BenchGecko)"
        subtitle = (
            f"聚合 ARC-AGI-2 / FrontierMath / FrontierSWE / GPQA 等多方基准综合分 · 右侧 API 单价 ($/1M)"
            f"{all_tag}"
        )
        ranked = sorted(
            (m for m in working if isinstance(m.get("iq"), (int, float))),
            key=lambda m: float(m["iq"]),
            reverse=True,
        )
        ranking_cards = _build_ranking_cards(
            ranked, score_key="iq", limit=max_ranking_items, default_max=100.0
        )

    elif not q_lower and effort_filter is not None:
        layout = "ranking"
        title = f"AI 模型智商榜 · {effort_filter.upper()} 档位"
        subtitle = f"按 AA 智商分降序 · 右上大字为题均成本 · 底部 API 单价与速度延迟{all_tag}"
        ranked = sorted(
            (m for m in working if isinstance(m.get("iq"), (int, float))),
            key=lambda m: float(m["iq"]),
            reverse=True,
        )
        ranking_cards = _build_ranking_cards(
            ranked, score_key="iq", limit=max_ranking_items
        )

    elif q_lower:
        maker_target = MAKER_ALIASES.get(q_lower)
        if maker_target:
            matched = [
                m
                for m in working
                if str(m.get("maker") or "").lower() == maker_target
                and isinstance(m.get("iq"), (int, float))
            ]
            label = MAKER_THEMES.get(maker_target, {}).get("label", maker_target.upper())
            if is_gecko_source:
                layout = "ranking"
                title = f"{label} 硬核多榜综合排名 (BenchGecko)"
                matched.sort(key=lambda m: float(m["iq"]), reverse=True)
                ranking_cards = _build_ranking_cards(
                    matched, score_key="iq", limit=max_ranking_items, default_max=100.0
                )
            else:
                title = f"{label} 实时智商与推理强度"
                max_sc = max((float(m["iq"]) for m in matched), default=70.0)
                sec = _build_vendor_section(
                    maker_target,
                    matched,
                    max_releases=None,
                    max_efforts=max_efforts,
                    score_key="iq",
                    max_score=max_sc,
                )
                if sec:
                    sections.append(sec)
        else:
            terms = [t for t in q_lower.split() if t]
            matched = [
                m
                for m in working
                if isinstance(m.get("iq"), (int, float))
                and all(
                    t
                    in (
                        f"{m.get('id', '')} {m.get('release_slug', '')} "
                        f"{m.get('release_name', '')} {m.get('name', '')} {m.get('maker', '')}"
                    ).lower()
                    for t in terms
                )
            ]
            if is_gecko_source:
                layout = "ranking"
                title = f"BenchGecko 硬核榜搜索：{raw_q}"
                matched.sort(key=lambda m: float(m["iq"]), reverse=True)
                ranking_cards = _build_ranking_cards(
                    matched, score_key="iq", limit=max_ranking_items, default_max=100.0
                )
            else:
                title = f"AI 模型搜索：{raw_q}"
                by_maker: dict[str, list[dict[str, Any]]] = defaultdict(list)
                for m in matched:
                    by_maker[str(m.get("maker") or "other").lower()].append(m)
                max_sc = max((float(m["iq"]) for m in matched), default=70.0)
                ordered_makers = sorted(
                    by_maker.keys(),
                    key=lambda mk: max(float(x["iq"]) for x in by_maker[mk]),
                    reverse=True,
                )
                for mk in ordered_makers:
                    sec = _build_vendor_section(
                        mk,
                        by_maker[mk],
                        max_releases=None,
                        max_efforts=max_efforts,
                        score_key="iq",
                        max_score=max_sc,
                    )
                    if sec:
                        sections.append(sec)
    else:
        by_maker = defaultdict(list)
        all_iqs: list[float] = []
        for m in working:
            if not isinstance(m.get("iq"), (int, float)):
                continue
            by_maker[str(m.get("maker") or "other").lower()].append(m)
            all_iqs.append(float(m["iq"]))
        max_sc = max(all_iqs, default=70.0)

        for maker in default_makers:
            group = by_maker.get(maker)
            if not group:
                continue
            sec = _build_vendor_section(
                maker,
                group,
                max_releases=max(1, max_releases_per_maker),
                max_efforts=max_efforts,
                score_key="iq",
                max_score=max_sc,
            )
            if sec:
                sections.append(sec)

    updated_str = datetime.fromtimestamp(fetched_at).strftime("%Y-%m-%d %H:%M")
    if is_fallback:
        stale_note = "（主源暂不可达，当前为临时回退，下次查询将自动重试）"
    elif is_stale:
        stale_note = "（上游暂不可用，当前为历史缓存）"
    else:
        stale_note = ""

    source_label = _SOURCE_LABELS.get(source, source)
    total_cards = (
        sum(s["tile_count"] for s in sections)
        if layout == "matrix"
        else len(ranking_cards)
    )

    return {
        "layout": layout,
        "title": title,
        "subtitle": subtitle,
        "sections": sections,
        "ranking_cards": ranking_cards,
        "updated_str": updated_str,
        "stale_note": stale_note,
        "source_label": source_label,
        "total_cards": total_cards,
    }


def format_text_fallback(view_data: dict[str, Any]) -> str:
    """Plain-text fallback when HTML image rendering is unavailable."""
    lines = [f"【{view_data['title']}】", view_data["subtitle"], ""]
    if view_data.get("layout") == "matrix":
        for sec in view_data.get("sections", []):
            lines.append(f"■ {sec['label']}")
            for model in sec["models"]:
                efforts_str = " | ".join(
                    f"{t['effort']}={t['score']}"
                    + (f"({t['task_cost']})" if t["task_cost"] else "")
                    for t in model["efforts"]
                )
                lines.append(f"  - {model['name']} ({model['price']}): {efforts_str}")
    else:
        for c in view_data.get("ranking_cards", []):
            prefix = f"{c['badge']} " if c["badge"] else ""
            ef = f" [{c['effort']}]" if c["effort"] else ""
            cost_part = f"{c['task_cost']} ({c['price']})" if c["task_cost"] else c["price"]
            lines.append(
                f"- {prefix}{c['name']}{ef} | 评分: {c['score']} | {cost_part} | {c['perf']}"
            )
    lines.append("")
    lines.append(
        f"数据来源：{view_data['source_label']} · 更新于 {view_data['updated_str']}{view_data['stale_note']}"
    )
    return "\n".join(lines)
