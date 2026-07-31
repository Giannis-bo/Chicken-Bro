#!/usr/bin/env node
'use strict'

const fs = require('node:fs')
const path = require('node:path')
const { writeBoundedJsonAtomic } = require('./bounded-json-detail')
const {
  normalizeSpecMatrix,
  requiredActions,
  summarizeWechatGearCatalogOnlyClassReports,
  summarizeWechatGearClassReports,
  summarizeWechatGearPreviewClassReports,
  summarizeWechatGearSlotShardReports,
} = require('./wechat-gear-matrix-contract')

const requestTimeoutMs = 15000

function requiredEnvironment(name) {
  const value = String(process.env[name] ?? '').trim()
  if (!value) throw new Error(`${name} is required`)
  return value
}

function readJson(filePath, label) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'))
  } catch (error) {
    throw new Error(`${label} is not readable JSON at ${filePath}: ${error instanceof Error ? error.message : String(error)}`)
  }
}

async function fetchJson(url, label) {
  const response = await fetch(url, { signal: AbortSignal.timeout(requestTimeoutMs) })
  const text = await response.text()
  if (!response.ok) throw new Error(`${label} HTTP ${response.status}: ${text.slice(0, 240)}`)
  try {
    return JSON.parse(text)
  } catch {
    throw new Error(`${label} did not return JSON`)
  }
}

async function main() {
  const apiBaseUrl = requiredEnvironment('WECHAT_GEAR_MATRIX_API_BASE_URL')
  const buildMetadataPath = path.resolve(requiredEnvironment('WECHAT_GEAR_MATRIX_BUILD_METADATA'))
  const outputPath = path.resolve(requiredEnvironment('WECHAT_GEAR_MATRIX_SUMMARY_OUTPUT'))
  const phase = String(process.env.WECHAT_GEAR_MATRIX_SUMMARY_PHASE || 'full').trim()
  if (
    phase !== 'full'
    && phase !== 'preview_catalog_actions'
    && phase !== 'preview_catalog_only_classes'
    && phase !== 'preview_catalog_slot_shards'
  ) {
    throw new Error(`unsupported WECHAT_GEAR_MATRIX_SUMMARY_PHASE ${phase}`)
  }
  const rawReportPaths = JSON.parse(requiredEnvironment('WECHAT_GEAR_MATRIX_REPORTS'))
  if (!Array.isArray(rawReportPaths) || rawReportPaths.some((item) => typeof item !== 'string')) {
    throw new Error('WECHAT_GEAR_MATRIX_REPORTS must be a JSON array of report paths')
  }
  const reportPaths = rawReportPaths.map((item) => path.resolve(item))
  const build = readJson(buildMetadataPath, 'WeChat build metadata')
  if (!build?.gitHead || !build?.sourceHash) throw new Error('WeChat build metadata lacks gitHead/sourceHash')
  const reports = reportPaths.map((filePath) => readJson(filePath, 'WeChat class matrix report'))
  const home = await fetchJson(new URL('/api/builds/home', apiBaseUrl), 'builds home')
  const expectedSpecs = normalizeSpecMatrix(home)
  const summary = phase === 'preview_catalog_only_classes'
    ? summarizeWechatGearCatalogOnlyClassReports(reports, expectedSpecs, build)
    : phase === 'preview_catalog_slot_shards'
    ? summarizeWechatGearSlotShardReports(reports, expectedSpecs, build)
    : phase === 'preview_catalog_actions'
      ? summarizeWechatGearPreviewClassReports(reports, expectedSpecs, build)
      : summarizeWechatGearClassReports(reports, expectedSpecs, build)
  const expectedStatus = phase === 'preview_catalog_only_classes'
    ? 'CATALOG_ONLY_MATRIX_PASS'
    : phase === 'preview_catalog_slot_shards'
    ? 'SLOT_SHARD_MATRIX_PASS'
    : phase === 'preview_catalog_actions'
      ? 'PREVIEW_CATALOG_ACTIONS_PASS'
      : 'PASS'
  const artifact = {
    schemaVersion: 1,
    kind: phase === 'preview_catalog_only_classes'
      ? 'wechat-gear-preview-catalog-only-class-summary'
      : phase === 'preview_catalog_slot_shards'
      ? 'wechat-gear-preview-slot-shard-summary'
      : phase === 'preview_catalog_actions'
        ? 'wechat-gear-preview-catalog-actions-summary'
        : 'wechat-gear-goal-matrix-summary',
    status: summary.status,
    completedAt: new Date().toISOString(),
    scope: {
      requiredClasses: 13,
      requiredSpecs: 40,
      requiredSlotsPerSpec: 16,
      requiredActionsPerSpec: (
        phase === 'preview_catalog_slot_shards'
        || phase === 'preview_catalog_only_classes'
      )
        ? 0
        : requiredActions.length,
      diagnosticReportsAllowed: false,
      phase,
      formalSimcProven: phase === 'full',
    },
    runtime: {
      apiBaseUrl,
      build,
    },
    inputs: reportPaths,
    summary,
  }
  writeBoundedJsonAtomic(outputPath, artifact, 'WeChat gear Goal matrix summary')
  process.stdout.write(`${JSON.stringify({ status: artifact.status, outputPath, summary }, null, 2)}\n`)
  if (artifact.status !== expectedStatus) process.exitCode = 1
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`)
  process.exit(1)
})
