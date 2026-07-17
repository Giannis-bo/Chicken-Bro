const assert = require('node:assert/strict')
const test = require('node:test')

const fixtures = require('./fixtures/gear-attribute-calculator-cases-v1.json')
const armoryFixtures = require('./fixtures/gear-attribute-armory-v1.json')
const { calculateNonCombatAttributes } = require('../pages/builds/gear-attribute-engine')

for (const fixture of fixtures.cases) {
  test(`attribute fixture ${fixture.id}`, () => {
    assert.deepEqual(
      calculateNonCombatAttributes(
        fixture.rule,
        fixture.characterContext,
        fixture.staticAttributes,
        fixture.stableEffects,
      ),
      fixture.expected,
    )
  })
}

test('missing race and invalid conversion return no numeric final panel', () => {
  const fixture = fixtures.cases[0]
  const missingRace = calculateNonCombatAttributes(
    fixture.rule,
    { raceKey: 'orc' },
    fixture.staticAttributes,
    fixture.stableEffects,
  )
  const invalidRule = structuredClone(fixture.rule)
  invalidRule.secondaryRules[0].ratingPerPercent = 0
  const invalidConversion = calculateNonCombatAttributes(
    invalidRule,
    fixture.characterContext,
    fixture.staticAttributes,
    fixture.stableEffects,
  )

  assert.equal(missingRace.status, 'rule_unavailable')
  assert.equal(missingRace.primary, null)
  assert.equal(invalidConversion.problems[0].code, 'INVALID_RATING_CONVERSION')
  assert.deepEqual(invalidConversion.secondary, [])
})

test('unrecognized stable effects remain conditional and never change totals', () => {
  const fixture = fixtures.cases[0]
  const result = calculateNonCombatAttributes(
    fixture.rule,
    fixture.characterContext,
    fixture.staticAttributes,
    [{ effectId: 'fixture:not-allowed' }],
  )

  assert.equal(result.primary.rawValue, 1500)
  assert.deepEqual(result.conditionals, [
    { effectId: 'fixture:not-allowed', included: false, reason: 'UNSUPPORTED_STABLE_EFFECT' },
  ])
})

test('piecewise curve matches official Frost avoidance sample', () => {
  const fixture = fixtures.cases[0]
  const rule = structuredClone(fixture.rule)
  rule.secondaryRules = [{
    inputKey: 'avoidance_rating',
    outputKey: 'avoidance',
    label: '闪避',
    basePercent: 0,
    ratingTransform: {
      kind: 'piecewise_linear',
      ratingPerPercent: 36.80052531,
      points: [
        { input: 0, output: 0 },
        { input: 0.5, output: 0.5 },
        { input: 10, output: 10 },
        { input: 15, output: 14 },
        { input: 20, output: 17 },
        { input: 25, output: 19 },
        { input: 100, output: 49 }
      ],
      outOfRange: 'clamp'
    },
    precision: 6,
    sourceRefs: ['simc:dbc:curve:21025'],
    displayUnit: 'percent'
  }]

  const result = calculateNonCombatAttributes(
    rule,
    fixture.characterContext,
    { avoidance_rating: 470 },
    [],
  )

  assert.equal(result.status, 'calculated')
  assert.deepEqual(result.secondary, [{
    key: 'avoidance',
    label: '闪避',
    rawValue: 470,
    value: '470',
    convertedValue: '12.217245%',
    displayUnit: 'percent'
  }])
})

test('candidate Armory records cannot become a calculated rule input', () => {
  const candidate = armoryFixtures.samples.find((sample) => sample.status === 'candidate')
  assert.ok(candidate)
  const fixture = fixtures.cases[0]
  const candidateRule = {
    ...fixture.rule,
    status: candidate.status,
    goldenSampleIds: [candidate.id]
  }

  const result = calculateNonCombatAttributes(
    candidateRule,
    fixture.characterContext,
    fixture.staticAttributes,
    fixture.stableEffects,
  )

  assert.equal(result.status, 'rule_unavailable')
  assert.equal(result.primary, null)
})

test('input signature changes when a rating transform changes without a revision bump', () => {
  const fixture = fixtures.cases[0]
  const baseline = calculateNonCombatAttributes(
    fixture.rule,
    fixture.characterContext,
    fixture.staticAttributes,
    fixture.stableEffects,
  )
  const changedRule = structuredClone(fixture.rule)
  changedRule.secondaryRules[0].ratingPerPercent = 36
  const changed = calculateNonCombatAttributes(
    changedRule,
    fixture.characterContext,
    fixture.staticAttributes,
    fixture.stableEffects,
  )

  assert.notEqual(changed.inputSignature, baseline.inputSignature)
})
