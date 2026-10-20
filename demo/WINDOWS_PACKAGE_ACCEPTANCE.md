# Windows 真实 Package 联调准备记录

准备基线：`99aa3062637e9ec32a58557c2c7f19de17188c4f`（origin/dev，包含 PR #41）。
本记录是测试设计，所有真实 Package 场景均为 **blocked / 未执行**，不是验收通过证明。
本轮不启动服务、不发 HTTP/LLM 请求、不读取课程正文、不创建模拟课程材料或执行 Package。
不修改 #43/#44/#45 的文件。开始实际验收前必须重新记录已合并 HEAD，不能沿用此基线的结论。

## 已有能力与复用入口

| 入口 | 已有用途 | 不证明的能力 |
| --- | --- | --- |
| `demo/run_offline_browser.py`、`demo/OFFLINE_BROWSER.md` | 固定 Planner、临时 Workspace、真实只读 HTTP；mixed / no_candidates / no_requirements / read_failure / empty 五场景 | 非真实 LLM、无真实 Package 执行；本轮未重新运行 |
| `frontend/tests/offline-browser-smoke.py`、`offline-startup-smoke.py`、`offline-browser.cjs` | 离线 HTTP、启动及浏览器回归 | 不证明 Package 审批或复制；不得把历史记录作为本轮结果 |
| `frontend/tests/package-preview.test.cjs`、`package-browser.cjs` | 合成 Package 展示、异常和隔离回归 | Fixture 不是真实 Snapshot 或执行证据 |
| `tests/test_package_planning.py`、`test_package_paths.py`、`test_package_report.py` | D 的规划、路径和冻结报告单元测试 | 不证明 A 的组合审批执行链路 |
| `tests/test_agent_package_approval.py`、`test_agent_package_evidence.py` | 审批输入、来源重验及证据辅助逻辑 | 不证明当前注册了可执行的 Package 流程 |
| `tests/test_package_evidence_freshness.py`、`docs/document-package-acceptance.md` | C 的读取变化、中文路径和跨层证据边界 | 不替代批准后的 A 重验及 Windows 全链路 |

当前默认 ToolRouter 没有注册 `plan_package`、`build_package`、`write_package_report`。
`TaskService.decide` 存在 `Package execution is not available` 拒绝执行路径。
这些是源码静态事实；不能根据 TOOL_RISKS 中存在工具名推断其已可调用。
#43 来源证据、#44 真实只读预览、#45 执行展示仍需各自独立审查及整合，不能修改其分支替代整合。
以实际合并状态为准，API_CONTRACT 中的设计描述不等于已实现。

## 22 文件逐项清单

清单位于 `demo/package_acceptance/course-materials-22.json`，22 行均为 **待提供**。
slot 仅是本地验收行号，不是 Document.file_id。文件名、扩展名、类型、可读取性、预期处理方式均为 null。
本轮检索 demo、tests、frontend、docs 和 TASKS 未找到 22 文件课程清单。
`demo/sample_workspace` 有 9 个既有示例文件，不是本次课程材料，不能扩充或替代清单。
Fixture 场景数量也不是文件数量。实际文件已检查数 **0/22**。

收到授权目录后，仅先盘点第一层文件，不跟随符号链接或 reparse point；逐行填写真实相对文件名、观察到的扩展名和文件类型。
再按 C 的 `read_document extraction scope` 记录实际读取结果及脱敏错误，不能根据扩展名或文件名推断正文、有效性或材料匹配。
TXT / PDF 文本层 / DOCX 正文段落及表格 / XLSX 缓存单元格分别受提取范围约束；扫描 PDF、图片、公式计算及未支持格式不得标记已完整读取。
预期处理方式只能在真实类型和读取证据确认后填写，例如支持范围内分析、需人工补充、阻塞；不能预填预期分析结论。

当前动态候选读取上限 `_MAX_CANDIDATE_READS=10`。22 文件盘点不等于能在一个任务中分析全部文件。
该上限的准确含义、计数范围及适用阶段尚待 A 确认，不能仅凭常量名推断为全 Workspace 文件上限或已检查数量。
超过限制而没有实际检查的文件必须保留“未检查/待提供”状态；不得静默跳过、填入推测结果或宣称 22 文件验收通过。
必须由 A 确认正式候选选择/批次策略和契约限制；B 不截断、不跨任务拼接结果、不自行改变 Version/Document 配额。

## 进入真实 Windows 验收的门槛

