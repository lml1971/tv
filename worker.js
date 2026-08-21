// Cloudflare Worker - 直播源聚合 / 引流注入
// 已接入 KV 缓存，避免每次冷启动重新抓取

const SOURCE_URLS = [
    { url: "https://0701.tv1288.xyz/m3u", format: "m3u" },
    { url: "https://m3u.lml1971.ccwu.cc/xymm" },
    { url: "https://5266.kstore.space/xiangxichuanshuo.txt", format: "txt" },
];

const PROMO_LIST = [
    {
        title: "山西农大宣传片",
        url:   "https://vio.alltuu.com/vf1PWo247.mp4?Expires=1787751240&OSSAccessKeyId=LTAI5tCKgYFjLSzev9mGY4Vs&Signature=KvkTyfigKhLCN1LzJ7GFycrQoRQ%3D&response-content-disposition=attachment%3Bfilename%3D%22%E5%86%9C%E5%A4%A7%E5%AE%A3%E4%BC%A0%E7%89%871.mp4%22",
        pic:   "https://www.3wen.com/userfiles/images/3shanxi.jpg",
        group: "林学系92级",
        from:  "毕业三十年1",
        remarks: "置顶引流",
     },
     {
        title: "林学院宣传片",
        url:   "https://vio.alltuu.com/vf1PWoM20.mp4?Expires=1787751240&OSSAccessKeyId=LTAI5tCKgYFjLSzev9mGY4Vs&Signature=Mjo%2BIkl5h%2FX%2F97wyr0G5MGa1sIY%3D&response-content-disposition=attachment%3Bfilename%3D%22%E6%9E%97%E5%AD%A6%E9%99%A2%E5%AE%A3%E4%BC%A0%E7%89%87%EF%BC%882026.5.6%E5%AE%9A%E7%A8%BF%29.mp4%22",
        pic:   "https://www.3wen.com/userfiles/images/3shanxi.jpg",
        group: "林学系92级",
        from:  "备用线路",
        remarks: "推广",
     },
     {
        title: "林学92级毕业卅年",
        url:   "https://vio.alltuu.com/vf1PmHLd9.mp4?Expires=1787751240&OSSAccessKeyId=LTAI5tCKgYFjLSzev9mGY4Vs&Signature=Y1%2FviyPd93xBXRSo5xpa%2BdrvZeQ%3D&response-content-disposition=attachment%3Bfilename%3D%222026.08%20%E5%86%9C%E5%A4%A7%E6%9E%97%E5%AD%A692%E7%BA%A7%E6%AF%95%E4%B8%9A%E5%8D%85%E5%B9%B4%E5%90%8C%E5%AD%A6%E8%81%9A%E4%BC%9A%E7%BA%AA%E5%AE%9E_20260811_18223261.mp4%22",
        pic:   "https://www.3wen.com/userfiles/images/3shanxi.jpg",
        group: "林学系92级",
        from:  "备用线路",
        remarks: "推广",
     },
     {
        title: "林学92级毕业十年",
        url:   "https://lmlcyp.ccwu.cc/raw/mp4/10.mp4",
        pic:   "https://www.3wen.com/userfiles/images/3shanxi.jpg",
        group: "林学系92级",
        from:  "备用线路",
        remarks: "推广",
       },
       {
        title: "幸福家",
        url:   "https://lmlcyp.ccwu.cc/raw/mp4/1.mp4",
        pic:   "https://ts1.tc.mm.bing.net/th/id/R-C.44a8fce5f82322ff6047579c70ba87a5?rik=GtFY9WEgT3mvmg&riu=http%3a%2f%2f5b0988e595225.cdn.sohucs.com%2fq_70%2cc_zoom%2cw_640%2fimages%2f20170819%2f31955e56cdbc478e8a9d53b54d92cbf0.jpeg&ehk=kYySxDkRdxi37EML22nDcDWX8ypoyqXbPt6ziempjDg%3d&risl=&pid=ImgRaw&r=0",
        group: "茂哥TV",
        from:  "线路A",
        remarks: "置顶引流",
    },
    {
        title: "老李卡通",
        url:   "https://lmlcyp.ccwu.cc/raw/mp4/2.mp4",
        pic:   "https://ts1.tc.mm.bing.net/th/id/R-C.44a8fce5f82322ff6047579c70ba87a5?rik=GtFY9WEgT3mvmg&riu=http%3a%2f%2f5b0988e595225.cdn.sohucs.com%2fq_70%2cc_zoom%2cw_640%2fimages%2f20170819%2f31955e56cdbc478e8a9d53b54d92cbf0.jpeg&ehk=kYySxDkRdxi37EML22nDcDWX8ypoyqXbPt6ziempjDg%3d&risl=&pid=ImgRaw&r=0",
        group: "茂哥TV",
        from:  "线路A",
        remarks: "置顶引流",
    },
    {
        title: "父母亲",
        url:   "https://lmlcyp.ccwu.cc/raw/mp4/3.mp4",
        pic:   "https://ts1.tc.mm.bing.net/th/id/R-C.44a8fce5f82322ff6047579c70ba87a5?rik=GtFY9WEgT3mvmg&riu=http%3a%2f%2f5b0988e595225.cdn.sohucs.com%2fq_70%2cc_zoom%2cw_640%2fimages%2f20170819%2f31955e56cdbc478e8a9d53b54d92cbf0.jpeg&ehk=kYySxDkRdxi37EML22nDcDWX8ypoyqXbPt6ziempjDg%3d&risl=&pid=ImgRaw&r=0",
        group: "茂哥TV",
        from:  "线路A",
        remarks: "置顶引流",
    },
    {
        title: "这头猪",
        url:   "https://lmlcyp.ccwu.cc/raw/mp4/4.mp4",
        pic:   "https://ts1.tc.mm.bing.net/th/id/R-C.44a8fce5f82322ff6047579c70ba87a5?rik=GtFY9WEgT3mvmg&riu=http%3a%2f%2f5b0988e595225.cdn.sohucs.com%2fq_70%2cc_zoom%2cw_640%2fimages%2f20170819%2f31955e56cdbc478e8a9d53b54d92cbf0.jpeg&ehk=kYySxDkRdxi37EML22nDcDWX8ypoyqXbPt6ziempjDg%3d&risl=&pid=ImgRaw&r=0",
        group: "茂哥TV",
        from:  "线路A",
        remarks: "置顶引流",
    },
    {
        title: "大实话",
        url:   "https://lmlcyp.ccwu.cc/raw/mp4/5.mp4",
        pic:   "https://ts1.tc.mm.bing.net/th/id/R-C.44a8fce5f82322ff6047579c70ba87a5?rik=GtFY9WEgT3mvmg&riu=http%3a%2f%2f5b0988e595225.cdn.sohucs.com%2fq_70%2cc_zoom%2cw_640%2fimages%2f20170819%2f31955e56cdbc478e8a9d53b54d92cbf0.jpeg&ehk=kYySxDkRdxi37EML22nDcDWX8ypoyqXbPt6ziempjDg%3d&risl=&pid=ImgRaw&r=0",
        group: "茂哥TV",
        from:  "线路A",
        remarks: "置顶引流",
    },
    {
        title: "后悔药",
        url:   "https://lmlcyp.ccwu.cc/raw/mp4/6.mp4",
        pic:   "https://ts1.tc.mm.bing.net/th/id/R-C.44a8fce5f82322ff6047579c70ba87a5?rik=GtFY9WEgT3mvmg&riu=http%3a%2f%2f5b0988e595225.cdn.sohucs.com%2fq_70%2cc_zoom%2cw_640%2fimages%2f20170819%2f31955e56cdbc478e8a9d53b54d92cbf0.jpeg&ehk=kYySxDkRdxi37EML22nDcDWX8ypoyqXbPt6ziempjDg%3d&risl=&pid=ImgRaw&r=0",
        group: "茂哥TV",
        from:  "线路A",
        remarks: "置顶引流",
    },
    {
        title: "丢人",
        url:   "https://lmlcyp.ccwu.cc/raw/mp4/7.mp4",
        pic:   "https://ts1.tc.mm.bing.net/th/id/R-C.44a8fce5f82322ff6047579c70ba87a5?rik=GtFY9WEgT3mvmg&riu=http%3a%2f%2f5b0988e595225.cdn.sohucs.com%2fq_70%2cc_zoom%2cw_640%2fimages%2f20170819%2f31955e56cdbc478e8a9d53b54d92cbf0.jpeg&ehk=kYySxDkRdxi37EML22nDcDWX8ypoyqXbPt6ziempjDg%3d&risl=&pid=ImgRaw&r=0",
        group: "茂哥TV",
        from:  "线路A",
        remarks: "置顶引流",
    },
    {
        title: "家规",
        url:   "https://lmlcyp.ccwu.cc/raw/mp4/8.mp4",
        pic:   "https://ts1.tc.mm.bing.net/th/id/R-C.44a8fce5f82322ff6047579c70ba87a5?rik=GtFY9WEgT3mvmg&riu=http%3a%2f%2f5b0988e595225.cdn.sohucs.com%2fq_70%2cc_zoom%2cw_640%2fimages%2f20170819%2f31955e56cdbc478e8a9d53b54d92cbf0.jpeg&ehk=kYySxDkRdxi37EML22nDcDWX8ypoyqXbPt6ziempjDg%3d&risl=&pid=ImgRaw&r=0",
        group: "茂哥TV",
        from:  "线路A",
        remarks: "置顶引流",
    },
    {
        title: "酒瓶瓶",
        url:   "https://lmlcyp.ccwu.cc/raw/mp4/9.mp4",
        pic:   "https://ts1.tc.mm.bing.net/th/id/R-C.44a8fce5f82322ff6047579c70ba87a5?rik=GtFY9WEgT3mvmg&riu=http%3a%2f%2f5b0988e595225.cdn.sohucs.com%2fq_70%2cc_zoom%2cw_640%2fimages%2f20170819%2f31955e56cdbc478e8a9d53b54d92cbf0.jpeg&ehk=kYySxDkRdxi37EML22nDcDWX8ypoyqXbPt6ziempjDg%3d&risl=&pid=ImgRaw&r=0",
        group: "茂哥TV",
        from:  "线路A",
        remarks: "置顶引流",
    },
    {
        title: "25年前",
        url:   "https://lmlcyp.ccwu.cc/raw/mp4/VDO_0012.mp4",
        pic:   "https://ts1.tc.mm.bing.net/th/id/R-C.44a8fce5f82322ff6047579c70ba87a5?rik=GtFY9WEgT3mvmg&riu=http%3a%2f%2f5b0988e595225.cdn.sohucs.com%2fq_70%2cc_zoom%2cw_640%2fimages%2f20170819%2f31955e56cdbc478e8a9d53b54d92cbf0.jpeg&ehk=kYySxDkRdxi37EML22nDcDWX8ypoyqXbPt6ziempjDg%3d&risl=&pid=ImgRaw&r=0",
        group: "茂哥TV",
        from:  "线路A",
        remarks: "置顶引流",
    },
];

