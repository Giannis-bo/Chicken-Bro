import json
import re

try:
    from .llm_client import call_chat_completion, llm_configured
except ImportError:
    from llm_client import call_chat_completion, llm_configured


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

VISIBLE_TERM_TRANSLATIONS = [
    ("Trading Post", "商栈"),
    ("Traveler's Log", "旅行者日志"),
    ("Flame-Painted Sun Roc", "焰绘太阳洛克"),
    ("Omnium Folio", "全能典籍"),
    ("WoW Ambassadors", "魔兽大使"),
    ("WoW Ambassador", "魔兽大使"),
    ("Blizzard News", "暴雪新闻"),
]


def has_cjk(value):
    return bool(re.search(r"[\u4e00-\u9fff]", value or ""))


def compact_space(value):
    return re.sub(r"\s+", " ", value or "").strip()


def untranslated_word_count(value):
    return len(re.findall(r"\b[A-Za-z]{3,}\b", value or ""))


def chinese_display_text(value, max_english_words):
    text = compact_space(value)
    return bool(text and has_cjk(text) and untranslated_word_count(text) <= max_english_words)


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


def localize_visible_terms(value):
    text = compact_space(value)
    for source, target in VISIBLE_TERM_TRANSLATIONS:
        text = re.sub(re.escape(source), target, text, flags=re.I)
    return text


def translate_summary(summary, title=""):
    text = compact_space(summary or title)
    if not text or has_cjk(text):
        return text

    if re.search(r"Here you will find a list of hotfixes", text, flags=re.I):
        expansion_match = re.search(r"World of Warcraft(?::\s*([^\.…]+))?", text, flags=re.I)
        expansion = expansion_match.group(1).strip() if expansion_match and expansion_match.group(1) else ""
        suffix = f"：{expansion}" if expansion else ""
        return localize_visible_terms(f"这里会列出解决《魔兽世界》{suffix}相关问题的官方热修。")

    ptr_match = re.search(r"PTR development notes.*class tuning", text, flags=re.I)
    if ptr_match:
        return "暴雪发布了新的 PTR 开发说明，其中包含职业调优内容。"

    translated = translate_fragment(text)
    if translated == text:
        return "这条资讯来自官方来源，原文摘录已保留在详情页，可结合原文链接查看完整上下文。"
    if untranslated_word_count(translated) > 6:
        return "这条资讯来自官方来源，原文摘录已保留在详情页，可结合原文链接查看完整上下文。"
    return localize_visible_terms(translated)


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


def strip_json_fence(value):
    text = compact_space(value)
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_llm_json(value):
    text = strip_json_fence(value)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def normalize_llm_translation(payload):
    if not isinstance(payload, dict):
        return None

    title = compact_space(payload.get("title", ""))
    summary = compact_space(payload.get("summary", ""))
    body_zh = compact_space(payload.get("bodyZh") or payload.get("body", ""))
    if not chinese_display_text(title, 3):
        return None
    if not chinese_display_text(summary, 6):
        return None
    if not chinese_display_text(body_zh, 10):
        return None
    if "中文正文" not in body_zh:
        body_zh = f"中文正文：{body_zh}"
    return {
        "title": localize_visible_terms(title),
        "summary": localize_visible_terms(summary),
        "bodyZh": localize_visible_terms(body_zh),
    }


def visible_translation_issues(articles):
    thresholds = {"title": 3, "summary": 6, "bodyZh": 6}
    issues = []
    for article in articles:
        article_id = article.get("id", "")
        for field, max_english_words in thresholds.items():
            value = compact_space(article.get(field, ""))
            if not value:
                issues.append({"id": article_id, "field": field, "reason": "missing visible text"})
                continue
            if not has_cjk(value):
                issues.append({"id": article_id, "field": field, "reason": "missing Chinese text"})
                continue
            english_words = untranslated_word_count(value)
            if english_words > max_english_words:
                issues.append(
                    {
                        "id": article_id,
                        "field": field,
                        "reason": f"too many untranslated English words: {english_words}",
                    }
                )
    return issues


def should_use_llm_translation():
    return llm_configured()


def truncate_for_llm(value, limit):
    text = str(value or "")
    if len(text) <= limit:
        return text
    return f"{text[:limit]} [truncated]"


def translate_article_with_llm(article):
    if not should_use_llm_translation():
        return None

    original_title = truncate_for_llm(article.get("originalTitle") or article.get("title", ""), 200)
    original_summary = truncate_for_llm(article.get("originalSummary") or article.get("summary", ""), 1000)
    original_body = truncate_for_llm(article.get("originalBody") or article.get("body") or article.get("summary", ""), 3000)

    prompt = "\n".join(
        [
            "请把这条魔兽世界资讯完整改写为中文展示内容。",
            "只返回 JSON，不要 Markdown，不要解释。",
            "JSON schema: {\"title\":\"中文标题\",\"summary\":\"中文摘要\",\"bodyZh\":\"中文正文\"}",
            "要求：title、summary、bodyZh 必须主要为中文；专有名词可以保留英文；不要编造原文没有的信息；不要翻译 sourceUrl。",
            "",
            f"原始标题：{original_title}",
            f"原始摘要：{original_summary}",
            f"原始正文摘录：{original_body}",
            f"频道：{article.get('channel', '')}",
            f"分类：{article.get('category', '')}",
            f"来源：{article.get('sourceName', '')} {article.get('sourceUrl', '')}",
            f"发布日期：{article.get('publishedAt', '')}",
        ]
    )
    result = call_chat_completion(
        "你是面向中文魔兽世界玩家的资讯编辑。你的任务是忠实翻译和本地化英文资讯，输出可直接展示在小程序里的中文内容。",
        prompt,
        temperature=0.1,
    )
    if result.get("error") or not result.get("content"):
        return None
    return parse_llm_json(result["content"])


def localize_article(article, translate_with_llm=None):
    original_title = article.get("originalTitle") or article.get("title", "")
    original_summary = article.get("originalSummary") or article.get("summary", "")
    original_body = article.get("originalBody") or article.get("body") or original_summary or original_title

    title = translate_title(article.get("title", original_title))
    summary = translate_summary(article.get("summary", original_summary), original_title)
    body_zh = article.get("bodyZh") or build_body_zh(article, summary)
    translator = translate_with_llm
    if translator is None and should_use_llm_translation():
        translator = translate_article_with_llm

    localized = dict(article)
    localized.update(
        {
            "title": localize_visible_terms(title),
            "summary": localize_visible_terms(summary),
            "bodyZh": localize_visible_terms(body_zh),
            "originalTitle": compact_space(original_title),
            "originalSummary": compact_space(original_summary),
            "originalBody": compact_space(original_body),
        }
    )
    if translator:
        llm_translation = normalize_llm_translation(translator(localized))
        if llm_translation:
            localized.update(llm_translation)
    return localized
