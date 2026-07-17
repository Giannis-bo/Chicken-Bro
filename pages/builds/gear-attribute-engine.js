const ATTRIBUTE_CALCULATION_CONTRACT_REVISION = 'gear-attribute-calculation-v1'
const MAX_IDENTIFIER_LENGTH = 256
const MAX_RATING_TRANSFORM_POINTS = 128

const STATIC_ATTRIBUTE_ALIASES = {
  int: 'intellect',
  intellect: 'intellect',
  stam: 'stamina',
  stamina: 'stamina',
  crit: 'crit_rating',
  critical_strike: 'crit_rating',
  critical_strike_rating: 'crit_rating',
  crit_rating: 'crit_rating',
  haste: 'haste_rating',
  haste_rating: 'haste_rating',
  mastery: 'mastery_rating',
  mastery_rating: 'mastery_rating',
  versatility: 'versatility_rating',
  versatility_rating: 'versatility_rating',
  avoidance: 'avoidance_rating',
  avoidance_rating: 'avoidance_rating',
  leech: 'leech_rating',
  leech_rating: 'leech_rating',
  speed: 'speed_rating',
  speed_rating: 'speed_rating'
}

function issue(code, path, message) {
  return { kind: 'ATTRIBUTE_RULE_UNAVAILABLE', code, path, message }
}

function boundedKey(value) {
  if (typeof value !== 'string') return null
  const normalized = value.trim()
  if (!normalized || normalized.length > MAX_IDENTIFIER_LENGTH || normalized !== normalized.toLowerCase()) return null
  return normalized
}

function finiteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function cleanNumber(value) {
  return Number.isInteger(value) ? Number(value) : value
}

function groupInteger(value) {
  const sign = value < 0 ? '-' : ''
  const digits = String(Math.abs(value))
  return `${sign}${digits.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}`
}

function formatAttributeValue(value) {
  const numeric = Number(value)
  if (Number.isInteger(numeric)) return groupInteger(Math.round(numeric))
  const sign = numeric < 0 ? '-' : ''
  const rendered = Math.abs(numeric).toFixed(1)
  const [integer, fraction] = rendered.split('.')
  return `${sign}${groupInteger(Number(integer))}${fraction === '0' ? '' : `.${fraction}`}`
}

function formatConvertedValue(value, precision, displayUnit) {
  const rendered = Number(value).toFixed(precision)
  return displayUnit === 'percent' ? `${rendered}%` : rendered
}

function unavailable(attributeRuleRevision, code, path, message) {
  return {
    contractRevision: ATTRIBUTE_CALCULATION_CONTRACT_REVISION,
    status: 'rule_unavailable',
    attributeRuleRevision,
    primary: null,
    stamina: null,
    resources: {},
    secondary: [],
    conditionals: [],
    problems: [issue(code, path, message)],
    inputSignature: ''
  }
}

function normalizeStaticAttributes(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return { issue: issue('INVALID_STATIC_ATTRIBUTES', 'staticAttributes', 'staticAttributes must be an object') }
  }
  const normalized = {}
  for (const key of Object.keys(raw)) {
    const normalizedKey = boundedKey(key)
    const value = finiteNumber(raw[key])
    if (!normalizedKey || value === null) {
      return { issue: issue('INVALID_STATIC_ATTRIBUTE', `staticAttributes.${key}`, 'static attributes require lower-case keys and finite numeric values') }
    }
    const canonicalKey = STATIC_ATTRIBUTE_ALIASES[normalizedKey] || normalizedKey
    normalized[canonicalKey] = (normalized[canonicalKey] || 0) + value
  }
  return { value: normalized }
}

function normalizeStableEffects(raw) {
  if (!Array.isArray(raw)) {
    return { issue: issue('INVALID_STABLE_EFFECTS', 'stableEffects', 'stableEffects must be a list') }
  }
  const effectIds = new Set()
  for (let index = 0; index < raw.length; index += 1) {
    const effect = raw[index]
    if (!effect || typeof effect !== 'object' || Array.isArray(effect)) {
      return { issue: issue('INVALID_STABLE_EFFECT', `stableEffects[${index}]`, 'stable effects must be objects') }
    }
    const effectId = boundedKey(effect.effectId)
    if (!effectId) {
      return { issue: issue('INVALID_STABLE_EFFECT', `stableEffects[${index}].effectId`, 'stable effects require a bounded lower-case effectId') }
    }
    effectIds.add(effectId)
  }
  return { value: Array.from(effectIds).sort() }
}

