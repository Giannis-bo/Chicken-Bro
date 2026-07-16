import type { TrustDescriptor } from './models'

export type JsonPrimitive = string | number | boolean | null
export type JsonValue = JsonPrimitive | JsonObject | readonly JsonValue[]
export interface JsonObject {
  readonly [key: string]: JsonValue
}

export interface SourceReference {
  name: string
  url: string
  note?: string
}

export type BuildsDataStatus =
  | 'verified'
  | 'partial'
  | 'stale'
  | 'blocked'
  | 'missing_credentials'
  | 'pending_official_audit'

export type RaiderIOSourceStatus =
  | 'synced'
  | 'verified'
  | 'partial'
  | 'stale'
  | 'blocked'
  | 'missing_credentials'
  | 'source_reference'

export interface RaiderIOSummary {
  sourceName?: string
  sourceStatus: RaiderIOSourceStatus
  sourceStatusLabel?: string
  seasonSlug?: string
  region?: string
  checkedAt?: string
  expiresAt?: string
  analysisWindow?: string
  sampleCount: number
  maxKeyLevel?: number
  bestScore?: number
  numericValuesUsable?: boolean
  sourceUrl?: string
}

export interface NewsTag {
  id?: string
  label: string
}

export interface NewsBodyBlock {
  type: 'paragraph' | 'heading' | 'list' | 'quote' | string
  text?: string
  items?: readonly string[]
}

export interface NewsArticle {
  id: string
  title: string
  summary: string
  channel: string
  category: string
  sourceName: string
  sourceUrl: string
  publishedAt: string
  originalTitle?: string
  sourceNote?: string
  bodyZh?: string
  bodyBlocksZh?: readonly NewsBodyBlock[]
  tags?: readonly string[]
  tagItems?: readonly NewsTag[]
  sourceBadges?: readonly string[]
  contentStatus?: string
  translationStatus?: string
  translationFidelity?: string
  verificationStatus?: string
  licenseStatus?: string
  sourceTier?: string
  imageUrl?: string
}

export interface NewsMetric {
  key: string
  value: string | number
  label: string
}

export interface NewsChannel {
  id: string
  title: string
  desc?: string
  updateCount?: number
}

export interface NewsHomePayload {
  navTitle: string
  heroNews: readonly NewsArticle[]
  metrics: readonly NewsMetric[]
  channels: readonly NewsChannel[]
  highlights: readonly NewsArticle[]
  lastRefreshedAt: string
  refreshMode: string
}

export interface NewsListPayload {
  title: string
  type: string
  key: string
  value: string
  count: number
  articles: readonly NewsArticle[]
}

export interface BuildQuickAction {
  key: 'talents' | 'gear' | 'simc' | 'tasks'
  title: string
  desc: string
  phaseLabel?: string
  actionLabel?: string
  scopeLabel?: string
  evidenceLabel?: string
  impactLabel?: string
}

export interface SpecializationOption {
  name: string
  id?: string
  specId?: string
  title?: string
  className?: string
  specName?: string
  classKey?: string
  specKey?: string
  websimClassKey?: string
  websimSpecKey?: string
  heroKey?: string
  heroLabel?: string
  role?: string
  status?: string
  classSlug?: string
  specSlug?: string
  iconUrl?: string
  classIconUrl?: string
  specIconUrl?: string
  desc?: string
  sourceName: string
  sourceUrl: string
  sourceNote?: string
  publishedAt?: string
  analysisWindow?: string
  dataStatus?: BuildsDataStatus
  raiderio?: RaiderIOSummary
  raiderioSourceStatus?: RaiderIOSourceStatus
  sampleCount?: number
  maxKeyLevel?: number
  bestScore?: number
}

export interface ClassOption {
  name: string
  id?: string
  websimClassKey: string
  iconUrl?: string
  specializations: readonly SpecializationOption[]
}

export interface SpecializationSummary {
  id: string
  className: string
  specName: string
  role: string
  title: string
  status?: string
  classSlug?: string
  specSlug?: string
  websimClassKey?: string
  websimSpecKey?: string
  classIconUrl?: string
  specIconUrl?: string
  iconUrl?: string
  desc?: string
  sourceName?: string
  sourceUrl?: string
  sourceNote?: string
  publishedAt?: string
  analysisWindow?: string
  dataStatus?: string
  raiderio?: RaiderIOSummary
  raiderioSourceStatus?: RaiderIOSourceStatus
  sampleCount?: number
  maxKeyLevel?: number
  bestScore?: number
}

