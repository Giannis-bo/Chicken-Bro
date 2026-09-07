# 更新日志关闭按钮对齐（2026-09-07）

用户报告叉号窜行。浏览器测量发现原按钮中心比标题中心高 14.703125px，文字叉号所在行框高 38.3984375px，中心比 36px 按钮低 2.19921875px。改为标题行网格对齐，并用 18px SVG 叉号取代字符 ×。

- 8 项现有交互回归、类型检查、改动文件 ESLint、测试 H5 构建和 diff check 通过；构建保留两项体积警告。
- Chrome 桌面及 390px 实测：标题与按钮中心 Y 偏差均为 0；SVG 与按钮中心 Y 偏差均为 0，桌面 X 偏差为 0。关闭按钮点击后返回 FAQ，视口恢复。
- 测试 Web 构建 `b6c7878dfa15b466f3f8888663068f73677cc40f1d9a89333ae0461d8b5cfc7e`；21 项部署文件逐项核验，公网 index.html、js/app.js、css/app.css SHA 与本地构建匹配。源码/产物 SHA 见 `web-changelog-close-manifest.json`。
- 仅更新测试静态 Web；没有生产部署、数据库写入或服务重启。上版静态页面保留 `/opt/chickenbro-test/web-updates/b6c7878dfa15/web`，回退前核对该目录与 previous-manifest.json 以及当前新 manifest，再反向原子交换。
- 源码尚未提交/推送；本次页面修复待用户体验确认。
