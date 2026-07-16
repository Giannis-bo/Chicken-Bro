import vectorManifest from '../../design-system/assets/vector/manifest.json'
import buildIntelRasterManifest from '../../design-system/assets/raster/build-intel-v1/manifest.json'
import buildsHomeRasterManifest from '../../design-system/assets/raster/builds-home-v1/manifest.json'
import newsDetailRasterManifest from '../../design-system/assets/raster/news-detail-v1/manifest.json'
import newsHomeRasterManifest from '../../design-system/assets/raster/news-home-v1/manifest.json'
import newsListRasterManifest from '../../design-system/assets/raster/news-list-v1/manifest.json'
import sharedChromeRasterManifest from '../../design-system/assets/raster/shared-chrome-v1/manifest.json'

export type ProductionAssetId = string
export type AssetSlotId = string

export type AssetSourceClass = 'system_vector' | 'imagegen_raster' | 'canonical_target_derivative'
export type CandidateReviewStatus =
  | 'untrusted_candidate'
  | 'generated_pending_isolated_review'
  | 'independent_review_passed_for_canary'
export type ProductionReviewStatus = 'wechat_verified_production'

export interface CandidateAsset {
  assetId: string
  slotId: string
  variant: string
  filePath: string
  sourceClass: AssetSourceClass
  dimensions: readonly [number, number]
  sizeBytes: number
  reviewStatus: CandidateReviewStatus
}

export interface CandidateAssetSlot {
  slotId: string
  packageLocation: string
  reviewStatus: CandidateReviewStatus
}

export interface ProductionAsset extends Omit<CandidateAsset, 'reviewStatus'> {
  reviewStatus: ProductionReviewStatus
  route: 'news_home'
}

export interface ProductionAssetSlot extends Omit<CandidateAssetSlot, 'reviewStatus'> {
  reviewStatus: ProductionReviewStatus
  route: 'news_home'
}

export const defaultRuntimeAssetRoot = '/assets/ui-v2' as const

let configuredRuntimeAssetRoot: string = defaultRuntimeAssetRoot

function normalizeRoot(root: string): string {
  if (!root || root === '/') return ''
  if (root === '.') return '.'
  return `/${root.replace(/^\/+|\/+$/g, '')}`
}

function toRuntimeRelativePath(filePath: string): string {
  const marker = 'packages/design-system/assets/'
  if (!filePath.startsWith(marker)) throw new Error(`Asset is outside the candidate package: ${filePath}`)
  return filePath.slice(marker.length)
}

const rawCandidateAssets = vectorManifest.assets
const rawCandidateSlots = vectorManifest.slots

const buildsHomeCandidateAssets: readonly CandidateAsset[] = buildsHomeRasterManifest.assets.map((asset) => ({
  assetId: asset.assetId,
  slotId: asset.slotId,
  variant: asset.variant,
  filePath: `packages/design-system/assets/raster/builds-home-v1/${asset.path2x}`,
  sourceClass: asset.sourceClass as AssetSourceClass,
  dimensions: [asset.dimensions['2x'].width, asset.dimensions['2x'].height] as const,
  sizeBytes: asset.bytes['2x'],
  reviewStatus: 'generated_pending_isolated_review',
}))

const buildsHomeCandidateAssetSlots: readonly CandidateAssetSlot[] = buildsHomeRasterManifest.slots.map((slot) => ({
  slotId: slot.slotId,
  packageLocation: slot.packageLocation,
  reviewStatus: 'generated_pending_isolated_review',
}))

const buildIntelCandidateAssets: readonly CandidateAsset[] = buildIntelRasterManifest.assets.map((asset) => ({
  assetId: asset.assetId,
  slotId: asset.slotId,
  variant: asset.assetId.split('.').at(-1) ?? 'default',
  filePath: asset.runtime['2x'].path,
  sourceClass: asset.sourceClass as AssetSourceClass,
  dimensions: [asset.runtime['2x'].width, asset.runtime['2x'].height] as const,
  sizeBytes: asset.runtime['2x'].bytes,
  reviewStatus: 'independent_review_passed_for_canary',
}))

const buildIntelCandidateAssetSlots: readonly CandidateAssetSlot[] = Array.from(new Set(
  buildIntelCandidateAssets.map((asset) => asset.slotId),
)).map((slotId) => ({
  slotId,
  packageLocation: 'packages/design-system/assets/raster/build-intel-v1/runtime',
  reviewStatus: 'independent_review_passed_for_canary',
}))

