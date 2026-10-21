"""Synthetic unit inputs test evidence rules; they are NOT real Agent acceptance."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import shared_acceptance as tool
from acceptance_datasets import package_rows, classification_rows


class SharedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='shared-evidence-unit-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'independent'
        tool.generate(self.root)
        _, self.gold, self.sha = tool.baseline(self.root)
        self.files = self.gold['workflows']['package']['files']

    def snapshot(self, name=None, success=True):
        goal = '只读读取验收文件 ' + name if name else tool.GOAL
        args = {'path': str(self.root / 'package' / name)} if name else {'workspace': str(self.root / 'package'), 'recursive': False}
        typ = 'read_document' if name else 'list_files'
        doc = {'file_id': 'synthetic-test-id', 'path': args.get('path'), 'filename': name, 'size': self.gold['workflows']['package']['baseline'][name]['size'] if name else 0, 'text': 'synthetic unit content', 'metadata': {}}
        data = {'document': doc} if name else {'files': [{'path': str(self.root / 'package' / row['path'])} for row in self.files]}
        result = {'tool': typ, 'success': success, 'data': data if success else None, 'message': 'unit result', 'error': None if success else 'unit read failure'}
        return {'task': {'task_id': 'task_unit', 'user_goal': goal, 'workspace': str(self.root / 'package'), 'status': 'completed' if success else 'failed'},
                'plan': {'task_id': 'task_unit', 'goal': goal, 'steps': [{'step_id': 'only', 'tool': typ, 'arguments': args}]}, 'results': [result], 'package_execution': None, 'error': None if success else 'unit read failure'}

    def artifact(self, snapshot, tag='batch'):
        record = {'schema': tool.SCHEMA, 'gold_sha256': self.sha, 'kind': 'controlled_agent_read_only',
                  'environment': {'system': 'SyntheticUnitNotRealWindows'}, 'command': 'synthetic unit test only',
                  'observations': [{'tag': tag, 'task_id': snapshot['task']['task_id'], 'goal': snapshot['task']['user_goal'], 'snapshot': snapshot}]}
        path = self.root / 'runs' / 'unit.json'
        path.write_bytes(tool.json_bytes(record))
        return path

    def test_meaningful_22_gold_and_non_course_classification_20(self):
        self.assertEqual(len(package_rows()), 22)
        self.assertEqual(len(classification_rows()), 20)
        self.assertEqual(sum(not row['data'] for row in package_rows()), 1)
        self.assertTrue(all('expected_handling' in r and 'expected_version' in r and 'purpose' in r for r in self.files))
        org = self.gold['workflows']['classification']['files']
        self.assertTrue(any(r['must_abstain_purpose'] for r in org))
        self.assertTrue({'finance', 'travel', 'housing', 'home_maintenance'} <= {r['human_category'] for r in org})
        self.assertEqual(self.gold['workflows']['package']['expected_filename_absence'], ['验收意见'])

    def test_dataset_is_reproducible_and_gold_not_output_driven(self):
        other = Path(self.temp.name) / 'other'
        tool.generate(other)
        _, gold, _ = tool.baseline(other)
        self.assertEqual(self.gold['workflows'], gold['workflows'])
        with self.assertRaises(FileExistsError):
            tool.generate(self.root)
        with self.assertRaises(ValueError):
            tool.generate(Path('relative-directory'))

    def test_changed_gold_rejected_instead_of_relabeling_to_pass(self):
        value = copy.deepcopy(self.gold)
        value['workflows']['classification']['files'][0]['human_category'] = 'easy-new-label'
        (self.root / 'gold.json').write_bytes(tool.json_bytes(value))
        with self.assertRaises(ValueError):
            tool.report(self.root)

    def test_no_evidence_means_unverifiable_not_coverage_or_95_success(self):
        r = tool.report(self.root)
        self.assertEqual(r['status'], 'blocked')
        self.assertIsNone(r['classification']['purpose_accuracy'])
        self.assertEqual(r['layers']['deepseek']['status'], 'not_run')
        self.assertEqual(r['coverage']['discovered']['confirmed'], 0)
        self.assertTrue(all(v['state'] == 'unverifiable' for row in r['files'] for v in row['states'].values()))

    def test_discovery_is_positive_evidence_not_implicit_read_or_unsupported(self):
        r = tool.report(self.root, self.artifact(self.snapshot()))
        self.assertEqual(r['coverage']['discovered']['confirmed'], 22)
        for state in ('read_success', 'unsupported', 'not_processed_due_to_limit'):
            self.assertEqual(r['coverage'][state]['confirmed'], 0)
        self.assertNotEqual(r['layers']['deepseek']['status'], 'passed')

    def test_single_explicit_read_binds_success_and_failure_without_index_guessing(self):
        name = self.files[0]['path']
        for success, state in ((True, 'read_success'), (False, 'read_failed')):
            r = tool.report(self.root, self.artifact(self.snapshot(name, success), 'read:' + name))
            self.assertEqual(r['coverage'][state]['confirmed'], 1)
            evidence = r['files'][0]['states'][state]['evidence'][0]
            self.assertEqual(evidence['task_id'], 'task_unit')
            self.assertEqual(evidence['result_index'], 0)

    def test_dynamic_failure_has_no_authoritative_per_file_failed_or_skipped_list(self):
        s = self.snapshot(self.files[0]['path'], False)
        s['plan']['steps'][0]['arguments'] = {}
        s['error'] = 'Document batch exceeds 10 candidates'
        r = tool.report(self.root, self.artifact(s, 'read:' + self.files[0]['path']))
        self.assertEqual(r['coverage']['read_failed']['confirmed'], 0)
        self.assertEqual(r['coverage']['not_processed_due_to_limit']['confirmed'], 0)

    def test_foreign_task_workspace_goal_and_bad_result_reject_entire_artifact(self):
        changes = [lambda s: s['task'].update(task_id='foreign'), lambda s: s['task'].update(workspace=str(self.root)),
                   lambda s: s['task'].update(user_goal='foreign'), lambda s: s['results'][0].update(data=None)]
        for change in changes:
            s = self.snapshot()
            p = self.artifact(s)
            record = tool.loads(p.read_bytes())
            change(record['observations'][0]['snapshot'])
            p.write_bytes(tool.json_bytes(record))
            r = tool.report(self.root, p)
            self.assertEqual(r['coverage']['discovered']['confirmed'], 0)
            self.assertEqual(r['tool_results'], [])
            self.assertTrue(any('rejected' in i['reason'] for i in r['issues']))

    def test_duplicate_or_stale_task_observations_are_not_merged(self):
        path = self.artifact(self.snapshot())
        record = tool.loads(path.read_bytes())
        record['observations'].append(copy.deepcopy(record['observations'][0]))
        path.write_bytes(tool.json_bytes(record))
        r = tool.report(self.root, path)
        self.assertEqual(r['coverage']['discovered']['confirmed'], 0)
        self.assertNotEqual(r['status'], 'passed')

    def test_analyzed_needs_explicit_same_identity_not_a_successful_empty_analysis(self):
        name = self.files[0]['path']
        s = self.snapshot(name)
        r = {'tool': 'compare_versions', 'success': True, 'data': {'groups': []}, 'message': 'synthetic', 'error': None}
        s['results'].append(r)
        self.assertEqual(tool.report(self.root, self.artifact(s, 'read:' + name))['coverage']['analyzed']['confirmed'], 0)
        r['data']['groups'] = [{'documents': [copy.deepcopy(s['results'][0]['data']['document'])]}]
        self.assertEqual(tool.report(self.root, self.artifact(s, 'read:' + name))['coverage']['analyzed']['confirmed'], 1)
        r['data']['groups'][0]['documents'][0]['file_id'] = 'wrong'
        self.assertEqual(tool.report(self.root, self.artifact(s, 'read:' + name))['coverage']['analyzed']['confirmed'], 0)

    def test_original_bytes_and_mtime_change_fail_even_without_execution(self):
        p = self.root / 'package' / self.files[0]['path']
        p.write_bytes(b'changed-original')
        r = tool.report(self.root)
        self.assertEqual(r['status'], 'failed')
        self.assertIn(self.files[0]['path'], r['filesystem']['package']['changed_or_missing'])

    def test_report_json_markdown_are_readonly_and_blocked_exit_two(self):
        before = tool.inventory(self.root)
        for fmt in ('json', 'markdown'):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code = tool.main(['report', '--directory', str(self.root), '--format', fmt])
            self.assertEqual(code, 2)
            self.assertIn('blocked', output.getvalue())
        self.assertEqual(tool.inventory(self.root), before)

    def test_no_cherry_picked_subset_counts_as_accuracy(self):
        rows = self.gold['workflows']['classification']['files']
        one = [{'path': rows[0]['path'], 'label': rows[0]['human_category'], 'method': 'purpose_from_content', 'evidence': 'unit'}]
        self.assertEqual(tool.classification_metrics(rows, one)['status'], 'unverifiable')

    def test_type_grouping_and_abstention_do_not_inflate_purpose_accuracy(self):
        rows = self.gold['workflows']['classification']['files']
        decisions = [{'path': r['path'], 'label': r['human_file_type'], 'method': 'file_type_only', 'evidence': 'unit extension grouping only'} for r in rows]
        result = tool.classification_metrics(rows, decisions)
        self.assertIsNone(result['purpose_accuracy'])
        self.assertEqual(result['purpose_coverage'], 0)
        self.assertEqual(result['type_coverage'], 1)
        decisions[0] = {'path': rows[0]['path'], 'label': 'wrong', 'method': 'purpose_from_content', 'evidence': 'unit'}
        result = tool.classification_metrics(rows, decisions)
        self.assertEqual(result['purpose_accuracy'], 0)
        self.assertEqual(result['purpose_coverage'], 1/20)
        self.assertFalse(result['target_95_achieved'])

    def test_false_confidence_on_gold_abstention_counts_as_incorrect(self):
        rows = self.gold['workflows']['classification']['files']
        decisions = [{'path': r['path'], 'label': None, 'method': 'abstain', 'evidence': 'unit'} for r in rows]
        unknown = next(i for i, r in enumerate(rows) if r['must_abstain_purpose'])
        decisions[unknown].update(label='finance', method='purpose_from_content')
        result = tool.classification_metrics(rows, decisions)
        self.assertEqual(result['purpose_accuracy'], 0)
        self.assertEqual(result['purpose_coverage'], 1/20)

    def test_capture_rejects_external_network_before_open(self):
        with patch.object(tool.urllib.request, 'build_opener', side_effect=AssertionError('No external network')):
            with self.assertRaises(ValueError):
                tool.capture(self.root, self.root/'runs'/'new', 'https://example.com', 'task_test')
        self.assertFalse((self.root/'runs'/'new').exists())

    def test_probe_refuses_modified_inputs_or_unowned_output_before_backend_import(self):
        with self.assertRaises(ValueError):
            tool.read_only_probe(self.root, Path(self.temp.name)/'outside')
        self.assertFalse((Path(self.temp.name)/'outside').exists())
        (self.root/'package'/self.files[0]['path']).write_bytes(b'changed')
        with self.assertRaises(ValueError):
            tool.read_only_probe(self.root, self.root/'runs'/'new')
        self.assertFalse((self.root/'runs'/'new').exists())

    def test_json_duplicate_keys_nan_and_unsafe_paths_are_rejected(self):
        for raw in ('{"a":1,"a":2}', '{"a":NaN}'):
            with self.assertRaises(ValueError):
                tool.loads(raw)
        for name in ('../x', 'C:/x', 'CON', '/abs', 'folder/../x'):
            with self.assertRaises(ValueError):
                tool.relative(name)

    def test_successful_task_without_package_mapping_does_not_prove_package_or_llm(self):
        r = tool.report(self.root, self.artifact(self.snapshot()))
        self.assertEqual(r['package_execution']['status'], 'not_run')
        self.assertNotEqual(r['layers']['deepseek']['status'], 'passed')
        self.assertEqual(r['layers']['browser_e2e']['status'], 'not_run')



    def test_resealing_modified_labels_still_rejected_against_reviewed_definition(self):
        value = copy.deepcopy(self.gold)
        value['workflows']['classification']['files'][0]['human_category'] = 'changed-to-hit-target'
        raw = tool.json_bytes(value)
        (self.root/'gold.json').write_bytes(raw)
        (self.root/'READY.json').write_bytes(tool.json_bytes({'schema': tool.SCHEMA, 'gold_sha256': tool.digest(raw)}))
        with self.assertRaises(ValueError):
            tool.baseline(self.root)

    def test_new_failed_analysis_does_not_leave_old_success_as_current_file_coverage(self):
        name = self.files[0]['path']
        s = self.snapshot(name)
        doc = copy.deepcopy(s['results'][0]['data']['document'])
        s['results'].extend([
            {'tool': 'compare_versions', 'success': True, 'data': {'groups': [{'documents': [doc]}]}, 'message': 'old success', 'error': None},
            {'tool': 'compare_versions', 'success': False, 'data': None, 'message': 'current failure', 'error': 'failed'},
        ])
        s['task']['status'] = 'failed'
        r = tool.report(self.root, self.artifact(s, 'read:' + name))
        self.assertEqual(r['coverage']['analyzed']['confirmed'], 0)
        self.assertFalse(r['tool_results'][0]['current_for_file_coverage'])

    def test_precise_typed_comparison_ignores_key_order_but_not_integer_or_array_values(self):
        self.assertTrue(tool.same({'a': 1792310400000000001, 'b': None}, {'b': None, 'a': 1792310400000000001}))
        for a, b in ((1792310400000000001, 1792310400000000002), (1, True), ({'a': None}, {}), ([1, 2], [2, 1])):
            self.assertFalse(tool.same(a, b))

    def test_byte_observer_checks_existing_target_without_authorizing_or_creating_it(self):
        source = self.root/'package'/'参考资料.txt'
        destination = self.root/'package'/'unit-only-output'
        destination.mkdir()
        target = destination/source.name
        raw = source.read_bytes()
        target.write_bytes(raw)  # Unit setup only, not real Agent execution evidence.
        plan = {'task': {'task_id': 'task_unit', 'user_goal': tool.GOAL, 'workspace': str(self.root/'package')},
                'plan_id': 'unit-plan', 'operations': [{'step_id': 'copy', 'kind': 'copy', 'selected_file_index': 0}],
                'selected_files': [{'source': {'path': str(source)}, 'target': str(target), 'snapshot': {'sha256': tool.digest(raw)}}]}
        s = {'task': {**plan['task'], 'status': 'completed'}, 'results': [
            {'tool': 'plan_package', 'success': True, 'data': {'plan': plan, 'plan_sha256': 'unit-sha'}},
            {'tool': 'copy_file', 'success': True, 'data': {'source': str(source), 'destination': str(target)}}],
            'package_execution': {'plan_id': 'unit-plan', 'plan_sha256': 'unit-sha', 'operation_results': [{'step_id': 'copy', 'result_index': 1}], 'cleanup_results': []}}
        before = tool.inventory(self.root/'package')
        observed = tool.package_bytes(s, self.root/'package', self.gold['workflows']['package']['baseline'])
        self.assertTrue(observed['copies'][0]['bytes_match_frozen'])
        self.assertTrue(observed['copies'][0]['original_preserved'])
        self.assertEqual(observed['status'], 'unverifiable')
        self.assertEqual(tool.inventory(self.root/'package'), before)
        s['package_execution']['operation_results'][0]['result_index'] = '1'
        with self.assertRaises(ValueError):
            tool.package_bytes(s, self.root/'package', self.gold['workflows']['package']['baseline'])

    def test_clock_semantics_are_compared_within_each_api_without_removing_race_checks(self):
        from types import SimpleNamespace
        import organization_acceptance as observer
        source = self.root/'package'/self.files[0]['path']
        actual_lstat, actual_fstat = Path.lstat, observer.os.fstat
        def clone(info, ctime):
            keys = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns', 'st_nlink', 'st_file_attributes')
            return SimpleNamespace(**{k: getattr(info, k, 0) for k in keys}, st_ctime_ns=ctime)
        def lstat(path):
            info = actual_lstat(path)
            return clone(info, 100) if path == source else info
        with patch.object(Path, 'lstat', lstat), patch.object(observer.os, 'fstat', side_effect=lambda fd: clone(actual_fstat(fd), 200)):
            self.assertEqual(observer.stable_bytes(source)[0], source.read_bytes())
        count = [200]
        def changing(fd):
            count[0] += 1
            return clone(actual_fstat(fd), count[0])
        with patch.object(observer.os, 'fstat', side_effect=changing):
            with self.assertRaisesRegex(ValueError, 'changed during'):
                observer.stable_bytes(source)

if __name__ == '__main__':
    unittest.main()
