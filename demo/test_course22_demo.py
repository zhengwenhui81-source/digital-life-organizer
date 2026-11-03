"""B material-input tests. No fixed Planner, no model or fabricated ToolResult."""
import tempfile
import unittest
from pathlib import Path
from course22_demo import ROUTES, NOTICE, OUTPUT, CATEGORIES, prepare, inventory, read_rules, material_input, selected_workspace

class CourseDemoTests(unittest.TestCase):
    def setUp(self):
        from docx import Document
        self.temp=tempfile.TemporaryDirectory(prefix='course22-input-');self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.source=self.base/'source';self.source.mkdir();self.takes=self.base/'takes';self.takes.mkdir()
        for name in ROUTES:
            if name.endswith('.docx'):
                d=Document();d.add_paragraph('课程材料，必须提交课程报告。');d.save(self.source/name)
            else:(self.source/name).write_bytes(b'synthetic input')

    def test_exact_mapping_originals_and_fresh_reset(self):
        before=inventory(self.source);one=prepare(self.source,self.takes);two=prepare(self.source,self.takes)
        self.assertEqual(before,inventory(self.source));self.assertNotEqual(one['workspace'],two['workspace'])
        self.assertEqual(len(ROUTES),22);self.assertEqual(len({m['target'] for m in one['mapping']}),22)
        self.assertNotEqual(one['baseline'][NOTICE]['sha256'],before[NOTICE]['sha256'])
        for n in ROUTES:
            if n!=NOTICE:self.assertEqual(before[n]['sha256'],one['baseline'][n]['sha256'])

    def test_context_contains_actual_scan_and_read_but_no_plan(self):
        rec=prepare(self.source,self.takes);root=Path(rec['workspace']);before=inventory(root);value=material_input(root)
        scan,read=value['tool_inputs'];self.assertEqual(scan['tool'],'list_files');self.assertTrue(scan['success']);self.assertEqual(len(scan['data']['files']),22)
        self.assertEqual(read['tool'],'read_document');self.assertTrue(read['success']);self.assertEqual(read['data']['document']['filename'],NOTICE)
        self.assertEqual(read_rules(read['data']['document']['text']),ROUTES);self.assertNotIn('steps',value)
        self.assertEqual(inventory(root),before);self.assertFalse((root/OUTPUT).exists())

    def test_changed_doc_rule_is_preserved_in_real_material_context(self):
        from docx import Document
        rec=prepare(self.source,self.takes);root=Path(rec['workspace']);doc=Document(root/NOTICE)
        for p in doc.paragraphs:
            if p.text.startswith('[整理规则] main.cpp => '):p.text='[整理规则] main.cpp => '+OUTPUT+'/'+CATEGORIES[4]+'/main.cpp'
        doc.save(root/NOTICE);value=material_input(root);text=value['tool_inputs'][1]['data']['document']['text']
        self.assertEqual(read_rules(text)['main.cpp'],CATEGORIES[4]);self.assertIn(text.splitlines()[-1],value['prompt_context'])
        with self.assertRaises(ValueError):read_rules(text+'\n[整理规则] main.cpp => ../outside/main.cpp')
        with self.assertRaises(ValueError):read_rules('没有完整规则')
        self.assertFalse((root/OUTPUT).exists())

    def test_unknown_inputs_and_unreadable_notice_rejected(self):
        (self.source/'unknown.txt').write_bytes(b'extra')
        with self.assertRaises(ValueError):prepare(self.source,self.takes)
        empty=self.base/'empty';empty.mkdir()
        with self.assertRaises(ValueError):material_input(empty)

    def test_selection_has_no_default_and_rejects_invalid_paths(self):
        for raw in ('', '   ', None, 'relative', str(self.base/'missing')):
            with self.assertRaises(ValueError):selected_workspace(raw)
        self.assertEqual(selected_workspace(str(self.source)),self.source.resolve())

    def test_identical_materials_are_read_at_new_location_without_rewriting(self):
        import shutil
        rec=prepare(self.source,self.takes);a=Path(rec['workspace']);b=self.base/'unrelated_name';shutil.copytree(a,b)
        before=inventory(b);first=material_input(a);second=material_input(b)
        self.assertEqual(first['tool_inputs'][1]['data']['document']['text'],second['tool_inputs'][1]['data']['document']['text'])
        self.assertNotEqual(first['tool_inputs'][1]['data']['document']['path'],second['tool_inputs'][1]['data']['document']['path'])
        self.assertNotIn(str(a),second['prompt_context']);self.assertEqual(before,inventory(b))

    def test_page_never_restores_or_prefills_a_workspace(self):
        html=Path(__file__).with_name('course22.html').read_text(encoding='utf-8')
        self.assertNotIn('sessionStorage',html);self.assertNotIn('c.workspace',html)
        self.assertRegex(html,r'<input id="workspace"[^>]*>');self.assertNotRegex(html,r'<input id="workspace"[^>]*\bvalue=');self.assertIn('apiReady=true',html)
        self.assertNotIn('E:\\Demo',html);self.assertIn("openBrowser('workspace')",html)
        original=Path(__file__).resolve().parents[1]/'frontend'/'index.html'
        reused=Path(__file__).with_name('course22-browser.js').read_text(encoding='utf-8')
        self.assertIn("fetch('/api/browse?path=' + encodeURIComponent(path))",reused)
        self.assertIn('var browserRequestId = 0;',reused)
        self.assertIn('function renderBreadcrumb(path, parent)',original.read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()
