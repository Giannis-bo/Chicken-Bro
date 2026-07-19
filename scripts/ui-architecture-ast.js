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

module.exports = { pageFrameLiteralVariants }