const SPAM_KEYWORDS = [
    "注意事项", "加群", "TG频道", "轮播视频",  "US", "关注Q群", "交流群", "防失联",
    "防丢关注", "网址", "官网", "广告位", "微信公众号", "最新资源",
    "获取资源", "备用地址", "防丢地址", "更新时间", "关于本源"
];

const CACHE_TTL_MS       = 10 * 60 * 1000;
const DEFAULT_PAGE_SIZE  = 20;
const MAX_RETURN_LIMIT   = 500;
const FALLBACK_LOGO_BASE = "https://epg.112114.xyz/logo";
const FETCH_TIMEOUT_MS   = 15 * 1000;

// KV 缓存配置
const KV_CACHE_KEY    = "all_channels_v1";
const KV_TTL_SECONDS  = 600; // 10 分钟

// ---------- 工具函数 ----------

function normalizeSource(src) {
    const url = typeof src === "string" ? src : (src && src.url) || "";
    return { url, format: src && src.format, _skip: !isValidHttpUrl(url) };
}

function isValidHttpUrl(str) {
    if (!str || typeof str !== "string") return false;
    try {
        const u = new URL(str);
        return u.protocol === "http:" || u.protocol === "https:";
    } catch {
        return false;
    }
}

function isSpam(text) {
    return text && SPAM_KEYWORDS.some(kw => text.includes(kw));
}

