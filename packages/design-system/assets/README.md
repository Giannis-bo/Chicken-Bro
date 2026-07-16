# Current Runtime Assets

`vector/` 只包含当前源码依赖的功能性 utility icon。它们可以支撑交互和 fallback，但不构成 canonical target 的设计素材，也不拥有跨路由视觉复用权。

`raster/news-home-v1/` 包含 `news_home` 的 33 个具名候选素材、5 个 source master、1x/2x runtime、manifest 与 generation record。它们必须保持 manifest 的候选状态，直到独立素材复核和整页 target/runtime 复核都通过；构建只复制 `runtime/2x/`，不会把 master、1x 或生成记录打进运行包。

Production asset registry 当前为空。目录存在、素材数量、生成任务自检或 H5 成功加载都不能自行晋级 production；晋级仍由当前 route asset contract、独立视觉复核和人工验收共同决定。
