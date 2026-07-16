'use strict'

const selectorParser = require('postcss-selector-parser')

const structuralPseudos = new Set([':first-child', ':last-child', ':nth-child'])

function normalizeSelectorMarker(value) {
  const normalized = String(value)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')

  return normalized || 'empty'
}

function globalClassName(value) {
  return selectorParser.pseudo({
    value: ':global',
    nodes: [
      selectorParser.selector({
        nodes: [selectorParser.className({ value })],
      }),
    ],
  })
}

function replaceUnsupportedAttributes(selector) {
  selector.walkAttributes((attribute) => {
    if (attribute.attribute === 'class' && attribute.operator === '*=') {
      attribute.replaceWith(globalClassName(`wx-style-${normalizeSelectorMarker(attribute.value)}`))
      return
    }

    if (attribute.attribute.startsWith('data-') && attribute.operator === '=') {
      attribute.replaceWith(globalClassName(
        `wx-data-${normalizeSelectorMarker(attribute.attribute.slice(5))}-${normalizeSelectorMarker(attribute.value)}`,
      ))
    }
  })
}

function implicitStructuralPseudo(selector) {
  let match = null
  selector.walkPseudos((pseudo) => {
    if (match || !structuralPseudos.has(pseudo.value)) return
    const previous = pseudo.prev()
    if (previous?.type === 'combinator' && previous.value.trim() === '>') match = pseudo
  })
  return match
}

function expandImplicitChildren(selector, childTags) {
  let pending = [selector.clone()]
  const completed = []

  while (pending.length) {
    const current = pending.pop()
    const pseudo = implicitStructuralPseudo(current)
    if (!pseudo) {
      completed.push(current)
      continue
    }

    for (const tagName of childTags) {
      const clone = current.clone()
      const target = implicitStructuralPseudo(clone)
      target.parent.insertBefore(target, selectorParser.tag({ value: tagName }))
      pending.push(clone)
    }
  }

  return completed
}

module.exports = function weappCompatibleSelectors(options = {}) {
  const childTags = options.childTags ?? ['view', 'text', 'image', 'button']

  return {
    postcssPlugin: 'postcss-weapp-compatible-selectors',
    Rule(rule) {
      rule.selector = selectorParser((selectors) => {
        const expanded = []
        selectors.each((selector) => {
          replaceUnsupportedAttributes(selector)
          expanded.push(...expandImplicitChildren(selector, childTags))
        })
        selectors.removeAll()
        for (const selector of expanded) selectors.append(selector)
      }).processSync(rule.selector)
    },
  }
}

module.exports.postcss = true
