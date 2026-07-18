'use strict'

const maxOnlineRoutesPerRun = 2

function requireOnlineRouteBatch(value, envName, knownRoutes) {
  const requested = [...new Set((value ?? '').split(',').map((route) => route.trim()).filter(Boolean))]
  if (requested.length === 0) throw new Error(`${envName} is required; use one or two comma-separated contract route ids`)
  if (requested.includes('all')) throw new Error(`${envName} rejects "all"; run at most ${maxOnlineRoutesPerRun} routes and merge offline`)
  if (requested.length > maxOnlineRoutesPerRun) throw new Error(`${envName} is limited to ${maxOnlineRoutesPerRun} routes per online run`)
  const known = new Set(knownRoutes)
  const unknown = requested.filter((route) => !known.has(route))
  if (unknown.length > 0) throw new Error(`unknown ${envName}: ${unknown.join(', ')}`)
  return new Set(requested)
}

module.exports = { maxOnlineRoutesPerRun, requireOnlineRouteBatch }
