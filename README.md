# astrbot_plugin_ai_iq

AstrBot 实时 AI 模型智商榜插件。一条指令查询全球主流大模型（**Claude / GPT / Gemini / DeepSeek / Qwen / GLM / Kimi / Grok** 等）的实时智商评分、**推理强度分档（`MAX / XHIGH / HIGH / MEDIUM / LOW`）**、API 单价与题均成本、输出速度与首答延迟，并以厂商真实品牌色 + 递减灰阶卡片图直观呈现，方便快速选模型与思考档位干活。

## 功能特性

- **多源容错 & 不污染缓存**：
  - 主源优先 **Artificial Analysis**（支持官方 v2 API 并发分页拉取与公开实时榜单，保留完整推理强度分档、题均成本、速度与首答延迟）；
  - 主源超时（8s 快速建连检测）时，并发竞速回退 **`llmpricing.dev`** 与 **`modelgrep`**，谁先返回立刻用谁，且**回退结果不写入缓存**，下次查询自动重试主源；
  - 内置 **BenchGecko** 硬核多榜（`/aiiq 硬核` 或 `/aiiq gecko`），提供非 AA 体系的 ARC-AGI-2 / FrontierMath / FrontierSWE / GPQA 综合视角。
- **厂商真实品牌色 + 推理强度递减灰阶**：
  - 主流厂商采用各自品牌色（Claude 陶土红 / OpenAI 翡翠绿 / Google 亮蓝 / DeepSeek 靛蓝 / Qwen 通义紫 / GLM 青蓝 / Kimi 深玫红 / Grok 石墨灰），未知新厂商自动读取 AA 品牌色或稳定哈希派生色阶；
  - 推理强度从 `ULTRA / MAX → XHIGH → HIGH → MEDIUM → LOW` 逐级降温至中性灰，默认隐藏「无推理」档位，画布收紧为 5 列齐平，手机端高可读。
- **自动过滤过期与旧代模型**：
  - 同系列版本去重（例如已有 `Claude Fable 5.2` 时自动隐藏 `5.1`，已有 `DeepSeek V4 Pro 0813` 时自动隐藏 `0423`）；
  - 跨大代自动清理（例如 `Gemini 4` 系列上线后自动隐藏 `Gemini 3.5 Flash-Lite` 等旧代模型）；
  - 支持按发布天数过滤远古模型（默认 180 天，可在配置页关闭或查询时附带 `全部` 临时查看）。
- **灵活配置**：支持自定义唤醒词（默认 `aiiq`）、多选主流厂商 + 自定义追加厂商、AA 官方 API Key 掩码保护、自定义反代 API 地址与 HTTP 代理。
- **缓存与降级**：内存 + 磁盘双层缓存，所有上游不可用时回退历史缓存；HTML 渲染异常时自动降级纯文本输出。

## 指令列表

| 指令 | 说明 |
| --- | --- |
| `/aiiq` | 查看主流厂商最新在役模型与推理强度分组矩阵图（唤醒词可在配置页自定义） |
| `/aiiq gemini` / `/aiiq deepseek` / `/aiiq gpt` / `/aiiq claude` | 查看指定厂商全部在役系列及各推理强度档位 |
| `/aiiq max` / `/aiiq high` / `/aiiq gemini high` | 按推理强度筛选（支持组合厂商与强度） |
| `/aiiq 编程` | 按编程 / 工程评测综合分降序排行 |
| `/aiiq 性价比` | 按「智商 ÷ 题均成本/综合单价」降序推荐（智商 ≥ 20） |
| `/aiiq 硬核` / `/aiiq gecko` | 查看 BenchGecko 硬核多榜综合分（ARC-AGI-2 / FrontierMath / FrontierSWE / GPQA 等） |
| `/aiiq 免费` | 查看 `$0` 免费模型智商排行 |
| `/aiiq 全部 gemini` | 临时关闭过期与「无推理」过滤，查看包含旧代模型的完整列表 |
| `/aiiq 刷新` | 忽略缓存，强制拉取最新数据 |
| `/aiiq 帮助` | 查看指令帮助 |

## 卡片字段说明

- **总览 / 厂商视图（矩阵看板）**：按厂商分块，每行一个模型系列（左侧展示型号名 + API 单价 `$/1M`，右侧横向展开各推理强度档位，默认 5 列齐平）。
- **每个档位格内**：左上为递减色阶**推理强度徽章**（`ULTRA / MAX / XHIGH / HIGH / MEDIUM / LOW`），右上大字为**评测题均成本**（`$x.xx`），中间大号数字为 **AA 智商指数** + 进度条，底部为**输出速度 · 首答延迟**。
- **榜单视图（编程 / 性价比 / 硬核 / 免费 / 单档位）**：高可读性 3 列宽卡排行，突出名次、评分、题均成本与单价速度。

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

