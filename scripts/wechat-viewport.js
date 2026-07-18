'use strict'

function finitePositive(value, name) {
  const number = Number(value)
  if (!Number.isFinite(number) || number <= 0) throw new Error(`WeChat ${name} must be a positive finite number`)
  return number
}

function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value))
}

function normalizeSystemViewport(system) {
  const width = finitePositive(system?.windowWidth, 'windowWidth')
  const height = finitePositive(system?.windowHeight, 'windowHeight')
  const dpr = finitePositive(system?.pixelRatio, 'pixelRatio')
  const safeTop = clamp(Number(system?.safeArea?.top ?? 0), 0, height)
  const safeAreaBottom = clamp(Number(system?.safeArea?.bottom ?? height), safeTop, height)
  const safeBottom = height - safeAreaBottom
  return {
    width,
    height,
    dpr,
    safeTop,
    safeBottom,
    safeAreaBottom,
    // Retained for the current geometry detail schema; both names now have
    // the same window-coordinate meaning.
    safeBottomInset: safeBottom,
  }
}

module.exports = { normalizeSystemViewport }