// 从 #EXTINF 行提取属性值（兼容有/无引号）
function extractAttr(line, key) {
    const re = new RegExp(
        key + '=(?:"([^"]+)"|\'([^\']+)\'|([^,\\s][^,]*?)(?=,\\s*\\w+=|$))'
    );
    const m = line.match(re);
    return m ? (m[1] || m[2] || m[3] || "").trim() : "";
}

async function fetchWithTimeout(url, timeoutMs) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
        return await fetch(url, {
            headers: {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
            },
            signal: controller.signal,
        });
    } finally {
        clearTimeout(timer);
    }
}

// ---------- 解析器 ----------

function parseM3U(text) {
    const list = [];
    let current = null;

    for (const line of text.split('\n')) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        if (trimmed.startsWith('#EXTINF')) {
            const group = extractAttr(trimmed, 'group-title') || "默认频道";
            let logo = extractAttr(trimmed, 'tvg-logo');
            const commaIdx = trimmed.lastIndexOf(',');
            const title = commaIdx > -1 ? trimmed.substring(commaIdx + 1).trim() : "未知频道";
            if (!logo) logo = `${FALLBACK_LOGO_BASE}/${encodeURIComponent(title)}.png`;
            current = { group, logo, title };
        } else if (trimmed.startsWith('#')) {
            continue;
        } else if (current) {
            const urls = trimmed.split(',').map(s => s.trim()).filter(Boolean);
            if (urls.length > 0) {
                const channel = { ...current, url: urls[0], urls };
                if (!isSpam(channel.group) && !isSpam(channel.title)) {
                    list.push(channel);
                }
            }
            current = null;
        }
    }
    return list;
}

