# Package Real Mode 集成与 Windows 验收记录

基线：`origin/dev a5b89985ec24f536b9445823c783a273c672730f`（2026-10-21 获取）。
仅 B 的 frontend/demo 改动；不更改公共契约、A/C/D 实现或网络配置。

## 实际接入

- 普通 `POST /api/agent/tasks` 创建任务，后端规划末尾的 `build_package {}` 触发 A 的只读提议与冻结。**没有新增 plan_package/build_package HTTP 路由**。
- `GET /api/agent/tasks/{id}` 的最后一次 `plan_package` 是正式预览来源。复用 `PackagePreview.inspectSnapshot/renderSnapshot` 的 provided 门槛；无来源、失败、格式错误或跨任务只给诊断，不用 Fixture/历史成功补齐。
- 同时核对 task_id/user_goal/workspace、plan_id/plan_sha256 和具体 pending_operations 的顺序、step_id、tool、arguments、risk、status。preview_id 只使用服务端字符串，不重算哈希，不推断授权。
- 正式 `POST .../approve` 发送 `{preview_id}`；存在冻结 missing/unresolved 且用户明确勾选本次风险才附加 `accept_incomplete:true`。`POST .../reject` 始终只发送 `{preview_id}`。服务端独占校验与授权。
- 本地风险意向绑定当前任务、方案、摘要、preview、映射和风险；变化、拒绝、错误/409、模式切换后失效。处理中锁定审批；409 只读刷新，不自动重试写请求。
- 复用当前 Snapshot 的 package_execution/operation_results/cleanup_results 与 FinalReport。仅完整、按序、当前有效的执行/验证/报告证据才能显示文件操作与验证成功，不等于材料合格。失败及无效预览的执行诊断不展示详细文件映射。
- 新增显式 Task ID 恢复入口：刷新后输入原 Task ID，只 GET 当前服务状态，再决定后续操作。服务重启丢失内存任务会显示 404，不重建或重放任务。
- 整理模式仍禁用正式任务、扫描、审批、复制；不消费 Package 数据。独立 Package Fixture 页面正式审批仍禁用，不接真实 transport。

## 纳秒整数

Agent transport 在 JSON 整数 token 转为 Number **之前**保留超出安全范围的值为本地 BigInt。
数字字符串仍是字符串，数组顺序及字段类型仍有意义；界面以十进制文本展示 BigInt。
已舍入的 Number 仍触发精度警告，不能用 Number/JSON.stringify 相等重建来源证明。
不改 wire schema，不计算权威摘要，也不把 BigInt 放进审批请求。

## 可重复的受控真实 HTTP 验收

这套启动器只替换规划输入为明确的受控 Plan；**没有替换任何 ToolResult、Document、来源快照、审批状态或文件执行结果**。
真实 C/D 分析、A TaskService、审批 HTTP、Windows 文件创建/复制/报告/验证均使用已合并实现。
这是受控规划的真实文件执行验收，不是 DeepSeek/任意自然语言规划验收。

现有虚拟环境和已安装 Chrome，无安装依赖：

```powershell
# 终端 1：明确指定一个从未存在的测试目录；其父目录必须已经存在。
$caseRoot = Join-Path $env:TEMP ('package-live-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -B demo/package_live_acceptance.py --directory $caseRoot --port 18000

# 终端 2：将 caseRoot 换成终端 1 的实际完整路径。
$env:PACKAGE_LIVE_MANIFEST = Join-Path $caseRoot 'manifest.json'
node --test frontend/tests/package-live-browser.cjs
```

启动器拒绝复用既有目录，拒绝链接/reparse 祖先，只接受它自己生成的七个测试 Workspace。
只监听 127.0.0.1；不要对外发布这个受控规划验收服务。测试结束只停止终端 1 的自己进程。
不自动清理或覆盖验收目录；再次运行必须生成新目录。浏览器证据以 `wx` 独占写入。

浏览器禁用外部 HTTPS 请求，使用正式页面及普通审批接口；风险复选框和批准使用真实 DOM click。
改变来源和部分失败场景只会修改本轮生成的合成测试来源；生产页面没有任何直接文件写接口。
部分失败观察器在首次真实复制出现后修改第二个合成来源，**不 patch 后端算法或伪造失败**。
这项时序故障注入若未命中必须报告断言失败，不是稳定性/并发安全证明。

`browser-evidence.json` 保存原始 HTTP Snapshot 字符串（避免 Node Number 重新舍入）、任务 ID、
实际路径、源/目标/冻结摘要、报告摘要及观察结果。只用于合成验收目录，不应指向个人 Workspace。
观察测试通过只表示断言如实核对了结果；JSON 的 `status=blocked,e2e=false` 不表示验收通过。

## 本轮实际 Windows 结果

Python 3.12.12，Node 24.14.1，已安装 Chrome，服务 `http://127.0.0.1:18000`。
最终证据目录名 `package-live-1792566719197`，本机完整位置随交付提供，不提交原始本机日志/材料。

