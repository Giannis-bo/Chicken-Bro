'use strict'

function finitePositive(value, name) {
  const number = Number(value)
  if (!Number.isFinite(number) || number <= 0) throw new Error(`WeChat ${name} must be a positive finite number`)
  return number
}

function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value))
}

function normalizeCapsuleBounds(menuButton, width, height, screenTop) {
  const left = Number(menuButton?.left)
  const top = Number(menuButton?.top) - screenTop
  const capsuleWidth = Number(menuButton?.width)
  const capsuleHeight = Number(menuButton?.height)
  const values = [left, top, capsuleWidth, capsuleHeight]
  if (!values.every(Number.isFinite) || capsuleWidth <= 0 || capsuleHeight <= 0) {
    throw new Error('WeChat menu button bounds must be finite and non-empty')
  }
  if (left < 0 || top < 0 || left + capsuleWidth > width + 2 || top + capsuleHeight > height + 2) {
    throw new Error('WeChat menu button bounds must fit the measured window')
  }
  return values
}

function normalizeSystemViewport(system, menuButton) {
  const width = finitePositive(system?.windowWidth, 'windowWidth')
  const height = finitePositive(system?.windowHeight, 'windowHeight')
  const dpr = finitePositive(system?.pixelRatio, 'pixelRatio')
  const safeTop = clamp(Number(system?.safeArea?.top ?? 0), 0, height)
  const safeAreaBottom = clamp(Number(system?.safeArea?.bottom ?? height), safeTop, height)
  const safeBottom = height - safeAreaBottom
  const screenTop = Math.max(0, Number(system?.screenTop ?? 0))
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
    capsuleBounds: normalizeCapsuleBounds(menuButton, width, height, screenTop),
  }
}

module.exports = { normalizeSystemViewport }