function ruleRevision(rule) {
  return rule && typeof rule === 'object' && typeof rule.attributeRuleRevision === 'string'
    ? rule.attributeRuleRevision
    : ''
}

function validateRuleAndCharacter(rule, characterContext) {
  const revision = ruleRevision(rule)
  if (!rule || typeof rule !== 'object' || Array.isArray(rule)) {
    return { revision, issue: issue('ATTRIBUTE_RULE_UNAVAILABLE', 'rule', 'attribute rule is unavailable') }
  }
  const requiredKeys = [
    'attributeRuleRevision', 'contextKey', 'raceKey', 'status', 'primaryKey',
    'baseAttributes', 'stableModifiers', 'resources', 'secondaryRules'
  ]
  const missingKey = requiredKeys.find((key) => !(key in rule))
  if (missingKey) return { revision, issue: issue('INVALID_ATTRIBUTE_RULE', `rule.${missingKey}`, 'attribute rule is incomplete') }
  if (!boundedKey(rule.attributeRuleRevision)) {
    return { revision, issue: issue('INVALID_ATTRIBUTE_RULE', 'rule.attributeRuleRevision', 'attribute rule revision is invalid') }
  }
  if (!['verified', 'fixture_only'].includes(rule.status)) {
    return { revision, issue: issue('INVALID_ATTRIBUTE_RULE', 'rule.status', 'attribute rule is not usable') }
  }
  const raceKey = boundedKey(rule.raceKey)
  const primaryKey = boundedKey(rule.primaryKey)
  if (!raceKey || !primaryKey) {
    return { revision, issue: issue('INVALID_ATTRIBUTE_RULE', 'rule', 'rule identifiers must be bounded lower-case values') }
  }
  if (!characterContext || typeof characterContext !== 'object' || Array.isArray(characterContext) || boundedKey(characterContext.raceKey) !== raceKey) {
    return { revision, issue: issue('ATTRIBUTE_RULE_UNAVAILABLE', 'characterContext.raceKey', 'no attribute rule is available for this race') }
  }
  if (!rule.baseAttributes || typeof rule.baseAttributes !== 'object' || Array.isArray(rule.baseAttributes) || !Array.isArray(rule.stableModifiers)) {
    return { revision, issue: issue('INVALID_ATTRIBUTE_RULE', 'rule', 'rule base attributes or modifiers are invalid') }
  }
  if (!rule.resources || typeof rule.resources !== 'object' || Array.isArray(rule.resources) || !Array.isArray(rule.secondaryRules)) {
    return { revision, issue: issue('INVALID_ATTRIBUTE_RULE', 'rule', 'rule resources or secondary rules are invalid') }
  }
  return { value: rule, revision }
}

function applyStableModifiers(attributes, modifiers, effectIds) {
  const activeEffects = new Set(effectIds)
  const allowedEffects = new Set()
  const baseAttributes = { ...attributes }
  for (let index = 0; index < modifiers.length; index += 1) {
    const modifier = modifiers[index]
    const path = `rule.stableModifiers[${index}]`
    if (!modifier || typeof modifier !== 'object' || Array.isArray(modifier)) {
      return { issue: issue('INVALID_STABLE_MODIFIER', path, 'stable modifiers must be objects') }
    }
    const effectId = boundedKey(modifier.effectId)
    const targetKey = boundedKey(modifier.targetKey)
    const value = finiteNumber(modifier.value)
    if (!effectId || !targetKey || !['add', 'multiply', 'add_percent_of_base', 'round_nearest'].includes(modifier.operation) || value === null || (modifier.operation === 'round_nearest' && value !== 0)) {
      return { issue: issue('INVALID_STABLE_MODIFIER', path, 'stable modifier requires effectId, targetKey, operation and finite value') }
    }
    allowedEffects.add(effectId)
    if (!activeEffects.has(effectId)) continue
    const current = attributes[targetKey] || 0
    if (modifier.operation === 'add') attributes[targetKey] = current + value
    else if (modifier.operation === 'multiply') attributes[targetKey] = current * value
    else if (modifier.operation === 'add_percent_of_base') attributes[targetKey] = current + (baseAttributes[targetKey] || 0) * value
    else attributes[targetKey] = Math.floor(current + 0.5)
  }
  return {
    value: {
      attributes,
      allowedEffects
    }
  }
}

