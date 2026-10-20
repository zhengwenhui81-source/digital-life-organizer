# Organization UI preview (Developer B)

Agent Workspace → 轻量智能分类整理 now opens a **formal integration shell**.
It reuses the existing Workspace/goal controls and defaults to a blocked,
read-only status view. The current contract has no frozen classification API;
this is not a `classify_files` ToolResult consumer. Run, approval, copy and task
refresh are disabled in this workflow, including direct handler calls. No
organization task is submitted. Browse retains the existing read-only directory
API; this work does not invoke it automatically or scan personal files.

To inspect the existing synthetic UI, explicitly enable “查看隔离的本地 Fixture”,
choose a local scenario, then 加载演示预览. This panel is separate from the formal
container, never a fallback for an absent/error response. It does not classify,
plan backend operations, or approve/execute filesystem changes. Material-mode
API transport and Mock data are unchanged.

`organization-demo.js` supplies synthetic Windows paths, explicit categories,
evidence descriptions and optional empty folders. No category names or counts
are embedded in the renderer. Scenarios: mixed, empty, single, all uncertain,
same-name collision, incomplete. The visible demo label is independent of the
Agent Mock/Real selector. Unknown files have no destination and never appear in
the copy list/tree. Excluded files stay outside the plan too.

Local display-only shape (must be adapted after the team freezes a contract):

```js
{
  localPreview: true,
  pathStyle: 'windows', // or 'posix'; presentation only, no path authorization
  outputRoot: 'E:\\UI演示输出（未创建）',
  folders: [['optional empty folder']], // relative display segments
  categories: [{name: 'any category', files: [{
    filename: 'any.txt', source: 'C:\\fictional\\any.txt',
    target: ['nested', 'any.txt'], // explicit suggested target, never inferred
    evidenceKind: 'file_type', // filename | text also supported
    reason: '.txt extension only; purpose unknown'
  }]}],
  pending: [{filename: 'unknown.pdf', source: 'C:\\fictional\\unknown.pdf', reason: 'insufficient evidence'}],
  excluded: []
}
```

The module groups supplied categories, joins display paths, builds a collapsible
tree from target segments, and lists their parent folders and copies. Root is a
label / proposed destination, not an existing directory check. Empty folders are
preserved. Repeated Windows targets are compared case-insensitively for a visible
**possible collision** warning; file/folder target collisions are also shown.
It neither resolves collisions nor verifies actual disk contents, source scope,
permissions or path identity. Backend validation remains mandatory.
All data is escaped before HTML rendering; native `<details>` supports keyboard
expansion. Long paths wrap. Display segments support up to 32 levels; malformed
or deeper data gets an explicit incomplete-data state with no partial plan.

Run:

```powershell
node --test frontend/tests/*.test.cjs
node --check frontend/organization-preview.js
node --check frontend/organization-demo.js
git diff --check
```

Serve the existing application with the normal project startup command. Browser
regression: check 1280×720 and 1366×768; load each scenario, toggle folders, verify
disabled real buttons and no classification/mutation request, return to materials,
then run Mock happy path and verify Real Mode transport/error behavior. Preview
files should never appear in the material form or an outgoing API payload.

Next integration requires frozen D classification/evidence/uncertainty output
and A operation planning + `pending_operations`/`preview_id` approval/verification.
No current demo shape is a proposal to freeze a second public contract.

## 正式整理接入准备（2026-10-21）

基线：dev `2201a86fd642ff88fa9419f3fbfa458557bf5caa`，包含 #44/#45/#46。
任务依据为 TASKS.md 第 10 节的团队已确认第二工作流；本轮仓库未找到独立任务书文件。
API_CONTRACT.md 只将 classify_files 列为未来能力，未冻结其公开入口或数据结构。

| 范围 | 当前实际状态 |
| --- | --- |
| Workspace / 用户目标输入 | 与材料工作流共用同一组 DOM 控件，切换保留值 |
| 正式整理入口、状态和风险区域 | 已实现容器；分类目录、源/目标路径、依据、未确定文件、待确认类别、重名冲突、危险路径均明确待提供/未检查 |
| 目录树、具体分类依据、多候选/冲突和文件映射 | 只有既有本地 UI Fixture，默认隐藏；没有真实分类结果 |
| 真实分类与文件执行 | blocked；无任务提交、批准、复制、移动、删除、覆盖或权威摘要计算 |
| Package 与普通 Agent | 保留已合并逻辑，整理模式不将其结果作为分类输入 |

OrganizationPreview.inspectSnapshot/renderSnapshot 仅核对已定义的 TaskSnapshot task_id/user_goal/workspace、任务状态和工具记录基本结构。
其 blocked/invalid/taskStatus/approvalEnabled 是内部视图投影，不是公共 API 字段。
分类正文保持不透明：即使有貌似分类的成功记录、历史重复结果或 Package manifest，也不读取映射，不把 completed 当作整理成功。
异常/跨任务返回 invalid，契约未接入返回 blocked；均无 detailed/provided 分支。
未来只能在正式契约和来源绑定验收后增加适配器，不能把 localPreview 结构当作后端契约。

复用 Package 的保守状态模式及 Agent 的 generation/task_id/mode 归属防护，并在请求上下文中加入**本地** workflow 维度；不复制 Package 的后端授权逻辑。
切换工作流会停止旧轮询、增加 generation、清除任务/报告/审批和两边展示，保留输入。
忙碌、轮询或审批处理中不能切换。整理模式的 runAgent/pollAgent/decideAgent 均在发请求之前返回，旧 renderAgent/renderAgentReport 不写入整理视图。
普通材料任务的批准/拒绝/报告仍使用原 transport，未新增 HTTP 字段。Fixture 必须显式开启，关闭或切换后清空。

### 必须等待 A/C/D 确认

- D：分类公开工具名、字段、依据与不确定性、成功空结果与失败语义；先经契约评审，不沿用本地展示 shape。
- A：如何创建受限的只读分类任务、当前任务/冻结预览/来源索引绑定、路径安全和重名占用检查、审批与复制执行。接口未验收前本页不启动通用 Planner 代替分类。
- C/A：可读取内容的格式边界和候选上限的实际适用范围；未知/未读取必须保留，不能默认为无风险或全部分类完毕。
- 团队：批准真实接入后再开放只读结果适配；正式执行还需独立审批、验证和失败回归，不因 UI 已存在而开放。

### 验证方式

```powershell
node --test frontend/tests/package-preview.test.cjs frontend/tests/agent-results.test.cjs frontend/tests/agent-workspace.test.cjs frontend/tests/organization-preview.test.cjs
node --test frontend/tests/organization-browser.cjs frontend/tests/package-browser.cjs
```

整理浏览器回归改用与 Package 回归相同的已安装 Chrome / Node CDP 方式，无 Playwright 安装要求。
测试仅启动静态 localhost 资源服务，GET /api/sessions 返回空合成会话列表；其他 API 拒绝，所有请求均记录，不导入 Agent 后端。
覆盖 1366/390 窗口、共享输入、正式 blocked、六个隔离 Fixture、XSS/长路径/目录展开、异常/跨任务/过期/Package 数据隐藏、零 Agent 请求及返回材料 Mock 完成流程。
这些测试不是后端、LLM 或真实文件整理验收。

本轮实际运行（2026-10-21）：上述 Node 回归 119 通过、0 失败、exit 0；两个 Chrome 回归
2 通过、0 失败、exit 0。四个修改 JS/CJS 与 index.html 内联脚本语法检查、共享控件 ID 唯一性、
`git diff --check` 通过。没有新增依赖，没有访问真实用户文件或运行分类/Package 执行。
