# Package Builder 第一阶段 — 待 A/B/C 确认

这是私有规划原型和接口提案，不是冻结契约。API_CONTRACT.md 不变。
本阶段不具备实际打包执行能力：不创建目录、不复制、不写报告、不进行文件验证，
不注册或导出可执行公共 build_package，不生成公开 package ToolResult。

## 私有输入与路径规则

`_plan_package(task_id, requirements, selected_files, destination)` 接收调用方已选定
的文件引用 `{file_id, path, filename}`，不调用匹配器，不选择版本。额外引用字段忽略。
要求是非空字符串数组，可整体为空；selected_files 必须非空。名称/身份不自动纠正。
相同身份和来源稳定去重；同 ID 不同来源、同来源不同 ID/文件名拒绝。

destination 就是最终包目录。例如 `/workspace/demo/Hackathon_Package`，不会再次
追加目录名；是否默认选这个名称由后续调用方决定。本机 POSIX 接受绝对 POSIX 路径；
本机 Windows 只接受绝对本地盘符路径；UNC、URL、相对路径、波浪号、空路径段、
`.`、`..` 及异平台格式拒绝，Windows 路径不会被当作 POSIX 普通文件名。

源文件 basename 必须与 filename 一致。所有文件/目录组件都保守拒绝 Windows
非法字符、控制字符、设备保留名、尾随点/空格；目标名称按 Unicode NFC + casefold
检测重名，包括 PACKAGE_REPORT.md 的保留名。不改写实际输出名称或来源 file_id。
这些规则可能拒绝 POSIX 合法的文件名，目的是保守避免跨平台重名/误解，不保证
所有文件系统完全等价。仅做词法处理，不 resolve、不 stat、不探测大小写规则、
符号链接、权限或文件存在性。后续仍必须执行本机预检和执行时复检。

## 暂定内部计划

以下结构只供 D 内部测试/迭代，不供 A/B 直接依赖：

```json
{
  "status": "planned",
  "task_id": "task_1",
  "requirements": ["报名表"],
  "planned_package_path": "/workspace/demo/Hackathon_Package",
  "copies": [
    {
      "source_file_id": "file_example",
      "source": "/workspace/demo/报名表.pdf",
      "filename": "报名表.pdf",
      "destination": "/workspace/demo/Hackathon_Package/报名表.pdf"
    }
  ],
  "planned_report_path": "/workspace/demo/Hackathon_Package/PACKAGE_REPORT.md",
  "verification_targets": {
    "base": "/workspace/demo/Hackathon_Package",
    "files": ["报名表.pdf", "PACKAGE_REPORT.md"],
    "archive": []
  }
}
```

verification_targets.files 相对于内部 base，不能直接作为 A 当前相对于 workspace
的 expected.files。A 适配器必须校验包目录处于已授权 workspace，并转换相对路径。
这些是预期目标，不能当作已生成文件清单。

`_render_plan_report(plan, conflicts=None, missing=None)` 返回 Markdown 字符串。
只渲染 planned 状态；校验目标与纯计划器一致，不允许篡改后伪装成功。
冲突/缺项未传时写“未提供分析结果”；明确 `[]` 时标注调用方提供空结果。
报告包含任务、要求、来源到计划目标，显著写“尚未执行、尚未验证”。
用户文本按 HTML/Markdown 转义，换行不能注入标题或破坏表格。分析数据须可 JSON
序列化。渲染不读取源文件、不推断缺项，也不生成完成报告。

## 未来公共成功输出（提案，尚未实现）

公开输入仍以 API_CONTRACT.md 的 task_id/requirements/selected_files/destination
为边界；selected_files 元素是否采用上述引用格式，须 A/C 确认。
只有执行和验证真正成功后，才可能返回以下候选结果：

```json
{
  "success": true,
  "tool": "build_package",
  "data": {
    "package_path": "/workspace/demo/Hackathon_Package",
    "generated_files": [
      {
        "kind": "material",
        "source_file_id": "file_example",
        "source": "/workspace/demo/报名表.pdf",
        "path": "/workspace/demo/Hackathon_Package/报名表.pdf"
      },
      {
        "kind": "report",
        "source_file_id": null,
        "source": null,
        "path": "/workspace/demo/Hackathon_Package/PACKAGE_REPORT.md"
      }
    ],
    "report_path": "/workspace/demo/Hackathon_Package/PACKAGE_REPORT.md",
    "verification_targets": {
      "files": ["Hackathon_Package/报名表.pdf", "Hackathon_Package/PACKAGE_REPORT.md"],
      "archive": []
    }
  },
  "message": "Package created and verified",
  "error": null
}
```

上述公共 targets 示例相对于 `/workspace/demo` workspace，与内部 base 不同。
source_file_id 只标识来源；复制后的 Document 身份不能沿用来源身份。
失败仍遵循既有 envelope：success=false、data=null；不能私自增加失败 data。

## A 审批、执行及验证接入（未实现）

只读预检来源、权限、目录及身份快照后，A 冻结具体建目录、每次复制与报告创建
操作，绑定 preview_id；路径、名称及报告生成规则必须在批准前确定。
批准由 A 的任务服务消费，不能通过公共参数 approved=True 自报授权；D 不绕过。
执行默认复制、独占创建，禁止删除来源和静默覆盖。目标变化后不能自动改名重试，
必须重新规划和批准。报告写入同样属于受批文件操作，不是渲染器的副作用。

已检查 A 分支 39f4149：TaskService._validate_preview 只允许 create_folder/
copy_file/move_file；ToolRouter 未接通 build_package 授权，尚无报告写入公共工具。
完整 build_package 预览与执行适配须 A 实现/确认，本阶段不能直接注册替代。

A 当前 verify_result 仅检查 expected.files/archive 的文件存在性，不验证内容。
还须明确调用验证并检查 data.passed（不能只看 success），才可宣称验证通过。
是否增加 SHA-256、大小、来源未变以及报告内容校验，由 A/C/D 共同确认。

## 待决定事项

- A/B/C：selected_files 格式、实际 package_path、generated_files、report_path 和
  verification_targets 的最终字段，以及 FinalReport 映射。确认后再更新共享契约。
- A/D：复合操作的冻结 manifest、授权传递、批准后来源变化检测和再次批准策略。
- A/D：执行失败立即停止后，如何记录部分完成；失败 envelope 保持 data=null，
  已完成操作须在任务结果中保留，不得虚构完整包或自动回滚删除用户文件。
- A/D：自身新建残片是否允许清理，部分目录/报告失败如何展示与恢复；未确认前
  不借用已有工具的残片删除行为来假定授权。
- A/B/D：报告内容冻结与后续真实执行状态的绑定，实际完成报告的生成和独占写入。
- A/C/D：来源快照/校验和、符号链接、运行平台、目录已占用的预检规则。

下一阶段仍需审批接入、实际复制、报告落盘和执行验证，才能完成 build_package。
