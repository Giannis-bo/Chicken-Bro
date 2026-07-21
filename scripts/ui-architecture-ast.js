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

function closedSemanticRegionIds({ publishedRouteRegions, publishedPageFrameRegions, requiredRegionIds, sharedPublished = [] }) {
  const required = new Set(requiredRegionIds)
  return [
    ...publishedRouteRegions,
    ...publishedPageFrameRegions.filter((regionId) => required.has(regionId)),
    ...sharedPublished,
  ]
}

function literalStyleModuleImports(source) {
  const ast = babelParser.parse(source, {
    sourceType: 'module',
    plugins: ['jsx', 'typescript'],
  })
  return ast.program.body.flatMap((statement) => {
    if (statement.type !== 'ImportDeclaration' || !statement.source.value.endsWith('.module.scss')) return []
    const defaultImport = statement.specifiers.find((specifier) => specifier.type === 'ImportDefaultSpecifier')
    return defaultImport ? [{ localName: defaultImport.local.name, source: statement.source.value }] : []
  })
}

function parameterizedStyleMemberImport(node, importedByLocalName, parameterName) {
  if (node?.type !== 'MemberExpression' || !node.computed) return null
  if (node.object.type !== 'Identifier' || node.property.type !== 'Identifier') return null
  if (node.property.name !== parameterName) return null
  return importedByLocalName.get(node.object.name) ?? null
}

function parameterizedStyleImportsInExpression(node, importedByLocalName, parameterName, found = new Map()) {
  if (!node || typeof node !== 'object') return found
  const directImport = parameterizedStyleMemberImport(node, importedByLocalName, parameterName)
  if (directImport) found.set(directImport.localName, directImport)
  for (const [key, value] of Object.entries(node)) {
    if (['end', 'extra', 'loc', 'start'].includes(key)) continue
    if (Array.isArray(value)) {
      for (const item of value) parameterizedStyleImportsInExpression(item, importedByLocalName, parameterName, found)
    } else if (value && typeof value === 'object') {
      parameterizedStyleImportsInExpression(value, importedByLocalName, parameterName, found)
    }
  }
  return found
}

function sameStyleImport(styleImports) {
  const unique = new Map(styleImports.filter(Boolean).map((styleImport) => [styleImport.localName, styleImport]))
  return unique.size === 1 ? [...unique.values()][0] : null
}

function isEmptyStyleFallback(node) {
  return node?.type === 'StringLiteral' && node.value === ''
}

function additiveStyleBinding(expressions, importedByLocalName, parameterName) {
  const bindings = []
  for (const expression of expressions) {
    if (!expression) continue
    const binding = returnedStyleBinding(expression, importedByLocalName, parameterName)
    if (binding) {
      bindings.push(binding)
      continue
    }
    if (parameterizedStyleImportsInExpression(expression, importedByLocalName, parameterName).size > 0) return null
  }
  return sameStyleImport(bindings)
}

function joinedArrayElements(node) {
  if (node?.type === 'ArrayExpression') return node.elements
  if (
    node?.type === 'CallExpression'
    && node.callee.type === 'MemberExpression'
    && !node.callee.computed
    && node.callee.property.type === 'Identifier'
    && node.callee.property.name === 'filter'
    && node.arguments.length === 1
    && node.arguments[0].type === 'Identifier'
    && node.arguments[0].name === 'Boolean'
  ) {
    return joinedArrayElements(node.callee.object)
  }
  return null
}

