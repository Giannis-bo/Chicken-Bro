import unittest

from server import gear_enhancement_management, gear_socket_authority


class GearEnhancementManagementTest(unittest.TestCase):
    def valid_management(self):
        return {
            "schemaRevision": "gear-enhancement-management-v1",
            "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
            "fields": {
                "gem_id": "editor_managed",
                "embellishment": "source_only",
            },
        }

    def test_v2_management_requires_exact_schema_authority_field_set_and_enum(self):
        simc_options = {
            "ilevel": "289",
            "gem_id": "240916",
            "embellishment": "built_in_effect",
        }
        valid = self.valid_management()

        self.assertEqual(
            gear_enhancement_management.validated_enhancement_management_fields(
                simc_options,
                valid,
                gear_socket_authority.CAPABILITY_REVISION,
            ),
            {
                "gem_id": "editor_managed",
                "embellishment": "source_only",
            },
        )

        invalid_cases = {
            "missing marker": None,
            "forged schema": {**valid, "schemaRevision": "forged-v0"},
            "wrong authority": {**valid, "authorityRevision": "gear-capability-v999"},
            "missing field": {
                **valid,
                "fields": {"embellishment": "source_only"},
            },
            "extra field": {
                **valid,
                "fields": {**valid["fields"], "enchant_id": "source_only"},
            },
            "invalid enum": {
                **valid,
                "fields": {**valid["fields"], "gem_id": "trust_me"},
            },
        }
        for name, management in invalid_cases.items():
            with self.subTest(name=name):
                self.assertEqual(
                    gear_enhancement_management.validated_enhancement_management_fields(
                        simc_options,
                        management,
                        gear_socket_authority.CAPABILITY_REVISION,
                    ),
                    {},
                )

    def test_management_is_v2_only_and_non_string_raw_fields_are_still_present(self):
        simc_options = {"gem_id": 240916}
        management = {
            "schemaRevision": "gear-enhancement-management-v1",
            "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
            "fields": {"gem_id": "source_only"},
        }

        self.assertEqual(
            gear_enhancement_management.present_enhancement_simc_fields(simc_options),
            {"gem_id"},
        )
        self.assertEqual(
            gear_enhancement_management.validated_enhancement_management_fields(
                simc_options,
                management,
                gear_socket_authority.LEGACY_CAPABILITY_REVISION,
            ),
            {},
        )


if __name__ == "__main__":
    unittest.main()
