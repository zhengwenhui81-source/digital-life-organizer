> 当前正式 Agent 的接入与实测状态见 [Package Real Mode 集成记录](PACKAGE_REAL_INTEGRATION.md)。下文各阶段的“尚未接通/未实现”是历史基线；独立 Fixture 页面仍始终禁用正式审批，不调用真实 API。

# Package Fixture 前端

独立合成数据验收页，不调用模型、AgentAPI、Package HTTP 或文件操作接口。正式审批始终禁用；风险复选框只记录本地 UI 意向，不生成 preview_id 或服务端批准事实。

正式 Agent 页现已复用同一展示模块读取 TaskSnapshot，详见下方“正式页面只读预览”；独立 Fixture 页仍仅用于合成数据测试。

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

D 的 plan_package 已通过 PR #35 合并；A 的 PR #40 已提供 accept_incomplete 请求解析和当前不可执行的审批防护。默认 Agent 路由尚未注册 plan_package，仍待 A 实现规划证据到当前 preview 的集成、复合执行、结果索引关联、清理记录及成功 FinalReport 映射。前端未接通 accept_incomplete 或 Package 执行，也没有 plan_package/build_package HTTP 调用。失败任务保持 Snapshot 诊断，报告 409 不降级为普通成功。公共契约部分“未实现”基线文字可能早于这些提交，本说明以实际代码区分已合并能力和剩余阻塞，不修改公共契约。

## 正式页面只读预览

基线：dev `a0267e8`（PR #35 / #40 / #42 已合并）。生产 index.html 仅新增加载纯展示模块 package-preview.js，不加载 package-fixtures.js 或 package-demo.js。

- 数据入口仍为现有 GET /api/agent/tasks/{task_id}；不新增请求或端点。renderSnapshot(snapshot, expectedTask) 从当前 results 选择最后一次 plan_package，显示其 result_index、task_id、plan_id、plan_sha256 以及同一 Snapshot 的 preview_id，再复用 render 展示冻结映射、提议依据、风险、缺项和报告。
- 无 plan_package 且 Snapshot 格式正常时显示“真实 Package 规划数据尚未提供”。缺少 results/task、当前 ToolResult 格式异常或当前 manifest 不完整，另行显示数据诊断；不以 Fixture 填补。Mock Mode 不向此区域提供真实规划。
- 创建任务响应中的 task_id/user_goal/workspace 保存在本地视图上下文，仅用于响应归属比较；新任务和模式切换清空。跨任务 manifest 不显示映射；最新规划失败、当前任务/工具失败、规划后出现新分析/文档读取时，不回退展示旧成功方案。字段异常和不安全整数延续保守诊断，输入不被修改。
- preview_id 仅按服务端返回展示，不由前端生成，也不证明其已经权威绑定当前 manifest。规划成功但尚未提供审批预览时只显示只读规划；等待审批却缺 preview_id，或已有 preview_id 却无 pending_operations，均提示绑定无法确认。
- Package 批准仍由页面按钮和事件处理器双重阻塞，未增加风险接受或执行交互；普通 Agent 的 approve/reject、轮询、报告和过期响应防护保留。

测试中的 HTTP JSON 和 Fixture 都是明确的合成输入，用于验证生产页的数据映射及保守展示，不是后端或真实 LLM/Package 验收。当前仍缺 A 实际产生并绑定的规划 Snapshot、真实执行适配器及成功报告的验收证据，亦未解决无损纳秒整数传输。

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

上述补审阶段未同步 PR #44；其合并后的共同组件整合见下节。真实后端契约验收仍待进行。

补审修复实际回归：四文件 Node 测试 92 通过、0 失败，exit 0；已安装 Chrome 本地测试
1 通过、0 失败，exit 0（22 Fixture × 两种宽度、8 异常输入、2 失败链及 5 验证/报告场景；
无 HTTP 请求、无页面异常或横向溢出，正式批准禁用）。三个修改 JS/CJS 语法和 diff 空白检查通过。
六组新增 Node 测试覆盖 C 的原始复现、工具失败及 passed=false、重复/缺失/错误验证关联、
报告完整来源比较和过期/错误来源、显式未执行冲突分析正向场景与风险被擦除反例。