function returnedStyleBinding(node, importedByLocalName, parameterName) {
  if (!node) return null
  const directImport = parameterizedStyleMemberImport(node, importedByLocalName, parameterName)
  if (directImport) return directImport
  if (['TSAsExpression', 'TSNonNullExpression', 'TypeCastExpression'].includes(node.type)) {
    return returnedStyleBinding(node.expression, importedByLocalName, parameterName)
  }
  if (node.type === 'SequenceExpression') {
    return returnedStyleBinding(node.expressions.at(-1), importedByLocalName, parameterName)
  }
  if (node.type === 'ConditionalExpression') {
    const consequent = returnedStyleBinding(node.consequent, importedByLocalName, parameterName)
    const alternate = returnedStyleBinding(node.alternate, importedByLocalName, parameterName)
    return consequent && alternate && consequent.localName === alternate.localName ? consequent : null
  }
  if (node.type === 'LogicalExpression') {
    const left = returnedStyleBinding(node.left, importedByLocalName, parameterName)
    const right = returnedStyleBinding(node.right, importedByLocalName, parameterName)
    if (left && right && left.localName === right.localName) return left
    // The exact class declaration is verified before this inferred binding can satisfy the audit,
    // so the CSS-module lookup is non-empty for the literal class used by the caller.
    if (['??', '||'].includes(node.operator) && left && isEmptyStyleFallback(node.right)) return left
    return null
  }
  if (node.type === 'TemplateLiteral') {
    return additiveStyleBinding(node.expressions, importedByLocalName, parameterName)
  }
  if (node.type === 'BinaryExpression' && node.operator === '+') {
    return additiveStyleBinding([node.left, node.right], importedByLocalName, parameterName)
  }
  if (
    node.type === 'CallExpression'
    && node.callee.type === 'MemberExpression'
    && !node.callee.computed
    && node.callee.property.type === 'Identifier'
    && node.callee.property.name === 'join'
  ) {
    const elements = joinedArrayElements(node.callee.object)
    return elements ? additiveStyleBinding(elements, importedByLocalName, parameterName) : null
  }
  return null
}

function styleHelperBindings(source, styleImports) {
  const ast = babelParser.parse(source, { sourceType: 'module', plugins: ['jsx', 'typescript'] })
  const importedByLocalName = new Map(styleImports.map((styleImport) => [styleImport.localName, styleImport]))
  const helpers = new Map()

  for (const statement of ast.program.body) {
    if (statement.type !== 'ImportDeclaration' || statement.source.value !== './reconstruction-style') continue
    for (const specifier of statement.specifiers) {
      if (specifier.type === 'ImportSpecifier' && specifier.imported.type === 'Identifier' && specifier.imported.name === 'reconstructionStyle') {
        helpers.set(specifier.local.name, { localName: specifier.local.name, source: './reconstruction.module.scss' })
      }
    }
  }

  traverse(ast, {
    FunctionDeclaration(functionPath) {
      const helperName = functionPath.node.id?.name
      const parameterName = functionPath.node.params[0]?.type === 'Identifier' ? functionPath.node.params[0].name : null
      if (!helperName || !parameterName) return
      const returnedStyleImports = []
      functionPath.traverse({
        ReturnStatement(returnPath) {
          if (returnPath.getFunctionParent()?.node !== functionPath.node) return
          const styleImport = returnedStyleBinding(returnPath.node.argument, importedByLocalName, parameterName)
          returnedStyleImports.push(styleImport ? [styleImport] : [])
        },
      })
      if (returnedStyleImports.length === 0 || returnedStyleImports.some((imports) => imports.length !== 1)) return
      const compatibleImports = new Map(returnedStyleImports.flat().map((styleImport) => [styleImport.localName, styleImport]))
      if (compatibleImports.size === 1) helpers.set(helperName, [...compatibleImports.values()][0])
    },
  })
  return helpers
}

function validCssModuleClassToken(className) {
  return /^[A-Za-z_][A-Za-z0-9_-]*$/u.test(className)
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/gu, '\\$&')
}

function styleModuleDeclaresSelectedMaterial(styles, className, stateAttribute) {
  if (!validCssModuleClassToken(className)) return false
  const declaredClasses = new Set([...styles.matchAll(/\.([A-Za-z_][A-Za-z0-9_-]*)/gu)].map((match) => match[1]))
  if (!declaredClasses.has(className)) return false
  const escapedClassName = escapeRegExp(className)
  const escapedStateAttribute = escapeRegExp(stateAttribute)
  return new RegExp(`\\.${escapedClassName}(?![A-Za-z0-9_-])\\[${escapedStateAttribute}=['"]true['"]\\]`, 'u').test(styles)
}

