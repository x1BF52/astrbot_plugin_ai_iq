from __future__ import annotations

import re
import time
from collections import defaultdict
from datetime import datetime
from typing import Any

# Theme palette per vendor: accent (top bar & text), border, background, divider, pill_bg
MAKER_THEMES: dict[str, dict[str, str]] = {
    "anthropic": {
        "label": "Anthropic · Claude",
        "accent": "#d9534f",
        "border": "#e88b84",
        "bg": "#fff6f5",
        "divider": "#f0c2be",
        "pill_bg": "#fde4e2",
    },
    "openai": {
        "label": "OpenAI · GPT",
        "accent": "#c88a1e",
        "border": "#e5b85c",
        "bg": "#fffbf0",
        "divider": "#f0d9a3",
        "pill_bg": "#fdf0cf",
    },
    "google": {
        "label": "Google · Gemini",
        "accent": "#2f74c9",
        "border": "#7fb0eb",
        "bg": "#f2f8ff",
        "divider": "#bdd7f6",
        "pill_bg": "#ddebfd",
    },
    "deepseek": {
        "label": "DeepSeek",
        "accent": "#139c80",
        "border": "#68ccb6",
        "bg": "#effcf9",
        "divider": "#b0e6da",
        "pill_bg": "#d6f5ed",
    },
    "qwen": {
        "label": "Alibaba · Qwen",
        "accent": "#7352d1",
        "border": "#a992ea",
        "bg": "#f7f4ff",
        "divider": "#d3c6f5",
        "pill_bg": "#e8e0fc",
    },
    "z-ai": {
        "label": "Z.ai · GLM",
        "accent": "#4863d4",
        "border": "#8ea2ea",
        "bg": "#f3f6ff",
        "divider": "#c4cef5",
        "pill_bg": "#dfe6fc",
    },
    "moonshotai": {
        "label": "Moonshot · Kimi",
        "accent": "#be4488",
        "border": "#df8ab9",
        "bg": "#fff4fa",
        "divider": "#f0c2dc",
        "pill_bg": "#fbe0ef",
    },
    "x-ai": {
        "label": "xAI · Grok",
        "accent": "#5a687a",
        "border": "#9aa8ba",
        "bg": "#f6f8fa",
        "divider": "#cfd7e2",
        "pill_bg": "#e5eaf0",
    },
    "meta": {
        "label": "Meta",
        "accent": "#2e6fd9",
        "border": "#84aee9",
        "bg": "#f3f7ff",
        "divider": "#c2d7f6",
        "pill_bg": "#dfeafe",
    },
    "mistralai": {
        "label": "Mistral",
        "accent": "#d96b27",
        "border": "#eaa475",
        "bg": "#fff7f2",
        "divider": "#f4cdb4",
        "pill_bg": "#fde7d8",
    },
    "minimax": {
        "label": "MiniMax",
        "accent": "#c94c68",
        "border": "#e594a7",
        "bg": "#fff5f7",
        "divider": "#f2c6d0",
        "pill_bg": "#fbe1e7",
    },
    "tencent": {
        "label": "Tencent · Hunyuan",
        "accent": "#2382c9",
        "border": "#7cb8e5",
        "bg": "#f2f9ff",
        "divider": "#bcdcf4",
        "pill_bg": "#dcedfb",
    },
    "xiaomi": {
        "label": "Xiaomi · MiMo",
        "accent": "#d6681e",
        "border": "#e8a572",
        "bg": "#fff7f0",
        "divider": "#f2cdb0",
        "pill_bg": "#fde8d7",
    },
}

