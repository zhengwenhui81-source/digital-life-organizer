# B Windows 项目验收与交付记录

日期：2026-10-21。dev：`b05ae3debec1f94b6e91ecc6b430cb3eda3d5ade`。
PR #51/#52/#53 已核对合并。测试基于该 dev；浏览器测试增强提交 `f408c8f`。
完整脱敏证据见同目录 `windows-delivery-b05ae3d.json`；原始 Snapshot/正文仅保留本机。
安装、操作和重现命令见 `frontend/WINDOWS_DELIVERY.md`。

总体 **blocked**，未宣称全项目通过、22 文件同任务通过或真实模型端到端通过。
本轮没有修改公共契约或 A/C/D 生产/测试文件，没有调用模型，没有使用私人 Workspace。

## 层级与真实达到的范围

| 项目 | 层级 | 实际依据 / 限制 |
| --- | --- | --- |
| Package Real Mode UI / 风险确认 / FinalReport | controlled_pass | 固定 Planner，真实 Windows Chrome、HTTP、工具、审批、创建和复制 |
| 真实小规模文档/要求/Matching/Version/Conflict 工具 | controlled_pass | 工具实际执行；候选不是审核通过，空冲突不是冲突识别准确率证明 |
| 任意目录动态发现 | tested | 新合成目录扫描确实发现22文件；没有真实模型处理任意用户目录的证据 |
| 完整22文件同一任务 | blocked | `Document batch exceeds 10 candidates`，未绕过上限 |
| 每文件完整分析覆盖 | unverifiable | 缺少权威 skipped / unsupported / limit 逐文件字段 |
| DeepSeek 真实端到端 | blocked | 未配置模型凭据/目标；仅检查存在性，没有读取或打印密钥，没有发请求 |
| Organization 动态演示及正式禁用壳 | tested | Node/Chrome隔离通过；仅 Fixture 渲染 |
| Organization 正式分类/修正/批准复制 | not_implemented | API_CONTRACT §8 NOT FROZEN，无 classify_files 正式工具 |
| 真实分类准确率/覆盖率 | blocked | 20文件人工答案存在，但没有实际分类决策；accuracy/coverage=null |
| 大整数、延迟响应、跨任务/工作流防护 | tested | Node 受控回归；未做真实浏览器网络故障注入 |
| 时间到期的 preview | unverifiable | 已验证错误身份/跨任务/重复409，但这不证明 TTL 到期 |
| 中断复制、未知残留、最终字节失败的真实HTTP故障 | blocked | 现有后端安全 seam 单测/前端 Fixture 不能代替真实故障验收 |

implemented 仅指代码存在；tested 指明确范围的自动检查通过；controlled_pass 指固定
Planner 下真实隔离执行；e2e_pass 要求真实模型和完整目标链路。本轮没有 e2e_pass。

## Windows Chrome + 真实 HTTP Package

| 场景 | 实际结果 |
| --- | --- |
| normal | completed，创建包目录、复制1文件、写报告、字节验证通过 |
| missing | 无 accept_incomplete 返回409，显式接受后真实执行成功；缺项/未决风险保留 |
| reject | failed，User rejected pending operations；不生成包，报告409 |
| changed | failed，Approved Package source differs from frozen preview；不生成包，报告409 |
| occupied | failed，Package destination is occupied or parent changed；既有 sentinel 不被覆盖 |
| partial_source_changed | 第一次真实复制成功后改变第二份合成源；第二次复制失败，报告409，不显示最终成功 |
| unrecognized_notice | blocked，No unambiguous material candidate can be proposed for Package；没有生成包 |

观察器 1 passed / 0 failed，但场景总体 blocked、e2e=false，不能把观察器退出0说成7项产品交付通过。
六个进入预览的任务验证错误 preview409、刷新恢复相同 preview、重复批准409；之后的任务
还验证跨任务 preview409。write_package_report 的 plan_id/digest、verify 的 task/workspace/
expected、执行映射、最终 build_package 及成功 verify_result 均与冻结计划对应。

两份完成包的材料源/目标/批准快照摘要均为：
`b4a056667a8035313fcff51c12de49e3e03ba1f79e270d8320472e37b726e418`。
报告与包相对路径、原始证据摘要、完整绑定标识列在 JSON；没有仅凭页面或 HTTP200 认定复制成功。
partial 场景保留第一次成功复制，不自动删除；cleanup 两条为 not_attempted/absent，分别
copy_succeeded / Source revalidation failed before target creation。absent 不表示成功文件回滚。
changed 与 partial 的第二份源是有意修改的本轮合成输入，不声称这两份被注入的源保持不变。