function styleModuleClassReferences(source, classExpression) {
  const styleImports = literalStyleModuleImports(source)
  const importedByLocalName = new Map(styleImports.map((styleImport) => [styleImport.localName, styleImport]))
  const helpers = styleHelperBindings(source, styleImports)
  let expressionAst
  try {
    expressionAst = babelParser.parse(`const __className = (${classExpression})`, {
      sourceType: 'module',
      plugins: ['jsx', 'typescript'],
    })
  } catch {
    return []
  }
  const references = []
  traverse(expressionAst, {
    MemberExpression(memberPath) {
      const member = memberPath.node
      if (member.object.type !== 'Identifier') return
      const styleImport = importedByLocalName.get(member.object.name)
      if (!styleImport) return
      const className = member.computed && member.property.type === 'StringLiteral'
        ? member.property.value
        : !member.computed && member.property.type === 'Identifier'
          ? member.property.name
          : null
      if (className) references.push({ ...styleImport, className })
    },
    CallExpression(callPath) {
      const call = callPath.node
      if (call.callee.type !== 'Identifier' || call.arguments[0]?.type !== 'StringLiteral') return
      const styleImport = helpers.get(call.callee.name)
      if (styleImport) references.push({ ...styleImport, className: call.arguments[0].value })
    },
  })
  return [...new Map(references.map((reference) => (
    [`${reference.localName}:${reference.source}:${reference.className}`, reference]
  ))).values()]
}

function styleModuleOwnsSelectedMaterial({ source, classExpression, stateAttribute, readStyleModule }) {
  const references = styleModuleClassReferences(source, classExpression)
  if (references.length > 0) {
    return references.some((reference) => (
      styleModuleDeclaresSelectedMaterial(readStyleModule(reference.source), reference.className, stateAttribute)
    ))
  }
  const styleImports = literalStyleModuleImports(source)
  const escapedStateAttribute = escapeRegExp(stateAttribute)
  return styleImports.length === 1
    && /\bstyleSelectorClass\s*\(/u.test(classExpression)
    && new RegExp(`[^{}]+\\[${escapedStateAttribute}=['"]true['"]\\]\\s*\\{`, 'u').test(readStyleModule(styleImports[0].source))
}

function buildsSpecializationFillContractRequired({ source, assetContract, componentContract }) {
  return source.includes('BuildSpecializationOverview')
    || assetContract.slots?.some((slot) => slot.slotId === 'asset_slot.builds-specialization-object') === true
    || componentContract.components?.some((component) => component.owner === 'BuildSpecializationOverview') === true
}

function buildsSpecializationFillAudit({ source, assetContract, componentContract, readLegacyFile }) {
  const required = buildsSpecializationFillContractRequired({ source, assetContract, componentContract })
  if (!required) return { required: false, pass: true }
  const specializationObjectSlot = assetContract.slots?.find((slot) => slot.slotId === 'asset_slot.builds-specialization-object')
  const specializationRuntimeCrop = specializationObjectSlot?.runtimeCrop
  let overviewSource
  let overviewStyles
  try {
    overviewSource = readLegacyFile('packages/design-system/src/components/BuildSpecializationOverview.tsx')
    overviewStyles = readLegacyFile('packages/design-system/src/components/BuildsHomeComponents.module.scss')
  } catch {
    return { required: true, pass: false }
  }
  return {
    required: true,
    pass: Boolean(
      specializationObjectSlot?.targetAspect?.includes('aspectFill')
        && specializationRuntimeCrop?.fit === 'aspectFill'
        && specializationRuntimeCrop?.scale >= 1
        && overviewSource.includes('mode="aspectFill"')
        && /\.specializationImage\s*\{[^}]*object-fit:\s*cover;/s.test(overviewStyles)
        && /\.specializationImage\s*\{[^}]*inset:\s*0;[^}]*display:\s*block;[^}]*width:\s*100%;[^}]*height:\s*100%;/s.test(overviewStyles)
        && !/\.specializationImage\s*\{[^}]*(?:border-radius|overflow|transform):/s.test(overviewStyles)
    ),
  }
}

function routeLayoutFamilyCoverageMatches(actual) {
  return actual.stage === 9
    && actual.flow === 3
    && actual.column === 5
    && actual.grid === 1
    && actual.region === 14
}

module.exports = {
  buildsSpecializationFillAudit,
  buildsSpecializationFillContractRequired,
  closedSemanticRegionIds,
  literalStyleModuleImports,
  pageFrameLiteralVariants,
  publishedPageFrameRegionIds,
  publishedRouteRegionIds,
  publishedSemanticRegionIds,
  routeLayoutFamilyCoverageMatches,
  styleModuleClassReferences,
  styleModuleOwnsSelectedMaterial,
}
