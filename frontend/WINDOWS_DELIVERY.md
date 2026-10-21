# Windows 联调与交付入口

本页是 B 的交付说明；正式接口以 `API_CONTRACT.md` 为准。实际测量见
`demo/acceptance_reports/windows-delivery-b05ae3d.{json,md}`，历史记录不被本页覆盖。
代码存在、单测通过、受控文件执行、真实模型端到端是不同层级。

## 安装与正常 Real Mode

需要 Python >=3.11、Node（浏览器测试需要支持全局 WebSocket 的新版 Node）以及
已安装的 Chrome。从仓库根目录执行；安装需要网络，本轮没有重装依赖：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -B -m uvicorn fileforge.api.server:app --app-dir src --host 127.0.0.1 --port 8000
```

浏览器访问 `http://127.0.0.1:8000/`，进入 Agent Workspace，选择 Real Mode。
正常生产 Planner 默认为 llm；模型配置使用既有环境变量：
`FILEFORGE_AGENT_PLANNER_MODE=llm`、`FILEFORGE_AGENT_PLANNER_BASE_URL`、
`FILEFORGE_AGENT_PLANNER_MODEL`、`FILEFORGE_AGENT_PLANNER_API_KEY`。
由用户在本机安全设置，不把凭据写进命令历史、日志或 PR；不要打印环境变量全集。
配置应指向实际获准使用的兼容模型服务；没有配置不能把固定 Planner 当成模型成功。
`docs/local-agent-development.md` 的旧 Package 未完成描述是历史阶段说明，当前
Package 实现/受控验证范围请以本轮报告和 `PACKAGE_REAL_INTEGRATION.md` 为准。

先选独立、非私人测试目录，Browse 可用路径快速跳转跨 Windows 盘符。
输入目标后查看 Plan、真实 Analysis Results 和来源证据。Matching 的 0/1/N 个文件名
候选都不是审核结论；版本推荐不是用户已采用。等待 Package 冻结预览，检查来源、
目标、未处理风险及操作，再显式批准或拒绝。需要接受缺项/未决风险时单独勾选；
没有有效预览不得审批。Final Result 只能以当前任务绑定的执行及字节验证为成功依据。
刷新后可用“恢复任务 ID”读取服务内原任务；服务重启不保证任务持久化，不自动重批。
409 后读取当前状态，不自动重试审批。失败和部分成功不是材料包交付成功。

## 无模型只读演示

```powershell
.\.venv\Scripts\python.exe -B demo/run_offline_browser.py
```

自动创建临时 Workspace，仅绑定 127.0.0.1，由同一 socket 分配并保留实际端口，
就绪后打开浏览器；Ctrl+C 关闭并清理自己创建的临时目录。
显示“固定 Planner · 非 LLM · 只读”，不批准 Package，不连接 OpenAI/DeepSeek。
细节及五种场景见 `demo/OFFLINE_BROWSER.md`。

## 受控真实 Package 浏览器验收

这是固定 Plan + 真实工具 + 真实 TaskService/HTTP/审批/文件复制，不是 LLM 验收。
仅在全新合成目录中使用。此启动器使用生产 app，**不是用于不可信客户端的通用
安全沙箱**；只在可信本机测试会话运行，不用于私人目录，不对外暴露。

终端 A（选择未占用端口；占用时换端口，不能关闭别人的进程）：

```powershell
$packageRun = Join-Path ([IO.Path]::GetTempPath()) ('dlo-package-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -B demo/package_live_acceptance.py --directory $packageRun --port 18085
```

终端 B 使用终端 A 打印的实际新目录：

```powershell
$env:PACKAGE_LIVE_MANIFEST = Join-Path $packageRun 'manifest.json'
node --test frontend/tests/package-live-browser.cjs
```

