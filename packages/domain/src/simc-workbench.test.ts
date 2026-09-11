import { describe, it, expect } from 'vitest'
import { isSimulationReport, isSimulationScenario, isSimulationRuntimeView, type SimulationReport } from './simc-workbench'

const report: SimulationReport = {
  schemaVersion: 1, engine: { version: '1210-01', gameVersion:'12.1.0', build:'69299' },
  actor:{name:'Stormsample',className:'shaman',specialization:'elemental',level:90,race:'orc',talents:null},
  metric:{name:'dps',value:12345,error:20},statistics:{iterations:1000,fightLengthSeconds:300,elapsedSeconds:2},
  abilities:[{name:'Lightning Bolt',amount:1000,portion:15,executions:30,critPercent:20}],
  buffs:[{name:'Bloodlust',uptime:13}],resources:[],attributes:[],gear:[],
}
describe('SimC workbench guards', () => {
  it('validates short bounded attribute experiments', () => {
    expect(isSimulationScenario({maxTime:20,food:'disabled',statBonuses:{intellect:50,crit:72}})).toBe(true)
    for (const statBonuses of [{}, {bad:1}, {crit:-1}, {crit:1001}, {crit:1.5}, {crit:true}]) expect(isSimulationScenario({statBonuses})).toBe(false)
    expect(isSimulationScenario({maxTime:19})).toBe(false)
  })
  it('accepts bounded food settings and rejects injected directives', () => {
    expect(isSimulationScenario({food: 'hearty_silvermoon_parade'})).toBe(true)
    expect(isSimulationScenario({food: 'disabled'})).toBe(true)
    for (const food of ['', 'x\ninput=file', 'x,y', 1, null]) expect(isSimulationScenario({food})).toBe(false)
  })
  it('accepts custom rotations and rejects malformed or injected lists', () => {
    expect(isSimulationScenario({ actionLists: { default: ['strict_sequence,name=burst:stormkeeper:ascendance', 'lightning_bolt'] } })).toBe(true)
    for (const actionLists of [{}, { cooldowns: ['ascendance'] }, { default: ['lightning_bolt\ninput=/etc/passwd'] }, { default: Array(257).fill('lightning_bolt') }]) {
      expect(isSimulationScenario({ actionLists })).toBe(false)
    }
  })
  it('validates talent variants without accepting ambiguous or injected edits', () => {
    const node = { nodeId: 80999, entryId: 1234, rank: 1 }
    expect(isSimulationScenario({ talentOverrides: { nodes: [node] } })).toBe(true)
    for (const change of [{ nodes: [] }, { nodes: [node, node] }, { nodes: [{ ...node, rank: true }] }, { string: 'A'.repeat(30) + '\noutput=/tmp/x' }, { string: 'A'.repeat(30), nodes: [node] }]) {
      expect(isSimulationScenario({ talentOverrides: change })).toBe(false)
    }
  })
  it('requires aligned versioned localization without widening the legacy contract', () => {
    const label = { text: '闪电箭', status: 'resolved', spellId: 188196, sourceNpcId: null, method: 'spell_id' }
    const localization = { locale: 'zhCN', gameVersion: report.engine.gameVersion, catalogRevision: 'a'.repeat(64), status: 'complete', abilities: [label], buffs: [{ ...label, text: '嗜血', spellId: 2825 }] }
    expect(isSimulationReport({ ...report, schemaVersion: 2, localization })).toBe(true)
    expect(isSimulationReport({ ...report, localization })).toBe(false)
    expect(isSimulationReport({ ...report, schemaVersion: 2 })).toBe(false)
    expect(isSimulationReport({ ...report, schemaVersion: 2, localization: { ...localization, abilities: [] } })).toBe(false)
    expect(isSimulationReport({ ...report, schemaVersion: 2, localization: { ...localization, gameVersion: 'other' } })).toBe(false)
    expect(isSimulationReport({ ...report, schemaVersion: 2, localization: { ...localization, abilities: [{ ...label, spellId: true }] } })).toBe(false)
  })
  it('accepts a bounded report and rejects invalid metrics and private expansion', () => {
    expect(isSimulationReport(report)).toBe(true)
    expect(isSimulationReport({...report,metric:{...report.metric,value:Infinity}})).toBe(false)
    expect(isSimulationReport({...report,actor:{...report.actor,userId:'private'}})).toBe(false)
    expect(isSimulationReport({...report,buffs:[{name:'Invalid',uptime:101}]})).toBe(false)
  })
  it('reads equipment variant scenarios but rejects incomplete item data', () => {
    const item = { itemId: 12345, itemLevel: 285, bonusIds: [123], gems: [], enchant: null }
    expect(isSimulationScenario({ equipmentOverrides: { trinket1: item } })).toBe(true)
    expect(isSimulationScenario({ equipmentOverrides: { trinket1: { itemId: 12345 } } })).toBe(false)
    expect(isSimulationScenario({ equipmentOverrides: { unknown: item } })).toBe(false)
    expect(isSimulationScenario({ equipmentOverrides: { trinket1: { ...item, itemLevel: true } } })).toBe(false)
  })
  it('validates options and actual version metadata', () => {
    expect(isSimulationScenario({maxTime:300,targetError:.5,raidBuffs:true})).toBe(true)
    expect(isSimulationScenario({fightStyle:'bogus'})).toBe(false)
    expect(isSimulationScenario({desiredTargets:true})).toBe(false)
    expect(isSimulationRuntimeView({status:'available',version:null,gameVersion:null,build:null,sourceCommit:null,runtimeRevision:null})).toBe(false)
  })
})
