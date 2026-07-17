import fs from 'node:fs'
import path from 'node:path'

import { describe, expect, it } from 'vitest'

import {
  assetSlots,
  assetRuntimePath,
  assetRuntimePathForSlot,
  candidateAssets,
  candidateAssetSlots,
  configureAssetRuntimeRoot,
  currentAssetRuntimeRoot,
  productionAssets,
} from './index'

describe('current asset authority', () => {
  it('promotes only the WeChat-verified news_home asset family', () => {
    expect(productionAssets).toHaveLength(33)
    expect(assetSlots).toHaveLength(10)
    expect(productionAssets.every((asset) => asset.route === 'news_home')).toBe(true)
    expect(productionAssets.every((asset) => asset.reviewStatus === 'wechat_verified_production')).toBe(true)
    expect(assetSlots.every((slot) => slot.route === 'news_home' && slot.reviewStatus === 'wechat_verified_production')).toBe(true)
  })

  it('keeps every candidate file registered with an explicit non-production status', () => {
    expect(candidateAssets.length).toBeGreaterThan(0)
    for (const asset of candidateAssets) {
      expect([
        'untrusted_candidate',
        'generated_pending_isolated_review',
        'independent_review_passed_for_canary',
      ]).toContain(asset.reviewStatus)
      expect(fs.existsSync(path.join(process.cwd(), asset.filePath)), asset.filePath).toBe(true)
    }
  })

  it('registers independently reviewed shared chrome without promoting it to production', () => {
    const sharedChromeAssets = candidateAssets.filter((asset) => asset.filePath.includes('/raster/shared-chrome-v1/'))
    const sharedChromeSlots = candidateAssetSlots.filter((slot) => [
      'asset_slot.shared-page-corner',
      'asset_slot.shared-page-side-rail',
      'asset_slot.title-ornament-family',
      'asset_slot.pushed-back-medallion',
    ].includes(slot.slotId))

    expect(sharedChromeAssets).toHaveLength(5)
    expect(sharedChromeSlots).toHaveLength(4)
    expect(sharedChromeAssets.every((asset) => asset.reviewStatus === 'independent_review_passed_for_canary')).toBe(true)
    expect(sharedChromeSlots.every((slot) => slot.reviewStatus === 'independent_review_passed_for_canary')).toBe(true)
    expect(productionAssets.some((asset) => asset.filePath.includes('/raster/shared-chrome-v1/'))).toBe(false)
    expect(assetRuntimePath('shared-page-corner.default')).toBe('/assets/ui-v2/raster/shared-chrome-v1/runtime/2x/shared-page-corner.default.png')
    expect(assetRuntimePath('pushed-back-medallion.default')).toBe('/assets/ui-v2/raster/shared-chrome-v1/runtime/2x/pushed-back-medallion.default.png')
  })

  it('registers independently reviewed news-list medallions without promoting them to production', () => {
    const newsListAssets = candidateAssets.filter((asset) => asset.filePath.includes('/raster/news-list-v1/'))
    const newsListSlots = candidateAssetSlots.filter((slot) => [
      'asset_slot.news-list-document-medallion',
      'asset_slot.news-list-terminal-emblem',
    ].includes(slot.slotId))

    expect(newsListAssets).toHaveLength(2)
    expect(newsListSlots).toHaveLength(2)
    expect(newsListAssets.every((asset) => asset.reviewStatus === 'independent_review_passed_for_canary')).toBe(true)
    expect(newsListSlots.every((slot) => slot.reviewStatus === 'independent_review_passed_for_canary')).toBe(true)
    expect(productionAssets.some((asset) => asset.filePath.includes('/raster/news-list-v1/'))).toBe(false)
    expect(assetRuntimePath('news-list-document-medallion.default')).toBe('/assets/ui-v2/raster/news-list-v1/runtime/2x/news-list-document-medallion.default.png')
    expect(assetRuntimePath('news-list-terminal-medallion.default')).toBe('/assets/ui-v2/raster/news-list-v1/runtime/2x/news-list-terminal-medallion.default.png')
  })

  it('registers independently reviewed news-detail medallions and their slots without promoting them', () => {
    const newsDetailAssets = candidateAssets.filter((asset) => asset.filePath.includes('/raster/news-detail-v1/'))
    const newsDetailSlotIds = [
      'asset_slot.news-detail-source-crest',
      'asset_slot.news-detail-evidence-emblem',
      'asset_slot.news-detail-terminal-emblem',
    ]
    const newsDetailSlots = candidateAssetSlots.filter((slot) => newsDetailSlotIds.includes(slot.slotId))

    expect(newsDetailAssets).toHaveLength(3)
    expect(newsDetailSlots).toHaveLength(3)
    expect(newsDetailAssets.every((asset) => asset.reviewStatus === 'independent_review_passed_for_canary')).toBe(true)
    expect(newsDetailSlots.every((slot) => slot.reviewStatus === 'independent_review_passed_for_canary')).toBe(true)
    expect(productionAssets.some((asset) => asset.filePath.includes('/raster/news-detail-v1/'))).toBe(false)
    expect(assetRuntimePath('news-detail-source-crest.default')).toBe('/assets/ui-v2/raster/news-detail-v1/runtime/2x/news-detail-source-crest.default.png')
    expect(assetRuntimePath('news-detail-evidence-medallion.default')).toBe('/assets/ui-v2/raster/news-detail-v1/runtime/2x/news-detail-evidence-medallion.default.png')
    expect(assetRuntimePath('news-detail-terminal-medallion.default')).toBe('/assets/ui-v2/raster/news-detail-v1/runtime/2x/news-detail-terminal-medallion.default.png')
    expect(assetRuntimePathForSlot('asset_slot.news-detail-source-crest')).toBe('/assets/ui-v2/raster/news-detail-v1/runtime/2x/news-detail-source-crest.default.png')
    expect(assetRuntimePathForSlot('asset_slot.news-detail-evidence-emblem')).toBe('/assets/ui-v2/raster/news-detail-v1/runtime/2x/news-detail-evidence-medallion.default.png')
    expect(assetRuntimePathForSlot('asset_slot.news-detail-terminal-emblem')).toBe('/assets/ui-v2/raster/news-detail-v1/runtime/2x/news-detail-terminal-medallion.default.png')
  })

  it('registers independently reviewed build-intel route assets without promoting them', () => {
    const buildIntelAssets = candidateAssets.filter((asset) => asset.filePath.includes('/raster/build-intel-v1/'))
    const buildIntelSlotIds = [
      'asset_slot.build-intel-summary-medallion',
      'asset_slot.build-intel-card-medallion-shell',
      'asset_slot.build-intel-primary-action',
    ]
    const buildIntelSlots = candidateAssetSlots.filter((slot) => buildIntelSlotIds.includes(slot.slotId))

    expect(buildIntelAssets).toHaveLength(3)
    expect(buildIntelSlots).toHaveLength(3)
    expect(buildIntelAssets.every((asset) => asset.reviewStatus === 'independent_review_passed_for_canary')).toBe(true)
    expect(buildIntelSlots.every((slot) => slot.reviewStatus === 'independent_review_passed_for_canary')).toBe(true)
    expect(productionAssets.some((asset) => asset.filePath.includes('/raster/build-intel-v1/'))).toBe(false)
    expect(assetRuntimePath('build-intel-summary-medallion.default')).toBe('/assets/ui-v2/raster/build-intel-v1/runtime/2x/build-intel-summary-medallion.default.png')
    expect(assetRuntimePath('build-intel-card-medallion-shell.default')).toBe('/assets/ui-v2/raster/build-intel-v1/runtime/2x/build-intel-card-medallion-shell.default.png')
    expect(assetRuntimePath('build-intel-primary-action.default')).toBe('/assets/ui-v2/raster/build-intel-v1/runtime/2x/build-intel-primary-action.default.png')
    expect(assetRuntimePathForSlot('asset_slot.build-intel-summary-medallion')).toBe('/assets/ui-v2/raster/build-intel-v1/runtime/2x/build-intel-summary-medallion.default.png')
    expect(assetRuntimePathForSlot('asset_slot.build-intel-card-medallion-shell')).toBe('/assets/ui-v2/raster/build-intel-v1/runtime/2x/build-intel-card-medallion-shell.default.png')
    expect(assetRuntimePathForSlot('asset_slot.build-intel-primary-action')).toBe('/assets/ui-v2/raster/build-intel-v1/runtime/2x/build-intel-primary-action.default.png')
  })

  it('registers the complete news_home raster family at 2x for production runtime use', () => {
    const newsHomeAssets = productionAssets.filter((asset) => asset.filePath.includes('/raster/news-home-v1/'))
    expect(newsHomeAssets).toHaveLength(33)
    expect(new Set(newsHomeAssets.map((asset) => asset.assetId)).size).toBe(33)
    expect(newsHomeAssets.every((asset) => asset.reviewStatus === 'wechat_verified_production')).toBe(true)
    expect(newsHomeAssets.filter((asset) => asset.sourceClass === 'canonical_target_derivative')).toHaveLength(29)
    expect(newsHomeAssets.filter((asset) => asset.sourceClass === 'imagegen_raster')).toHaveLength(4)
    expect(assetRuntimePath('news-frame.panel')).toBe('/assets/ui-v2/raster/news-home-v1/runtime/2x/frames/news-frame.panel.png')
    expect(assetRuntimePath('news-favorite-control.default')).toBe('/assets/ui-v2/raster/news-home-v1/runtime/2x/actions/news-favorite-control.default.png')
  })

  it('resolves generated builds_home assets as non-production candidates', () => {
    const buildsHomeAssets = candidateAssets.filter((asset) => asset.filePath.includes('/raster/builds-home-v1/'))
    const buildsHomeSlots = candidateAssetSlots.filter((slot) => slot.slotId.startsWith('asset_slot.builds-'))
    expect(buildsHomeAssets).toHaveLength(23)
    expect(new Set(buildsHomeAssets.map((asset) => asset.assetId)).size).toBe(23)
    expect(buildsHomeSlots).toHaveLength(7)
    expect(buildsHomeAssets.every((asset) => asset.reviewStatus === 'generated_pending_isolated_review')).toBe(true)
    expect(buildsHomeSlots.every((slot) => slot.reviewStatus === 'generated_pending_isolated_review')).toBe(true)
    expect(productionAssets.some((asset) => asset.filePath.includes('/raster/builds-home-v1/'))).toBe(false)
    expect(assetRuntimePath('builds-surface-texture.default')).toBe('/assets/ui-v2/raster/builds-home-v1/runtime/2x/surfaces/builds-surface-texture.default.png')
    expect(assetRuntimePath('builds-frame.overview')).toBe('/assets/ui-v2/raster/builds-home-v1/runtime/2x/frames/builds-frame.overview.png')
    expect(assetRuntimePath('builds-evidence-medallion.talents')).toBe('/assets/ui-v2/raster/builds-home-v1/runtime/2x/evidence/builds-evidence-medallion.talents.png')
  })

  it('fails closed for unregistered ids', () => {
    expect(assetRuntimePath('not-registered')).toBeNull()
    expect(assetRuntimePath('product-tab-news-icon.default')).toBe('/assets/ui-v2/vector/product-tab-news-icon/default.svg')
  })

  it('supports an explicit HTTPS runtime root without corrupting the URL', () => {
    configureAssetRuntimeRoot('https://cdn.example.com/wow-assets/')
    expect(currentAssetRuntimeRoot()).toBe('https://cdn.example.com/wow-assets')
    expect(assetRuntimePath('news-frame.panel')).toBe(
      'https://cdn.example.com/wow-assets/raster/news-home-v1/runtime/2x/frames/news-frame.panel.png',
    )
    expect(() => configureAssetRuntimeRoot('http://cdn.example.com/wow-assets')).toThrow('must use HTTPS')
    expect(() => configureAssetRuntimeRoot('https://')).toThrow('must use HTTPS')
    expect(() => configureAssetRuntimeRoot('https://cdn.example.com/assets?mutable=1')).toThrow('must use HTTPS')
    configureAssetRuntimeRoot('/assets/ui-v2')
  })
})
