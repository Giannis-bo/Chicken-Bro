import { describe, expect, it } from 'vitest'
import { isSimulationScenario } from './simc-workbench'
describe('phase scenarios', () => {
  const phase = { measurement: { durationSeconds: 20, actions: [{ action: 'elemental_blast', buff: 'master_of_the_elements' }] }, actionLists: { default: ['elemental_blast', 'lightning_bolt'] }, initialState: { resources: { maelstrom: 'max' }, buffs: { flowing_elements: { stacks: 2, remainingSeconds: 'full' } } }, iterations: 32 }
  it('retains structured initial state and measurement when reading jobs', () => { expect(isSimulationScenario(phase)).toBe(true) })
  it('rejects conflicting windows, unbounded batches and missing rotation', () => {
    for (const bad of [{ ...phase, maxTime: 30 }, { ...phase, iterations: 10000 }, { ...phase, actionLists: {} }, { ...phase, initialState: { buffs: { x: { stacks: 0, remainingSeconds: 2 } } } }]) expect(isSimulationScenario(bad)).toBe(false)
  })
})