export interface SeasonDungeon {
  id: string
  dungeonId?: string
  instanceId?: string
  name: string
  shortName?: string
  timerSeconds?: number
  sourceRefs?: readonly SourceReference[]
}

export interface SeasonRaid {
  id: string
  raidId?: string
  instanceId?: string
  name: string
  category?: string
}

export interface SeasonSnapshot {
  id?: string
  seasonId?: string
  label?: string
  seasonLabel?: string
  revision?: string
  seasonRevision?: string
  verifiedAt?: string
  expiresAt?: string
  locale?: string
  dataStatus?: BuildsDataStatus
  dungeons?: readonly SeasonDungeon[]
  raids?: readonly SeasonRaid[]
  errors?: readonly string[]
  sourceRefs?: readonly SourceReference[]
}

export interface BuildsHomePayload {
  navTitle: string
  kicker: string
  title: string
  desc: string
  quickActions: readonly BuildQuickAction[]
  classOptions: readonly ClassOption[]
  featuredSpecializations: readonly SpecializationSummary[]
  trustedSources: readonly SourceReference[]
  lastAnalyzedAt?: string
  analysisWindow?: string
  currentSeason: SeasonSnapshot
  seasonId?: string
  seasonLabel?: string
  seasonRevision?: string
  verifiedAt?: string
  expiresAt?: string
  locale?: string
  dataStatus: BuildsDataStatus
  blockedReason?: string
  sourceRefs: readonly SourceReference[]
  raiderio: RaiderIOSummary
  raiderioError?: string
}

export interface BuildsIntelPayload {
  navTitle: string
  title: string
  desc: string
  count: number
  items: readonly SpecializationSummary[]
  trustedSources?: readonly SourceReference[]
  analysisWindow?: string
  currentSeason?: SeasonSnapshot
  dataStatus?: string
}

export interface BuildsDetailPayload extends SpecializationSummary {
  details: Readonly<Record<string, unknown>>
  currentSeason?: SeasonSnapshot
  sourceRefs?: readonly SourceReference[]
}

export interface WebsimSelection {
  classKey: string
  specKey: string
  heroKey?: string
}

export interface WebsimScenario {
  key: string
  title?: string
  label?: string
  description?: string
}

export interface WebsimBootstrapPayload {
  navTitle: string
  classes: readonly ClassOption[]
  scenarios: readonly WebsimScenario[]
  gearSlots: readonly GearSlotDefinition[]
  defaultSelection: WebsimSelection
  currentSeason?: SeasonSnapshot
  dataStatus: string
}

export interface TalentNode {
  id: string
  key?: string
  name: string
  description?: string
  descriptionStatus?: string
  treeKey?: string
  treeType?: string
  row?: number
  column?: number
  maxRank?: number
  ranks?: number
  requiredPoints?: number
  prerequisiteIds?: readonly string[]
  parentMode?: string
  shape?: string
  granted?: boolean
  choiceOptions?: readonly TalentNode[]
  iconUrl?: string
  sourceUrl?: string
}

export interface TalentTreeSection {
  key: string
  title: string
  maxPoints?: number
  pointCap?: number
  requiredPoints?: number
}

export interface CommunityTemplateReference {
  id?: string
  title?: string
  name?: string
  rawImportCode?: string
  importCode?: string
  talentImport?: string
  sourceUrl?: string
  source?: string
  status?: string
  analysisWindow?: string
  gearItems?: readonly GearItemReference[]
}

export interface TalentReadinessSummary {
  schemaRevision?: string
  sourceStatus?: string
  treeReady?: boolean
  ruleReady?: boolean
  spellReady?: boolean
  encodingReady?: boolean
  simcReady?: boolean
  blockers?: readonly string[]
  treeCoverage?: {
    required?: readonly string[]
    present?: readonly string[]
    missing?: readonly string[]
    nodeCounts?: Readonly<Record<string, number>>
  }
  spellCoverage?: {
    covered?: number
    total?: number
    percent?: number
    missingDescriptionCount?: number
    unresolvedDescriptionCount?: number
    missingIconCount?: number
  }
}

export interface WebsimTalentsPayload extends WebsimSelection {
  nodes: readonly TalentNode[]
  treeSections: readonly TalentTreeSection[]
  presets: readonly CommunityTemplateReference[]
  communityTemplates: readonly CommunityTemplateReference[]
  talentStatus: string
  talentSchemaRevision?: string
  talentReadiness?: TalentReadinessSummary
  talentAuthority?: Readonly<Record<string, unknown>>
  blockers?: readonly string[]
  currentSeason?: SeasonSnapshot
  dataStatus?: string
  sourceRefs?: readonly SourceReference[]
  errors: readonly string[]
}

