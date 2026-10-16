"""Fault checks for release recovery and safe same-batch migration retries."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import deploy


class ReleaseFaultTests(unittest.TestCase):
    def release(self):
        release = deploy.Release.__new__(deploy.Release)
        release.m = {'sourceCommit':'a'*40, 'releaseId':'b'*64, 'files':{'server/migrations/product/0021_simc_characters.sql':'c'*64}}
        release.base,release.web,release.target,release.web_target = map(Path,('/old-api','/old-web','/new-api','/new-web'))
        release.link,release.web_link = Mock(),Mock()
        release.link.resolve.return_value=release.base
        release.web_link.resolve.return_value=release.web
        for method in ('runtime','staged','baseline','save_recovery'):
            setattr(release,method,Mock())
        return release

    def test_partially_stopped_services_trigger_recovery(self):
        release=self.release()
        release.migration=Mock()
        release.activate=Mock(side_effect=[RuntimeError('worker stop failed'),None])
        with patch.object(deploy.subprocess,'run',return_value=Mock(returncode=1)):
            with self.assertRaisesRegex(RuntimeError,'prior backend/Web recovered'):
                release.run('promote')
        self.assertEqual(release.activate.call_count,2)
        self.assertEqual(release.activate.call_args.args,(release.base,release.web,release.base,release.web))

    def test_same_batch_migration_reused_and_foreign_batch_refused(self):
        release=self.release()
        with tempfile.TemporaryDirectory() as directory:
            release.path=Path(directory)/'manifest.json'
            (release.path.parent/'database-recovery.json').write_text(json.dumps({'restoreCountsMatched':True,'newMigrationVerified':True}))
            connection=Mock()
            context=Mock()
            context.__enter__=Mock(return_value=connection)
            context.__exit__=Mock(return_value=False)
            release.connect=lambda:context
            connection.execute.return_value.fetchone.side_effect=[('simc-characters-release:'+'b'*64,),('simc.character_preferences',),(True,)]
            with patch.object(deploy,'sha',return_value='c'*64),patch.object(deploy.subprocess,'run') as command:
                release.migration()
                command.assert_not_called()
            connection.execute.return_value.fetchone.side_effect=[('another-release',)]
            with patch.object(deploy,'sha',return_value='c'*64):
                with self.assertRaisesRegex(RuntimeError,'another activation'):
                    release.migration()

    def test_new_migration_uses_psql_quoted_variable(self):
        release=self.release()
        with tempfile.TemporaryDirectory() as directory:
            release.path=Path(directory)/'manifest.json'
            release.target=Path(directory)
            sql=release.target/'server/migrations/product/0021_simc_characters.sql'
            sql.parent.mkdir(parents=True)
            sql.write_text('SELECT 1;')
            (release.path.parent/'database-recovery.json').write_text(json.dumps({'restoreCountsMatched':True,'newMigrationVerified':True}))
            connection=Mock()
            context=Mock()
            context.__enter__=Mock(return_value=connection)
            context.__exit__=Mock(return_value=False)
            release.connect=lambda:context
            connection.execute.return_value.fetchone.side_effect=[None,(None,),(True,)]
            with patch.object(deploy,'sha',return_value='c'*64),patch.object(deploy.subprocess,'run',return_value=Mock(returncode=0)) as command:
                release.migration()
                self.assertIn('release_description=simc-characters-release:'+'b'*64,command.call_args.args[0])
                self.assertIn(":'release_description'",command.call_args.kwargs['input'])


if __name__=='__main__':unittest.main()