function parseTXT(text) {
    const list = [];
    let currentGroup = "默认频道";

    for (const raw of text.split('\n')) {
        const line = raw.trim();
        if (!line || line.startsWith('#')) continue;

        // 分组行: xxx,#genre#
        if (/,#genre#\s*$/i.test(line)) {
            currentGroup = line.split(',')[0].trim() || "默认频道";
            continue;
        }

        // 频道行: title,url[#备用地址]
        const commaIdx = line.indexOf(',');
        if (commaIdx < 0) continue;
        const title = line.substring(0, commaIdx).trim();
        let urlPart = line.substring(commaIdx + 1).trim();
        if (!title || !urlPart) continue;

        // 仅当 # 后非空时才截断
        const hashIdx = urlPart.indexOf('#');
        if (hashIdx !== -1 && urlPart.substring(hashIdx + 1).trim()) {
            urlPart = urlPart.substring(0, hashIdx).trim();
        }
        if (!urlPart || isSpam(currentGroup) || isSpam(title)) continue;

        list.push({
            group: currentGroup,
            title,
            logo: `${FALLBACK_LOGO_BASE}/${encodeURIComponent(title)}.png`,
            url: urlPart,
            urls: [urlPart],
        });
    }
    return list;
}

function parseSource(text, formatHint) {
    const isM3U = formatHint === "m3u"
        ? true
        : formatHint === "txt"
            ? false
            : text.includes('#EXTM3U') || text.includes('#EXTINF');
    return isM3U ? parseM3U(text) : parseTXT(text);
}

// ---------- 抓取与合并（已接入 KV 缓存）----------

async function fetchOneSource(srcConfig) {
    const { url, format, _skip } = normalizeSource(srcConfig);
    if (_skip) {
        console.error(`[fetchOneSource] 跳过无效 URL: ${url || "(empty)"}`);
        return { source: url || "(invalid)", channels: [], error: "Invalid URL" };
    }
    try {
        const resp = await fetchWithTimeout(url, FETCH_TIMEOUT_MS);
        if (!resp.ok) {
            console.error(`[fetchOneSource] HTTP ${resp.status} for ${url}`);
            return { source: url, channels: [], error: `HTTP ${resp.status}` };
        }
        const text = await resp.text();
        if (!text || !text.trim()) {
            console.error(`[fetchOneSource] Empty body from ${url}`);
            return { source: url, channels: [], error: "Empty body" };
        }
        const channels = parseSource(text, format);
        console.log(`[fetchOneSource] ${url} -> ${channels.length} channels`);
        return { source: url, channels, error: null };
    } catch (err) {
        console.error(`[fetchOneSource] ${url} -> ${err.message}`);
        return { source: url, channels: [], error: err.message };
    }
}

