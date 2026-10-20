# Package Fixture 前端

独立合成数据验收页，不调用模型、AgentAPI、Package HTTP 或文件操作接口。正式审批始终禁用；风险复选框只记录本地 UI 意向，不生成 preview_id 或服务端批准事实。

## 打开页面

直接在本机浏览器打开 `frontend/package-preview.html`（file URL），无需运行后端。
也可以使用已有静态服务器访问该文件；本阶段不要提交真实任务。

## 模块与数据

- `PackagePreview.render({planResult,snapshot,report})` 返回已转义 HTML，`inspect` 返回展示检查结果；不改变输入，不读取 Fixture，不执行审批。
- planResult 接收 `plan_package` ToolResult 的 `data.{plan,plan_sha256}`。展示唯一冻结 manifest，不构造第二套公共数据结构。
- snapshot 接收 TaskSnapshot；未来通过契约定义的 `package_execution` 的 operation_results/result_index、final_result_index 关联原始 results，禁止回退查找旧成功。
- report 接收 FinalReport；非 Package 可省略 package_unresolved。Package 必须提供与冻结方案一致的结构化风险；验证/执行关联不足时不声称成功。
- `package-fixtures.js` 仅包含虚构路径、ID、摘要和工具事实。摘要为合成占位值，不声称密码学验证通过。
- `package-demo.js` 管理场景及本地确认；场景、plan_id、摘要或方案内容变化均重置意向。
- 缺失任务、无效操作或结果记录显示数据不完整提示，并保留原始执行记录；未决来源索引必须与当前成功分析关联，否则保留原始风险并提示“未决事项来源关联无效”。本地风险意向不能消除这些警告。
- stale_success 中历史成功与当前失败使用不同方案身份；插入历史结果时同步调整当前分析、未决事项、子操作及最终结果索引，测试直接核对关联，不依赖场景文案。

Package schema 依据已合并 PR #29 和 PR #36；`cleanup_results` 四字段结构及安全记录规则已确认，但 Package Snapshot、审批、执行及清理能力均尚未实现。A 仍需完成分析来源重读、字节摘要复验及同次预览绑定。读取原始字段不构成支持实际执行的声明。前端检查仅用于保守展示，不能代替后端完整校验、摘要验证和授权。

## 本地检查

```powershell
node --test frontend/tests/package-preview.test.cjs frontend/tests/agent-results.test.cjs frontend/tests/agent-workspace.test.cjs frontend/tests/organization-preview.test.cjs
node --test frontend/tests/package-browser.cjs
```

浏览器检查使用本机 Chrome 和 Node 自带 WebSocket；可通过 CHROME_PATH 指向已有 Chrome/Edge，无需安装依赖。仅在系统临时目录建立隔离浏览器配置，结束后移除该配置；不操作任务 Workspace。CDP 只连接本机调试 WebSocket，测试页面使用 file URL，阻止并检查任何 HTTP(S) 请求。测试不访问外网。

## 人工浏览器验收

1. 打开页面，确认醒目的 Mock/Fixture 标识和禁用的正式审批按钮。
2. 选择 complete：核对目标、ID、摘要、文件源/目标、大小、依据、冻结操作和报告。多候选证据包含两个引用，但选材仍只是提议。
3. 选择 risks：逐项查看 missing 与四类未决事项；勾选风险意向，确认文案仅表示本地意向。切换场景后确认复选框清空。
4. 选择 success：缺项与风险仍保留；执行成功和文件验证不表示材料审核通过。
5. 选择 partial、cleanup_failed、unknown_residual：观察已成功操作、失败原因、清理记录与未知残留；不显示回滚保证。
6. 选择 bad_index、mismatch、missing_unresolved、stale_success：确认来源警告，不能回退到旧成功。
7. 选择 missing、null、empty、wrong_type、long、non_package：确认页面不崩溃、空与未知分离；390px 宽度不产生横向页面溢出。
8. 所有场景中正式审批始终禁用，开发者工具 Network 中没有 HTTP/API 请求。

## 真实接入依赖

等待 D 实现/导出冻结计划和报告，A 注册工具并实现当前 task/plan/digest/preview 绑定、风险接受、单次执行和结果索引关联、清理记录及成功 FinalReport 映射。未来只向展示模块提供真实对象；当前没有 plan_package/build_package HTTP 调用。approve 的 accept_incomplete 增量未接入，也不改变现有 Real Mode。失败任务保持 Snapshot 诊断，报告 409 不降级为普通成功。Matching/Version 和现有 Agent UI 未改动。
