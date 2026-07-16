#!/usr/bin/env node
'use strict'

const crypto = require('node:crypto')
const { execFileSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const rasterRoot = path.join(root, 'packages/design-system/assets/raster/news-home-v1')
const targetPath = path.join(root, 'artifacts/ui-visual-targets/current/news-home.png')
const manifestPath = path.join(rasterRoot, 'manifest.json')
const generationRecordPath = path.join(rasterRoot, 'generation-record.json')
const derivationRecordPath = path.join(rasterRoot, 'target-derivation-record.json')

function option(name, fallback = '') {
  const prefix = `--${name}=`
  return process.argv.find((value) => value.startsWith(prefix))?.slice(prefix.length) ?? fallback
}

function sha256(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex')
}

function runMagick(args) {
  execFileSync('magick', args, { stdio: 'pipe' })
}

function dimensions(filePath) {
  const output = execFileSync('magick', ['identify', '-format', '%w %h', filePath], { encoding: 'utf8' }).trim()
  const [width, height] = output.split(/\s+/).map(Number)
  if (!width || !height) throw new Error(`Cannot read PNG dimensions: ${filePath}`)
  return { width, height }
}

function alphaBoundingBox(filePath) {
  const output = execFileSync('magick', [
    filePath,
    '-alpha', 'extract',
    '-threshold', '0',
    '-trim',
    '-format', '%wx%h%O',
    'info:',
  ], { encoding: 'utf8' }).trim()
  const match = output.match(/^(\d+)x(\d+)\+(\d+)\+(\d+)$/)
  if (!match) throw new Error(`Cannot read PNG alpha bounds: ${filePath} (${output})`)
  return [Number(match[3]), Number(match[4]), Number(match[1]), Number(match[2])]
}

function ensureParent(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
}

function crop(input, rect, output) {
  const [x, y, width, height] = rect
  ensureParent(output)
  runMagick([input, '-crop', `${width}x${height}+${x}+${y}`, '+repage', output])
}

function halfSize(input, output) {
  ensureParent(output)
  runMagick([input, '-filter', 'Lanczos', '-resize', '50%', output])
}

function centeredMatteCrop(input, rect, canvas, matte, output) {
  const tempCrop = path.join(tempRoot, `crop-${crypto.randomUUID()}.png`)
  crop(input, rect, tempCrop)
  ensureParent(output)
  runMagick([
    '-size', `${canvas[0]}x${canvas[1]}`,
    `xc:${matte}`,
    tempCrop,
    '-gravity', 'center',
    '-compose', 'over',
    '-composite',
    output,
  ])
}

function centeredColorKeyCrop(input, rect, canvas, matte, fuzz, output) {
  const tempCrop = path.join(tempRoot, `crop-${crypto.randomUUID()}.png`)
  crop(input, rect, tempCrop)
  ensureParent(output)
  runMagick([
    tempCrop,
    '-alpha', 'on',
    '-fuzz', fuzz,
    '-transparent', matte,
    '-gravity', 'center',
    '-background', 'none',
    '-extent', `${canvas[0]}x${canvas[1]}`,
    '-strip',
    `PNG32:${output}`,
  ])
}

function channelComponentCrop(input, rect, fuzz, areaThreshold, output) {
  const tempCrop = path.join(tempRoot, `crop-${crypto.randomUUID()}.png`)
  const raw = path.join(tempRoot, `raw-${crypto.randomUUID()}.png`)
  const mask = path.join(tempRoot, `mask-${crypto.randomUUID()}.png`)
  const softMask = path.join(tempRoot, `soft-mask-${crypto.randomUUID()}.png`)
  crop(input, rect, tempCrop)
  runMagick([
    tempCrop,
    '-alpha', 'on',
    '-fuzz', fuzz,
    '-fill', 'none',
    '-draw', 'color 0,0 floodfill color 73,0 floodfill color 0,73 floodfill color 73,73 floodfill',
    raw,
  ])
  runMagick([
    raw,
    '-channel', 'A',
    '-separate',
    '-threshold', '0',
    '-define', `connected-components:area-threshold=${areaThreshold}`,
    '-define', 'connected-components:mean-color=true',
    '-connected-components', '8',
    '-threshold', '50%',
    mask,
  ])
  runMagick([
    mask,
    '-morphology', 'Dilate', 'Disk:2',
    '-blur', '0x0.75',
    '-level', '15%,100%',
    '-fill', 'black',
    '-draw', 'rectangle 0,0 2,2 rectangle 71,0 73,2 rectangle 0,71 2,73 rectangle 71,71 73,73',
    softMask,
  ])
  ensureParent(output)
  runMagick([
    tempCrop,
    softMask,
    '-alpha', 'off',
    '-compose', 'CopyOpacity',
    '-composite',
    '-strip',
    output,
  ])
}

function clippedRect(rect, sourceRect) {
  const [x, y, width, height] = rect
  const [sourceX, sourceY, sourceWidth, sourceHeight] = sourceRect
  const left = Math.max(x, sourceX)
  const top = Math.max(y, sourceY)
  const right = Math.min(x + width, sourceX + sourceWidth)
  const bottom = Math.min(y + height, sourceY + sourceHeight)
  if (right <= left || bottom <= top) return null
  return [left - sourceX, top - sourceY, right - left, bottom - top]
}

function frameOverlay(input, sourceRect, keepRects, output) {
  const base = path.join(tempRoot, `base-${crypto.randomUUID()}.png`)
  const mask = path.join(tempRoot, `mask-${crypto.randomUUID()}.png`)
  crop(input, sourceRect, base)
  const localRects = keepRects.map((rect) => clippedRect(rect, sourceRect)).filter(Boolean)
  const draws = localRects.map(([x, y, width, height]) => `rectangle ${x},${y} ${x + width - 1},${y + height - 1}`)
  runMagick([
    '-size', `${sourceRect[2]}x${sourceRect[3]}`,
    'xc:black',
    '-fill', 'white',
    '-draw', draws.join(' '),
    mask,
  ])
  ensureParent(output)
  runMagick([base, mask, '-alpha', 'off', '-compose', 'CopyOpacity', '-composite', output])
}

function borderRects(rect, thickness) {
  const [x, y, width, height] = rect
  return [
    [x, y, width, thickness],
    [x, y + height - thickness, width, thickness],
    [x, y + thickness, thickness, height - thickness * 2],
    [x + width - thickness, y + thickness, thickness, height - thickness * 2],
  ]
}

function fileMetadata(filePath) {
  return {
    dimensions: dimensions(filePath),
    sha256: sha256(filePath),
    bytes: fs.statSync(filePath).size,
  }
}

function sourceTarget(region, regionRect, cropRect, extra = {}) {
  return {
    path: 'artifacts/ui-visual-targets/current/news-home.png',
    sha256: targetHash,
    normalizedDimensions: { width: 780, height: 1552 },
    region,
    regionRect,
    cropRect,
    ...extra,
  }
}

function targetAsset(definition) {
  const path2x = `runtime/2x/${definition.relativePath}`
  const path1x = `runtime/1x/${definition.relativePath}`
  const absolute2x = path.join(stageRoot, path2x)
  const absolute1x = path.join(stageRoot, path1x)
  halfSize(absolute2x, absolute1x)
  const metadata2x = fileMetadata(absolute2x)
  const metadata1x = fileMetadata(absolute1x)
  return {
    assetId: definition.assetId,
    slotId: definition.slotId,
    variant: definition.variant,
    path1x,
    path2x,
    dimensions: { '1x': metadata1x.dimensions, '2x': metadata2x.dimensions },
    hash: { '1x': metadata1x.sha256, '2x': metadata2x.sha256 },
    bytes: { '1x': metadata1x.bytes, '2x': metadata2x.bytes },
    sourceMaster: null,
    sourceGeneration: null,
    sourceTarget: definition.sourceTarget,
    crop: definition.crop ?? null,
    opticalContentBox2x: definition.opticalContentBox2x ?? null,
    transparentPadding: {
      '1x': { top: 0, right: 0, bottom: 0, left: 0 },
      '2x': { top: 0, right: 0, bottom: 0, left: 0 },
      thresholdAlpha: 8,
    },
    owner: definition.owner,
    sourceClass: 'canonical_target_derivative',
    reviewStatus,
    processing: definition.processing,
  }
}

function generatedAsset(definition) {
  const absolute2x = path.join(stageRoot, definition.path2x)
  const absolute1x = path.join(stageRoot, definition.path1x)
  const metadata2x = fileMetadata(absolute2x)
  const metadata1x = fileMetadata(absolute1x)
  return {
    ...definition.base,
    path1x: definition.path1x,
    path2x: definition.path2x,
    dimensions: { '1x': metadata1x.dimensions, '2x': metadata2x.dimensions },
    hash: { '1x': metadata1x.sha256, '2x': metadata2x.sha256 },
    bytes: { '1x': metadata1x.bytes, '2x': metadata2x.bytes },
  }
}

const heroSource = option('hero-source')
const heroGeneration = option('hero-generation', heroSource)
const reviewStatus = option('review-status', 'generated_pending_isolated_review')
const derivationStatusByReviewStatus = {
  generated_pending_isolated_review: 'built_pending_isolated_review',
  isolated_page_review_passed_pending_human_review: 'built_isolated_page_review_passed_pending_human_review',
}
if (!heroSource || !path.isAbsolute(heroSource) || !fs.existsSync(heroSource)) {
  throw new Error('--hero-source must point to the isolated imagegen-selected PNG')
}
if (!heroGeneration || !path.isAbsolute(heroGeneration)) {
  throw new Error('--hero-generation must be an absolute imagegen saved path')
}
if (!derivationStatusByReviewStatus[reviewStatus]) {
  throw new Error(`Unsupported --review-status: ${reviewStatus}`)
}

const registry = JSON.parse(fs.readFileSync(path.join(root, 'docs/design/current-ui/target-registry.json'), 'utf8'))
const targetEntry = registry.canonicalTargets.find((entry) => entry.route === 'news_home')
const targetHash = sha256(targetPath)
if (!targetEntry || targetEntry.sha256 !== targetHash) throw new Error('news_home canonical target hash changed')

const oldManifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))
const oldGenerationRecord = JSON.parse(fs.readFileSync(generationRecordPath, 'utf8'))
const utilityGeneration = oldGenerationRecord.generations.find((entry) => path.basename(entry.imagegenSavedPath) === 'exec-34910f1e-dd2e-4602-9e27-9206f39aaf86.png')
if (!utilityGeneration) throw new Error('Utility glyph generation provenance is missing')