const sharedChromeSlotIds: Readonly<Record<string, AssetSlotId>> = {
  'shared-page-corner.default': 'asset_slot.shared-page-corner',
  'shared-page-side-rail.default': 'asset_slot.shared-page-side-rail',
  'title-ornament-family.left-rail': 'asset_slot.title-ornament-family',
  'title-ornament-family.right-rail': 'asset_slot.title-ornament-family',
  'pushed-back-medallion.default': 'asset_slot.pushed-back-medallion',
}

function sharedChromeSlotId(assetId: string): AssetSlotId {
  const slotId = sharedChromeSlotIds[assetId]
  if (!slotId) throw new Error(`Missing shared chrome slot mapping for: ${assetId}`)
  return slotId
}

const sharedChromeCandidateAssets: readonly CandidateAsset[] = sharedChromeRasterManifest.assets.map((asset) => ({
  assetId: asset.assetId,
  slotId: sharedChromeSlotId(asset.assetId),
  variant: asset.assetId.split('.').at(-1) ?? 'default',
  filePath: asset.runtime['2x'].path,
  sourceClass: asset.sourceClass as AssetSourceClass,
  dimensions: [asset.runtime['2x'].width, asset.runtime['2x'].height] as const,
  sizeBytes: asset.runtime['2x'].bytes,
  reviewStatus: 'independent_review_passed_for_canary',
}))

const sharedChromeCandidateAssetSlots: readonly CandidateAssetSlot[] = Array.from(new Set(
  sharedChromeCandidateAssets.map((asset) => asset.slotId),
)).map((slotId) => ({
  slotId,
  packageLocation: 'packages/design-system/assets/raster/shared-chrome-v1/runtime',
  reviewStatus: 'independent_review_passed_for_canary',
}))

const newsListCandidateAssets: readonly CandidateAsset[] = newsListRasterManifest.assets.map((asset) => ({
  assetId: asset.assetId,
  slotId: asset.slotId,
  variant: asset.assetId.split('.').at(-1) ?? 'default',
  filePath: asset.runtime['2x'].path,
  sourceClass: asset.sourceClass as AssetSourceClass,
  dimensions: [asset.runtime['2x'].width, asset.runtime['2x'].height] as const,
  sizeBytes: asset.runtime['2x'].bytes,
  reviewStatus: 'independent_review_passed_for_canary',
}))

const newsListCandidateAssetSlots: readonly CandidateAssetSlot[] = Array.from(new Set(
  newsListCandidateAssets.map((asset) => asset.slotId),
)).map((slotId) => ({
  slotId,
  packageLocation: 'packages/design-system/assets/raster/news-list-v1/runtime',
  reviewStatus: 'independent_review_passed_for_canary',
}))

const newsDetailCandidateAssets: readonly CandidateAsset[] = newsDetailRasterManifest.assets.map((asset) => ({
  assetId: asset.assetId,
  slotId: asset.slotId,
  variant: asset.assetId.split('.').at(-1) ?? 'default',
  filePath: asset.runtime['2x'].path,
  sourceClass: asset.sourceClass as AssetSourceClass,
  dimensions: [asset.runtime['2x'].width, asset.runtime['2x'].height] as const,
  sizeBytes: asset.runtime['2x'].bytes,
  reviewStatus: 'independent_review_passed_for_canary',
}))

const newsDetailCandidateAssetSlots: readonly CandidateAssetSlot[] = Array.from(new Set(
  newsDetailCandidateAssets.map((asset) => asset.slotId),
)).map((slotId) => ({
  slotId,
  packageLocation: 'packages/design-system/assets/raster/news-detail-v1/runtime',
  reviewStatus: 'independent_review_passed_for_canary',
}))

const rasterSlotIds: Readonly<Record<string, AssetSlotId>> = {
  'news.frame.family': 'asset_slot.news-frame',
  'news.daily.emblem': 'asset_slot.news-daily-emblem',
  'news.channel.glyphs': 'asset_slot.news-channel-glyphs',
  'product.tab.glyphs': 'asset_slot.product-tab-glyphs',
  'news.hero.fallback': 'asset_slot.news-hero-fallback-scene',
  'news.feed.fallback': 'asset_slot.news-feed-fallback',
  'news.metric.glyphs': 'asset_slot.news-metric-glyphs',
  'news.evidence.glyph': 'asset_slot.news-evidence-glyph',
  'news.favorite.control': 'asset_slot.news-favorite-control',
  'news.bookmark.glyph': 'asset_slot.news-bookmark-glyph',
}