1. A 提供已合并的规划、来源重验、冻结预览、组合审批执行、失败清理及验证适配器；默认路由与 API_CONTRACT 对齐。
2. D 确认冻结计划和报告、操作顺序、源快照与实际结果契约；A/D 共同确认 cleanup_results 的实现状态。
3. B 的正式只读/执行展示 PR 完成独立审查；正式 Package 批准按钮在后端契约验收前继续禁用。
4. 提供 22 文件的授权测试来源。实际执行只能在新建、隔离、可丢弃的测试 Workspace 中使用经授权的副本；保留原始来源不动。
5. 明确测试操作授权和安全注入方式。复制/清理/验证故障须使用 A 已有或确认的测试注入点；没有注入点则 blocked，不改生产代码、ACL、系统配置或真实文件来制造故障。
6. 记录环境和基线，确认本次服务 PID、端口和实际代码；不结束其他服务、不安装依赖、不调整网络。固定 Planner 测试与真实 LLM 测试分别记账。

现有 API 入口应复用 `/api/agent/tasks` 的创建、Snapshot、审批、拒绝和报告路由，具体方法与 payload 以 API_CONTRACT 及已合并路由为准。
不创建独立 Package 执行接口，不直接调用文件工具绕过 Approval Gate。不存在的接口保持 blocked。
每次操作都核对当前 task_id、preview_id、plan_id、plan_sha256 及当前规划/执行结果索引。
审批只能提交当前 preview_id；有冻结缺项/未决时单独提交布尔 accept_incomplete，不在前端生成批准事实。
用户拒绝不能携带 accept_incomplete。前端不计算权威摘要、不自动修复索引。

## 场景矩阵

以下每项都保存“通用证据包”，并补充最后一列。执行顺序为独立任务、独立目标目录；失败场景不自动重试或复用批准。

| 场景 / 当前状态 | 输入条件 | 操作步骤（将来授权后） | 可观察结果与通过标准 | 补充失败证据 |
| --- | --- | --- | --- | --- |
| 正常 / blocked | 可读且有依据的完整选材，无未决，独占新目标 | 创建任务→读规划→核对映射→批准当前预览→轮询→报告 | 批准前零写入；顺序为建目录/复制/冻结报告/验证；所有预期操作与最终验证成功；报告仍不宣称材料真实有效 | 冻结映射、实际成功操作、目标文件集合与验证证据 |
| 缺失材料 / blocked | 实际要求分析产生 missing，不用名字臆造要求 | 读取预览；先不接受风险尝试审批 | 明示 missing；默认审批 409、预览仍待批、零写入；绝不把缺失解释为空风险 | missing 原项、409、前后 Snapshot 与目标状态 |
| 版本未决 / blocked | 有有效 Version 分析且无法确认选材 | 核对多候选、来源索引和 selection_pending/version_undecided | 推荐不是用户选材；未决原项和依据可见；不把 analysis_not_run 显示为无风险 | 当前分析索引、候选与未决关联；无正文 |
| 用户拒绝 / blocked | 当前有效冻结预览 | 仅 reject 当前 preview_id→轮询 | 按契约进入拒绝后的任务状态，零执行；不产生 Package 成功报告；旧成功不覆盖此任务 | 拒绝 payload、响应、状态序列、零写入证据 |
| accept_incomplete / blocked | 有明确冻结 missing/未决的有效预览 | false/省略→确认409；明确风险确认后提交 true | true 只接受同一冻结风险，不修复无效来源；成功报告仍保留 missing_items/package_unresolved；换预览必须重新确认 | 两次脱敏审批响应、同一冻结身份及保留风险 |
| 源变化 / blocked | 已建立有效读取证据的隔离副本 | 分别在分析后/批准前和批准后/复制前通过受控测试点改变源字节 | 旧分析/快照不可复用；阻止计划或执行，不能用相同大小/mtime 证明未变；纳秒数值精度不作为前端权威证明 | 阶段、A 的重验失败、字节摘要证据；不上传文件 |
| 复制失败 / blocked | A 可控注入某次复制失败 | 批准后注入失败→观察后续步骤 | 首次失败停止后续；任务 failed，失败 ToolResult data=null；成功复制保留真实结果，不能生成成功报告，报告GET409 | step_id/result_index、错误、尝试/未尝试列表及残留 |
| 清理失败 / blocked | 失败复制产生 A 能证明归属的片段，清理注入失败 | 复制失败后触发既有清理分支 | 明示 cleanup failed 和残留；无法证明归属则 not_attempted/unknown 或 other_object；不删来源、旧目标或成功文件，不递归清理 | 每次尝试复制的 cleanup 条目、reason/residual_state；缺失/重复/未知步骤告警 |
| 验证失败 / blocked | 复制后在隔离注入点产生内容/报告/文件集合不符 | 完成操作→执行真实验证→取 Snapshot | failed 不能显示验证通过；存在文件不等于内容验证；无成功 FinalReport，不能回退历史成功 | verification_targets、实际 verify ToolResult 与报告409 |
| 异常/过期污染 / blocked | 受控传入缺失、null、错类型、跨 task 或旧结果 | 用已有 B 单元/浏览器测试入口输入，不伪装生产后端 | 无崩溃、无路径泄露、无未授权批准；索引严格非负整数，任务/Workspace/goal 不一致时拒绝成功证据 | 当前/旧任务身份、脱敏异常形状、前端诊断与请求计数 |

