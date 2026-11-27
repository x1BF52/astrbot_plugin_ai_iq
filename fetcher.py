from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp

from astrbot.api import logger


AA_LEADERBOARD_URL = "https://artificialanalysis.ai/leaderboards/models"
AA_API_URL = "https://artificialanalysis.ai/api/v2/language/models/free"
LLMPRICING_API_URL = "https://llmpricing.dev/api/models.json"
BENCHGECKO_API_URL = "https://benchgecko.ai/api/v1/models"
MODELGREP_API_URL = "https://modelgrep.com/api/v1/models"

CACHE_SCHEMA_VERSION = 3

_NEXT_RSC_CHUNK_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', re.S)
_PAREN_SUFFIX_RE = re.compile(r"^(.*?)\s*\(([^()]+)\)\s*$")
_EFFORT_SUFFIX_HINTS = (
    "extreme",
    "ultra",
    "max",
    "xhigh",
    "high",
    "medium",
    "low",
    "minimal",
    "reason",
    "think",
    "non-reasoning",
    "adaptive",
)

_CREATOR_MAP: dict[str, str] = {
    "anthropic": "anthropic",
    "openai": "openai",
    "google": "google",
    "deepseek": "deepseek",
    "alibaba": "qwen",
    "qwen": "qwen",
    "z ai": "z-ai",
    "z.ai": "z-ai",
    "z-ai": "z-ai",
    "zai": "z-ai",
    "zhipu": "z-ai",
    "zhipuai": "z-ai",
    "kimi": "moonshotai",
    "moonshot": "moonshotai",
    "moonshot ai": "moonshotai",
    "moonshotai": "moonshotai",
    "xai": "x-ai",
    "x-ai": "x-ai",
    "spacexai": "x-ai",
    "spacexsi": "x-ai",
    "meta": "meta",
    "meta-llama": "meta",
    "mistral": "mistralai",
    "mistral ai": "mistralai",
    "mistralai": "mistralai",
    "minimax": "minimax",
    "tencent": "tencent",
    "xiaomi": "xiaomi",
    "nvidia": "nvidia",
    "stepfun": "stepfun",
    "cohere": "cohere",
    "liquid ai": "liquid",
    "upstage": "upstage",
    "reflection": "reflection",
    "thinking machines": "thinkingmachines",
    "inclusionai": "inclusionai",
    "baidu": "baidu",
}

EFFORT_LABELS: dict[str, str] = {
    "extreme": "extreme",
    "ultra": "ultra",
    "max": "max",
    "xhigh": "xhigh",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "minimal": "minimal",
    "reasoning": "推理",
    "non-reasoning": "无推理",
    "": "默认",
}


def format_exc(exc: BaseException) -> str:
    """Format an exception reliably even when str(exc) is empty (e.g. asyncio.TimeoutError)."""
    msg = str(exc).strip()
    return f"{type(exc).__name__}: {msg}" if msg else type(exc).__name__


def normalize_creator(creator_name: str | None) -> str:
    """Canonicalize upstream vendor/creator identifiers into internal maker keys."""
    key = (creator_name or "").strip().lower()
    if key in _CREATOR_MAP:
        return _CREATOR_MAP[key]
    return re.sub(r"[^a-z0-9-]+", "-", key).strip("-") or "other"


def normalize_effort(suffix: str | None, is_reasoning: bool | None) -> tuple[str, str]:
    """Normalize AA suffix / reasoning flag into (canonical_key, display_label)."""
    raw = (suffix or "").strip()
    if raw:
        # Strip trailing tags like ", Default Fallback", ", Adaptive Reasoning"
        head = raw.split(",")[0].strip().lower()
        head = head.replace("_", "-").replace(" ", "-")
        if "non-reasoning" in head or head in {"none", "off", "no-reasoning"}:
            return "non-reasoning", EFFORT_LABELS["non-reasoning"]
        if head in EFFORT_LABELS:
            return head, EFFORT_LABELS[head]
        for key in ("extreme", "ultra", "xhigh", "max", "high", "medium", "low", "minimal"):
            if key in head:
                return key, EFFORT_LABELS[key]
        if "reason" in head or "think" in head:
            return "reasoning", EFFORT_LABELS["reasoning"]
        return head, raw.split(",")[0].strip()

    if is_reasoning is True:
        return "reasoning", EFFORT_LABELS["reasoning"]
    if is_reasoning is False:
        return "non-reasoning", EFFORT_LABELS["non-reasoning"]
    return "", EFFORT_LABELS[""]


