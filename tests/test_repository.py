"""Regression checks for truthful runtime metadata and source-derived views."""
from pathlib import Path
from copy import deepcopy
import json
import platform
import shutil
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import verify_all as verification
from scripts.listing_views import canonical_listings, check_views, check_readiness_views

ROOT = Path(__file__).resolve().parent.parent


class RuntimeComparisonTests(unittest.TestCase):
    def test_truthful_runtime_difference_preserves_semantic_comparison(self):
        expected = {'python':'3.12.14','value':50,'source_sha256':'retained'}
        actual = dict(expected,python=platform.python_version())
        verification.compare_json(actual,expected,'fixture',('python',))
        self.assertEqual(actual['python'],platform.python_version())
        self.assertEqual(expected['python'],'3.12.14')

    def test_incorrect_semantic_value_is_never_normalized(self):
        with self.assertRaisesRegex(RuntimeError,'semantic output differs'):
            verification.compare_json({'python':platform.python_version(),'value':51},
                                      {'python':'3.12.14','value':50},'fixture',('python',))

    def test_false_runtime_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'False runtime metadata'):
            verification.compare_json({'python':'invented','value':50},
                                      {'python':'3.12.14','value':50},'fixture',('python',))

    def test_numeric_and_boolean_aliases_are_not_equal_outputs(self):
        with self.assertRaisesRegex(RuntimeError,'semantic output differs'):
            verification.compare_json({'value':True},{'value':1},'typed fixture')

    def test_code_hash_remains_part_of_manifest_comparison(self):
        with self.assertRaisesRegex(RuntimeError,'semantic output differs'):
            verification.compare_json({'runtime':{'python_version':platform.python_version()},'code_sha256':'changed'},
                                      {'runtime':{'python_version':'3.12.14'},'code_sha256':'original'},
                                      'manifest',('runtime.python_version',))


class ReviewedCodeIdentityTests(unittest.TestCase):
    def historical(self):
        with zipfile.ZipFile(ROOT/'provenance/companion-code-baseline.zip') as archive:
            return json.loads(archive.read('chapter06/generated/manifest.json'))

    def test_only_declared_code_metadata_changes_and_input_is_preserved(self):
        original=self.historical();before=deepcopy(original)
        corrected=verification.reviewed_code_manifest(original,'chapter06')
        updates=verification.load(ROOT/'provenance/RUNTIME_MANIFEST_UPDATES.json')['runtime_manifest_code_updates']
        self.assertEqual(original,before)
        self.assertEqual(corrected['code_sha256']['randomized_checks.py'],next(c['after_sha256'] for c in updates if c['folder']=='chapter06'))
        corrected['code_sha256']=before['code_sha256']
        self.assertEqual(corrected,before)

    def test_changed_historical_code_identity_is_rejected(self):
        original=self.historical();original['code_sha256']['randomized_checks.py']='0'*64
        with self.assertRaisesRegex(RuntimeError,'Historical code identity differs'):
            verification.reviewed_code_manifest(original,'chapter06')

    def test_resealed_active_hash_without_reviewed_identity_is_rejected(self):
        original=self.historical();load=verification.load
        def altered(path):
            value=load(path)
            if path.name=='LAB_FILES.json':
                value=dict(value);value['chapter06/randomized_checks.py']='0'*64
            return value
        with patch.object(verification,'load',side_effect=altered),self.assertRaisesRegex(RuntimeError,'Current code identity differs'):
            verification.reviewed_code_manifest(original,'chapter06')


