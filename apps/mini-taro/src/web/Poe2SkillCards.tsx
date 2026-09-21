import {poe2Term, poe2Slots, type Poe2Result} from '@wow-mini/domain'
import styles from './WebPoe2.module.scss'

export default function Poe2SkillCards({result}: {result: Poe2Result}) {
  const groups = result.skillSetup
  if (!groups) return <section aria-label="技能搭配"><h3>技能搭配</h3><p>此记录暂无完整技能搭配信息，请重新导入构筑。</p></section>
  const configured = groups.filter(g => g.source === 'configured')
  const granted = groups.filter(g => g.source !== 'configured')
  const cards = (rows: typeof groups) => <div className={styles['skillGrid']}>{rows.map(group => {
    const skills = group.gems.filter(gem => gem.kind === 'skill')
    const supports = group.gems.filter(gem => gem.kind === 'support')
    const unknown = group.gems.filter(gem => gem.kind === 'unknown')
    return <article key={group.index} className={styles['skillCard']}>
      <header><span>{group.source === 'tree' ? '天赋授予' : group.source === 'item' ? '装备授予' : group.source === 'generated' ? '额外技能' : '技能'}</span>{group.slot ? <small>{poe2Slots[group.slot] ?? group.slot}</small> : null}</header>
      {skills.length ? skills.map((gem, index) => <h4 key={index}>{poe2Term(gem.name, 'gem')}<small>{gem.level} 级</small></h4>) : <h4>关联宝石</h4>}
      <p className={styles['supportLabel']}>{supports.length ? `关联辅助 · ${supports.length}` : '未配置辅助宝石'}</p>
      {supports.length ? <ul className={styles['supportGems']}>{supports.map((gem, index) => <li key={index}>{poe2Term(gem.name, 'gem')}<small>{gem.level} 级</small></li>)}</ul> : null}
      {unknown.length ? <ul className={styles['supportGems']}>{unknown.map((gem, index) => <li key={index}>{poe2Term(gem.name, 'gem')}<small>{gem.level} 级 · 类型未标记</small></li>)}</ul> : null}
    </article>
  })}</div>
  return <section aria-label="技能搭配"><h3>技能搭配</h3><p>来自导入构筑当前技能方案中已启用的技能与宝石。</p>
    {configured.length ? cards(configured) : <p>当前方案没有已启用的技能搭配。</p>}
    {granted.length ? <details className={styles['grantedSkills']}><summary>装备与天赋授予技能 · {granted.length}</summary>{cards(granted)}</details> : null}
  </section>
}
