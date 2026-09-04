#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""canonical.py —— 频道名称规范化：全场唯一的「命名真相来源」。

背景（本模块存在的理由）：
    上游源对同一个频道有 N 种写法，改名不一致会让「同名去重」彻底失效 ——
    一个频道在 tv.txt 里散落十几条别名，分组顺序也被打乱。典型症状：

        CCTV-1 / CCTV-1 综合 / CCTV1 / CCTV-1(720p)
        CCTV-世界地理 / CCTV世界地理 / CCTV-World Geography
        CCTV-央视台球 / CCTV央视台球 / CCTV-Billiards
        CGTN-法语 / CGTN法语 / CGTN French (1080p)
        CHC-动作电影 / CHC动作电影 / CHC动作影院
        「中」翁立友-独身仔的生活 —— 歌曲点播，却因含「生活」掉进生活频道

规范后的形态：
        央视主频道   CCTV-1 综合 …… CCTV-17 农业农村（裸号自动补官方副名）
        央视付费     CCTV-风云足球 / CCTV-世界地理（中英文写法合并到中文）
        超高清       CCTV-4K / CGTN-4K 系（CCTV-4 4K / CCTV-4K 不再并存）
        CGTN         CGTN / CGTN-法语 / CGTN-西班牙语 / CGTN-阿拉伯语
                     / CGTN-俄语 / CGTN-纪录 / CGTN-财经（CGTN-新闻 == CGTN）
        CETV         CETV-1 …… CETV-4
        CHC          CHC-动作电影 / CHC-家庭影院 / CHC-影迷电影

设计约束：
    * 零依赖（仅标准库），且**绝不 import grouping** —— 避免循环导入。
      grouping.py / aggregate.py / normalize_tv.py 都单向依赖本模块。
    * canonical_name() 对未收录的频道只是「剥离清晰度标签 + 压空白」，
      原样返回，可安全地对所有条目调用。
    * 清晰度标签默认剥离。需要保留实测标签时用 canonical_name_keep_label()，
      它会先摘下 (1080p) 再挂回规范名之后：CCTV-1 综合(1080p)。

