# 真实可用 Agent 本机交付记录（2026-10-23）

## 当前版本及入口

基线 HEAD：1426b9932e42c2e6ccb4d82fe4a486637a95c981，带未提交本地修改。
验收源码：E:/Hackthon/digital-life-organizer-course-ui；服务 PID 30044，127.0.0.1:8000。
未提交、推送、切换分支或清理原有工作区。主项目 .env 未覆盖，已被忽略、未跟踪。

```powershell
& E:\Hackthon\digital-life-organizer\.venv\Scripts\python.exe -B E:\Hackthon\digital-life-organizer-course-ui\demo\start_local_agent.py
```

打开 http://127.0.0.1:8000/ 。服务已运行时不重复启动；启动器不会接管占用端口。
正常产品页不安装验收脚本的请求拦截，不自动发起任务或批准操作。
主项目 .venv 基于 Miniconda；子进程显示 D:/miniconda3/python.exe 不代表虚拟环境失效。
实际解释器 sys.prefix、绝对源码与前端目录均由启动器强制核对。
启动时在进程内读取主项目 .env；仅主项目既有 literal loader 被复用，不持久化系统环境。
DeepSeek 配置为 llm / deepseek-flash / https://api.deepseek.com；不使用本地11434缺省值。
/api/health 为服务健康证据，不是模型连接证据。真实模型证据见后述3次响应。

## 根因及修复

旧启动命令不加载 .env，且 --app-dir src 随启动目录变化，无法稳定绑定当前验收源码。
缺失配置会回落到 qwen3-coder / localhost:11434/v1。已用绝对源码、显式模型配置修复。
已有澄清实现原先只在主项目未提交工作中；已整合到验收目录，保留原 TaskService、
Executor、Approval Gate、Package 安全展示等，不创建第二套审批或文件执行器。
动态流程图原先存在无对应 ToolResult 却变绿、澄清时计划提前完成、任意旧报告点亮结果、
灰色连线仍有活动光点等问题；完成节点现以当前任务有效执行链和报告为依据。
自动 verify_result 并非 PlanStep，现可依据当前服务端核验和有效 FinalReport 显示核验完成。
完成态主链只展示实际安排的阶段；未安排能力另列，既不计为成功，也不阻碍已验证任务完成。
阶段原始证据可在节点内的原生 details 展开，所有外来文本经过转义。

本次按用户最后要求：失败卡片的外观也为绿色，但失败状态、错误文字和核验事实保持原值，
不把失败复制计入成功。页面说明卡片颜色不代表成功。等待及运行仍有对应状态和样式。
统一蓝白主题、默认实际材料澄清模式，正式页面没有新增 Mock 替代入口。

## 修改文件及目的

| 文件 | 目的 |
| --- | --- |
| frontend/index.html | 蓝白主题入口、真实澄清 UI 调用、默认正文分析、保留工作空间及审批报告；移除外网字体依赖 |
| frontend/agent-workbench.css | 蓝白主题及用户指定的绿色失败卡片，保留失败文字 |
| frontend/agent-api.js | 真实 transport 默认值、已有 answers 请求 |
| frontend/agent-clarification.js | 展示服务端问题，提交回答，不生成授权 |
| frontend/agent-flow-visualization.js | 当前任务执行证据、详情、动态顺序、自动核验及最终报告门槛 |
| frontend/agent-flow-visualization.css | 当前节点/等待节点/真实运行连线样式，不激活未执行连线 |
| src/fileforge/agent/planner.py | 复用已有交互上下文和真实模型响应追踪实现 |
| src/fileforge/agent/clarification.py | 复用已有正文发现、澄清、同任务继续及来源复核实现 |
| src/fileforge/agent/service.py | 整合可选 interactive 生命周期及来源变化检查 |
| src/fileforge/api/agent.py | 整合既有 interactive/answers 入口，保持普通请求兼容 |
| frontend/tests/agent-flow-visualization.test.cjs | 工具证据、失败阻断、最终报告、未安排阶段及详情转义回归 |
| frontend/tests/agent-flow-browser.cjs | 桌面/窄屏样式、状态、动画、详情交互与绿色失败外观回归 |
| frontend/tests/agent-workspace.test.cjs | 同任务页面、普通审批与异步归属回归 |
| frontend/tests/agent-clarification.test.cjs | 问题/回答验证、重复点击及转义回归 |
| frontend/tests/organization-browser.cjs | 修复测试资源白名单，仅测试内注入 Mock 选项；不改正式入口 |
| tests/test_agent_clarification.py | 澄清、回答、继续、来源变化、审批安全受控测试 |
| demo/start_local_agent.py | 明确 venv、源码、配置和端口的本机启动入口 |
| demo/test_start_local_agent.py | 离线启动配置与不泄漏密钥测试 |
| demo/verify_real_agent.cjs | 上一轮只读/澄清验收及已有真实任务检查工具 |
| demo/real_agent_e2e.cjs | 本轮明确授权的完整真实浏览器验收，只使用新临时 Workspace |
| demo/check_completed_task.py | 独立只读复核当前 API、原件和目标字节、唯一审批及同任务关联 |
| demo/test_completed_task.py | 核查器对损坏、缺失、重复、原件变化的负向测试 |
| demo/LOCAL_AGENT_START.md | 上一轮配置及暂停验收记录，保留历史边界 |
| demo/REAL_AGENT_DELIVERY.md | 本交付记录 |

