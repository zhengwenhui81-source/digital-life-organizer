# 本机真实 Agent 启动与验收（2026-10-23）

## 启动

在 PowerShell 执行（不依赖当前目录、不需要重新输入密钥）：

```powershell
& E:\Hackthon\digital-life-organizer\.venv\Scripts\python.exe -B E:\Hackthon\digital-life-organizer-course-ui\demo\start_local_agent.py
```

网页：http://127.0.0.1:8000/ 。保持终端开启，Ctrl+C 结束本服务。
端口被占用时启动器拒绝接管，不会结束其他进程；先核对原有进程。
不需要再次启动时直接使用已运行的页面。

启动器复用主项目 `demo/start_course22.py` 的配置读取函数，读取主项目根目录
`.env`。该文件正常重启后保留、已被主项目 Git 忽略且未被跟踪。
不复制密钥，不写入前端/参数/运行记录，不修改系统环境变量或代理。
仅进程内设置真实 Planner 模式、官方 `deepseek-flash`、
`https://api.deepseek.com`。模型名可显式通过 `--model` 传入；本次采用
https://api-docs.deepseek.com/ 当前官方文档列出的模型，不使用本地 Ollama 默认值。
不会覆盖现有 `.env`；配置文件中的密钥不需要包含在启动命令中。

启动器强制验证主项目 `.venv` 的 sys.prefix，使用本验收目录的绝对 src 路径，
核对实际导入的 Planner 文件和前端根目录，打印完整 HEAD、工作进程 PID、
Python 版本、Planner 源码 SHA-256、配置来源及密钥是否存在。
不打印密钥。健康成功不等于模型成功；启动器明确标记 model_connection 未测试。
默认不发送模型请求、不创建任务、不进行工作空间文件操作。

```powershell
& E:\Hackthon\digital-life-organizer\.venv\Scripts\python.exe -B E:\Hackthon\digital-life-organizer-course-ui\demo\start_local_agent.py --check
```

`--check` 为离线检查，不启动监听或调用模型。

## 根因与代码整合边界

原命令 `python -m uvicorn ... --app-dir src` 不读取 `.env`；`src` 又依赖启动时
的当前目录，不能证明前后端来自同一个 checkout。Planner 缺省值是
qwen3-coder / localhost:11434/v1，缺失显式配置时会访问错误服务。
旧 PID 36780 的父进程 35340 是主项目 venv 的 python.exe；该 venv 基于
D:/miniconda3，因此 Windows 子进程显示 Miniconda 路径本身不能证明 venv 无效。
原进程未留下源码路径启动证明，其实际导入路径无法事后完整追溯。
只结束了核对命令与父进程一致的原 8000 监听进程，没有处理其他 Python 服务。

验收基线为 1426b9932e42c2e6ccb4d82fe4a486637a95c981，带本轮未提交修复。
已将主项目已有的可选 interactive 澄清实现、answers API、同任务继续规划和
相应 UI/测试整合到此目录，保留动态流程图。不实现另一套规划或审批。
这部分来自主项目已有的未提交工作，仍需团队独立审查；未变更本目录的
API_CONTRACT.md，未宣称该扩展已经合并或得到新的公共协议批准。
非 interactive 调用仍走既有接口。未引入生产 Mock 入口。

## 动态流程图修复

- 完成步骤必须关联当前任务、同序工具返回的真实成功结果；失败后记录不计成功。
- 结果节点只接受当前完成任务对应的合法 FinalReport；Package 复用原证据门槛。
- 等待澄清与文件审批分开显示，澄清时冻结执行方案不得提前变绿。
- 分析分组按当前计划首次出现顺序排列，蛇形布局与动态连线保留。
- 未执行连线不显示活动光点；仅真实运行中的当前节点显示活动动画。
- 未运行的冲突分析明确提示，不能由已完成版本比较推断无冲突。

## 自动检查

```powershell
node --test frontend/tests/*.test.cjs
node --test frontend/tests/agent-flow-browser.cjs frontend/tests/package-browser.cjs frontend/tests/organization-browser.cjs
& E:\Hackthon\digital-life-organizer\.venv\Scripts\python.exe -B demo/test_start_local_agent.py -v
```

全量 Agent pytest 使用 Python Path.glob 展开 tests/test_agent*.py 后逐项传入，
Windows 下不能假定 shell 自动展开通配符。实际结果：164 通过、2 跳过，退出码 0；
跳过原因分别是无法创建目录符号链接、POSIX dir_fd 专属用例。
前端 149 通过，退出码 0；Chrome 离线回归 4 通过，退出码 0；
启动器离线测试 3 通过，退出码 0。Fixture/受控 Planner 测试不属于真实 LLM 验收。
最初的测试夹具/命令失败已修复后重跑，未计入通过数。

## 真实浏览器验收证据

本轮只创建一个真实任务：task_23dc0a9a7c154151b4a1183a031affe9。
独立临时 Workspace：
C:/Users/Zwen/AppData/Local/Temp/dlo-real-agent-LSNczA/workspace

三份有实际正文的合成文档，不是空壳；不接触课程 Demo 原件。
证据目录 C:/Users/Zwen/AppData/Local/Temp/dlo-real-agent-LSNczA 包含
原始只读 Snapshot 响应、acceptance.json、history.json。
真实 DeepSeek 响应记录 2 次，真实成功工具：list_files、read_document ×3、
compare_versions、extract_requirements。停在 awaiting_clarification，未发送审批，
未生成 FinalReport，三个原始 SHA-256 未变、输出目录不存在。

用户首次指出高亮/颜色/连线不正确，已按真实快照修复并重跑测试。
随后只读浏览器复核桌面/窄屏 12 项断言通过；没有再次调用模型。
可以显式复用已有真实任务打开修复后的检查窗口，不创建新任务：

```powershell
node demo/verify_real_agent.cjs --inspect task_23dc0a9a7c154151b4a1183a031affe9
```

该窗口拦截 approve/reject；回答仅由用户点击提交。不自动选择选材、不自动批准。
`--run` 是额外真实验收入口，会新建测试 Workspace 并产生模型费用；本轮已执行一次，
不要为了打开现有任务重复运行它。其合成输入不代表22文件或任意未知资料全面验收。
当前尚需用户复核修复后的流程图、提交回答后继续验证到等待审批；
未经明确批准，不执行复制、移动、覆盖或删除。实际文件执行与最终报告的真实链路
本轮按要求不执行，仅有既有受控回归证据，不能宣称真实端到端写入已验收。

用户已确认修复后的流程图显示正常，并选择暂不提交澄清回答。任务继续暂停；未向 answers 或 approve 发出后续请求，未追加模型调用。回答后真实审批阶段待用户继续，不能计为通过。
