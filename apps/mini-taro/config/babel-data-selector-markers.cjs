'use strict'

module.exports = function dataSelectorMarkers({ types: t }) {
  return {
    name: 'wow-data-selector-markers',
    visitor: {
      Program: {
        enter(programPath, state) {
          state.markerImports = null
        },
        exit(programPath, state) {
          if (!state.markerImports) return
          programPath.unshiftContainer('body', t.importDeclaration([
            t.importSpecifier(state.markerImports.data, t.identifier('dataSelectorClass')),
            t.importSpecifier(state.markerImports.join, t.identifier('selectorClass')),
          ], t.stringLiteral('@wow-mini/design-system/components/selector-markers')))
        },
      },
      JSXOpeningElement(elementPath, state) {
        const attributes = elementPath.get('attributes')
        const dataAttributes = attributes.filter((attributePath) => {
          if (!attributePath.isJSXAttribute()) return false
          const name = attributePath.node.name
          return t.isJSXIdentifier(name) && name.name.startsWith('data-')
        })
        if (!dataAttributes.length) return

        if (!state.markerImports) {
          state.markerImports = {
            data: elementPath.scope.generateUidIdentifier('dataSelectorClass'),
            join: elementPath.scope.generateUidIdentifier('selectorClass'),
          }
        }

        const markers = dataAttributes.flatMap((attributePath) => {
          const attribute = attributePath.node
          const name = attribute.name.name.slice(5)
          let value
          if (!attribute.value) value = t.booleanLiteral(true)
          else if (t.isStringLiteral(attribute.value)) value = t.stringLiteral(attribute.value.value)
          else if (t.isJSXExpressionContainer(attribute.value) && !t.isJSXEmptyExpression(attribute.value.expression)) {
            value = t.cloneNode(attribute.value.expression, true)
          } else return []
          return [t.callExpression(state.markerImports.data, [t.stringLiteral(name), value])]
        })
        if (!markers.length) return

        const classNamePath = attributes.find((attributePath) => {
          if (!attributePath.isJSXAttribute()) return false
          const name = attributePath.node.name
          return t.isJSXIdentifier(name) && name.name === 'className'
        })
        let existingClassName = t.nullLiteral()
        if (classNamePath) {
          const value = classNamePath.node.value
          if (t.isStringLiteral(value)) existingClassName = t.stringLiteral(value.value)
          else if (t.isJSXExpressionContainer(value) && !t.isJSXEmptyExpression(value.expression)) {
            existingClassName = t.cloneNode(value.expression, true)
          }
          classNamePath.remove()
        }
        elementPath.pushContainer('attributes', t.jsxAttribute(
          t.jsxIdentifier('className'),
          t.jsxExpressionContainer(t.callExpression(state.markerImports.join, [existingClassName, ...markers])),
        ))
      },
    },
  }
}
