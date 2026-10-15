# 黑客松报名资料演示工作区

本目录仅用于 Digital Life Organizer 演示。人物、单位、经历、通知及证件内容均为虚构，
不得用于真实报名或身份核验。不包含真实身份证号码、学号、电话或地址。

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
| README_DEMO.md | 开发说明，不属于报名材料 |

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

README_DEMO.md 包含预期答案。正式 Agent 分析应通过已有且受支持的排除规则排除它，
不把它当通知或材料来源。若当前系统没有排除能力，请明确说明运行中含有答案说明，
不能据此宣称通过独立分析验收；不要为此加入文件名特判。

## 版本时间与跨机器复现

DOCX 内部 modified 属性记录了对应版本时间。本机文件 mtime 已设置为：
初版 2026-10-11 10:00、最终版 2026-10-14 16:30，均为 Asia/Shanghai。
Git 不保留文件系统 mtime，新 checkout 后两版时间可能接近。
如需验证基于 mtime 的选择，可从仓库根目录运行以下标准库脚本，仅恢复这两份演示文件的时间：

```python
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os

root = Path("demo/sample_workspace")
zone = timezone(timedelta(hours=8))
for name, value in [
    ("项目介绍_v1.docx", "2026-10-11T10:00:00"),
    ("项目介绍_最终版.docx", "2026-10-14T16:30:00"),
]:
    stamp = datetime.fromisoformat(value).replace(tzinfo=zone).timestamp()
    os.utime(root / name, (stamp, stamp))
```

不要对真实用户文件使用这段时间恢复脚本。

## 当前能力边界

本目录是实际输入数据，不是后端分析结果。当前公共 read_document 支持 TXT；
PDF/DOCX 解析、版本比较、任务分析和资料包生成仍需 C/D/A 对接。
学生证 JPG 主要用于文件发现及材料名称匹配，MVP 不要求 OCR。
最终判断必须由后端完成，不能把本 README 或 Mock 结果作为真实分析输出。
