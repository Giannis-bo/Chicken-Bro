import unittest


class ChickenbroAnswerStreamTest(unittest.TestCase):
    def test_releases_only_safe_answer_after_unicode_json_chunks(self):
        from server.chickenbro_stream import ChickenbroAnswerStream

        stream = ChickenbroAnswerStream(allowed_numbers=["100"])
        emitted = []
        for chunk in ('{"answer":"你好，', '这是', ' 100% 的建议', '"}'):
            emitted.extend(stream.feed(chunk))

        self.assertEqual("".join(emitted), "你好，这是 100% 的建议")
        self.assertEqual(stream.finish()["answer"], "你好，这是 100% 的建议")

    def test_holds_an_unapproved_number_and_rejects_terminal_payload(self):
        from server.chickenbro_stream import ChickenbroAnswerStream, ChickenbroStreamValidationError

        stream = ChickenbroAnswerStream(allowed_numbers=["100"])
        self.assertEqual(stream.feed('{"answer":"请打 200%"}'), [])
        with self.assertRaises(ChickenbroStreamValidationError):
            stream.finish()

    def test_accepts_an_allowed_decimal_when_the_fraction_arrives_in_the_next_chunk(self):
        from server.chickenbro_stream import ChickenbroAnswerStream

        answer = "PTR 12.1 版本的强度需要结合后续说明判断。"
        stream = ChickenbroAnswerStream(allowed_numbers=["12.1"])
        emitted = []
        for chunk in ('{"answer":"PTR 12', '.1 版本的强度需要结合后续说明判断。"}'):
            emitted.extend(stream.feed(chunk))

        self.assertEqual("".join(emitted), answer)
        self.assertEqual(stream.finish()["answer"], answer)

    def test_accepts_an_allowed_decimal_when_its_fraction_is_split_mid_digit(self):
        from server.chickenbro_stream import ChickenbroAnswerStream

        answer = "最高观察分数是 4326.51。"
        stream = ChickenbroAnswerStream(allowed_numbers=["4326.51"])
        emitted = []
        for chunk in ('{"answer":"最高观察分数是 4326.5', '1。"}'):
            emitted.extend(stream.feed(chunk))

        self.assertEqual("".join(emitted), answer)
        self.assertEqual(stream.finish()["answer"], answer)

    def test_accepts_a_positive_number_with_an_explicit_plus_sign(self):
        from server.chickenbro_stream import ChickenbroAnswerStream

        stream = ChickenbroAnswerStream(allowed_numbers=["24"])
        emitted = stream.feed('{"answer":"最高钥石层数为 +24。"}')

        self.assertEqual("最高钥石层数为 +24。", "".join(emitted))
        self.assertEqual("最高钥石层数为 +24。", stream.finish()["answer"])

    def test_rejects_unknown_top_level_fields_before_releasing_complete_payload(self):
        from server.chickenbro_stream import ChickenbroAnswerStream, ChickenbroStreamValidationError

        stream = ChickenbroAnswerStream(allowed_numbers=[])
        self.assertEqual(stream.feed('{"answer":"安全文本","internal":"secret"}'), [])
        with self.assertRaises(ChickenbroStreamValidationError):
            stream.finish()

    def test_caps_incomplete_payload_without_releasing_text(self):
        from server.chickenbro_stream import ChickenbroAnswerStream, ChickenbroStreamValidationError

        stream = ChickenbroAnswerStream(allowed_numbers=[], max_buffer_chars=42)
        self.assertEqual(stream.feed('{"answer":"' + ("a" * 31)), [])
        with self.assertRaises(ChickenbroStreamValidationError):
            stream.feed("a")


if __name__ == "__main__":
    unittest.main()