function resourceRows(resources, attributes, secondaryValues) {
  const rows = {}
  for (const resourceKey of Object.keys(resources)) {
    const normalizedKey = boundedKey(resourceKey)
    const definition = resources[resourceKey]
    const path = `rule.resources.${resourceKey}`
    if (!normalizedKey || !definition || typeof definition !== 'object' || Array.isArray(definition)) {
      return { issue: issue('INVALID_RESOURCE_RULE', path, 'resource definitions must be keyed objects') }
    }
    const base = finiteNumber(definition.base)
    const perStamina = finiteNumber(definition.perStamina === undefined ? 0 : definition.perStamina)
    const perIntellect = finiteNumber(definition.perIntellect === undefined ? 0 : definition.perIntellect)
    if (base === null || perStamina === null || perIntellect === null || !['floor', 'ceil', 'round'].includes(definition.round)) {
      return { issue: issue('INVALID_RESOURCE_RULE', path, 'resource definitions require finite base/per-attribute values and a round mode') }
    }
    let rawValue = base + (attributes.stamina || 0) * perStamina + (attributes.intellect || 0) * perIntellect
    if (definition.percentFromSecondary !== undefined) {
      const sourceKey = boundedKey(definition.percentFromSecondary)
      const sourcePercent = sourceKey ? secondaryValues[sourceKey] : undefined
      if (sourcePercent === undefined) {
        return { issue: issue('INVALID_RESOURCE_RULE', `${path}.percentFromSecondary`, 'percentFromSecondary must name a calculated secondary output') }
      }
      rawValue *= 1 + sourcePercent / 100
    }
    if (definition.round === 'floor') rawValue = Math.floor(rawValue)
    if (definition.round === 'ceil') rawValue = Math.ceil(rawValue)
    if (definition.round === 'round') rawValue = Math.round(rawValue)
    rows[normalizedKey] = { key: normalizedKey, rawValue: cleanNumber(rawValue), value: formatAttributeValue(rawValue) }
  }
  return { value: rows }
}

function piecewiseRatingValue(rawValue, transform, path) {
  const requiredKeys = ['kind', 'ratingPerPercent', 'points', 'outOfRange']
  if (!transform || typeof transform !== 'object' || Array.isArray(transform) || Object.keys(transform).length !== requiredKeys.length || requiredKeys.some((key) => !(key in transform))) {
    return { issue: issue('INVALID_RATING_TRANSFORM', path, 'ratingTransform must be an exact piecewise-linear transform') }
  }
  if (transform.kind !== 'piecewise_linear' || transform.outOfRange !== 'clamp') {
    return { issue: issue('INVALID_RATING_TRANSFORM', path, 'ratingTransform must declare piecewise_linear clamp semantics') }
  }
  const ratingPerPercent = finiteNumber(transform.ratingPerPercent)
  if (ratingPerPercent === null || ratingPerPercent <= 0) {
    return { issue: issue('INVALID_RATING_CONVERSION', `${path}.ratingPerPercent`, 'ratingPerPercent must be a finite number greater than zero') }
  }
  if (!Array.isArray(transform.points) || transform.points.length < 2 || transform.points.length > MAX_RATING_TRANSFORM_POINTS) {
    return { issue: issue('INVALID_RATING_TRANSFORM', `${path}.points`, 'ratingTransform points must contain two to 128 points') }
  }

  const points = []
  let previousInput = null
  let previousOutput = null
  for (let index = 0; index < transform.points.length; index += 1) {
    const point = transform.points[index]
    const pointPath = `${path}.points[${index}]`
    if (!point || typeof point !== 'object' || Array.isArray(point) || Object.keys(point).length !== 2 || !('input' in point) || !('output' in point)) {
      return { issue: issue('INVALID_RATING_TRANSFORM', pointPath, 'curve points require only finite input and output values') }
    }
    const input = finiteNumber(point.input)
    const output = finiteNumber(point.output)
    if (input === null || output === null || input < 0 || output < 0) {
      return { issue: issue('INVALID_RATING_TRANSFORM', pointPath, 'curve point values must be finite and non-negative') }
    }
    if (previousInput !== null && input <= previousInput) {
      return { issue: issue('INVALID_RATING_TRANSFORM', `${pointPath}.input`, 'curve point inputs must be strictly increasing') }
    }
    if (previousOutput !== null && output < previousOutput) {
      return { issue: issue('INVALID_RATING_TRANSFORM', `${pointPath}.output`, 'curve point outputs must be non-decreasing') }
    }
    points.push({ input, output })
    previousInput = input
    previousOutput = output
  }

  const curveInput = rawValue / ratingPerPercent
  if (curveInput <= points[0].input) return { value: points[0].output }
  if (curveInput >= points[points.length - 1].input) return { value: points[points.length - 1].output }
  for (let index = 0; index < points.length - 1; index += 1) {
    const lower = points[index]
    const upper = points[index + 1]
    if (curveInput <= upper.input) {
      const ratio = (curveInput - lower.input) / (upper.input - lower.input)
      return { value: lower.output + (upper.output - lower.output) * ratio }
    }
  }
  return { issue: issue('INVALID_RATING_TRANSFORM', path, 'curve interpolation did not resolve') }
}

