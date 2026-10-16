"""Display labels only; source IDs/scopes always come from the live catalog."""
import re

# CN dungeon/raid names: wow.blizzard.cn/news/24244646 and /24294369;
# raid boss labels additionally verified in the public CN WCL gameData profile.
NAMES = {
 'The Venomous Abyss':'烈毒之渊', 'Altar of Fangs':'毒牙祭坛',
 'Den of Nalorakk':'纳洛拉克的洞穴', "Kings' Rest":'诸王之眠', 'Murder Row':'密谋小径',
 'Ruby Life Pools':'红玉新生法池', 'Temple of Sethraliss':'塞塔里斯神庙',
 'The Blinding Vale':'夺目谷', 'Voidscar Arena':'虚空之痕竞技场',
 "Nek'zali the Soulcoiler":'盘魂者内克扎莉', 'Entombed Sentinels':'陵寝哨兵',
 'Vashnik the Malignant':'万毒邪祟者瓦什尼克', 'The Twin Fangs':'双子毒牙', "Ula'tek":'乌拉特克',
 # Player-confirmed short labels; IDs and ordinal positions remain catalog-owned.
 'Nymrissa Wavecaller':'唤潮者', "Kith'ix":'基希克斯',
 'Shaman':'萨满祭司','Mage':'法师','Warrior':'战士','Paladin':'圣骑士','Hunter':'猎人',
 'Rogue':'潜行者','Priest':'牧师','Death Knight':'死亡骑士','Monk':'武僧','Druid':'德鲁伊',
 'Demon Hunter':'恶魔猎手','Evoker':'唤魔师','Warlock':'术士',
 'Affliction':'痛苦','Demonology':'恶魔学识','Destruction':'毁灭',
 'Elemental':'元素','Enhancement':'增强','Restoration':'恢复','Fire':'火焰','Frost':'冰霜',
 'Arcane':'奥术','Arms':'武器','Fury':'狂怒','Protection':'防护','Retribution':'惩戒','Holy':'神圣',
 'Discipline':'戒律','Shadow':'暗影','Assassination':'奇袭','Outlaw':'狂徒','Subtlety':'敏锐',
 'Blood':'鲜血','Unholy':'邪恶','Balance':'平衡','Feral':'野性','Guardian':'守护',
 'Beast Mastery':'野兽控制','Marksmanship':'射击','Survival':'生存',
 'Brewmaster':'酒仙','Mistweaver':'织雾','Windwalker':'踏风',
 'Havoc':'浩劫','Vengeance':'复仇','Devourer':'噬灭','Devastation':'湮灭','Preservation':'恩护','Augmentation':'增辉',
 'Dark Iron Dwarf':'黑铁矮人','Dwarf':'矮人','Human':'人类','Gnome':'侏儒','Night Elf':'暗夜精灵',
 'Draenei':'德莱尼','Worgen':'狼人','Pandaren':'熊猫人','Orc':'兽人','Undead':'亡灵','Tauren':'牛头人',
 'Troll':'巨魔','Blood Elf':'血精灵','Goblin':'地精','Nightborne':'夜之子','Highmountain Tauren':'至高岭牛头人',
 'Void Elf':'虚空精灵','Lightforged Draenei':'光铸德莱尼','Mag\'har Orc':'玛格汉兽人',
 'Zandalari Troll':'赞达拉巨魔','Kul Tiran':'库尔提拉斯人','Vulpera':'狐人','Mechagnome':'机械侏儒',
 'Dracthyr':'龙希尔','Earthen':'土灵',
}
HEALERS = {'Restoration','Holy','Discipline','Mistweaver','Preservation'}


def normalized(value):
    return re.sub(r'[\W_]+', '', str(value or '').casefold())


def label(name):
    if name in NAMES: return NAMES[name]
    return name


def matches(text, entries):
    needle = normalized(text)
    exact = [e for e in entries if needle in {normalized(e['name']),normalized(label(e['name'])),str(e['id'])}]
    if exact: return exact
    return [e for e in entries if len(needle) >= 2 and
            any(needle in normalized(n) for n in (e['name'],label(e['name'])))]
