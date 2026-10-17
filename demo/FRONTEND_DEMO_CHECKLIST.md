# 前端演示回归清单

这些复选框是待执行步骤，不代表当前后端能力已经通过验收。记录日期、提交 SHA、
浏览器、系统、Mock/Real 模式、实际结果和失败详情；Mock 成功不能替代 Real 集成验收。

## 准备与启动

- [ ] Python 3.11+，使用团队现有环境。初次 clone 若未安装项目，先在虚拟环境执行
  `python -m pip install -e .`；这是应用依赖，准备脚本本身不需要它们。
- [ ] 从仓库根目录运行 `python demo/prepare_demo_workspace.py`，确认九个 mtime 恢复成功。
- [ ] 确认 sample_workspace 只有九份原始输入；没有 README、fixtures、指导教师确认书
  或先前生成的 Hackathon_Package。准备脚本不会删除这些额外文件。
- [ ] 运行 `python -m fileforge server`，打开 http://localhost:8082/。
- [ ] 默认显示 Agent Workspace；Files、Settings 可访问。打开开发者工具 Console/Network。
- [ ] 桌面 1366×768、1920×1080 检查主要按钮、Plan 和审批区可读，页面无明显横向溢出。

## Browse 与输入

- [ ] 在 Workspace 中 Browse，进入本机 clone 的 demo/sample_workspace，选择当前目录。
  显示真实绝对路径；Windows 面包屑不产生 /E:/ 等错误路径。
- [ ] Files 的 Browse 同样能选择这个目录；选择目录本身不会启动 Scan 或修改文件。
- [ ] 清空 Workspace 或 Goal 时 Run Agent 禁用；填好两者后启用。
- [ ] Goal 使用 README_DEMO.md 中的主任务，Workspace 不要选择 demo/ 外层。

## Mock Mode Happy Path

- [ ] 选择 Mock Mode、Happy path；连续点击 Run Agent 只创建一个任务。
- [ ] 输入暂时锁定，状态显示 created/planning，Plan 逐步更新；Console 无异常。
- [ ] Mock 版本、冲突和材料结果显示。明确可见 Mock Mode，不宣称读取了真实文件。
- [ ] awaiting_approval 时自动轮询暂停，展示模拟操作与风险；等待时不会自行执行。
- [ ] 点击 Approve & Execute 后经历 executing/verifying/completed，不重复提交。
- [ ] Completed 展示统计、summary、模拟 Package Path；Copy Path 成功或给出明确权限错误。
- [ ] 磁盘没有新增包或变化的输入内容。Mock Cancel 显示 Task stopped；失败场景显示
  分析错误，剩余步骤可为 skipped；Task 不新增 cancelled/rejected 等状态。

## Real Mode backend unavailable

- [ ] 切到 Real Mode，Mock Scenario 选择器隐藏，切回 Mock 时恢复。
- [ ] 后端服务运行但 Agent 路由尚未提供时，Run 显示实际 HTTP 404/501 等错误，
  不出现模拟 Plan 或模拟成功，不切换到 Mock。按实际状态记录，不强行要求一定 404。
- [ ] 服务停止或断网时显示 Agent backend unavailable 或超时；恢复后可重新运行。
- [ ] Network 中没有未定义的 Agent 路径或偷偷读取 fixture 的请求。

## Approval 与 Final Report

在真实 API 可用时检查；尚不可用时用下一节 fixture 做独立 UI 检查，注明 stub。

- [ ] 展示 Snapshot 原样提供的 pending_operations 与 arguments，不拼造真实目标路径。
- [ ] preview_id=null 时不能审批；有有效 preview_id 时 approve/reject 请求携带完全相同的值。
- [ ] 连续点击不重复提交。409 时刷新 GET Snapshot 并提示预览失效，不自动重试 POST。
- [ ] 用户拒绝后显示 Task stopped，后端 Task 仍为 failed，不误报系统崩溃。
- [ ] 仅 completed 后请求 report；报告 409 时显示“最终报告尚未生成”，可 Refresh Task Status。
- [ ] FinalReport 缺少可选展示数据不崩溃；package_path 为空时无 Copy Path，不提供 Open Folder。
- [ ] 有路径时可复制；缺失材料和通知冲突仍应呈现，不能把部分资料包描述为全部材料齐全。

## JSON fixtures 的隔离使用

四个 task_*.json 对应 GET task 和审批响应的 TaskSnapshot；final_report.json 对应 GET report。
createTask 的响应应取 planning fixture 的 task 对象并使用 HTTP 202；其他成功响应为 200。
可以在临时 fetch stub 中按 planning → awaiting_approval → completed 的顺序返回快照，
或在页面控制台做独立渲染检查。现有服务器不提供 demo/fixtures 的 URL；不要添加路由。
先刷新页面，确保没有运行中的任务。使用开发者工具 Sources/Snippets 将所需 JSON
复制为局部变量，然后仅调用现有渲染函数；不要点击 Run / Approve / Cancel / Refresh：

```javascript
// const snapshot = <粘贴 task_*.json 的完整 JSON>;
agentState.mode = 'real';
renderAgent(snapshot);
// completed UI 另行：const report = <粘贴 final_report.json>;
// renderAgentReport(report);
// 完成后刷新页面清除人工状态，不向真实服务器使用 fixture 的 task_id/preview_id。
```

fixtures 不自动接入正式 Mock。preview_id 只是独立 UI 示例，不能用于真实审批。
未冻结的 newest_candidate、changes、matched/missing 嵌套结构保持空数组或不提供；
完成 fixture 的空结果也不表示真实工作区无冲突或无缺失。

## 错误态与演示前确认

- [ ] 使用临时 fetch stub 检查 400/404/409/500、非 JSON、空 results、空 pending_operations、
  plan 暂无数据、失败 ToolResult。错误可读，Console 无未处理异常。
- [ ] 自动轮询同一时间只有一个循环；awaiting_approval/completed/failed 停止，
  连续刷新不创建并行请求，网络错误不自动重试文件操作。
- [ ] 核对当前后端支持格式；学生证 JPG 不要求 OCR。无法完成 Real 链路时如实说明。
- [ ] 正式演示使用的输入、模式、审批范围和复制目标均已确认，保留旧版本，不覆盖文件。
- [ ] README 和 fixtures 不在 Agent 输入范围；本机路径已填写，不使用其他成员硬编码路径。
- [ ] `git diff --check` 通过；准备脚本重跑不改变输入文件 SHA-256。
