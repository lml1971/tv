# Cloudflare Worker 直播源聚合 — KV 部署指南

## 📦 文件说明

| 文件 | 用途 |
|---|---|
| `worker.js` | Worker 主代码（已接入 KV 缓存） |
| `wrangler.toml` | Wrangler CLI 部署配置 |
| `README.md` | 本说明文档 |

---

## 🚀 部署步骤

### 方式一：Wrangler CLI（推荐）

#### 1. 安装 Wrangler

```bash
npm install -g wrangler
wrangler login
```

#### 2. 创建 KV 命名空间

```bash
wrangler kv:namespace create "live_cache"
```

输出示例：
```
🌀 Creating namespace with title "live-aggregator-live_cache"
✨ Success!
Add the following to your wrangler.toml:
[[kv_namespaces]]
binding = "KV"
id = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

#### 3. 填入 ID

将上面输出的 `id` 复制到 `wrangler.toml` 中替换 `替换为你的-namespace-id`。

#### 4. 部署

```bash
wrangler deploy
```

部署成功后终端会输出你的 Worker URL，例如：
```
https://live-aggregator.your-subdomain.workers.dev
```

---

### 方式二：Cloudflare Dashboard

#### 1. 创建 KV 命名空间

- 进入 **Workers & Pages** → 左侧 **KV**
- 点击 **Create a namespace**
- 名称填 `live_cache`
- 记下生成的 **Namespace ID**

#### 2. 创建 / 编辑 Worker

- 进入 **Workers & Pages** → **Create application** → **Create Worker**
- 将 `worker.js` 的完整内容粘贴到代码编辑器
- 点击 **Save**

#### 3. 绑定 KV

- 进入 Worker → **Settings** → **Variables**
- 滚动到 **KV Namespace Bindings** → **Add binding**
- 变量名填 `KV`
- 选择刚才创建的 `live_cache`
- 点击 **Save**

---

## 🔗 接口用法

部署后你的 Worker URL 记为 `https://your-worker.xxx.workers.dev`

| 接口 | 说明 |
|---|---|
| `GET /` | 首页，返回分类 + 推广 + 每组前5频道 |
| `GET /?ac=list&t=分组名&pg=1&limit=20` | 按分组分页列表 |
| `GET /?ac=detail&ids=ch_0,ch_1` | 频道详情 |
| `GET /m3u` 或 `/live.m3u` | 输出 M3U 播放列表 |
| `GET /txt` 或 `/live.txt` | 输出 TXT 格式列表 |

---

## 🔧 常见问题

**Q: 绑定后报 `env.KV is undefined`？**
A: 检查 `wrangler.toml` 中 `binding` 名称是否为 `KV`，需与代码中 `env.KV` 一致。改完后重新 `wrangler deploy`。

**Q: KV 缓存多久刷新一次？**
A: 代码中 `KV_TTL_SECONDS = 600`（10 分钟）。如需调整，修改 `worker.js` 顶部常量后重新部署。

**Q: 没有 KV 绑定能跑吗？**
A: 能。代码做了兼容——没有 KV 时会直接抓取源站，只是每次冷启动会慢一些（最多 15 秒超时）。

**Q: 如何手动清除 KV 缓存？**
A: Dashboard → KV → 找到 `all_channels_v1` 这个 key → 删除即可。下次请求会自动重新抓取。