前一轮原观察器成功；增强断言第一次因测试错误地假设 verify 参数含 plan_id 而失败，
已按现有正式接口修正；最终全新目录增强观察器成功。失败轮次没有覆盖或计为通过。

## 22文件同任务与只读探针

新生成22 Package +20分类文件，人工标准答案未改，旧课程模板仍待提供。
同任务批量：`task_a090d29d44c94a0c85c446975445bbb5`，failed，
`Document batch exceeds 10 candidates`；已执行 list_files，扫描22文件，
未产生伪造 Document/Version。限制位置 `src/fileforge/agent/service.py` 的
`_MAX_CANDIDATE_READS = 10`；B 没有修改或绕开。

另22个显式单文件任务：16读取成功、6失败（空白、损坏、不支持输入）。
8文件子集真实工具已分析，之后 Package 规划遇到 `Source changed before reading`。
总计24任务：16 completed、8 failed。各文件证据是跨独立记录的下界，不是同任务完整覆盖。
22发现、16读取成功、6读取失败、8有明确分析成员证据；其余保持 unverifiable，
不能据扩展名/缺少结果推断后台主动跳过。详细逐文件状态见下表及 JSON。
42个源文件 SHA-256/mtime 均与 gold 一致，无意外文件；测试输出在 runs 而非源输入目录。
JSON/Markdown 原始报告已生成，报告总体 blocked（CLI 退出2为预期）。

## 自动回归实际结果

