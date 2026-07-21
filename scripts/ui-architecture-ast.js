'use strict'

const babelParser = require('@babel/parser')
const traverse = require('@babel/traverse').default

function pageFrameLiteralVariants(source) {
  const ast = babelParser.parse(source, {
    sourceType: 'module',
    plugins: ['jsx', 'typescript'],
  })
  const variants = []

  traverse(ast, {
    JSXOpeningElement(path) {
      const openingElement = path.node
      if (openingElement.name.type !== 'JSXIdentifier' || openingElement.name.name !== 'PageFrame') return

      const variantAttribute = openingElement.attributes.find((attribute) => (
        attribute.type === 'JSXAttribute'
          && attribute.name.type === 'JSXIdentifier'
          && attribute.name.name === 'variant'
      ))
      if (!variantAttribute?.value) {
        variants.push(null)
        return
      }

      if (variantAttribute.value.type === 'StringLiteral') {
        variants.push(variantAttribute.value.value)
        return
      }

      const expression = variantAttribute.value.type === 'JSXExpressionContainer'
        ? variantAttribute.value.expression
        : null
      variants.push(expression?.type === 'StringLiteral' ? expression.value : null)
    },
  })

  return variants
}

function publishedRegionRecords(source) {
  const ast = babelParser.parse(source, {
    sourceType: 'module',
    plugins: ['jsx', 'typescript'],
  })
  const stringArrays = new Map()
  const regions = []

  traverse(ast, {
    VariableDeclarator(variablePath) {
      if (variablePath.node.id.type !== 'Identifier') return
      let initializer = variablePath.node.init
      while (initializer?.type === 'TSAsExpression' || initializer?.type === 'TSSatisfiesExpression') initializer = initializer.expression
      if (initializer?.type !== 'ArrayExpression') return
      const values = initializer.elements.map((element) => element?.type === 'StringLiteral' ? element.value : null)
      if (values.length > 0 && values.every(Boolean)) stringArrays.set(variablePath.node.id.name, values)
    },
    JSXOpeningElement(elementPath) {
      if (elementPath.node.name.type !== 'JSXIdentifier') return
      const componentName = elementPath.node.name.name
      const attributeName = componentName === 'RouteRegion'
        ? 'data-region'
        : componentName === 'PageFrame'
          ? 'region'
          : null
      if (!attributeName) return
      const attribute = elementPath.node.attributes.find((candidate) => (
        candidate.type === 'JSXAttribute'
        && candidate.name.type === 'JSXIdentifier'
        && candidate.name.name === attributeName
      ))
      if (attribute?.value?.type === 'StringLiteral') {
        regions.push({ owner: componentName, value: attribute.value.value })
        return
      }
      if (componentName !== 'RouteRegion' || attribute?.value?.type !== 'JSXExpressionContainer') return
      const expressionSource = source.slice(attribute.value.expression.start, attribute.value.expression.end)
      for (const [name, values] of stringArrays) {
        if (new RegExp(`\\b${name}\\b`, 'u').test(expressionSource)) {
          regions.push(...values.map((value) => ({ owner: componentName, value })))
        }
      }
    },
  })
  return regions
}

function publishedSemanticRegionIds(source) {
  return publishedRegionRecords(source).map((region) => region.value)
}

function publishedPageFrameRegionIds(source) {
  return publishedRegionRecords(source)
    .filter((region) => region.owner === 'PageFrame')
    .map((region) => region.value)
}

function publishedRouteRegionIds(source) {
  return publishedRegionRecords(source)
    .filter((region) => region.owner === 'RouteRegion')
    .map((region) => region.value)
}

function literalStyleModuleImports(source) {
  const ast = babelParser.parse(source, {
    sourceType: 'module',
    plugins: ['jsx', 'typescript'],
  })
  return ast.program.body.flatMap((statement) => (
    statement.type === 'ImportDeclaration'
      && statement.source.value.endsWith('.module.scss')
      ? [statement.source.value]
      : []
  ))
}

function buildsSpecializationFillContractRequired({ source, assetContract, componentContract }) {
  return source.includes('BuildSpecializationOverview')
    || assetContract.slots?.some((slot) => slot.slotId === 'asset_slot.builds-specialization-object') === true
    || componentContract.components?.some((component) => component.owner === 'BuildSpecializationOverview') === true
}

module.exports = {
  buildsSpecializationFillContractRequired,
  literalStyleModuleImports,
  pageFrameLiteralVariants,
  publishedPageFrameRegionIds,
  publishedRouteRegionIds,
  publishedSemanticRegionIds,
}