两个终端不会共享 `$packageRun`，需在终端 B 明确设置为终端 A 的路径。
可用 `CHROME_PATH` 指定已安装 Chrome。测试只修改这些新合成输入以模拟来源变化，
通过 UI/既有 HTTP 接口审批；不删除材料包、不清理用户文件。Ctrl+C 结束终端 A；
数据和原始 `browser-evidence.json` 保留供复核。每次重跑使用新目录，不覆盖证据。
部分失败用例的时序观察可能未命中；断言未命中就是失败，不当作已验证。

验收器检查 preview/plan/digest 关联、错误 preview 的 409、跨任务与重复审批 409、
刷新恢复、风险接受、真实复制与报告 SHA-256、拒绝/来源变化/目标占用/部分失败。
错误身份不等于时间过期；没有证明 TTL 到期。测试进程退出 0 也不代表全部场景
可交付，必须检查证据内的各场景 status 和总体 blocked。

## 22 文件及分类数据

复用 `demo/SHARED_ACCEPTANCE.md` 中 generate → probe → check-tools → report 命令。
数据集必须是新临时目录：22 个 Package 文件、20 个分类文件，gold 不可按结果修改。
报告保存到源 Workspace 外的 runs 目录，保留原件 SHA-256/mtime 对比。
当前单任务读取上限 10；完整 22 文件任务阻塞时保留原错误，不修改 TaskService、
拆批绕过或拼接单文件任务。缺少权威逐文件覆盖时保留 unverifiable。

## 第二条工作流

正式 classify_files / 路径规划 / 修改确认 / 审批执行接口尚未冻结，正式整理按钮保持
禁用。本地 Fixture 分类列表、目录树、待确认项和操作预览明确隔离，不能当真实扫描。
目前没有真实分类准确率，也没有真实 `整理结果/` 执行通过证明。

后续 A/B/C/D 必须先同意：源文件身份与证据、正文/文件类型/弃权区别、资源限制、
动态类别与人工修正的服务端再验证、安全目标路径与重名诊断、排除输出子树、冻结
预览及任务关联、明确批准/拒绝、逐操作结果/残留/字节验证。这里只列能力需求，
不定义新 JSON 字段。C 负责约定 seams 的规划/组件，D 分类，A 唯一生产写入口，B
消费冻结接口；不从 Fixture 推导正式消费者。

## 回归命令与证据层级

```powershell
node --test frontend/tests/*.test.cjs
node --test frontend/tests/package-browser.cjs frontend/tests/organization-browser.cjs
.\.venv\Scripts\python.exe -B -m unittest discover -s demo -p 'test_*acceptance*.py' -q
.\.venv\Scripts\python.exe -B frontend/tests/matching-public-smoke.py
.\.venv\Scripts\python.exe -B frontend/tests/real-results-smoke.py
.\.venv\Scripts\python.exe -B frontend/tests/offline-browser-smoke.py
.\.venv\Scripts\python.exe -B frontend/tests/offline-startup-smoke.py
git diff --check
```

Node 单测包括延迟响应、跨任务/工作流隔离、失败报告、JSON 大整数精度；这些是
受控状态测试。Chrome Fixture 覆盖桌面 1366 与窄屏 390、XSS/长路径/中文，
实际 HTTP Chrome 另跑上面的 opt-in 命令。未安装依赖或跳过不能记为通过。

已有 A/C/D Package 安全回归可只读检查并运行，不更改其测试/生产模块：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/test_agent_package_approval.py tests/test_agent_package_preview.py tests/test_agent_package_evidence.py tests/test_agent_package_provenance.py tests/test_package_evidence_freshness.py tests/test_document_package_evidence.py tests/test_package_paths.py tests/test_package_planning.py tests/test_package_report.py -q -rs --tb=short
```

本轮这组测试存在 Windows 间歇性快照失败，不能宣称全项目测试全绿。
实际复制中途进程/磁盘故障、未知清理残留、最终字节不一致目前只有已有测试 seam /
前端合成回归，未完成真实浏览器故障验收；不要对生产模块注入新故障入口。
最新详情、最小复现和 A/C/D 待办均在本轮报告。
