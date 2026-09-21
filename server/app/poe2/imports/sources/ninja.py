"""Ninja handoff is deliberately network-free."""
def handoff(ref):
    return {'status':'needs_input','next_action':'supply_pob',
            'preview':{'sourceUrl':ref.canonical_url,'character':ref.character,'league':ref.league},
            'issues':[]}
