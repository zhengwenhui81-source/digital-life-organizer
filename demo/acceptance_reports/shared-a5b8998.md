# 共享验收工具实际运行摘要

- 基线：a5b89985ec24f536b9445823c783a273c672730f
- 环境：Windows / Python 3.12.12
- 总体：blocked；工具测试通过不等于端到端通过。
- 人工标准答案未修改；只读观察覆盖数量是独立证据下界，不能拼成同一任务。
- 原始证据保留在本机临时数据目录；本摘要不包含正文或本机绝对路径。

| 层级 | 本轮结果 |
| --- | --- |
| 合成数据 | 22 个 Package + 20 个分类文件已生成 |
| 工具单测 | 53 passed / 0 failed / 0 skipped，退出 0 |
| 受控 TaskService | 24 个独立任务；16 completed、7 failed、1 awaiting_approval |
| 同任务完整 22 文件分析 | blocked：Document batch exceeds 10 candidates |
| 分析子集 | 8 文件；真实工具成功；停在 awaiting_approval，未批准 |
| Windows 浏览器 | not_run |
| DeepSeek 端到端 | not_run；提供商身份 unverifiable |
| 真实分类准确率 | blocked；没有真实决策，accuracy/coverage=null |
| Package 批准执行 | not_run；approvals_sent=0 |

## 实际命令与报告

generate、probe、check-tools 退出 0；JSON/Markdown report 各退出 2（blocked 预期）。
具体命令、原始证据/日志/报告 SHA-256、逐文件状态及测试代码指纹见同目录 JSON。
单文件读取任务：16 成功、6 失败，失败包括空/损坏/不支持输入。
分析子集完成 detect_conflicts、extract_requirements、compare_versions、match_requirements、plan_package。
不把审批前计划或 plan_package 成功说成 build_package 执行成功。

## 原件与人工标准答案

两数据集共 42 个原始文件的 SHA-256 / 大小 / mtime 与 gold 基线完全一致。
gold_sha256：19d9d8506a6ab666bbdc361fab27302c7c50c898757e5ac58e493c030d9a1a53
现有真实课程 22 行待提供模板保持不变；合成数据不填充该模板。

## 逐文件证据状态（不是完整任务覆盖）

| 文件 | discovered | read_success | read_failed | unsupported | not_processed_due_to_limit | analyzed | needs_confirmation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 通知_原版.txt | confirmed | confirmed | unverifiable | unverifiable | unverifiable | confirmed | confirmed |
| 通知_补充.txt | confirmed | confirmed | unverifiable | unverifiable | unverifiable | confirmed | confirmed |
| 结题报告_v1.txt | confirmed | confirmed | unverifiable | unverifiable | unverifiable | confirmed | confirmed |
| 实验记录_v1.docx | confirmed | confirmed | unverifiable | unverifiable | unverifiable | confirmed | confirmed |
| 结题报告_v2.txt | confirmed | confirmed | unverifiable | unverifiable | unverifiable | confirmed | confirmed |
| 实验记录_v2.docx | confirmed | confirmed | unverifiable | unverifiable | unverifiable | confirmed | confirmed |
| 费用清单.xlsx | confirmed | confirmed | unverifiable | unverifiable | unverifiable | confirmed | confirmed |
| 费用凭证.pdf | confirmed | confirmed | unverifiable | unverifiable | unverifiable | unverifiable | unverifiable |
| 课程说明.docx | confirmed | confirmed | unverifiable | unverifiable | unverifiable | unverifiable | unverifiable |
| 项目总结.txt | confirmed | confirmed | unverifiable | unverifiable | unverifiable | unverifiable | unverifiable |
| 附件索引.txt | confirmed | confirmed | unverifiable | unverifiable | unverifiable | unverifiable | unverifiable |
| 预算草稿.xlsx | confirmed | confirmed | unverifiable | unverifiable | unverifiable | unverifiable | unverifiable |
| course_notes.pdf | confirmed | confirmed | unverifiable | unverifiable | unverifiable | unverifiable | unverifiable |
| personal_schedule.txt | confirmed | confirmed | unverifiable | unverifiable | unverifiable | unverifiable | unverifiable |
| 合影.png | confirmed | unverifiable | confirmed | unverifiable | unverifiable | unverifiable | unverifiable |
| 图像通知.png | confirmed | unverifiable | confirmed | unverifiable | unverifiable | unverifiable | unverifiable |
| 损坏记录.pdf | confirmed | unverifiable | confirmed | unverifiable | unverifiable | unverifiable | unverifiable |
| 损坏表格.docx | confirmed | unverifiable | confirmed | unverifiable | unverifiable | unverifiable | unverifiable |
| 空材料.txt | confirmed | unverifiable | confirmed | unverifiable | unverifiable | unverifiable | unverifiable |
| 未知数据.bin | confirmed | unverifiable | confirmed | unverifiable | unverifiable | unverifiable | unverifiable |
| 参考资料.txt | confirmed | confirmed | unverifiable | unverifiable | unverifiable | unverifiable | unverifiable |
| 签字页_待确认.txt | confirmed | confirmed | unverifiable | unverifiable | unverifiable | confirmed | confirmed |

## 仍然受限

- 批量读取上限 10，不修改 A 的生产限额，也不累计独立探针冒充同任务处理。
- unsupported/limit 等逐文件状态缺少权威映射时保留 unverifiable，不凭文件名猜测。
- classify_files 契约/真实适配未冻结；指标计算器只是规则与算术，不是分类实现。
- 本轮未启动浏览器、调用模型、发送审批或复制；没有真实 LLM/Package/分类全链路证据。
- 记录是本地证据，不是加密服务端证明；源捕获/审批/字节验证仍需独立真实联调。
