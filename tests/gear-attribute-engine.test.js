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

test('pre-conversion stable modifiers retain their target key contract', () => {
  const fixture = fixtures.cases[0]
  const rule = structuredClone(fixture.rule)
  rule.stableModifiers = [
    { effectId: 'fixture:intellect-multiply', targetKey: 'intellect', operation: 'multiply', value: 2 }
  ]

  const result = calculateNonCombatAttributes(
    rule,
    fixture.characterContext,
    fixture.staticAttributes,
    [{ effectId: 'fixture:intellect-multiply' }],
  )

  assert.equal(result.status, 'calculated')
  assert.equal(result.primary.rawValue, 3000)
})

test('stable raw rating rounding happens before percent conversion', () => {
  const fixture = fixtures.cases[0]
  const rule = structuredClone(fixture.rule)
  rule.stableModifiers = [
    { effectId: 'fixture:haste-scale', targetKey: 'haste_rating', operation: 'multiply', value: 1.05 },
    { effectId: 'fixture:haste-round', targetKey: 'haste_rating', operation: 'round_nearest', value: 0 }
  ]
  rule.secondaryRules = [{
    inputKey: 'haste_rating',
    outputKey: 'haste',
    label: '急速',
    basePercent: 0,
    ratingPerPercent: 44,
    precision: 6,
    sourceRefs: ['fixture:stable-rating-rounding'],
    displayUnit: 'percent'
  }]

  const result = calculateNonCombatAttributes(
    rule,
    fixture.characterContext,
    { haste_rating: 637 },
    [{ effectId: 'fixture:haste-scale' }, { effectId: 'fixture:haste-round' }],
  )

  assert.equal(result.status, 'calculated')
  assert.deepEqual(result.secondary, [{
    key: 'haste',
    label: '急速',
    rawValue: 669,
    value: '669',
    convertedValue: '15.204545%',
    displayUnit: 'percent'
  }])
})

test('post-conversion modifier order is declared by rule, not effect input order', () => {
  const fixture = fixtures.cases[0]
  const rule = structuredClone(fixture.rule)
  rule.secondaryRules = [{
    inputKey: 'haste_rating',
    outputKey: 'haste',
    label: '急速',
    basePercent: 10,
    ratingPerPercent: 50,
    postConversionModifiers: [
      { effectId: 'fixture:haste-add', operation: 'add', value: 2 },
      { effectId: 'fixture:haste-multiply', operation: 'multiply', value: 1.05 }
    ],
    precision: 1,
    sourceRefs: ['fixture:post-conversion-order'],
    displayUnit: 'percent'
  }]
  const effects = [{ effectId: 'fixture:haste-multiply' }, { effectId: 'fixture:haste-add' }]

  const declaredOrder = calculateNonCombatAttributes(
    rule, fixture.characterContext, { haste_rating: 100 }, effects,
  )
  rule.secondaryRules[0].postConversionModifiers.reverse()
  const reversedOrder = calculateNonCombatAttributes(
    rule, fixture.characterContext, { haste_rating: 100 }, effects,
  )

  assert.equal(declaredOrder.secondary[0].convertedValue, '14.7%')
  assert.equal(reversedOrder.secondary[0].convertedValue, '14.6%')
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