const utilityMasterSource = path.join(rasterRoot, 'masters/news-utility-glyphs-master.png')
if (!fs.existsSync(utilityMasterSource)) throw new Error('Utility glyph master is missing')

const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-news-home-target-assets-'))
const stageRoot = path.join(tempRoot, 'news-home-v1')
const normalizedTarget = path.join(tempRoot, 'target-normalized.png')
fs.mkdirSync(stageRoot, { recursive: true })

try {
  runMagick([targetPath, '-resize', '780x1552!', normalizedTarget])

  const regions = {
    header: { rect: [0, 0, 780, 86], file: path.join(tempRoot, 'header.png') },
    dailyBrief: { rect: [0, 86, 780, 242], file: path.join(tempRoot, 'daily-brief.png') },
    featuredCarousel: { rect: [0, 340, 780, 372], file: path.join(tempRoot, 'featured-carousel.png') },
    channelDock: { rect: [0, 724, 780, 146], file: path.join(tempRoot, 'channel-dock.png') },
    rankedFeed: { rect: [0, 882, 780, 506], file: path.join(tempRoot, 'ranked-feed.png') },
    productTabBar: { rect: [0, 1406, 780, 142], file: path.join(tempRoot, 'product-tab-bar.png') },
  }
  for (const region of Object.values(regions)) crop(normalizedTarget, region.rect, region.file)

  const frameSpecs = [
    {
      assetId: 'news-frame.panel', variant: 'panel', owner: 'Frame', relativePath: 'frames/news-frame.panel.png',
      region: 'daily_brief', regionRef: regions.dailyBrief, sourceRect: [18, 0, 744, 242],
      keepRects: [
        [18, 0, 744, 10], [18, 229, 744, 13], [18, 8, 23, 222], [747, 8, 15, 222],
        [201, 5, 4, 151], [203, 154, 547, 4],
        [18, 0, 38, 28], [724, 0, 38, 28], [18, 214, 38, 28], [724, 214, 38, 28],
        ...borderRects([48, 169, 161, 56], 8), ...borderRects([228, 169, 161, 56], 8),
        ...borderRects([407, 169, 162, 56], 8), ...borderRects([587, 169, 159, 56], 8),
      ],
    },
    {
      assetId: 'news-frame.media', variant: 'media', owner: 'Frame', relativePath: 'frames/news-frame.media.png',
      region: 'featured_carousel', regionRef: regions.featuredCarousel, sourceRect: [18, 0, 744, 372],
      keepRects: [
        [18, 0, 744, 12], [18, 360, 744, 12], [18, 12, 12, 348], [750, 12, 12, 348],
        [18, 0, 34, 28], [728, 0, 34, 28], [18, 344, 34, 28], [728, 344, 34, 28],
      ],
    },
    {
      assetId: 'news-frame.tile', variant: 'tile', owner: 'ChannelDock', relativePath: 'frames/news-frame.tile.png',
      region: 'channel_dock', regionRef: regions.channelDock, sourceRect: [16, 0, 748, 146],
      keepRects: [
        [16, 0, 748, 18], [16, 130, 748, 16], [16, 18, 12, 112], [752, 18, 12, 112],
        [20, 18, 6, 112], [136, 18, 12, 112], [259, 18, 12, 112], [382, 18, 12, 112],
        [505, 18, 12, 112], [628, 18, 12, 112], [752, 18, 12, 112],
      ],
    },
    {
      assetId: 'news-frame.feed', variant: 'feed', owner: 'RankedFeed', relativePath: 'frames/news-frame.feed.png',
      region: 'ranked_feed', regionRef: regions.rankedFeed, sourceRect: [18, 0, 744, 504],
      keepRects: [
        [18, 0, 744, 9], [18, 0, 12, 486], [750, 0, 12, 486], [18, 68, 744, 12], [18, 483, 744, 23],
        [18, 0, 37, 39], [725, 0, 37, 39], [18, 57, 37, 23], [725, 57, 37, 23],
        [18, 477, 37, 29], [725, 477, 37, 29],
        [29, 177, 721, 1], [29, 283, 721, 1], [29, 389, 721, 1],
      ],
    },
    {
      assetId: 'news-frame.tab', variant: 'tab', owner: 'ProductTabBar', relativePath: 'frames/news-frame.tab.png',
      region: 'product_tab_bar', regionRef: regions.productTabBar, sourceRect: [4, 0, 772, 140],
      keepRects: [
        [4, 0, 772, 10], [4, 130, 772, 10], [4, 0, 14, 140], [762, 0, 14, 140],
        [198, 4, 6, 132], [390, 4, 6, 132], [582, 4, 6, 132],
      ],
    },
  ]

  for (const frame of frameSpecs) {
    const output = path.join(stageRoot, 'runtime/2x', frame.relativePath)
    frameOverlay(frame.regionRef.file, frame.sourceRect, frame.keepRects, output)
  }

  const directSpecs = [
    {
      assetId: 'news-daily-emblem.default', slotId: 'news.daily.emblem', variant: 'default', owner: 'Brief',
      relativePath: 'emblems/news-daily-emblem.default.png', region: 'daily_brief', regionRef: regions.dailyBrief,
      cropRect: [36, 12, 157, 156], opticalContentBox2x: [0, 0, 157, 156],
    },
    {
      assetId: 'news-favorite-control.default', slotId: 'news.favorite.control', variant: 'default', owner: 'PageFrame',
      relativePath: 'actions/news-favorite-control.default.png', region: 'header', regionRef: regions.header,
      cropRect: [686, 11, 70, 66], opticalContentBox2x: [0, 0, 70, 66],
    },
    {
      assetId: 'news-feed-fallback.neutral-01', slotId: 'news.feed.fallback', variant: 'neutral-01', owner: 'RankedFeed',
      relativePath: 'fallbacks/news-feed-fallback.neutral-01.png', region: 'ranked_feed', regionRef: regions.rankedFeed,
      cropRect: [47, 88, 123, 80], opticalContentBox2x: [0, 0, 123, 80],
    },
    {
      assetId: 'news-feed-fallback.neutral-02', slotId: 'news.feed.fallback', variant: 'neutral-02', owner: 'RankedFeed',
      relativePath: 'fallbacks/news-feed-fallback.neutral-02.png', region: 'ranked_feed', regionRef: regions.rankedFeed,
      cropRect: [47, 88, 123, 80], opticalContentBox2x: [0, 0, 123, 80],
    },
    {
      assetId: 'news-feed-fallback.neutral-03', slotId: 'news.feed.fallback', variant: 'neutral-03', owner: 'RankedFeed',
      relativePath: 'fallbacks/news-feed-fallback.neutral-03.png', region: 'ranked_feed', regionRef: regions.rankedFeed,
      cropRect: [47, 88, 123, 80], opticalContentBox2x: [0, 0, 123, 80],
    },
    {
      assetId: 'news-feed-fallback.neutral-04', slotId: 'news.feed.fallback', variant: 'neutral-04', owner: 'RankedFeed',
      relativePath: 'fallbacks/news-feed-fallback.neutral-04.png', region: 'ranked_feed', regionRef: regions.rankedFeed,
      cropRect: [47, 88, 123, 80], opticalContentBox2x: [0, 0, 123, 80],
    },
  ]

  for (const direct of directSpecs) {
    crop(direct.regionRef.file, direct.cropRect, path.join(stageRoot, 'runtime/2x', direct.relativePath))
  }

  const channelSpecs = [
    { assetId: 'news-channel-glyph.all', variant: 'all', relativePath: 'channels/news-channel-glyph.all.png', cropRect: [44, 24, 74, 74], fuzz: '8%', areaThreshold: 12, opticalContentBox2x: [6, 0, 66, 67] },
    { assetId: 'news-channel-glyph.class', variant: 'class', relativePath: 'channels/news-channel-glyph.class.png', cropRect: [168, 24, 74, 74], fuzz: '9%', areaThreshold: 5, opticalContentBox2x: [7, 1, 57, 64] },
    { assetId: 'news-channel-glyph.mythic', variant: 'mythic', relativePath: 'channels/news-channel-glyph.mythic.png', cropRect: [292, 24, 74, 74], fuzz: '8.5%', areaThreshold: 5, opticalContentBox2x: [4, 0, 60, 66] },
    { assetId: 'news-channel-glyph.gear', variant: 'gear', relativePath: 'channels/news-channel-glyph.gear.png', cropRect: [416, 24, 74, 74], fuzz: '7.5%', areaThreshold: 5, opticalContentBox2x: [0, 2, 66, 64] },
    { assetId: 'news-channel-glyph.system', variant: 'system', relativePath: 'channels/news-channel-glyph.system.png', cropRect: [540, 24, 74, 74], fuzz: '8%', areaThreshold: 5, opticalContentBox2x: [4, 2, 59, 61] },
    { assetId: 'news-channel-glyph.more', variant: 'more', relativePath: 'channels/news-channel-glyph.more.png', cropRect: [664, 24, 74, 74], fuzz: '8.5%', areaThreshold: 5, opticalContentBox2x: [9, 9, 47, 47] },
  ].map((spec) => ({ ...spec, slotId: 'news.channel.glyphs', owner: 'ChannelDock', region: 'channel_dock', regionRef: regions.channelDock }))

  const tabSpecs = [
    { assetId: 'product-tab-glyph.news', variant: 'news', relativePath: 'product-tabs/product-tab-glyph.news.png', cropRect: [76, 16, 70, 72], matte: '#171611', opticalContentBox2x: [5, 4, 70, 72], runtimeOffset2x: [11, -4] },
    { assetId: 'product-tab-glyph.spec', variant: 'spec', relativePath: 'product-tabs/product-tab-glyph.spec.png', cropRect: [262, 14, 78, 78], matte: '#101314', opticalContentBox2x: [1, 1, 78, 78], runtimeOffset2x: [7, -3] },
    { assetId: 'product-tab-glyph.captain', variant: 'captain', relativePath: 'product-tabs/product-tab-glyph.captain.png', cropRect: [456, 16, 68, 76], matte: '#101314', opticalContentBox2x: [6, 2, 68, 76], runtimeOffset2x: [4, -2] },
    { assetId: 'product-tab-glyph.profile', variant: 'profile', relativePath: 'product-tabs/product-tab-glyph.profile.png', cropRect: [646, 14, 66, 80], matte: '#101314', opticalContentBox2x: [7, 0, 66, 80], runtimeOffset2x: [-1, -2] },
  ].map((spec) => ({ ...spec, slotId: 'product.tab.glyphs', owner: 'ProductTabBar', region: 'product_tab_bar', regionRef: regions.productTabBar, canvas: [80, 80] }))

  const matteSpecs = [
    { assetId: 'news-metric-glyph.headline', slotId: 'news.metric.glyphs', variant: 'headline', owner: 'Brief', relativePath: 'metrics/news-metric-glyph.headline.png', regionRef: regions.dailyBrief, region: 'daily_brief', cropRect: [72, 182, 28, 33], canvas: [36, 36], matte: '#141719' },
    { assetId: 'news-metric-glyph.updates', slotId: 'news.metric.glyphs', variant: 'updates', owner: 'Brief', relativePath: 'metrics/news-metric-glyph.updates.png', regionRef: regions.dailyBrief, region: 'daily_brief', cropRect: [253, 182, 34, 33], canvas: [36, 36], matte: '#141719' },
    { assetId: 'news-metric-glyph.balance', slotId: 'news.metric.glyphs', variant: 'balance', owner: 'Brief', relativePath: 'metrics/news-metric-glyph.balance.png', regionRef: regions.dailyBrief, region: 'daily_brief', cropRect: [433, 181, 34, 34], canvas: [36, 36], matte: '#141719' },
    { assetId: 'news-metric-glyph.events', slotId: 'news.metric.glyphs', variant: 'events', owner: 'Brief', relativePath: 'metrics/news-metric-glyph.events.png', regionRef: regions.dailyBrief, region: 'daily_brief', cropRect: [611, 182, 34, 33], canvas: [36, 36], matte: '#141719' },
    { assetId: 'news-evidence-glyph.source', slotId: 'news.evidence.glyph', variant: 'source', owner: 'EvidenceBadge', relativePath: 'evidence/news-evidence-glyph.source.png', regionRef: regions.rankedFeed, region: 'ranked_feed', cropRect: [198, 140, 21, 22], canvas: [22, 22], matte: '#0d1011' },
    { assetId: 'news-bookmark-glyph.default', slotId: 'news.bookmark.glyph', variant: 'default', owner: 'RankedFeed', relativePath: 'actions/news-bookmark-glyph.default.png', regionRef: regions.rankedFeed, region: 'ranked_feed', cropRect: [701, 110, 26, 35], canvas: [28, 36], matte: '#0d1011' },
  ]

  for (const spec of channelSpecs) {
    const output = path.join(stageRoot, 'runtime/2x', spec.relativePath)
    channelComponentCrop(spec.regionRef.file, spec.cropRect, spec.fuzz, spec.areaThreshold, output)
    spec.opticalContentBox2x = alphaBoundingBox(output)
  }
  for (const spec of tabSpecs) {
    const output = path.join(stageRoot, 'runtime/2x', spec.relativePath)
    centeredColorKeyCrop(spec.regionRef.file, spec.cropRect, spec.canvas, spec.matte, '8%', output)
    spec.opticalContentBox2x = alphaBoundingBox(output)
  }
  for (const spec of matteSpecs) {
    centeredMatteCrop(spec.regionRef.file, spec.cropRect, spec.canvas, spec.matte, path.join(stageRoot, 'runtime/2x', spec.relativePath))
  }

  const favoriteDefault = path.join(stageRoot, 'runtime/2x/actions/news-favorite-control.default.png')
  const favoriteSelected = path.join(stageRoot, 'runtime/2x/actions/news-favorite-control.selected.png')
  ensureParent(favoriteSelected)
  runMagick([favoriteDefault, '-modulate', '108,112,100', favoriteSelected])

  const bookmarkDefault = path.join(stageRoot, 'runtime/2x/actions/news-bookmark-glyph.default.png')
  const bookmarkSelected = path.join(stageRoot, 'runtime/2x/actions/news-bookmark-glyph.selected.png')
  ensureParent(bookmarkSelected)
  runMagick([bookmarkDefault, '-modulate', '118,120,100', bookmarkSelected])

  const utilityMasterPath = path.join(stageRoot, 'masters/news-utility-glyphs-master.png')
  ensureParent(utilityMasterPath)
  fs.copyFileSync(utilityMasterSource, utilityMasterPath)

  const heroMasterPath = path.join(stageRoot, 'masters/news-hero-fallback-master-v3.png')
  ensureParent(heroMasterPath)
  fs.copyFileSync(heroSource, heroMasterPath)
  const hero2x = path.join(stageRoot, 'runtime/2x/fallbacks/news-hero-fallback.neutral-editorial.png')
  const hero1x = path.join(stageRoot, 'runtime/1x/fallbacks/news-hero-fallback.neutral-editorial.png')
  ensureParent(hero2x)
  runMagick([heroMasterPath, '-resize', '832x400^', '-gravity', 'center', '-extent', '832x400', hero2x])
  halfSize(hero2x, hero1x)

  const retainedEvidenceIds = new Set([
    'news-evidence-glyph.verified',
    'news-evidence-glyph.unavailable',
    'news-evidence-glyph.fallback',
  ])
  const retainedEvidence = oldManifest.assets.filter((asset) => retainedEvidenceIds.has(asset.assetId))
  if (retainedEvidence.length !== 3) throw new Error('Expected three retained evidence assets')
  for (const asset of retainedEvidence) {
    for (const density of ['1x', '2x']) {
      const source = path.join(rasterRoot, asset[`path${density}`])
      const destination = path.join(stageRoot, asset[`path${density}`])
      ensureParent(destination)
      fs.copyFileSync(source, destination)
    }
  }

  const assets = []
  for (const frame of frameSpecs) {
    assets.push(targetAsset({
      assetId: frame.assetId,
      slotId: 'news.frame.family',
      variant: frame.variant,
      owner: frame.owner,
      relativePath: frame.relativePath,
      sourceTarget: sourceTarget(frame.region, frame.regionRef.rect, frame.sourceRect, { keepRects: frame.keepRects }),
      crop: { x: frame.sourceRect[0], y: frame.sourceRect[1], width: frame.sourceRect[2], height: frame.sourceRect[3], normalizedRegion: frame.region },
      processing: { kind: 'canonical_target_frame_overlay', keepRectCount: frame.keepRects.length },
    }))
  }

  for (const direct of directSpecs) {
    assets.push(targetAsset({
      ...direct,
      sourceTarget: sourceTarget(direct.region, direct.regionRef.rect, direct.cropRect, { includesBackground: true }),
      crop: { x: direct.cropRect[0], y: direct.cropRect[1], width: direct.cropRect[2], height: direct.cropRect[3], normalizedRegion: direct.region },
      processing: { kind: 'canonical_target_matted_crop' },
    }))
  }

  for (const spec of channelSpecs) {
    assets.push(targetAsset({
      assetId: spec.assetId, slotId: spec.slotId, variant: spec.variant, owner: spec.owner, relativePath: spec.relativePath,
      sourceTarget: sourceTarget(spec.region, spec.regionRef.rect, spec.cropRect, {
        includesBackground: false,
        backgroundRemoval: 'four_corner_floodfill_connected_components_soft_matte',
      }),
      crop: { x: spec.cropRect[0], y: spec.cropRect[1], width: spec.cropRect[2], height: spec.cropRect[3], normalizedRegion: spec.region },
      opticalContentBox2x: spec.opticalContentBox2x,
      processing: {
        kind: 'canonical_target_transparent_foreground',
        canvas2x: { width: 74, height: 74 },
        alphaMethod: 'four_corner_floodfill_connected_components',
        fuzz: spec.fuzz,
        areaThreshold: spec.areaThreshold,
        softMatte: { dilate: 'Disk:2', blur: '0x0.75', blackPoint: '15%' },
        placement: 'fixed_target_canvas',
      },
    }))
  }

  for (const spec of tabSpecs) {
    assets.push(targetAsset({
      assetId: spec.assetId, slotId: spec.slotId, variant: spec.variant, owner: spec.owner, relativePath: spec.relativePath,
      sourceTarget: sourceTarget(spec.region, spec.regionRef.rect, spec.cropRect, {
        includesBackground: false,
        matte: spec.matte,
        backgroundRemoval: 'global_color_key_8_percent',
      }),
      crop: { x: spec.cropRect[0], y: spec.cropRect[1], width: spec.cropRect[2], height: spec.cropRect[3], normalizedRegion: spec.region },
      opticalContentBox2x: spec.opticalContentBox2x,
      processing: {
        kind: 'canonical_target_transparent_foreground',
        canvas2x: { width: spec.canvas[0], height: spec.canvas[1] },
        alphaMethod: 'global_color_key',
        fuzz: '8%',
        runtimeOffset2x: spec.runtimeOffset2x,
      },
    }))
  }

  for (const spec of matteSpecs) {
    assets.push(targetAsset({
      assetId: spec.assetId, slotId: spec.slotId, variant: spec.variant, owner: spec.owner, relativePath: spec.relativePath,
      sourceTarget: sourceTarget(spec.region, spec.regionRef.rect, spec.cropRect, { includesBackground: true, matte: spec.matte }),
      crop: { x: spec.cropRect[0], y: spec.cropRect[1], width: spec.cropRect[2], height: spec.cropRect[3], normalizedRegion: spec.region },
      opticalContentBox2x: [
        Math.floor((spec.canvas[0] - spec.cropRect[2]) / 2),
        Math.floor((spec.canvas[1] - spec.cropRect[3]) / 2),
        spec.cropRect[2],
        spec.cropRect[3],
      ],
      processing: { kind: 'canonical_target_matted_crop', canvas2x: { width: spec.canvas[0], height: spec.canvas[1] } },
    }))
  }

  assets.push(targetAsset({
    assetId: 'news-favorite-control.selected', slotId: 'news.favorite.control', variant: 'selected', owner: 'PageFrame',
    relativePath: 'actions/news-favorite-control.selected.png',
    sourceTarget: sourceTarget('header', regions.header.rect, [686, 11, 70, 66], { includesBackground: true }),
    crop: { x: 686, y: 11, width: 70, height: 66, normalizedRegion: 'header' },
    opticalContentBox2x: [0, 0, 70, 66],
    processing: { kind: 'canonical_target_crop_selected_tone', modulate: '108,112,100' },
  }))
  assets.push(targetAsset({
    assetId: 'news-bookmark-glyph.selected', slotId: 'news.bookmark.glyph', variant: 'selected', owner: 'RankedFeed',
    relativePath: 'actions/news-bookmark-glyph.selected.png',
    sourceTarget: sourceTarget('ranked_feed', regions.rankedFeed.rect, [701, 110, 26, 35], { includesBackground: true, matte: '#0d1011' }),
    crop: { x: 701, y: 110, width: 26, height: 35, normalizedRegion: 'ranked_feed' },
    opticalContentBox2x: [1, 0, 26, 35],
    processing: { kind: 'canonical_target_crop_selected_tone', modulate: '118,120,100' },
  }))

  for (const asset of retainedEvidence) {
    assets.push(generatedAsset({
      path1x: asset.path1x,
      path2x: asset.path2x,
      base: {
        ...asset,
        dimensions: undefined,
        hash: undefined,
        bytes: undefined,
        sourceClass: 'imagegen_raster',
        reviewStatus,
      },
    }))
  }

  assets.push(generatedAsset({
    path1x: 'runtime/1x/fallbacks/news-hero-fallback.neutral-editorial.png',
    path2x: 'runtime/2x/fallbacks/news-hero-fallback.neutral-editorial.png',
    base: {
      assetId: 'news-hero-fallback.neutral-editorial',
      slotId: 'news.hero.fallback',
      variant: 'neutral-editorial',
      sourceMaster: 'masters/news-hero-fallback-master-v3.png',
      sourceGeneration: heroGeneration,
      sourceTarget: null,
      crop: null,
      opticalContentBox2x: [0, 0, 832, 400],
      transparentPadding: {
        '1x': { top: 0, right: 0, bottom: 0, left: 0 },
        '2x': { top: 0, right: 0, bottom: 0, left: 0 },
        thresholdAlpha: 8,
      },
      owner: 'Carousel',
      sourceClass: 'imagegen_raster',
      reviewStatus,
      processing: { kind: 'imagegen_reference_edit_clean_scene', outputAspect: 2.08 },
    },
  }))

  const requiredOrder = [
    'news-frame.panel', 'news-frame.media', 'news-frame.tile', 'news-frame.feed', 'news-frame.tab',
    'news-daily-emblem.default',
    'news-channel-glyph.all', 'news-channel-glyph.class', 'news-channel-glyph.mythic', 'news-channel-glyph.gear', 'news-channel-glyph.system', 'news-channel-glyph.more',
    'product-tab-glyph.news', 'product-tab-glyph.spec', 'product-tab-glyph.captain', 'product-tab-glyph.profile',
    'news-hero-fallback.neutral-editorial',
    'news-feed-fallback.neutral-01', 'news-feed-fallback.neutral-02', 'news-feed-fallback.neutral-03', 'news-feed-fallback.neutral-04',
    'news-metric-glyph.headline', 'news-metric-glyph.updates', 'news-metric-glyph.balance', 'news-metric-glyph.events',
    'news-evidence-glyph.source', 'news-evidence-glyph.verified', 'news-evidence-glyph.unavailable', 'news-evidence-glyph.fallback',
    'news-favorite-control.default', 'news-favorite-control.selected',
    'news-bookmark-glyph.default', 'news-bookmark-glyph.selected',
  ]
  const byId = new Map(assets.map((asset) => [asset.assetId, asset]))
  const orderedAssets = requiredOrder.map((assetId) => {
    const asset = byId.get(assetId)
    if (!asset) throw new Error(`Missing rebuilt asset: ${assetId}`)
    return asset
  })
  if (new Set(orderedAssets.map((asset) => asset.assetId)).size !== 33) throw new Error('Rebuilt asset ids are not unique')

  const utilityMasterMetadata = fileMetadata(utilityMasterPath)
  const heroMasterMetadata = fileMetadata(heroMasterPath)
  const masters = [
    {
      path: 'masters/news-hero-fallback-master-v3.png',
      sourceGeneration: heroGeneration,
      dimensions: heroMasterMetadata.dimensions,
      sha256: heroMasterMetadata.sha256,
      bytes: heroMasterMetadata.bytes,
    },
    {
      path: 'masters/news-utility-glyphs-master.png',
      sourceGeneration: utilityGeneration.imagegenSavedPath,
      dimensions: utilityMasterMetadata.dimensions,
      sha256: utilityMasterMetadata.sha256,
      bytes: utilityMasterMetadata.bytes,
    },
  ]

  const manifest = {
    schemaVersion: 2,
    status: reviewStatus,
    route: 'news_home',
    target: { path: targetEntry.path, sha256: targetEntry.sha256 },
    assetCount: orderedAssets.length,
    masterCount: masters.length,
    masters,
    assets: orderedAssets,
  }

  const generationRecord = {
    schemaVersion: 2,
    generations: [
      utilityGeneration,
      {
        promptSummary: 'Reference edit of the canonical carousel scene into a clean anonymous non-factual fantasy architecture fallback without UI or text.',
        imagegenSavedPath: heroGeneration,
        selectedPath: heroSource,
        generatedAt: new Date().toISOString(),
        targetSha256: targetEntry.sha256,
      },
    ],
    stateDerivationPolicy: {
      favorite: 'default is a canonical-target matted control crop; selected uses deterministic tone only',
      bookmark: 'default is a canonical-target matted glyph crop; selected uses deterministic tone only',
    },
  }

  const derivationRecord = {
    schemaVersion: 1,
    status: derivationStatusByReviewStatus[reviewStatus],
    route: 'news_home',
    target: { path: targetEntry.path, sha256: targetEntry.sha256 },
    normalization: { width: 780, height: 1552, method: 'forced review-grid normalization' },
    targetDerivedAssetCount: orderedAssets.filter((asset) => asset.sourceClass === 'canonical_target_derivative').length,
    imagegenAssetCount: orderedAssets.filter((asset) => asset.sourceClass === 'imagegen_raster').length,
    derivations: orderedAssets
      .filter((asset) => asset.sourceClass === 'canonical_target_derivative')
      .map((asset) => ({ assetId: asset.assetId, sourceTarget: asset.sourceTarget, processing: asset.processing })),
  }

  fs.rmSync(path.join(rasterRoot, 'runtime'), { recursive: true, force: true })
  fs.rmSync(path.join(rasterRoot, 'masters'), { recursive: true, force: true })
  fs.renameSync(path.join(stageRoot, 'runtime'), path.join(rasterRoot, 'runtime'))
  fs.renameSync(path.join(stageRoot, 'masters'), path.join(rasterRoot, 'masters'))
  fs.writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`)
  fs.writeFileSync(generationRecordPath, `${JSON.stringify(generationRecord, null, 2)}\n`)
  fs.writeFileSync(derivationRecordPath, `${JSON.stringify(derivationRecord, null, 2)}\n`)

  process.stdout.write(`${JSON.stringify({
    status: 'pass',
    assetCount: manifest.assetCount,
    masterCount: manifest.masterCount,
    generationCount: generationRecord.generations.length,
    targetDerivedAssetCount: derivationRecord.targetDerivedAssetCount,
    imagegenAssetCount: derivationRecord.imagegenAssetCount,
    targetSha256: targetEntry.sha256,
    reviewStatus,
  }, null, 2)}\n`)
} finally {
  fs.rmSync(tempRoot, { recursive: true, force: true })
}
