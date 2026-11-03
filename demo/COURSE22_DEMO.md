# 22文件整理：用户选择目录与路径无关性验收

## 本机持久化启动（2026-10-22）

项目根目录 `.env` 保存 `FILEFORGE_AGENT_PLANNER_API_KEY`，已被 `.gitignore`
忽略；不要提交或分享该文件。它是磁盘文件，正常重启不会消失。启动器每次从
项目根目录读取，不依赖当前终端之前设置的变量，也不写入系统环境变量。
仅支持单行字面值（可加引号、注释），不执行变量插值或 shell 命令。
可选配置为 `FILEFORGE_AGENT_PLANNER_MODE`、`FILEFORGE_AGENT_PLANNER_MODEL`、
`FILEFORGE_AGENT_PLANNER_BASE_URL`；缺省为 `llm`、`deepseek-chat`、
`https://api.deepseek.com/v1`。密钥没有缺省值。已有服务不会因编辑 `.env` 热更新。

当前录制 Demo 仍使用原验证 checkout。每次开机，在 PowerShell 执行：

```powershell
cd E:\Hackthon\digital-life-organizer
.\.venv\Scripts\python.exe -B demo\start_course22.py --code-root C:\Users\Zwen\AppData\Local\Temp\dlo-deepseek-round2-20261021-01\checkout
```

启动器启动已有后端和课程 Demo，检查本机健康接口后自动打开浏览器。
前端端口由系统分配，以终端打印的 URL 为准；不要依赖上次的 61779 端口。
保留该终端；Ctrl+C 只停止本次启动的两个服务。51851 已占用时拒绝启动，
不会停止或接管旧服务。只创建独立临时服务/证据目录，不选择或修改材料目录，
不会创建 Agent 任务或调用模型。模型调用仅在用户实际提交任务时发生。
原 checkout 在临时目录中，若被系统清理，必须提供仍可用的已验证 `--code-root`；
启动器不会偷偷替换后端版本。不带该参数会使用当前项目代码，非原录制基线。

无网络、无服务启动的配置检查（输出仅含密钥存在状态及非密钥配置）：

```powershell
.\.venv\Scripts\python.exe -B demo\start_course22.py --check --code-root C:\Users\Zwen\AppData\Local\Temp\dlo-deepseek-round2-20261021-01\checkout
```

直接运行 `python -m uvicorn ...` 不会自动加载 `.env`，请使用上述入口。
无需安装 dotenv；启动器只加载四项 Planner 配置，不改变代理设置。

## 当前可用入口

网页：http://127.0.0.1:52833/course-workspace

页面初始Workspace与任务输入均为空，不自动恢复上次任务或选择默认路径。原有“选择文件夹”弹窗支持浏览、面包屑、Go to path、Select This Folder；也可直接粘贴绝对路径。不存在或空目录路径不能启动。Run Agent前会实际读取所选目录的课程要求；无课程要求则真实报错，不伪造结果。

可供录制的一份尚未整理材料位于 `E:\Demo\DLO-Ready-80xjq65o`。这是文档中的可选资料位置，不是页面默认值或服务绑定；可先把其22文件整体复制到任意其他目录再选择。材料含相对分类去向，无需因迁移修改正文、Prompt或代码。

指令：请根据课程设计要求，整理当前工作空间中的全部22份材料。识别最终提交材料、源代码、实验数据、配置说明、历史版本和无关文件。请保留所有原始文件，先生成整理方案，得到我的确认后再创建分类文件夹并复制材料。

操作：自行选择或粘贴目录 → 输入上述指令 → Run Agent → 查看22项操作 → 批准 → 等待复制与验证22 → 在同一目录的资源管理器F5，查看课程设计_智能整理结果。

录制重置使用新的材料副本，不删除、覆盖已有结果。旧“自动准备并绑定Workspace”入口已移除；本页不会自行修改或重写用户选择的材料。

## 本次改动

