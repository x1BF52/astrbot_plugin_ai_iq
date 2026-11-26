from __future__ import annotations

from datetime import datetime
from typing import Any

# Theme palette per vendor: accent (top bar & text), border, background, divider
MAKER_THEMES: dict[str, dict[str, str]] = {
    "anthropic": {
        "label": "Anthropic · Claude",
        "accent": "#d9534f",
        "border": "#e88b84",
        "bg": "#fff6f5",
        "divider": "#f0c2be",
    },
    "openai": {
        "label": "OpenAI · GPT",
        "accent": "#c88a1e",
        "border": "#e5b85c",
        "bg": "#fffbf0",
        "divider": "#f0d9a3",
    },
    "google": {
        "label": "Google · Gemini",
        "accent": "#2f74c9",
        "border": "#7fb0eb",
        "bg": "#f2f8ff",
        "divider": "#bdd7f6",
    },
    "deepseek": {
        "label": "DeepSeek",
        "accent": "#139c80",
        "border": "#68ccb6",
        "bg": "#effcf9",
        "divider": "#b0e6da",
    },
    "qwen": {
        "label": "Alibaba · Qwen",
        "accent": "#7352d1",
        "border": "#a992ea",
        "bg": "#f7f4ff",
        "divider": "#d3c6f5",
    },
    "z-ai": {
        "label": "Z.ai · GLM",
        "accent": "#4863d4",
        "border": "#8ea2ea",
        "bg": "#f3f6ff",
        "divider": "#c4cef5",
    },
    "moonshotai": {
        "label": "Moonshot · Kimi",
        "accent": "#be4488",
        "border": "#df8ab9",
        "bg": "#fff4fa",
        "divider": "#f0c2dc",
    },
    "x-ai": {
        "label": "xAI · Grok",
        "accent": "#5a687a",
        "border": "#9aa8ba",
        "bg": "#f6f8fa",
        "divider": "#cfd7e2",
    },
    "meta": {
        "label": "Meta",
        "accent": "#2e6fd9",
        "border": "#84aee9",
        "bg": "#f3f7ff",
        "divider": "#c2d7f6",
    },
    "mistralai": {
        "label": "Mistral",
        "accent": "#d96b27",
        "border": "#eaa475",
        "bg": "#fff7f2",
        "divider": "#f4cdb4",
    },
    "minimax": {
        "label": "MiniMax",
        "accent": "#c94c68",
        "border": "#e594a7",
        "bg": "#fff5f7",
        "divider": "#f2c6d0",
    },
    "tencent": {
        "label": "Tencent · Hunyuan",
        "accent": "#2382c9",
        "border": "#7cb8e5",
        "bg": "#f2f9ff",
        "divider": "#bcdcf4",
    },
    "xiaomi": {
        "label": "Xiaomi · MiMo",
        "accent": "#d6681e",
        "border": "#e8a572",
        "bg": "#fff7f0",
        "divider": "#f2cdb0",
    },
}

