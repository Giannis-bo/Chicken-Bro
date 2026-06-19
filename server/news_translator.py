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

TAG_LABELS = {
    "retail": "正式服",
    "content-update": "内容更新",
    "patch-notes": "补丁说明",
    "hotfix": "热修",
    "class-change": "职业调整",
    "ptr": "测试服",
    "weekly": "周报",
    "event": "活动",
    "raid": "团队副本",
    "trading-post": "商栈",
    "season": "赛季",
    "rewards": "奖励",
    "official": "官方",
}

TAG_KEYWORDS = [
    ("retail", ("retail", "正式服")),
    ("hotfix", ("hotfix", "热修")),
    ("patch-notes", ("patch notes", "development notes", "补丁说明", "开发说明")),
    ("class-change", ("class tuning", "class changes", "职业", "调优", "平衡")),
    ("ptr", ("ptr", "public test realm", "beta", "测试服")),
    ("trading-post", ("trading post", "商栈", "traveler's log", "旅行者日志")),
    ("raid", ("raid", "团队副本")),
    ("season", ("season", "赛季")),
    ("rewards", ("reward", "rewards", "奖励")),
    ("weekly", ("this week in wow", "weekly", "周报")),
    ("event", ("event", "活动")),
    ("content-update", ("content update", "内容更新", "update", "更新")),
]

MIN_BODY_ZH_CHARS = 50
SOURCE_TRANSLATION_FIDELITY = "source_translation"
BODY_BLOCK_CHUNK_SIZE = 6
EXCERPT_BODY_SOURCE_KINDS = {"feed_excerpt", "forum_excerpt", "listing_excerpt"}


def has_cjk(value):
    return bool(re.search(r"[\u4e00-\u9fff]", value or ""))


def compact_space(value):
    return re.sub(r"\s+", " ", value or "").strip()


def strip_body_label(value):
    return re.sub(r"^中文正文\s*[:：]\s*", "", compact_space(value))


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


def infer_tags(*values):
    text = " ".join(compact_space(value).lower() for value in values if value)
    tags = []
    for tag_id, keywords in TAG_KEYWORDS:
        if any(keyword.lower() in text for keyword in keywords):
            tags.append(tag_id)
    return tags


def normalize_tags(tags=None, tag_items=None, text_values=None):
    seen = set()
    normalized = []
    for tag in tags or []:
        tag_id = compact_space(tag)
        if tag_id in TAG_LABELS and tag_id not in seen:
            normalized.append(tag_id)
            seen.add(tag_id)
    for item in tag_items or []:
        tag_id = compact_space(item.get("id", "") if isinstance(item, dict) else item)
        if tag_id in TAG_LABELS and tag_id not in seen:
            normalized.append(tag_id)
            seen.add(tag_id)
    if not normalized:
        for tag_id in infer_tags(*(text_values or [])):
            if tag_id not in seen:
                normalized.append(tag_id)
                seen.add(tag_id)
    return normalized


def normalize_tag_items(tag_items=None, tags=None, text_values=None):
    normalized_tags = normalize_tags(tags, tag_items, text_values)
    return [{"id": tag_id, "label": TAG_LABELS[tag_id]} for tag_id in normalized_tags]


def body_zh_is_complete(body_zh, summary):
    body_text = strip_body_label(body_zh)
    summary_text = compact_space(summary)
    if len(body_text) < MIN_BODY_ZH_CHARS:
        return False
    if not chinese_display_text(body_text, 10):
        return False
    if summary_text and body_text == summary_text:
        return False
    return True


def normalize_body_blocks(blocks=None, fallback_text=""):
    normalized = []
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        block_type = compact_space(block.get("type", "paragraph")) or "paragraph"
        if block_type not in {"paragraph", "heading", "list", "quote"}:
            block_type = "paragraph"
        if block_type == "list":
            items = [compact_space(item) for item in block.get("items", []) if compact_space(item)]
            if items:
                normalized.append({"type": "list", "items": items})
            continue
        text = strip_body_label(block.get("text", ""))
        if text:
            normalized.append({"type": block_type, "text": text})

    if normalized or not fallback_text:
        return normalized

    parts = [part.strip() for part in re.split(r"\n\s*\n", fallback_text or "") if part.strip()]
    return [{"type": "paragraph", "text": compact_space(part)} for part in parts]