class ReviewedChapter04IdentityTests(unittest.TestCase):
    def historical(self):
        with zipfile.ZipFile(ROOT/'provenance/companion-code-baseline.zip') as archive:
            return json.loads(archive.read('chapter04/dataset_manifest.json'))

    def test_only_source_hash_and_global_identity_declaration_change(self):
        original = self.historical()
        before = deepcopy(original)
        revised = verification.reviewed_chapter04_manifest(original)
        self.assertEqual(original, before)
        self.assertEqual(revised['event_identity'], ['event', 'version'])
        self.assertEqual(revised['source_sha256'], verification.load(ROOT/'provenance/LAB_FILES.json')['chapter04/chapter4.py'])
        for field in ('source_sha256', 'event_identity'):
            revised[field] = before[field]
        self.assertEqual(revised, before)

    def test_unexpected_historical_identity_or_hash_is_rejected(self):
        for field, value in [('source_sha256', '0'*64), ('event_identity', ['invented'])]:
            with self.subTest(field=field):
                original = self.historical()
                original[field] = value
                with self.assertRaisesRegex(RuntimeError, 'Historical chapter04 identity differs'):
                    verification.reviewed_chapter04_manifest(original)

    def test_resealed_source_hash_without_reviewed_identity_is_rejected(self):
        original = self.historical()
        load = verification.load
        def altered(path):
            value = load(path)
            if path.name == 'LAB_FILES.json':
                value = dict(value)
                value['chapter04/chapter4.py'] = '0'*64
            return value
        with patch.object(verification, 'load', side_effect=altered), self.assertRaisesRegex(RuntimeError, 'Current chapter04 source identity differs'):
            verification.reviewed_chapter04_manifest(original)


class ListingViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='listing-view-tests-')
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT/'docs',self.root/'docs')
        for folder in verification.ORDER:
            target = self.root/folder; target.mkdir()
            for name in ('printed_snippets.json','printed_examples.py'):
                if (ROOT/folder/name).exists(): shutil.copyfile(ROOT/folder/name,target/name)

    def tearDown(self):
        self.temp.cleanup()

    def test_all_72_views_match_canonical_bodies_without_execution(self):
        self.assertEqual(check_views(self.root),72)

    def test_changed_listing_view_is_rejected(self):
        item = canonical_listings(self.root)[0]
        path = self.root/item['view_path']
        path.write_text(path.read_text().replace(item['code'],item['code']+'# changed\n'))
        with self.assertRaisesRegex(ValueError,'differs from canonical'):
            check_views(self.root)

    def test_unknown_extra_view_is_rejected(self):
        (self.root/'docs/listings/untracked.md').write_text('untracked')
        with self.assertRaisesRegex(ValueError,'inventory differs'):
            check_views(self.root)


class ReadinessViewTests(unittest.TestCase):
    def test_both_book_refresher_views_match_the_canonical_bodies(self):
        self.assertEqual(check_readiness_views(ROOT),2)

    def test_changed_refresher_view_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='refresher-view-tests-') as temp:
            root = Path(temp)
            shutil.copytree(ROOT/'prerequisites',root/'prerequisites')
            path = root/'prerequisites/refresher-python.md'
            path.write_text(path.read_text().replace('print(rows[0]["value"] == 0)','print(False)'))
            with self.assertRaisesRegex(ValueError,'refresher view differs'):
                check_readiness_views(root)


class IntegrityBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='repository-integrity-tests-')
        self.root = (Path(self.temp.name)/'repository').resolve()
        shutil.copytree(ROOT,self.root,ignore=shutil.ignore_patterns('.venv','.git','generated','__pycache__'))

    def tearDown(self):
        self.temp.cleanup()

    def test_modified_active_lesson_fails_integrity(self):
        target = self.root/'chapter03/historical_lab.py'
        target.write_text(target.read_text()+'\n# deliberate test modification\n')
        with patch.object(verification,'ROOT',self.root):
            with self.assertRaisesRegex(RuntimeError,'Lesson hash differs'):
                verification.source_checks()

    def test_unexpected_file_inside_active_lesson_fails_integrity(self):
        (self.root/'chapter03/unexpected.txt').write_text('unexpected')
        with patch.object(verification,'ROOT',self.root):
            with self.assertRaisesRegex(RuntimeError,'inventory differs'):
                verification.source_checks()

    def test_git_metadata_and_wrapper_docs_remain_outside_lesson_inventory(self):
        (self.root/'.git').mkdir()
        (self.root/'.git/test-marker').write_text('not lesson source')
        (self.root/'docs/experiment-note.md').write_text('An independent wrapper note.\n')
        with patch.object(verification,'ROOT',self.root):
            result = verification.source_checks()
        self.assertFalse(result['lab_code_executed'])
        self.assertEqual(result['canonical_listing_views_checked'],72)


if __name__ == '__main__':
    unittest.main()