## 与已合并 PR #44 的整合

本轮普通 merge 基线为 dev `6c12c979c887a9cde4e495ceb9f41a6c9df2a580`，保留 #45 历史，不修改 #44 开发分支。
冲突为本说明、package-preview.test.cjs、package-browser.cjs 的追加段落；保留两边测试与说明，采用 dev 已更正的依赖段落，浏览器汇总包含两边场景。package-preview.js 自动合并后逐段复核，无删除任一套适配器/证据逻辑。

- 正式 renderSnapshot 仍只在 inspectSnapshot.state=provided 时调用详细 render；invalid/failed/unavailable 不渲染映射或原始执行正文。规划、任务、来源、索引及 preview 缺失保护不变，不用历史或 Fixture 补齐。
- 独立 inspect/render 保留执行进度、失败停止、异常验证、报告来源与未决风险核对、cleanup 诊断和完整成功链检查。正式 Snapshot 入口的执行证据异常同样触发详细展示保护；不能用独立 Fixture 诊断规则绕过正式入口。
- 正式页面仍未接通 Package 批准或成功 FinalReport；没有报告时不能由 Snapshot 自行生成 Package 成功。组件可接收原始 FinalReport 的展示能力保留，不放宽普通 Agent 的报告/审批/拒绝/轮询保护。
- 新增组合单测覆盖正式入口的 executing/verifying、无报告的完成 Snapshot、较新失败验证、失败复制、未知 cleanup 以及生产页面审批禁用与映射撤回。真实 API、文件操作、来源摘要和审批权威性仍由 A 负责。

Windows 验收准备文件在独立 #46 分支保存，不在本 PR 差异中；本轮不修改、删除或重新暂存这些文件。

本轮整合实际运行：`node --test frontend/tests/package-preview.test.cjs frontend/tests/agent-results.test.cjs frontend/tests/agent-workspace.test.cjs frontend/tests/organization-preview.test.cjs` 为 110 passed、0 failed、exit 0。
`node --test frontend/tests/package-browser.cjs` 为 1 passed、0 failed、exit 0；覆盖 22 Fixture × 两种宽度、8 异常输入、2 失败链、5 验证/报告、4 Snapshot 保护及 3 组合状态，无 HTTP 请求、页面异常或横向溢出。
package-preview.js、package-fixtures.js 和三个相关测试 CJS 的 `node --check`，以及相对最新 dev 的 diff 空白检查通过。测试均为合成展示/HTTP 响应回归，不是实际后端 Package 或 LLM 验收。

## null/not-run 与真实分析记录一致性修复

在集成 HEAD `9ba13065d7c4dabf0c10cafbf98f679e0a4bc947` 重跑 C 的 Version/Conflicts 两种反例，均能复现错误成功。
现统一由 analysisNotRun 检查冻结槽为 null 且当前 Snapshot 中没有同名工具记录。
只要存在该工具调用（包括成功空结果、失败或畸形记录），就不能以 analysis_not_run 擦除执行历史。
矛盾会诊断“分析来源矛盾”，对应 reportSources 保持 null，Package 成功判定为 false，正式 Snapshot 入口为 invalid，不展示详细映射。
不从历史记录自动恢复分析槽、修复索引或重新计算摘要；原始输入不变。真正无该工具记录、显式冻结未决风险且报告完整保留风险的合法不完整方案仍可展示执行结果，authorizationConfirmed=false，正式批准禁用。
本轮不再次 merge、不撤销冲突解决，不修改 A/C/D 或公共契约。新增两个工具各自的矛盾/合法正向单测，以及空/失败/畸形记录反例和四个浏览器 not-run 场景。

本轮实际结果：既有四组 Node 回归 115 passed、0 failed、exit 0；Chrome 1 passed、0 failed、exit 0（保留全部整合场景，另加四个 not-run 场景，无 HTTP/页面异常/溢出）。五个相关 JS/CJS 的语法检查及 diff 空白检查通过。以上是合成输入展示回归，不是实际 Package 执行或材料验收。
