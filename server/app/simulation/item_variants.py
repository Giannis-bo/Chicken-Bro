"""Engine-bound candidates using an observed upgrade rank, never guessed bonuses."""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _catalog():
    return json.loads((Path(__file__).parent / 'data/item-variants-12.1.0.json').read_text())


def same_upgrade_variants(item_id, gear, runtime):
    catalog = _catalog()
    if not runtime.startswith('simc:managed:' + catalog['revision'] + ':'):
        return []
    target = catalog['items'].get(str(item_id))
    if not target:
        return []
    results = []
    for slot in ('trinket1', 'trinket2'):
        source = gear.get(slot, {})
        source_item = catalog['items'].get(str(source.get('itemId')))
        if not source_item or source.get('itemId') == item_id:
            continue
        if any(v.get('itemId') == item_id for v in gear.values()):
            continue
        upgrades = [b for b in source.get('bonusIds', []) if str(b) in catalog['upgrades']]
        if len(upgrades) != 1:
            continue
        bonus = upgrades[0]; version = catalog['upgrades'][str(bonus)]
        if version['itemLevel'] != source.get('itemLevel'):
            continue
        # Only bare trinkets with an engine-defined generic scaling bonus are
        # resolved here. Sockets, tertiary stats and enchants need separate data.
        results.append({'slot': slot, 'replacesItemId': source['itemId'],
                        'equipment': {'itemId': item_id, 'itemLevel': version['itemLevel'],
                                      'bonusIds': [bonus], 'gems': [], 'enchant': None},
                        'assumption': 'Use the same upgrade bonus and rank as the replaced item; no sockets or tertiary stats.',
                        'upgradeIds': version['upgradeIds'], 'rank': version['rank'],
                        'validation': 'engine_item_and_observed_upgrade',
                        'limitation': 'This models a hypothetical item variant; it does not prove ownership or drop availability.'})
    return results
