"""Product specialization scope; aliases stay at the SimC transport boundary."""

SPECIALIZATIONS = {
    'warrior': ('arms', 'fury', 'protection'),
    'paladin': ('holy', 'protection', 'retribution'),
    'hunter': ('beast_mastery', 'marksmanship', 'survival'),
    'rogue': ('assassination', 'outlaw', 'subtlety'),
    'priest': ('discipline', 'holy', 'shadow'),
    'death_knight': ('blood', 'frost', 'unholy'),
    'shaman': ('elemental', 'enhancement', 'restoration'),
    'mage': ('arcane', 'fire', 'frost'),
    'warlock': ('affliction', 'demonology', 'destruction'),
    'monk': ('brewmaster', 'mistweaver', 'windwalker'),
    'druid': ('balance', 'feral', 'guardian', 'restoration'),
    'demon_hunter': ('havoc', 'vengeance', 'devourer'),
    'evoker': ('devastation', 'preservation', 'augmentation'),
}
HEALER_SPECS = frozenset({
    ('paladin', 'holy'), ('priest', 'discipline'), ('priest', 'holy'),
    ('shaman', 'restoration'), ('monk', 'mistweaver'), ('druid', 'restoration'),
    ('evoker', 'preservation'),
})
SIMULATION_SPECS = frozenset(
    (klass, spec) for klass, specs in SPECIALIZATIONS.items() for spec in specs
) - HEALER_SPECS


def canonical_class(class_key: str) -> str:
    return {'deathknight': 'death_knight', 'demonhunter': 'demon_hunter'}.get(class_key, class_key)


def simc_class_token(class_key: str) -> str:
    return {'death_knight': 'deathknight', 'demon_hunter': 'demonhunter'}.get(class_key, class_key)
