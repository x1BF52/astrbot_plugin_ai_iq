from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp

try:
    from astrbot.api import logger
except ImportError:  # pragma: no cover - local test fallback
    import logging

    logger = logging.getLogger("astrbot_plugin_ai_iq")


MODELGREP_API_URL = "https://modelgrep.com/api/v1/models"


@dataclass
class FetchResult:
    models: list[dict[str, Any]]
    fetched_at: float
    from_cache: bool = False
    is_stale: bool = False
    error: str | None = None


class ModelDataFetcher:
    """Fetches and caches realtime LLM benchmark, pricing, and speed data."""

    def __init__(
        self,
        cache_file: Path,
        ttl_seconds: int = 900,
        timeout_seconds: int = 20,
        proxy: str = "",
    ) -> None:
        self.cache_file = cache_file
        self.ttl_seconds = max(60, ttl_seconds)
        self.timeout_seconds = max(5, timeout_seconds)
        self.proxy = proxy.strip() or None
        self._lock = asyncio.Lock()
        self._session: aiohttp.ClientSession | None = None
        self._mem_models: list[dict[str, Any]] | None = None
        self._mem_fetched_at: float = 0.0

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            headers = {
                "User-Agent": "AstrBot-Plugin-AI-IQ/1.0 (+https://github.com/x1BF52/astrbot_plugin_ai_iq)",
                "Accept": "application/json",
            }
            self._session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    def _load_disk_cache(self) -> tuple[list[dict[str, Any]], float] | None:
        if not self.cache_file.exists():
            return None
        try:
            raw = json.loads(self.cache_file.read_text(encoding="utf-8"))
            models = raw.get("models")
            fetched_at = float(raw.get("fetched_at", 0.0))
            if isinstance(models, list) and models and fetched_at > 0:
                return models, fetched_at
        except Exception as exc:
            logger.warning(f"[ai_iq] 读取本地缓存失败: {exc}")
        return None

    def _save_disk_cache(self, models: list[dict[str, Any]], fetched_at: float) -> None:
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {"fetched_at": fetched_at, "models": models}
            self.cache_file.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning(f"[ai_iq] 写入本地缓存失败: {exc}")

    async def _fetch_remote(self) -> list[dict[str, Any]]:
        session = await self._get_session()
        all_models: list[dict[str, Any]] = []
        offset = 0
        limit = 200

        # Paginate safely (capped at 5 pages = 1000 models)
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
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"上游接口返回状态码 {resp.status}")
                body = await resp.json()

            batch = body.get("data") or []
            all_models.extend(batch)
            meta = body.get("meta") or {}
            if not meta.get("has_more") or not batch:
                break
            next_offset = meta.get("next_offset")
            offset = int(next_offset) if next_offset is not None else offset + len(batch)

        if not all_models:
            raise RuntimeError("上游接口返回了空的模型列表")
        return all_models

    async def get_models(self, force_refresh: bool = False) -> FetchResult:
        now = time.time()

        # Fast path: valid in-memory cache
        if (
            not force_refresh
            and self._mem_models
            and (now - self._mem_fetched_at) < self.ttl_seconds
        ):
            return FetchResult(
                models=self._mem_models,
                fetched_at=self._mem_fetched_at,
                from_cache=True,
            )

        async with self._lock:
            now = time.time()
            if (
                not force_refresh
                and self._mem_models
                and (now - self._mem_fetched_at) < self.ttl_seconds
            ):
                return FetchResult(
                    models=self._mem_models,
                    fetched_at=self._mem_fetched_at,
                    from_cache=True,
                )

            # Check disk cache before hitting network
            disk_cache = self._load_disk_cache()
            if (
                not force_refresh
                and disk_cache is not None
                and (now - disk_cache[1]) < self.ttl_seconds
            ):
                self._mem_models, self._mem_fetched_at = disk_cache
                return FetchResult(
                    models=self._mem_models,
                    fetched_at=self._mem_fetched_at,
                    from_cache=True,
                )

            try:
                models = await self._fetch_remote()
                fetched_at = time.time()
                self._mem_models = models
                self._mem_fetched_at = fetched_at
                self._save_disk_cache(models, fetched_at)
                return FetchResult(
                    models=models,
                    fetched_at=fetched_at,
                    from_cache=False,
                )
            except Exception as exc:
                logger.error(f"[ai_iq] 获取远程模型数据失败: {exc}")
                fallback = (
                    (self._mem_models, self._mem_fetched_at)
                    if self._mem_models
                    else disk_cache
                )
                if fallback is not None:
                    return FetchResult(
                        models=fallback[0],
                        fetched_at=fallback[1],
                        from_cache=True,
                        is_stale=True,
                        error=str(exc),
                    )
                raise
