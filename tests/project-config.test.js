const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

test('mini-program pack options ignore non-client workspace directories without dropping runtime fallback modules', () => {
  const projectConfig = JSON.parse(fs.readFileSync('project.config.json', 'utf8'))
  const ignored = new Set((projectConfig.packOptions?.ignore || []).map((entry) => `${entry.type}:${entry.value}`))

  for (const value of [
    '.worktrees/**',
    'tests/**',
    'docs/**',
    'websim/**'
  ]) {
    assert.ok(ignored.has(`glob:${value}`), `${value} should be ignored by WeChat DevTools packaging`)
  }

  for (const value of [
    'server/**/*.py',
    'server/**/*.pyc',
    'server/**/__pycache__/**',
    'server/data/**',
    'server/*.sh',
    'server/*.service',
    'server/*.timer'
  ]) {
    assert.ok(ignored.has(`glob:${value}`), `${value} should be ignored by WeChat DevTools packaging`)
  }

  assert.equal(ignored.has('glob:server/**'), false, 'server JS fallback modules must stay package-visible')

  for (const runtimeModule of [
    'server/news/home-payload.js',
    'server/news/articles.seed.js',
    'server/builds/home-payload.js',
    'server/pve/home-payload.js',
    'server/game-season.js'
  ]) {
    assert.ok(fs.existsSync(runtimeModule), `${runtimeModule} should remain available to mini-program require()`)
  }
})

test('roadmap marks first-version deferred surfaces as pending planning', () => {
  const roadmap = fs.readFileSync('docs/roadmap.md', 'utf8')

  assert.match(roadmap, /\| 职业专精 \| [^\n|]*热门专精\/属性权重\/输出循环待规划/)
  assert.match(roadmap, /职业专精 tab 开放“天赋构筑”“装备模拟”“模拟 SimC”“任务列表”四个入口/)
  assert.match(roadmap, /\| PVE 专区 \| 待规划 \|/)
  assert.match(roadmap, /\| 智能分析 \/ SimC \| [^\n|]*首版只保留炸鸡队长/)
  assert.match(roadmap, /\| 智能分析 \/ SimC \| [^\n|]*SimC 与任务列表迁入职业专精/)
  assert.match(roadmap, /\| 智能分析 \/ SimC \| [^\n|]*WCL 待规划/)
  assert.match(roadmap, /\| 待规划 \| PVE 职业天梯移动端排行 \|/)
  assert.match(roadmap, /\| 待规划 \| WCL \/ 日志复盘链路 \|/)
})
