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

本阶段增强独立展示模块、合成数据和离线测试，并为现有 Agent 页的异步报告、审批及轮询补齐 generation/task_id/mode 防护。没有改动 HTTP transport 或后端；正式 Package 审批仍始终禁用。展示诊断不是后端完整 schema、源文件所有权、字节摘要或批准状态的校验。

- `partial` / `stale_success` 为每次已尝试复制保留一条清理观察：成功复制为 not_attempted/copy_succeeded/absent；第二次复制在创建目标前失败，为 not_attempted/absent。成功文件仍保留，失败任务没有 FinalReport。
- `cleanup_failed` 表示后端已安全绑定失败片段，获准进行的移除尝试失败；`unknown_residual` 表示所有权无法确认，未尝试移除。前端只呈现这些合成事实，不推断所有权或执行清理。
- `invalid_cleanup` 故意缺少第二次复制的清理记录，应出现关联不完整警告。bad_index、mismatch 等仍是独立的畸形数据测试，不是正式响应样例。
- `stale_success` 注入历史成功污染用于防回退测试，不代表契约支持失败任务恢复或历史结果导入。当前任务的分析、子操作及最终失败索引保持一致，不能被历史记录覆盖。

### 纳秒整数精度

普通 Fixture 使用小的合成整数 `mtime_ns=123456789`，仅用于可精确表示的展示基线，不代表真实文件时间。独立 `unsafe_timestamp` 场景保留常见大数值并展示精度警告，不能显示文件验证通过。

契约的 mtime_ns 仍是整数；没有改成字符串或新增字段。JavaScript 普通 JSON.parse 可能把不同的超安全范围整数解析为相同 Number，本模块不会用这种相等证明来源一致。结构比较遇到不安全整数也保守判定不能确认相等，不会修改或自动修复输入。

这不是无损 JSON transport 的实现，也不表示后端方案无效。真实接入前仍须与 A/D 确认无损整数展示/关联策略、当前 preview 与冻结 manifest 的绑定、accept_incomplete HTTP 行为、执行索引及 cleanup/FinalReport 的实际支持。浏览器不重算规范摘要、不复验真实文件、不替代服务端授权。

Chrome 回归覆盖 22 个 Fixture、1366px / 390px 两种宽度及 8 组异常组合；同时检查无页面异常、无 HTTP 请求、输入不变、HTML 转义、切换后确认清空和正式审批禁用。这些检查不构成 LLM、真实 Package 或 Windows 离线五场景的人工验收记录。

### 真实入口的受控阻塞

Agent 页识别 Snapshot 中显式的 Package 工具/执行记录后禁用批准，事件处理器也阻止发送批准请求；现有 reject 仍仅提交 preview_id。若真实响应带 Package 路径或结构化风险，普通 FinalReport 渲染器不将其降级为已验收的 Package 成功。Mock 流程不受此阻塞影响，生产入口不加载 Package Fixture 数据。

报告和审批响应、错误、409 状态刷新及 finally 均检查请求的 generation/task_id/mode；报告额外绑定发起读取时的 Snapshot 对象，避免同一任务较新的失败快照被旧报告覆盖。不自动重试审批，不新建轮询并发，也不将这些前端检查当成服务端授权。

| 阶段 | 沿用接口及数据 | 仍待 A/D 完成或确认 |
| --- | --- | --- |
| 预览 | GET /api/agent/tasks/{task_id}，results 中 plan_package 的 data.{plan,plan_sha256}，同一 Snapshot 的 pending_operations/preview_id | A 保证当前预览与 D 冻结 manifest、来源重验和任务归属一致；不按旧成功结果补齐 |
| 批准/拒绝 | 现有 POST approve/reject；本阶段 Package 批准阻塞，reject 仍仅 preview_id | A 实现并验收 approve 的 accept_incomplete 增量；同预览风险接受不能产生独立授权 |
| 执行/失败 | GET Snapshot 的 package_execution 与 results 原始索引；失败不取成功报告 | A 提供实际子操作、终止结果及每次复制的 cleanup_results；失败报告 GET 保持 409 |
| 成功报告 | 现有 GET report；未来复用展示模块的 Snapshot/manifest/FinalReport 输入 | A 保留冻结 missing/package_unresolved/conflicts 并绑定当前验证成功执行；D 保证冻结报告及快照；A/D 明确无损整数策略 |

这些是现有契约的数据映射和阻塞说明，不是新 API，也不是已接入能力。没有 plan_package/build_package HTTP 请求、前端文件整理、权威哈希计算或客户端批准凭据。

## 真实接入依赖

等待 D 实现/导出冻结计划和报告，A 注册工具并实现当前 task/plan/digest/preview 绑定、风险接受、单次执行和结果索引关联、清理记录及成功 FinalReport 映射。未来只向展示模块提供真实对象；当前没有 plan_package/build_package HTTP 调用。approve 的 accept_incomplete 增量未接入，也不改变现有 Real Mode。失败任务保持 Snapshot 诊断，报告 409 不降级为普通成功。Matching/Version 和现有 Agent UI 未改动。

## 执行结果展示准备（与 PR #44 独立）

基于 dev `a0267e84a4ace9dd8af470c61bc5ae5a44697681`，不包含或修改仍在审查的 PR #44。此轮复用 inspect/render 原有输入签名 `{planResult,snapshot,report}`，没有改动生产 index.html、Agent transport、审批或轮询。新增的 operationRows、cleanupRows、executionLabel、packageSucceeded 仅为组件内部展示投影，不是公共 Task 状态或响应字段。

