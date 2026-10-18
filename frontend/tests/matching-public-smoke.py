"""Actual public D tool -> B renderer, in-memory only; NOT Agent HTTP acceptance.

No model, disk reads/scans, Workspace writes, or registry injection.
Run: .venv/Scripts/python.exe -B frontend/tests/matching-public-smoke.py
"""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fileforge.task_intelligence import match_requirements


def document(filename, identity):
    return {
        "file_id": "file_" + identity * 64,
        "path": "E:\\synthetic-not-on-disk\\" + filename,
        "filename": filename,
        "extension": ".txt",
        "text": "Synthetic in-memory document; no content-review claim.",
        "size": 1,
        "modified_time": "2026-10-18T08:00:00+00:00",
        "metadata": {},
    }


def main():
    documents = [document("申请表_v2.txt", "b"), document("申请表.txt", "a")]
    cases = [
        ([], [], "没有明确的材料要求"),
        (["申请表"], documents[:1], "1 个文件名候选"),
        (["申请表", "证明"], documents, "2 个文件名候选"),
        (["证明"], documents, "本次未找到文件名候选"),
        (["申请表"], [], "本次未找到文件名候选"),
        (["申请表"], [{}], "工具执行失败"),
    ]
    node = """
const fs=require('node:fs'),assert=require('node:assert/strict'),ui=require('./frontend/agent-results.js');
const {result,expected}=JSON.parse(fs.readFileSync(0,'utf8')), before=JSON.stringify(result);
const html=ui.matching(result);assert.ok(html.includes(expected));
assert.equal(JSON.stringify(result),before);
if(result.success)for(const entry of result.data.matched){
 let position=-1;
 for(const doc of entry.documents){
  const next=html.indexOf(doc.file_id,position+1);assert.ok(next>position);position=next;
  assert.ok(html.includes(doc.path));assert.ok(html.includes(doc.filename));
 }
} else assert.ok(html.includes(result.error.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')));
"""
    for requirements, candidates, expected in cases:
        result = match_requirements(requirements, candidates)
        subprocess.run(
            ["node", "-e", node], cwd=ROOT,
            input=json.dumps({"result": result, "expected": expected}),
            text=True, check=True,
        )
    print("PASS 6 actual public Matching -> frontend renderer cases (no HTTP/model/filesystem operations)")


if __name__ == "__main__":
    main()
