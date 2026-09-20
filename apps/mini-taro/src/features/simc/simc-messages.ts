// Display text only. API codes, snapshot paths and job states remain unchanged.
const readiness: Readonly<Record<string, string>> = {
  READY_FOR_SIMC: '可以模拟', INCOMPLETE_FOR_SIMC: '角色资料待完善', INVALID_LINK: '角色链接无效',
  CHARACTER_NOT_FOUND: '未找到角色', ACCESS_RESTRICTED: '角色资料访问受限', SNAPSHOT_UNAVAILABLE: '角色资料暂不可用',
}

const characterFields: Readonly<Record<string, string>> = {
  name: '角色名称', region: '角色地区', realm: '角色服务器', level: '角色等级',
  classkey: '角色职业', speckey: '角色专精', racekey: '角色种族',
}
const slots: Readonly<Record<string, string>> = {
  head: '头部', neck: '颈部', shoulder: '肩部', back: '背部', chest: '胸部', wrist: '腕部',
  hands: '手部', waist: '腰部', legs: '腿部', feet: '脚部', finger1: '戒指一', finger2: '戒指二',
  trinket1: '饰品一', trinket2: '饰品二', main_hand: '主手', off_hand: '副手',
}
const gearFields: Readonly<Record<string, string>> = {
  itemid: '物品编号', itemlevel: '物品等级', bonusids: '附加属性标识', gems: '宝石', enchant: '附魔',
}
const requiredFields: Readonly<Record<string, string>> = {
  talents: '天赋配置', 'talents.loadout': '天赋配置', 'talents.string': '天赋导入代码', gear: '装备资料',
  class: '角色职业', spec: '角色专精', race: '角色种族', level: '角色等级', region: '角色地区', realm: '角色服务器',
  provenance: '资料来源记录', sourcerevision: '资料来源版本', sourceurl: '资料来源链接',
}

