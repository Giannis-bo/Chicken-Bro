import { simcDiagnosticMessage } from '../features/simc/simc-messages'
import type { SimulationJobDetail } from '@wow-mini/domain'

import { simcAttributeValue, simcDate, simcFightStyles, simcLabel, simcMetricName, simcResourceName, simcNumber, simcStatuses } from './simc-presentation'
import { simcReportName, simcNameStatus } from '../features/simc/simc-terms'
import styles from './WebSimc.module.scss'

const bonusLabels: Record<string, string> = { strength:'力量', agility:'敏捷', intellect:'智力', crit:'暴击等级', haste:'急速等级', mastery:'精通等级', versatility:'全能等级' }

interface Props {
  job: SimulationJobDetail
  onBack: () => void
  onRefresh: () => void
  refreshing: boolean
}

export default function WebSimcReport({ job, onBack, onRefresh, refreshing }: Props) {
  const report = job.result?.report
  const metricError = report?.metric.error ?? job.result?.metricError
  const actor = report?.actor ?? job.character
  const scenario = job.scenario
  const pending = job.status === 'queued' || job.status === 'running'
  return <article className={styles['report']} data-job-status={job.status}>
    <button data-simc-button="" className={styles['backButton']} onClick={onBack}>返回模拟任务</button>
    <div className={styles['reportHeader']}>
      <div><p className={styles['eyebrow']}>战斗表现分析</p><h2>模拟报告</h2>
        <p className={styles['muted']}>{actor ? `${actor.name} · ${simcLabel(actor.specialization)} ${simcLabel(actor.className)}` : '角色信息未记录'} · {simcDate(job.createdAt)}</p>
      </div>
      <span className={styles['status']} data-status={job.status}>{simcStatuses[job.status]}</span>
    </div>
    <div className={styles['reportMeta']}>
      <span>{report?.engine.version ? `Simc版本：${report.engine.version}` : 'Simc版本：未记录'}</span>
      {report?.engine.gameVersion ? <span>游戏 {report.engine.gameVersion}</span> : null}
      {report?.engine.build ? <span>游戏构建版本 {report.engine.build}</span> : null}
    </div>

    {pending ? <section className={styles['empty']} role="status">
      <span className={styles['pendingIcon']} aria-hidden="true">◷</span>
      <h3>{job.status === 'queued' ? '任务已提交，等待云端模拟' : '云端正在模拟你的角色'}</h3>
      <p>结果生成后会自动更新。你也可以返回任务列表，稍后继续查看。</p>
      <button data-simc-button="" className={styles['secondaryButton']} disabled={refreshing} onClick={onRefresh}>{refreshing ? '正在更新…' : '刷新状态'}</button>
    </section> : null}
    {job.status === 'failed' || job.status === 'cancelled' ? <section className={styles['empty']}>
      <h3>{job.status === 'failed' ? '模拟未完成' : '任务已取消'}</h3>
      <p>{job.status === 'failed' ? '本次运行没有可用结果。请检查角色来源和配置后重新提交。' : '本次任务未生成模拟结果。'}</p>
      {job.errorCode ? <span className={styles['failureCode']} data-error-code={job.errorCode}>{simcDiagnosticMessage(job.errorCode)}</span> : null}
    </section> : null}

    {job.result ? <>
      {actor?.className.toLowerCase() === 'evoker' && actor.specialization.toLowerCase() === 'augmentation' ? <p className={styles['notice']}>增辉结果使用 SimC 默认模拟队友估算增益，不代表实际队伍表现；显示的是引擎归属于该角色的 DPS，并非全队总伤害。</p> : null}
      <section className={styles['metrics']} aria-label="模拟结果摘要" data-result-id={job.result.id}>
        <div className={styles['primaryMetric']}><span>{simcMetricName(job.result.metricName)}</span>
          <strong>{simcNumber(job.result.metricValue)}</strong>
          <small>{metricError != null ? `误差 ± ${simcNumber(metricError)}` : '误差未记录'}</small>
        </div>
        <div><span>迭代次数</span><strong>{simcNumber(report?.statistics.iterations)}</strong><small>实际完成的模拟次数</small></div>
        <div><span>平均战斗时长</span><strong>{simcNumber(report?.statistics.fightLengthSeconds)}{report?.statistics.fightLengthSeconds != null ? <em> 秒</em> : null}</strong><small>本次模拟的战斗长度</small></div>
        <div><span>计算耗时</span><strong>{simcNumber(report?.statistics.elapsedSeconds)}{report?.statistics.elapsedSeconds != null ? <em> 秒</em> : null}</strong><small>云端引擎运行时间</small></div>
      </section>
      {!report ? <div className={styles['notice']}>该历史任务仅保存了结果摘要，未记录技能、增益、装备天赋及引擎版本详情。</div> : <>
        {report.localization && report.localization.status !== 'complete' ? <p className={styles['notice']} role="status">{simcNameStatus(report)}</p> : null}
        <section className={styles['card']}><div className={styles['sectionHeading']}><h3>技能贡献</h3><span>按贡献量排序 · 占比以所列技能合计计算</span></div>
          {report.abilities.length ? <div className={styles['tableScroll']}><table className={styles['abilityTable']}><thead><tr><th>技能</th><th>贡献量</th><th>贡献占比</th><th>施放次数</th><th>爆击率</th></tr></thead><tbody>
            {report.abilities.map((ability, index) => ({ ability, index })).sort((a, b) => b.ability.amount - a.ability.amount).map(({ ability, index }) => <tr key={`${ability.name}-${index}`}>
              <td><span>{simcReportName(report, 'abilities', index)}</span>{ability.portion != null ? <div className={styles['barTrack']}><i style={{ width: `${Math.min(100, Math.max(0, ability.portion))}%` }} /></div> : null}</td>
              <td>{simcNumber(ability.amount)}</td><td>{ability.portion == null ? '未记录' : `${simcNumber(ability.portion)}%`}</td>
              <td>{simcNumber(ability.executions)}</td><td>{ability.critPercent == null ? '未记录' : `${simcNumber(ability.critPercent)}%`}</td>
            </tr>)}
          </tbody></table></div> : <p className={styles['missing']}>本次报告未记录技能贡献。</p>}
        </section>
        <div className={styles['reportColumns']}>
          <section className={styles['card']}><h3>增益覆盖</h3>{report.buffs.length ? <div className={styles['buffList']}>
            {report.buffs.map((buff, index) => <div key={`${buff.name}-${index}`}><div className={styles['summaryRow']}><span>{simcReportName(report, 'buffs', index)}</span><strong>{simcNumber(buff.uptime)}%</strong></div><div className={styles['barTrack']}><i style={{ width: `${Math.min(100, Math.max(0, buff.uptime))}%` }} /></div></div>)}
          </div> : <p className={styles['missing']}>本次报告未记录增益覆盖。</p>}</section>
          <section className={styles['card']}><h3>资源</h3>{report.resources.length ? <div className={styles['tableScroll']}><table><thead><tr><th>资源</th><th>获得</th><th>消耗</th></tr></thead><tbody>
            {report.resources.map((resource, index) => <tr key={`${resource.name}-${index}`}><td>{simcResourceName(resource.name)}</td><td>{simcNumber(resource.gained)}</td><td>{simcNumber(resource.lost)}</td></tr>)}
          </tbody></table></div> : <p className={styles['missing']}>本次报告未记录资源收支。</p>}</section>
        </div>
        <section className={styles['card']}><h3>属性</h3>{report.attributes.length ? <dl className={styles['attributeGrid']}>
          {report.attributes.map((attribute, index) => <div key={`${attribute.name}-${index}`}><dt>{simcLabel(attribute.name)}</dt><dd>{simcAttributeValue(attribute.name, attribute.value)}</dd></div>)}
        </dl> : <p className={styles['missing']}>本次报告未记录角色属性。</p>}</section>
        <section className={styles['card']}><h3>装备与天赋</h3><p className={styles['muted']}>本次运行使用的角色资料</p>
          {report.gear.length ? <div className={styles['tableScroll']}><table><thead><tr><th>部位</th><th>物品编号</th><th>物品等级</th></tr></thead><tbody>
            {report.gear.map((item, index) => <tr key={`${item.slot}-${index}`}><td>{simcLabel(item.slot)}</td><td>{item.itemId}</td><td>{simcNumber(item.itemLevel)}</td></tr>)}
          </tbody></table></div> : <p className={styles['missing']}>本次报告未记录装备。</p>}
          <div className={styles['talents']}><h4>天赋导入代码</h4>{report.actor.talents ? <pre>{report.actor.talents}</pre> : <p className={styles['missing']}>本次报告未记录天赋。</p>}</div>
        </section>
      </>}
    </> : null}

    <section className={styles['card']}><h3>本次模拟配置</h3>{scenario ? <dl className={styles['scenarioGrid']}>
      {scenario.measurement && <div><dt>阶段实验</dt><dd>从指定状态开始，统计 {scenario.measurement.durationSeconds} 秒；详细状态与条件验证见对应对话。</dd></div>}
      {scenario.initialState?.resources && <div><dt>初始资源</dt><dd>{Object.entries(scenario.initialState.resources).map(([name, value]) => `${name}：${value === 'max' ? '满值' : value}`).join('；')}</dd></div>}
      {scenario.initialState?.buffs && <div><dt>初始增益</dt><dd>{Object.entries(scenario.initialState.buffs).map(([name, value]) => `${name}：${value.stacks} 层，${value.remainingSeconds === 'full' ? '完整持续时间' : `${value.remainingSeconds} 秒`}`).join('；')}</dd></div>}
      <div><dt>战斗类型</dt><dd>{simcFightStyles[scenario.fightStyle as keyof typeof simcFightStyles] ?? '未记录战斗类型'}</dd></div>
      <div><dt>目标数</dt><dd>{simcNumber(scenario.desiredTargets)}</dd></div>
      <div><dt>迭代上限</dt><dd>{simcNumber(scenario.iterations)}</dd></div>
      <div><dt>战斗时长</dt><dd>{scenario.maxTime == null ? '未记录' : `${scenario.maxTime} 秒`}</dd></div>
      <div><dt>时长浮动</dt><dd>{scenario.varyCombatLength == null ? '未记录' : `± ${simcNumber(scenario.varyCombatLength * 100)}%`}</dd></div>
      <div><dt>目标误差</dt><dd>{scenario.targetError == null ? '未记录' : scenario.targetError === 0 ? '按迭代上限' : `${scenario.targetError}%`}</dd></div>
      {scenario.food != null ? <div><dt>食物</dt><dd>{scenario.food === 'disabled' ? '关闭' : scenario.food.replaceAll('_', ' ')}</dd></div> : null}
      {scenario.statBonuses ? <div><dt>假设增加属性</dt><dd>{Object.entries(scenario.statBonuses).map(([stat, value]) => `${bonusLabels[stat] ?? stat} +${value}`).join('、')}</dd></div> : null}
      <div><dt>团队增益</dt><dd>{scenario.raidBuffs == null ? '未记录' : scenario.raidBuffs ? '开启' : '关闭'}</dd></div>
      <div><dt>嗜血 / 英勇</dt><dd>{scenario.bloodlust == null ? '未记录' : scenario.bloodlust ? '开启' : '关闭'}</dd></div>
    </dl> : <p className={styles['missing']}>该历史任务未记录完整模拟配置。</p>}</section>
    <details className={styles['provenance']}><summary>运行记录与来源</summary><dl>
      <div><dt>任务编号</dt><dd>{job.id}</dd></div><div><dt>编译器</dt><dd>{job.compilerRevision}</dd></div>
      <div><dt>运行身份</dt><dd>{job.runtimeRevision}</dd></div><div><dt>场景校验</dt><dd>{job.scenarioHash}</dd></div>
      {report?.localization ? <><div><dt>国服名称</dt><dd>{simcNameStatus(report)}</dd></div><div><dt>名称数据校验</dt><dd>{report.localization.catalogRevision ?? '不可用'}</dd></div></> : null}
      {job.result ? <div><dt>角色配置校验</dt><dd>{job.result.profileSha256}</dd></div> : null}
    </dl></details>
  </article>
}