// 从 KV 读取缓存，未命中则抓取并写回 KV
async function loadAllChannels(env, ctx) {
    // 1. 尝试从 KV 读取
    if (env && env.KV) {
        try {
            const cached = await env.KV.get(KV_CACHE_KEY, { type: "json" });
            if (cached && cached.expireAt > Date.now()) {
                console.log(`[loadAllChannels] KV cache HIT, ${cached.channels.length} channels`);
                return cached.channels;
            }
            if (cached) {
                console.log(`[loadAllChannels] KV cache EXPIRED, re-fetching`);
            } else {
                console.log(`[loadAllChannels] KV cache MISS`);
            }
        } catch (e) {
            console.error(`[loadAllChannels] KV read error: ${e.message}`);
        }
    } else {
        console.log(`[loadAllChannels] No KV binding found, fetching directly`);
    }

    // 2. KV 未命中或已过期，抓取所有源
    const results = await Promise.all(SOURCE_URLS.map(u => fetchOneSource(u)));
    const successCount = results.filter(r => r.error === null).length;
    const totalChannels = results.reduce((sum, r) => sum + r.channels.length, 0);
    console.log(`[loadAllChannels] ${successCount}/${results.length} sources OK, ${totalChannels} channels`);

    const merged = [];
    for (const result of results) {
        for (const ch of result.channels) {
            merged.push({ ...ch });
        }
    }

    console.log(`[loadAllChannels] ${merged.length} channels merged (no dedup)`);

    // 3. 异步写回 KV（不阻塞响应）
    // Workers 中 fetch 返回后继续 I/O 必须用 ctx.waitUntil，不能用 setTimeout
    const writeKV = async () => {
        if (!env || !env.KV) return;
        try {
            const cacheData = {
                channels: merged,
                expireAt: Date.now() + CACHE_TTL_MS,
            };
            await env.KV.put(KV_CACHE_KEY, JSON.stringify(cacheData), {
                expirationTtl: KV_TTL_SECONDS,
            });
            console.log(`[loadAllChannels] KV cache written, ${merged.length} channels`);
        } catch (e) {
            console.error(`[loadAllChannels] KV write error: ${e.message}`);
        }
    };

    if (ctx && typeof ctx.waitUntil === "function") {
        ctx.waitUntil(writeKV());
    } else {
        // 本地/兜底：直接 await（会略微增加响应时间）
        await writeKV();
    }

    return merged;
}

// ---------- Vod 构造 ----------

function buildPromoVods() {
    return PROMO_LIST.map((p, idx) => ({
        vod_id:        `live_promo_${idx}`,
        vod_name:      p.title,
        vod_pic:       p.pic || "",
        vod_remarks:   p.remarks || "引流",
        vod_play_from: p.from  || "推广线路",
        vod_play_url:  `${p.title}$${p.url}`,
        type_name:     p.group || "📢 频道关注",
    }));
}

function channelToVod(ch, idx) {
    const playUrl = ch.urls && ch.urls.length > 1
        ? `${ch.title}$${ch.urls.join('#')}`
        : `${ch.title}$${ch.url}`;
    return {
        vod_id:        `ch_${idx}`,
        vod_name:      ch.title,
        vod_pic:       ch.logo,
        vod_remarks:   "直播",
        vod_play_from: ch.group,
        vod_play_url:  playUrl,
        type_name:     ch.group,
    };
}

// ---------- 响应构造 ----------

function buildHomeResponse(channels) {
    const groupMap = new Map();
    channels.forEach((ch, i) => {
        if (!groupMap.has(ch.group)) groupMap.set(ch.group, []);
        groupMap.get(ch.group).push({ ch, i });
    });

    const promoGroups = Array.from(new Set(PROMO_LIST.map(p => p.group || "📢 频道关注")));
    const otherGroups = Array.from(groupMap.keys()).filter(g => !promoGroups.includes(g));
    const allGroups = [...promoGroups, ...otherGroups];

    const class_list = allGroups.map(g => ({ type_id: g, type_name: g }));

    const promoVods = buildPromoVods();
    const groupVods = [];
    for (const g of otherGroups) {
        const items = (groupMap.get(g) || []).slice(0, 5);
        for (const { ch, i } of items) groupVods.push(channelToVod(ch, i));
    }

    return { class: class_list, list: [...promoVods, ...groupVods] };
}