- course22_demo.py：服务启动不再要求source、不创建/绑定默认Workspace；material-input仅处理当前请求显式提供的路径，校验目录、保存该次实际读取基线；audit使用独立evidence_id与Task Workspace绑定。已有结果目录拒绝覆盖。真实Planner、HTTP、审批、Executor和SHA验证未改。
- course22.html：移除预填、自动副本、sessionStorage恢复和固定目录拒绝条件；复用原有Browse，允许手动输入；有效目录及非空任务才允许Run。切换目录清空Task、Snapshot、preview、验证与结果，并通过请求序号丢弃过期校验/轮询响应。运行/审批请求进行时锁定选择控件。
- course22-browser.js：从frontend/index.html提取复用原有Directory Browser，保留browse API、Windows/UNC面包屑、快速路径跳转和Select This Folder；仅把原updateAgentControls回调替换为当前输入框input事件。
- test_course22_demo.py、course22_portability.cjs：增加无默认目录、非法路径、材料迁移和三盘符真实审批/复制/分类一致性检查。

没有修改A/C/D生产代码或API_CONTRACT.md。运行入口、模型输入、执行器中没有这三处测试目录的判断分支；ROUTES仅供独立材料生成，不参与所选目录的模型计划生成。运行时分类依据来自实际read_document正文；audit读取正文规则复核输出，不替模型选择类别。课程场景仍要求同一套已含Prompt的22文件，不宣称任意未知资料的通用分类准确率。

## 三个绝对路径实际验收

| 位置 | Task | 扫描/复制 | 审批 | 结果 |
|---|---|---|---|---|
| E:\Demo\DLO-A-78tcgoag | task_4051e31a5375449a8edf001ab522b445 | 22/22 | 1 | 通过 |
| D:\DLO-B-v2rwv95o | task_329b70d8f7ef4b91814d35ea75ba84eb | 22/22 | 1 | 通过 |
| C:\Users\Zwen\AppData\Local\Temp\DLO-C-4e9q4olj | task_edc0e4494a32454fb83ba972af09d655 | 22/22 | 1 | 通过 |

三个位置的输入字节一致，无迁移后修改材料。分类映射逐文件比较一致，六类数量2/4/5/3/7/1。每处审批前无输出目录，审批后输出目录在本Task选中Workspace内。22源文件SHA-256、大小、mtime不变；22目标各出现一次且SHA-256匹配。报告、自动verify_result及独立磁盘核验通过。Chrome 1920×1080，无页面脚本错误、无水平溢出。切换后显示新目录，旧Task与审批不复用。

证据：`E:\Demo\DLO22Portable\portable-rehearsals-1792595542039\acceptance.json`，同目录包含各次preview、result、截图、真实HTTP请求；读取输入和逐任务Snapshot/FinalReport在`E:\Demo\DLO22Portable\evidence`。旧失败测试日志保留：首个断言将面包屑分隔符误认路径；随后等待按钮而非目标目录的测试时序断言在第三Task创建前失败。修正测试后仅继续第三位置，未重复调用已通过的两个Task，也未隐去原记录。

## 本轮测试

- 设置PYTHONPATH为实际生产worktree的src后，python -B demo/test_course22_demo.py -v：7通过、0失败、0跳过。
- node --test frontend/tests/*.test.cjs：127通过、0失败、0跳过。
- node demo/course22_portability.cjs <server.json> <基准材料目录> <locations.json> [已有证据目录]：3个真实浏览器/HTTP/文件操作场景通过。可选最后参数仅从已保存结果继续未完成场景，不重新执行已成功任务。
- node --check demo/course22-browser.js / course22_portability.cjs，Python AST，git diff --check：通过。

服务启动维护命令：python -B demo/course22_demo.py --root <新证据目录> --code-root <生产worktree> --backend-url http://127.0.0.1:51851。没有Workspace命令行默认值；仅监听127.0.0.1，端口由OS分配，实际URL记入server.json。

## 真实性与限制

沿用用户启动的51851真实LLM Agent服务；生产基线f084b8a18198f61634c82e5bc12ee9bffc44f0f0。先用实际Scanner和read_document取得材料输入上下文，再交给现有Planner；不注入固定Plan、不伪造模型/工具记录、不用脚本提前整理文件。Task内再次扫描、读取、提取要求，只比较三份课程报告，审批后由现有工具创建/复制并由TaskService自动验证。未证明22文件全部正文语义分析，也未宣称课程内容审核齐全。

需要保持51851后端及本页服务运行；模型/网络仍有波动风险，三次通过不是未来绝对保证。不自动重试Task或审批。页面刷新不恢复旧Workspace/Task，避免误用旧计划；若录制中刷新，旧后端任务仍存在但不会自动被当前页批准。不关闭其他服务、不修改网络配置、不读取或记录API Key。本轮未提交、推送或合并。
