from __future__ import annotations

import re
import time
from collections import defaultdict
from datetime import datetime
from typing import Any

# Theme palette per vendor: accent, border, soft_bg, pill_bg
MAKER_THEMES: dict[str, dict[str, str]] = {
    "anthropic": {
        "label": "Anthropic · Claude",
        "accent": "#cf4642",
        "border": "#ebb0ad",
        "bg": "#fff7f6",
        "pill_bg": "#fde5e3",
    },
    "openai": {
        "label": "OpenAI · GPT",
        "accent": "#b87a14",
        "border": "#e6c687",
        "bg": "#fffbf2",
        "pill_bg": "#fdf0d5",
    },
    "google": {
        "label": "Google · Gemini",
        "accent": "#2567bd",
        "border": "#9cc1f0",
        "bg": "#f4f9ff",
        "pill_bg": "#e0edfe",
    },
    "deepseek": {
        "label": "DeepSeek",
        "accent": "#0e8a70",
        "border": "#88d4c3",
        "bg": "#f2fcf9",
        "pill_bg": "#daf5ee",
    },
    "qwen": {
        "label": "Alibaba · Qwen",
        "accent": "#6845c9",
        "border": "#bcacee",
        "bg": "#f8f6ff",
        "pill_bg": "#eae3fc",
    },
    "z-ai": {
        "label": "Z.ai · GLM",
        "accent": "#3e58c9",
        "border": "#a4b4ee",
        "bg": "#f4f7ff",
        "pill_bg": "#e2e8fd",
    },
    "moonshotai": {
        "label": "Moonshot · Kimi",
        "accent": "#b5387d",
        "border": "#e3a1c5",
        "bg": "#fff5fa",
        "pill_bg": "#fbe2f0",
    },
    "x-ai": {
        "label": "xAI · Grok",
        "accent": "#475569",
        "border": "#aebac9",
        "bg": "#f7f9fb",
        "pill_bg": "#e6ebf1",
    },
    "meta": {
        "label": "Meta",
        "accent": "#2563c9",
        "border": "#9cbcf0",
        "bg": "#f4f8ff",
        "pill_bg": "#e0ecfe",
    },
    "mistralai": {
        "label": "Mistral",
        "accent": "#cc5f1d",
        "border": "#ebb492",
        "bg": "#fff8f4",
        "pill_bg": "#fde9dc",
    },
    "minimax": {
        "label": "MiniMax",
        "accent": "#be405d",
        "border": "#e6a3b3",
        "bg": "#fff6f8",
        "pill_bg": "#fbe3e8",
    },
    "tencent": {
        "label": "Tencent · Hunyuan",
        "accent": "#1d75bc",
        "border": "#94c4ea",
        "bg": "#f3faff",
        "pill_bg": "#deeffc",
    },
    "xiaomi": {
        "label": "Xiaomi · MiMo",
        "accent": "#c95d16",
        "border": "#ebb38c",
        "bg": "#fff8f2",
        "pill_bg": "#fde9da",
    },
}

DEFAULT_THEME: dict[str, str] = {
    "label": "Other",
    "accent": "#475569",
    "border": "#cbd5e1",
    "bg": "#f8fafc",
    "pill_bg": "#e8edf3",
}

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
    "llama": "meta-llama",
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

    # Extract snapshot date codes like 1017, 0910, 0813, 0423, (0902), 2026-02-15
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
            "rel_name": rel_name,
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
    for _, entries in by_lineage.items():
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
    if value >= 10:
        s = f"{value:.1f}"
    else:
        s = f"{value:.2f}"
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
    """Concise task cost without prefix (e.g. $26.5, $4.00, $0.60, $0.07)."""
    if cost is None:
        return ""
    if cost >= 10:
        return f"${_fmt_num(cost)}"
    if cost >= 0.1:
        return f"${cost:.2f}"
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
    name = re.sub(r"\s*\(free\)\s*$", "", name, flags=re.I)
    return name


def _effort_sort_key(m: dict[str, Any]) -> tuple[int, float]:
    ef = str(m.get("effort") or "").lower()
    order = EFFORT_ORDER.get(ef, 5)
    iq = float(m["iq"]) if isinstance(m.get("iq"), (int, float)) else -1.0
    return (order, -iq)


def _score_pct(val: Any, max_score: float) -> int:
    if not isinstance(val, (int, float)) or max_score <= 0:
        return 0
    pct = round(max(4.0, min(100.0, (float(val) / max_score) * 100.0)))
    return int(pct)