自检：python scripts/canonical.py
"""
import re

# ==================== [0] 通用清洗工具 ====================

# 清晰度 / 制式标签：判归属前、去重前都要先剥离
_RES_SUFFIX_RE = re.compile(
    r"[\(（]\s*\d{2,4}\s*[ip]?\s*[\)）]"      # (1080p) （720P）
    r"|\bHD\b|\bUHD\b|\bFHD\b|\b4K\b|\b8K\b"  # HD / UHD / 4K
    r"|高清|超清|标清|蓝光",
    re.I,
)
_WS_RE = re.compile(r"\s+")
_TAIL_SEP_RE = re.compile(r"[\s\-_－]+$")
_HEAD_SEP_RE = re.compile(r"^[\s\-_－]+")
_CLARITY_TAG_RE = re.compile(r"[\(（]\s*(\d{3,4})\s*[ip]\s*[\)）]", re.I)


def strip_clarity(name: str) -> str:
    """剥离清晰度 / 制式标签，压平空白，去掉首尾残留分隔符。"""
    n = _RES_SUFFIX_RE.sub("", name or "")
    n = _WS_RE.sub(" ", n).strip()
    n = _TAIL_SEP_RE.sub("", n)
    return _HEAD_SEP_RE.sub("", n).strip()


def split_clarity(name: str):
    """拆成 (基准名, 清晰度标签)；无标签时标签为空串。"""
    n = (name or "").strip()
    m = _CLARITY_TAG_RE.search(n)
    if not m:
        return n, ""
    return strip_clarity(n), m.group(1).lower() + "p"


def _norm_en(s: str) -> str:
    """英文后缀归一：小写、& → and、去所有格，便于查表。"""
    s = (s or "").lower().replace("&", " and ").replace("'", "")
    return _WS_RE.sub(" ", s).strip()


# ==================== [1] 央视频道 ====================

_CCTV_NUM_RE = re.compile(r"^CCTV\s*[-_\s]?\s*(\d{1,2})", re.I)

# 主频官方副名（裸号 CCTV-1 → CCTV-1 综合）
_CCTV_MAIN_SUB = {
    1: "综合", 2: "财经", 3: "综艺", 4: "中文国际", 5: "体育",
    6: "电影", 7: "国防军事", 8: "电视剧", 9: "纪录", 10: "科教",
    11: "戏曲", 12: "社会与法", 13: "新闻", 14: "少儿", 15: "音乐",
    16: "奥林匹克", 17: "农业农村",
}

# CCTV-5+ 这类「+」频道是独立频道，裸写时补官方副名
_CCTV_PLUS_SUB = {5: "体育赛事"}

# 副名同义归一：把上游的花式写法收敛到官方形态
_CCTV_SUB_ALIAS = {
    "中文国际": "中文国际", "中文": "中文国际", "国际": "中文国际",
    "综合": "综合", "新闻": "新闻", "体育": "体育", "体育赛事": "体育赛事",
    "电影": "电影", "电影频道": "电影", "电视剧": "电视剧", "电视剧频道": "电视剧",
    "纪录": "纪录", "纪录频道": "纪录", "科教": "科教", "科学教育": "科教",
    "戏曲": "戏曲", "社会与法": "社会与法", "少儿": "少儿", "少儿频道": "少儿",
    "音乐": "音乐", "农业农村": "农业农村", "农业": "农业农村",
    "国防军事": "国防军事", "军事": "国防军事", "军事农业": "国防军事",
    "奥林匹克": "奥林匹克", "奥运": "奥林匹克", "奥林匹克频道": "奥林匹克",
    "欧洲": "欧洲", "美洲": "美洲", "高清": "高清",
}

# 央视付费 / 数字频道的英文名 → 官方中文名（中英文写法合并的关键）
_CCTV_EN2CN = {
    "billiards": "央视台球",
    "culture of quality": "文化精品",
    "golf and tennis": "高尔夫网球",
    "health": "卫生健康",
    "nostalgia theater": "怀旧剧场",
    "storm football": "风云足球",
    "storm music": "风云音乐",
    "storm theater": "风云剧场",
    "the first theater": "第一剧场",
    "weapon and technology": "兵器科技",
    "womens fashion": "女性时尚",
    "world geography": "世界地理",
}

# 中文付费频道的别名归一（台球 / 央视台球 是同一套付费频道）
_CCTV_PAY_ALIAS = {
    "台球": "央视台球", "央视台球": "央视台球",
    "卫生健康": "卫生健康", "健康": "卫生健康",
    "电视指南": "电视指南", "指南": "电视指南",
    # 上游常见的缩写 / 赘余前缀写法
    "央视文化精品": "文化精品", "文化精品": "文化精品",
    "央视高网": "高尔夫网球", "高网": "高尔夫网球",
    "央视高尔夫": "高尔夫网球", "高尔夫": "高尔夫网球",
}


def _cctv_pay_body(n: str) -> str:
    """无编号央视频道（CCTV-风云足球 / CCTV世界地理 / CCTV-央视台球）。"""
    body = re.sub(r"^(CCTV|央视)\s*", "", n, flags=re.I).strip()
    body = strip_clarity(body)
    body = _HEAD_SEP_RE.sub("", body).strip()

    # 纯英文：查表翻译，未收录则原样返回（不臆造中文名）
    if body and not re.search(r"[\u4e00-\u9fff]", body):
        cn = _CCTV_EN2CN.get(_norm_en(body))
        return f"CCTV-{cn}" if cn else n

    body = _CCTV_PAY_ALIAS.get(body, body)
    prefix = "CCTV" if re.match(r"^CCTV", n, re.I) else "央视"
    return f"{prefix}-{body}" if body else n


def canonical_cctv(name: str) -> str:
    """统一央视频道命名；非央视频道原样返回（判定口径与 grouping.is_central 一致）。"""
    n = (name or "").strip()
    if not n:
        return n

    # 1. CETV / 中国教育电视台
    if re.search(r"CETV|中国教育|中央教育", n, re.I):
        m = re.search(r"CETV\s*[-_]?\s*(\d)", n, re.I)
        return f"CETV-{m.group(1) if m else '1'}"

    # 2. CGTN（含英文后缀变体）
    if re.match(r"^CGTN", n, re.I):
        return canonical_cgtn(n)

    if not re.match(r"^(CCTV|央视)", n, re.I):
        return n

    # 3. 4K / 8K 超高清：CCTV-4K / CCTV4K / CCTV-4 4K → CCTV-4K
    m_k = re.match(r"^CCTV\s*[-_]?\s*(\d)\s*[Kk]\b", n, re.I)
    if m_k:
        return f"CCTV-{m_k.group(1)}K"

    # 4. 带编号：CCTV1 / CCTV-1 / CCTV-1 综合 / CCTV-5+体育赛事
    m = _CCTV_NUM_RE.match(n)
    if m:
        num = int(m.group(1))
        raw_rest = n[m.end():]
        # CCTV-4 4K / CCTV-8 8K：源端对超高清频道的写法，先于 strip 捕获
        # （strip_clarity 会把 4K/8K 当标签剥掉，导致退化成 CCTV-4 中文国际）
        mk = re.match(r"^[\s\-_]*(4K|8K)\b", raw_rest, re.I)
        if mk:
            # 频道号取自 K 前的数字本身（CCTV-4 4K == CCTV-4K），不再拼主频号
            return f"CCTV-{mk.group(1).upper()}"
        rest = _HEAD_SEP_RE.sub("", strip_clarity(raw_rest)).strip()

        # CCTV-5+ / CCTV-5⁺ 体育赛事
        if rest.startswith(("+", "⁺")):
            sub = rest.lstrip("+⁺").strip()
            sub = _CCTV_SUB_ALIAS.get(sub, sub) or _CCTV_PLUS_SUB.get(num, "")
            # CCTV-5+ 官方全称是「CCTV-5+ 体育赛事」，裸写 CCTV-5+ 会产生第二套名字
            return f"CCTV-{num}+ {sub}" if sub else f"CCTV-{num}+"

        # CCTV-4 4K / CCTV-8 8K：实为超高清频道，避免与主频混淆
        if rest.upper() in ("4K", "8K"):
            return f"CCTV-{num}{rest.upper()}"

        # 裸号：补官方副名（CCTV-1 → CCTV-1 综合）
        if not rest:
            sub = _CCTV_MAIN_SUB.get(num)
            return f"CCTV-{num} {sub}" if sub else f"CCTV-{num}"

        sub = _CCTV_SUB_ALIAS.get(rest, rest)
        return f"CCTV-{num} {sub}" if sub else f"CCTV-{num}"

    # 5. 无编号付费 / 数字频道
    return _cctv_pay_body(n)


# ==================== [2] CGTN ====================

_CGTN_ZH = {
    "法语": "法语", "法文": "法语", "french": "法语",
    "西班牙语": "西班牙语", "西语": "西班牙语", "spanish": "西班牙语",
    "阿拉伯语": "阿拉伯语", "阿语": "阿拉伯语", "arabic": "阿拉伯语",
    "俄语": "俄语", "russian": "俄语",
    "纪录": "纪录", "记录": "纪录", "外语纪录": "纪录", "documentary": "纪录",
    "纪录频道": "纪录",
    "新闻": "新闻", "news": "新闻",
    "财经": "财经", "全球财经": "财经",
    "global biz": "财经", "global business": "财经",
}


def canonical_cgtn(name: str) -> str:
    """CGTN 归一：CGTN-新闻 == CGTN（主频即英语新闻频道），英文后缀 → 中文。"""
    n = (name or "").strip()
    if not re.match(r"^CGTN", n, re.I):
        return n
    rest = _HEAD_SEP_RE.sub("", strip_clarity(n[4:])).strip()
    if not rest:
        return "CGTN"
    zh = _CGTN_ZH.get(rest) or _CGTN_ZH.get(_norm_en(rest))
    if not zh:
        return f"CGTN-{rest}"
    return "CGTN" if zh == "新闻" else f"CGTN-{zh}"


# ==================== [3] CHC 电影频道 ====================

_CHC_RE = re.compile(r"^CHC\s*[-－_]?\s*(.*)$", re.I)
# 官方只有三条：动作电影 / 家庭影院 / 影迷电影
_CHC_CANON = (
    ("动作", "CHC-动作电影"),
    ("家庭", "CHC-家庭影院"),
    ("影迷", "CHC-影迷电影"),
)


def canonical_chc(name: str) -> str:
    """CHC 归一：CHC动作影院 / CHC-动作电影 / CHC 动作电影 → CHC-动作电影。"""
    n = (name or "").strip()
    m = _CHC_RE.match(n)
    if not m:
        return n
    body = strip_clarity(m.group(1)).strip()
    for kw, canon in _CHC_CANON:
        if kw in body:
            return canon
    return "CHC" if not body else n


# ==================== [4] 主入口 ====================

def canonical_name(name: str) -> str:
    """统一频道名称（剥离清晰度标签）。非目标频道仅做清洗后原样返回。"""
    n = _WS_RE.sub(" ", (name or "").strip())
    if not n:
        return n

    # 央视 / CGTN / CETV：内部自行处理 4K、英文后缀等特例
    # ★ 命中中央台的，即使归一结果与原名相同也必须直接返回：
    #   否则会掉到末尾的 strip_clarity，把 CCTV-4K 的「4K」当标签剥离成 CCTV。
    c = canonical_cctv(n)
    if c != n or re.match(r"^(CCTV|CGTN|CETV|央视)", n, re.I):
        return c

    # CHC 系列
    c = canonical_chc(n)
    if c != n or re.match(r"^CHC", n, re.I):
        return c

    # 其余频道：仅剥离清晰度标签（浙江卫视(1080p) → 浙江卫视，与裸名合并）
    cleaned = strip_clarity(n)
    return cleaned or n


def canonical_name_keep_label(name: str) -> str:
    """规范化但保留实测清晰度标签：CCTV-1 综合(1080p)。

    aggregate 的抓流实测会把真实分辨率写回名称（relabel_name），
    若此处直接剥掉，probe 的修正成果就白测了 —— 所以先摘下标签再挂回去。
    """
    base, label = split_clarity(name)
    out = canonical_name(base)
    if label and f"({label})" not in out:
        return f"{out}({label})"
    return out


# ==================== [5] 自检 ====================

_CASES = [
    # 央视主频：裸号补副名，写法统一
    ("CCTV-1", "CCTV-1 综合"), ("CCTV1", "CCTV-1 综合"),
    ("CCTV-1 综合", "CCTV-1 综合"), ("CCTV-1(720p)", "CCTV-1 综合"),
    ("CCTV-1 -综合", "CCTV-1 综合"),
    ("CCTV-5+", "CCTV-5+ 体育赛事"), ("CCTV-5⁺体育赛事", "CCTV-5+ 体育赛事"),
    ("CCTV5+", "CCTV-5+ 体育赛事"),
    ("CCTV-4 欧洲", "CCTV-4 欧洲"), ("CCTV-4中文国际", "CCTV-4 中文国际"),
    ("CCTV-4K", "CCTV-4K"), ("CCTV-4 4K", "CCTV-4K"),
    ("CCTV-8 8K", "CCTV-8K"), ("CCTV-6 电影", "CCTV-6 电影"),
    ("CCTV-17", "CCTV-17 农业农村"),
    # 央视付费：中英文合并 + 去重复前缀
    ("CCTV世界地理", "CCTV-世界地理"), ("CCTV-世界地理", "CCTV-世界地理"),
    ("CCTV-World Geography", "CCTV-世界地理"),
    ("CCTV央视台球", "CCTV-央视台球"), ("CCTV-央视台球", "CCTV-央视台球"),
    ("CCTV台球", "CCTV-央视台球"), ("CCTV-Billiards", "CCTV-央视台球"),
    ("CCTV风云足球", "CCTV-风云足球"), ("CCTV-Storm Football", "CCTV-风云足球"),
    ("CCTV卫生健康", "CCTV-卫生健康"), ("CCTV-Health", "CCTV-卫生健康"),
    ("央视精品", "央视-精品"),
    # CGTN
    ("CGTN", "CGTN"), ("CGTN-新闻", "CGTN"), ("CGTN News", "CGTN"),
    ("CGTN法语", "CGTN-法语"), ("CGTN-法语", "CGTN-法语"),
    ("CGTN French (1080p)", "CGTN-法语"),
    ("CGTN西语", "CGTN-西班牙语"), ("CGTN-西班牙语", "CGTN-西班牙语"),
    ("CGTN阿语", "CGTN-阿拉伯语"), ("CGTN阿拉伯语", "CGTN-阿拉伯语"),
    ("CGTN俄语", "CGTN-俄语"), ("CGTN俄语 (1080p)", "CGTN-俄语"),
    ("CGTN纪录", "CGTN-纪录"), ("CGTN-外语纪录", "CGTN-纪录"),
    ("CGTN Global Biz (1080p)", "CGTN-财经"),
    # CETV
    ("CETV-1", "CETV-1"), ("中国教育电视台", "CETV-1"), ("CETV2", "CETV-2"),
    # CHC
    ("CHC-动作电影", "CHC-动作电影"), ("CHC动作电影", "CHC-动作电影"),
    ("CHC动作影院", "CHC-动作电影"), ("CHC 动作电影", "CHC-动作电影"),
    ("CHC家庭影院", "CHC-家庭影院"), ("CHC-家庭影院", "CHC-家庭影院"),
    ("CHC家庭电影", "CHC-家庭影院"), ("CHC影迷电影", "CHC-影迷电影"),
    # 非央视：只清洗，不改名
    ("浙江卫视(1080p)", "浙江卫视"), ("湖南卫视 HD", "湖南卫视"),
    ("忻州综合", "忻州综合"), ("翁立友-独身仔的生活", "翁立友-独身仔的生活"),
    ("Alin精选16首(1小时)", "Alin精选16首(1小时)"),
]


def _selftest():
    ok = fail = 0
    for src, want in _CASES:
        got = canonical_name(src)
        if got == want:
            ok += 1
        else:
            fail += 1
            print(f"[FAIL] {src!r} -> {got!r}（期望 {want!r}）")
    # 保留标签的入口
    for src, want in [("CCTV-1 综合(1080p)", "CCTV-1 综合(1080p)"),
                      ("CCTV1(720p)", "CCTV-1 综合(720p)"),
                      ("CHC动作电影(1080p)", "CHC-动作电影(1080p)")]:
        got = canonical_name_keep_label(src)
        if got == want:
            ok += 1
        else:
            fail += 1
            print(f"[FAIL] keep_label {src!r} -> {got!r}（期望 {want!r}）")
    print(f"[SELFTEST] canonical.py：通过 {ok} 项，失败 {fail} 项")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_selftest())
