'use strict'

const sha256Pattern = /^[a-f\d]{64}$/u

function isCompletePassRecord(review, contract) {
  const passRecord = review?.reviewRecord
  const passMetrics = passRecord?.passMetrics
  return Boolean(
    review?.status === 'PASS'
    && passRecord
    && contract.requiredFields.every((field) => Object.hasOwn(passRecord, field))
    && passRecord.route === review.route
    && passRecord.path === review.path
    && passRecord.status === 'PASS'
    && passRecord.interaction?.status === 'PASS'
    && typeof passRecord.runtimeArtifact?.path === 'string'
    && passRecord.runtimeArtifact.path.length > 0
    && sha256Pattern.test(passRecord.runtimeArtifact?.sha256 ?? '')
    && sha256Pattern.test(passRecord.targetArtifact?.sha256 ?? '')
    && Array.isArray(passRecord.regions)
    && passRecord.regions.length > 0
    && passRecord.regions.every((region) => region.status === 'PASS')
    && Array.isArray(passRecord.assetSemantics)
    && passRecord.assetSemantics.length > 0
    && passRecord.assetSemantics.every((asset) => asset.status === 'PASS')
    && Array.isArray(passRecord.p0)
    && passRecord.p0.length === 0
    && Array.isArray(passRecord.p1)
    && passRecord.p1.length === 0
    && Array.isArray(passRecord.p2)
    && contract.fieldContract.collisions.every((field) => passRecord.collisions?.[field] === 0)
    && passMetrics?.p0Count === contract.passCriteria.p0Count
    && passMetrics?.p1Count === contract.passCriteria.p1Count
    && passMetrics?.systemCollisionPx === contract.passCriteria.systemCollisionPx
    && passMetrics?.textClipCount === contract.passCriteria.textClipCount
    && passMetrics?.componentOverlapPx === contract.passCriteria.componentOverlapPx
    && passRecord.humanConfirmation?.status === 'confirmed'
    && typeof passRecord.humanConfirmation?.reviewer === 'string'
    && passRecord.humanConfirmation.reviewer.length > 0
    && typeof passRecord.humanConfirmation?.confirmedAt === 'string'
    && passRecord.humanConfirmation.confirmedAt.length > 0
  )
}

module.exports = { isCompletePassRecord }
