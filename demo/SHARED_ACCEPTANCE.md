# 统一验收工具：使用与证据边界

这是 B 维护的**本地验收工具**，不是公共 API、生产分类器、第二套 Agent 或批准执行入口。
人工标准答案来自 `acceptance_datasets.py`，不能根据实际输出修改标签以提高分数。
生成数据、独立单文件探针、同任务子集分析、完整任务、浏览器和 LLM 验收必须分别记录。

## 环境与生成

在仓库根目录，使用已安装项目依赖的 Python 环境。以下 PowerShell 示例创建一个
**全新、绝对路径**的数据集；目录不能已经存在，父目录必须存在。

```powershell
$dataset = Join-Path ([IO.Path]::GetTempPath()) ('dlo_acceptance_' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -B demo/shared_acceptance.py generate --directory $dataset
```

成功退出 0，返回 `prepared_not_tested`。产生：

- `package/`：22 个合成输入，涵盖要求、版本、冲突、缺候选、损坏、空白及不支持格式。
- `classification/`：20 个合成输入，含同名不同用途、误导文件名、非课程资料及应弃权项。
- `gold.json`、`gold.md`：人工标准答案、原始 SHA-256 / 大小 / mtime 基线。
- `READY.json`：绑定 gold 的 SHA-256；`runs/`：本地证据目录。

**这不是已有真实课程材料。** 既有 `demo/package_acceptance/course-materials-22.json`
待提供模板保持不变，不能把这里的合成数据当作该课程真实验收完成。
默认无命令时拒绝执行，不隐式生成数据。已有目录、修改过的 gold、重新封印但改变
标签的 gold 都会被拒绝；要更改输入实验，应创建新数据集并保留旧记录。

## 只读受控 TaskService 探针

```powershell
.\.venv\Scripts\python.exe -B demo/shared_acceptance.py probe --directory $dataset --output (Join-Path $dataset 'runs/read-only')
```

使用真实 TaskService / 工具及固定 Planner，不调用模型，不调用 approve/decide：

1. 一个批量发现、读取和分析任务。当前 10 个候选读取限制可能明确阻塞；不绕过限制。
2. 22 个各自独立的显式路径读取任务。它们只证明该次单文件读取结果。
3. 一个读取两份通知及六份材料的分析子集，调用真实要求、冲突、Version、Matching
   与 Package 计划。代码中的 `build_package` 步骤交由 A 的审批门处理；停在
   `awaiting_approval` 不等于执行成功，本命令不批准、不写材料包。

输出 `runs/read-only/observations.json`，退出 0 表示探针记录完成，**不是所有任务成功**。
文件中保留各任务的 ID、计划、原始 ToolResult、失败信息、运行环境和数据基线 hash。
独立任务永远不能拼成“同一任务完整 22 文件分析”；报告中的 confirmed 数量只是跨记录
的证据下界。没有权威逐文件信息时，unsupported / limit / skipped 不靠扩展名或数组位置猜测。

命令仅对新生成数据读取、在新的 runs 子目录保存证据；可能记录审批前预览，但不提交
审批、复制、移动、删除或清理观察对象。勿将它改为真实用户目录的批量执行工具。

## 记录工具测试

```powershell
.\.venv\Scripts\python.exe -B demo/shared_acceptance.py check-tools --directory $dataset --output (Join-Path $dataset 'runs/unit-tests')
```

实际执行 `python -B -m unittest discover -s demo -p 'test_*acceptance*.py' -v`，保存
`tests.log` 与 `test-record.json`。记录原命令、退出码、用例总数、日志 hash、环境及
验收代码指纹；报告会重新检查日志和代码是否被修改。这里的单测使用合成证据验证
校验器，**不等于生产审批/复制、真实分类或模型验收**。

## HTTP Snapshot 采集

只有你已在独立测试服务运行了明确的任务，且其目标文本和 Workspace 与 gold 完全
一致时，才使用以下命令。不要用猜测的 task_id 或其他任务结果填补缺失证据。

```powershell
.\.venv\Scripts\python.exe -B demo/shared_acceptance.py capture --directory $dataset --output (Join-Path $dataset 'runs/http-capture') --url http://127.0.0.1:实际端口 --task-id task_实际ID
```

只接受明确的 `http://127.0.0.1:<port>`；仅 GET Snapshot，任务 completed 时再 GET
报告并重读 Snapshot 防止陈旧拼接。校验 task_id / goal / Workspace、ToolResult
envelope 及报告身份。原始 JSON 本地保存，不作为公共 API 扩展，也不作为服务端签名。
仅捕获不能鉴别模型提供商：`captured_http_unknown_planner` **不是 DeepSeek 证明**。
本轮工具交付没有执行真实浏览器或模型采集，不需要 API Key。

## JSON / Markdown 报告

```powershell
$evidence = Join-Path $dataset 'runs/read-only/observations.json'
$tests = Join-Path $dataset 'runs/unit-tests/test-record.json'
.\.venv\Scripts\python.exe -B demo/shared_acceptance.py report --directory $dataset --evidence $evidence --tests $tests --format json
.\.venv\Scripts\python.exe -B demo/shared_acceptance.py report --directory $dataset --evidence $evidence --tests $tests --format markdown
```

`report` 只读输入并写 stdout，不修改源文件或标签。重定向报告时使用 UTF-8、并选择
**源 Workspace 之外**的 runs 路径。未附 evidence/tests 时对应层级保持 not_run 或
unverifiable，不从旧日志推测。报告总体 blocked 的退出码 **2 是预期行为**；失败为 1。
probe/generate/capture/check-tools 的非报告成功为 0，失败非零。

报告逐文件列出发现、读成功/失败、分析和待确认的证据来源（task_id/result_index），
记录原件 SHA-256、mtime 变化及 Package 字节观察。成功空分析不证明每个文件已分析；
较新失败不保留旧成功作为当前覆盖。只有匹配候选不等于材料核验通过；Version 推荐
不等于最终选择。Package 预览不等于批准执行，字节相同也不独立证明审批来源可信。

分类指标计算要求全部人工标注文件各有一条实际决策，分别报告用途准确率/覆盖率、
扩展名类型准确率/覆盖率和弃权。类型分组不当作用途理解；少数高置信文件不冒充
整体覆盖。当前共享报告未接真实分类适配器，指标保持 blocked/null；95% 只是目标。

## 旧组织观察工具及安全边界

`organization_acceptance.py` 仍保留其独立的 12 源文件夹具与两个既有输出哨兵；不是
上述 20 文件数据集。`generate --directory <new-absolute-dir>` 生成新夹具，
`check --directory <dir> [--review <private-index.json> --raw-results <raw.json>]
[--format json|markdown]` 只读核对。review 是本地人工索引，不是冻结分类契约或授权。
它不提交人工分类、不调用写 API，也不会清理失败残留。全链路缺乏权威绑定时保持
unverifiable，不能因观察到正确字节就发成功证书。

文件观察拒绝符号链接、reparse point、硬链接、路径穿越、Windows 非法/同名路径；
检查大小、hash、文件身份及观察前后时钟变化，遇变化失败关闭。工具有本地证据读取
安全预算，不改变 C/D 的生产限额。JSON 拒绝重复字段和非有限数值。

原始证据可能含本机路径及 Document 正文，**不要直接提交**。PR 只保留脱敏摘要，
完整本地证据应由操作者保存；工具不自动删除数据集或旧证据。禁止修改金标准迎合
结果，不根据受控 Planner 声称真实 DeepSeek 成功，不修改 A/C/D 的生产代码。

本次实际运行记录见 [验收摘要](acceptance_reports/shared-a5b8998.md)。