| 场景 | 实际观察 | 结论 |
| --- | --- | --- |
| normal | task_e02c8363afea42478aeb4116b60b139e；页面批准，真实复制及冻结报告、验证、FinalReport 一致 | 受控真实执行通过 |
| missing | task_0fd7b03e976c485b9a3435d1655a6c69；签字页缺失；不接受风险返回409，DOM勾选后批准，报告保留缺项 | 受控真实执行通过，不代表材料齐全 |
| reject | 最终轮 task_83d42f52ccff490da172dae2d4d1efa1 在预览前失败 `Source changed before reading`，无写入 | 本轮 blocked；不得算拒绝通过 |
| changed | 预览后主动修改合成来源；`Approved Package source differs from frozen preview`，无 Package 创建，report409 | 安全拒绝已观察 |
| occupied | 预览后创建目标及占位哨兵；`Package destination is occupied or parent changed`，哨兵保持，report409 | 安全拒绝已观察 |
| partial_source_changed | 首次复制真实成功；第二来源改变后复制失败，保留首文件；后续报告/验证未执行，report409 | 部分失败已观察，不能宣称回滚 |
| unrecognized_notice | `报名时必须提交报名表。` 提取为 required_documents=[]；Matching空，Package报 `No unambiguous material candidate can be proposed for Package` | blocked，不补造选材 |
| 重复/跨任务过期 preview | 真实已消费预览重复提交、其他任务预览提交当前任务均409 | 安全拒绝已观察 |
| 刷新/恢复 | 刷新后通过显式Task ID重新GET并继续同一预览审批；无自动写重试 | 受控浏览器观察通过 |
| 整理隔离 | 切换后扫描、批准、复制仍禁用 | 浏览器回归通过 |

先前一轮 `package-live-1792565832918` 中，reject 的 task_5d03559d1b8d4e4b846839ca538cc1c5
确实通过真实 Reject 接口停止且没有 Package 输出；原始证据保留。
**不得以该先前结果掩盖最终轮的 Windows 快照阻塞。**

普通及缺项两例复制的 `报名表.txt` 均为60字节，源/目标/冻结 SHA-256：
`b4a056667a8035313fcff51c12de49e3e03ba1f79e270d8320472e37b726e418`。
原始文件保持不变。实际输出相对本轮验收根目录：

- `normal/package_task_e02c8363afea42478aeb4116b60b139e/报名表.txt` 与 `PACKAGE_REPORT.md`；报告摘要 `42d38b87644703e769d85628a9e7d9667306cf691189eafe6552a50159cb20d0`。
- `missing/package_task_0fd7b03e976c485b9a3435d1655a6c69/报名表.txt` 与 `PACKAGE_REPORT.md`；报告摘要 `38e4a1d4f1741c1aea78da486f98d59d5f655783b893df6ccfab5b4584dd9428`。
- `partial_source_changed/package_task_ee5bb37ac07e494e9f00c938b75720ee/报名表.txt` 保留；相同材料摘要。cleanup 两条均 not_attempted/absent，分别为 copy_succeeded 与 Source revalidation failed before target creation。absent 不表示成功文件已回滚。

## 未完成及归属

1. **D / Windows snapshot：** 最终 reject 在 `fileforge.package._paths.snapshot` 的读取前签名比较失败。
   事后只读探针：同一60字节文件 lstat/fstat 的 dev、inode、mode、size、mtime_ns 相同，
   但 ctime_ns 分别 `1792566729204823000` / `1792566729205198100`。未改动校验或手工替换快照；需 D 确认 Windows ctime 语义及修复。
2. **A / 状态原子性：** 曾观察 task_e741f9f76e2d49a19c3d44d3d508d748 在普通分析报告 completed 后又进入 awaiting_approval。
   实际 service.run 先 `_finish` 再 `_propose_package/prepare_package`；前端按终态停止轮询可能漏掉后来的预览。
   受控验收显式刷新捕获此过渡，产品可手动刷新恢复；不能由前端猜测将普通 completed 改成其他公共状态。需 A 提供一致的终态可见性。
3. **D / Requirements 支持范围：** 前缀“报名时”的自然语言通知未被当前保守语法抽取。记录为空，不假装内容理解成功；支持该语句与否需 D/团队确认。
4. **真实 LLM：** 当前会话未提供 Planner 模型配置，不读取密钥文件，不调用 DeepSeek。本轮不是 LLM 端到端通过记录。
5. **未覆盖的真实故障：** 实际片段清理失败/未知残留、最终字节验证失败尚未通过真实故障注入验收；仅有现有合成回归，不能记为真实通过。
6. **22 文件：** 本轮仅新建小规模合成输入并使用真实工具执行。原22文件模板仍为0/22、待提供；没有权威逐文件覆盖接口，10候选上限与逐文件检查仍不可验证。
7. **Workflow 2：** 继续遵守已合并的分工及未冻结分类接口门槛，不开启整理执行。

## 独立检查

```powershell
node --test frontend/tests/package-preview.test.cjs frontend/tests/agent-results.test.cjs frontend/tests/agent-workspace.test.cjs frontend/tests/organization-preview.test.cjs
node --test frontend/tests/package-browser.cjs frontend/tests/organization-browser.cjs
.\.venv\Scripts\python.exe -B -m unittest discover -s demo -p test_package_live_acceptance.py -v
node --check frontend/agent-api.js
node --check frontend/package-preview.js
node --check frontend/tests/package-live-browser.cjs
git diff --check
```

本次最终 Node 127通过/0失败，退出0；Package+Organization Chrome 2通过/0失败，退出0；
启动器6通过/0失败，退出0；真实HTTP浏览器观察器1通过/0失败，退出0，但场景总体 blocked、e2e=false。
`frontend/tests/offline-browser.cjs` 额外尝试：0通过/1失败，退出1，原因缺少 playwright-core；未安装依赖。
最初沙箱内 Chrome 启动超时与临时目录权限错误也未计通过；获准在本地已安装环境复跑结果如上。
语法、inline JS、Python AST 和 diff 空白检查通过。没有修改公共 API。

补充静态工具检查：现有虚拟环境未安装 black/ruff，两个模块检查均退出1，未执行格式/lint验收、未安装依赖；Python AST语法检查通过。
