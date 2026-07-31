'use strict'

function gearApplyEvidenceMatches({
  candidateItemId,
  candidateVariantKey,
  committedBefore,
  committedVariantBefore,
  resolvedBefore,
  resolvedVariantBefore,
  committedAfter,
  committedVariantAfter,
  resolvedAfter,
  resolvedVariantAfter,
  resolveState,
  sawResolving,
}) {
  return Boolean(
    sawResolving
    && candidateItemId
    && typeof candidateVariantKey === 'string'
    && typeof committedVariantBefore === 'string'
    && typeof resolvedVariantBefore === 'string'
    && typeof committedVariantAfter === 'string'
    && typeof resolvedVariantAfter === 'string'
    && committedBefore !== candidateItemId
    && resolvedBefore !== candidateItemId
    && (resolveState === 'verified' || resolveState === 'idle')
    && committedAfter === candidateItemId
    && resolvedAfter === candidateItemId
    && committedVariantAfter === candidateVariantKey
    && resolvedVariantAfter === candidateVariantKey
  )
}

module.exports = { gearApplyEvidenceMatches }