DEFAULT_THEME: dict[str, str] = {
    "label": "Other",
    "accent": "#64748b",
    "border": "#a0aec0",
    "bg": "#f7f9fc",
    "divider": "#cbd5e1",
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

EFFORT_ORDER: dict[str, int] = {
    "ultra": 0,
    "max": 1,
    "xhigh": 2,
    "high": 3,
    "medium": 4,
    "low": 5,
    "minimal": 6,
    "reasoning": 7,
    "non-reasoning": 8,
    "": 9,
}

EFFORT_ALIASES: dict[str, str] = {
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

_MAJOR_GEN_SERIES = ("gemini", "gpt", "claude")

_DATE_CODE_RE = re.compile(
    r"(?:\b20\d{2}-\d{2}-\d{2}\b|\(\d{4}\)|\b(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\b|\b2[4-9](?:0[1-9]|1[0-2])\b)"
)
_VERSION_RE = re.compile(r"(?<![a-z0-9])(?:v|k|m)?(\d+(?:\.\d+)?)(?![a-z0-9]*b\b)", re.I)


def _extract_lineage_info(
    maker: str, release_name: str
) -> tuple[str, tuple[int, ...], int, str | None, int | None]:
    """Parse a release name into (lineage_key, version_tuple, date_code, major_series, major_ver)."""
    clean = release_name.strip().lower()
    clean = re.sub(r"\(free\)|\(preview\)|\bpreview\b", "", clean)
    clean = re.sub(r"[_/]+", " ", clean)

    # Extract snapshot date codes like 1017, 0813, 0423, (0902), 2026-02-15
    date_code = 0
    for dm in _DATE_CODE_RE.finditer(clean):
        digits = re.sub(r"\D", "", dm.group(0))
        if digits:
            val = int(digits)
            if val > date_code:
                date_code = val
    no_date = _DATE_CODE_RE.sub(" ", clean)

    # Normalize hyphens for matching while preserving word boundaries
    tokens_str = re.sub(r"[-]+", " ", no_date)
    tokens_str = re.sub(r"\s+", " ", tokens_str).strip()

    # Check major named series (gemini 4, gpt 6.2, claude ... 5.2)
    major_series: str | None = None
    for s in _MAJOR_GEN_SERIES:
        if re.search(rf"\b{s}\b", tokens_str):
            major_series = s
            break

    # Extract primary version (skip parameter sizes like 27b, 120b, 397b, 31b)
    ver_tuple: tuple[int, ...] = (0,)
    major_ver: int | None = None
    ver_match = re.search(
        r"(?:\b(?:gpt|gemini|claude|qwen|glm|grok)\s*|\bv|\bk|\bm|\s)(\d+(?:\.\d+)?)(?=\s|$)",
        tokens_str,
    )
    if ver_match:
        parts = ver_match.group(1).split(".")
        ver_tuple = tuple(int(p) for p in parts)
        major_ver = ver_tuple[0]
        # Remove just the version number from lineage_key
        s_idx, e_idx = ver_match.span(1)
        lineage_raw = tokens_str[:s_idx] + " " + tokens_str[e_idx:]
    else:
        lineage_raw = tokens_str

    # Remove dangling single-letter version prefixes like "v", "k", "m" before the stripped number
    lineage_raw = re.sub(r"\b[vkm]\b", " ", lineage_raw)
    # Remove "next" suffix for lineage matching? Keep distinct tiers like flash / pro / max / ultra / lite / astra / sol / terra / luna / fable / opus / sonnet / haiku
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

    # Group variants by (maker, release_slug)
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

    # Step 1: Age filter & parse lineage metadata per release
    active_releases: dict[tuple[str, str], dict[str, Any]] = {}
    for key, variants in releases.items():
        maker, _ = key
        # Representative timestamp & name
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

    # Step 2: Major-generation pruning for flagship series (e.g. Gemini 4 drops Gemini 3.x;
    # GPT-6 drops GPT-5.x; Claude 5 drops Claude 4.x) when >=2 releases exist in the newer gen.
    series_gen_counts: dict[tuple[str, str], dict[int, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for info in active_releases.values():
        if info["major_series"] and info["major_ver"] is not None:
            series_gen_counts[(info["maker"], info["major_series"])][info["major_ver"]] += 1

    series_min_major: dict[tuple[str, str], int] = {}
    for skey, gen_counts in series_gen_counts.items():
        # Highest major generation that already has >= 2 active releases
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

    # Step 3: Same-lineage version deduplication (e.g. Fable 5.2 drops 5.1;
    # GPT-6.2 Astra drops GPT-6 Astra; DeepSeek V4 Pro 0813 drops 0423; Qwen4 Max drops Qwen3.8 Max)
    by_lineage: dict[str, list[tuple[tuple[str, str], dict[str, Any]]]] = defaultdict(list)
    for key, info in after_gen_prune.items():
        by_lineage[info["lineage_key"]].append((key, info))

    kept_keys: set[tuple[str, str]] = set()
    for _, entries in by_lineage.items():
        if len(entries) == 1:
            kept_keys.add(entries[0][0])
            continue
        # Pick the newest version -> newest snapshot date_code -> newest created_ts -> highest IQ
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
    return f"${_fmt_num(pin_f)}/${_fmt_num(pout_f)}"


def _format_task_cost(cost: float | None) -> str:
    if cost is None:
        return ""
    if cost >= 10:
        return f"题均 ${_fmt_num(cost)}"
    if cost >= 0.1:
        return f"题均 ${cost:.2f}"
    return f"题均 ${cost:.3f}"


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
    order = EFFORT_ORDER.get(ef, 8)
    iq = float(m["iq"]) if isinstance(m.get("iq"), (int, float)) else -1.0
    return (order, -iq)


def _to_card(
    m: dict[str, Any],
    *,
    score_key: str = "iq",
    badge: str = "",
) -> dict[str, Any]:
    maker = str(m.get("maker") or "other").lower()
    theme = MAKER_THEMES.get(maker, DEFAULT_THEME)
    val = m.get(score_key)
    score_str = f"{float(val):.1f}" if isinstance(val, (int, float)) else "--"
    effort_label = str(m.get("effort_label") or "").strip()
    effort_key = str(m.get("effort") or "").lower()
    return {
        "name": _clean_display_name(m),
        "effort": effort_label,
        "effort_key": effort_key,
        "score": score_str,
        "price": _format_price(m.get("price_in"), m.get("price_out")),
        "task_cost": _format_task_cost(m.get("cost_per_task")),
        "perf": _format_perf(m.get("tps"), m.get("latency_s")),
        "badge": badge,
        "accent": theme["accent"],
        "border": theme["border"],
        "bg": theme["bg"],
        "divider": theme["divider"],
        "pill_bg": theme["pill_bg"],
    }


def _chunk(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _group_release_rows(
    items: list[dict[str, Any]],
    *,
    max_releases: int | None,
    max_per_row: int,
    score_key: str = "iq",
) -> list[dict[str, Any]]:
    """Group items of one maker into centered rows:
    - Multi-effort releases get their own dedicated row (ordered strongest -> lightest effort).
    - Single-effort releases of the same maker are packed neatly into shared rows.
    """
    by_rel: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for m in items:
        rslug = str(m.get("release_slug") or m.get("id") or "")
        by_rel[rslug].append(m)

    # Sort releases by best score descending
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

    rows: list[dict[str, Any]] = []
    singles_buf: list[dict[str, Any]] = []

    def _flush_singles() -> None:
        nonlocal singles_buf
        if singles_buf:
            for chunk in _chunk(singles_buf, max_per_row):
                rows.append(
                    {
                        "cards": [_to_card(m, score_key=score_key) for m in chunk],
                        "section_start": False,
                    }
                )
            singles_buf = []

    for grp in sorted_rels:
        grp_sorted = sorted(grp, key=_effort_sort_key)
        if len(grp_sorted) == 1:
            if (
                rows
                and len(rows[-1]["cards"]) <= 2
                and len(rows[-1]["cards"]) + 1 <= max_per_row
            ):
                rows[-1]["cards"].append(_to_card(grp_sorted[0], score_key=score_key))
            else:
                singles_buf.append(grp_sorted[0])
        else:
            _flush_singles()
            for chunk in _chunk(grp_sorted, max_per_row):
                rows.append(
                    {
                        "cards": [_to_card(m, score_key=score_key) for m in chunk],
                        "section_start": False,
                    }
                )
    _flush_singles()
    return rows


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
    max_releases_per_maker: int = 4,
) -> dict[str, Any]:
    """Select, filter, sort, and group models into card rows for HTML rendering."""
    raw_q, effort_filter, include_all = _parse_query_tokens(query)
    q_lower = raw_q.lower()
    per_row = max(3, min(6, max_per_maker))

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

    effort_tag = f" · 推理强度: {effort_filter}" if effort_filter else ""
    all_tag = " · 含旧代模型" if include_all else ""

    rows: list[dict[str, Any]] = []
    title = "AI 模型实时智商榜"
    subtitle = (
        f"左下大字 AA 智商分 · 旁侧标签为推理强度 · 右上单价 ($/1M) 与题均成本 · 右下速度 & 首答延迟"
        f"{effort_tag}{all_tag}"
    )

    if q_lower in {"coding", "code", "编程", "代码"}:
        title = "AI 模型编程跑分榜 (Coding)"
        subtitle = (
            f"按编程评测综合分降序 · 含各推理强度档位 · 速度 & 首答延迟{effort_tag}{all_tag}"
        )
        ranked = [m for m in working if isinstance(m.get("coding"), (int, float))]
        ranked.sort(key=lambda m: float(m["coding"]), reverse=True)
        cards = [
            _to_card(m, score_key="coding", badge=f"#{i + 1}")
            for i, m in enumerate(ranked[:max_ranking_items])
        ]
        rows = [{"cards": chunk} for chunk in _chunk(cards, per_row)]

    elif q_lower in {"value", "性价比", "划算", "便宜"}:
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
        cards = [
            _to_card(m, score_key="iq", badge=f"#{i + 1}")
            for i, (_, m) in enumerate(candidates[:max_ranking_items])
        ]
        rows = [{"cards": chunk} for chunk in _chunk(cards, per_row)]

    elif is_free_mode:
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
        cards = [
            _to_card(m, score_key="iq", badge=f"#{i + 1}")
            for i, m in enumerate(free_models[:max_ranking_items])
        ]
        rows = [{"cards": chunk} for chunk in _chunk(cards, per_row)]

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
            subtitle = (
                f"每行同一模型按推理强度从高到低排列 · 右上单价/题均 · 右下速度 & 首答延迟"
                f"{effort_tag}{all_tag}"
            )
            rows = _group_release_rows(
                matched,
                max_releases=None,
                max_per_row=per_row,
                score_key="iq",
            )
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
            subtitle = (
                f"匹配在役模型按系列与推理强度分组 · 速度 & 首答延迟{effort_tag}{all_tag}"
            )
            rows = _group_release_rows(
                matched,
                max_releases=None,
                max_per_row=per_row,
                score_key="iq",
            )
    else:
        # Default multi-vendor overview
        by_maker: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for m in working:
            if not isinstance(m.get("iq"), (int, float)):
                continue
            by_maker[str(m.get("maker") or "other").lower()].append(m)

        for maker in default_makers:
            group = by_maker.get(maker)
            if not group:
                continue
            maker_rows = _group_release_rows(
                group,
                max_releases=max(1, max_releases_per_maker),
                max_per_row=per_row,
                score_key="iq",
            )
            if maker_rows and rows:
                maker_rows[0]["section_start"] = True
            rows.extend(maker_rows)

    updated_str = datetime.fromtimestamp(fetched_at).strftime("%Y-%m-%d %H:%M")
    stale_note = "（上游暂不可用，当前为历史缓存）" if is_stale else ""
    source_label = (
        "Artificial Analysis 官方实时榜单"
        if source == "artificial_analysis"
        else "Artificial Analysis + OpenRouter (via modelgrep)"
    )
    total_cards = sum(len(r["cards"]) for r in rows)

    return {
        "title": title,
        "subtitle": subtitle,
        "rows": rows,
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
    background: #ffffff;
    padding: 12px 12px 10px 12px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
      "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
    color: #111827;
    -webkit-font-smoothing: antialiased;
  }
  .header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 24px;
    margin-bottom: 10px;
    padding: 0 4px;
  }
  .title {
    font-size: 28px;
    font-weight: 800;
    color: #111827;
    letter-spacing: 0.2px;
  }
  .subtitle {
    font-size: 15px;
    font-weight: 500;
    color: #4b5563;
  }
  .rows {
    display: flex;
    flex-direction: column;
    gap: 7px;
  }
  .row {
    display: flex;
    justify-content: center;
    flex-wrap: nowrap;
    gap: 7px;
  }
  .row.section-start {
    margin-top: 10px;
  }
  .card {
    position: relative;
    width: 280px;
    min-height: 92px;
    border-radius: 10px;
    border: 1.6px solid var(--border);
    background: var(--bg);
    overflow: hidden;
    display: flex;
    flex-direction: row;
    align-items: stretch;
  }
  .card::before {
    content: "";
    position: absolute;
    top: 0;
    left: 10px;
    right: 10px;
    height: 4.5px;
    background: var(--accent);
    border-radius: 0 0 3px 3px;
  }
  .card-left {
    flex: 1;
    min-width: 0;
    padding: 10px 8px 7px 11px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }
  .model-name {
    font-size: 15px;
    line-height: 1.18;
    font-weight: 700;
    letter-spacing: -0.15px;
    color: var(--accent);
    overflow-wrap: break-word;
  }
  .badge {
    font-size: 12px;
    font-weight: 800;
    opacity: 0.85;
    margin-right: 4px;
  }
  .score-row {
    display: flex;
    align-items: baseline;
    justify-content: flex-start;
    gap: 7px;
    margin-top: 5px;
  }
  .score {
    font-size: 35px;
    line-height: 0.98;
    font-weight: 700;
    color: #111827;
    letter-spacing: -0.8px;
    font-variant-numeric: tabular-nums;
  }
  .effort-pill {
    display: inline-block;
    font-size: 11px;
    line-height: 1.25;
    font-weight: 800;
    letter-spacing: 0.1px;
    padding: 2px 5px;
    border-radius: 5px;
    white-space: nowrap;
    flex-shrink: 0;
    text-transform: uppercase;
    color: var(--accent);
    background: var(--pill-bg);
    border: 1px solid var(--border);
  }
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
    background: #e5e7eb;
    color: #374151;
    border-color: #cbd5e1;
    font-weight: 700;
    text-transform: none;
  }
  .card-right {
    width: 114px;
    flex-shrink: 0;
    border-left: 1.5px solid var(--divider);
    margin: 9px 0 7px 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }
  .metric-top {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 0 4px 3px 4px;
    line-height: 1.14;
    font-variant-numeric: tabular-nums;
  }
  .price-main {
    font-size: 15px;
    font-weight: 700;
    color: var(--accent);
    white-space: nowrap;
  }
  .price-sub {
    font-size: 12px;
    font-weight: 600;
    color: #4b5563;
    margin-top: 2px;
    white-space: nowrap;
  }
  .metric-bottom {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    border-top: 1.5px solid var(--divider);
    margin: 0 4px;
    padding: 3px 2px 0 2px;
    font-size: 12.5px;
    font-weight: 700;
    color: #374151;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .footer {
    margin-top: 10px;
    padding: 0 4px;
    display: flex;
    justify-content: space-between;
    gap: 16px;
    font-size: 13.5px;
    font-weight: 500;
    color: #6b7280;
  }
</style>
</head>
<body>
  <div class="header">
    <div class="title">{{ title }}</div>
    <div class="subtitle">{{ subtitle }}</div>
  </div>
  <div class="rows">
    {% for row in rows %}
    <div class="row{% if row.section_start %} section-start{% endif %}">
      {% for card in row.cards %}
      <div class="card" style="--accent: {{ card.accent }}; --border: {{ card.border }}; --bg: {{ card.bg }}; --divider: {{ card.divider }}; --pill-bg: {{ card.pill_bg }};">
        <div class="card-left">
          <div class="model-name">{% if card.badge %}<span class="badge">{{ card.badge }}</span>{% endif %}{{ card.name }}</div>
          <div class="score-row">
            <div class="score">{{ card.score }}</div>
            {% if card.effort %}<span class="effort-pill effort-{{ card.effort_key }}">{{ card.effort }}</span>{% endif %}
          </div>
        </div>
        <div class="card-right">
          <div class="metric-top">
            <span class="price-main">{{ card.price }}</span>
            {% if card.task_cost %}<span class="price-sub">{{ card.task_cost }}</span>{% endif %}
          </div>
          <div class="metric-bottom">{{ card.perf }}</div>
        </div>
      </div>
      {% endfor %}
    </div>
    {% endfor %}
  </div>
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
    for row in view_data["rows"]:
        if not row["cards"]:
            continue
        for c in row["cards"]:
            prefix = f"{c['badge']} " if c["badge"] else ""
            ef = f" [{c['effort']}]" if c["effort"] else ""
            tc = f" ({c['task_cost']})" if c["task_cost"] else ""
            lines.append(
                f"- {prefix}{c['name']}{ef} | 评分: {c['score']} | 价格: {c['price']}{tc} | 速度/延迟: {c['perf']}"
            )
    lines.append("")
    lines.append(
        f"数据来源：{view_data['source_label']} · 更新于 {view_data['updated_str']}{view_data['stale_note']}"
    )
    return "\n".join(lines)