function buildCategoryResponse(channels, typeId, page, pageSize) {
    if (!typeId) {
        return { page: 1, pagecount: 1, limit: pageSize, total: 0, list: [], notice: "typeId (参数 t) 不能为空" };
    }

    const promoGroups = new Set(PROMO_LIST.map(p => p.group || "📢 频道关注"));
    const list = [];

    if (promoGroups.has(typeId)) {
        list.push(...buildPromoVods().filter(v => v.type_name === typeId));
    }
    channels.forEach((ch, i) => {
        if (ch.group === typeId) list.push(channelToVod(ch, i));
    });

    const total = Math.min(list.length, MAX_RETURN_LIMIT);
    const totalPage = Math.max(1, Math.ceil(total / pageSize));
    const safePage = Math.min(page, totalPage);
    const start = (safePage - 1) * pageSize;

    return {
        page: safePage,
        pagecount: totalPage,
        limit: pageSize,
        total,
        list: list.slice(start, start + pageSize),
    };
}

function buildDetailResponse(channels, ids) {
    const idSet = new Set(ids);
    const list = [];

    for (const v of buildPromoVods()) {
        if (idSet.has(v.vod_id)) list.push(v);
    }
    channels.forEach((ch, i) => {
        const vodId = `ch_${i}`;
        if (idSet.has(vodId)) list.push(channelToVod(ch, i));
    });

    return { list };
}

function buildM3U(channels) {
    const lines = ['#EXTM3U'];
    for (const p of PROMO_LIST) {
        lines.push(`#EXTINF:-1 tvg-logo="${p.pic || ''}" group-title="${p.group || '📢 频道关注'}",${p.title}`);
        lines.push(p.url);
    }
    for (const ch of channels) {
        lines.push(`#EXTINF:-1 tvg-logo="${ch.logo}" group-title="${ch.group}",${ch.title}`);
        lines.push(ch.urls && ch.urls.length > 1 ? ch.urls.join(',') : ch.url);
    }
    return lines.join('\n');
}

function buildTXT(channels) {
    const groupMap = new Map();
    for (const p of PROMO_LIST) {
        const g = p.group || "📢 频道关注";
        if (!groupMap.has(g)) groupMap.set(g, []);
        groupMap.get(g).push({ title: p.title, url: p.url });
    }
    for (const ch of channels) {
        if (!groupMap.has(ch.group)) groupMap.set(ch.group, []);
        const u = ch.urls && ch.urls.length > 0 ? ch.urls[0] : ch.url;
        groupMap.get(ch.group).push({ title: ch.title, url: u });
    }
    const out = [];
    for (const [group, items] of groupMap.entries()) {
        out.push(`${group},#genre#`);
        for (const it of items) out.push(`${it.title},${it.url}`);
        out.push('');
    }
    return out.join('\n');
}

// ---------- 主入口 ----------

const corsHeaders = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "*",
};

function jsonResponse(obj, status = 200) {
    return new Response(JSON.stringify(obj), {
        status,
        headers: { ...corsHeaders, "Content-Type": "application/json; charset=utf-8" },
    });
}

export default {
    async fetch(request, env, ctx) {
        const url = new URL(request.url);
        const path = url.pathname;
        const params = url.searchParams;

        if (request.method === "OPTIONS") {
            return new Response(null, { headers: corsHeaders });
        }

        try {
            const channels = await loadAllChannels(env, ctx);

            if (path === '/m3u' || path === '/live.m3u') {
                return new Response(buildM3U(channels), {
                    headers: { ...corsHeaders, "Content-Type": "audio/x-mpegurl; charset=utf-8" },
                });
            }

            if (path === '/txt' || path === '/live.txt') {
                return new Response(buildTXT(channels), {
                    headers: { ...corsHeaders, "Content-Type": "text/plain; charset=utf-8" },
                });
            }

            const ac = params.get('ac');

            if (ac === 'detail') {
                const ids = (params.get('ids') || '').split(',').filter(Boolean);
                return jsonResponse(buildDetailResponse(channels, ids));
            }

            if (ac === 'list' || params.has('t')) {
                const typeId = params.get('t') || '';
                const page = parseInt(params.get('pg') || '1', 10) || 1;
                const size = parseInt(params.get('limit') || String(DEFAULT_PAGE_SIZE), 10) || DEFAULT_PAGE_SIZE;
                return jsonResponse(buildCategoryResponse(channels, typeId, page, size));
            }

            return jsonResponse(buildHomeResponse(channels));

        } catch (err) {
            console.error(`[fetch] Unhandled error: ${err.message}`);
            return jsonResponse({ error: true, message: err.message || String(err) }, 500);
        }
    },
};