function applyPostConversionModifiers(convertedValue, modifiers, effectIds, allowedEffects, path) {
  if (modifiers === undefined) return { value: convertedValue }
  if (!Array.isArray(modifiers)) {
    return { issue: issue('INVALID_POST_CONVERSION_MODIFIERS', path, 'post-conversion modifiers must be an ordered list') }
  }
  const activeEffects = new Set(effectIds)
  for (let index = 0; index < modifiers.length; index += 1) {
    const modifier = modifiers[index]
    const modifierPath = `${path}[${index}]`
    if (!modifier || typeof modifier !== 'object' || Array.isArray(modifier) || Object.keys(modifier).length !== 3 || !('effectId' in modifier) || !('operation' in modifier) || !('value' in modifier)) {
      return { issue: issue('INVALID_POST_CONVERSION_MODIFIER', modifierPath, 'post-conversion modifiers must be objects') }
    }
    const effectId = boundedKey(modifier.effectId)
    const value = finiteNumber(modifier.value)
    if (!effectId || !['add', 'multiply', 'multiply_total'].includes(modifier.operation) || value === null) {
      return { issue: issue('INVALID_POST_CONVERSION_MODIFIER', modifierPath, 'post-conversion modifiers require effectId, operation and finite value') }
    }
    allowedEffects.add(effectId)
    if (!activeEffects.has(effectId)) continue
    if (modifier.operation === 'add') convertedValue += value
    else if (modifier.operation === 'multiply') convertedValue *= value
    else convertedValue = ((1 + convertedValue / 100) * value - 1) * 100
  }
  return { value: convertedValue }
}

function secondaryRows(secondaryRules, attributes, effectIds, allowedEffects) {
  const rows = []
  const numericValues = {}
  const outputKeys = new Set()
  for (let index = 0; index < secondaryRules.length; index += 1) {
    const definition = secondaryRules[index]
    const path = `rule.secondaryRules[${index}]`
    if (!definition || typeof definition !== 'object' || Array.isArray(definition)) {
      return { issue: issue('INVALID_SECONDARY_RULE', path, 'secondary rules must be objects') }
    }
    const inputKey = boundedKey(definition.inputKey)
    const outputKey = boundedKey(definition.outputKey)
    const basePercent = finiteNumber(definition.basePercent)
    const precision = definition.precision
    const displayUnit = definition.displayUnit
    if (!inputKey || !outputKey || typeof definition.label !== 'string' || !definition.label.trim()) {
      return { issue: issue('INVALID_SECONDARY_RULE', path, 'secondary rules require input, output and label') }
    }
    if (outputKeys.has(outputKey)) return { issue: issue('DUPLICATE_OUTPUT_KEY', `${path}.outputKey`, 'secondary output keys must be unique') }
    outputKeys.add(outputKey)
    if (basePercent === null) {
      return { issue: issue('INVALID_RATING_CONVERSION', `${path}.basePercent`, 'basePercent must be a finite number') }
    }
    if (!Number.isInteger(precision) || precision < 0 || precision > 6) {
      return { issue: issue('INVALID_PRECISION', `${path}.precision`, 'precision must be an integer from 0 to 6') }
    }
    if (!['percent', 'effect'].includes(displayUnit)) {
      return { issue: issue('INVALID_DISPLAY_UNIT', `${path}.displayUnit`, 'displayUnit must be percent or effect') }
    }
    const canonicalInputKey = STATIC_ATTRIBUTE_ALIASES[inputKey] || inputKey
    const rawValue = attributes[canonicalInputKey] || 0
    let convertedValue
    if ('ratingTransform' in definition) {
      if ('ratingPerPercent' in definition) {
        return { issue: issue('INVALID_RATING_TRANSFORM', path, 'secondary rules must use exactly one rating conversion model') }
      }
      const transformed = piecewiseRatingValue(rawValue, definition.ratingTransform, `${path}.ratingTransform`)
      if (transformed.issue) return transformed
      convertedValue = basePercent + transformed.value
    } else {
      const ratingPerPercent = finiteNumber(definition.ratingPerPercent)
      if (ratingPerPercent === null || ratingPerPercent <= 0) {
        return { issue: issue('INVALID_RATING_CONVERSION', `${path}.ratingPerPercent`, 'ratingPerPercent must be a finite number greater than zero') }
      }
      convertedValue = basePercent + rawValue / ratingPerPercent
    }
    const postConversion = applyPostConversionModifiers(
      convertedValue,
      definition.postConversionModifiers,
      effectIds,
      allowedEffects,
      `${path}.postConversionModifiers`,
    )
    if (postConversion.issue) return postConversion
    convertedValue = postConversion.value
    numericValues[outputKey] = convertedValue
    rows.push({
      key: outputKey,
      label: definition.label,
      rawValue: cleanNumber(rawValue),
      value: formatAttributeValue(rawValue),
      convertedValue: formatConvertedValue(convertedValue, precision, displayUnit),
      displayUnit
    })
  }
  return { value: rows, numericValues }
}

