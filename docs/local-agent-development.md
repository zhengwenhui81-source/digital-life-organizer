# Agent 本地开发与运行

本页用于从仓库源码运行 **Agent HTTP API + 前端**。上游 FileForge CLI 的说明见
[`setup.md`](setup.md)。每次反馈请记录 `git rev-parse HEAD`、操作系统、Python
版本、具体命令和结果；模块测试不等同于真实 LLM／浏览器端到端验收。

## 1. 获取源码与安装依赖

使用 Python 3.11 或更新版本。下面命令均从仓库根目录执行；`.[dev]` 安装
项目依赖和 pytest、Black、Ruff。Agent 服务需要 `uvicorn`，真实 LLM 模式
还需要 `openai`；两者已经列在 `pyproject.toml` 的项目依赖中。

Windows PowerShell：

```powershell
git clone https://github.com/zhengwenhui81-source/digital-life-organizer.git
cd digital-life-organizer
git switch dev
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
git rev-parse HEAD
```

Linux shell：

```bash
git clone https://github.com/zhengwenhui81-source/digital-life-organizer.git
cd digital-life-organizer
git switch dev
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
git rev-parse HEAD
```

如果已有 checkout，先按 `AGENTS.md` 将最新 `dev` 合入自己的 feature 分支。
不要把 `.venv`、密钥文件或真实 Workspace 放进提交。

## 2. 不依赖模型的模块测试

测试使用 pytest 临时目录或可复现 Fixture，不需要 B 的 Workspace、API Key
或代理。Windows：

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_agent_planner.py tests/test_agent_executor.py tests/test_agent_verification.py
.\.venv\Scripts\python.exe -m black --check src/fileforge/agent/planner.py tests/test_agent_planner.py
.\.venv\Scripts\python.exe -m ruff check src/fileforge/agent/planner.py tests/test_agent_planner.py
```

Linux：

```bash
.venv/bin/python -m pytest -q tests/test_agent_planner.py tests/test_agent_executor.py tests/test_agent_verification.py
.venv/bin/python -m black --check src/fileforge/agent/planner.py tests/test_agent_planner.py
.venv/bin/python -m ruff check src/fileforge/agent/planner.py tests/test_agent_planner.py
```

Black/Ruff 示例检查 Planner 文件；提交 PR 时还应检查本次实际改动的 Python 文件。
例如 C 可运行 `tests/test_document_parser.py tests/test_document_versions.py`，
D 可运行 `tests/test_task_requirements.py tests/test_task_matching.py`；
Package 专属测试以对应实现合入后的实际文件为准。
对正在修改的模块运行其相关测试；若未运行全量测试，请注明范围。测试跳过项、
受控 Plan、合成文档及 Linux 结果不能当作 Windows 浏览器或真实模型验收。

## 3. 离线 Demo 模式启动服务

Demo Planner 不连接 LLM，但它**固定规划一次扫描和一次待审批的新建目录**，
因此只在新建的临时 Workspace 中使用；不要在个人文件夹中批准演示操作。
没有点击批准时不会执行写操作。Windows：

```powershell
$env:FILEFORGE_AGENT_PLANNER_MODE = "demo"
$fixture = Join-Path $env:TEMP ("fileforge-agent-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $fixture | Out-Null
Set-Content -LiteralPath (Join-Path $fixture "example.txt") -Value "fixture"
.\.venv\Scripts\python.exe -m uvicorn fileforge.api.server:app --app-dir src --host 127.0.0.1 --port 8000
```

Linux（在另一个终端保留 `fixture` 路径以提交测试任务）：

```bash
export FILEFORGE_AGENT_PLANNER_MODE=demo
fixture=$(mktemp -d)
printf 'fixture\n' > "$fixture/example.txt"
.venv/bin/python -m uvicorn fileforge.api.server:app --app-dir src --host 127.0.0.1 --port 8000
```

浏览器访问 `http://127.0.0.1:8000/`，健康检查为
`http://127.0.0.1:8000/api/health`。在前端选择刚创建的临时 Workspace。
`demo` 只验证服务、任务轮询与审批通道，不验证真实任务理解、文档分析或
Package。当前 Package 功能尚未完成，前端 Package Fixture 也不是可执行审批。

## 4. 真实 LLM 模式

只有实际承担真实联调的机器才需配置模型连接。Planner 使用兼容 OpenAI
Chat Completions 的服务，设置以下环境变量后按第 3 节的 `uvicorn` 命令启动：

| 变量 | 用途 |
| --- | --- |
| `FILEFORGE_AGENT_PLANNER_MODE=llm` | 调用真实模型；不自动回退 Demo。 |
| `FILEFORGE_AGENT_PLANNER_BASE_URL` | 模型服务的完整 API base URL。 |
| `FILEFORGE_AGENT_PLANNER_MODEL` | 该服务支持的模型名。 |
| `FILEFORGE_AGENT_PLANNER_API_KEY` | 仅在本机进程环境中设置的凭证。 |

Windows 可在当前 PowerShell 会话中用
`$env:FILEFORGE_AGENT_PLANNER_API_KEY = Read-Host "API Key"` 输入凭证；
Linux 可用 `read -rs FILEFORGE_AGENT_PLANNER_API_KEY; export FILEFORGE_AGENT_PLANNER_API_KEY`。
不要将密钥写进命令行参数、文档、Fixture、日志、截图或 Git 提交。代理如有需要
由运行者在本机配置；本说明不要求 A/C/D 连接 B 的 DeepSeek 服务。

模型请求成功只证明规划阶段通过。真实跨模块验收仍须检查 TaskSnapshot、
工具结果、审批前后的实际路径与文件摘要，以及 FinalReport；失败时提供脱敏
Snapshot 和复现步骤。B 目前统一执行 Windows 浏览器、真实 DeepSeek 和端到端
验收；A/C/D 的模块与受控测试分别说明其验证边界。
