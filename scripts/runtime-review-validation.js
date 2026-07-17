'use strict'

const sha256Pattern = /^[a-f\d]{64}$/u
const isoUtcPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/u

function hasFields(value, fields) {
  return Boolean(value && fields.every((field) => Object.hasOwn(value, field)))
}

function isCompletePassRecord(review, contract) {
  const passRecord = review?.reviewRecord
  const passMetrics = passRecord?.passMetrics
  return Boolean(
    review?.status === 'PASS'
    && passRecord
    && contract.requiredFields.every((field) => Object.hasOwn(passRecord, field))
    && hasFields(passRecord.viewport, contract.fieldContract.viewport)
    && hasFields(passRecord.runtimeArtifact, contract.fieldContract.runtimeArtifact)
    && hasFields(passRecord.targetArtifact, contract.fieldContract.targetArtifact)
    && hasFields(passRecord.targetMapping, contract.fieldContract.targetMapping)
    && passRecord.route === review.route
    && passRecord.path === review.path
    && passRecord.status === 'PASS'
    && passRecord.interaction?.status === 'PASS'
    && typeof passRecord.runtimeArtifact?.path === 'string'
    && sha256Pattern.test(passRecord.runtimeArtifact?.sha256 ?? '')
    && passRecord.runtimeArtifact.path.includes(passRecord.runtimeArtifact.sha256)
    && sha256Pattern.test(passRecord.targetArtifact?.sha256 ?? '')
    && Array.isArray(passRecord.regions)
    && passRecord.regions.length > 0
    && passRecord.regions.every((region) => (
      hasFields(region, contract.fieldContract.regions) && region.status === 'PASS'
    ))
    && Array.isArray(passRecord.assetSemantics)
    && passRecord.assetSemantics.length > 0
    && passRecord.assetSemantics.every((asset) => (
      hasFields(asset, contract.fieldContract.assetSemantics) && asset.status === 'PASS'
    ))
    && Array.isArray(passRecord.p0)
    && passRecord.p0.length === 0
    && Array.isArray(passRecord.p1)
    && passRecord.p1.length === 0
    && Array.isArray(passRecord.p2)
    && hasFields(passRecord.collisions, contract.fieldContract.collisions)
    && contract.fieldContract.collisions.every((field) => passRecord.collisions?.[field] === 0)
    && hasFields(passRecord.interaction, contract.fieldContract.interaction)
    && hasFields(passMetrics, contract.fieldContract.passMetrics)
    && passMetrics?.p0Count === contract.passCriteria.p0Count
    && passMetrics?.p1Count === contract.passCriteria.p1Count
    && passMetrics?.systemCollisionPx === contract.passCriteria.systemCollisionPx
    && passMetrics?.textClipCount === contract.passCriteria.textClipCount
    && passMetrics?.componentOverlapPx === contract.passCriteria.componentOverlapPx
    && passRecord.humanConfirmation?.status === 'confirmed'
    && hasFields(passRecord.humanConfirmation, contract.fieldContract.humanConfirmation)
    && typeof passRecord.humanConfirmation?.reviewer === 'string'
    && passRecord.humanConfirmation.reviewer.trim().length > 0
    && typeof passRecord.humanConfirmation?.confirmedAt === 'string'
    && isoUtcPattern.test(passRecord.humanConfirmation.confirmedAt)
  )
}

module.exports = { isCompletePassRecord }
