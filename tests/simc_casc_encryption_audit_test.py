import types
import unittest

from server.simc_casc_encryption_audit import (
    install_blte_encryption_audit,
    summarize_blte_encryption_audit,
)


class SimcCascEncryptionAuditTest(unittest.TestCase):
    def test_blte_encryption_audit_separates_key_hits_from_decrypted_chunks(self):
        available_name = bytes.fromhex("be7d592cd36508a2")

        class FakeKeyfile:
            @staticmethod
            def find(name):
                return b"\x01" * 16 if name == available_name else None

        class FakeChunk:
            def __init__(self):
                self.output_length = 32
                self.is_decrypted = False

        def process_encrypted(chunk, data):
            key_name = data[2:10]
            chunk.is_decrypted = FakeKeyfile.find(key_name) is not None
            return True

        setattr(
            FakeChunk,
            "_BLTEChunk__process_encrypted",
            process_encrypted,
        )
        casc = types.SimpleNamespace(
            BLTEChunk=FakeChunk,
            NO_DECRYPT=False,
        )
        state = install_blte_encryption_audit(casc, FakeKeyfile)
        available_chunk = FakeChunk()
        missing_chunk = FakeChunk()

        available_chunk._BLTEChunk__process_encrypted(
            b"E\x08" + available_name,
        )
        missing_chunk._BLTEChunk__process_encrypted(
            b"E\x08" + bytes.fromhex("dd9ea834c9585585"),
        )
        summary = summarize_blte_encryption_audit(state)

        self.assertTrue(summary["salsa20Available"])
        self.assertEqual(summary["encryptedChunkCount"], 2)
        self.assertEqual(summary["keyAvailableChunkCount"], 1)
        self.assertEqual(summary["decryptedChunkCount"], 1)
        self.assertEqual(summary["zeroFallbackChunkCount"], 1)
        self.assertEqual(
            summary["keyAudits"],
            [
                {
                    "keyId": "be7d592cd36508a2",
                    "chunkCount": 1,
                    "outputBytes": 32,
                    "keyAvailableChunkCount": 1,
                    "decryptedChunkCount": 1,
                },
                {
                    "keyId": "dd9ea834c9585585",
                    "chunkCount": 1,
                    "outputBytes": 32,
                    "keyAvailableChunkCount": 0,
                    "decryptedChunkCount": 0,
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
