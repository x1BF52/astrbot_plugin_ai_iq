# astrbot_plugin_ai_iq

AstrBot 实时 AI 模型智商榜插件。一条指令查询全球主流大模型（**GPT / Gemini / Claude / DeepSeek / Qwen / GLM / Kimi / Grok** 等 20+ 厂商、150+ 模型）的实时智商评分、API 价格、输出速度与首字延迟，并以分组配色卡片图直观呈现，方便快速选模型干活。

## 功能特性

- **零配置免 API Key**：直连聚合实时数据源（Artificial Analysis 智商/编程指数 + OpenRouter 实时价格与测速）。
- **分组配色卡片图**：按厂商分行配色，单张卡片同时展示「模型名 + 智商分 + 输入/输出价格 + 输出速度 & 首字延迟」。
- **多维度筛选**：支持按厂商/关键词筛选、编程跑分榜、性价比榜、免费模型榜。
- **缓存与容错**：内置内存 + 本地磁盘缓存，防刷屏限流；上游超时时自动回退旧缓存；渲染不可用时自动降级为纯文本输出。

## 指令列表

| 指令 | 说明 |
| --- | --- |
| `/aiiq` | 查看主流厂商 Top 模型分组卡片图（别名 `/iq`、`/模型智商`） |
| `/aiiq gemini` / `/aiiq deepseek` / `/aiiq gpt` / `/aiiq claude` | 按厂商或模型名关键词筛选 |
| `/aiiq 编程` | 按 Artificial Analysis 编程跑分（Coding）降序排行 |
| `/aiiq 性价比` | 按「智商 ÷ 综合单价」排序，挑选最划算的干活模型 |
| `/aiiq 免费` | 查看 `$0` 免费模型智商排行 |
| `/aiiq 刷新` | 忽略缓存，强制拉取最新数据 |
| `/aiiq 帮助` | 查看指令帮助 |

## 卡片字段说明

- **左下大号数字**：Artificial Analysis 智商指数（`/aiiq 编程` 时为编程指数）
- **右上**：API 单价，单位为美元 / 百万 Token（`输入/输出`，免费显示 `FREE`）
- **右下**：实时输出速度（`tok/s`）· 首字延迟（`s` / `ms`）

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

- `cache_ttl_minutes`：缓存时间（默认 `15` 分钟）
- `default_makers`：默认视图展示的厂商及顺序（逗号分隔）
- `max_per_maker`：默认视图每个厂商最多展示的模型数量（默认 `6`）
- `max_ranking_items`：榜单/搜索模式最多展示卡片数量（默认 `24`）
- `request_timeout`：API 请求超时时间（默认 `20` 秒）
- `proxy`：可选 HTTP 代理地址

## 数据来源

- 模型评测与实时性能数据来自 [modelgrep](https://modelgrep.com/api)（聚合 Artificial Analysis 与 OpenRouter 公开数据）。

## License

MIT
