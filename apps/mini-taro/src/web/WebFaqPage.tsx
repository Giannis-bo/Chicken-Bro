import { useEffect, useRef } from 'react'

import { isTestLoginEnabled } from '../features/auth/test-login-mode'
import styles from './WebFaqPage.module.scss'

type FaqItem = { question: string; answer: string; prompt?: string }
type FaqGroup = { title: string; description: string; items: FaqItem[]; note?: string }

const groups: FaqGroup[] = [
  { title: '认识鸡哥', description: '你的魔兽世界讨论搭子', items: [
    { question: '鸡哥是谁？', answer: '鸡哥是使用 GPT-Astra 模型的魔兽世界助手。你可以和鸡哥聊副本、装备、天赋与输出手法，也可以发来角色或战斗日志链接，一起查资料、复盘战斗，或通过对话创建和查看云端 Simc 模拟任务。' },
    { question: '怎样让鸡哥更懂我的问题？', answer: '尽量带上职业与专精、游戏版本、团本或大秘境场景，以及角色链接或具体战斗日志。说清楚你想解决什么，例如“先找最值得改的三个地方，用国服技能名解释”。也可以继续追问，让鸡哥解释证据或调整模拟条件。' },
  ] },
  { title: '常见问题', description: '5 个真实案例，看看怎么问', note: '以下根据项目历史会话整理，提问经过简化，结果是当时的分析摘要。版本、装备和战斗条件变化后，需要重新核验。', items: [
    { question: '01 · 血 DK 有了四件套，为什么伤害还是不高？', prompt: '这是我的 WCL 战斗链接：[粘贴链接]。我是血 DK，已经有四件套，帮我确认套装有没有生效，找出最值得改进的地方。', answer: '当时的日志中，“殷红亡殁”造成约 466 万伤害、命中 101 次，证明四件套已经生效；约 22.5% 的符能生成被浪费。分析还区分了整场副本与实际战斗时间，优先建议减少符能溢出，再优化套装在怪群中的触发时机。' },
    { question: '02 · 武器战打到 97%，离高手还差在哪里？', prompt: '这是我的纳洛拉克洞穴日志：[粘贴链接]。排名显示 97%，请找同层、相近装等的武器战对比，用国服技能名告诉我手法差距。', answer: '当时先澄清了 97% 是同层钥匙排名，并非全局排名。可比样本秒伤约 27.1 万，自己的约 22.5 万；进一步对比致死打击、英勇打击的施放频率、怒气溢出与附魔情况，给出了按优先级排列的改进建议。' },
    { question: '03 · 先知元素萨一定要优先堆精通吗？', prompt: '我玩先知元素萨，先祖不能触发过载，为什么还推荐精通？请把先祖和本体的收益分开解释，暴击、急速会不会更好？', answer: '当时的分析修正了“精通必然最高”的说法：先祖与本体受益方式不同，不能只看先祖占比就判断全部属性收益，也不存在通用的固定毕业属性线。最终建议结合自己的装备与目标数做个人模拟，而不是照抄属性比例。' },
    { question: '04 · 元素萨四件套选减冷却，还是召唤风元素？', prompt: '我有先知元素萨四件套，主要打约 30 分钟的大秘境。风暴守护者减冷却和召唤风元素，哪个总伤害更高？请在相同装备下对比。', answer: '当时的云端 Simc 在同一模板的 1、3、5 目标持续输出窗口中做了对照，风元素方案约领先 2%–4%。分析同时说明：30 分钟副本计时包含跑图和等待，这些固定目标窗口不能当作完整副本实战，也不是你当前角色的固定收益。' },
    { question: '05 · 密谋小径楼下的怪到底是谁引到的？', prompt: '这是密谋小径日志：[粘贴链接]，请检查第 16 场约 26 分钟楼梯位置，楼下机器人为什么进战？是闪电链还是其他技能？', answer: '当时按事件时间线发现：机器人先攻击邪 DK 新召出的召唤物，约 3.8 秒后火焰符文才命中；此前没有闪电链命中。日志支持召唤物先触发引怪的判断，但具体楼层与寻路原因只能推测，因为位置数据缺少高度信息。' },
  ] },
  { title: 'Simc模拟', description: '导入角色，也能直接对话操作', items: [
    { question: '国服角色怎么导入？', answer: '当前国服不支持英雄榜导入，只能通过 Raider.IO 或 WCL（Warcraft Logs）等公开数据来源导入角色。请在“模拟”中粘贴 HTTPS 的 Raider.IO 角色链接或 WCL 日志链接，格式可以参考提交页示例。当前不支持直接粘贴插件 /simc 导出的文本。' },
    { question: '可以直接让鸡哥控制 Simc 吗？', prompt: '用这个角色链接：[粘贴 Raider.IO 或 WCL 链接]，帮我跑一份 5 目标、300 秒的模拟，然后解释结果。', answer: '可以。你可以通过对话让鸡哥导入角色、设置模拟条件、提交云端 Simc 任务，并查询进度和解读结果；也可以接着说“改成单体再跑一次”。资料齐全后才能提交；任务提交不代表完成，结果以实际任务状态和报告为准。' },
    { question: '怎样用任务 ID 换装备再跑一次？', prompt: '基于模拟任务 [粘贴完整任务 ID]，把第一个饰品换成 [装备链接或物品 ID、装等及具体版本]，其余装备、天赋和战斗条件保持一致，重新跑一次并对比结果。', answer: '在“模拟任务”列表点击“复制 ID”，把完整任务 ID 粘贴给鸡哥并说清要替换的部位和装备。鸡哥会读取当前账号的原任务，核对替换装备的物品 ID、装等、加成、宝石和附魔，再创建新任务；原任务不会被覆盖。装备资料不完整时会先补查或向你确认，运行结束后再比较数值与误差。' },
    { question: '资料不完整或模拟失败怎么办？', answer: '公开来源可能缺少装备、天赋等字段。先根据提示检查链接和缺失信息，补充可用来源后重试；鸡哥不会凭空补齐。失败原因可在任务详情中查看，比较结果时也要核对角色资料、模拟条件与引擎版本。' },
  ] },
  { title: '账号记录', description: '登录、同步与历史管理', items: [
    { question: 'Web 和小程序的记录会同步吗？', answer: '使用同一个微信账号登录后，两端可以查看并继续同一段对话，也能查看同一模拟任务的状态和结果。若记录不同，先检查是否登录了同一账号。' },
    { question: '退出登录会删除记录吗？', answer: '不会。对话和模拟记录仍保留在当前账号下，重新登录同一账号后可以继续查看。Web 与小程序分别登录和退出。' },
    { question: '怎样删除对话？', answer: '在 Web 会话列表中点击对应会话的垃圾桶，确认后该对话会从两端历史列表中移除。若对话正在回复，请等待回复结束后再删除。' },
    { question: '为什么另一个对话提示等待？', answer: '同一账号同时只能有一个正在生成的回复，无论是在 Web、小程序还是其他窗口。你仍可查看历史或新建空会话，等当前回复结束后再发送新消息。' },
  ] },
]