export interface TalentImportPayload extends WebsimSelection {
  importCode: string
  source: string
  status: string
  blockers: readonly string[]
}

export interface GearSlotDefinition {
  slot: string
  simcSlot?: string
  label: string
}

export interface GearEnhancementOption {
  id?: string
  optionKey?: string
  type?: string
  optionType?: string
  name?: string
  label?: string
  displayName?: string
  displayLabel?: string
  displayStatus?: string
  iconUrl?: string
  status?: string
  [key: string]: unknown
}

export interface GearItemReference {
  id?: string
  itemId?: string | number
  name?: string
  itemName?: string
  displayName?: string
  iconUrl?: string
  sourceUrl?: string
  itemLevel?: number
  ilevel?: string | number
  quality?: string | number
  status?: string
  simcReady?: boolean
  source?: string
  sourceType?: string
  variantKey?: string
  compatibility?: string | Readonly<Record<string, unknown>>
  metadataStatus?: string
  statDisplayStatus?: string
  statSummary?: string
  missingFields?: readonly string[]
  socketOptions?: readonly GearEnhancementOption[]
  enchantOptions?: readonly GearEnhancementOption[]
  embellishmentOptions?: readonly GearEnhancementOption[]
  modCapabilities?: Readonly<Record<string, unknown>>
  [key: string]: unknown
}

export interface GearSlotReadiness {
  slot: string
  label: string
  status: string
  simcReady: boolean
  missingFields?: readonly string[]
  reason?: string
}

export interface StatValue {
  key: string
  label: string
  value: string | number
  rawValue?: number
}

export interface GearReadiness {
  fullReady: boolean
  simcReadyCount: number
  selectedCount: number
  candidateCount: number
  missingRequiredSlots: readonly string[]
  missingCoreSlots: readonly string[]
  requiredReadyCount: number
  itemLevel?: StatValue
  warnings: readonly string[]
}

export interface GearStatsPayload extends WebsimSelection {
  statStatus: string
  blockers: readonly string[]
  primary: StatValue | null
  stamina: StatValue | null
  secondary: readonly StatValue[]
  armor: StatValue | null
  weaponDps: StatValue | null
  itemLevel: StatValue
  gearReadiness?: Partial<GearReadiness>
  talentEncoding?: {
    status: string
    lines: readonly string[]
    errors: readonly string[]
  }
  checkedAt?: string
}

export interface GearIntentSlot {
  itemId: string
  variantKey: string
  gemOptionIds: readonly string[]
  enchantOptionId: string
  embellishmentOptionId: string
  craftedOptionId: string
  catalystOptionId: string
}

export interface GearEnhancementSelection {
  gemOptionIds: readonly string[]
  enchantOptionId: string
  embellishmentOptionId: string
  craftedOptionId: string
  catalystOptionId: string
}

export interface GearSelectionIntent {
  schemaRevision: string
  authoredAgainst: Readonly<Record<string, string>>
  eligibilityContext: {
    classKey: string
    specKey: string
    level: number
  }
  slots: Readonly<Record<string, GearIntentSlot>>
}

export interface GearProblem {
  kind?: string
  code?: string
  title?: string
  detail?: string
  path?: string
  retryable?: boolean
  [key: string]: unknown
}

export interface GearResolvedSnapshot {
  contractRevision?: string
  status?: string
  resolvedGearSignature?: string
  resolvedSlots?: Readonly<Record<string, Readonly<Record<string, unknown>>>>
  aggregateLegality?: Readonly<Record<string, unknown>>
  staticAttributes?: Readonly<Record<string, unknown>>
  setState?: Readonly<Record<string, unknown>>
  constraints?: Readonly<Record<string, unknown>>
  profileReadiness?: Readonly<Record<string, unknown>>
  statSnapshot?: GearStatsPayload
  statSignature?: string
  retryAfterMs?: number
  selectionIntent?: GearSelectionIntent
  [key: string]: unknown
}

export interface GearResultEnvelope<T = GearResolvedSnapshot> {
  contractRevision: 'gear-result-envelope-v1'
  requestId: string
  status: string
  releaseContext: Readonly<Record<string, unknown>>
  data: T
  problems: readonly GearProblem[]
}