const diagnostic: Readonly<Record<string, string>> = {
  ...readiness,
  RUNNING: '正在执行', QUEUED: '等待执行', SUCCEEDED: '执行完成', FAILED: '执行失败', CANCELLED: '已取消',
  SIMC_RESULT_VALID: '模拟结果已验证',
  AUTH_REQUIRED: '登录已失效，请重新登录', MINI_SESSION_REQUIRED: '小程序登录已失效，请重新登录',
  WEB_SESSION_REQUIRED: '网页登录已失效，请重新登录', CSRF_INVALID: '登录验证已失效，请刷新页面后重试',
  INVALID_LINK: '角色链接无效，仅支持 HTTPS 的 Raider.IO 角色链接',
  CHARACTER_NOT_FOUND: '未找到角色，请检查角色链接', ACCESS_RESTRICTED: '角色资料访问受限，请检查来源网站的公开权限',
  SNAPSHOT_UNAVAILABLE: '角色资料暂不可用，请稍后重新读取', SNAPSHOT_NOT_FOUND: '未找到角色资料，请重新读取角色',
  SNAPSHOT_NOT_READY: '角色资料尚不完整，请先补齐所需资料', SIMULATION_NOT_FOUND: '未找到该模拟任务',
  TALENT_CATALOG_RUNTIME_MISMATCH: '天赋资料与模拟引擎版本不一致，暂不能修改天赋',
  TALENT_PATH_RULES_UNAVAILABLE: '当前缺少这次跨节点调整的前置规则，暂不能验证合法性',
  TALENT_PREREQUISITE_INVALID: '天赋前置节点未满足', TALENT_POINT_GATE_INVALID: '天赋点数门槛未满足',
  TALENT_NODE_INVALID: '天赋节点、选择或等级无效', TALENT_BUILD_INVALID: '天赋点数、专精或英雄树组合无效',
  TALENT_EXPORT_INVALID: '天赋导出码无效', TALENT_SPEC_INVALID: '天赋与角色专精不匹配',
  TALENT_OVERRIDE_INVALID: '天赋修改参数无效', TALENT_LEVEL_UNSUPPORTED: '当前角色等级不支持天赋编辑',
  SIMC_EFFECTIVE_CONFIG_MISMATCH: '模拟报告未确认采用指定配置，无法作为对照结果',
  TALENTS_MISSING: '缺少天赋配置', MISSING_TALENTS: '缺少天赋配置', TALENTS_INVALID: '天赋配置无效，请重新读取角色',
  SOURCE_PROVENANCE_MISSING: '缺少角色资料来源记录，请重新读取角色',
  SOURCE_PROVENANCE_INVALID: '角色资料来源记录无效，请重新读取角色',
  SOURCE_HASH_MISSING: '缺少角色资料校验记录，请重新读取角色',
  PROFILE_NOT_REAL_SOURCE: '角色资料缺少可验证的真实来源，请重新读取角色',
  COMPILER_UNAVAILABLE: '角色配置编译服务暂不可用，请稍后重试',
  RUNTIME_UNAVAILABLE: '云端模拟引擎暂不可用，请稍后重试',
  HEALER_SPEC_UNSUPPORTED: 'SimC 不支持治疗专精进行模拟',
  SPEC_UNSUPPORTED: '无法识别该职业专精，请检查角色当前专精',
  SPEC_NOT_ENABLED: '该专精尚未开放模拟，请联系管理员',
  SIMC_UNAVAILABLE: '云端模拟引擎暂不可用，请稍后重试',
  SIMC_RUNTIME_REVISION_STALE: '云端引擎版本已变化，请重新读取角色后提交',
  SIMC_IDENTITY_INVALID: '云端引擎身份校验失败，请稍后重试',
  SIMC_IDENTITY_MISMATCH: '云端引擎身份不一致，请稍后重试',
  SIMC_TIMEOUT: '云端模拟超时，请稍后重试',
  SIMC_POLL_LIMIT: '任务仍在运行，请稍后刷新状态',
  SIMC_EXECUTION_FAILED: '云端模拟执行失败，请检查角色资料和战斗设置',
  SIMC_FATAL_DIAGNOSTIC: '云端模拟遇到执行错误，未生成可用结果',
  SIMC_ACTOR_INVALID: '模拟结果的角色校验失败，无法展示结果',
  SIMC_METRIC_INVALID: '模拟结果指标无效，无法展示结果', SIMC_METRIC_MISSING: '模拟结果缺少有效指标',
  SIMC_REPORT_INVALID: '模拟报告校验失败，无法展示报告', SIMC_RESULT_INVALID: '模拟结果校验失败，无法展示结果',
  SIMC_PERSISTENCE_FAILED: '模拟结果保存失败，请稍后刷新状态',
  SIMC_PHASE_STATE_MISMATCH: '实际阶段状态与设置不符，请检查资源、增益及冷却',
  SIMC_PHASE_ASSERTION_FAILED: '实际模拟未满足指定的动作、增益或资源条件，请查看对话中的实验设置',
  SIMC_PHASE_TIMEOUT: '阶段实验超时，请减少迭代次数后重试',
  SIMC_PHASE_EXECUTION_FAILED: '引擎未能执行指定阶段，请检查状态和施法设置',
  SIMC_PHASE_PREFLIGHT_FAILED: '阶段预检未通过，无法确认角色配置',
  SIMC_PHASE_RESOURCE_UNSUPPORTED: '引擎未提供该角色资源的初始状态证据',
  SIMC_PHASE_EVIDENCE_MISSING: '阶段验证证据不完整，无法确认结果',
  SIMC_FAILED: '模拟未完成，请检查角色资料和战斗设置',
  SCENARIO_INVALID: '战斗设置无效，请检查参数范围', SIMC_SCENARIO_INVALID: '已保存的战斗设置校验失败',
  GEM_OVERRIDE_SOCKET_MISMATCH: '宝石配置与装备插槽不匹配，请检查宝石数量',
  PROFILE_TOO_LARGE: '角色配置超出大小限制，请重新读取角色', JOB_PAYLOAD_INVALID: '模拟任务参数校验失败',
  LEASE_LOST: '执行归属已变化，请刷新任务状态',
  IDEMPOTENCY_CONFLICT: '本次提交记录与参数不一致，请重新提交',
  IDEMPOTENCY_KEY_INVALID: '提交标识无效，请重新提交', IDEMPOTENCY_KEY_REQUIRED: '缺少提交标识，请重新提交',
  INVALID_CURSOR: '任务列表位置已失效，请刷新列表',
  NETWORK_ERROR: '网络连接失败，请稍后重试', SIMC_REQUEST_FAILED: '模拟请求失败，请稍后重试',
}

