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
  it('accepts a bounded report and rejects invalid metrics and private expansion', () => {
    expect(isSimulationReport(report)).toBe(true)
    expect(isSimulationReport({...report,metric:{...report.metric,value:Infinity}})).toBe(false)
    expect(isSimulationReport({...report,actor:{...report.actor,userId:'private'}})).toBe(false)
    expect(isSimulationReport({...report,buffs:[{name:'Invalid',uptime:101}]})).toBe(false)
  })
  it('validates options and actual version metadata', () => {
    expect(isSimulationScenario({maxTime:300,targetError:.5,raidBuffs:true})).toBe(true)
    expect(isSimulationScenario({fightStyle:'bogus'})).toBe(false)
    expect(isSimulationScenario({desiredTargets:true})).toBe(false)
    expect(isSimulationRuntimeView({status:'available',version:null,gameVersion:null,build:null,sourceCommit:null,runtimeRevision:null})).toBe(false)
  })
})