- `trigger_keywords`：唤醒指令词（逗号分隔，默认 `aiiq`，可改为或追加如 `aiiq,模型智商,查智商`）
- `data_source`：数据源选择（`auto` / `artificial_analysis` / `llmpricing` / `benchgecko` / `modelgrep`，默认 `auto`）
- `aa_api_key`：Artificial Analysis 官方 API Key（可选，WebUI 自动掩码保护；留空拉取公开榜，填写后优先并发拉取官方 v2 API `/api/v2/language/models/free`，免费档 1000 次/天）
- `custom_api_url`：自定义数据源 / 反代 API 地址（可选，自动兼容 AA 官方 JSON / AA 榜单反代 / `llmpricing.dev` / `BenchGecko` / `modelgrep`）
- `selected_makers`：默认展示的主流厂商（多选下拉框，按勾选顺序分段展示）
- `custom_makers`：自定义追加厂商（逗号分隔，如 `stepfun,nvidia,cohere`，追加在勾选厂商之后）
- `hide_non_reasoning`：隐藏「无推理」档位（默认 `true`，查询时输入 `无推理` 或 `全部` 可临时查看）
- `filter_outdated`：是否自动过滤过期与旧代模型（默认 `true`）
- `max_model_age_days`：模型最大保留天数（默认 `180` 天，`0` 表示不限制）
- `max_series_per_maker`：默认总览每个厂商最多展示的系列行数（默认 `5`，自动覆盖旗舰到轻量全档位）
- `max_per_maker`：每行最多展示的卡片数量（默认 `5`）
- `max_ranking_items`：榜单/搜索模式最多展示卡片数（默认 `24`）
- `cache_ttl_minutes`：缓存时间（默认 `15` 分钟；主源失败触发降级回退时不写入缓存，下次查询自动重试主源）
- `request_timeout`：API 请求超时时间（秒，默认 `25`）
- `proxy`：可选 HTTP 代理地址（宿主机 Clash 可填 `http://127.0.0.1:7890`，Docker 内填 `http://host.docker.internal:7890`）

## Cloudflare Workers 反代部署（国内服务器加速）

如果部署 AstrBot 的服务器直连 `artificialanalysis.ai` 超时且未配置代理，可以用 Cloudflare Workers 免费搭一个专属反代（每天 10 万次免费请求），填进插件的 `custom_api_url` 即可稳定秒开完整多档位数据。

### 部署步骤

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/) → 左侧菜单 **Workers & Pages** → **Create** → **Create Worker**（如命名为 `aa-iq-proxy`）→ **Deploy** → **Edit code**。
2. 清空默认代码，粘贴以下脚本并点击 **Deploy**：

```js
export default {
  async fetch(request, env) {
    // 优先使用插件请求头传来的 Key，也可在 Worker 环境变量里配 AA_API_KEY
    const apiKey = request.headers.get("x-api-key") || env.AA_API_KEY || "";

    // 模式 A：有 API Key -> 并发拉取 AA v2 API 全部分页并合并为单个 JSON（最快最稳）
    if (apiKey) {
      const headers = { "x-api-key": apiKey, Accept: "application/json" };
      const fetchPage = (p) =>
        fetch(`https://artificialanalysis.ai/api/v2/language/models/free?page=${p}`, {
          headers,
          cf: { cacheTtl: 600, cacheEverything: true },
        });

      const firstResp = await fetchPage(1);
      if (!firstResp.ok) {
        return new Response(await firstResp.text(), {
          status: firstResp.status,
          headers: { "content-type": "application/json; charset=utf-8" },
        });
      }
      const firstJson = await firstResp.json();
      const totalPages = Math.min(12, Math.max(1, Number(firstJson?.pagination?.total_pages || 1)));
      const allData = Array.isArray(firstJson?.data) ? [...firstJson.data] : [];

      if (totalPages > 1) {
        const restResps = await Promise.all(
          Array.from({ length: totalPages - 1 }, (_, i) => fetchPage(i + 2))
        );
        for (const resp of restResps) {
          if (resp.ok) {
            const j = await resp.json();
            if (Array.isArray(j?.data)) allData.push(...j.data);
          }
        }
      }

      return new Response(JSON.stringify({ data: allData }), {
        headers: {
          "content-type": "application/json; charset=utf-8",
          "cache-control": "public, max-age=600",
        },
      });
    }

    // 模式 B：无 API Key -> 直接反代 AA 公开榜单页
    const resp = await fetch("https://artificialanalysis.ai/leaderboards/models", {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        Accept: "text/html,application/xhtml+xml",
      },
      cf: { cacheTtl: 600, cacheEverything: true },
    });

    return new Response(resp.body, {
      status: resp.status,
      headers: {
        "content-type": resp.headers.get("content-type") || "text/html; charset=utf-8",
        "cache-control": "public, max-age=600",
      },
    });
  },
};
```

3. **绑定自定义域名（强烈推荐）**：`*.workers.dev` 在国内部分网络易被阻断，建议在 Worker 的 **Settings → Domains & Routes → Add → Custom Domain** 绑定一个自己托管在 Cloudflare 的子域名（例如 `https://aa.yourdomain.com`）。
4. **在 AstrBot 插件配置页填写**：
   - `custom_api_url`：填入你的 Worker 地址（如 `https://aa.yourdomain.com`）
   - `aa_api_key`：填入你的 AA Key（或在 Worker 的 **Settings → Variables and Secrets** 里添加 Secret `AA_API_KEY`，插件侧留空即可）
   - 保存后发 `/aiiq 刷新` 验证，底部数据源显示「自定义数据源 API」即生效。

## 数据来源

- 主数据源：[Artificial Analysis](https://artificialanalysis.ai/leaderboards/models) 官方 v2 API / 实时榜单（含推理强度分档、题均成本、速度与首答延迟）。
- 并发高速回退源：[LLM Pricing](https://llmpricing.dev/api/models.json)（AA v5 + 官方定价 + 题均成本）与 [modelgrep](https://modelgrep.com/api)（兼作 `/aiiq 免费` 数据源）。
- 硬核多榜数据源：[BenchGecko](https://benchgecko.ai/models)（CC BY 4.0，聚合 ARC-AGI-2 / FrontierMath / FrontierSWE / GPQA 等多方基准）。

## License

MIT
