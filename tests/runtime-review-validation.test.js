const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

const {
  expectedReviewOverallStatus,
  isCompletePassRecord,
  sharedEvidenceMatchesStatus,
} = require('../scripts/runtime-review-validation')

const contract = JSON.parse(fs.readFileSync('docs/design/current-ui/runtime-review-contract.json', 'utf8'))
const sha256 = 'a'.repeat(64)

function validReview() {
  return {
    route: 'news_home',
    path: '/pages/news/news',
    status: 'PASS',
    reviewRecord: {
      route: 'news_home',
      path: '/pages/news/news',
      viewport: { width: 390, height: 844, dpr: 3, safeTop: 47, safeBottom: 34, capsuleBounds: [296, 51, 87, 32] },
      runtimeArtifact: { path: `immutable/runtime/${sha256}/news-home.png`, width: 1170, height: 2532, bytes: 1, sha256, captureMethod: 'wechat' },
      targetArtifact: { path: 'artifacts/ui-visual-targets/current/news-home.png', width: 1170, height: 2532, sha256 },
      targetMapping: { scale: 1, translateX: 0, translateY: 0, systemChromeIncluded: true, contentOrigin: [0, 0] },
      regions: [{ id: 'page', targetBounds: [0, 0, 390, 844], runtimeBounds: [0, 0, 390, 844], delta: [0, 0, 0, 0], tolerance: 0, status: 'PASS' }],
      assetSemantics: [{ slotId: 'asset_slot.news-frame', expectedRole: 'frame', runtimeRole: 'frame', status: 'PASS' }],
      collisions: { statusBar: 0, capsule: 0, header: 0, tabBar: 0, textClip: 0, componentOverlap: 0 },
      interaction: { name: 'open metric', precondition: 'ready', action: 'tap', expected: 'list', actual: 'list', status: 'PASS' },
      passMetrics: { p0Count: 0, p1Count: 0, systemCollisionPx: 0, textClipCount: 0, componentOverlapPx: 0 },
      humanConfirmation: { reviewer: 'human-reviewer', confirmedAt: '2026-07-18T00:00:00Z', status: 'confirmed' },
      p0: [],
      p1: [],
      p2: [],
      status: 'PASS',
    },
  }
}

test('runtime review accepts only a complete pass record', () => {
  assert.equal(isCompletePassRecord(validReview(), contract), true)
})

test('runtime review rejects incomplete or contradictory pass evidence', () => {
  const mutations = [
    (review) => { review.reviewRecord.runtimeArtifact.sha256 = 'bad' },
    (review) => { review.reviewRecord.runtimeArtifact.path = 'mutable/runtime/news-home.png' },
    (review) => { review.reviewRecord.regions[0].status = 'FAIL' },
    (review) => { review.reviewRecord.assetSemantics[0].status = 'FAIL' },
    (review) => { review.reviewRecord.p0.push({ issue: 'collision' }) },
    (review) => { review.reviewRecord.collisions.header = 1 },
    (review) => { review.reviewRecord.passMetrics.textClipCount = 1 },
    (review) => { review.reviewRecord.interaction.status = 'FAIL' },
    (review) => { review.reviewRecord.humanConfirmation.status = 'pending' },
    (review) => { review.reviewRecord.humanConfirmation.confirmedAt = 'yesterday' },
    (review) => { delete review.reviewRecord.regions[0].runtimeBounds },
    (review) => { delete review.reviewRecord.targetMapping },
  ]
  for (const mutate of mutations) {
    const review = validReview()
    mutate(review)
    assert.equal(isCompletePassRecord(review, contract), false)
  }
})

test('runtime review status clears shared blockers only after every route passes', () => {
  const required = ['runtime', 'interaction', 'human']
  assert.equal(expectedReviewOverallStatus([{ status: 'UNVERIFIED' }, { status: 'PASS' }]), 'active_unverified')
  assert.equal(sharedEvidenceMatchesStatus('active_unverified', required, required), true)
  assert.equal(sharedEvidenceMatchesStatus('active_unverified', [], required), false)
  assert.equal(expectedReviewOverallStatus([{ status: 'PASS' }, { status: 'PASS' }]), 'complete')
  assert.equal(sharedEvidenceMatchesStatus('complete', [], required), true)
  assert.equal(sharedEvidenceMatchesStatus('complete', required, required), false)
})