- 在冻结操作顺序中逐项展示已关联结果、源/目标路径、错误及原始 ToolResult；失败 data=null 时路径明确来自冻结映射，不代表复制完成。每个已返回工具结果不等于字节进度。
- `executing` / `verifying` 是既有 Task 状态。没有逐文件 running 信号时显示“尚无完成结果，无法确认是否已开始”；没有执行关联且任务尚未执行时显示未执行。失败子操作及最终失败已关联后，后续无结果步骤显示失败后停止；证据不完整时保持未知，不静默当作成功或跳过。
- cleanup 按 step_id 关联已尝试复制。succeeded 只表示失败复制片段已移除；failed 保留原始复制失败与清理原因；unknown 不推断对象已删除。absent 不表示成功文件或目录已回滚。重复/未知步骤与矛盾清理记录保留原文，标为关联无效。
- 只有当前任务 completed、当前有效规划/执行绑定、全部子操作和验证证据一致、完整 Package FinalReport 保留冻结风险时，显示 Package 执行与文件验证成功。没有 FinalReport 时不确认 Package 完成。验证调用返回 success=true 但 passed=false 仍是验证未通过。
- 较新 plan_package/build_package、跨任务、异常或非递增索引、生成文件/报告路径不符、必要报告字段缺失均禁止确认成功；不从旧成功搜索补齐。独立失败 ToolResult 仍作为诊断保留，不因正向证据失效而丢弃原始失败。

新增合成场景：executing（只返回目录操作）、verifying（写操作已返回，验证尚无结果）、verification_failed（复制成功但验证失败）、cleanup_succeeded（失败片段移除成功，任务仍失败）。它们只描述约定数据，不执行复制或清理，也不是已存在后端能力的声明。

### 必须等待 A 的后端清单

以实际代码为准：D 的只读 plan_package 已通过 PR #35 合并；PR #40 已有 accept_incomplete 解析和执行不可用防护。仍待 A 完成默认工具路由/TaskService 规划接入，当前 task/plan/digest/preview 的权威绑定，受批准约束的复合执行、按序追加子结果与唯一 final_result_index、每次已尝试复制的 cleanup_results、批准源摘要/冻结报告/精确文件集的实际验证，以及成功 FinalReport 映射和失败报告 GET 409。前端不补造任何接口或事实。

本轮不接通这些真实接口；未来只传入 A 的原始 Snapshot 与报告即可复用展示。实际文件验证、无损纳秒整数传输和真实 HTTP/Package 验收仍待后续工作，当前合成测试通过不能替代它们。
# PR #45 执行证据修复

有效子操作首次失败后，后续子结果仅保留为“失败后异常记录，不可作为有效执行证据”。
它们不进入 boundOperations、writes 或 verification；异常成功 build_package 不进入 build。
合法的最终失败 build_package 仍保留原始错误。逐步展示以 evidenceValid 区分原始诊断和有效执行记录，不能将异常 success=true 标为文件操作执行成功。
异常复制的 cleanup_results 原样保留但不确认其关联或清理成功；前端不推断实际文件状态，也不执行清理。
最终成功还要求完整、按序、有效且全部成功的子链、当前验证、任务和 FinalReport。

本轮回归：四文件 Node 回归 86 通过、0 失败（exit 0）；Chrome 沙箱内首次启动超时，
该次未完成、不计通过。获准在沙箱外重跑本地浏览器后 1 通过、0 失败（exit 0），
覆盖 22 Fixture × 两种宽度、8 组异常输入和 2 条失败执行链；零 HTTP、正式审批禁用。
新增四组 Node 回归直接断言可信集合、逐步 evidenceValid、原始错误、异常验证/构建隔离、
cleanup 诊断、输入不可变及完整合法成功链。上述仅为合成展示测试，不是实际 Package 执行验收。

## C 补审：验证时序与报告来源

- 规划之后的 verify_result 必须唯一关联冻结 verify 步骤；额外、重复或范围无法归属的验证不作为重试。旧验证与异常新记录原样保留诊断，旧验证移出可信集合，成功构建也不能再充当有效证据。不会用最后一个成功结果填补缺失关联。
- found_files 按当前 Snapshot 的规划前成功 list_files/files、search_files/matches 收集，保持后端发现顺序及首次路径去重语义，并比较完整记录；同路径冲突、失败、缺失或规划后出现新发现使来源不能确认。路径仅用于既有去重，不能代替内容比较或后端来源认证。
- version_groups 和 conflicts 绑定冻结 analysis 的工具、数值索引、完整结果和当前 Snapshot；过期或内容不符时报告不确认。这里不计算文件摘要或重新分析，也不替代 A 的权威任务来源验证。
- null/not-run 分支必须有对应 analysis_not_run 冻结未决项，报告必须保留完全一致的 package_unresolved 和不完整摘要。此时 conflicts=[] 只表示没有可报告的已确认分析结论，不是“已分析无冲突”。没有风险记录、风险被报告擦除或缺少分析槽位仍会拒绝成功判定。
- authorizationConfirmed=false 仅为内部展示投影；没有新增公共字段或批准事实。不从完整/不完整展示、本地风险勾选推断审批有效，正式批准仍禁用。

PR #44 合并后的共同组件整合和真实后端契约验收仍待进行，本次不提前同步或修改其分支。

补审修复实际回归：四文件 Node 测试 92 通过、0 失败，exit 0；已安装 Chrome 本地测试
1 通过、0 失败，exit 0（22 Fixture × 两种宽度、8 异常输入、2 失败链及 5 验证/报告场景；
无 HTTP 请求、无页面异常或横向溢出，正式批准禁用）。三个修改 JS/CJS 语法和 diff 空白检查通过。
六组新增 Node 测试覆盖 C 的原始复现、工具失败及 passed=false、重复/缺失/错误验证关联、
报告完整来源比较和过期/错误来源、显式未执行冲突分析正向场景与风险被擦除反例。
