# astrbot_plugin_ai_iq

AstrBot 实时 AI 模型智商榜插件。一条指令查询全球主流大模型（**Claude / GPT / Gemini / DeepSeek / Qwen / GLM / Kimi / Grok** 等）的实时智商评分、**推理强度分档（`max / xhigh / high / medium / low / 无推理`）**、API 单价与题均成本、输出速度与首答延迟，并以分组配色卡片图直观呈现，方便快速选模型与思考档位干活。

## 功能特性

- **零配置免 API Key，双源自动容错**：优先直连 **Artificial Analysis** 官方实时榜单（含完整推理强度分档与题均成本），不可达时自动回退至 **modelgrep**（聚合 Artificial Analysis + OpenRouter 数据）。
- **推理强度分档展示**：同一模型按 `max / xhigh / high / medium / low / 无推理` 从高到低分行居中排布，一眼看清不同思考档位的智商收益、题均成本与首答耗时差异。
- **自动过滤过期与旧代模型**：
  - 同系列版本去重（例如已有 `Claude Fable 5.2` 时自动隐藏 `5.1`，已有 `DeepSeek V4 Pro 0813` 时自动隐藏 `0423`）；
  - 跨大代自动清理（例如 `Gemini 4` 系列上线后自动隐藏 `Gemini 3.5 Flash-Lite` 等旧代模型）；
  - 支持按发布天数过滤远古模型（默认 180 天，可在配置页关闭或查询时附带 `全部` 临时查看）。
- **多维度筛选**：支持按厂商、关键词、推理强度筛选，以及编程跑分榜、性价比榜、免费模型榜。
- **缓存与降级**：内置内存 + 磁盘缓存，上游超时自动回退历史缓存，HTML 渲染不可用时自动降级纯文本。

## 指令列表

| 指令 | 说明 |
| --- | --- |
| `/aiiq` | 查看主流厂商最新在役模型与推理强度分组卡片图（别名 `/模型智商`） |
| `/aiiq gemini` / `/aiiq deepseek` / `/aiiq gpt` / `/aiiq claude` | 查看指定厂商全部在役系列及各推理强度档位 |
| `/aiiq max` / `/aiiq high` / `/aiiq gemini high` | 按推理强度筛选（支持组合厂商与强度） |
| `/aiiq 编程` | 按编程评测综合分（Coding）降序排行 |
| `/aiiq 性价比` | 按「智商 ÷ 题均成本/综合单价」降序推荐（智商 ≥ 20） |
| `/aiiq 免费` | 查看 `$0` 免费模型智商排行 |
| `/aiiq 全部 gemini` | 临时关闭过期过滤，查看包含旧代模型的完整列表 |
| `/aiiq 刷新` | 忽略缓存，强制拉取最新数据 |
| `/aiiq 帮助` | 查看指令帮助 |

## 卡片字段说明

- **左上**：完整模型系列名（自动换行，不截断版本号或日期后缀）
- **左下**：超大号 Artificial Analysis 智商指数（`/aiiq 编程` 时为编程综合分）+ 高对比度**推理强度标签**（`MAX / XHIGH / HIGH / MEDIUM / LOW / 推理 / 无推理`）
- **右上**：API 单价（`$/1M Tokens`，输入/输出）+ 题均实际成本（`题均 $x.xx`，来自 AA 评测消耗）
- **右下**：实时输出速度（`tok/s`）· 首答延迟（`s` / `ms`，直观反映思考等待时间）

## 安装方式

1. 打开 AstrBot WebUI → 插件管理 → 安装插件 → 输入本仓库地址：
   ```text
   https://github.com/x1BF52/astrbot_plugin_ai_iq
   ```
2. 或直接克隆到插件目录后重启 AstrBot：
   ```bash
   cd AstrBot/data/plugins
   git clone https://github.com/x1BF52/astrbot_plugin_ai_iq.git
   ```

## 配置项说明

可在 AstrBot WebUI 插件配置页直接调整：

- `data_source`：数据源选择（`auto` / `artificial_analysis` / `modelgrep`，默认 `auto`）
- `cache_ttl_minutes`：缓存时间（默认 `15` 分钟）
- `filter_outdated`：是否自动过滤过期与旧代模型（默认 `true`）
- `max_model_age_days`：模型最大保留天数（默认 `180` 天，`0` 表示不限制）
- `default_makers`：默认总览展示的厂商及顺序（逗号分隔）
- `max_releases_per_maker`：默认总览每个厂商最多展示的系列行数（默认 `4`，覆盖旗舰到轻量全档位）
- `max_per_maker`：每行最多展示的卡片数量（默认 `6`）
- `max_ranking_items`：榜单/搜索模式最多展示卡片数（默认 `24`）
- `request_timeout`：API 请求超时时间（默认 `25` 秒）
- `proxy`：可选 HTTP 代理地址（宿主机 Clash 可填 `http://127.0.0.1:7890`，Docker 内填 `http://host.docker.internal:7890`）

## 数据来源

- 主数据源：[Artificial Analysis](https://artificialanalysis.ai/leaderboards/models) 官方实时榜单（含推理强度分档、题均成本、速度与首答延迟）。
- 回退数据源 & 免费榜：[modelgrep](https://modelgrep.com/api)（聚合 Artificial Analysis 与 OpenRouter 公开数据）。

## License

MIT
