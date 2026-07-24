'use strict'

function gearApplyEvidenceMatches({
  candidateItemId,
  committedBefore,
  resolvedBefore,
  committedAfter,
  resolvedAfter,
  resolveState,
  sawResolving,
}) {
  return Boolean(
    sawResolving
    && candidateItemId
    && committedBefore !== candidateItemId
    && resolvedBefore !== candidateItemId
    && resolveState === 'verified'
    && committedAfter === candidateItemId
    && resolvedAfter === candidateItemId
  )
}

module.exports = { gearApplyEvidenceMatches }
