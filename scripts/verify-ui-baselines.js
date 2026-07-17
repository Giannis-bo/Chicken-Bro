#!/usr/bin/env node
'use strict'

const { connectMiniProgram, timeout } = require('./wechat-automator')

const operationTimeoutMs = 8000

async function elementGeometry(page, selector, includeText = false) {
  const element = await timeout(page.$(selector), operationTimeoutMs, `query ${selector}`)
  if (!element) return null
  const [offset, size] = await Promise.all([
    timeout(element.offset(), operationTimeoutMs, `${selector} offset`),
    timeout(element.size(), operationTimeoutMs, `${selector} size`),
  ])
  return {
    offset,
    size,
    ...(includeText ? { text: await timeout(element.text(), operationTimeoutMs, `${selector} text`) } : {}),
  }
}

async function elementText(page, selector) {
  const element = await timeout(page.$(selector), operationTimeoutMs, `query ${selector}`)
  return element ? timeout(element.text(), operationTimeoutMs, `${selector} text`) : null
}

async function elementGeometries(page, selector) {
  const elements = await timeout(page.$$(selector), operationTimeoutMs, `query all ${selector}`)
  return Promise.all(elements.map(async (element) => ({
    offset: await timeout(element.offset(), operationTimeoutMs, `${selector} offset`),
    size: await timeout(element.size(), operationTimeoutMs, `${selector} size`),
  })))
}

async function measure(miniProgram, baseline) {
  const page = await timeout(miniProgram.reLaunch(baseline.url), operationTimeoutMs, `reLaunch ${baseline.id}`)
  if (!page) throw new Error(`reLaunch ${baseline.id} returned no page`)
  await new Promise((resolve) => setTimeout(resolve, 600))
  let carousel = null
  if (baseline.carouselAutoplay) {
    const titleSelector = '.wx-data-role-featured-title'
    const availableDots = await timeout(
      page.$$('.wx-data-role-carousel-dot.wx-data-available-true'),
      operationTimeoutMs,
      'query available carousel items',
    )
    const before = await elementText(page, titleSelector)
    let after = before
    if (availableDots.length >= 2) {
      await new Promise((resolve) => setTimeout(resolve, 6000))
      after = await elementText(page, titleSelector)
    }
    carousel = { availableItemCount: availableDots.length, before, after }
  }
  let metricAlignment = null
  if (baseline.metricOpticalAlignment) {
    const [glyphs, labels, values] = await Promise.all([
      elementGeometries(page, '.wx-style-newshomebriefmetricglyph'),
      elementGeometries(page, '.wx-style-newshomebriefmetriclabel'),
      elementGeometries(page, '.wx-style-newshomebriefmetricvalue'),
    ])
    metricAlignment = glyphs.map((glyph, index) => {
      const label = labels[index]
      const value = values[index]
      const glyphCenter = glyph.offset.top + glyph.size.height / 2
      const labelCenter = label ? label.offset.top + label.size.height / 2 : null
      const valueCenter = value ? value.offset.top + value.size.height / 2 : null
      return {
        glyphCenter,
        labelCenter,
        valueCenter,
        opticalOffset: labelCenter === null ? null : glyphCenter - labelCenter,
      }
    })
  }
  let evidenceTextRhythm = null
  if (baseline.evidenceTextRhythm) {
    const [titles, statuses, values, medallions] = await Promise.all([
      elementGeometries(page, '.wx-style-evidencecontentgrid .wx-style-evidencetitle'),
      elementGeometries(page, '.wx-style-evidencecontentgrid .wx-style-evidencestatus'),
      elementGeometries(page, '.wx-style-evidencecontentgrid .wx-style-evidencevalue'),
      elementGeometries(page, '.wx-style-evidencecontentgrid .wx-style-evidencemedallion'),
    ])
    evidenceTextRhythm = titles.map((title, index) => {
      const status = statuses[index]
      const value = values[index]
      const medallion = medallions[index]
      const titleStatusGap = status ? status.offset.top - title.offset.top - title.size.height : null
      const statusValueGap = status && value ? value.offset.top - status.offset.top - status.size.height : null
      const copyCenter = value ? (title.offset.top + value.offset.top + value.size.height) / 2 : null
      const medallionCenter = medallion ? medallion.offset.top + medallion.size.height / 2 : null
      return { titleStatusGap, statusValueGap, copyCenter, medallionCenter }
    })
  }
  return {
    id: baseline.id,
    path: page.path,
    shell: await elementGeometry(page, '.wx-style-shell'),
    header: await elementGeometry(page, '.wx-style-pageframeheader'),
    title: await elementGeometry(page, '.wx-style-pageframetitletext', true),
    back: await elementGeometry(page, '.wx-style-pageframebackcontrol'),
    carousel,
    metricAlignment,
    evidenceTextRhythm,
  }
}

function closeTo(actual, expected, tolerance = 1) {
  return typeof actual === 'number' && Math.abs(actual - expected) <= tolerance
}

