# Windows 离线浏览器联调（开发专用）

在仓库根目录使用已安装项目依赖的虚拟环境，一条命令启动并打开默认浏览器：

```powershell
.\.venv\Scripts\python.exe -B demo/run_offline_browser.py
```

服务仅在 `127.0.0.1` 上绑定，默认端口 `0` 由操作系统分配。终端打印的 URL、
浏览器 URL 与传给 Uvicorn 的**同一个已绑定 socket**一致；不会先探测再重新绑定。
无需使用 8765，不会停止其他程序或修改代理、系统网络配置。
可用 `--no-browser` 手动打开终端打印的 URL。显式 `--port N` 被占用时清楚退出，
不创建夹具或打开浏览器；改回默认 `--port 0` 即可。Ctrl+C 正常关闭服务并清理本次临时
数据；异常终止可能留下系统临时目录，不会清理任何用户 Workspace。
不安装依赖、不配置 API Key、不调用 OpenAI、不处理代理。

浏览器默认使用 **Real Mode HTTP**，但页首持续标注 **离线固定 Planner，非 LLM
推理**。点击 Run Agent，观察 Plan、真实要求提取、版本推荐、Matching 和最终报告。
自然语言只保留为任务标签；它不改变固定步骤，也不能用于验收自然语言理解。
工具默认每次延迟 0.35 秒方便观察，`--step-delay 0` 可取消显示延迟。

## 复用与隔离

- 不改生产 Planner、TaskService、HTTP 契约或生产 Real Mode 默认行为。
- 独立开发 FastAPI app 复用原 `/api/agent/tasks` 路由，使用现有
  `TaskService(planner=..., router=...)` 与 app-local dependency override。
- 每次启动只在系统 TemporaryDirectory 创建合成 TXT 输入；工具结果全部来自
  真实 list_files / read_document / extract_requirements / match_requirements /
  compare_versions，无伪造 Document、匹配或版本结果。
- 固定步骤：列出 notice → 读取 → 提取要求 → 列出 materials → 读取 → Matching
  → Version。两目录只是开发夹具布局，不是生产文件用途识别逻辑。
- 要求名称只存在于合成输入文本，Planner 不硬编码或选择材料；A 的现有参数解析
  负责传递提取要求、排除通知、保留候选。C/D 现有算法及限制完全保留。
- 仅允许本次生成的临时场景根目录，不允许用户真实 Workspace。开发 Router 在
  调用原 ToolRouter 前只放行上述五种只读工具，拒绝审批授权或任何写工具。
- 开发服务没有 `/api/scan`、配置写入或其他 FileForge 写入入口。审批接口保留
  原始语义，但这些计划不会产生 pending_operations，审批请求不能执行写操作。
- 原页面只在此开发响应中移除远程字体并附加 offline-browser.js。持续显示离线
  标签，禁用 Mock、Browse、Files、Settings、分类演示等无关入口；生产 index.html
  不引用这个脚本。CSP 限制网络到本机同源，不需要公网字体或其他在线资源。

## 场景与验收

| 场景 | 预期 |
| --- | --- |
| 单 / 多 / 零候选 | 真实提取三项要求，一项一个候选、一项两个候选、一项未找到；版本推荐不等于最终选择 |
| 有要求无候选 | 空候选读取按现有 A 逻辑 skipped，Matching 成功且全部进入 missing，Version 成功空分组 |
| 未提取到要求 | Matching 三个空数组，不表示材料齐全 |
| 空 TXT 读取失败 | 真实 read_document 失败，任务 failed，Matching 未执行，无 FinalReport |
| 无文件可读 | 无通知可读，任务 failed，后续工具未运行，报告 409 |

所有场景均无审批操作、无材料包。脚本只在启动时创建测试输入、退出时清理自己
的临时数据；Agent 不复制、移动、删除或创建任何文件。不支持任意真实 Workspace、
自定义目录布局、语义材料审核、生产 LLM 规划、Package 或实际写操作验收。

## 自动化验证

```powershell
.\.venv\Scripts\python.exe -B frontend/tests/offline-browser-smoke.py
.\.venv\Scripts\python.exe -B frontend/tests/offline-startup-smoke.py
node --test frontend/tests/*.test.cjs
.\.venv\Scripts\python.exe -B frontend/tests/matching-public-smoke.py
.\.venv\Scripts\python.exe -B frontend/tests/real-results-smoke.py
node --check frontend/offline-browser.js
node --check frontend/tests/offline-browser.cjs
git diff --check
```

HTTP 检查使用进程内 TestClient 与同一开发 app；不启动模型或注册虚假工具。
验证五种场景、真实数据/报告、审批 409、只读白名单、拒绝非临时路径、源文件 hash
和 mtime 不变。若受执行沙箱影响 TestClient 停滞，应在正常 Windows 终端运行。

可选浏览器自动化（需要已有 Playwright 和 Chrome，不自动下载依赖）：先以
`--no-browser` 启动脚本，再在另一个终端设置 `PLAYWRIGHT_MODULE` 为已安装模块
路径、`CHROME_PATH` 为本机 Chrome 可执行文件路径，执行：

```powershell
node frontend/tests/offline-browser.cjs
```

必须将 `UI_BASE_URL` 设置为本次终端打印的完整 URL（没有默认 8765），例如
`$env:UI_BASE_URL='http://127.0.0.1:实际端口'`。可设置 `UI_SCREENSHOT_DIR` 为已有截图目录。
检查 1280×720 与 1366×768 的真实 HTTP 场景、离线标记、0/1/N 候选、错误态、
页面溢出和外网/写接口请求。不会 stub HTTP 结果，不代表真实 LLM 验收。

启动回归只占用测试自己申请的随机端口模拟冲突，不访问或操作现有 8765 服务。
验证系统分配端口、socket 持续保留、浏览器仅在 ready 后使用实际 URL、显式冲突
不打开浏览器/创建夹具、启动异常清理，以及真实 Uvicorn 接收 SIGINT 后的目录清理。
