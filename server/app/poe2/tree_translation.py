"""Presentation-only translation of effective PoB text, never of node allocations.

PoE2DB 4.5 cn/us paired strings, retrieved 2026-09-21. Match complete English
effects (including numbers), not node IDs: transformed attributes and patch
differences must retain the engine's actual effects. See the accompanying plan.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

NAME_OVERRIDES = {
    'Jewel Socket': '珠宝插槽', 'Sinister Jewel Socket': '邪恶珠宝插槽',
    'Life Leech. Armour and Evasion while Leeching': '生命偷取、偷取时护甲与闪避',
    'Defenses and Companion Life': '防御与伙伴生命', 'Devestating Devices': '毁灭装置',
    'Invoker': '祈求者', 'Lich': '巫妖', 'Warbringer': '战争使者',
    'Gemling Legionnaire': '古灵使徒斗士',
}
# PoB-specific wording, resolved attribute choices and line wrapping.
STAT_OVERRIDES = {
    '+0.1% to Critical Hit Chance per 10 Item Energy Shield on Equipped Armour Items': '装备的护甲物品每有 10 点物品能量护盾，暴击几率 +0.1%',
    '+1 Charm Slot': '+1 护符栏位', '+5 to Intelligence': '+5 智慧',
    '-20% increased Spirit Reservation Efficiency': '精魂保留效率降低 20%',
    '1 Boots socket': '靴子 1 个插槽', '1 Gloves socket': '手套 1 个插槽',
    '1 Helmet socket': '头盔 1 个插槽', '2 Body Armour sockets': '胸甲 2 个插槽',
    '1% more Attack Speed per 75 Item Evasion on Equipped Armour Items': '装备的护甲物品每有 75 点物品闪避值，攻击速度总增 1%',
    'Adapt to the highest Elemental Damage Type of each Hit you take': '适应你受到的每次击中中伤害最高的元素伤害类型',
    'Arrows Pierce an additional Target': '箭矢额外穿透一个目标',
    'Base Unarmed Physical damage replaced with damage based on their Skill Level': '基础徒手物理伤害替换为基于其技能等级的伤害',
    'Blue: Skills have 30% less cost': '蓝色：技能消耗总降 30%',
    'Can Attack as though using a Quarterstaff while both of your hand slots are empty': '双手栏位均为空时，可以视为使用长杖进行攻击',
    'Can tattoo Runes onto your body, gaining': '可以将符文纹刻于身体，获得',
    'Expend an Owl Feather when you Dodge to trigger Primal Bounty': '闪避翻滚时消耗一根枭之羽毛，触发枭羽馈赠',
    'For each colour of Socketed Support Gem that is most numerous, gain:': '每种插入数量最多的辅助宝石颜色提供以下效果：',
    'Gain 1 Life Flask Charge per 2% Life spent': '每消耗 2% 生命，获得 1 点生命药剂充能',
    'Gain a Primal Owl Feather every 4 seconds, up to a maximum of 3': '每 4 秒获得一根原始枭之羽毛，最多 3 根',
    'Gain a Vivid Wisp when Vivid Stampede ends': '鲜活奔踏结束时获得一个鲜活灵火',
    'Grants 1 Passive Skill Point': '赋予 1 点天赋点数',
    'Grants 4 Passive Skill Point': '赋予 4 点天赋点数',
    'Green: 40% less Movement Speed Penalty from using Skills while Moving': '绿色：移动时使用技能的移动速度惩罚总降 40%',
    'Grenade Skills Fire an additional Projectile': '手雷技能额外发射一个投射物',
    'Grenade Skills have +1 Cooldown Use': '手雷技能的冷却使用次数 +1',
    'Quarterstaff Skills that consume Power Charges count as consuming an additional Power Charge': '消耗暴击球的长杖技能视为额外消耗一个暴击球',
    'Red: Hits against you have no Critical Damage Bonus': '红色：对你的击中没有暴击伤害加成',
    'Remove a Curse after Channelling for 2 seconds': '持续吟唱 2 秒后移除一个诅咒',
    'Storm and Plant Spells:': '风暴与植物法术：',
    'Unaffected by Elemental Weakness': '不受元素要害影响',
    "Unarmed Attacks that would use an Equipped Quarterstaff's damage have:": '原本使用装备长杖伤害的徒手攻击获得以下效果：',
    'Warcries Empower an additional Attack': '战吼额外强化一次攻击',
    'When you gain Combo, gain an additional Combo': '获得连击时额外获得一次连击',
    'additional Rune-only sockets:': '额外的仅限符文插槽：',
    'cost 50% less': '消耗总降 50%', 'deal 50% more damage': '伤害总增 50%',
    'have 75% less duration': '持续时间总降 75%',
    'Warcries Debilitate Enemies': '战吼使敌人疲惫',
}


def normalized(text):
    return re.sub(r'\s+', ' ', text).strip().lower()


@lru_cache(maxsize=1)
def catalogue():
    data = json.loads(Path(__file__).with_name('tree-zh-CN.json').read_text())
    data['names'].update(NAME_OVERRIDES)
    data['names'] = {normalized(k): v for k, v in data['names'].items()}
    data['stats'].update({normalized(k): v for k, v in STAT_OVERRIDES.items()})
    return data


def translate_stats(lines):
    translations = catalogue()['stats']
    result, start = [], 0
    while start < len(lines):
        for end in range(len(lines), start, -1):
            key = normalized(' '.join(lines[start:end]))
            if key in translations:
                result.append(translations[key])
                start = end
                break
        else:
            result.append(lines[start])
            start += 1
    return result


def translate_tree(tree):
    names = catalogue()['names']
    return {**tree, 'nodes': [{**node, 'originalName': node['name'],
        'originalStats': node['stats'], 'name': names.get(normalized(node['name']), node['name']),
        'stats': translate_stats(node['stats'])} for node in tree['nodes']]}