def _as_float(val: Any) -> float | None:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return None
    return float(val)


def _parse_iso_date_ts(date_str: str | None) -> float | None:
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


def _derive_coding_from_evals(evals: dict[str, Any]) -> float | None:
    """Derive a 0-100 coding composite from FrontierCode 2.0 & Terminal-Bench 4.x."""
    fc2 = evals.get("frontiercode-2-0")
    tb = evals.get("terminalbench-4-1") or evals.get("terminalbench-4-0")
    vals = [v for v in (_as_float(fc2), _as_float(tb)) if v is not None]
    return round(sum(vals) / len(vals) * 100.0, 2) if vals else None


def _build_model_record(
    *,
    model_id: str,
    release_slug: str,
    release_name: str,
    name: str,
    effort: str,
    effort_label: str,
    maker: str,
    source: str,
    iq: Any = None,
    coding: Any = None,
    price_in: Any = None,
    price_out: Any = None,
    cost_per_task: Any = None,
    time_per_task: Any = None,
    tps: Any = None,
    latency_s: Any = None,
    release_date: str | None = None,
    created_ts: float | None = None,
    deprecated: bool = False,
    is_reasoning: bool = True,
    creator_color: str | None = None,
) -> dict[str, Any]:
    return {
        "id": model_id,
        "release_slug": release_slug,
        "release_name": release_name,
        "name": name,
        "effort": effort,
        "effort_label": effort_label,
        "maker": maker,
        "creator_color": creator_color,
        "release_date": release_date,
        "created_ts": created_ts if created_ts is not None else _parse_iso_date_ts(release_date),
        "deprecated": deprecated,
        "is_reasoning": is_reasoning,
        "iq": _as_float(iq),
        "coding": _as_float(coding),
        "price_in": _as_float(price_in),
        "price_out": _as_float(price_out),
        "cost_per_task": _as_float(cost_per_task),
        "time_per_task": _as_float(time_per_task),
        "tps": _as_float(tps),
        "latency_s": _as_float(latency_s),
        "source": source,
    }