export interface CommunityTemplateImportData {
  contractRevision?: string
  status?: string
  template?: Readonly<Record<string, unknown>>
  manifest?: Readonly<Record<string, unknown>>
  importedGearBySlot?: Readonly<Record<string, GearItemReference>>
  resolvedSnapshot?: GearResolvedSnapshot
}

export interface CommunityTemplateImportEnvelope {
  contractRevision: 'community-template-import-envelope-v1'
  requestId: string
  status: string
  releaseContext: Readonly<Record<string, unknown>>
  data: CommunityTemplateImportData
  problems: readonly GearProblem[]
}

export interface GearResolverContext {
  contractRevision?: string
  selectionSchemaRevision?: string
  authoredAgainst?: Readonly<Record<string, string>>
  [key: string]: unknown
}

export interface WebsimGearPayload extends WebsimSelection {
  slots: readonly GearSlotDefinition[]
  slotGroups: readonly (GearSlotDefinition & { items: readonly GearItemReference[] })[]
  equippedSet: Readonly<Record<string, GearItemReference>>
  slotReadiness: Readonly<Record<string, GearSlotReadiness>>
  replacementCandidates: readonly (GearSlotDefinition & { items: readonly GearItemReference[] })[]
  communityTemplates: readonly CommunityTemplateReference[]
  readiness: GearReadiness
  statSnapshot: GearStatsPayload
  catalogStatus: string
  gearSchemaRevision?: string
  gearCatalogRevision?: string
  itemDatabaseRevision?: string
  variantRevision?: string
  manifestRevision?: string
  maxLevel?: number
  catalogHealthSummary?: Readonly<Record<string, unknown>>
  catalogBlockers: readonly string[]
  sourceRefs?: readonly SourceReference[]
  checkedAt?: string
  dataStatus: string
  resolverContext?: GearResolverContext
}

export type BuildTemplateType = 'talent' | 'gear'

export interface BuildTemplate {
  id: string
  clientId: string
  type: BuildTemplateType
  title: string
  classKey: string
  className: string
  specKey: string
  specName: string
  heroKey: string
  heroLabel: string
  scenarioKey: string
  scenarioTitle: string
  rawString: string
  simcLines: readonly string[]
  status: string
  statusLabel: string
  source: string
  metadata: Readonly<Record<string, unknown>>
  createdAt: string
  updatedAt: string
  remote: boolean
  schemaVersion: 1
  trust: TrustDescriptor
}

export interface AuthUser {
  openid?: string
  nickname?: string
  avatarUrl?: string
  [key: string]: unknown
}

export interface AuthSession {
  accessToken: string
  user: AuthUser | null
  expiresAt: number
}

export interface ChatEvidenceAction {
  title: string
  evidenceRefs: readonly string[]
}

export interface AssistantPayload {
  answerSource: string
  confidence: string
  answerLayer?: string
  basisLabel?: string
  priorityActions: readonly ChatEvidenceAction[]
  evidenceRefs: readonly string[]
  limitations: readonly string[]
  missingInputs?: readonly string[]
  nextQuestion?: string
}

export interface ChatMessage {
  messageId?: string
  role: 'user' | 'assistant' | 'system'
  content: string
  status?: string
  payload?: AssistantPayload
}

export interface ChickenbroResponse {
  mode: 'chickenbro'
  session: { sessionId: string; title?: string }
  job?: { jobId: string; status: string }
  userMessage: ChatMessage
  assistantMessage: ChatMessage
}

export interface SimulatorAnalysisResponse {
  mode: string
  status: string
  taskId?: string
  request?: Readonly<Record<string, unknown>>
  agent?: Readonly<Record<string, unknown>>
  stages?: readonly Readonly<Record<string, unknown>>[]
  simulation?: Readonly<Record<string, unknown>>
  recommendations: readonly string[]
  simcReport?: Readonly<Record<string, unknown>>
}

export interface SimulatorTaskReportSummary {
  state?: string
  title?: string
  summary?: string
  dpsDisplay?: string
  scenario?: Readonly<Record<string, unknown>>
  preparation?: Readonly<Record<string, unknown>>
  build?: Readonly<Record<string, unknown>>
  timing?: Readonly<Record<string, unknown>>
  statusText?: string
  updatedAt?: string
}

export interface SimulatorTaskRecord {
  taskId: string
  id?: string
  status: string
  mode?: string
  question?: string
  createdAt?: string
  updatedAt?: string
  request?: Readonly<Record<string, unknown>>
  analysis?: SimulatorAnalysisResponse
  recommendations?: readonly string[]
  simcReportSummary?: SimulatorTaskReportSummary
}