function lookup(values: Readonly<Record<string, string>>, key: string): string | undefined {
  return Object.prototype.hasOwnProperty.call(values, key) ? values[key] : undefined
}

function chineseMessage(value: string | undefined): string | undefined {
  const text = value?.trim()
  return text && /[\u3400-\u9fff]/u.test(text) && !/[A-Za-z]/u.test(text) ? text : undefined
}

export function simcReadinessLabel(value: string, blockers: readonly string[] = []): string {
  if (value.trim().toUpperCase() === 'INCOMPLETE_FOR_SIMC') {
    if (blockers.includes('HEALER_SPEC_UNSUPPORTED')) return '治疗专精不支持模拟'
    if (blockers.some((code) => ['RUNTIME_UNAVAILABLE', 'COMPILER_UNAVAILABLE', 'SPEC_UNSUPPORTED', 'SPEC_NOT_ENABLED'].includes(code))) return '暂时无法模拟'
  }
  return lookup(readiness, value.trim().toUpperCase()) ?? chineseMessage(value) ?? '资料状态暂不可用'
}

function gearFieldLabel(slot: string, field?: string): string | undefined {
  const slotName = lookup(slots, slot)
  if (!slotName) return undefined
  if (!field) return `${slotName}装备`
  const fieldName = lookup(gearFields, field)
  return fieldName ? `${slotName}装备${fieldName}` : undefined
}

export function simcRequiredFieldLabel(path: string): string {
  const key = path.trim().toLowerCase()
  const explicit = lookup(requiredFields, key)
  if (explicit) return explicit
  const segments = key.split('.')
  if (segments[0] === 'character' && segments.length === 2) {
    return lookup(characterFields, segments[1]!) ?? '未识别的角色资料项'
  }
  if (segments[0] === 'gear' && (segments.length === 2 || segments.length === 3)) {
    return gearFieldLabel(segments[1]!, segments[2]) ?? '未识别的装备资料项'
  }
  if (key === 'gearstate.unequippedslots.off_hand') return '副手未装备状态'
  return chineseMessage(path) ?? '未识别的资料项'
}

function gearDiagnostic(code: string): string | undefined {
  const missing = code.startsWith('GEAR_') && code.endsWith('_MISSING')
  const invalid = code.startsWith('INVALID_GEAR_')
  if (!missing && !invalid) return undefined
  const detail = (missing ? code.slice(5, -8) : code.slice(13)).toLowerCase()
  for (const slot of Object.keys(slots)) {
    if (detail !== slot && !detail.startsWith(`${slot}_`)) continue
    const label = gearFieldLabel(slot, detail === slot ? undefined : detail.slice(slot.length + 1))
    if (label) return missing ? `缺少${label}` : `${label}无效`
  }
  return undefined
}

export function simcDiagnosticMessage(code: string, message?: string): string {
  const translated = chineseMessage(message)
  if (translated) return translated
  const key = code.trim().toUpperCase()
  const known = lookup(diagnostic, key) ?? gearDiagnostic(key)
  if (known) return known
  const characterMissing: Readonly<Record<string, string>> = {
    CHARACTER_IDENTITY_MISSING: 'name', CHARACTER_REGION_MISSING: 'region', CHARACTER_REALM_MISSING: 'realm',
    CHARACTER_LEVEL_MISSING: 'level', CHARACTER_CLASS_MISSING: 'classkey', CHARACTER_SPEC_MISSING: 'speckey',
    CHARACTER_RACE_MISSING: 'racekey', MISSING_CHARACTER_NAME: 'name', MISSING_CLASS: 'classkey',
    MISSING_SPEC: 'speckey', MISSING_RACE: 'racekey', MISSING_LEVEL: 'level', MISSING_REGION: 'region', MISSING_REALM: 'realm',
  }
  const field = lookup(characterMissing, key)
  if (field) return `缺少${lookup(characterFields, field)}`
  return chineseMessage(code) ?? '暂时无法完成此操作，请稍后重试'
}