function canonicalJson(value) {
  if (value === null) return 'null'
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`
  if (typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}`
  }
  return JSON.stringify(value)
}

function utf8Bytes(value) {
  if (typeof TextEncoder !== 'undefined') return Array.from(new TextEncoder().encode(value))
  const encoded = unescape(encodeURIComponent(value))
  return Array.from(encoded, (character) => character.charCodeAt(0))
}

function rightRotate(value, amount) {
  return (value >>> amount) | (value << (32 - amount))
}

function sha256Hex(value) {
  const bytes = utf8Bytes(value)
  const bitLength = bytes.length * 8
  bytes.push(0x80)
  while ((bytes.length % 64) !== 56) bytes.push(0)
  const high = Math.floor(bitLength / 0x100000000)
  const low = bitLength >>> 0
  for (const part of [high, low]) {
    bytes.push((part >>> 24) & 0xff, (part >>> 16) & 0xff, (part >>> 8) & 0xff, part & 0xff)
  }

  const hash = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
  ]
  const constants = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
  ]

  for (let offset = 0; offset < bytes.length; offset += 64) {
    const words = new Array(64)
    for (let index = 0; index < 16; index += 1) {
      const base = offset + index * 4
      words[index] = ((bytes[base] << 24) | (bytes[base + 1] << 16) | (bytes[base + 2] << 8) | bytes[base + 3]) >>> 0
    }
    for (let index = 16; index < 64; index += 1) {
      const s0 = rightRotate(words[index - 15], 7) ^ rightRotate(words[index - 15], 18) ^ (words[index - 15] >>> 3)
      const s1 = rightRotate(words[index - 2], 17) ^ rightRotate(words[index - 2], 19) ^ (words[index - 2] >>> 10)
      words[index] = (words[index - 16] + s0 + words[index - 7] + s1) >>> 0
    }
    let [a, b, c, d, e, f, g, h] = hash
    for (let index = 0; index < 64; index += 1) {
      const sum1 = rightRotate(e, 6) ^ rightRotate(e, 11) ^ rightRotate(e, 25)
      const choice = (e & f) ^ ((~e) & g)
      const temp1 = (h + sum1 + choice + constants[index] + words[index]) >>> 0
      const sum0 = rightRotate(a, 2) ^ rightRotate(a, 13) ^ rightRotate(a, 22)
      const majority = (a & b) ^ (a & c) ^ (b & c)
      const temp2 = (sum0 + majority) >>> 0
      h = g
      g = f
      f = e
      e = (d + temp1) >>> 0
      d = c
      c = b
      b = a
      a = (temp1 + temp2) >>> 0
    }
    hash[0] = (hash[0] + a) >>> 0
    hash[1] = (hash[1] + b) >>> 0
    hash[2] = (hash[2] + c) >>> 0
    hash[3] = (hash[3] + d) >>> 0
    hash[4] = (hash[4] + e) >>> 0
    hash[5] = (hash[5] + f) >>> 0
    hash[6] = (hash[6] + g) >>> 0
    hash[7] = (hash[7] + h) >>> 0
  }
  return hash.map((part) => part.toString(16).padStart(8, '0')).join('')
}

