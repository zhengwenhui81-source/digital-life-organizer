# C → D 本地开发演示

这是 C 公共 TXT 读取器与 D 分析工具的开发演示，不是 A 的工具注册、
Agent 调度、真实 UI 接入或公共 API。仓库尚无 examples 目录，因此复用 scripts。

在仓库根目录、已安装项目及开发依赖的 Python 环境运行：

```bash
python -m pip install -e '.[dev]'
python scripts/task_intelligence_demo.py
python -m pytest -q tests/test_task_intelligence_integration.py
```

本次云环境已有依赖环境时可直接使用：

```bash
/tmp/dlo-d1-venv/bin/python scripts/task_intelligence_demo.py
```

脚本通过 TemporaryDirectory 创建两份 UTF-8 TXT，使用公共入口：

```python
from fileforge.document import read_document
from fileforge.task_intelligence import detect_conflicts, extract_requirements
```

每个 `read_document(path=...)` 成功后，从 `data.document` 获取真实 Document。
任一读取失败时，输出读取结果且 analysis=null，不调用 D 的工具，退出码为 1。
成功时输出 JSON 中的 read_results 和 analysis（仅为演示容器，不是新增共享契约）。
预期产生两个冲突：报名截止 2026-10-18/2026-10-20，学生证必交/无需提交；
required_documents 顺序为报名表、学生证、项目介绍。矛盾的否定不覆盖必交要求。
所有临时 TXT 自动清理，输出中的路径随后不再存在；不扫描用户目录，不整理、
打包或覆盖现有文件。工具分析成功不代表通知没有冲突，需人工确认矛盾。

限制：C 当前公共入口仅支持非空 TXT；D 使用保守的中文规则，仅识别有限截止
标签、完整日期/明确时间、简单材料语句及有限列表。这里未验证多格式、模型、
工作区授权、版本选择或端到端 Agent/UI。生产调用方仍须执行 workspace 授权。

source 完整路径、field/value 编码及 matched/missing 方案仍待 A/B/C 确认，
参见 task-intelligence-interface-proposal.md；集成测试验证当前代码能互通，
不等于接口已冻结。本轮未实现匹配、工具注册、前端接入或 Package Builder。