def parse_aa_leaderboard_html(html: str) -> list[dict[str, Any]]:
    """Extract realtime model evaluations (with reasoning effort tiers) from AA's RSC payload."""
    chunks = _NEXT_RSC_CHUNK_RE.findall(html)
    if not chunks:
        raise RuntimeError("Artificial Analysis 页面未找到 Next.js 数据块")

    decoded_parts: list[str] = []
    for chunk in chunks:
        try:
            decoded_parts.append(json.loads('"' + chunk + '"'))
        except Exception:
            continue
    full = "".join(decoded_parts)

    idx = full.find('"intelligenceIndex"')
    if idx == -1:
        raise RuntimeError("Artificial Analysis 页面中未找到 intelligenceIndex 数据")
    arr_start = full.rfind('[{"id":', 0, idx)
    if arr_start == -1:
        raise RuntimeError("Artificial Analysis 页面中未定位到模型数组起始位置")

    decoder = json.JSONDecoder()
    models_arr, _ = decoder.raw_decode(full, arr_start)
    if not isinstance(models_arr, list) or not models_arr:
        raise RuntimeError("Artificial Analysis 模型数组为空")

    # Optional release metadata array for accurate releaseDate & deprecated flags
    release_meta: dict[str, dict[str, Any]] = {}
    r_idx = full.find('"releaseDate":')
    if r_idx != -1:
        r_start = full.rfind('[{"slug":', 0, r_idx)
        if r_start != -1:
            try:
                rel_arr, _ = decoder.raw_decode(full, r_start)
                if isinstance(rel_arr, list):
                    for item in rel_arr:
                        slug = item.get("slug")
                        if slug:
                            release_meta[slug] = item
            except Exception:
                pass

    normalized: list[dict[str, Any]] = []
    for item in models_arr:
        if not isinstance(item, dict):
            continue
        iq = _as_float(item.get("intelligenceIndex"))
        scores = item.get("scores") if isinstance(item.get("scores"), dict) else {}
        coding = _derive_coding_from_evals(scores)
        if iq is None and coding is None:
            continue

        rel_obj = item.get("release") if isinstance(item.get("release"), dict) else {}
        rel_slug = str(rel_obj.get("slug") or item.get("id") or "").strip()
        rel_name = str(rel_obj.get("name") or item.get("shortName") or item.get("name") or "").strip()
        if not rel_obj.get("name") and "(" in rel_name:
            rel_name = re.sub(r"\s*\([^)]*\)\s*$", "", rel_name).strip()

        rmeta = release_meta.get(rel_slug, {})
        is_reasoning = item.get("isReasoning")
        effort, effort_label = normalize_effort(item.get("suffix"), is_reasoning)
        latency_s = item.get("timeToFirstAnswerToken")
        if latency_s is None:
            latency_s = item.get("timeToFirstToken")

        normalized.append(
            _build_model_record(
                model_id=str(item.get("id") or f"{rel_slug}:{effort}"),
                release_slug=rel_slug,
                release_name=rel_name,
                name=str(item.get("shortName") or item.get("name") or rel_name),
                effort=effort,
                effort_label=effort_label,
                maker=normalize_creator(item.get("modelCreatorName")),
                creator_color=item.get("modelCreatorColor"),
                release_date=rmeta.get("releaseDate"),
                deprecated=bool(item.get("deprecated")) or bool(rmeta.get("deprecated")),
                is_reasoning=bool(is_reasoning),
                iq=iq,
                coding=coding,
                price_in=item.get("price1mInputTokens"),
                price_out=item.get("price1mOutputTokens"),
                cost_per_task=item.get("intelligenceIndexCostPerTask"),
                time_per_task=item.get("intelligenceIndexTimePerTask"),
                tps=item.get("outputSpeed"),
                latency_s=latency_s,
                source="artificial_analysis",
            )
        )

    if not normalized:
        raise RuntimeError("Artificial Analysis 未解析出有效带评分模型")
    return normalized


