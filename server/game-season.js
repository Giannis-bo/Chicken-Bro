const officialSeasonSourceRefs = [
  {
    name: 'Blizzard News',
    url: 'https://news.blizzard.com/en-us/article/24266321/midnight-season-1-mythic-now-available',
    note: 'Official Midnight Season 1 Mythic+ dungeon rotation.'
  },
  {
    name: 'Battle.net Game Data API',
    url: 'https://develop.battle.net/documentation/world-of-warcraft/game-data-apis',
    note: 'Authoritative WoW Game Data API for season, dungeon, journal, item, spell and media data.'
  }
]

const currentSeason = {
  id: 'midnight-season-1',
  seasonId: 'midnight-season-1',
  label: '至暗之夜 Season 1',
  seasonLabel: '至暗之夜 Season 1',
  revision: 'season-midnight-season-1-c09b0948e307',
  seasonRevision: 'season-midnight-season-1-c09b0948e307',
  verifiedAt: '2026-06-12T00:00:00+00:00',
  expiresAt: '2026-06-13T00:00:00+00:00',
  locale: 'zh_CN',
  dataStatus: 'verified',
  dungeons: [
    "Magisters' Terrace",
    'Maisara Caverns',
    'Nexus-Point Xenas',
    'Windrunner Spire',
    "Algeth'ar Academy",
    'Pit of Saron',
    'Seat of the Triumvirate',
    'Skyreach'
  ].map((name) => ({
    id: name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
    dungeonId: name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
    instanceId: '',
    name,
    shortName: name,
    timerSeconds: 0,
    sourceRefs: officialSeasonSourceRefs
  })),
  raids: [
    'The Voidspire',
    'The Dreamrift',
    "March on Quel'Danas",
    'Sporefall'
  ].map((name) => ({
    id: '',
    raidId: '',
    instanceId: '',
    name,
    category: 'Raid'
  })),
  sourceRefs: officialSeasonSourceRefs,
  errors: []
}

function buildCurrentSeasonPayload() {
  return JSON.parse(JSON.stringify(currentSeason))
}

function seasonMetadataFields(season) {
  const payload = season || buildCurrentSeasonPayload()
  return {
    currentSeason: payload,
    seasonId: payload.seasonId || payload.id,
    seasonLabel: payload.seasonLabel || payload.label,
    seasonRevision: payload.seasonRevision || payload.revision,
    verifiedAt: payload.verifiedAt,
    expiresAt: payload.expiresAt,
    locale: payload.locale,
    dataStatus: payload.dataStatus,
    sourceRefs: payload.sourceRefs || []
  }
}

module.exports = {
  buildCurrentSeasonPayload,
  seasonMetadataFields,
  officialSeasonSourceRefs
}