export default function WebFaqPage({ returnLabel, onReturn }: { returnLabel: string; onReturn: () => void }) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    const previousScroll = window.scrollY
    headingRef.current?.focus({ preventScroll: true })
    window.scrollTo(0, 0)
    return () => window.scrollTo(0, previousScroll)
  }, [])
  return (
    <main className={styles['page']} aria-labelledby="web-faq-title">
      <div className={styles['content']}>
        <button type="button" className={styles['back']} aria-label={returnLabel} onClick={onReturn}>
          <span aria-hidden="true">←</span> {returnLabel}
        </button>
        <header className={styles['header']}>
          <span className={styles['eyebrow']}>使用帮助</span>
          <h1 ref={headingRef} tabIndex={-1} id="web-faq-title">FAQ</h1>
        </header>
        {isTestLoginEnabled() ? (
          <div className={styles['testNote']}>你正在使用测试版。选择 A / B 测试账号并输入对应凭证登录，两端请选同一个账号。</div>
        ) : null}
        {groups.map((group, index) => (
          <details className={styles['group']} key={group.title}>
            <summary className={styles['groupTitle']}>
              <span><h2>{group.title}</h2><span className={styles['description']}>{group.description}</span></span>
              <span className={styles['chevron']} aria-hidden="true">⌄</span>
            </summary>
            <div className={styles['answers']}>
              {group.note ? <p className={styles['caseNote']}>{group.note}</p> : null}
              {group.items.map(item => (
                <article key={item.question} className={styles['answer']}>
                  <h3>{item.question}</h3>
                  {item.prompt ? <div className={styles['prompt']}><h4>可以这样问</h4><p>{item.prompt}</p></div> : null}
                  {item.prompt ? <h4>{index === 1 ? '当时得到的结果' : '鸡哥会怎么做'}</h4> : null}
                  <p>{item.answer}</p>
                </article>
              ))}
            </div>
          </details>
        ))}
      </div>
    </main>
  )
}