未修改 API_CONTRACT.md；沿用主项目既有、但仍待团队代码审查的澄清扩展。
没有宣称公共协议已合并或进行新的协议批准。

## 本轮真实端到端验收

独立临时根目录：C:/Users/Zwen/AppData/Local/Temp/dlo-complete-e2e-fkqOQd
Workspace 为其 workspace 子目录。
真实任务：task_274865f700ed42b58fd5920923257d26。

五份实际正文材料：说明、报告v1/v2、文件名不透露用途的报销和行程资料。
真实模型通过正文提出选材澄清，浏览器提交测试答案后继续同一 task_id；
产生并展示真实冻结 preview_id，审批前确认无输出、所有原件未变；
仅通过既有网页批准按钮提交一次，后端创建4个目录并复制3个文件，最终完成核验与报告。
没有固定 Plan 注入、Mock ToolResult、预建结果目录或前端伪造完成。

| 实际目标（均在 Workspace 内） | 字节 | SHA-256 |
| --- | ---: | --- |
| 整理结果/项目报告/附件B.txt | 108 | 43349f73854cd906e3dd4da72a5c24165f583e672a9c0f41ca5b3aec648212fd |
| 整理结果/财务报销凭据/记录甲.txt | 148 | 5a38ef8d901138e0805e2ebd7a5b50953927725f51c5ca548d8d2e69bcf79c34 |
| 整理结果/出差行程安排/清单乙.txt | 142 | 653d3b50c5c31f13d4d497f4ccb19c33f6c569255453918eb0a8663846075ce9 |

3次真实 DeepSeek responded 事件；5次真实 read_document、compare_versions、
4次 create_folder、3次 copy_file、1次自动 verify_result 均成功。
唯一审批请求使用冻结时服务端 preview_id；answers 与 approve 均属于同一 task_id。
服务端核验7项均通过。独立核对3目标字节一致、没有异常副本；
5原件 SHA-256、大小、mtime_ns 保持不变。当前 FinalReport 与保存报告一致。
本轮模型未选择 extract_requirements/detect_conflicts；这些未执行阶段不冒充成功。
需求提取已有上一轮真实任务和受控回归证据，不等于本轮运行冲突检查。

证据：baseline.json、frozen-preview.json、原始HTTP响应 response-*.json、acceptance.json。
验收工具检查完成后保留浏览器用于查看，其进程仍等待窗口关闭；不声称该持窗进程已退出。
另行执行的独立只读核查命令真实退出码为0：

```powershell
& E:\Hackthon\digital-life-organizer\.venv\Scripts\python.exe -B -X utf8 demo/check_completed_task.py C:\Users\Zwen\AppData\Local\Temp\dlo-complete-e2e-fkqOQd
```

如仅打开已有真实任务的测试检查窗口，勿重复 --run；检查窗口会拦截审批，
用户自己的文件操作应从默认浏览器的正常产品页 http://127.0.0.1:8000/ 开始。
此前暂停任务 task_23dc0a9a7c154151b4a1183a031affe9 原样保留，未代替它伪造完成。

## 最终自动测试

- node --test frontend/tests/*.test.cjs：153通过、0失败、0跳过，退出码0。
- node --test frontend/tests/agent-flow-browser.cjs frontend/tests/package-browser.cjs frontend/tests/organization-browser.cjs：4通过、0失败，退出码0。
- 对 Path.glob('tests/test_agent*.py') 展开的文件运行 pytest -q -rs -p no:cacheprovider：164通过、2跳过，退出码0。
  跳过：当前环境不能创建目录符号链接、POSIX dir_fd 专属用例。
- demo/test_completed_task.py：6通过；demo/test_start_local_agent.py：3通过，退出码均0。
- 语法、git diff --check、源码密钥扫描另行执行；没有为了验证配置重复调用模型。

一次完成态显示回归因原测试假定未执行节点一定出现在主链而失败，已修复失败核验的明确显示，
重跑153项通过；旧失败输出未作为通过结果。真实文件执行第一次即通过，未重复复制。
初始本轮主题测试151项通过，后续增补安全/完成态回归后为153项。

## 范围限制

本次证明这组独立混合用途材料的真实闭环，不代表任意文件/任意分类准确率保证。
正文支持TXT/PDF文本层/DOCX/XLSX现有提取范围；不承诺OCR、代码正文解析或完全Office提取。
当前交互模式最多10个可读文档；超限会明确失败，不冒充全量扫描分析验收。
本轮未执行22文件验收，没有放宽资源限制或安全检查。
未批准的任务不写文件；不删除、覆盖原件；所有旧测试证据和未提交修改保留。

最终检查已实际执行：全部修改/新增 Python、JavaScript 和内联脚本语法通过，git diff --check 通过；24 个修改/新增文件中未发现真实密钥。主项目 .env 已忽略且未跟踪。最终前端153项、Chrome4项均通过。独立只读任务与磁盘核查再次退出0；8000健康检查正常。默认浏览器已打开未安装测试请求拦截的正常产品页。