function requiredRasterSlotId(slotId: string): AssetSlotId {
  const runtimeSlotId = rasterSlotIds[slotId]
  if (!runtimeSlotId) throw new Error(`Missing runtime slot mapping for raster slot: ${slotId}`)
  return runtimeSlotId
}

export const candidateAssets: readonly CandidateAsset[] = [
  ...rawCandidateAssets.map((asset) => ({
    assetId: asset.assetId,
    slotId: asset.slotId,
    variant: asset.variant,
    filePath: asset.filePath,
    sourceClass: asset.sourceClass as AssetSourceClass,
    dimensions: asset.dimensions as [number, number],
    sizeBytes: asset.sizeBytes,
    reviewStatus: 'untrusted_candidate' as const,
  })),
  ...buildsHomeCandidateAssets,
  ...buildIntelCandidateAssets,
  ...sharedChromeCandidateAssets,
  ...newsListCandidateAssets,
  ...newsDetailCandidateAssets,
]

export const candidateAssetSlots: readonly CandidateAssetSlot[] = [
  ...rawCandidateSlots.map((slot) => ({
    slotId: slot.slotId,
    packageLocation: slot.packageLocation,
    reviewStatus: 'untrusted_candidate' as const,
  })),
  ...buildsHomeCandidateAssetSlots,
  ...buildIntelCandidateAssetSlots,
  ...sharedChromeCandidateAssetSlots,
  ...newsListCandidateAssetSlots,
  ...newsDetailCandidateAssetSlots,
]

const newsHomeProductionAssets: readonly ProductionAsset[] = newsHomeRasterManifest.assets.map((asset) => ({
  assetId: asset.assetId,
  slotId: requiredRasterSlotId(asset.slotId),
  variant: asset.variant,
  filePath: `packages/design-system/assets/raster/news-home-v1/${asset.path2x}`,
  sourceClass: asset.sourceClass as AssetSourceClass,
  dimensions: [asset.dimensions['2x'].width, asset.dimensions['2x'].height] as const,
  sizeBytes: asset.bytes['2x'],
  reviewStatus: 'wechat_verified_production',
  route: 'news_home',
}))

const newsHomeProductionAssetSlots: readonly ProductionAssetSlot[] = Object.values(rasterSlotIds).map((slotId) => ({
  slotId,
  packageLocation: 'packages/design-system/assets/raster/news-home-v1/runtime',
  reviewStatus: 'wechat_verified_production',
  route: 'news_home',
}))

export const productionAssets: readonly ProductionAsset[] = newsHomeProductionAssets
export const assetSlots: readonly ProductionAssetSlot[] = newsHomeProductionAssetSlots

export function configureAssetRuntimeRoot(root: string): void {
  configuredRuntimeAssetRoot = normalizeRoot(root)
}

export function currentAssetRuntimeRoot(): string {
  return configuredRuntimeAssetRoot
}

export function assetRuntimePath(assetId: ProductionAssetId): string | null {
  const asset = productionAssets.find((candidate) => candidate.assetId === assetId)
    ?? candidateAssets.find((candidate) => candidate.assetId === assetId)
  return asset ? `${configuredRuntimeAssetRoot}/${toRuntimeRelativePath(asset.filePath)}` : null
}

export function assetRuntimePathForSlot(slotId: AssetSlotId, variant?: string): string | null {
  const candidates = [...productionAssets, ...candidateAssets].filter((asset) => asset.slotId === slotId)
  const asset = variant
    ? candidates.find((candidate) => candidate.variant === variant)
    : candidates[0]
  return asset ? assetRuntimePath(asset.assetId) : null
}

function requiredCandidatePath(assetId: string): string {
  const runtimePath = assetRuntimePath(assetId)
  if (!runtimePath) throw new Error(`Missing required utility candidate: ${assetId}`)
  return runtimePath
}

export const systemVectorAssets = {
  tabBarNews: requiredCandidatePath('product-tab-news-icon.default'),
  tabBarSpecialization: requiredCandidatePath('product-tab-builds-icon.default'),
  tabBarAssistant: requiredCandidatePath('product-tab-simulator-icon.default'),
  tabBarProfile: requiredCandidatePath('product-tab-profile-icon.default'),
} as const
