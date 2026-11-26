from pathlib import Path
import re

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.star.filter.command import GreedyStr

try:
    from astrbot.api.star import StarTools
except ImportError:  # pragma: no cover
    StarTools = None  # type: ignore[assignment]

from .fetcher import ModelDataFetcher
from .renderer import HTML_TEMPLATE, build_view_data, format_text_fallback

_MSG_ID_PATTERN = re.compile(r"\s*\[MSG_ID:[^\]]*\]\s*")
_TRIGGER_SPLIT_RE = re.compile(r"[,，、;；\n]+")
_FREE_KEYWORDS = {"free", "免费", "白嫖"}
_GECKO_KEYWORDS = {"gecko", "benchgecko", "硬核", "多榜"}


def _build_help_text(primary_cmd: str, all_triggers: tuple[str, ...]) -> str:
    alias_hint = (
        f"（已启用唤醒词：{' / '.join(all_triggers)}）"
        if len(all_triggers) > 1
        else ""
    )
    return (
        f"AI 模型实时智商榜 - 使用说明{alias_hint}\n"
        f"• /{primary_cmd} — 主流厂商（Claude / GPT / Gemini / DeepSeek / Qwen / GLM / Kimi / Grok）最新在役模型与各推理强度看板\n"
        f"• /{primary_cmd} <厂商/关键词> — 查看该厂商全部在役系列及推理强度，如：/{primary_cmd} gemini、/{primary_cmd} deepseek\n"
        f"• /{primary_cmd} <推理强度> — 按推理强度筛选，如：/{primary_cmd} max、/{primary_cmd} high、/{primary_cmd} gemini high\n"
        f"• /{primary_cmd} 编程 — 按编程评测综合分 (Coding) 排序\n"
        f"• /{primary_cmd} 性价比 — 按「智商 ÷ 题均成本/单价」排序推荐\n"
        f"• /{primary_cmd} 硬核 — BenchGecko 多榜综合分（ARC-AGI-2 / FrontierMath / FrontierSWE / GPQA），也可用 /{primary_cmd} gecko\n"
        f"• /{primary_cmd} 免费 — 查看 $0 免费模型智商榜\n"
        f"• /{primary_cmd} 全部 <关键词> — 临时关闭过期与无推理过滤，查看完整列表\n"
        f"• /{primary_cmd} 刷新 — 忽略缓存，强制拉取最新数据\n\n"
        f"看板说明：大字为 AA 智商分，格内右上为评测题均成本 ($)，左侧为 API 单价 ($/1M)，底部为「输出速度 · 首答延迟」。"
    )


class AIIQPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig | dict | None = None):
        super().__init__(context)
        self.config = config if config is not None else {}
        cache_dir = self._resolve_data_dir()
        ttl_minutes = int(self.config.get("cache_ttl_minutes", 15))
        timeout_seconds = int(self.config.get("request_timeout", 25))
        proxy = str(self.config.get("proxy", "") or "")
        data_source = str(self.config.get("data_source", "auto") or "auto")
        aa_api_key = str(self.config.get("aa_api_key", "") or "")
        custom_api_url = str(self.config.get("custom_api_url", "") or "")
        self.fetcher = ModelDataFetcher(
            cache_file=cache_dir / "models_cache.json",
            ttl_seconds=ttl_minutes * 60,
            timeout_seconds=timeout_seconds,
            proxy=proxy,
            data_source=data_source,
            aa_api_key=aa_api_key,
            custom_api_url=custom_api_url,
        )
        triggers = self._get_trigger_keywords()
        logger.info(
            f"[ai_iq] 插件已加载，唤醒词: {triggers}，数据源: {data_source}，"
            f"AA Key: {'已配置' if aa_api_key.strip() else '未配置'}，"
            f"自定义 API: {'已配置' if custom_api_url.strip() else '未配置'}"
        )

    def _resolve_data_dir(self) -> Path:
        if StarTools is not None:
            try:
                return Path(StarTools.get_data_dir("astrbot_plugin_ai_iq"))
            except Exception:
                pass
        return Path(__file__).resolve().parent / "data"

    def _get_default_makers(self) -> list[str]:
        makers: list[str] = []
        seen: set[str] = set()

        def _add(item: str) -> None:
            key = item.strip().lower()
            if key and key not in seen:
                seen.add(key)
                makers.append(key)

        selected = self.config.get("selected_makers")
        if isinstance(selected, list):
            for item in selected:
                _add(str(item))
        elif isinstance(selected, str) and selected.strip():
            for part in _TRIGGER_SPLIT_RE.split(selected):
                _add(part)
        else:
            # Backwards compatibility with older default_makers string config
            legacy = str(
                self.config.get(
                    "default_makers",
                    "anthropic,openai,google,deepseek,qwen,z-ai,moonshotai,x-ai",
                )
            )
            for part in _TRIGGER_SPLIT_RE.split(legacy):
                _add(part)

        custom = str(self.config.get("custom_makers", "") or "")
        if custom.strip():
            for part in _TRIGGER_SPLIT_RE.split(custom):
                _add(part)

        return makers or [
            "anthropic",
            "openai",
            "google",
            "deepseek",
            "qwen",
            "z-ai",
            "moonshotai",
            "x-ai",
        ]

    def _get_trigger_keywords(self) -> tuple[str, ...]:
        raw = str(self.config.get("trigger_keywords", "aiiq") or "aiiq")
        seen: set[str] = set()
        items: list[str] = []
        for part in _TRIGGER_SPLIT_RE.split(raw):
            kw = part.strip().lstrip("/／").strip().lower()
            if kw and kw not in seen:
                seen.add(kw)
                items.append(kw)
        if not items:
            return ("aiiq",)
        # Sort longer triggers first so prefix matching never shadows longer keywords
        items.sort(key=len, reverse=True)
        return tuple(items)

    @filter.command("aiiq")
    async def cmd_aiiq(self, event: AstrMessageEvent, query: GreedyStr = ""):
        """查询全球主流 AI 模型实时智商、推理强度、价格与速度延迟"""
        if "aiiq" not in self._get_trigger_keywords():
            return
        async for res in self._run_query(event, str(query or "")):
            yield res

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_trigger_message(self, event: AstrMessageEvent):
        """支持自定义唤醒词，并兜底处理带 [MSG_ID:...] 等平台后缀的指令"""
        raw = event.get_message_str() or ""
        if not raw.strip():
            return
        triggers = self._get_trigger_keywords()
        raw_lower = raw.lower()
        if not any(t in raw_lower for t in triggers):
            return
        for handler in event.get_extra("activated_handlers") or []:
            if getattr(handler, "handler_name", "") == "cmd_aiiq":
                return
        if not event.is_at_or_wake_command and not raw.lstrip().startswith(("/", "／")):
            return
        arg = self._extract_query(raw, triggers)
        if arg is None:
            return
        logger.info(f"[ai_iq] 唤醒词监听命中，原始消息: {raw!r}")
        event.stop_event()
        async for res in self._run_query(event, arg):
            yield res

    @staticmethod
    def _extract_query(raw: str, triggers: tuple[str, ...]) -> str | None:
        text = _MSG_ID_PATTERN.sub("", raw).strip().lstrip("/／").strip()
        lowered = text.lower()
        for trigger in triggers:
            if lowered == trigger:
                return ""
            if lowered.startswith(trigger) and text[len(trigger)] in " \t\n[":
                return _MSG_ID_PATTERN.sub("", text[len(trigger) :]).strip()
        return None

    async def _run_query(self, event: AstrMessageEvent, arg: str):
        arg = _MSG_ID_PATTERN.sub("", arg).strip()
        logger.info(f"[ai_iq] 收到查询: {arg!r}")

        triggers = self._get_trigger_keywords()
        primary_cmd = triggers[-1] if "aiiq" not in triggers else "aiiq"

        if arg.lower() in {"help", "帮助", "-h", "?"}:
            yield event.plain_result(_build_help_text(primary_cmd, triggers))
            return

        force_refresh = False
        if arg.lower() in {"refresh", "刷新"}:
            force_refresh = True
            arg = ""
        elif arg.lower().startswith("refresh ") or arg.startswith("刷新 "):
            force_refresh = True
            arg = arg.split(maxsplit=1)[1].strip()

        # Route special commands to dedicated upstream sources
        tokens = [t for t in arg.split() if t]
        tokens_lower = {t.lower() for t in tokens}
        source_override: str | None = None
        if tokens_lower & _FREE_KEYWORDS:
            source_override = "modelgrep"
        elif tokens_lower & _GECKO_KEYWORDS:
            source_override = "benchgecko"
            remaining = [t for t in tokens if t.lower() not in _GECKO_KEYWORDS]
            arg = " ".join(remaining).strip()

        try:
            result = await self.fetcher.get_models(
                force_refresh=force_refresh,
                source_override=source_override,
            )
        except Exception as exc:
            err_msg = (
                f"{type(exc).__name__}: {exc}"
                if str(exc).strip()
                else type(exc).__name__
            )
            logger.error(f"[ai_iq] 拉取模型数据异常: {err_msg}")
            yield event.plain_result(f"获取实时模型智商数据失败：{err_msg}")
            return

        max_per_maker = max(1, int(self.config.get("max_per_maker", 5)))
        max_ranking_items = max(6, int(self.config.get("max_ranking_items", 24)))
        filter_outdated = bool(self.config.get("filter_outdated", True))
        hide_non_reasoning = bool(self.config.get("hide_non_reasoning", True))
        max_model_age_days = max(0, int(self.config.get("max_model_age_days", 180)))
        max_releases_per_maker = max(
            1, int(self.config.get("max_series_per_maker", 5))
        )

        view_data = build_view_data(
            models=result.models,
            query=arg,
            default_makers=self._get_default_makers(),
            max_per_maker=max_per_maker,
            max_ranking_items=max_ranking_items,
            fetched_at=result.fetched_at,
            source=result.source,
            is_stale=result.is_stale,
            is_fallback=result.is_fallback,
            filter_outdated=filter_outdated,
            hide_non_reasoning=hide_non_reasoning,
            max_model_age_days=max_model_age_days,
            max_releases_per_maker=max_releases_per_maker,
        )

        if view_data["total_cards"] == 0:
            yield event.plain_result(
                f"未找到与「{arg}」匹配的在役带跑分模型，试试 `/{primary_cmd} gemini`、`/{primary_cmd} deepseek`、`/{primary_cmd} 全部 {arg}` 或 `/{primary_cmd}` 查看总览。"
            )
            return

        try:
            img_url = await self.html_render(
                HTML_TEMPLATE,
                view_data,
                options={
                    "type": "png",
                    "full_page": True,
                    "scale": "device",
                },
            )
            yield event.image_result(img_url)
        except Exception as exc:
            logger.warning(f"[ai_iq] HTML 渲染图片失败，降级为文本输出: {exc}")
            yield event.plain_result(format_text_fallback(view_data))

    async def terminate(self):
        await self.fetcher.close()
