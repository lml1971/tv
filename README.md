<div align="center">

# 📺 茂哥点播 & 直播源接口

**TVBox 多仓 / 单仓接口** · **多源直播每日自动聚合**

> ——思路是我的，代码是 AI 的：**我负责不正经思路，它负责正规代码**。

<br>

[关于作者](#-关于作者) · [特性](#-特性) · [30 秒接入](#-30-秒接入) · [文件结构](#-文件结构) · [配置](#️-配置) · [自动更新](#-自动更新) · [FAQ](#-faq)

</div>

---

## 👤 关于作者

不是程序员，看不懂代码也不妨碍折腾：想给自己攒一份好用的直播源，就打开对话框，跟 AI 一句一句把代码**嗑**了出来——报错、丢回去、再改……某个时刻，它跑通了，而且挺好用。

- **思路是我的，代码是 AI 的**：我负责提需求，它负责写实现
- 不懂代码没关系，知道自己想要什么就行；懂代码更好，看到哪里写得笨，欢迎提 issue

> ⚠️ 仅供学习研究与技术交流，直播源均来自公开网络，不保证稳定性与合法性，请遵守当地法律法规。

---

## ✨ 特性

| | |
|---|---|
| 🔄 **多源聚合** | 自动拉取合并多个上游源，txt / m3u 自动识别，跨源去重 |
| 🗂️ **延用上游分组 + 按档排队** | 组名沿用上游（多源同名组自动加序号）；组间按 央视→卫视→地方→港澳台/国际→其他 排队，茂哥TV 之后第一个就是央视 |
| 🚫 **双重黑名单** | 组名黑名单整组剔除，频道名黑名单整条剔除 |
| 🔍 **真实分辨率** | ffprobe 抓流实测帧高，虚标重写名称，`< 720p` 自动剔除 |
| 🎯 **测速择优** | 并发测连接 / 首包耗时，快者在前，失败源沉底 |
| 📡 **茂哥TV 置顶** | `mgou_tv.txt` 永远首位，不受任何黑名单 / 探测 / 剔除影响 |
| 📦 **双格式产出** | 同步生成 `tv.txt` 与 `tv.m3u`，组名、条目、顺序完全一致 |
| ⏰ **每日自动更新 + 永不断源** | GitHub Actions 定时聚合；两阶段推送 + `FORCE_KEEP`，上游全挂也保留上一版 |

---

## 🚀 30 秒接入

任意 TVBox 类壳子（TVBox、影视仓、猫影视、FongMi……），把地址填进「接口地址」：

| 接口 | 填什么 | 说明 |
|------|--------|------|
| **多仓接口** | `maoge.json` 的 raw 地址 | 一次装进多个仓库 |
| **单仓接口** | `maoge.txt` 的 raw 地址 | 茂哥聚合线路列表 |
| **直播源** | `tv.txt` 的 raw 地址 | 填进「直播」，频道按天自动更新 |

填完等几秒，出画面就成了；出不来换一个仓试试。🔍

---

## 📁 文件结构

```
.
├── scripts/
│   ├── aggregate.py          # 核心：抓取→黑名单→剔除→实测→测速→产物
│   ├── normalize_tv.py       # 清洗：归一、去重、排序、双格式产出
│   ├── canonical.py          # 频道命名归一（CCTV/CGTN/CETV/CHC）
│   └── output.py 等          # 其余模块见脚本内注释
├── .github/workflows/
│   └── live-aggregator.yml   # 定时工作流
├── sources.txt               # ★ 上游直播源列表（一行一个 URL）
├── mgou_tv.txt               # ★ 茂哥TV 固定节目（置顶，按需维护）
├── group_blacklist.txt       # ★ 组名黑名单（命中整组剔除）
├── name_blacklist.txt        # ★ 频道名黑名单（命中整条剔除）
├── maoge.json / maoge.txt    # 多仓 / 单仓接口
└── tv.txt / tv.m3u           # ★ 最终产物（自动生成，双格式）
```

> 日常只需要动 4 个标 ★ 的文本文件，都在仓库根目录，改完推送即生效。

---

## ⚙️ 配置

- **加直播源**：`sources.txt` 一行一个 URL，`#` 开头为注释，txt / m3u 按内容自动识别
- **茂哥TV 置顶**：`mgou_tv.txt`，格式 `节目名,地址`，受版本控制，不会被上游覆盖
- **组名 / 频道名黑名单**：`group_blacklist.txt` / `name_blacklist.txt`，每行一个，命中剔除（`茂哥TV` 为保留组名，请勿删除）
- **运行参数**：改 `.github/workflows/live-aggregator.yml` 各 step 的 `env`（每个变量旁有注释），脚本顶部注明默认值

常用环境变量：

| 变量 | 默认 | 说明 |
|------|------|------|
| `MIN_HEIGHT` | 720 | 清晰度门槛帧高（360/480/720/1080/2160） |
| `DISABLE_VALIDATE` / `DISABLE_PROBE` / `DISABLE_SPEED` | 未设 | 设为 `1` 分别关闭无效源剔除 / 抓流探测 / 测速择优 |
| `VALIDATE_*` / `SPEED_*` | 见脚本 | 探测与测速的超时、并发、单轮上限、总预算，详见脚本顶部注释 |
| `FORCE_KEEP` | true | 所有源失败时保留旧 `tv.txt` |

---

## 🤖 自动更新

`.github/workflows/live-aggregator.yml` 已配好：每日 UTC 17:00（北京时间 01:00）自动跑，支持手动 `Run workflow`，自动安装 ffmpeg，仅内容变化时提交（需仓库开启 `contents: write` 权限）。

| 阶段 | 做什么 | 目的 |
|------|--------|------|
| **A · 快速通道** | 抓取 + 黑名单 + 剔除无效源 + 清洗 | 几分钟内必定产出并推送 |
| **B · 增强通道** | 复验 + 实测分辨率 + 测速择优（双预算限流） | 超时只损失优化，不影响产物 |

---

## 📝 输出格式

tv.txt（TVBox 类壳子「直播」通用）：

```
茂哥TV,#genre#
幸福家,https://example.com/1.mp4

央视频道,#genre#
CCTV-1 综合,http://example.com/cctv1.m3u8
```

分组头 `分组名,#genre#`，条目 `节目名,播放地址`，分组间空行；支持 `http/https/rtsp/rtp/udp://`。`tv.m3u` 与 `tv.txt` 同组名、同条目、同顺序，均由脚本自动生成，组名来自上游源。

---

## ❓ FAQ

<details>
<summary><b>怎么加直播源？</b></summary>

`sources.txt` 加一行 URL，脚本自动拉取、探测、合并。
</details>

<details>
<summary><b>为什么有些频道被剔除了？</b></summary>

命中 `name_blacklist.txt` 或所在组命中 `group_blacklist.txt`；探测判死（连接失败 / 404 / 410）；实测帧高 `< MIN_HEIGHT`。茂哥TV 置顶节目不受任何剔除影响。
</details>

<details>
<summary><b>为什么产物里有很多带序号的重复组名？</b></summary>

「延用上游分组」的设计：多源组名相同时按出现顺序加序号（央视频道 / 央视频道2……），避免不同源的频道混在一起。想合并或剔除，改 `group_blacklist.txt`。
</details>

<details>
<summary><b>所有源都挂了会怎样？</b></summary>

`FORCE_KEEP=true`（默认）保留上一次 `tv.txt`，脚本正常退出。
</details>

<details>
<summary><b>为什么 CCTV-1 只有一条？</b></summary>

`canonical.py` 把 `CCTV1 / CCTV-1 / CCTV-1 综合 / CCTV-1(720p)` 等别名归一后去重，`ci_assert.py` 在 CI 断言产物中不允许残留别名。
</details>

<details>
<summary><b>想立刻跑一次？</b></summary>

GitHub → Actions → Aggregate Live Sources → Run workflow，或本地：

```bash
python scripts/aggregate.py     # 需 ffmpeg 启用分辨率探测
python scripts/normalize_tv.py
```
</details>

---

<div align="center">

⭐ **觉得有用，欢迎 Star；有问题或建议，欢迎提 issue。**

</div>
