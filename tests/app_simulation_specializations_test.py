import unittest
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID

from server.app.identity.domain import Principal
from server.app.simulation.application import SimulationApplication, SimulationApplicationError
from server.app.simulation.compiler import SimcCompileError, SimcProfileCompiler
from server.app.simulation.domain import SourceReadiness
from server.app.simulation.readiness import SimcReadinessValidator, SimcRuntimeCapabilities
from tests.app_simulation_readiness_test import candidate_from_fixture
from tests.app_simulation_application_test import MemorySimulationRepository, MemoryQueue


# Independent complete game specialization matrix; seven healing specs excluded.
NON_HEALERS = {
    'warrior': ('arms', 'fury', 'protection'),
    'paladin': ('protection', 'retribution'),
    'hunter': ('beast_mastery', 'marksmanship', 'survival'),
    'rogue': ('assassination', 'outlaw', 'subtlety'),
    'priest': ('shadow',),
    'death_knight': ('blood', 'frost', 'unholy'),
    'shaman': ('elemental', 'enhancement'),
    'mage': ('arcane', 'fire', 'frost'),
    'warlock': ('affliction', 'demonology', 'destruction'),
    'monk': ('brewmaster', 'windwalker'),
    'druid': ('balance', 'feral', 'guardian'),
    'demon_hunter': ('havoc', 'vengeance', 'devourer'),
    'evoker': ('devastation', 'augmentation'),
}
HEALERS = (('paladin', 'holy'), ('priest', 'holy'), ('priest', 'discipline'),
           ('shaman', 'restoration'), ('monk', 'mistweaver'), ('druid', 'restoration'),
           ('evoker', 'preservation'))


def candidate_for(klass, spec):
    candidate = candidate_from_fixture()
    data = deepcopy(candidate.snapshot)
    data['character'].update(classKey=klass, specKey=spec)
    return replace(candidate, snapshot=data)


class SpecializationSupportTest(unittest.TestCase):
    def capabilities(self, configured='all', runtime='test:runtime'):
        return SimcRuntimeCapabilities.from_env({
            'WOW_SIMC_SUPPORTED_SPECS': configured,
            'WOW_SIMC_RUNTIME_REVISION': runtime,
            'WOW_SIMC_COMPILER_REVISION': 'chickenbro-simc-compiler-v4',
        })

    def test_all_non_healers_reach_compiler_with_real_simc_class_tokens(self):
        caps = self.capabilities()
        for klass, specs in NON_HEALERS.items():
            for spec in specs:
                with self.subTest(klass=klass, spec=spec):
                    candidate = candidate_for(klass, spec)
                    report = SimcReadinessValidator().validate(candidate, caps)
                    self.assertEqual(report.readiness, SourceReadiness.READY_FOR_SIMC)
                    snapshot = candidate.to_source_snapshot(
                        user_id='00000000-0000-4000-8000-000000000001',
                        snapshot_id='00000000-0000-4000-8000-000000000002', readiness_report=report)
                    compiled = SimcProfileCompiler(capabilities=caps).compile(snapshot, {})
                    self.assertTrue(compiled.profile.startswith(klass.replace('_', '') + '="'))
                    self.assertIn('\nspec=' + spec + '\n', compiled.profile)

    def test_healers_have_specific_error_even_with_wildcard_or_explicit_allowance(self):
        for klass, spec in HEALERS:
            for configured in ('all', '*:*', klass + ':' + spec):
                with self.subTest(klass=klass, spec=spec, configured=configured):
                    caps = self.capabilities(configured)
                    candidate = candidate_for(klass, spec)
                    report = SimcReadinessValidator().validate(candidate, caps)
                    self.assertIn('HEALER_SPEC_UNSUPPORTED', report.blockers)
                    self.assertNotIn('RUNTIME_UNAVAILABLE', report.blockers)
                    self.assertFalse(caps.supports(klass, spec))
                    # A retained READY snapshot must not bypass the same compiler gate.
                    snapshot = candidate.to_source_snapshot(
                        user_id='00000000-0000-4000-8000-000000000001',
                        snapshot_id='00000000-0000-4000-8000-000000000002',
                        readiness_report=replace(report, readiness=SourceReadiness.READY_FOR_SIMC))
                    with self.assertRaises(SimcCompileError) as raised:
                        SimcProfileCompiler(capabilities=caps).compile(snapshot, {})
                    self.assertEqual(raised.exception.code, 'HEALER_SPEC_UNSUPPORTED')

    def test_unknown_and_disabled_specs_are_distinct_from_broken_engine(self):
        for klass, spec, configured, expected in (
            ('druid', 'feral', 'shaman:elemental', 'SPEC_NOT_ENABLED'),
            ('mage', 'feral', '*:*', 'SPEC_UNSUPPORTED'),
            ('unknown', 'arms', 'all', 'SPEC_UNSUPPORTED'),
        ):
            report = SimcReadinessValidator().validate(candidate_for(klass, spec), self.capabilities(configured))
            self.assertIn(expected, report.blockers)
            self.assertNotIn('RUNTIME_UNAVAILABLE', report.blockers)
        report = SimcReadinessValidator().validate(candidate_for('druid', 'feral'), self.capabilities(runtime=''))
        self.assertIn('RUNTIME_UNAVAILABLE', report.blockers)

    def test_legacy_class_aliases_and_empty_config(self):
        for configured in ('all', 'deathknight:blood,demonhunter:havoc'):
            caps = self.capabilities(configured)
            for klass, spec in (('death_knight', 'blood'), ('deathknight', 'blood'),
                                ('demon_hunter', 'havoc'), ('demonhunter', 'havoc')):
                self.assertTrue(caps.supports(klass, spec))
        self.assertFalse(self.capabilities('').supports('druid', 'feral'))

    def test_healers_never_enqueue_and_feral_remains_owner_scoped_and_idempotent(self):
        caps = self.capabilities()
        for klass, spec in (*HEALERS, ('druid', 'feral')):
            with self.subTest(klass=klass, spec=spec):
                repository = MemorySimulationRepository()
                queue = MemoryQueue()
                repository.queue = queue
                app = SimulationApplication(repository=repository,
                    source_router=SimpleNamespace(resolve=lambda _: candidate_for(klass, spec)),
                    readiness_validator=SimcReadinessValidator(),
                    compiler=SimcProfileCompiler(capabilities=caps), runtime_capabilities=caps)
                owner = Principal(user_id=UUID('00000000-0000-4000-8000-000000000001'), session_kind='web_cookie')
                other = replace(owner, user_id=UUID('00000000-0000-4000-8000-000000000002'))
                snapshot = app.resolve_source(owner, 'https://raider.io/characters/cn/the-masters-glaive/test')
                with self.assertRaises(SimulationApplicationError) as denied:
                    app.submit(other, snapshot.id, {}, 'other-account')
                self.assertEqual(denied.exception.code, 'SNAPSHOT_NOT_FOUND')
                if (klass, spec) in HEALERS:
                    with self.assertRaises(SimulationApplicationError) as denied:
                        app.submit(owner, snapshot.id, {}, 'healer-submit')
                    self.assertIn('HEALER_SPEC_UNSUPPORTED', denied.exception.blockers)
                    self.assertEqual(queue.calls, [])
                else:
                    job = app.submit(owner, snapshot.id, {}, 'feral-submit')
                    self.assertEqual(app.submit(owner, snapshot.id, {}, 'feral-submit').id, job.id)
                    self.assertEqual(len(queue.calls), 1)
