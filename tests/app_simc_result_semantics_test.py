import unittest

from server.app.simulation.worker import (
    RawSimulationExecution,
    SimulationResultParser,
    SimulationWorkerError,
)


class SimcResultSemanticsTest(unittest.TestCase):
    def setUp(self):
        self.parser = SimulationResultParser()

    def parse_stdout(self, stdout):
        return self.parser.parse(
            RawSimulationExecution(0, stdout, "", "simc:current:abc"),
            expected_actor="Stormsample",
        )

    def test_actor_summary_metric_and_error_are_not_replaced_by_pet_or_secondary_healing(self):
        metric = self.parse_stdout(
            "Player: Stormsample tauren shaman elemental 80\n"
            "  DPS=12345 DPS-Error=12.5/0.10% DPS-Range=100/1.00%\n"
            "  HPS=500 HPS-Error=2/0.40%\n"
            "  Actions:\n    spirit_wolf (DPS=123)\n"
        )
        self.assertEqual((metric.name, metric.value, metric.error, metric.error_pct), ("dps", 12345, 12.5, 0.10))

    def test_healing_summary_and_zero_reported_error_are_preserved(self):
        metric = self.parse_stdout("Player: Stormsample\n HPS=10000 HPS-Error=0/0.00%\n")
        self.assertEqual((metric.name, metric.error, metric.error_pct), ("hps", 0, 0))

    def test_unavailable_or_invalid_error_is_not_fabricated(self):
        for suffix in (
            "", "DPS-Error=-1/1%", "DPS-Error=nan/1%", "DPS-Error=1/inf%",
            "DPS-Error=1e309/1%", "HPS-Error=1/1%",
            "DPS-Error=1/1% DPS-Error=2/2%", "DPS-Error=1/1%extra",
            "DPS-Error=1/1% DPS-Error=garbage", "DPS-Error=1_0/1%",
        ):
            with self.subTest(suffix=suffix):
                metric = self.parse_stdout(f"Player: Stormsample\nDPS=10000 {suffix}\n")
                self.assertEqual(metric.value, 10000)
                self.assertIsNone(metric.error)
                self.assertIsNone(metric.error_pct)

    def test_pet_only_or_metric_before_actor_is_not_a_player_result(self):
        for stdout in (
            "DPS=10000\nPlayer: Stormsample\n",
            "Player: Stormsample\n Actions:\n pet (DPS=10000)\n",
        ):
            with self.subTest(stdout=stdout):
                with self.assertRaises(SimulationWorkerError) as error:
                    self.parse_stdout(stdout)
                self.assertEqual(error.exception.code, "SIMC_METRIC_MISSING")

    def test_metric_without_one_valid_actor_is_rejected(self):
        for stdout in (
            "DPS=12345\n",
            "Player: none\nDPS=12345\n",
            "Player: Stormsample race=none\nDPS=12345\n",
            "Player: AnotherCharacter\nDPS=12345\n",
            "Player: First\nPlayer: Second\nDPS=12345\n",
        ):
            with self.subTest(stdout=stdout):
                with self.assertRaises(SimulationWorkerError) as context:
                    self.parser.parse(
                        RawSimulationExecution(
                            return_code=0,
                            stdout=stdout,
                            stderr="",
                            runtime_revision="simc:current:abc",
                        ),
                        expected_actor="Stormsample",
                    )
                self.assertEqual(context.exception.code, "SIMC_ACTOR_INVALID")

    def test_fatal_diagnostic_rejects_an_otherwise_valid_metric(self):
        with self.assertRaises(SimulationWorkerError) as context:
            self.parser.parse(
                RawSimulationExecution(
                    return_code=0,
                    stdout="Player: Stormsample\nDPS=12345\n",
                    stderr="Fatal error: actor profile could not be initialized",
                    runtime_revision="simc:current:abc",
                ),
                expected_actor="Stormsample",
            )

        self.assertEqual(context.exception.code, "SIMC_FATAL_DIAGNOSTIC")

    def test_non_finite_or_non_positive_metric_is_rejected(self):
        for raw_value in ("NaN", "Infinity", "-1", "0", "1e309"):
            with self.subTest(raw_value=raw_value):
                with self.assertRaises(SimulationWorkerError) as context:
                    self.parser.parse(
                        RawSimulationExecution(
                            return_code=0,
                            stdout=f"Player: Stormsample\nDPS={raw_value}\n",
                            stderr="",
                            runtime_revision="simc:current:abc",
                        ),
                        expected_actor="Stormsample",
                    )
                self.assertEqual(context.exception.code, "SIMC_METRIC_INVALID")


if __name__ == "__main__":
    unittest.main()
