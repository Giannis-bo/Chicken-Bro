const { iconUrlFromIconName } = require('./game-asset')

const classIconNameByKey = {
  deathknight: 'classicon_deathknight',
  demonhunter: 'classicon_demonhunter',
  druid: 'classicon_druid',
  evoker: 'classicon_evoker',
  hunter: 'classicon_hunter',
  mage: 'classicon_mage',
  monk: 'classicon_monk',
  paladin: 'classicon_paladin',
  priest: 'classicon_priest',
  rogue: 'classicon_rogue',
  shaman: 'classicon_shaman',
  warlock: 'classicon_warlock',
  warrior: 'classicon_warrior'
}

const specIconNameByKey = {
  affliction: 'spell_shadow_deathcoil',
  arcane: 'spell_holy_magicalsentry',
  arms: 'ability_warrior_savageblow',
  assassination: 'ability_rogue_eviscerate',
  augmentation: 'classicon_evoker_augmentation',
  balance: 'spell_nature_starfall',
  beast_mastery: 'ability_hunter_bestialdiscipline',
  blood: 'spell_deathknight_bloodpresence',
  brewmaster: 'spell_monk_brewmaster_spec',
  demonology: 'spell_shadow_metamorphosis',
  destruction: 'spell_shadow_rainoffire',
  devastation: 'classicon_evoker_devastation',
  devourer: 'ability_demonhunter_specdevourer',
  discipline: 'spell_holy_powerwordshield',
  elemental: 'spell_nature_lightning',
  enhancement: 'spell_shaman_improvedstormstrike',
  feral: 'ability_druid_catform',
  fire: 'spell_fire_firebolt02',
  frost: 'spell_frost_frostbolt02',
  fury: 'ability_warrior_innerrage',
  guardian: 'ability_racial_bearform',
  havoc: 'ability_demonhunter_specdps',
  holy: 'spell_holy_holybolt',
  marksmanship: 'ability_hunter_focusedaim',
  mistweaver: 'spell_monk_mistweaver_spec',
  outlaw: 'ability_rogue_waylay',
  preservation: 'classicon_evoker_preservation',
  protection: 'ability_warrior_defensivestance',
  restoration: 'spell_nature_magicimmunity',
  retribution: 'spell_holy_auraoflight',
  shadow: 'spell_shadow_shadowwordpain',
  subtlety: 'ability_stealth',
  survival: 'ability_hunter_camouflage',
  unholy: 'spell_deathknight_unholypresence',
  vengeance: 'ability_demonhunter_spectank',
  windwalker: 'spell_monk_windwalker_spec'
}

const CLASS_ASSET_MAP = classIconNameByKey
const SPEC_ASSET_MAP = specIconNameByKey

function classIconUrlFor(classKey) {
  const iconName = classIconNameByKey[String(classKey || '').toLowerCase()]
  return iconName ? iconUrlFromIconName(iconName) : ''
}

function specIconUrlFor(specKey, classKey) {
  const iconName = specIconNameByKey[String(specKey || '').toLowerCase()]
  if (iconName) return iconUrlFromIconName(iconName)
  return classIconUrlFor(classKey)
}

module.exports = {
  CLASS_ASSET_MAP,
  SPEC_ASSET_MAP,
  classIconUrlFor,
  specIconUrlFor
}
