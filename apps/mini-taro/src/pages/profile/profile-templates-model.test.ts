import { describe, expect, it } from 'vitest'

import type { BuildTemplate } from '@wow-mini/domain'

import { buildProfileTemplatesView } from './profile-templates-model'

function template(id: string, type: 'talent' | 'gear', updatedAt: string, remote = false): BuildTemplate {
  return {
    id,
    clientId: '',
    type,
    title: `后端模板 ${id}`,
    classKey: '',
    className: '',
    specKey: '',
    specName: '',
    heroKey: '',
    heroLabel: '',
    scenarioKey: '',
    scenarioTitle: '',
    rawString: `${type}=${id}`,
    simcLines: [],
    status: 'saved',
    statusLabel: '已保存',
    source: 'verification',
    metadata: {},
    createdAt: updatedAt,
    updatedAt,
    remote,
    schemaVersion: 1,
    trust: { level: remote ? 'backend_verified' : 'local_only' },
  }
}

describe('profile/templates truth model', () => {
  it('derives real counts and the two latest stable positions', () => {
    const view = buildProfileTemplatesView(
      { nickname: '真实昵称' },
      [
        template('old', 'talent', '2026-07-15T01:00:00Z'),
        template('new', 'gear', '2026-07-15T03:00:00Z'),
        template('middle', 'talent', '2026-07-15T02:00:00Z'),
      ],
      'ready',
    )
    expect(view.metrics.map((metric) => metric.value)).toEqual(['2', '1', '已创建 3'])
    expect(view.recent.map((item) => item.id)).toEqual(['new', 'middle'])
    expect(view.nickname).toBe('真实昵称')
  })

  it('retains neutral positions and zero counts for an empty repository', () => {
    const view = buildProfileTemplatesView({}, [], 'stale')
    expect(view.metrics.map((metric) => metric.value)).toEqual(['0', '0', '尚未创建'])
    expect(view.recent).toHaveLength(2)
    expect(view.recent.every((item) => item.empty && !item.deletable)).toBe(true)
    expect(view.storageModeLabel).toBe('本地模式')
    expect(view.syncLabel).toContain('本地')
  })

  it('distinguishes account, mixed and local storage without inventing identity', () => {
    expect(buildProfileTemplatesView({ openid: 'owner' }, [template('remote', 'talent', '2026-07-15T01:00:00Z', true)], 'ready').storageMode).toBe('account')
    expect(buildProfileTemplatesView({ openid: 'owner' }, [
      template('remote', 'talent', '2026-07-15T01:00:00Z', true),
      template('local', 'gear', '2026-07-15T02:00:00Z'),
    ], 'ready').storageMode).toBe('mixed')
    const local = buildProfileTemplatesView({}, [], 'blocked')
    expect(local.storageMode).toBe('local')
    expect(local.settings[0]?.value).toBe('未设置')
    expect(local.settings[1]?.value).toBe('未设置')
  })

  it('uses only explicit character, server, profession and signature fields', () => {
    const view = buildProfileTemplatesView({
      nickname: '玩家',
      signature: '明确签名',
      characterName: '角色甲',
      realmName: '服务器乙',
      className: '法师',
      specName: '冰霜',
    }, [], 'ready')
    expect(view.signature).toBe('明确签名')
    expect(view.settings[0]?.value).toBe('角色甲 · 服务器乙')
    expect(view.settings[1]?.value).toBe('法师 · 冰霜')
  })
})
