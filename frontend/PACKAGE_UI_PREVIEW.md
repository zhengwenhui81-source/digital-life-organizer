# Package Fixture 前端

独立合成数据验收页，不调用模型、AgentAPI、Package HTTP 或文件操作接口。正式审批始终禁用；风险复选框只记录本地 UI 意向，不生成 preview_id 或服务端批准事实。

## 打开页面

直接在本机浏览器打开 `frontend/package-preview.html`（file URL），无需运行后端。
也可以使用已有静态服务器访问该文件；本阶段不要提交真实任务。

## 模块与数据

- `PackagePreview.render({planResult,snapshot,report})` 返回已转义 HTML，`inspect` 返回展示检查结果；不改变输入，不读取 Fixture，不执行审批。
- planResult 接收 `plan_package` ToolResult 的 `data.{plan,plan_sha256}`。展示唯一冻结 manifest，不构造第二套公共数据结构。
- snapshot 接收 TaskSnapshot；未来通过契约定义的 `package_execution` 的 operation_results/result_index、final_result_index 关联原始 results，禁止回退查找旧成功。
- report 接收 FinalReport；非 Package 可省略 package_unresolved。Package 必须提供与冻结方案一致的结构化风险；验证/执行关联不足时不声称成功。
- `package-fixtures.js` 仅包含虚构路径、ID、摘要和工具事实。摘要为合成占位值，不声称密码学验证通过。
- `package-demo.js` 管理场景及本地确认；场景、plan_id、摘要或方案内容变化均重置意向。
- 缺失任务、无效操作或结果记录显示数据不完整提示，并保留原始执行记录；未决来源索引必须与当前成功分析关联，否则保留原始风险并提示“未决事项来源关联无效”。本地风险意向不能消除这些警告。
- 展示诊断核对报告 status、完整任务 task_id/user_goal/workspace、verification_targets 的有序选材覆盖，以及每次已尝试复制的 cleanup_results。记录缺失、重复、来源不匹配或结果矛盾时，不显示文件验证通过；原始失败和残留记录继续展示。
- stale_success 中历史成功与当前失败使用不同方案身份；插入历史结果时同步调整当前分析、未决事项、子操作及最终结果索引，测试直接核对关联，不依赖场景文案。

Package schema 依据已合并 PR #29 和 PR #36；`cleanup_results` 四字段结构及安全记录规则已确认，但 Package Snapshot、审批、执行及清理能力均尚未实现。A 仍需完成分析来源重读、字节摘要复验及同次预览绑定。读取原始字段不构成支持实际执行的声明。前端检查仅用于保守展示，不能代替后端完整校验、摘要验证和授权。

## 本地检查

```powershell
node --test frontend/tests/package-preview.test.cjs frontend/tests/agent-results.test.cjs frontend/tests/agent-workspace.test.cjs frontend/tests/organization-preview.test.cjs
node --test frontend/tests/package-browser.cjs
```

浏览器检查使用本机 Chrome 和 Node 自带 WebSocket；可通过 CHROME_PATH 指向已有 Chrome/Edge，无需安装依赖。仅在系统临时目录建立隔离浏览器配置，结束后移除该配置；不操作任务 Workspace。CDP 只连接本机调试 WebSocket，测试页面使用 file URL，阻止并检查任何 HTTP(S) 请求。测试不访问外网。

## 人工浏览器验收

1. 打开页面，确认醒目的 Mock/Fixture 标识和禁用的正式审批按钮。
2. 选择 complete：核对目标、ID、摘要、文件源/目标、大小、依据、冻结操作和报告。多候选证据包含两个引用，但选材仍只是提议。
3. 选择 risks：逐项查看 missing 与四类未决事项；勾选风险意向，确认文案仅表示本地意向。切换场景后确认复选框清空。
4. 选择 success：缺项与风险仍保留；执行成功和文件验证不表示材料审核通过。
5. 选择 partial、cleanup_failed、unknown_residual：观察已成功操作、失败原因、清理记录与未知残留；不显示回滚保证。
6. 选择 bad_index、mismatch、missing_unresolved、stale_success：确认来源警告，不能回退到旧成功。
7. 选择 missing、null、empty、wrong_type、long、non_package：确认页面不崩溃、空与未知分离；390px 宽度不产生横向页面溢出。
8. 所有场景中正式审批始终禁用，开发者工具 Network 中没有 HTTP/API 请求。

## 第一阶段集成准备边界

本阶段只增强独立展示模块、合成数据和离线测试。没有改动生产 Agent 页面、HTTP transport 或后端；正式 Package 审批仍始终禁用。展示诊断不是后端完整 schema、源文件所有权、字节摘要或批准状态的校验。

- `partial` / `stale_success` 为每次已尝试复制保留一条清理观察：成功复制为 not_attempted/copy_succeeded/absent；第二次复制在创建目标前失败，为 not_attempted/absent。成功文件仍保留，失败任务没有 FinalReport。
- `cleanup_failed` 表示后端已安全绑定失败片段，获准进行的移除尝试失败；`unknown_residual` 表示所有权无法确认，未尝试移除。前端只呈现这些合成事实，不推断所有权或执行清理。
- `invalid_cleanup` 故意缺少第二次复制的清理记录，应出现关联不完整警告。bad_index、mismatch 等仍是独立的畸形数据测试，不是正式响应样例。
- `stale_success` 注入历史成功污染用于防回退测试，不代表契约支持失败任务恢复或历史结果导入。当前任务的分析、子操作及最终失败索引保持一致，不能被历史记录覆盖。

### 纳秒整数精度

普通 Fixture 使用小的合成整数 `mtime_ns=123456789`，仅用于可精确表示的展示基线，不代表真实文件时间。独立 `unsafe_timestamp` 场景保留常见大数值并展示精度警告，不能显示文件验证通过。

契约的 mtime_ns 仍是整数；没有改成字符串或新增字段。JavaScript 普通 JSON.parse 可能把不同的超安全范围整数解析为相同 Number，本模块不会用这种相等证明来源一致。结构比较遇到不安全整数也保守判定不能确认相等，不会修改或自动修复输入。

这不是无损 JSON transport 的实现，也不表示后端方案无效。真实接入前仍须与 A/D 确认无损整数展示/关联策略、当前 preview 与冻结 manifest 的绑定、accept_incomplete HTTP 行为、执行索引及 cleanup/FinalReport 的实际支持。浏览器不重算规范摘要、不复验真实文件、不替代服务端授权。

Chrome 回归覆盖 18 个 Fixture、1366px / 390px 两种宽度及 8 组异常组合；同时检查无页面异常、无 HTTP 请求、输入不变、HTML 转义、切换后确认清空和正式审批禁用。这些检查不构成 LLM、真实 Package 或 Windows 离线五场景的人工验收记录。

## 真实接入依赖

等待 D 实现/导出冻结计划和报告，A 注册工具并实现当前 task/plan/digest/preview 绑定、风险接受、单次执行和结果索引关联、清理记录及成功 FinalReport 映射。未来只向展示模块提供真实对象；当前没有 plan_package/build_package HTTP 调用。approve 的 accept_incomplete 增量未接入，也不改变现有 Real Mode。失败任务保持 Snapshot 诊断，报告 409 不降级为普通成功。Matching/Version 和现有 Agent UI 未改动。
