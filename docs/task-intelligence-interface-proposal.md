# D 接口提案 — 待 A/B/C 确认

本文件是讨论稿，不是冻结契约。`API_CONTRACT.md` 保持不变。

## D1 已有契约与暂定编码

公共 Python 入口 `from fileforge.task_intelligence import detect_conflicts`，
调用 `detect_conflicts(documents=[document_a, document_b])`，对应现有 JSON
输入 `{"documents": [...]}`。沿用 C 的参数式调用与字典 ToolResult 惯例。
不新增字段、HTTP API 或工具注册。非法 Document 返回失败 ToolResult。

暂定细节集中在 `src/fileforge/task_intelligence/_encoding.py`：

- `source` 原样使用 `Document.path`，不访问磁盘、不重新解析路径。
  完整路径区分同名文件，UI 可展示 filename，但不能丢失来源。
- 泛化截止使用 `field="deadline"`；明确语义使用 `deadline:报名`、
  `deadline:提交`、`deadline:材料提交`、`deadline:申请`、`deadline:答辩`。
  不把不同标签直接合并。未知语义保守忽略。
- 材料使用 `field="required_documents:学生证"`，值为 `required` 或
  `not_required`；后者仅表示明确无需提交，不表示禁止提交。
- 日期规范化为 YYYY-MM-DD；明确时间为 YYYY-MM-DDTHH:MM:SS。
  不推断年份、时区；不同日期即使精度不同也比较。同日仅在双方明确时间时
  比较时刻，不把日期当午夜；报告冲突时保留该语义下全部来源和值。
- 同值不同来源均保留；相同值和来源重复去重；不选择正确来源。

示例（暂定编码）：

```json
{
  "success": true,
  "tool": "detect_conflicts",
  "data": {
    "conflicts": [
      {
        "field": "deadline:报名",
        "values": [
          {"value": "2026-10-18T18:00:00", "source": "/demo/a/通知.txt"},
          {"value": "2026-10-18T20:00:00", "source": "/demo/b/通知.txt"}
        ],
        "recommendation": "请人工确认"
      },
      {
        "field": "required_documents:学生证",
        "values": [
          {"value": "required", "source": "/demo/a/通知.txt"},
          {"value": "not_required", "source": "/demo/b/通知.txt"}
        ],
        "recommendation": "请人工确认"
      }
    ]
  },
  "message": "Conflict detection completed",
  "error": null
}
```

## 与现有契约/消费者的兼容边界

API_CONTRACT.md 示例仅使用 field="deadline"、日期字符串和文件名 source。
当前 deadline:报名 等编码不是该示例值；对 field === "deadline"、只解析日期
或假定 source 是 basename 的消费者不兼容。材料 field/value 也无既有定义。
只保证现有 envelope 和字段形状，不能宣称这些语义已兼容或已获批准。
目标提交的 frontend/index.html 未找到 detect_conflicts 消费者；不据此推断
其他开发者分支或未来消费者兼容。A/B/C 确认前不得作严格集成。

## D2 要求提取行为（已实现，公共输出沿用现有契约）

公共入口 `from fileforge.task_intelligence import extract_requirements`，调用
`extract_requirements(documents=documents)`。标准 ToolResult.data 严格为
`{"required_documents": ["报名表", "学生证"]}`，不增加来源或匹配字段。

D1/D2 共用内部材料证据解析器和输入校验。支持明确必交/无需提交语句、
“提交材料/所需材料/必交材料”标题后的连续简单编号/项目符号列表及标题行
冒号后的并列项。空行、普通段落、新标题结束标题作用范围；未知上下文不推断。
名称稳定去重、保留文档和文本中的首次必交出现顺序。嵌套缩进项不继承必交
语义；逗号可分隔明确正反语句，但拆分前先检查条件，避免脱离条件单独提取。

仅精确“（必交）”或“(必交)”标记可提升为必交；可选及未知括号不做删除后猜测。
明确否定与必交标记矛盾的单项保守跳过。条件项、任选组合不提升为必交。
同一材料有独立的必交与无需提交证据时，要求提取保留必交名称，否定不能静默
覆盖必交；detect_conflicts 单独保留双方来源并报告矛盾，不自动选正确来源。

D1 输出字段和暂定编码不变；由于共享解析器扩展，列表及明确必交标记也能
成为冲突证据。这是识别范围扩展，不代表相关暂定接口已经冻结。

## required_documents / matched / missing 最小方案（匹配未实现）

通知与候选材料由调用方分开提供：通知交给要求提取，候选材料交给匹配。
调用方保证属于同一任务并已执行 workspace 授权；不能把通知里提到的
“学生证”当成候选学生证。提取工具仍返回 `required_documents: string[]`。

建议匹配内部输入为 `required_documents: string[]`、`documents: Document[]`。
输出如下，Document 引用的值直接来自 C，不生成或修改身份：

```json
{
  "required_documents": ["报名表", "学生证"],
  "matched": [
    {
      "requirement": "报名表",
      "documents": [
        {
          "file_id": "file_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "path": "/demo/报名表.txt",
          "filename": "报名表.txt"
        }
      ]
    }
  ],
  "missing": ["学生证"]
}
```

- matched.requirement 对应原要求名称；documents 保留全部匹配候选，
  不自动挑选版本；不复制全文。
- missing 仅表示当前候选集合没有匹配，不保证整个 workspace 或机器不存在。
- 同一名称恰好归入 matched 或 missing，不另造 required 同义字段。
- 本轮不实现匹配、不增加或注册 match_requirements。

## 待确认事项

- A/B/C：上述 source、field、value 编码和截止语义分类是否接受；
  “无需提交”与“禁止提交”是否需要分别表达；日期精度差异的处理。
- A：匹配保持内部函数还是以后新增公共工具；候选来源和通知排除；
  失败传播、结果进入 TaskSnapshot.results 的方式及 FinalReport.missing_items 映射。
- B：来源路径展示、多个候选及空结果展示；不得依赖尚未确认的编码作严格 UI。
- C：Document 引用、材料别名以及版本候选的约定；不依赖 C 私有实现或
  未冻结的 newest_candidate 结构。
- 共同：先限定精确/规范化文件名匹配还是允许内容匹配；别名、任选组合、
  条件要求、数量和歧义的处理。确认后先更新 API_CONTRACT.md，再交付消费者。

## MVP 支持范围

仅识别独立分句的明确中文截止标签和完整公历日期（年/月/日、横线、斜线），
以及可选的 24 小时时分秒；不支持年份缺失、时区、自然语言相对日期或范围。
不推断不支持的语句，无冲突仅代表这些规则未发现冲突，不保证文档完全一致。
材料支持上文 D2 所述的明确语句、有限标题列表和精确必交标记；简单并列项
按顿号/逗号分隔，不把名称中的“和/及/与”拆开。不推断局部清单缺项、可选项、
条件或替代项。列表必须连续，空行后的列表不继承此前标题；不支持表格、
嵌套列表、跨段条件、复杂数量/选项组、材料别名或未知括号修饰。
匹配与 Package Builder 均未实现；所有待团队确认的接口仍是提案。
