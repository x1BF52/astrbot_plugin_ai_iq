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
_TRIGGERS = ("aiiq", "模型智商")
_FREE_KEYWORDS = {"free", "免费", "白嫖"}

HELP_TEXT = """AI 模型实时智商榜 - 使用说明
• /aiiq — 主流厂商（Claude / GPT / Gemini / DeepSeek / Qwen / GLM / Kimi / Grok）最新在役模型与各推理强度卡片图
• /aiiq <厂商/关键词> — 查看该厂商全部在役系列及推理强度，如：/aiiq gemini、/aiiq deepseek、/aiiq gpt、/aiiq claude
• /aiiq <推理强度> — 按推理强度筛选，如：/aiiq max、/aiiq high、/aiiq gemini high、/aiiq deepseek max
• /aiiq 编程 — 按编程评测综合分 (Coding) 排序
• /aiiq 性价比 — 按「智商 ÷ 题均成本/单价」排序推荐
• /aiiq 免费 — 查看 $0 免费模型智商榜
• /aiiq 全部 <关键词> — 临时关闭过期过滤，查看包含旧代模型的完整列表
• /aiiq 刷新 — 忽略缓存，强制拉取最新数据

卡片说明：左下大字为 AA 智商分，型号下方为推理强度（max/xhigh/high/medium/low/无推理），右上为 API 单价 ($/1M) 与题均成本，右下为「输出速度 · 首答延迟」。"""


class AIIQPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig | dict | None = None):
        super().__init__(context)
        self.config = config if config is not None else {}
        cache_dir = self._resolve_data_dir()
        ttl_minutes = int(self.config.get("cache_ttl_minutes", 15))
        timeout_seconds = int(self.config.get("request_timeout", 25))
        proxy = str(self.config.get("proxy", "") or "")
        data_source = str(self.config.get("data_source", "auto") or "auto")
        self.fetcher = ModelDataFetcher(
            cache_file=cache_dir / "models_cache.json",
            ttl_seconds=ttl_minutes * 60,
            timeout_seconds=timeout_seconds,
            proxy=proxy,
            data_source=data_source,
        )
        logger.info(
            f"[ai_iq] 插件已加载，数据源: {data_source}，缓存目录: {cache_dir}"
        )

    def _resolve_data_dir(self) -> Path:
        if StarTools is not None:
            try:
                return Path(StarTools.get_data_dir("astrbot_plugin_ai_iq"))
            except Exception:
                pass
        return Path(__file__).resolve().parent / "data"

    def _get_default_makers(self) -> list[str]:
        raw = str(
            self.config.get(
                "default_makers",
                "anthropic,openai,google,deepseek,qwen,z-ai,moonshotai,x-ai",
            )
        )
        return [item.strip().lower() for item in raw.split(",") if item.strip()]

    @filter.command("aiiq", alias={"模型智商"})
    async def cmd_aiiq(self, event: AstrMessageEvent, query: GreedyStr = ""):
        """查询全球主流 AI 模型实时智商、推理强度、价格与速度延迟"""
        async for res in self._run_query(event, str(query or "")):
            yield res

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def fallback_aiiq(self, event: AstrMessageEvent):
        """兜底匹配：消息带 [MSG_ID:...] 等后缀导致 /aiiq 指令未命中时仍能触发"""
        raw = event.get_message_str() or ""
        if "aiiq" not in raw.lower() and "模型智商" not in raw:
            return
        for handler in event.get_extra("activated_handlers") or []:
            if getattr(handler, "handler_name", "") == "cmd_aiiq":
                return
        if not event.is_at_or_wake_command and not raw.lstrip().startswith(("/", "／")):
            return
        arg = self._extract_query(raw)
        if arg is None:
            return
        logger.info(f"[ai_iq] 兜底监听命中，原始消息: {raw!r}")
        event.stop_event()
        async for res in self._run_query(event, arg):
            yield res

    @staticmethod
    def _extract_query(raw: str) -> str | None:
        text = _MSG_ID_PATTERN.sub("", raw).strip().lstrip("/／").strip()
        lowered = text.lower()
        for trigger in _TRIGGERS:
            if lowered == trigger:
                return ""
            if lowered.startswith(trigger) and text[len(trigger)] in " \t\n[":
                return _MSG_ID_PATTERN.sub("", text[len(trigger) :]).strip()
        return None

    async def _run_query(self, event: AstrMessageEvent, arg: str):
        arg = _MSG_ID_PATTERN.sub("", arg).strip()
        logger.info(f"[ai_iq] 收到查询: {arg!r}")

        if arg.lower() in {"help", "帮助", "-h", "?"}:
            yield event.plain_result(HELP_TEXT)
            return

        force_refresh = False
        if arg.lower() in {"refresh", "刷新"}:
            force_refresh = True
            arg = ""
        elif arg.lower().startswith("refresh ") or arg.startswith("刷新 "):
            force_refresh = True
            arg = arg.split(maxsplit=1)[1].strip()

        # Free $0 models come from OpenRouter via modelgrep
        tokens_lower = {t.lower() for t in arg.split() if t}
        source_override = "modelgrep" if (tokens_lower & _FREE_KEYWORDS) else None

        try:
            result = await self.fetcher.get_models(
                force_refresh=force_refresh,
                source_override=source_override,
            )
        except Exception as exc:
            logger.error(f"[ai_iq] 拉取模型数据异常: {exc}")
            yield event.plain_result(f"获取实时模型智商数据失败：{exc}")
            return

        max_per_maker = max(1, int(self.config.get("max_per_maker", 6)))
        max_ranking_items = max(6, int(self.config.get("max_ranking_items", 24)))
        filter_outdated = bool(self.config.get("filter_outdated", True))
        max_model_age_days = max(0, int(self.config.get("max_model_age_days", 180)))
        max_releases_per_maker = max(
            1, int(self.config.get("max_releases_per_maker", 4))
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
            filter_outdated=filter_outdated,
            max_model_age_days=max_model_age_days,
            max_releases_per_maker=max_releases_per_maker,
        )

        if view_data["total_cards"] == 0:
            yield event.plain_result(
                f"未找到与「{arg}」匹配的在役带跑分模型，试试 `/aiiq gemini`、`/aiiq deepseek`、`/aiiq 全部 {arg}` 或 `/aiiq` 查看总览。"
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