def body_blocks_text(blocks):
    parts = []
    for block in normalize_body_blocks(blocks):
        if block["type"] == "list":
            parts.extend(block.get("items", []))
        else:
            parts.append(block.get("text", ""))
    return "\n\n".join(part for part in parts if part)


def ends_with_ellipsis(value):
    return bool(re.search(r"(?:…|\.{3}|．．．)$", compact_space(value)))


def comparable_text(value):
    return re.sub(r"[\W_]+", "", compact_space(value).lower(), flags=re.UNICODE)


def text_matches_or_contains_summary(body, summary):
    body_key = comparable_text(body)
    summary_key = comparable_text(summary)
    if not body_key or not summary_key:
        return False
    return body_key == summary_key


def source_body_quality_issue(article):
    source_kind = compact_space(article.get("bodySourceKind", ""))
    if source_kind in EXCERPT_BODY_SOURCE_KINDS:
        return "source_body_missing"

    source_blocks = normalize_body_blocks(article.get("bodyBlocks"))
    original_body = compact_space(body_blocks_text(source_blocks)) or compact_space(article.get("originalBody", ""))
    original_summary = compact_space(article.get("originalSummary", "")) or compact_space(article.get("summary", ""))
    if not source_blocks or not original_body:
        return "source_body_missing" if source_kind else ""
    if original_summary and text_matches_or_contains_summary(original_body, original_summary):
        return "summary_only_body"
    if len(source_blocks) == 1 and ends_with_ellipsis(original_body):
        return "summary_only_body"
    return ""


def split_translated_list_text(value):
    text = re.sub(r"^中文正文\s*[:：]\s*", "", str(value or ""), flags=re.I).strip()
    separators = r"(?:\n+|[;；]|(?<=[。！？.!?])\s+)"
    parts = []
    for part in re.split(separators, text):
        item = compact_space(re.sub(r"^[\-*•·\d\.\)、）\s]+", "", part))
        if item:
            parts.append(item)
    return parts


def coerce_body_blocks_to_source_structure(source_blocks, translated_blocks):
    source = normalize_body_blocks(source_blocks)
    translated = normalize_body_blocks(translated_blocks)
    if not source or len(source) != len(translated):
        return []

    coerced = []
    for source_block, translated_block in zip(source, translated):
        source_type = source_block.get("type", "paragraph")
        if source_type == "list":
            source_items = source_block.get("items", [])
            translated_items = translated_block.get("items", [])
            if not translated_items:
                translated_items = split_translated_list_text(translated_block.get("text", ""))
            if len(translated_items) != len(source_items):
                return []
            coerced.append({"type": "list", "items": translated_items})
            continue

        text = translated_block.get("text", "")
        if not text and translated_block.get("items"):
            text = " ".join(translated_block.get("items", []))
        text = strip_body_label(text)
        if not text:
            return []
        coerced.append({"type": source_type, "text": text})
    return coerced


def body_block_structure_matches(source_blocks, translated_blocks):
    source = normalize_body_blocks(source_blocks)
    translated = normalize_body_blocks(translated_blocks)
    if not source:
        return bool(translated)
    if len(source) != len(translated):
        return False
    for source_block, translated_block in zip(source, translated):
        if source_block.get("type") != translated_block.get("type"):
            return False
        if source_block.get("type") == "list" and len(source_block.get("items", [])) != len(translated_block.get("items", [])):
            return False
    return True