cleanup 不是整个事务回滚：成功复制通常保留；清理成功也不代表 Package 成功。
最终报告只展示真实成功操作；失败、未执行和未知必须分别显示。Package 成功必须有 package_unresolved；普通报告允许缺少该字段。
未知或缺失 verification_targets、异常 cleanup、failed 报告及任务归属矛盾都不能推出验证成功。

## 通用证据包（本地记录模板）

复制以下空模板填写；未执行保持 null / not_run，不能把示例值充当后端返回。
这是本地验收记录格式，不是新增公共 API。共享前脱敏，原始证据仅留在授权位置。

```text
scenario: <矩阵场景>
execution_status: blocked | not_run | passed | failed
blocker / reason: null
timestamp / Windows / Python / browser: null
repo_head / branch / dirty_files: null
server_pid / start_time / imported_planner_path / planner_mode: null
workspace_alias / target_alias: null
task_id / user_goal_redacted / task_status_timeline: null
preview_id / plan_id / plan_sha256: null
current_plan_result_index / execution_result_indexes / final_result_index: null
source_inventory_reference / parser_results_summary: null
frozen_mapping_reference / missing / unresolved / analysis_evidence_indexes: null
approval_or_reject_payload_redacted / HTTP_status / response: null
ToolResult(tool, success, data_shape, message, error): null
attempted_steps / succeeded_steps / failed_steps / unexecuted_steps: null
cleanup_results / residual_observations: null
verification_targets / verify_result / report_HTTP_status: null
before_after_filesystem_observations / zero_write_before_approval: null
frontend_diagnostics / screenshot_reference / no_stale_task_override: null
expected_vs_actual / pass_basis / missing_evidence: null
```

脱敏规则：不保存 API Key、Authorization、环境密钥、文档全文或敏感用户目标。路径使用稳定别名，文件标识/摘要仅保存必要部分或安全本地引用；需要核对完整摘要时在本地受控记录中核对。
失败 ToolResult 的 success/data/message/error 分别记录，不能编造 data 或 FinalReport。截图先检查路径及正文；不能用 UI 文字代替后端与实际文件状态。
证据缺失标 unknown，源文件不可读取标明工具错误，不能以规划成功、复制成功或验证成功宣称材料内容真实完整有效。

## 本轮准备工具

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s demo -p test_package_acceptance_prep.py -v
.\.venv\Scripts\python.exe -B demo/package_acceptance_prep.py checklist
.\.venv\Scripts\python.exe -B demo/package_acceptance_prep.py capabilities
```

后两条预期退出码 **2**：分别表示材料待提供、真实执行尚未验收，不是通过。
工具仅读取仓库清单与 Python 源码并作 AST 静态检查，不导入后端、不读取课程文件、不发请求或写文件。
单元测试仅使用内存数据，不创建模拟课程材料。它只验证准备工具，不验证 Package 安全逻辑。
将来默认路由声明齐全也不会由此工具自动标记可执行或验收通过。
离线浏览器及 D/A 测试继续复用上列已有工具，待授权时运行并独立记录新结果；本轮不为补齐结果制造材料或执行它们。

## 本轮实际运行（2026-10-20）

| 检查 | 实际结果 | 退出码 |
| --- | --- | --- |
| 上述 unittest discover | 8 通过，0 失败 | 0 |
| checklist | 模板有效，实际已核实 0/22；blocked | 2 |
| capabilities | 缺少三个默认注册工具、执行拒绝路径存在、读取上限 10；blocked | 2 |
| `node --test frontend/tests/package-preview.test.cjs frontend/tests/agent-results.test.cjs frontend/tests/agent-workspace.test.cjs frontend/tests/organization-preview.test.cjs` | 76 通过，0 失败 | 0 |
| 新增文件 AST/JSON/逐行尾空白检查 | 两个 Python AST、22 行 JSON 和四文件空白检查通过 | 0 |
| `git diff --check` | 通过；未跟踪新文件另做上述逐行检查 | 0 |

未运行浏览器、离线 HTTP、真实模型或真实 Package 验收；场景矩阵没有任何已通过项。
准备文件位于独立分支 `codex/windows-package-acceptance-prep`，按授权提交至面向 dev 的独立 PR；未修改原有功能文件。
