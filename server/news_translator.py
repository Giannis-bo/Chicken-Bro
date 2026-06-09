import re


MONTHS = {
    "january": "1",
    "february": "2",
    "march": "3",
    "april": "4",
    "may": "5",
    "june": "6",
    "july": "7",
    "august": "8",
    "september": "9",
    "october": "10",
    "november": "11",
    "december": "12",
}

TERM_TRANSLATIONS = [
    ("World of Warcraft", "《魔兽世界》"),
    ("The War Within", "地心之战"),
    ("Midnight Revelations", "Midnight: Revelations"),
    ("Midnight: Revelations", "Midnight: Revelations"),
    ("Midnight", "Midnight"),
    ("Mists of Pandaria Classic", "《熊猫人之谜》经典怀旧服"),
    ("Trading Post", "商栈"),
    ("Traveler's Log", "旅行者日志"),
    ("Public Test Realm", "PTR 测试服"),
    ("Development Notes", "开发说明"),
    ("Class Tuning", "职业调优"),
    ("Class Changes", "职业改动"),
    ("Hotfixes", "热修"),
    ("hotfixes", "热修"),
    ("content update", "内容更新"),
    ("raid", "团队副本"),
    ("rewards", "奖励"),
    ("now live", "现已开放"),
    ("players", "玩家"),
    ("issues", "问题"),
]


def has_cjk(value):
    return bool(re.search(r"[\u4e00-\u9fff]", value or ""))


def compact_space(value):
    return re.sub(r"\s+", " ", value or "").strip()


def untranslated_word_count(value):
    return len(re.findall(r"\b[A-Za-z]{3,}\b", value or ""))


def zh_date_from_english(value):
    match = re.search(
        r"\b("
        + "|".join(MONTHS.keys())
        + r")\s+(\d{1,2}),\s+(\d{4})\b",
        value or "",
        flags=re.I,
    )
    if not match:
        return ""
    month = MONTHS[match.group(1).lower()]
    return f"{match.group(3)} 年 {month} 月 {int(match.group(2))} 日"


def translate_title(title):
    text = compact_space(title)
    if not text or has_cjk(text):
        return text

    if re.search(r"^hotfixes:", text, flags=re.I):
        date_text = zh_date_from_english(text)
        return f"官方热修：{date_text}" if date_text else "官方热修更新"

    if re.search(r"this week in wow", text, flags=re.I):
        return "本周 WoW 动态汇总"

    if re.search(r"trading post", text, flags=re.I):
        translated = translate_fragment(text)
        translated = re.sub(r"take a", "来一场", translated, flags=re.I)
        translated = re.sub(r"over to", "前往", translated, flags=re.I)
        translated = re.sub(r"midsummer", "仲夏", translated, flags=re.I)
        translated = re.sub(r"stroll", "漫步", translated, flags=re.I)
        translated = re.sub(r"\bthe\b", "", translated, flags=re.I)
        translated = re.sub(r"\bjune\b", "六月", translated, flags=re.I)
        return translated

    translated = translate_fragment(text)
    if translated == text:
        return "暴雪官方资讯更新"
    if untranslated_word_count(translated) > 2:
        return "暴雪官方资讯更新"
    return translated


def translate_fragment(value):
    text = compact_space(value)
    for source, target in TERM_TRANSLATIONS:
        text = re.sub(re.escape(source), target, text, flags=re.I)
    text = re.sub(r"\bgoes live\b", "上线", text, flags=re.I)
    text = re.sub(r"\bnow available\b", "现已上线", text, flags=re.I)
    text = re.sub(r"\bwith\b", "，包含", text, flags=re.I)
    text = re.sub(r"\band\b", "和", text, flags=re.I)
    return text


def translate_summary(summary, title=""):
    text = compact_space(summary or title)
    if not text or has_cjk(text):
        return text

    if re.search(r"Here you will find a list of hotfixes", text, flags=re.I):
        expansion_match = re.search(r"World of Warcraft(?::\s*([^\.…]+))?", text, flags=re.I)
        expansion = expansion_match.group(1).strip() if expansion_match and expansion_match.group(1) else ""
        suffix = f"：{expansion}" if expansion else ""
        return f"这里会列出解决《魔兽世界》{suffix}相关问题的官方热修。"

    ptr_match = re.search(r"PTR development notes.*class tuning", text, flags=re.I)
    if ptr_match:
        return "暴雪发布了新的 PTR 开发说明，其中包含职业调优内容。"

    translated = translate_fragment(text)
    if translated == text:
        return "这条资讯来自官方来源，原文摘录已保留在详情页，可结合原文链接查看完整上下文。"
    if untranslated_word_count(translated) > 6:
        return "这条资讯来自官方来源，原文摘录已保留在详情页，可结合原文链接查看完整上下文。"
    return translated


def build_body_zh(article, translated_summary):
    source_name = article.get("sourceName", "官方来源")
    channel = article.get("channel", "资讯")
    category = article.get("category", "未分类")
    published_at = article.get("publishedAt", "")
    body = [
        f"中文正文：{translated_summary}",
        f"这条内容来自{source_name}，归入「{channel}」频道，分类为「{category}」。",
    ]
    if published_at:
        body.append(f"页面发布日期为 {published_at}，适合在查看原文前快速掌握本条资讯的核心信息。")
    return "\n\n".join(body)


def localize_article(article):
    original_title = article.get("originalTitle") or article.get("title", "")
    original_summary = article.get("originalSummary") or article.get("summary", "")
    original_body = article.get("originalBody") or article.get("body") or original_summary or original_title

    title = translate_title(article.get("title", original_title))
    summary = translate_summary(article.get("summary", original_summary), original_title)
    body_zh = article.get("bodyZh") or build_body_zh(article, summary)

    localized = dict(article)
    localized.update(
        {
            "title": title,
            "summary": summary,
            "bodyZh": body_zh,
            "originalTitle": compact_space(original_title),
            "originalSummary": compact_space(original_summary),
            "originalBody": compact_space(original_body),
        }
    )
    return localized