def content_quality_issues(article):
    issues = []
    article_id = article.get("id", "")
    text_thresholds = {"title": 3, "summary": 6, "bodyZh": 6}
    for field, max_english_words in text_thresholds.items():
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

    if not compact_space(article.get("originalTitle", "")):
        issues.append({"id": article_id, "field": "originalTitle", "reason": "missing original title"})
    if not body_zh_is_complete(article.get("bodyZh", ""), article.get("summary", "")):
        issues.append({"id": article_id, "field": "bodyZh", "reason": "translated body is not complete"})
    if not normalize_body_blocks(article.get("bodyBlocksZh"), article.get("bodyZh", "")):
        issues.append({"id": article_id, "field": "bodyBlocksZh", "reason": "missing translated body blocks"})
    if not article.get("tagItems"):
        issues.append({"id": article_id, "field": "tagItems", "reason": "missing public tags"})
    if article.get("translationStatus") == "llm" and article.get("translationFidelity") != SOURCE_TRANSLATION_FIDELITY:
        issues.append({"id": article_id, "field": "translationFidelity", "reason": "translated body is not a source translation"})
    return issues


def first_issue_reason(article):
    issues = content_quality_issues(article)
    return issues[0]["reason"].replace(" ", "_") if issues else ""


def block_article(article, reason, translation_status="blocked"):
    blocked = dict(article)
    blocked.update(
        {
            "contentStatus": "blocked",
            "translationStatus": translation_status,
            "blockedReason": reason,
        }
    )
    return blocked


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


def normalize_llm_translation(payload, source_body_blocks=None):
    if not isinstance(payload, dict):
        return None

    title = compact_space(payload.get("title", ""))
    summary = compact_space(payload.get("summary", ""))
    body_zh = compact_space(payload.get("bodyZh") or payload.get("body", ""))
    body_blocks_zh = normalize_body_blocks(payload.get("bodyBlocksZh") or payload.get("bodyBlocks"))
    source_blocks = normalize_body_blocks(source_body_blocks)
    if source_blocks:
        if not body_blocks_zh or not body_block_structure_matches(source_blocks, body_blocks_zh):
            return None
        body_zh = body_blocks_text(body_blocks_zh)
    elif body_blocks_zh:
        body_zh = body_blocks_text(body_blocks_zh)
    else:
        body_blocks_zh = normalize_body_blocks(fallback_text=body_zh)
    tag_items = normalize_tag_items(payload.get("tagItems") or payload.get("tags"), text_values=[title, summary, body_zh])
    if not chinese_display_text(title, 3):
        return None
    if not chinese_display_text(summary, 6):
        return None
    if not body_zh_is_complete(body_zh, summary):
        return None
    if not tag_items:
        return None
    body_zh = strip_body_label(body_zh)
    return {
        "title": localize_visible_terms(title),
        "summary": localize_visible_terms(summary),
        "bodyZh": localize_visible_terms(body_zh),
        "bodyBlocksZh": body_blocks_zh,
        "tagItems": tag_items,
        "tags": [item["id"] for item in tag_items],
        "translationFidelity": SOURCE_TRANSLATION_FIDELITY,
    }


def visible_translation_issues(articles):
    issues = []
    for article in articles:
        issues.extend(content_quality_issues(article))
    return issues


def should_use_llm_translation():
    return llm_configured()


def truncate_for_llm(value, limit):
    text = str(value or "")
    if len(text) <= limit:
        return text
    return f"{text[:limit]} [truncated]"


def llm_article_context(article):
    original_title = truncate_for_llm(article.get("originalTitle") or article.get("title", ""), 200)
    original_summary = truncate_for_llm(article.get("originalSummary") or article.get("summary", ""), 1000)
    original_body = truncate_for_llm(article.get("originalBody") or article.get("body") or article.get("summary", ""), 3000)
    return original_title, original_summary, original_body


