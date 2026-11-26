from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp

from astrbot.api import logger


AA_LEADERBOARD_URL = "https://artificialanalysis.ai/leaderboards/models"
AA_API_URL = "https://artificialanalysis.ai/api/v2/data/llms/models"
MODELGREP_API_URL = "https://modelgrep.com/api/v1/models"

CACHE_SCHEMA_VERSION = 3

_NEXT_RSC_CHUNK_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', re.S)
_PAREN_SUFFIX_RE = re.compile(r"^(.*?)\s*\(([^()]+)\)\s*$")

_AA_CREATOR_MAP: dict[str, str] = {
    "anthropic": "anthropic",
    "openai": "openai",
    "google": "google",
    "deepseek": "deepseek",
    "alibaba": "qwen",
    "qwen": "qwen",
    "z ai": "z-ai",
    "z.ai": "z-ai",
    "zhipu": "z-ai",
    "kimi": "moonshotai",
    "moonshot ai": "moonshotai",
    "moonshotai": "moonshotai",
    "xai": "x-ai",
    "spacexai": "x-ai",
    "spacexsi": "x-ai",
    "meta": "meta",
    "mistral": "mistralai",
    "mistral ai": "mistralai",
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


def _parse_iso_date_ts(date_str: str | None) -> float | None:
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


def _normalize_aa_creator(creator_name: str | None) -> str:
    key = (creator_name or "").strip().lower()
    if key in _AA_CREATOR_MAP:
        return _AA_CREATOR_MAP[key]
    return re.sub(r"[^a-z0-9-]+", "-", key).strip("-") or "other"


def parse_aa_leaderboard_html(html: str) -> list[dict[str, Any]]:
    """Extract normalized model-effort records from Artificial Analysis leaderboard SSR HTML."""
    chunks = _NEXT_RSC_CHUNK_RE.findall(html)
    if not chunks:
        raise RuntimeError("Artificial Analysis 页面中未找到 Next.js 数据块")

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
        iq = item.get("intelligenceIndex")
        scores = item.get("scores") if isinstance(item.get("scores"), dict) else {}

        # Derive a 0-100 coding composite from AA's FrontierCode 2.0 & Terminal-Bench 4.1
        fc2 = scores.get("frontiercode-2-0")
        tb41 = scores.get("terminalbench-4-1")
        coding_vals = [float(v) for v in (fc2, tb41) if isinstance(v, (int, float))]
        coding = round(sum(coding_vals) / len(coding_vals) * 100.0, 2) if coding_vals else None

        if iq is None and coding is None:
            continue

        rel_obj = item.get("release") if isinstance(item.get("release"), dict) else {}
        rel_slug = str(rel_obj.get("slug") or item.get("id") or "").strip()
        rel_name = str(rel_obj.get("name") or item.get("shortName") or item.get("name") or "").strip()
        # Strip trailing "(...)" from release_name if fallback came from full name
        if not rel_obj.get("name") and "(" in rel_name:
            rel_name = re.sub(r"\s*\([^)]*\)\s*$", "", rel_name).strip()

        rmeta = release_meta.get(rel_slug, {})
        release_date = rmeta.get("releaseDate")
        deprecated = bool(item.get("deprecated")) or bool(rmeta.get("deprecated"))
        is_reasoning = item.get("isReasoning")
        effort, effort_label = normalize_effort(item.get("suffix"), is_reasoning)
        maker = _normalize_aa_creator(item.get("modelCreatorName"))

        latency_s = item.get("timeToFirstAnswerToken")
        if latency_s is None:
            latency_s = item.get("timeToFirstToken")

        normalized.append(
            {
                "id": str(item.get("id") or f"{rel_slug}:{effort}"),
                "release_slug": rel_slug,
                "release_name": rel_name,
                "name": str(item.get("shortName") or item.get("name") or rel_name),
                "effort": effort,
                "effort_label": effort_label,
                "maker": maker,
                "release_date": release_date,
                "created_ts": _parse_iso_date_ts(release_date),
                "deprecated": deprecated,
                "is_reasoning": bool(is_reasoning),
                "iq": float(iq) if isinstance(iq, (int, float)) else None,
                "coding": coding,
                "price_in": float(item["price1mInputTokens"])
                if isinstance(item.get("price1mInputTokens"), (int, float))
                else None,
                "price_out": float(item["price1mOutputTokens"])
                if isinstance(item.get("price1mOutputTokens"), (int, float))
                else None,
                "cost_per_task": float(item["intelligenceIndexCostPerTask"])
                if isinstance(item.get("intelligenceIndexCostPerTask"), (int, float))
                else None,
                "time_per_task": float(item["intelligenceIndexTimePerTask"])
                if isinstance(item.get("intelligenceIndexTimePerTask"), (int, float))
                else None,
                "tps": float(item["outputSpeed"])
                if isinstance(item.get("outputSpeed"), (int, float))
                else None,
                "latency_s": float(latency_s)
                if isinstance(latency_s, (int, float))
                else None,
                "source": "artificial_analysis",
            }
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
        iq = aa.get("intelligence")
        coding = aa.get("coding")
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
        lat_ms = perf.get("latency_ms")
        created_ts = float(m["created"]) if isinstance(m.get("created"), (int, float)) else None
        release_date = (
            datetime.fromtimestamp(created_ts, tz=timezone.utc).strftime("%Y-%m-%d")
            if created_ts
            else None
        )

        normalized.append(
            {
                "id": mid,
                "release_slug": rel_slug,
                "release_name": raw_name,
                "name": raw_name,
                "effort": effort,
                "effort_label": effort_label,
                "maker": str(m.get("maker") or "other").lower(),
                "release_date": release_date,
                "created_ts": created_ts,
                "deprecated": False,
                "is_reasoning": bool(is_reasoning),
                "iq": float(iq) if isinstance(iq, (int, float)) else None,
                "coding": float(coding) if isinstance(coding, (int, float)) else None,
                "price_in": float(pricing["input"])
                if isinstance(pricing.get("input"), (int, float))
                else None,
                "price_out": float(pricing["output"])
                if isinstance(pricing.get("output"), (int, float))
                else None,
                "cost_per_task": None,
                "time_per_task": None,
                "tps": float(perf["throughput_tps"])
                if isinstance(perf.get("throughput_tps"), (int, float))
                else None,
                "latency_s": float(lat_ms) / 1000.0
                if isinstance(lat_ms, (int, float))
                else None,
                "source": "modelgrep",
            }
        )
    return normalized


def normalize_aa_api_models(raw_models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize Artificial Analysis official v2 API records into the unified schema."""
    normalized: list[dict[str, Any]] = []
    for item in raw_models:
        if not isinstance(item, dict):
            continue
        evals = item.get("evaluations") if isinstance(item.get("evaluations"), dict) else {}
        iq = evals.get("artificial_analysis_intelligence_index")
        coding = evals.get("artificial_analysis_coding_index")
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
                if any(
                    k in c_low
                    for k in (
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
                ):
                    base_name = m_paren.group(1).strip()
                    suffix = candidate

        creator_obj = (
            item.get("model_creator") if isinstance(item.get("model_creator"), dict) else {}
        )
        maker = _normalize_aa_creator(
            creator_obj.get("name") or creator_obj.get("slug") or item.get("maker")
        )
        rel_slug = re.sub(r"[^a-z0-9.+-]+", "-", base_name.lower()).strip("-") or str(
            item.get("slug") or item.get("id") or ""
        )
        is_reasoning = item.get("reasoning_model")
        effort, effort_label = normalize_effort(suffix, is_reasoning)

        pricing = item.get("pricing") if isinstance(item.get("pricing"), dict) else {}
        pin = pricing.get("price_1m_input_tokens")
        pout = pricing.get("price_1m_output_tokens")

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
        cost_per_task = cpt_obj.get("total_cost")

        perf_v3 = (
            item.get("performance_v3")
            if isinstance(item.get("performance_v3"), dict)
            else {}
        )
        tps = item.get("median_output_tokens_per_second")
        if tps is None:
            tps = perf_v3.get("mean_output_tokens_per_second") or perf_v3.get(
                "median_output_tokens_per_second"
            )
        latency_s = item.get("median_time_to_first_answer_token")
        if latency_s is None:
            latency_s = item.get("median_time_to_first_token_seconds")
        if latency_s is None:
            latency_s = perf_v3.get("mean_time_to_first_answer_token_seconds") or perf_v3.get(
                "mean_time_to_first_token_seconds"
            )
        time_per_task = perf_v3.get("time_per_task_seconds")

        release_date = item.get("release_date")
        normalized.append(
            {
                "id": str(item.get("id") or item.get("slug") or f"{rel_slug}:{effort}"),
                "release_slug": rel_slug,
                "release_name": base_name,
                "name": raw_name,
                "effort": effort,
                "effort_label": effort_label,
                "maker": maker,
                "release_date": release_date,
                "created_ts": _parse_iso_date_ts(release_date),
                "deprecated": bool(item.get("deprecated")),
                "is_reasoning": bool(is_reasoning) if is_reasoning is not None else (effort != "non-reasoning"),
                "iq": float(iq) if isinstance(iq, (int, float)) else None,
                "coding": float(coding) if isinstance(coding, (int, float)) else None,
                "price_in": float(pin) if isinstance(pin, (int, float)) else None,
                "price_out": float(pout) if isinstance(pout, (int, float)) else None,
                "cost_per_task": float(cost_per_task)
                if isinstance(cost_per_task, (int, float))
                else None,
                "time_per_task": float(time_per_task)
                if isinstance(time_per_task, (int, float))
                else None,
                "tps": float(tps) if isinstance(tps, (int, float)) else None,
                "latency_s": float(latency_s)
                if isinstance(latency_s, (int, float))
                else None,
                "source": "artificial_analysis_api",
            }
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

    # Already normalized schema
    if "release_slug" in sample and "effort" in sample:
        return items
    # Artificial Analysis v2 API format
    if "evaluations" in sample or "model_creator" in sample:
        return normalize_aa_api_models(items)
    # modelgrep format
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
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
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
            logger.warning(f"[ai_iq] 读取本地缓存失败 ({bucket}): {exc}")
        return None

    def _save_disk_cache(
        self, bucket: str, models: list[dict[str, Any]], fetched_at: float, source: str
    ) -> None:
        path = self._cache_path_for(bucket)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": CACHE_SCHEMA_VERSION,
                "source": source,
                "fetched_at": fetched_at,
                "models": models,
            }
            path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning(f"[ai_iq] 写入本地缓存失败 ({bucket}): {exc}")

    async def _fetch_aa_api(self) -> list[dict[str, Any]]:
        session = await self._get_session()
        headers = {
            "Accept": "application/json",
            "x-api-key": self.aa_api_key,
        }
        async with session.get(
            AA_API_URL,
            proxy=self.proxy,
            headers=headers,
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Artificial Analysis API 返回状态码 {resp.status}")
            body = await resp.json()
        items = body.get("data") if isinstance(body, dict) else body
        if not isinstance(items, list) or not items:
            raise RuntimeError("Artificial Analysis API 返回了空的模型列表")
        normalized = normalize_aa_api_models(items)
        if not normalized:
            raise RuntimeError("Artificial Analysis API 未包含带跑分模型")
        return normalized

    async def _fetch_custom_api(self) -> list[dict[str, Any]]:
        session = await self._get_session()
        headers: dict[str, str] = {"Accept": "application/json, text/html"}
        if self.aa_api_key:
            headers["x-api-key"] = self.aa_api_key
            headers["Authorization"] = f"Bearer {self.aa_api_key}"
        async with session.get(
            self.custom_api_url,
            proxy=self.proxy,
            headers=headers,
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"自定义 API 返回状态码 {resp.status}")
            text = await resp.text()
        return parse_custom_api_response(text)

    async def _fetch_artificial_analysis(self) -> tuple[list[dict[str, Any]], str]:
        if self.aa_api_key:
            try:
                return await self._fetch_aa_api(), "artificial_analysis_api"
            except Exception as api_exc:
                logger.warning(
                    f"[ai_iq] Artificial Analysis 官方 API 拉取失败，尝试公开榜单页: {api_exc}"
                )
        session = await self._get_session()
        async with session.get(
            AA_LEADERBOARD_URL,
            proxy=self.proxy,
            headers={"Accept": "text/html,application/xhtml+xml"},
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Artificial Analysis 返回状态码 {resp.status}")
            html = await resp.text()
        return parse_aa_leaderboard_html(html), "artificial_analysis"

    async def _fetch_modelgrep(self) -> list[dict[str, Any]]:
        session = await self._get_session()
        all_models: list[dict[str, Any]] = []
        offset = 0
        limit = 200

        for _ in range(5):
            params = {
                "benchmarked": "1",
                "sort": "intelligence",
                "limit": str(limit),
                "offset": str(offset),
            }
            async with session.get(
                MODELGREP_API_URL,
                params=params,
                proxy=self.proxy,
                headers={"Accept": "application/json"},
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"modelgrep 返回状态码 {resp.status}")
                body = await resp.json()

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

    async def _fetch_remote(
        self, prefer_source: str, *, allow_custom: bool = True
    ) -> tuple[list[dict[str, Any]], str, bool]:
        """Returns (models, actual_source, is_fallback)."""
        if prefer_source == "modelgrep":
            return await self._fetch_modelgrep(), "modelgrep", False

        if allow_custom and self.custom_api_url:
            try:
                return await self._fetch_custom_api(), "custom_api", False
            except Exception as custom_exc:
                if prefer_source != "auto":
                    raise
                logger.warning(
                    f"[ai_iq] 自定义 API 拉取失败，回退内置主源: {custom_exc}"
                )

        if prefer_source == "artificial_analysis":
            models, src = await self._fetch_artificial_analysis()
            return models, src, False

        # auto: try Artificial Analysis first (has reasoning effort breakdown),
        # temporarily fallback to modelgrep if AA is unreachable (do NOT poison cache).
        try:
            models, src = await self._fetch_artificial_analysis()
            return models, src, False
        except Exception as aa_exc:
            logger.warning(
                f"[ai_iq] Artificial Analysis 拉取失败，临时回退 modelgrep（不写入缓存）: {aa_exc}"
            )
            models = await self._fetch_modelgrep()
            return models, "modelgrep", True

    @staticmethod
    def _is_degraded_cache(prefer: str, cached_source: str) -> bool:
        return prefer == "auto" and cached_source == "modelgrep"

    async def get_models(
        self, force_refresh: bool = False, source_override: str | None = None
    ) -> FetchResult:
        prefer = (source_override or self.data_source or "auto").strip().lower()
        bucket = "primary" if source_override is None else prefer
        now = time.time()

        mem = self._mem_cache.get(bucket)
        if (
            not force_refresh
            and mem
            and (now - mem[1]) < self.ttl_seconds
            and not self._is_degraded_cache(prefer, mem[2])
        ):
            return FetchResult(
                models=mem[0],
                fetched_at=mem[1],
                source=mem[2],
                from_cache=True,
            )

        async with self._lock:
            now = time.time()
            mem = self._mem_cache.get(bucket)
            if (
                not force_refresh
                and mem
                and (now - mem[1]) < self.ttl_seconds
                and not self._is_degraded_cache(prefer, mem[2])
            ):
                return FetchResult(
                    models=mem[0],
                    fetched_at=mem[1],
                    source=mem[2],
                    from_cache=True,
                )

            disk_cache = self._load_disk_cache(bucket)
            if (
                not force_refresh
                and disk_cache is not None
                and (now - disk_cache[1]) < self.ttl_seconds
                and not self._is_degraded_cache(prefer, disk_cache[2])
            ):
                self._mem_cache[bucket] = disk_cache
                return FetchResult(
                    models=disk_cache[0],
                    fetched_at=disk_cache[1],
                    source=disk_cache[2],
                    from_cache=True,
                )

            try:
                models, actual_source, is_fallback = await self._fetch_remote(
                    prefer, allow_custom=(source_override is None)
                )
                fetched_at = time.time()
                # Only persist non-fallback primary data; never poison cache with degraded fallback
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
                logger.error(f"[ai_iq] 获取远程模型数据失败 ({prefer}): {exc}")
                fallback = mem or disk_cache
                if fallback is not None:
                    return FetchResult(
                        models=fallback[0],
                        fetched_at=fallback[1],
                        source=fallback[2],
                        from_cache=True,
                        is_stale=True,
                        error=str(exc),
                    )
                raise
