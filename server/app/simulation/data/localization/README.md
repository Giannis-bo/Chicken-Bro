# SIMC 国服名称数据

每个目录对应一个精确游戏构建。运行时只读本地 `catalog.json.gz`，先校验 `manifest.json` 中的 SHA-256、构建号和语言；缺失或不匹配时返回明确状态，不请求外部网站。

`SpellName` 的法术编号用于技能和增益，`Creature` 的编号用于可核实的来源，`ItemSparse` 保留物品名称。英文表只产生无歧义的精确别名索引，不能替代已有但未查到的法术编号。无国服翻译的原始条目不作为已匹配名称。

构建命令（使用已经下载并记录 SHA 的 CSV，不下载依赖或启动 SIMC）：

```text
python -m scripts.build_simc_localization_catalog <已下载CSV目录> server/app/simulation/data/localization/<游戏构建>
```

源目录包含 `manifest.json` 及五个 CSV：`SpellName.zhCN`、`SpellName.enUS`、`Creature.zhCN`、`Creature.enUS`、`ItemSparse.zhCN`。来源清单必须记录精确构建 URL、响应文件名及内容摘要。引擎自动攻击等内部统计项由 `engine-rules.json` 定义，并绑定源码提交；这些内部编号不能冒充游戏法术编号。历史名称规则保留先前已核实的名称，始终标记历史身份不足。

当前 `12.1.0.69299` 的数据表不是完整的服务器 NPC 名称集合；未包含的召唤物保持来源未匹配。不得把当前网站查到的名称伪装成该构建的已验证 NPC 名称。

更新流程：生成新目录 → 检查数据及来源摘要 → 对受管云端引擎运行专精/配置矩阵 → 分开记录匹配、缺项与模拟失败 → 隔离测试验证 → 按项目发布范围推进。旧目录用于旧报告；不写回历史任务，不重跑模拟替换原始结果。覆盖工具及本次结果见 `scripts/verify_simc_localization_matrix.py` 和 `artifacts/releases/2026-09-06-simc-workbench/localization-coverage.json`。