def normalize_modelgrep_models(raw_models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize modelgrep API payload into the unified schema."""
    normalized: list[dict[str, Any]] = []
    for m in raw_models:
        if not isinstance(m, dict):
            continue
        aa = (m.get("benchmarks") or {}).get("artificial_analysis") or {}
        iq = _as_float(aa.get("intelligence"))
        coding = _as_float(aa.get("coding"))
        if iq is None and coding is None:
            continue

        raw_name = str(m.get("name") or m.get("id") or "").strip()
        if ":" in raw_name:
            raw_name = raw_name.split(":", 1)[1].strip()
        mid = str(m.get("id") or raw_name)
        rel_slug = mid.split("/", 1)[-1].replace(":free", "")

        caps = m.get("capabilities") or {}
        is_reasoning = caps.get("reasoning")
        effort, effort_label = normalize_effort(None, is_reasoning)

        pricing = m.get("pricing") or {}
        perf = m.get("performance") or {}
        lat_ms = _as_float(perf.get("latency_ms"))
        created_ts = _as_float(m.get("created"))
        release_date = (
            datetime.fromtimestamp(created_ts, tz=timezone.utc).strftime("%Y-%m-%d")
            if created_ts
            else None
        )

        normalized.append(
            _build_model_record(
                model_id=mid,
                release_slug=rel_slug,
                release_name=raw_name,
                name=raw_name,
                effort=effort,
                effort_label=effort_label,
                maker=normalize_creator(m.get("maker")),
                release_date=release_date,
                created_ts=created_ts,
                is_reasoning=bool(is_reasoning),
                iq=iq,
                coding=coding,
                price_in=pricing.get("input"),
                price_out=pricing.get("output"),
                tps=perf.get("throughput_tps"),
                latency_s=(lat_ms / 1000.0) if lat_ms is not None else None,
                source="modelgrep",
            )
        )
    return normalized


def normalize_aa_api_models(raw_models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize Artificial Analysis official v2 API records into the unified schema."""
    normalized: list[dict[str, Any]] = []
    for item in raw_models:
        if not isinstance(item, dict):
            continue
        evals = item.get("evaluations") if isinstance(item.get("evaluations"), dict) else {}
        iq = _as_float(evals.get("artificial_analysis_intelligence_index"))
        coding = _as_float(evals.get("artificial_analysis_coding_index"))
        if coding is None:
            coding = _as_float(evals.get("artificial_analysis_engineering_index"))
        if iq is None and coding is None:
            continue

        raw_name = str(item.get("name") or item.get("slug") or "").strip()
        suffix = item.get("suffix")
        base_name = raw_name
        if not suffix:
            m_paren = _PAREN_SUFFIX_RE.match(raw_name)
            if m_paren:
                candidate = m_paren.group(2).strip()
                c_low = candidate.lower()
                if any(k in c_low for k in _EFFORT_SUFFIX_HINTS):
                    base_name = m_paren.group(1).strip()
                    suffix = candidate

        creator_obj = (
            item.get("model_creator") if isinstance(item.get("model_creator"), dict) else {}
        )
        maker = normalize_creator(
            creator_obj.get("name") or creator_obj.get("slug") or item.get("maker")
        )
        rel_slug = re.sub(r"[^a-z0-9.+-]+", "-", base_name.lower()).strip("-") or str(
            item.get("slug") or item.get("id") or ""
        )
        is_reasoning = item.get("reasoning_model")
        effort, effort_label = normalize_effort(suffix, is_reasoning)

        pricing = item.get("pricing") if isinstance(item.get("pricing"), dict) else {}
        cost_obj = (
            item.get("artificial_analysis_intelligence_index_cost")
            if isinstance(item.get("artificial_analysis_intelligence_index_cost"), dict)
            else {}
        )
        cpt_obj = (
            cost_obj.get("cost_per_task")
            if isinstance(cost_obj.get("cost_per_task"), dict)
            else {}
        )
        perf_v3 = (
            item.get("performance_v3")
            if isinstance(item.get("performance_v3"), dict)
            else {}
        )
        perf_legacy = (
            item.get("performance")
            if isinstance(item.get("performance"), dict)
            else {}
        )

        tps = (
            perf_v3.get("mean_output_tokens_per_second")
            or perf_v3.get("median_output_tokens_per_second")
            or perf_legacy.get("median_output_tokens_per_second")
            or item.get("median_output_tokens_per_second")
        )
        latency_s = (
            perf_v3.get("mean_time_to_first_answer_token_seconds")
            or perf_v3.get("mean_time_to_first_token_seconds")
            or perf_legacy.get("median_time_to_first_answer_token_seconds")
            or perf_legacy.get("median_time_to_first_token_seconds")
            or item.get("median_time_to_first_answer_token")
            or item.get("median_time_to_first_token_seconds")
        )

        normalized.append(
            _build_model_record(
                model_id=str(item.get("id") or item.get("slug") or f"{rel_slug}:{effort}"),
                release_slug=rel_slug,
                release_name=base_name,
                name=raw_name,
                effort=effort,
                effort_label=effort_label,
                maker=maker,
                release_date=item.get("release_date"),
                deprecated=bool(item.get("deprecated")),
                is_reasoning=bool(is_reasoning) if is_reasoning is not None else (effort != "non-reasoning"),
                iq=iq,
                coding=coding,
                price_in=pricing.get("price_1m_input_tokens"),
                price_out=pricing.get("price_1m_output_tokens"),
                cost_per_task=cpt_obj.get("total_cost"),
                time_per_task=perf_v3.get("time_per_task_seconds"),
                tps=tps,
                latency_s=latency_s,
                source="artificial_analysis_api",
            )
        )
    return normalized


def normalize_llmpricing_models(raw_models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize llmpricing.dev/api/models.json records into the unified schema."""
    normalized: list[dict[str, Any]] = []
    for item in raw_models:
        if not isinstance(item, dict):
            continue
        aa = item.get("aa") if isinstance(item.get("aa"), dict) else None
        if not aa:
            continue

        iq = _as_float(aa.get("idx"))
        coding = _as_float(aa.get("coding"))
        evals = aa.get("evals") if isinstance(aa.get("evals"), dict) else {}
        if coding is None and evals:
            coding = _derive_coding_from_evals(evals)
        if iq is None and coding is None:
            continue

        mid = str(item.get("id") or "").strip()
        raw_name = str(item.get("name") or mid).strip()
        rel_slug = mid.split("/", 1)[-1] if "/" in mid else mid
        lab = item.get("lab") or (mid.split("/", 1)[0] if "/" in mid else "")

        caps = item.get("capabilities") if isinstance(item.get("capabilities"), dict) else {}
        is_reasoning = caps.get("reasoning")
        effort, effort_label = normalize_effort(None, is_reasoning)

        price_obj = item.get("official") or item.get("reference") or item.get("cheapest") or {}
        if not isinstance(price_obj, dict):
            price_obj = {}

        normalized.append(
            _build_model_record(
                model_id=mid or rel_slug,
                release_slug=rel_slug,
                release_name=raw_name,
                name=raw_name,
                effort=effort,
                effort_label=effort_label,
                maker=normalize_creator(lab),
                release_date=item.get("releaseDate"),
                deprecated=str(item.get("status") or "").lower() == "deprecated",
                is_reasoning=bool(is_reasoning),
                iq=iq,
                coding=coding,
                price_in=price_obj.get("input"),
                price_out=price_obj.get("output"),
                cost_per_task=aa.get("taskCost"),
                tps=aa.get("speed"),
                latency_s=aa.get("ttft"),
                source="llmpricing",
            )
        )
    return normalized


def normalize_benchgecko_models(raw_models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize benchgecko.ai/api/v1/models multi-benchmark records into the unified schema."""
    normalized: list[dict[str, Any]] = []
    for item in raw_models:
        if not isinstance(item, dict):
            continue
        avg_score = _as_float(item.get("avg_score"))
        scores = item.get("scores") if isinstance(item.get("scores"), dict) else {}
        coding = _as_float(scores.get("frontierswe"))
        if avg_score is None and coding is None:
            continue

        slug = str(item.get("slug") or "").strip()
        raw_name = str(item.get("name") or slug).strip()
        pricing = item.get("pricing") if isinstance(item.get("pricing"), dict) else {}

        normalized.append(
            _build_model_record(
                model_id=slug or raw_name,
                release_slug=slug or raw_name.lower(),
                release_name=raw_name,
                name=raw_name,
                effort="",
                effort_label="",
                maker=normalize_creator(item.get("provider_slug") or item.get("provider")),
                release_date=item.get("release_date"),
                iq=avg_score,
                coding=coding,
                price_in=pricing.get("input"),
                price_out=pricing.get("output"),
                source="benchgecko",
            )
        )
    return normalized


def parse_custom_api_response(text: str) -> list[dict[str, Any]]:
    """Auto-detect and parse response from a custom API / reverse proxy URL."""
    stripped = text.lstrip()
    if stripped.startswith("<"):
        return parse_aa_leaderboard_html(text)

    body = json.loads(text)
    items = body.get("data") if isinstance(body, dict) else body
    if isinstance(body, dict) and items is None:
        items = body.get("models")
    if not isinstance(items, list) or not items:
        raise RuntimeError("自定义 API 返回了空的模型列表")

    sample = next((x for x in items if isinstance(x, dict)), None)
    if sample is None:
        raise RuntimeError("自定义 API 返回数据格式无法识别")

    if "release_slug" in sample and "effort" in sample:
        return items
    if "avg_score" in sample and "provider_slug" in sample:
        return normalize_benchgecko_models(items)
    if "aa" in sample and "lab" in sample:
        return normalize_llmpricing_models(items)
    if "evaluations" in sample or "model_creator" in sample:
        return normalize_aa_api_models(items)
    return normalize_modelgrep_models(items)


@dataclass
class FetchResult:
    models: list[dict[str, Any]]
    fetched_at: float
    source: str = "artificial_analysis"
    from_cache: bool = False
    is_stale: bool = False
    is_fallback: bool = False
    error: str | None = None


class ModelDataFetcher:
    """Fetches and caches realtime LLM benchmark, reasoning effort, pricing, and speed data."""

    def __init__(
        self,
        cache_file: Path,
        ttl_seconds: int = 900,
        timeout_seconds: int = 25,
        proxy: str = "",
        data_source: str = "auto",
        aa_api_key: str = "",
        custom_api_url: str = "",
    ) -> None:
        self.cache_file = cache_file
        self.ttl_seconds = max(60, ttl_seconds)
        self.timeout_seconds = max(5, timeout_seconds)
        self.proxy = proxy.strip() or None
        self.data_source = (data_source or "auto").strip().lower()
        self.aa_api_key = (aa_api_key or "").strip()
        self.custom_api_url = (custom_api_url or "").strip()
        self._lock = asyncio.Lock()
        self._session: aiohttp.ClientSession | None = None
        self._mem_cache: dict[str, tuple[list[dict[str, Any]], float, str]] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=self.timeout_seconds,
                sock_connect=min(8, self.timeout_seconds),
                sock_read=self.timeout_seconds,
            )
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            }
            self._session = aiohttp.ClientSession(
                timeout=timeout, headers=headers, trust_env=True
            )
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _get_json(
        self,
        url: str,
        label: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        session = await self._get_session()
        req_headers = {"Accept": "application/json", **(headers or {})}
        async with session.get(
            url, params=params, proxy=self.proxy, headers=req_headers
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"{label} 返回状态码 {resp.status}")
            return await resp.json(content_type=None)

    async def _get_text(
        self,
        url: str,
        label: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> str:
        session = await self._get_session()
        async with session.get(url, proxy=self.proxy, headers=headers) as resp:
            if resp.status != 200:
                raise RuntimeError(f"{label} 返回状态码 {resp.status}")
            return await resp.text()

    def _cache_bucket_for(self, prefer: str, allow_custom: bool) -> str:
        """Isolate disk/memory caches across different sources and custom API endpoints."""
        if prefer in {"benchgecko", "llmpricing", "modelgrep"}:
            return prefer
        if allow_custom and self.custom_api_url:
            digest = hashlib.md5(self.custom_api_url.encode("utf-8")).hexdigest()[:8]
            return f"custom_{digest}"
        return "primary"

    def _cache_path_for(self, bucket: str) -> Path:
        if bucket == "primary":
            return self.cache_file
        return self.cache_file.with_name(f"{self.cache_file.stem}_{bucket}{self.cache_file.suffix}")

    def _load_disk_cache(
        self, bucket: str
    ) -> tuple[list[dict[str, Any]], float, str] | None:
        path = self._cache_path_for(bucket)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if raw.get("schema_version") != CACHE_SCHEMA_VERSION:
                return None
            models = raw.get("models")
            fetched_at = float(raw.get("fetched_at", 0.0))
            source = str(raw.get("source") or "artificial_analysis")
            if isinstance(models, list) and models and fetched_at > 0:
                return models, fetched_at, source
        except Exception as exc:
            logger.warning(f"[ai_iq] 读取本地缓存失败 ({bucket}): {format_exc(exc)}")
        return None

    def _save_disk_cache(
        self, bucket: str, models: list[dict[str, Any]], fetched_at: float, source: str
    ) -> None:
        path = self._cache_path_for(bucket)
        tmp_path = path.with_suffix(f"{path.suffix}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": CACHE_SCHEMA_VERSION,
                "source": source,
                "fetched_at": fetched_at,
                "models": models,
            }
            tmp_path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            os.replace(tmp_path, path)
        except Exception as exc:
            logger.warning(f"[ai_iq] 写入本地缓存失败 ({bucket}): {format_exc(exc)}")
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass

    @staticmethod
    def _is_degraded_cache(prefer: str, cached_source: str) -> bool:
        return prefer == "auto" and cached_source in {"llmpricing", "modelgrep"}

    def _try_cache_hit(
        self,
        entry: tuple[list[dict[str, Any]], float, str] | None,
        *,
        prefer: str,
        now: float,
        force_refresh: bool,
    ) -> FetchResult | None:
        if (
            force_refresh
            or entry is None
            or (now - entry[1]) >= self.ttl_seconds
            or self._is_degraded_cache(prefer, entry[2])
        ):
            return None
        return FetchResult(
            models=entry[0],
            fetched_at=entry[1],
            source=entry[2],
            from_cache=True,
        )

    async def _fetch_aa_api(self) -> list[dict[str, Any]]:
        headers = {"x-api-key": self.aa_api_key}

        async def _get_page(page: int) -> dict[str, Any]:
            body = await self._get_json(
                AA_API_URL,
                "Artificial Analysis API",
                params={"page": str(page)},
                headers=headers,
            )
            if not isinstance(body, dict):
                return {"data": body if isinstance(body, list) else []}
            return body

        first = await _get_page(1)
        items: list[Any] = list(first.get("data") or [])
        pagination = first.get("pagination") if isinstance(first.get("pagination"), dict) else {}
        total_pages = max(1, min(12, int(pagination.get("total_pages") or 1)))

        if total_pages > 1:
            rest_pages = await asyncio.gather(
                *(_get_page(p) for p in range(2, total_pages + 1))
            )
            for page_body in rest_pages:
                items.extend(page_body.get("data") or [])

        if not items:
            raise RuntimeError("Artificial Analysis API 返回了空的模型列表")
        normalized = normalize_aa_api_models(items)
        if not normalized:
            raise RuntimeError("Artificial Analysis API 未包含带跑分模型")
        return normalized

    async def _fetch_custom_api(self) -> list[dict[str, Any]]:
        headers: dict[str, str] = {"Accept": "application/json, text/html"}
        if self.aa_api_key:
            headers["x-api-key"] = self.aa_api_key
            headers["Authorization"] = f"Bearer {self.aa_api_key}"
        text = await self._get_text(self.custom_api_url, "自定义 API", headers=headers)
        return parse_custom_api_response(text)

    async def _fetch_artificial_analysis(self) -> tuple[list[dict[str, Any]], str]:
        if self.aa_api_key:
            try:
                return await self._fetch_aa_api(), "artificial_analysis_api"
            except Exception as api_exc:
                logger.warning(
                    f"[ai_iq] Artificial Analysis 官方 API 拉取失败，尝试公开榜单页: {format_exc(api_exc)}"
                )
        html = await self._get_text(
            AA_LEADERBOARD_URL,
            "Artificial Analysis",
            headers={"Accept": "text/html,application/xhtml+xml"},
        )
        return parse_aa_leaderboard_html(html), "artificial_analysis"

    async def _fetch_modelgrep(self) -> list[dict[str, Any]]:
        all_models: list[dict[str, Any]] = []
        offset = 0
        limit = 200

        for _ in range(5):
            body = await self._get_json(
                MODELGREP_API_URL,
                "modelgrep",
                params={
                    "benchmarked": "1",
                    "sort": "intelligence",
                    "limit": str(limit),
                    "offset": str(offset),
                },
            )
            batch = body.get("data") or []
            all_models.extend(batch)
            meta = body.get("meta") or {}
            if not meta.get("has_more") or not batch:
                break
            next_offset = meta.get("next_offset")
            offset = int(next_offset) if next_offset is not None else offset + len(batch)

        normalized = normalize_modelgrep_models(all_models)
        if not normalized:
            raise RuntimeError("modelgrep 返回了空的模型列表")
        return normalized

    async def _fetch_llmpricing(self) -> list[dict[str, Any]]:
        body = await self._get_json(LLMPRICING_API_URL, "llmpricing.dev")
        items = body.get("models") if isinstance(body, dict) else body
        if not isinstance(items, list) or not items:
            raise RuntimeError("llmpricing.dev 返回了空的模型列表")
        normalized = normalize_llmpricing_models(items)
        if not normalized:
            raise RuntimeError("llmpricing.dev 未包含带 AA 跑分的模型")
        return normalized

    async def _fetch_benchgecko(self) -> list[dict[str, Any]]:
        body = await self._get_json(
            BENCHGECKO_API_URL, "BenchGecko", params={"limit": "200"}
        )
        items = body.get("data") if isinstance(body, dict) else body
        if not isinstance(items, list) or not items:
            raise RuntimeError("BenchGecko 返回了空的模型列表")
        normalized = normalize_benchgecko_models(items)
        if not normalized:
            raise RuntimeError("BenchGecko 未包含有效评分模型")
        return normalized

    async def _fetch_fallback_race(self) -> tuple[list[dict[str, Any]], str]:
        """Race llmpricing.dev and modelgrep concurrently with a bounded timeout."""
        fb_timeout = min(12, self.timeout_seconds)
        t0 = time.monotonic()

        async def _run(name: str, coro: Any) -> tuple[str, list[dict[str, Any]]]:
            models = await asyncio.wait_for(coro, timeout=fb_timeout)
            return name, models

        pending: set[asyncio.Task[tuple[str, list[dict[str, Any]]]]] = {
            asyncio.create_task(_run("llmpricing", self._fetch_llmpricing())),
            asyncio.create_task(_run("modelgrep", self._fetch_modelgrep())),
        }
        errors: list[str] = []

        try:
            while pending:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    exc = task.exception()
                    if exc is None:
                        src, models = task.result()
                        logger.info(
                            f"[ai_iq] 临时回退 {src} 成功（{len(models)} 条，耗时 {time.monotonic() - t0:.1f}s）"
                        )
                        return models, src
                    errors.append(format_exc(exc))
        finally:
            if pending:
                for p in pending:
                    p.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

        raise RuntimeError(f"所有回退数据源均失败: {' | '.join(errors)}")

    async def _fetch_remote(
        self, prefer_source: str, *, allow_custom: bool = True
    ) -> tuple[list[dict[str, Any]], str, bool]:
        """Returns (models, actual_source, is_fallback)."""
        if prefer_source == "benchgecko":
            return await self._fetch_benchgecko(), "benchgecko", False
        if prefer_source == "llmpricing":
            return await self._fetch_llmpricing(), "llmpricing", False
        if prefer_source == "modelgrep":
            return await self._fetch_modelgrep(), "modelgrep", False

        if allow_custom and self.custom_api_url:
            try:
                return await self._fetch_custom_api(), "custom_api", False
            except Exception as custom_exc:
                if prefer_source != "auto":
                    raise
                logger.warning(
                    f"[ai_iq] 自定义 API 拉取失败，回退内置主源: {format_exc(custom_exc)}"
                )

        if prefer_source == "artificial_analysis":
            models, src = await self._fetch_artificial_analysis()
            return models, src, False

        # auto: try Artificial Analysis first (has reasoning effort breakdown),
        # temporarily fallback to concurrent llmpricing.dev / modelgrep race if AA is unreachable
        # (do NOT poison cache with degraded fallback).
        try:
            models, src = await self._fetch_artificial_analysis()
            return models, src, False
        except Exception as aa_exc:
            logger.warning(
                f"[ai_iq] Artificial Analysis 拉取失败，并发回退 llmpricing.dev / modelgrep（不写入缓存）: {format_exc(aa_exc)}"
            )
            models, fb_src = await self._fetch_fallback_race()
            return models, fb_src, True

    async def get_models(
        self, force_refresh: bool = False, source_override: str | None = None
    ) -> FetchResult:
        prefer = (source_override or self.data_source or "auto").strip().lower()
        allow_custom = source_override is None
        bucket = self._cache_bucket_for(prefer, allow_custom)
        now = time.time()

        hit = self._try_cache_hit(
            self._mem_cache.get(bucket),
            prefer=prefer,
            now=now,
            force_refresh=force_refresh,
        )
        if hit is not None:
            return hit

        async with self._lock:
            now = time.time()
            mem = self._mem_cache.get(bucket)
            hit = self._try_cache_hit(
                mem, prefer=prefer, now=now, force_refresh=force_refresh
            )
            if hit is not None:
                return hit

            disk_cache = self._load_disk_cache(bucket)
            hit = self._try_cache_hit(
                disk_cache, prefer=prefer, now=now, force_refresh=force_refresh
            )
            if hit is not None:
                self._mem_cache[bucket] = disk_cache  # type: ignore[assignment]
                return hit

            try:
                models, actual_source, is_fallback = await self._fetch_remote(
                    prefer, allow_custom=allow_custom
                )
                fetched_at = time.time()
                if not is_fallback:
                    self._mem_cache[bucket] = (models, fetched_at, actual_source)
                    self._save_disk_cache(bucket, models, fetched_at, actual_source)
                return FetchResult(
                    models=models,
                    fetched_at=fetched_at,
                    source=actual_source,
                    from_cache=False,
                    is_fallback=is_fallback,
                )
            except Exception as exc:
                err_msg = format_exc(exc)
                logger.error(f"[ai_iq] 获取远程模型数据失败 ({prefer}): {err_msg}")
                fallback = mem or disk_cache
                if fallback is not None:
                    return FetchResult(
                        models=fallback[0],
                        fetched_at=fallback[1],
                        source=fallback[2],
                        from_cache=True,
                        is_stale=True,
                        error=err_msg,
                    )
                raise