def _to_effort_tile(m: dict[str, Any], *, score_key: str, max_score: float) -> dict[str, Any]:
    val = m.get(score_key)
    score_str = f"{float(val):.1f}" if isinstance(val, (int, float)) else "--"
    effort_key = str(m.get("effort") or "").lower()
    effort_label = str(m.get("effort_label") or "").strip()
    return {
        "effort": effort_label,
        "effort_key": effort_key,
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
    theme = MAKER_THEMES.get(maker, DEFAULT_THEME)
    val = m.get(score_key)
    score_str = f"{float(val):.1f}" if isinstance(val, (int, float)) else "--"
    effort_key = str(m.get("effort") or "").lower()
    effort_label = str(m.get("effort_label") or "").strip()
    return {
        "name": _clean_display_name(m),
        "maker_label": theme["label"],
        "effort": effort_label,
        "effort_key": effort_key,
        "score": score_str,
        "bar_pct": _score_pct(val, max_score),
        "price": _format_price(m.get("price_in"), m.get("price_out")),
        "task_cost": _format_task_cost(m.get("cost_per_task")),
        "perf": _format_perf(m.get("tps"), m.get("latency_s")),
        "badge": badge,
        "accent": theme["accent"],
        "border": theme["border"],
        "bg": theme["bg"],
        "pill_bg": theme["pill_bg"],
    }


def _build_vendor_section(
    maker: str,
    items: list[dict[str, Any]],
    *,
    max_releases: int | None,
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

    theme = MAKER_THEMES.get(maker, DEFAULT_THEME)
    model_rows: list[dict[str, Any]] = []
    for grp in sorted_rels:
        grp_sorted = sorted(grp, key=_effort_sort_key)
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
        "label": theme["label"] if maker in MAKER_THEMES else maker.upper(),
        "accent": theme["accent"],
        "border": theme["border"],
        "bg": theme["bg"],
        "pill_bg": theme["pill_bg"],
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
    filter_outdated: bool = True,
    max_model_age_days: int = 180,
    max_releases_per_maker: int = 5,
) -> dict[str, Any]:
    """Select, filter, sort, and structure models into either Matrix or Ranking view data."""
    raw_q, effort_filter, include_all = _parse_query_tokens(query)
    q_lower = raw_q.lower()

    is_free_mode = q_lower in {"free", "免费", "白嫖"}
    apply_outdated_filter = filter_outdated and not include_all

    working = list(models)
    if apply_outdated_filter:
        working = filter_outdated_models(
            working,
            max_age_days=max_model_age_days,
            keep_free_variants=is_free_mode,
        )
    elif not is_free_mode:
        working = [m for m in working if not str(m.get("id") or "").endswith(":free")]

    if effort_filter is not None:
        working = [m for m in working if str(m.get("effort") or "").lower() == effort_filter]

    effort_tag = f" · 推理强度: {effort_filter.upper()}" if effort_filter else ""
    all_tag = " · 含旧代模型" if include_all else ""

    layout = "matrix"
    sections: list[dict[str, Any]] = []
    ranking_cards: list[dict[str, Any]] = []

    title = "AI 模型实时智商榜"
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
        ranked = [m for m in working if isinstance(m.get("coding"), (int, float))]
        ranked.sort(key=lambda m: float(m["coding"]), reverse=True)
        top = ranked[:max_ranking_items]
        max_sc = max((float(m["coding"]) for m in top), default=100.0)
        ranking_cards = [
            _to_ranking_card(m, score_key="coding", max_score=max_sc, badge=f"#{i + 1}")
            for i, m in enumerate(top)
        ]

    elif q_lower in {"value", "性价比", "划算", "便宜"}:
        layout = "ranking"
        title = "AI 模型性价比榜"
        has_task_cost = any(isinstance(m.get("cost_per_task"), (int, float)) for m in working)
        subtitle = (
            f"按「智商 ÷ {'题均成本' if has_task_cost else '综合单价'}」降序（仅限智商 ≥ 20）"
            f"{effort_tag}{all_tag}"
        )
        candidates: list[tuple[float, dict[str, Any]]] = []
        for m in working:
            iq = m.get("iq")
            if not isinstance(iq, (int, float)) or iq < 20.0:
                continue
            denom = m.get("cost_per_task")
            if not isinstance(denom, (int, float)) or denom <= 0:
                denom = _blended_price(m)
            if denom is None or denom <= 0:
                continue
            candidates.append((float(iq) / float(denom), m))
        candidates.sort(key=lambda x: x[0], reverse=True)
        top = [m for _, m in candidates[:max_ranking_items]]
        max_sc = max((float(m["iq"]) for m in top), default=70.0)
        ranking_cards = [
            _to_ranking_card(m, score_key="iq", max_score=max_sc, badge=f"#{i + 1}")
            for i, m in enumerate(top)
        ]

    elif is_free_mode:
        layout = "ranking"
        title = "免费 AI 模型智商榜 ($0)"
        subtitle = f"输入/输出均为 $0 的带跑分模型 · 按智商降序{effort_tag}{all_tag}"
        free_models = [
            m
            for m in working
            if isinstance(m.get("iq"), (int, float))
            and (m.get("price_in") or 0) == 0
            and (m.get("price_out") or 0) == 0
            and (m.get("price_in") is not None or m.get("price_out") is not None)
        ]
        free_models.sort(key=lambda m: float(m["iq"]), reverse=True)
        top = free_models[:max_ranking_items]
        max_sc = max((float(m["iq"]) for m in top), default=70.0)
        ranking_cards = [
            _to_ranking_card(m, score_key="iq", max_score=max_sc, badge=f"#{i + 1}")
            for i, m in enumerate(top)
        ]

    elif not q_lower and effort_filter is not None:
        # Pure effort query like `/aiiq max` or `/aiiq ultra` -> clean global ranking grid
        layout = "ranking"
        title = f"AI 模型智商榜 · {effort_filter.upper()} 档位"
        subtitle = f"按 AA 智商分降序 · 右上大字为题均成本 · 底部 API 单价与速度延迟{all_tag}"
        ranked = [m for m in working if isinstance(m.get("iq"), (int, float))]
        ranked.sort(key=lambda m: float(m["iq"]), reverse=True)
        top = ranked[:max_ranking_items]
        max_sc = max((float(m["iq"]) for m in top), default=70.0)
        ranking_cards = [
            _to_ranking_card(m, score_key="iq", max_score=max_sc, badge=f"#{i + 1}")
            for i, m in enumerate(top)
        ]

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
            title = f"{label} 实时智商与推理强度"
            max_sc = max((float(m["iq"]) for m in matched), default=70.0)
            sec = _build_vendor_section(
                maker_target,
                matched,
                max_releases=None,
                score_key="iq",
                max_score=max_sc,
            )
            if sec:
                sections.append(sec)
        else:
            terms = [t for t in q_lower.split() if t]
            matched = []
            for m in working:
                if not isinstance(m.get("iq"), (int, float)):
                    continue
                hay = (
                    f"{m.get('id', '')} {m.get('release_slug', '')} "
                    f"{m.get('release_name', '')} {m.get('name', '')} {m.get('maker', '')}"
                ).lower()
                if all(t in hay for t in terms):
                    matched.append(m)
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
                    score_key="iq",
                    max_score=max_sc,
                )
                if sec:
                    sections.append(sec)
    else:
        # Default multi-vendor matrix overview
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
                score_key="iq",
                max_score=max_sc,
            )
            if sec:
                sections.append(sec)

    updated_str = datetime.fromtimestamp(fetched_at).strftime("%Y-%m-%d %H:%M")
    stale_note = "（上游暂不可用，当前为历史缓存）" if is_stale else ""
    source_label = (
        "Artificial Analysis 官方实时榜单"
        if source == "artificial_analysis"
        else "Artificial Analysis + OpenRouter (via modelgrep)"
    )
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


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    display: inline-block;
    width: 1200px;
    background: #eef2f7;
    padding: 18px 20px 14px 20px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
      "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
    color: #0f172a;
    -webkit-font-smoothing: antialiased;
  }

  /* Header */
  .header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 14px;
    padding: 0 2px;
  }
  .title {
    font-size: 30px;
    font-weight: 800;
    color: #0f172a;
    letter-spacing: -0.3px;
    line-height: 1.1;
  }
  .subtitle {
    font-size: 13.5px;
    font-weight: 600;
    color: #475569;
    line-height: 1.3;
    text-align: right;
  }

  /* Matrix Layout: Vendor Sections */
  .sections {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .vendor-card {
    background: #ffffff;
    border-radius: 14px;
    border: 1.5px solid #dde4ee;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
  }
  .vendor-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 9px 16px;
    background: var(--bg);
    border-bottom: 1.5px solid var(--border);
  }
  .vendor-title {
    display: flex;
    align-items: center;
    gap: 9px;
    font-size: 16.5px;
    font-weight: 800;
    color: var(--accent);
    letter-spacing: 0.1px;
  }
  .vendor-dot {
    width: 10px;
    height: 10px;
    border-radius: 999px;
    background: var(--accent);
    flex-shrink: 0;
  }
  .vendor-meta {
    font-size: 12.5px;
    font-weight: 600;
    color: #64748b;
  }

  .model-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    border-bottom: 1px solid #eef2f7;
  }
  .model-row:last-child {
    border-bottom: none;
  }
  .model-info {
    width: 192px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding-right: 4px;
  }
  .model-name {
    font-size: 17px;
    line-height: 1.2;
    font-weight: 800;
    color: #0f172a;
    overflow-wrap: break-word;
  }
  .api-price-row {
    display: inline-flex;
    align-items: baseline;
    gap: 4px;
    font-variant-numeric: tabular-nums;
  }
  .api-price {
    font-size: 14px;
    font-weight: 700;
    color: var(--accent);
    background: var(--pill_bg);
    padding: 2px 7px;
    border-radius: 6px;
    white-space: nowrap;
  }
  .api-unit {
    font-size: 11.5px;
    font-weight: 600;
    color: #64748b;
  }

  .effort-grid {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
  }
  .tile {
    width: 148px;
    border-radius: 10px;
    border: 1.4px solid #e2e8f0;
    background: #f8fafc;
    padding: 8px 9px 7px 9px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 5px;
  }
  .tile.tier-strong {
    background: var(--bg);
    border-color: var(--border);
  }
  .tile-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 4px;
  }
  .effort-pill {
    display: inline-block;
    font-size: 10.5px;
    line-height: 1.25;
    font-weight: 800;
    letter-spacing: 0.15px;
    padding: 2px 6px;
    border-radius: 5px;
    white-space: nowrap;
    flex-shrink: 0;
    text-transform: uppercase;
    color: var(--accent);
    background: var(--pill_bg);
    border: 1px solid var(--border);
  }
  .effort-pill.effort-extreme,
  .effort-pill.effort-ultra,
  .effort-pill.effort-max,
  .effort-pill.effort-xhigh {
    background: var(--accent);
    color: #ffffff;
    border-color: var(--accent);
  }
  .effort-pill.effort-medium,
  .effort-pill.effort-low,
  .effort-pill.effort-minimal {
    background: #ffffff;
    color: var(--accent);
    border-color: var(--border);
    font-weight: 700;
  }
  .effort-pill.effort-reasoning {
    text-transform: none;
  }
  .effort-pill.effort-non-reasoning {
    background: #e2e8f0;
    color: #334155;
    border-color: #cbd5e1;
    font-weight: 700;
    text-transform: none;
  }
  .task-cost {
    font-size: 16.5px;
    font-weight: 800;
    color: #0f172a;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.3px;
  }
  .tile-mid {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .tile-score {
    font-size: 33px;
    line-height: 1.0;
    font-weight: 800;
    color: #0f172a;
    letter-spacing: -0.8px;
    font-variant-numeric: tabular-nums;
  }
  .bar-track {
    width: 100%;
    height: 4px;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.08);
    overflow: hidden;
  }
  .bar-fill {
    height: 100%;
    border-radius: 999px;
    background: var(--accent);
  }
  .tile-perf {
    font-size: 12px;
    font-weight: 600;
    color: #475569;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }

  /* Ranking Layout: 3-Column High-Readability Grid */
  .rank-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 11px;
  }
  .rank-card {
    position: relative;
    background: #ffffff;
    border-radius: 12px;
    border: 1.5px solid var(--border);
    padding: 13px 14px 11px 14px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 8px;
    overflow: hidden;
    box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
  }
  .rank-card::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4.5px;
    background: var(--accent);
  }
  .rank-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
  }
  .rank-name-wrap {
    display: flex;
    align-items: baseline;
    gap: 6px;
    min-width: 0;
  }
  .rank-badge {
    font-size: 15px;
    font-weight: 800;
    color: var(--accent);
    flex-shrink: 0;
  }
  .rank-name {
    font-size: 17px;
    line-height: 1.2;
    font-weight: 800;
    color: #0f172a;
    overflow-wrap: break-word;
  }
  .rank-body {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 10px;
  }
  .rank-score-col {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .rank-score {
    font-size: 38px;
    line-height: 0.98;
    font-weight: 800;
    color: #0f172a;
    letter-spacing: -1px;
    font-variant-numeric: tabular-nums;
  }
  .rank-metrics {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 3px;
    flex-shrink: 0;
    font-variant-numeric: tabular-nums;
  }
  .rank-cost {
    font-size: 18px;
    font-weight: 800;
    color: var(--accent);
    line-height: 1.1;
  }
  .rank-price {
    font-size: 13px;
    font-weight: 700;
    color: #334155;
  }
  .rank-perf {
    font-size: 12.5px;
    font-weight: 600;
    color: #64748b;
  }

  /* Footer */
  .footer {
    margin-top: 12px;
    padding: 0 4px;
    display: flex;
    justify-content: space-between;
    gap: 16px;
    font-size: 13px;
    font-weight: 600;
    color: #64748b;
  }
</style>
</head>
<body>
  <div class="header">
    <div class="title">{{ title }}</div>
    <div class="subtitle">{{ subtitle }}</div>
  </div>

  {% if layout == 'matrix' %}
  <div class="sections">
    {% for sec in sections %}
    <div class="vendor-card" style="--accent: {{ sec.accent }}; --border: {{ sec.border }}; --bg: {{ sec.bg }}; --pill_bg: {{ sec.pill_bg }};">
      <div class="vendor-header">
        <div class="vendor-title"><span class="vendor-dot"></span>{{ sec.label }}</div>
        <div class="vendor-meta">{{ sec.models | length }} 个系列 · {{ sec.tile_count }} 个档位</div>
      </div>
      {% for model in sec.models %}
      <div class="model-row">
        <div class="model-info">
          <div class="model-name">{{ model.name }}</div>
          <div class="api-price-row">
            <span class="api-price">{{ model.price }}</span>
            {% if not model.is_free and model.price != '--' %}<span class="api-unit">/1M</span>{% endif %}
          </div>
        </div>
        <div class="effort-grid">
          {% for t in model.efforts %}
          <div class="tile{% if t.effort_key in ['extreme', 'ultra', 'max', 'xhigh', 'high'] %} tier-strong{% endif %}">
            <div class="tile-top">
              {% if t.effort %}<span class="effort-pill effort-{{ t.effort_key }}">{{ t.effort }}</span>{% endif %}
              {% if t.task_cost %}<span class="task-cost">{{ t.task_cost }}</span>{% endif %}
            </div>
            <div class="tile-mid">
              <div class="tile-score">{{ t.score }}</div>
              <div class="bar-track"><div class="bar-fill" style="width: {{ t.bar_pct }}%;"></div></div>
            </div>
            <div class="tile-perf">{{ t.perf }}</div>
          </div>
          {% endfor %}
        </div>
      </div>
      {% endfor %}
    </div>
    {% endfor %}
  </div>
  {% else %}
  <div class="rank-grid">
    {% for c in ranking_cards %}
    <div class="rank-card" style="--accent: {{ c.accent }}; --border: {{ c.border }}; --bg: {{ c.bg }}; --pill_bg: {{ c.pill_bg }};">
      <div class="rank-top">
        <div class="rank-name-wrap">
          {% if c.badge %}<span class="rank-badge">{{ c.badge }}</span>{% endif %}
          <span class="rank-name">{{ c.name }}</span>
        </div>
        {% if c.effort %}<span class="effort-pill effort-{{ c.effort_key }}">{{ c.effort }}</span>{% endif %}
      </div>
      <div class="rank-body">
        <div class="rank-score-col">
          <div class="rank-score">{{ c.score }}</div>
          <div class="bar-track"><div class="bar-fill" style="width: {{ c.bar_pct }}%;"></div></div>
        </div>
        <div class="rank-metrics">
          {% if c.task_cost %}<div class="rank-cost">{{ c.task_cost }}</div>{% endif %}
          <div class="rank-price">{{ c.price }}</div>
          <div class="rank-perf">{{ c.perf }}</div>
        </div>
      </div>
    </div>
    {% endfor %}
  </div>
  {% endif %}

  <div class="footer">
    <span>数据来源：{{ source_label }} · 共展示 {{ total_cards }} 个配置</span>
    <span>更新于 {{ updated_str }}{{ stale_note }}</span>
  </div>
</body>
</html>
"""


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
            tc = f" {c['task_cost']}" if c["task_cost"] else ""
            lines.append(
                f"- {prefix}{c['name']}{ef} | 评分: {c['score']} |{tc} ({c['price']}) | {c['perf']}"
            )
    lines.append("")
    lines.append(
        f"数据来源：{view_data['source_label']} · 更新于 {view_data['updated_str']}{view_data['stale_note']}"
    )
    return "\n".join(lines)
