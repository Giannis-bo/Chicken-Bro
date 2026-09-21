import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
from server.app.poe2.application import Poe2Application, Poe2Error


class TreeViewTests(unittest.TestCase):
    def setUp(self):
        self.owner = SimpleNamespace(user_id=uuid4())
        self.build = SimpleNamespace(id=uuid4(), source_xml='<PathOfBuilding2><Build/></PathOfBuilding2>', engine_version='pinned')
        self.repo = Mock()
        self.repo.get_build.return_value = self.build
        self.engine = Mock()
        self.engine.tree.return_value = {'engineVersion': 'pinned', 'treeVersion': '0_5', 'nodes': []}
        self.app = Poe2Application(self.repo, self.engine)

    def test_owner_checked_before_engine_and_no_source_returned(self):
        result = self.app.read_tree(self.owner, self.build.id)
        self.repo.get_build.assert_called_once_with(self.owner.user_id, self.build.id)
        self.engine.tree.assert_called_once_with(self.build.source_xml)
        self.assertEqual(result['buildId'], str(self.build.id))
        self.assertNotIn('source', result)

    def test_other_owner_never_runs_engine(self):
        self.repo.get_build.return_value = None
        with self.assertRaises(Poe2Error): self.app.read_tree(self.owner, self.build.id)
        self.engine.tree.assert_not_called()

    def test_changed_engine_does_not_silently_render_new_tree(self):
        self.engine.tree.return_value['engineVersion'] = 'different'
        with self.assertRaisesRegex(Poe2Error, 'POE2_TREE_VERSION_MISMATCH'):
            self.app.read_tree(self.owner, self.build.id)

    def test_job_tree_uses_exact_export_and_verifies_build(self):
        job = SimpleNamespace(build_id=self.build.id, result={'exportCode': 'exact-result', 'engineVersion': 'pinned'})
        self.repo.get_job.return_value = job
        job_id = uuid4()
        self.app.read_tree(self.owner, self.build.id, job_id)
        self.engine.tree.assert_called_once_with('exact-result')
        self.repo.get_job.assert_called_once_with(self.owner.user_id, job_id)
        self.engine.reset_mock()
        job.build_id = uuid4()
        with self.assertRaises(Poe2Error): self.app.read_tree(self.owner, self.build.id, job_id)
        self.engine.tree.assert_not_called()