def translate_article_metadata_with_llm(article):
    original_title, original_summary, original_body = llm_article_context(article)

    prompt = "\n".join(
        [
            "请为这条魔兽世界官方资讯生成中文标题、中文摘要和白名单 tag。",
            "只返回 JSON，不要 Markdown，不要解释。",
            "JSON schema: {\"title\":\"中文标题\",\"summary\":\"中文摘要\",\"tagItems\":[{\"id\":\"content-update\",\"label\":\"内容更新\"}]}",
            "可用 tag id 只能从这些值里选择：retail, content-update, patch-notes, hotfix, class-change, ptr, weekly, event, raid, trading-post, season, rewards, official。",
            "要求：title 和 summary 必须忠实对应原始标题/摘要/正文，不要添加读者建议，不要编造原文没有的信息。",
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
        "你是面向中文魔兽世界玩家的资讯编辑。你的任务是忠实翻译英文资讯元信息，输出可直接展示在小程序里的中文字段。",
        prompt,
        temperature=0.1,
    )
    if result.get("error") or not result.get("content"):
        return None
    payload = parse_llm_json(result["content"])
    if not isinstance(payload, dict):
        return None
    return {
        "title": compact_space(payload.get("title", "")),
        "summary": compact_space(payload.get("summary", "")),
        "tagItems": payload.get("tagItems") or payload.get("tags") or [],
    }


def body_block_chunks(blocks, chunk_size=None):
    size = max(1, int(chunk_size or BODY_BLOCK_CHUNK_SIZE))
    for start in range(0, len(blocks), size):
        yield start, blocks[start : start + size]


def translate_body_block_chunk_with_llm(article, chunk, start_index):
    prompt = "\n".join(
        [
            "请把下面的魔兽世界官方资讯正文块 JSON 逐块忠实翻译成中文。",
            "只返回 JSON，不要 Markdown，不要解释。",
            "JSON schema: {\"bodyBlocksZh\":[{\"type\":\"paragraph\",\"text\":\"中文译文\"}]}",
            "硬性要求：返回数组长度、每个块的 type、list items 数量必须与输入完全一致。",
            "硬性要求：逐句翻译原文含义，不要总结，不要改写成导读，不要添加读者建议，不要出现“详情页”“来源按钮”“方便核对”等原文没有的说明。",
            "硬性要求：不要输出“中文正文：”这类标签前缀；正文里只放译文。",
            "",
            f"文章原题：{article.get('originalTitle') or article.get('title', '')}",
            f"正文块起始序号：{start_index}",
            "正文块 JSON：",
            json.dumps(chunk, ensure_ascii=False),
        ]
    )
    result = call_chat_completion(
        "你是专业游戏资讯译者。你的任务是忠实翻译英文正文块，保持结构，不做总结。",
        prompt,
        temperature=0.1,
    )
    if result.get("error") or not result.get("content"):
        return None
    payload = parse_llm_json(result["content"])
    if isinstance(payload, list):
        raw_blocks = payload
    elif isinstance(payload, dict):
        raw_blocks = payload.get("bodyBlocksZh") or payload.get("bodyBlocks")
    else:
        return None
    translated = coerce_body_blocks_to_source_structure(chunk, raw_blocks)
    if not translated:
        return None
    return translated


def translate_body_blocks_with_llm(article, source_blocks):
    translated = []
    for start_index, chunk in body_block_chunks(source_blocks):
        chunk_translation = translate_body_block_chunk_with_llm(article, chunk, start_index)
        if not chunk_translation:
            if len(chunk) == 1:
                return None
            chunk_translation = []
            for offset, source_block in enumerate(chunk):
                single_translation = translate_body_block_chunk_with_llm(article, [source_block], start_index + offset)
                if not single_translation:
                    return None
                chunk_translation.extend(single_translation)
        translated.extend(chunk_translation)
    return translated


def translate_article_with_llm(article):
    if not should_use_llm_translation():
        return None

    source_blocks = normalize_body_blocks(article.get("bodyBlocks"))
    if source_blocks:
        metadata = translate_article_metadata_with_llm(article)
        if not metadata:
            return None
        body_blocks_zh = translate_body_blocks_with_llm(article, source_blocks)
        if not body_blocks_zh:
            return None
        return {**metadata, "bodyBlocksZh": body_blocks_zh}

    original_title, original_summary, original_body = llm_article_context(article)

    prompt = "\n".join(
        [
            "请把这条魔兽世界资讯按原文逐块忠实翻译成中文。",
            "只返回 JSON，不要 Markdown，不要解释。",
            "JSON schema: {\"title\":\"中文标题\",\"summary\":\"中文摘要\",\"bodyBlocksZh\":[{\"type\":\"paragraph\",\"text\":\"中文段落\"}],\"tagItems\":[{\"id\":\"content-update\",\"label\":\"内容更新\"}]}",
            "可用 tag id 只能从这些值里选择：retail, content-update, patch-notes, hotfix, class-change, ptr, weekly, event, raid, trading-post, season, rewards, official。",
            "硬性要求：bodyBlocksZh 必须与原始正文块 JSON 的块数量、块 type 和 list items 数量完全一致。",
            "硬性要求：逐句翻译原文含义，不要总结、不要改写成资讯导读、不要添加读者建议、不要出现“详情页”“来源按钮”“方便核对”等原文没有的说明。",
            "硬性要求：不要输出“中文正文：”这类标签前缀；正文里只放译文。",
            "专有名词可以保留英文；不要编造原文没有的信息；不要翻译 sourceUrl。",
            "",
            f"原始标题：{original_title}",
            f"原始摘要：{original_summary}",
            f"原始正文摘录：{original_body}",
            f"原始正文块 JSON：{truncate_for_llm(json.dumps(article.get('bodyBlocks', []), ensure_ascii=False), 2500)}",
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


def localize_article(article, translate_with_llm=None, require_llm=False):
    original_title = article.get("originalTitle") or article.get("title", "")
    original_summary = article.get("originalSummary") or article.get("summary", "")
    original_body = article.get("originalBody") or article.get("body") or original_summary or original_title

    title = compact_space(article.get("title", original_title))
    summary = compact_space(article.get("summary", original_summary))
    body_zh = compact_space(article.get("bodyZh", ""))
    body_zh = strip_body_label(body_zh)
    body_blocks = normalize_body_blocks(article.get("bodyBlocks"))
    body_blocks_zh = normalize_body_blocks(article.get("bodyBlocksZh"), body_zh)
    if body_blocks_zh and not body_zh:
        body_zh = body_blocks_text(body_blocks_zh)

    tag_items = normalize_tag_items(
        article.get("tagItems"),
        article.get("tags", []),
        [title, summary, body_zh, original_title, original_summary, original_body, article.get("channel", "")],
    )

    translator = translate_with_llm
    if translator is None and (require_llm or (not body_zh and should_use_llm_translation())):
        if not should_use_llm_translation():
            translator = None
        else:
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
            "bodyBlocks": body_blocks,
            "bodyBlocksZh": body_blocks_zh,
            "tags": [item["id"] for item in tag_items],
            "tagItems": tag_items,
            "blockedReason": "",
        }
    )

    if require_llm:
        source_issue = source_body_quality_issue(localized)
        if source_issue:
            return block_article(localized, source_issue)

    if translator:
        llm_translation = normalize_llm_translation(translator(localized), body_blocks)
        if llm_translation:
            localized.update(llm_translation)
            localized.update(
                {
                    "contentStatus": "ready",
                    "translationStatus": "llm",
                    "blockedReason": "",
                }
            )
            return localized
        return block_article(localized, "invalid_llm_translation")

    if require_llm:
        return block_article(localized, "llm_not_configured")

    if not localized.get("bodyZh"):
        title = translate_title(title)
        summary = translate_summary(summary, original_title)
        localized.update(
            {
                "title": localize_visible_terms(title),
                "summary": localize_visible_terms(summary),
            }
        )

    reason = first_issue_reason(localized)
    if reason:
        return block_article(localized, reason)

    localized.update(
        {
            "contentStatus": "ready",
            "translationStatus": localized.get("translationStatus") or "seed",
            "blockedReason": "",
        }
    )
    return localized