| 命令（仓库根目录） | 通过 | 失败 | 跳过 | 退出码 |
| --- | ---: | ---: | ---: | ---: |
| node --test frontend/tests/*.test.cjs | 127 | 0 | 0 | 0 |
| node --test frontend/tests/package-browser.cjs frontend/tests/organization-browser.cjs | 2 | 0 | 0 | 0 |
| PACKAGE_LIVE_MANIFEST 指定新临时目录后 node --test frontend/tests/package-live-browser.cjs | 1 | 0 | 0 | 0 |
| python -B -m unittest discover -s demo -p test_*acceptance*.py -q | 59 | 0 | 0 | 0 |
| python -B frontend/tests/matching-public-smoke.py | 6 | 0 | 0 | 0 |
| python -B frontend/tests/real-results-smoke.py | 3 | 0 | 0 | 0 |
| python -B frontend/tests/offline-browser-smoke.py | 5 | 0 | 0 | 0 |
| python -B frontend/tests/offline-startup-smoke.py | 5 | 0 | 0 | 0 |
| 既有Package跨模块pytest，第一轮 | 122 | 6 | 9 | 1 |
| 相同Package pytest复跑 | 121 | 7 | 9 | 1 |

上表 python 均使用 `.\.venv\Scripts\python.exe`，完整 Package pytest 命令在交付说明及 JSON。
59项另经 check-tools 实际执行，日志/代码指纹校验通过，不把复跑数累加成更多用例。
Chrome Fixture 在1366/390宽度运行22 Package场景、6整理场景及异常组合，检查长路径、
XSS、禁用审批、状态隔离；真实 HTTP Chrome 为另一项测试。没有人工交互浏览器验收声明。
9项跳过：7项无法创建符号链接，1项POSIX dir_fd，1项平台路径条件；不算通过。
环境为 Windows / Python 3.12.12 / Node v24.14.1 / Chrome 155.0.8059.85。
Python AST 15文件、JS语法10文件与页面inline脚本、报告JSON及22行结构、
个人绝对路径检查、git diff --check 均通过。原始报告只在临时目录保留；仓库报告使用占位根路径。

## 尚未完成与最小交接

**P0 / A：** 确定22文件资源限制及同任务覆盖能力。最小复现：共享工具 generate、probe；
保留 batch任务错误和 ToolResult，不能拆任务凑数。需要可解释的权威逐文件处理/限制记录，
字段须先走公共契约；B不自行添加。另确认 completed→Package预览的终态可见性，旧记录
曾观察到先普通完成再进入审批，本轮观察器显式刷新，不能证明默认终态竞态已解决。

**P0 / D，C独立验证：** Windows snapshot 间歇误拒绝。现有跨模块测试第一轮6失败，
第二轮7失败，用例随轮次变化；JSON列出第二轮失败名称。独立20个临时fixture，使用
`tests.test_package_planning.request_data.__wrapped__(Path(root))`，将 analysis置None后调用
`plan_package(**data)`，15成功/5失败，错误均为 `Source changed before reading`。
最小复现可运行既有 `tests/test_package_planning.py::test_unknown_and_failed_analysis`；
不修改源文件仍可能触发。快照签名时序是调查方向，不是本轮已证明的根因。

**P1 / D：** “报名时必须提交报名表。”未产生无歧义Package候选；使用现有
unrecognized_notice case复现，确认保守语法边界，不用前端补猜要求。

**P1 / A/C：** 复用既有测试 seam 的复制失败/验证失败/未知清理测试，补真实HTTP安全
故障注入证据及服务重启/到期策略；本轮已有测试通过不等于真实故障浏览器通过。
不能通过前端删除残留、修复实际文件或重新批准过期任务。

**Workflow2 / A/B/C/D：** 分类、证据、弃权、修正、路径碰撞、冻结预览、审批及逐文件
验证接口仍待共同冻结；B保留禁用入口，不实现第二执行器。95%目标无实际测量。

**环境：** 获准配置真实模型后再做DeepSeek完整链路；本轮不读取key文件、不排代理、
不充值、不消费额度。未知真实Workspace、真实LLM和完整22任务都没有通过证明。

## 逐文件状态（独立记录下界，非完整同任务）

| 文件 | discovered | read_success | read_failed | analyzed | not_processed_due_to_limit | needs_confirmation |
| --- | --- | --- | --- | --- | --- | --- |
| 通知_原版.txt | confirmed | confirmed | unverifiable | confirmed | unverifiable | unverifiable |
| 通知_补充.txt | confirmed | confirmed | unverifiable | confirmed | unverifiable | unverifiable |
| 结题报告_v1.txt | confirmed | confirmed | unverifiable | confirmed | unverifiable | unverifiable |
| 实验记录_v1.docx | confirmed | confirmed | unverifiable | confirmed | unverifiable | unverifiable |
| 结题报告_v2.txt | confirmed | confirmed | unverifiable | confirmed | unverifiable | unverifiable |
| 实验记录_v2.docx | confirmed | confirmed | unverifiable | confirmed | unverifiable | unverifiable |
| 费用清单.xlsx | confirmed | confirmed | unverifiable | confirmed | unverifiable | unverifiable |
| 费用凭证.pdf | confirmed | confirmed | unverifiable | unverifiable | unverifiable | unverifiable |
| 课程说明.docx | confirmed | confirmed | unverifiable | unverifiable | unverifiable | unverifiable |
| 项目总结.txt | confirmed | confirmed | unverifiable | unverifiable | unverifiable | unverifiable |
| 附件索引.txt | confirmed | confirmed | unverifiable | unverifiable | unverifiable | unverifiable |
| 预算草稿.xlsx | confirmed | confirmed | unverifiable | unverifiable | unverifiable | unverifiable |
| course_notes.pdf | confirmed | confirmed | unverifiable | unverifiable | unverifiable | unverifiable |
| personal_schedule.txt | confirmed | confirmed | unverifiable | unverifiable | unverifiable | unverifiable |
| 合影.png | confirmed | unverifiable | confirmed | unverifiable | unverifiable | unverifiable |
| 图像通知.png | confirmed | unverifiable | confirmed | unverifiable | unverifiable | unverifiable |
| 损坏记录.pdf | confirmed | unverifiable | confirmed | unverifiable | unverifiable | unverifiable |
| 损坏表格.docx | confirmed | unverifiable | confirmed | unverifiable | unverifiable | unverifiable |
| 空材料.txt | confirmed | unverifiable | confirmed | unverifiable | unverifiable | unverifiable |
| 未知数据.bin | confirmed | unverifiable | confirmed | unverifiable | unverifiable | unverifiable |
| 参考资料.txt | confirmed | confirmed | unverifiable | unverifiable | unverifiable | unverifiable |
| 签字页_待确认.txt | confirmed | confirmed | unverifiable | confirmed | unverifiable | unverifiable |
