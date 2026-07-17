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
