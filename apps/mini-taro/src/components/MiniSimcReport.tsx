import { useState, type ReactNode } from 'react'
import { Button, Text, View } from '@tarojs/components'
import type { SimulationJobDetail } from '@wow-mini/domain'
import { simcFightStyles, simcLabel, simcMetricName, simcNameStatus, simcReportName, simcResourceName } from '../features/simc/simc-terms'
import styles from './MiniSimcReport.module.scss'

const number = (value: number | null | undefined) => value == null ? '未记录' : value.toLocaleString('zh-CN', {maximumFractionDigits: 2})
const percent = (value: number | null | undefined) => value == null ? '未记录' : `${number(value)}%`
const toggle = (value: boolean | null | undefined) => value == null ? '未记录' : value ? '开启' : '关闭'
function Group({title, children, open = false}: {title: string; children: ReactNode; open?: boolean}) {
  const [expanded, setExpanded] = useState(open)
  return <View className={styles['card'] ?? ''}>
    <Button className={styles['groupTitle'] ?? ''} aria-label={title} aria-expanded={expanded} onClick={() => setExpanded(!expanded)}><Text>{title}</Text><Text className={styles['chevron'] ?? ''} aria-hidden>{expanded ? '⌃' : '⌄'}</Text></Button>
    {expanded ? <View className={styles['groupContent'] ?? ''}>{children}</View> : null}
  </View>
}
function Row({label, value}: {label: string; value: string}) {
  return <View className={styles['row'] ?? ''}><Text>{label}</Text><Text>{value}</Text></View>
}
export default function MiniSimcReport({job}: {job: SimulationJobDetail}) {
  const result = job.result
  const report = result?.report
  const actor = report?.actor ?? job.character
  const scenario = job.scenario
  const metricError = report?.metric.error ?? result?.metricError
  return <View>
    <View className={styles['identity'] ?? ''}>
      <Text className={styles['actor'] ?? ''}>{actor?.name || '角色信息未记录'}</Text>
      {actor ? <Text className={styles['muted'] ?? ''}>{simcLabel(actor.specialization)} {simcLabel(actor.className)}</Text> : null}
      <Text className={styles['muted'] ?? ''}>{report?.engine.version ? `本次运行 · Simc版本：${report.engine.version}` : 'Simc版本：未记录'}{report?.engine.gameVersion ? ` · 游戏 ${report.engine.gameVersion}` : ''}{report?.engine.build ? ` · 构建 ${report.engine.build}` : ''}</Text>
    </View>
    {result ? <>
      <View className={styles['metrics'] ?? ''} data-result-id={result.id}>
        <Text className={styles['metricLabel'] ?? ''}>{simcMetricName(result.metricName)}</Text>
        <Text className={styles['metric'] ?? ''}>{number(result.metricValue)}</Text>
        <Text className={styles['muted'] ?? ''}>{metricError == null ? '误差未记录' : `误差 ± ${number(metricError)}`}</Text>
        <Row label="实际迭代次数" value={number(report?.statistics.iterations)} />
        <Row label="平均战斗时长" value={report?.statistics.fightLengthSeconds == null ? '未记录' : `${number(report.statistics.fightLengthSeconds)} 秒`} />
        <Row label="计算耗时" value={report?.statistics.elapsedSeconds == null ? '未记录' : `${number(report.statistics.elapsedSeconds)} 秒`} />
      </View>
      {!report ? <Text className={styles['notice'] ?? ''}>该历史任务仅保存了结果摘要，未记录技能、增益、装备天赋及引擎版本详情。</Text> : <>
        {report.localization && report.localization.status !== 'complete' ? <Text className={styles['notice'] ?? ''}>{simcNameStatus(report)}</Text> : null}
        <Group title="技能贡献" open>
          <Text className={styles['muted'] ?? ''}>按贡献量排序；占比以所列技能合计计算。</Text>
          {report.abilities.length ? report.abilities.map((ability, index) => ({ability, index})).sort((a,b) => b.ability.amount - a.ability.amount).map(({ability, index}) => <View key={`${ability.name}-${index}`} className={styles['entry'] ?? ''} data-ability={index}>
            <Text className={styles['entryTitle'] ?? ''}>{simcReportName(report, 'abilities', index)}</Text>
            <Row label="贡献量" value={number(ability.amount)} /><Row label="占比" value={percent(ability.portion)} />
            {ability.portion != null ? <View className={styles['track'] ?? ''}><View className={styles['bar'] ?? ''} style={{width: `${Math.max(0,Math.min(100,ability.portion))}%`}} /></View> : null}
            <View className={styles['entryMeta'] ?? ''}><Text>施放次数 {number(ability.executions)}</Text><Text>爆击率 {percent(ability.critPercent)}</Text></View>
          </View>) : <Text className={styles['muted'] ?? ''}>本次报告未记录技能贡献。</Text>}
        </Group>
        <Group title="增益覆盖">
          {report.buffs.length ? report.buffs.map((buff, index) => <View key={`${buff.name}-${index}`} className={styles['entry'] ?? ''}>
            <Row label={simcReportName(report, 'buffs', index)} value={percent(buff.uptime)} />
            <View className={styles['track'] ?? ''}><View className={styles['bar'] ?? ''} style={{width: `${Math.max(0,Math.min(100,buff.uptime))}%`}} /></View>
          </View>) : <Text className={styles['muted'] ?? ''}>本次报告未记录增益覆盖。</Text>}
        </Group>
        <Group title="资源">
          {report.resources.length ? report.resources.map((resource, index) => <View key={`${resource.name}-${index}`} className={styles['entry'] ?? ''}>
            <Text className={styles['entryTitle'] ?? ''}>{simcResourceName(resource.name)}</Text><View className={styles['entryMeta'] ?? ''}><Text>获得 {number(resource.gained)}</Text><Text>消耗 {number(resource.lost)}</Text></View>
          </View>) : <Text className={styles['muted'] ?? ''}>本次报告未记录资源收支。</Text>}
        </Group>
        <Group title="属性">
          {report.attributes.length ? report.attributes.map((attribute, index) => <Row key={`${attribute.name}-${index}`} label={simcLabel(attribute.name)} value={`${number(attribute.value)}${attribute.name.endsWith('_pct') ? '%' : ''}`} />) : <Text className={styles['muted'] ?? ''}>本次报告未记录角色属性。</Text>}
        </Group>
        <Group title="装备与天赋">
          <Text className={styles['muted'] ?? ''}>本次运行使用的角色资料</Text>
          {report.gear.length ? report.gear.map((item, index) => <View key={`${item.slot}-${index}`} className={styles['entry'] ?? ''}>
            <Text className={styles['entryTitle'] ?? ''}>{simcLabel(item.slot)}</Text><View className={styles['entryMeta'] ?? ''}><Text>物品编号 {item.itemId}</Text><Text>物品等级 {number(item.itemLevel)}</Text></View>
          </View>) : <Text className={styles['muted'] ?? ''}>本次报告未记录装备。</Text>}
          <Text className={styles['entryTitle'] ?? ''}>天赋导入代码</Text><Text selectable className={styles['talents'] ?? ''}>{report.actor.talents || '本次报告未记录天赋。'}</Text>
        </Group>
      </>}
    </> : null}
    <Group title="本次模拟配置">
      {scenario ? <>
        <Row label="战斗类型" value={simcFightStyles[scenario.fightStyle as keyof typeof simcFightStyles] ?? '未记录'} />
        <Row label="目标数" value={number(scenario.desiredTargets)} /><Row label="迭代上限" value={number(scenario.iterations)} />
        <Row label="战斗时长" value={scenario.maxTime == null ? '未记录' : `${scenario.maxTime} 秒`} />
        <Row label="时长浮动" value={scenario.varyCombatLength == null ? '未记录' : `± ${percent(scenario.varyCombatLength * 100)}`} />
        <Row label="目标误差" value={scenario.targetError === 0 ? '按迭代上限' : percent(scenario.targetError)} />
        <Row label="团队增益" value={toggle(scenario.raidBuffs)} /><Row label="嗜血 / 英勇" value={toggle(scenario.bloodlust)} />
      </> : <Text className={styles['muted'] ?? ''}>该历史任务未记录完整模拟配置。</Text>}
    </Group>
  </View>
}