async function main() {
  let miniProgram
  try {
    miniProgram = await connectMiniProgram()
    const systemInfo = await timeout(miniProgram.systemInfo(), operationTimeoutMs, 'systemInfo')
    const baselines = []
    for (const baseline of [
      {
        id: 'news_home',
        url: '/pages/news/news',
        chrome: 'root',
        headerInset: 0,
        carouselAutoplay: true,
        metricOpticalAlignment: true,
      },
      {
        id: 'builds_home',
        url: '/pages/builds/builds',
        chrome: 'root',
        headerInset: 0,
        evidenceTextRhythm: true,
      },
      { id: 'simulator_home', url: '/pages/simulator/simulator', chrome: 'root', headerInset: 0 },
      { id: 'news_detail', url: '/pages/news/detail?id=architecture-preflight', chrome: 'pushed', headerInset: 6.77 },
    ]) {
      baselines.push({ ...baseline, ...await measure(miniProgram, baseline) })
    }

    const failures = []
    for (const baseline of baselines) {
      if (!baseline.shell || !baseline.header || !baseline.title) {
        failures.push(`${baseline.id}: missing shared shell/header/title owner`)
        continue
      }
      if (!closeTo(baseline.shell.size.width, systemInfo.windowWidth)) failures.push(`${baseline.id}: shell width drift`)
      if (!closeTo(baseline.header.offset.left, baseline.headerInset)) failures.push(`${baseline.id}: header leading inset drift`)
      if (!closeTo(baseline.header.size.width, systemInfo.windowWidth - baseline.headerInset * 2)) failures.push(`${baseline.id}: header width drift`)
      if (baseline.header.offset.top < systemInfo.safeArea.top || baseline.header.offset.top > systemInfo.safeArea.top + 5) {
        failures.push(`${baseline.id}: header safe-area origin drift`)
      }
      if (baseline.chrome === 'root') {
        if (baseline.back) failures.push(`${baseline.id}: root page rendered pushed back control`)
        if (!closeTo(baseline.title.offset.left, 16)) failures.push(`${baseline.id}: root title is not on the shared leading edge`)
      } else {
        if (!baseline.back) failures.push(`${baseline.id}: pushed page lost back control`)
        if (baseline.title.offset.left <= 40) failures.push(`${baseline.id}: pushed title fell into the root title slot`)
      }
      if (baseline.carouselAutoplay) {
        if (!baseline.carousel || baseline.carousel.availableItemCount < 2) {
          failures.push(`${baseline.id}: autoplay baseline has fewer than two available items`)
        } else if (!baseline.carousel.before || !baseline.carousel.after) {
          failures.push(`${baseline.id}: featured carousel title is missing`)
        } else if (baseline.carousel.before === baseline.carousel.after) {
          failures.push(`${baseline.id}: featured carousel did not advance after one interval`)
        }
      }
      if (baseline.metricOpticalAlignment) {
        if (!baseline.metricAlignment || baseline.metricAlignment.length !== 4) {
          failures.push(`${baseline.id}: daily brief metric alignment evidence is incomplete`)
        } else {
          baseline.metricAlignment.forEach((metric, index) => {
            if (!closeTo(metric.labelCenter, metric.valueCenter, 0.1)) {
              failures.push(`${baseline.id}: metric ${index + 1} label/value centers drifted`)
            }
            if (!closeTo(metric.opticalOffset, 0.75, 0.3)) {
              failures.push(`${baseline.id}: metric ${index + 1} glyph optical correction drifted`)
            }
          })
        }
      }
      if (baseline.evidenceTextRhythm) {
        if (!baseline.evidenceTextRhythm || baseline.evidenceTextRhythm.length !== 4) {
          failures.push(`${baseline.id}: evidence grid text rhythm evidence is incomplete`)
        } else {
          baseline.evidenceTextRhythm.forEach((item, index) => {
            if (!closeTo(item.titleStatusGap, 4, 0.25) || !closeTo(item.statusValueGap, 4, 0.25)) {
              failures.push(`${baseline.id}: evidence item ${index + 1} does not use equal three-line spacing`)
            }
            if (!closeTo(item.copyCenter, item.medallionCenter, 0.5)) {
              failures.push(`${baseline.id}: evidence item ${index + 1} copy is not centered with its medallion`)
            }
          })
        }
      }
    }

    console.log(JSON.stringify({
      status: failures.length ? 'fail' : 'pass',
      evidence: 'structured_wechat_runtime_geometry',
      visualPixelReview: 'UNVERIFIED',
      device: {
        model: systemInfo.model,
        windowWidth: systemInfo.windowWidth,
        windowHeight: systemInfo.windowHeight,
        safeTop: systemInfo.safeArea.top,
      },
      baselines,
      failures,
    }, null, 2))
    if (failures.length) process.exitCode = 1
  } finally {
    if (miniProgram) miniProgram.disconnect()
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error))
  process.exit(1)
})