function inputSignature(rule, raceKey, staticAttributes, effectIds) {
  const payload = {
    attributeRuleRevision: rule.attributeRuleRevision,
    contextKey: rule.contextKey,
    raceKey,
    calculationRule: {
      primaryKey: rule.primaryKey,
      baseAttributes: rule.baseAttributes,
      stableModifiers: rule.stableModifiers,
      resources: rule.resources,
      secondaryRules: rule.secondaryRules
    },
    staticAttributes: Object.keys(staticAttributes).sort().reduce((output, key) => {
      output[key] = cleanNumber(staticAttributes[key])
      return output
    }, {}),
    stableEffects: effectIds
  }
  return `sha256:${sha256Hex(canonicalJson(payload))}`
}

function calculateNonCombatAttributes(rule, characterContext, staticAttributes, stableEffects) {
  const validated = validateRuleAndCharacter(rule, characterContext)
  if (validated.issue) return unavailable(validated.revision, validated.issue.code, validated.issue.path, validated.issue.message)
  const normalizedStatic = normalizeStaticAttributes(staticAttributes)
  if (normalizedStatic.issue) return unavailable(validated.revision, normalizedStatic.issue.code, normalizedStatic.issue.path, normalizedStatic.issue.message)
  const normalizedEffects = normalizeStableEffects(stableEffects)
  if (normalizedEffects.issue) return unavailable(validated.revision, normalizedEffects.issue.code, normalizedEffects.issue.path, normalizedEffects.issue.message)

  const attributes = {}
  for (const key of Object.keys(rule.baseAttributes)) {
    const normalizedKey = boundedKey(key)
    const value = finiteNumber(rule.baseAttributes[key])
    if (!normalizedKey || value === null) {
      return unavailable(validated.revision, 'INVALID_BASE_ATTRIBUTE', `rule.baseAttributes.${key}`, 'base attributes require lower-case keys and finite numeric values')
    }
    const canonicalKey = STATIC_ATTRIBUTE_ALIASES[normalizedKey] || normalizedKey
    attributes[canonicalKey] = (attributes[canonicalKey] || 0) + value
  }
  for (const key of Object.keys(normalizedStatic.value)) {
    attributes[key] = (attributes[key] || 0) + normalizedStatic.value[key]
  }

  const appliedModifiers = applyStableModifiers(attributes, rule.stableModifiers, normalizedEffects.value)
  if (appliedModifiers.issue) return unavailable(validated.revision, appliedModifiers.issue.code, appliedModifiers.issue.path, appliedModifiers.issue.message)
  const secondary = secondaryRows(
    rule.secondaryRules,
    appliedModifiers.value.attributes,
    normalizedEffects.value,
    appliedModifiers.value.allowedEffects,
  )
  if (secondary.issue) return unavailable(validated.revision, secondary.issue.code, secondary.issue.path, secondary.issue.message)
  const resources = resourceRows(
    rule.resources,
    appliedModifiers.value.attributes,
    secondary.numericValues,
  )
  if (resources.issue) return unavailable(validated.revision, resources.issue.code, resources.issue.path, resources.issue.message)

  const primaryKey = STATIC_ATTRIBUTE_ALIASES[rule.primaryKey] || rule.primaryKey
  const primaryValue = appliedModifiers.value.attributes[primaryKey] || 0
  const staminaValue = appliedModifiers.value.attributes.stamina || 0
  return {
    contractRevision: ATTRIBUTE_CALCULATION_CONTRACT_REVISION,
    status: 'calculated',
    attributeRuleRevision: validated.revision,
    primary: { key: primaryKey, rawValue: cleanNumber(primaryValue), value: formatAttributeValue(primaryValue) },
    stamina: { key: 'stamina', rawValue: cleanNumber(staminaValue), value: formatAttributeValue(staminaValue) },
    resources: resources.value,
    secondary: secondary.value,
    conditionals: normalizedEffects.value
      .filter((effectId) => !appliedModifiers.value.allowedEffects.has(effectId))
      .map((effectId) => ({ effectId, included: false, reason: 'UNSUPPORTED_STABLE_EFFECT' })),
    problems: [],
    inputSignature: inputSignature(rule, rule.raceKey, normalizedStatic.value, normalizedEffects.value)
  }
}

module.exports = {
  calculateNonCombatAttributes,
  formatAttributeValue
}
