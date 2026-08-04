import unittest


class ChickenbroQuestionFrameTest(unittest.TestCase):
    def _builder(self):
        try:
            from server.chickenbro_question_frame import build_chickenbro_question_frame
        except ImportError as error:
            self.fail(f"QuestionFrame parser must exist: {error}")
        return build_chickenbro_question_frame

    def test_current_ptr_strength_resolves_player_alias_and_evidence_needs(self):
        frame = self._builder()("NQ 在 12.1 PTR 强度如何？", [])

        self.assertEqual("chickenbro-question-frame-v1", frame["schemaRevision"])
        self.assertEqual("current_research", frame["questionType"])
        self.assertEqual(
            {"classKey": "paladin", "specKey": "holy", "resolution": "resolved"},
            frame["subject"],
        )
        self.assertEqual("ptr", frame["scope"]["productPhase"])
        self.assertEqual("12.1", frame["scope"]["patchVersion"])
        self.assertEqual(
            ["official_current_changes", "comparative_strength_signal"],
            frame["evidenceNeeds"],
        )
        self.assertEqual(["scenarioKey"], frame["unresolvedFields"])

    def test_alias_catalog_resolves_chinese_and_canonical_forms_without_answer_templates(self):
        builder = self._builder()
        chinese = builder("奶骑 12.1 测试服改动和强度怎样", [])
        canonical = builder("holy paladin 12.1 PTR strength", [])

        self.assertEqual(chinese["subject"], canonical["subject"])
        self.assertEqual("paladin", canonical["subject"]["classKey"])
        self.assertEqual("holy", canonical["subject"]["specKey"])
        self.assertNotIn("answer", frame_text := str(chinese).lower())
        self.assertNotIn("rank", frame_text)

    def test_question_types_keep_personal_wcl_and_community_build_distinct(self):
        builder = self._builder()
        wcl = builder("看看 https://www.warcraftlogs.com/reports/ABC123 的防战手法", [])
        build = builder("防战现在天赋怎么点，属性怎么搭配？", [])

        self.assertEqual("personal_wcl", wcl["questionType"])
        self.assertEqual("community_build", build["questionType"])
        self.assertEqual(["personal_log_evidence"], wcl["evidenceNeeds"])
        self.assertEqual(["community_build_reference"], build["evidenceNeeds"])

    def test_ambiguous_current_question_is_explicitly_unresolved(self):
        frame = self._builder()("12.1 PTR 现在哪个治疗最强？", [])

        self.assertEqual("current_research", frame["questionType"])
        self.assertEqual(
            {"classKey": "", "specKey": "", "resolution": "unresolved"},
            frame["subject"],
        )
        self.assertIn("subject", frame["unresolvedFields"])
        self.assertIn("comparative_strength_signal", frame["evidenceNeeds"])

    def test_follow_up_inherits_only_recent_user_subject_and_scope(self):
        frame = self._builder()(
            "那改动后大秘境呢？",
            [
                {"role": "assistant", "content": "你问的是暗牧还是奶骑？"},
                {"role": "user", "content": "奶骑在 12.1 PTR 强度如何？"},
            ],
        )

        self.assertEqual("paladin", frame["subject"]["classKey"])
        self.assertEqual("holy", frame["subject"]["specKey"])
        self.assertEqual("ptr", frame["scope"]["productPhase"])
        self.assertEqual("12.1", frame["scope"]["patchVersion"])
        self.assertEqual("mythic_plus", frame["scope"]["scenarioKey"])

    def test_explicit_retail_correction_overrides_ptr_history(self):
        frame = self._builder()(
            "不是，你看元素萨现在版本，不需要测试服的大秘境强度",
            [{"role": "user", "content": "元素萨在 12.1 PTR 大秘境强度如何？"}],
        )

        self.assertEqual("current_research", frame["questionType"])
        self.assertEqual(
            {"classKey": "shaman", "specKey": "elemental", "resolution": "resolved"},
            frame["subject"],
        )
        self.assertEqual("retail", frame["scope"]["productPhase"])
        self.assertEqual("", frame["scope"]["patchVersion"])
        self.assertEqual("mythic_plus", frame["scope"]["scenarioKey"])
        self.assertEqual(["comparative_strength_signal"], frame["evidenceNeeds"])

    def test_positive_ptr_beats_a_generic_current_version_marker(self):
        frame = self._builder()("12.1 PTR 当前版本元素萨大秘境强度如何？", [])

        self.assertEqual("ptr", frame["scope"]["productPhase"])
        self.assertEqual("12.1", frame["scope"]["patchVersion"])

    def test_history_strength_does_not_turn_a_follow_up_build_question_into_research(self):
        frame = self._builder()(
            "那天赋怎么点？",
            [{"role": "user", "content": "元素萨现在版本大秘境强度如何？"}],
        )

        self.assertEqual("community_build", frame["questionType"])
        self.assertEqual(["community_build_reference"], frame["evidenceNeeds"])

    def test_evidence_ratio_follow_up_inherits_only_the_prior_strength_scope(self):
        frame = self._builder()(
            "解读一下15/27是啥意思？",
            [{"role": "user", "content": "现在版本的元素萨在大秘境DPS整体的排名如何？ 强度如何？"}],
        )

        self.assertEqual("current_research", frame["questionType"])
        self.assertEqual(["comparative_strength_signal"], frame["evidenceNeeds"])
        self.assertEqual(
            {"classKey": "shaman", "specKey": "elemental", "resolution": "resolved"},
            frame["subject"],
        )
        self.assertEqual("retail", frame["scope"]["productPhase"])
        self.assertEqual("mythic_plus", frame["scope"]["scenarioKey"])

    def test_evidence_ratio_follow_up_does_not_cross_an_intervening_user_turn(self):
        frame = self._builder()(
            "解读一下15/27是啥意思？",
            [
                {"role": "user", "content": "元素萨现在版本大秘境强度如何？"},
                {"role": "assistant", "content": "这里是当前高层样本信号。"},
                {"role": "user", "content": "那天赋怎么点？"},
            ],
        )

        self.assertEqual("community_build", frame["questionType"])
        self.assertEqual(["community_build_reference"], frame["evidenceNeeds"])

    def test_generic_raid_scope_is_preserved_without_becoming_mythic_plus(self):
        frame = self._builder()("元素萨正式服团本单体强度如何？", [])

        self.assertEqual("raid", frame["scope"]["scenarioKey"])


if __name__ == "__main__":
    unittest.main()
