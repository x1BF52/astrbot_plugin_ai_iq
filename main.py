from __future__ import annotations

from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

try:
    from astrbot.api.star import StarTools
except ImportError:  # pragma: no cover
    StarTools = None  # type: ignore[assignment]

from .fetcher import ModelDataFetcher
from .renderer import HTML_TEMPLATE, build_view_data, format_text_fallback

HELP_TEXT = """AI 模型实时智商榜 - 使用说明
• /aiiq — 查看主流厂商（Claude / GPT / Gemini / DeepSeek / Qwen / GLM / Kimi / Grok）分组卡片图
• /aiiq <厂商/关键词> — 筛选特定厂商或模型，如：/aiiq gemini、/aiiq deepseek、/aiiq gpt、/aiiq claude
• /aiiq 编程 — 按编程跑分 (Coding) 排序
• /aiiq 性价比 — 按「智商 ÷ 综合单价」排序推荐
• /aiiq 免费 — 查看 $0 免费模型智商榜
• /aiiq 刷新 — 强制拉取最新数据（忽略缓存）

卡片说明：左下大字为 AA 智商分，右上为 $/1M Tokens（输入/输出），右下为「输出速度 · 首字延迟」。"""


class AIIQPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.config = config or {}
        cache_dir = self._resolve_data_dir()
        ttl_minutes = int(self.config.get("cache_ttl_minutes", 15))
        timeout_seconds = int(self.config.get("request_timeout", 20))
        proxy = str(self.config.get("proxy", "") or "")
        self.fetcher = ModelDataFetcher(
            cache_file=cache_dir / "models_cache.json",
            ttl_seconds=ttl_minutes * 60,
            timeout_seconds=timeout_seconds,
            proxy=proxy,
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

    @filter.command("aiiq", alias={"iq", "模型智商"})
    async def cmd_aiiq(self, event: AstrMessageEvent):
        """查询全球主流 AI 模型实时智商、价格与速度延迟"""
        raw_msg = event.message_str.strip()
        parts = raw_msg.split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else ""

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

        try:
            result = await self.fetcher.get_models(force_refresh=force_refresh)
        except Exception as exc:
            logger.error(f"[ai_iq] 拉取模型数据异常: {exc}")
            yield event.plain_result(f"获取实时模型智商数据失败：{exc}")
            return

        max_per_maker = max(1, int(self.config.get("max_per_maker", 6)))
        max_ranking_items = max(6, int(self.config.get("max_ranking_items", 24)))

        view_data = build_view_data(
            models=result.models,
            query=arg,
            default_makers=self._get_default_makers(),
            max_per_maker=max_per_maker,
            max_ranking_items=max_ranking_items,
            fetched_at=result.fetched_at,
            is_stale=result.is_stale,
        )

        if view_data["total_cards"] == 0:
            yield event.plain_result(
                f"未找到与「{arg}」匹配的带跑分模型，试试 `/aiiq gemini`、`/aiiq deepseek` 或 `/aiiq` 查看总览。"
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
