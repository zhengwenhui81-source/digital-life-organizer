# 黑客松报名资料演示工作区

本目录仅用于 Digital Life Organizer 演示。人物、单位、经历、通知及证件内容均为虚构，
不得用于真实报名或身份核验。不包含真实身份证号码、学号、电话或地址。

## Clone 后一键准备

从仓库根目录运行（Python 3.11+，仅标准库，不需要安装项目依赖）：

```powershell
python demo/prepare_demo_workspace.py
```

脚本以自身位置定位 sample_workspace，与当前终端工作目录无关；也可通过绝对路径运行。
它预先检查全部九份输入是否存在且为普通文件，再恢复固定 mtime 并验证。
重复运行结果一致，不改内容，保留 atime，不删除文件，不创建目录或 Hackathon_Package。
缺失文件或符号链接会报错并退出，不补造材料。脚本不会清理先前演示产生的额外文件；
正式演示前请检查是否使用了未受污染的新 clone。它只恢复时间，不代表后端分析成功。

前端回归步骤见 [FRONTEND_DEMO_CHECKLIST.md](FRONTEND_DEMO_CHECKLIST.md)。

## 演示任务

帮我准备生成式人工智能黑客松报名资料。根据比赛通知找到需要提交的文件，
同一材料如果有多个版本选择最新版本，检查不同通知有没有冲突，缺少的材料告诉我，
最后生成一个报名资料包。执行文件操作前先让我确认。

## 输入文件

| 文件 | 作用 |
| --- | --- |
| 比赛通知.pdf | 初始报名要求与五项必交材料 |
| 补充通知.pdf | 调整截止时间，保留材料要求 |
| 报名表.docx | 已填写的虚构团队申请表 |
| 项目介绍_v1.docx | 初版项目方案 |
| 项目介绍_最终版.docx | 更新后的项目方案 |
| 学生证.jpg | 合法 JPEG，抽象头像，无真实证件信息 |
| 身份证.pdf | 明示无效的身份材料示意页 |
| 个人简历.docx | 个人背景，通知不要求提交 |
| 会议记录.txt | 无关的课程例会记录，UTF-8 |

sample_workspace 内只有上表九份材料。README、准备脚本、回归清单和 fixtures 均放在 demo/ 外层。

## 人工验收预期

- 同一版本组：项目介绍_v1.docx、项目介绍_最终版.docx。
- newest candidate：项目介绍_最终版.docx。两版保留共同背景、用户、场景、基础能力和团队分工；
  最终版更新定位，增加 local-first、Agent 工作流和文件操作前审批。
- deadline conflict：比赛通知.pdf 为 2026-10-18 18:00；
  补充通知.pdf 为 2026-10-20 18:00。保留两个来源，交由用户确认，前端不裁定答案。
- required materials：报名表、项目介绍、学生证、身份证、指导教师确认书。
- missing material：指导教师确认书故意缺失，不创建任何同名占位文件。
- irrelevant files：会议记录.txt；个人简历.docx 是非必交资料，不应自动加入资料包。
- 预期审批后创建 Hackathon_Package，并复制报名表.docx、项目介绍_最终版.docx、学生证.jpg、身份证.pdf。
- 资料仍不齐全，最终结果必须提示缺失项及通知分歧；四份文件并不代表满足全部报名要求。
- 不提前生成资料包，不删除或覆盖原文件，不自动移动旧版本；归档需要单独明确审批。

## 避免答案泄露

README_DEMO.md 包含人工验收答案，不应作为 Agent 输入，否则可能泄露版本候选、冲突与缺失项。
它已放在 demo/ 外层。Agent Workspace 必须精确选择 demo/sample_workspace，不能选择整个 demo/，
这样无需依赖额外排除功能，也不会读取说明文件或 JSON fixtures。不要加入文件名特判。

## 版本时间与跨机器复现

DOCX 内部 modified 属性包含版本元数据；版本场景使用准备脚本恢复的文件系统 mtime：
初版 2026-10-11 10:00、最终版 2026-10-14 16:30，均为 Asia/Shanghai。
Git 不保留文件系统 mtime，新 checkout 后两版时间可能接近。
每次 clone、checkout、解压或重新复制资料后，执行上述准备命令恢复全部九份输入的时间。
脚本使用带 +08:00 偏移的固定时间，不依赖本机时区或额外 tzdata 包；日期可能在本机
文件管理器中按当地时区显示，但对应时间点相同。完整时间表见 prepare_demo_workspace.py。

## 前端 fixtures

demo/fixtures/ 中四个 task_*.json 是 TaskSnapshot；final_report.json 是独立 FinalReport。
它们仅用于人工检查或临时 fetch stub，前端不会自动加载，不属于正式 Mock 流程，
也不能作为真实 Agent 结果或发送给实际审批接口。路径为虚构示例，不随 clone 位置变化。
具体用途及加载方式见前端回归清单。

## 当前能力边界

本目录是实际输入数据，不是后端分析结果。当前公共 read_document 支持 TXT；
PDF/DOCX 解析、版本比较、任务分析和资料包生成仍需 C/D/A 对接。
学生证 JPG 主要用于文件发现及材料名称匹配，MVP 不要求 OCR。
最终判断必须由后端完成，不能把本 README 或 Mock 结果作为真实分析输出。