DEFAULT_THEME: dict[str, str] = {
    "label": "Other",
    "accent": "#64748b",
    "border": "#a0aec0",
    "bg": "#f7f9fc",
    "divider": "#cbd5e1",
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
    "glm": "z-ai",
    "zhipu": "z-ai",
    "智谱": "z-ai",
    "z-ai": "z-ai",
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


def _fmt_num(value: float) -> str:
    if value == 0:
        return "0"
    if value >= 10:
        s = f"{value:.1f}"
    elif value >= 1:
        s = f"{value:.2f}"
    else:
        s = f"{value:.2f}"
    return s.rstrip("0").rstrip(".")


def _format_price(pricing: dict[str, Any] | None) -> str:
    if not pricing:
        return "--"
    pin = pricing.get("input")
    pout = pricing.get("output")
    if pin is None and pout is None:
        return "--"
    pin_f = float(pin) if pin is not None else 0.0
    pout_f = float(pout) if pout is not None else 0.0
    if pin_f == 0.0 and pout_f == 0.0:
        return "FREE"
    return f"${_fmt_num(pin_f)}/${_fmt_num(pout_f)}"


def _blended_price(pricing: dict[str, Any] | None) -> float | None:
    if not pricing:
        return None
    pin = pricing.get("input")
    pout = pricing.get("output")
    if pin is None or pout is None:
        return None
    return (3.0 * float(pin) + float(pout)) / 4.0


def _format_perf(perf: dict[str, Any] | None) -> str:
    if not perf:
        return "--"
    tps = perf.get("throughput_tps")
    lat = perf.get("latency_ms")
    parts: list[str] = []
    if tps is not None:
        parts.append(f"{round(float(tps))}t/s")
    if lat is not None:
        lat_f = float(lat)
        if lat_f >= 1000:
            parts.append(f"{lat_f / 1000:.1f}s")
        else:
            parts.append(f"{round(lat_f)}ms")
    return " · ".join(parts) if parts else "--"


def _shorten_name(model: dict[str, Any]) -> str:
    name = str(model.get("name") or model.get("id") or "Unknown").strip()
    if ": " in name:
        name = name.split(": ", 1)[1].strip()
    # Remove redundant trailing "(free)" if price already says FREE
    return name


def _theme_for(maker: str) -> dict[str, str]:
    theme = MAKER_THEMES.get(maker)
    if theme:
        return theme
    return {**DEFAULT_THEME, "label": maker.upper() if maker else "Other"}


def _to_card(
    model: dict[str, Any],
    score_key: str = "intelligence",
    extra_badge: str = "",
) -> dict[str, Any]:
    maker = str(model.get("maker") or "").lower()
    theme = _theme_for(maker)
    aa = (model.get("benchmarks") or {}).get("artificial_analysis") or {}
    raw_score = aa.get(score_key)
    if raw_score is None and score_key != "intelligence":
        raw_score = aa.get("intelligence")
    score_text = f"{float(raw_score):.1f}" if raw_score is not None else "--"

    return {
        "name": _shorten_name(model),
        "maker": maker,
        "maker_label": theme["label"],
        "score": score_text,
        "price": _format_price(model.get("pricing")),
        "perf": _format_perf(model.get("performance")),
        "badge": extra_badge,
        "accent": theme["accent"],
        "border": theme["border"],
        "bg": theme["bg"],
        "divider": theme["divider"],
    }


def _chunk(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def build_view_data(
    models: list[dict[str, Any]],
    query: str,
    default_makers: list[str],
    max_per_maker: int,
    max_ranking_items: int,
    fetched_at: float,
    is_stale: bool = False,
) -> dict[str, Any]:
    """Prepare structured rows & cards for Jinja2 HTML rendering."""
    q = query.strip().lower()
    updated_str = datetime.fromtimestamp(fetched_at).strftime("%Y-%m-%d %H:%M")
    stale_note = "（上游暂不可用，显示缓存）" if is_stale else ""

    rows: list[dict[str, Any]] = []
    title = "AI 模型实时智商榜"
    subtitle = "智商指数（AA）· 价格 $/1M Tokens（入/出）· 速度 & 首字延迟"

    # Mode 1: Coding leaderboard
    if q in {"coding", "code", "编程", "代码"}:
        title = "AI 模型编程跑分榜 (Coding)"
        subtitle = "按 Artificial Analysis 编程指数降序 · 价格 $/1M（入/出）· 速度 & 延迟"
        scored = [
            m
            for m in models
            if ((m.get("benchmarks") or {}).get("artificial_analysis") or {}).get("coding")
            is not None
        ]
        scored.sort(
            key=lambda m: float(m["benchmarks"]["artificial_analysis"]["coding"]),
            reverse=True,
        )
        cards = [
            _to_card(m, score_key="coding", extra_badge=f"#{idx}")
            for idx, m in enumerate(scored[:max_ranking_items], start=1)
        ]
        for group in _chunk(cards, 6):
            rows.append({"cards": group})

    # Mode 2: Best value (IQ / blended price)
    elif q in {"value", "性价比", "便宜", "划算"}:
        title = "AI 模型性价比榜 (智商 ÷ 综合单价)"
        subtitle = "综合单价 = (3×输入 + 输出) / 4 · 仅统计付费且具备智商分模型"
        scored: list[tuple[float, dict[str, Any]]] = []
        for m in models:
            iq = ((m.get("benchmarks") or {}).get("artificial_analysis") or {}).get(
                "intelligence"
            )
            bp = _blended_price(m.get("pricing"))
            if iq is not None and bp is not None and bp > 0:
                scored.append((float(iq) / bp, m))
        scored.sort(key=lambda item: item[0], reverse=True)
        cards = [
            _to_card(m, score_key="intelligence", extra_badge=f"#{idx}")
            for idx, (_, m) in enumerate(scored[:max_ranking_items], start=1)
        ]
        for group in _chunk(cards, 6):
            rows.append({"cards": group})

    # Mode 3: Free models
    elif q in {"free", "免费", "白嫖"}:
        title = "免费 AI 模型智商榜 ($0)"
        subtitle = "按智商指数降序 · 0 成本模型 · 速度 & 首字延迟"
        free_models = []
        for m in models:
            p = m.get("pricing") or {}
            if p.get("input") == 0 and p.get("output") == 0:
                free_models.append(m)
        free_models.sort(
            key=lambda m: float(
                ((m.get("benchmarks") or {}).get("artificial_analysis") or {}).get(
                    "intelligence"
                )
                or -1.0
            ),
            reverse=True,
        )
        cards = [_to_card(m) for m in free_models[:max_ranking_items]]
        for group in _chunk(cards, 6):
            rows.append({"cards": group})

    # Mode 4: Vendor / keyword filter
    elif q:
        mapped_maker = MAKER_ALIASES.get(q)
        if mapped_maker:
            matched = [
                m
                for m in models
                if str(m.get("maker") or "").lower() == mapped_maker
                or mapped_maker in str(m.get("id") or "").lower()
            ]
            label = _theme_for(mapped_maker)["label"]
            title = f"{label} 模型实时智商榜"
        else:
            matched = [
                m
                for m in models
                if q in str(m.get("id") or "").lower()
                or q in str(m.get("name") or "").lower()
                or q in str(m.get("maker") or "").lower()
            ]
            title = f"搜索「{query.strip()}」模型智商榜"

        matched.sort(
            key=lambda m: float(
                ((m.get("benchmarks") or {}).get("artificial_analysis") or {}).get(
                    "intelligence"
                )
                or -1.0
            ),
            reverse=True,
        )
        cards = [_to_card(m) for m in matched[:max_ranking_items]]
        for group in _chunk(cards, 6):
            rows.append({"cards": group})

    # Mode 5: Default multi-vendor grouped rows (mirrors reference screenshot)
    else:
        by_maker: dict[str, list[dict[str, Any]]] = {}
        for m in models:
            iq = ((m.get("benchmarks") or {}).get("artificial_analysis") or {}).get(
                "intelligence"
            )
            if iq is None:
                continue
            maker = str(m.get("maker") or "").lower()
            by_maker.setdefault(maker, []).append(m)

        for maker in default_makers:
            maker_key = maker.strip().lower()
            if not maker_key or maker_key not in by_maker:
                continue
            group_models = sorted(
                by_maker[maker_key],
                key=lambda m: float(
                    m["benchmarks"]["artificial_analysis"]["intelligence"]
                ),
                reverse=True,
            )[:max_per_maker]
            if group_models:
                rows.append({"cards": [_to_card(m) for m in group_models]})

    total_cards = sum(len(r["cards"]) for r in rows)
    return {
        "title": title,
        "subtitle": subtitle,
        "rows": rows,
        "total_cards": total_cards,
        "updated_str": updated_str,
        "stale_note": stale_note,
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<style>
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  body {
    background: #ffffff;
    font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    padding: 20px 22px 16px 22px;
    width: 1320px;
    color: #1f2937;
  }
  .header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 14px;
    padding: 0 4px;
  }
  .title {
    font-size: 20px;
    font-weight: 700;
    color: #111827;
    letter-spacing: 0.2px;
  }
  .subtitle {
    font-size: 12px;
    color: #6b7280;
  }
  .rows {
    display: flex;
    flex-direction: column;
    gap: 11px;
  }
  .row {
    display: flex;
    justify-content: center;
    flex-wrap: nowrap;
    gap: 10px;
  }
  .card {
    position: relative;
    width: 204px;
    min-height: 78px;
    border-radius: 9px;
    border: 1.2px solid var(--border);
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
    height: 3.5px;
    background: var(--accent);
    border-radius: 0 0 3px 3px;
  }
  .card-left {
    flex: 1;
    min-width: 0;
    padding: 9px 8px 7px 10px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }
  .model-name {
    font-size: 12.5px;
    line-height: 1.18;
    font-weight: 600;
    color: var(--accent);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    word-break: break-word;
  }
  .badge {
    font-size: 10px;
    font-weight: 700;
    opacity: 0.8;
    margin-right: 3px;
  }
  .score {
    font-size: 29px;
    line-height: 1.02;
    font-weight: 500;
    color: #1f2937;
    letter-spacing: -0.6px;
    margin-top: 4px;
    font-variant-numeric: tabular-nums;
  }
  .card-right {
    width: 78px;
    flex-shrink: 0;
    border-left: 1px solid var(--divider);
    margin: 10px 0 8px 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }
  .metric-top {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 4px 3px 4px;
    font-size: 12.5px;
    font-weight: 600;
    color: var(--accent);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .metric-bottom {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    border-top: 1px solid var(--divider);
    margin: 0 6px;
    padding: 3px 0 0 0;
    font-size: 11px;
    font-weight: 500;
    color: #556070;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .footer {
    margin-top: 12px;
    padding: 0 4px;
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: #9ca3af;
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
    <div class="row">
      {% for card in row.cards %}
      <div class="card" style="--accent: {{ card.accent }}; --border: {{ card.border }}; --bg: {{ card.bg }}; --divider: {{ card.divider }};">
        <div class="card-left">
          <div class="model-name">{% if card.badge %}<span class="badge">{{ card.badge }}</span>{% endif %}{{ card.name }}</div>
          <div class="score">{{ card.score }}</div>
        </div>
        <div class="card-right">
          <div class="metric-top">{{ card.price }}</div>
          <div class="metric-bottom">{{ card.perf }}</div>
        </div>
      </div>
      {% endfor %}
    </div>
    {% endfor %}
  </div>
  <div class="footer">
    <span>数据来源：Artificial Analysis + OpenRouter (via modelgrep) · 共展示 {{ total_cards }} 个模型</span>
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
            lines.append(
                f"- {prefix}{c['name']} | 评分: {c['score']} | 价格: {c['price']} | 速度/延迟: {c['perf']}"
            )
    lines.append("")
    lines.append(f"更新于 {view_data['updated_str']}{view_data['stale_note']}")
    return "\n".join(lines)
