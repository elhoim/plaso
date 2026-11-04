#!/usr/bin/env python3
"""Tests for the Apple Wallet pass (pkpass) plugin."""

import unittest
import zipfile

from plaso.parsers.czip_plugins import pkpass

from tests.parsers.czip_plugins import test_lib


class AppleWalletPassPluginTest(test_lib.CompoundZIPPluginTestCase):
    """Tests for the Apple Wallet pass (pkpass) plugin."""

    def testCheckRequiredPaths(self):
        """Tests the CheckRequiredPaths function."""
        plugin = pkpass.AppleWalletPassPlugin()

        for path_segments, expected_result in (
            (["wallet.pkpass"], True),
            (["Document.docx"], False),
            (["syslog.zip"], False),
        ):
            file_entry = self._GetTestFileEntry(path_segments)
            file_object = file_entry.GetFileObject()

            with zipfile.ZipFile(file_object, "r") as zip_file:
                result = plugin.CheckRequiredPaths(zip_file)

            self.assertEqual(result, expected_result)

    def testProcess(self):
        """Tests the Process function."""
        plugin = pkpass.AppleWalletPassPlugin()
        storage_writer = self._ParseZIPFileWithPlugin(["wallet.pkpass"], plugin)

        number_of_event_data = storage_writer.GetNumberOfAttributeContainers(
            "event_data"
        )
        self.assertEqual(number_of_event_data, 1)

        number_of_warnings = storage_writer.GetNumberOfAttributeContainers(
            "extraction_warning"
        )
        self.assertEqual(number_of_warnings, 0)

        number_of_warnings = storage_writer.GetNumberOfAttributeContainers(
            "recovery_warning"
        )
        self.assertEqual(number_of_warnings, 0)

        expected_event_values = {
            "data_type": "apple:wallet:pass",
            "description": "Concert ticket",
            "expiration_time": "2025-06-15T02:00:00+00:00",
            "logo_text": "Example Concert Hall",
            "organization_name": "Example Concert Hall",
            "pass_type_identifier": "pass.org.example.event-ticket",
            "relevant_time": "2025-06-14T19:30:00-07:00",
            "serial_number": "TICKET-0001",
            "team_identifier": "A1B2C3D4E5",
            "voided": False,
        }

        event_data = storage_writer.GetAttributeContainerByIndex("event_data", 0)
        self.CheckEventData(event_data, expected_event_values)

    def testProcessWithNotAPass(self):
        """Tests the Process function with a pass.json that is not a pass."""
        plugin = pkpass.AppleWalletPassPlugin()
        storage_writer = self._ParseZIPFileWithPlugin(
            ["wallet_not_a_pass.pkpass"], plugin
        )

        number_of_event_data = storage_writer.GetNumberOfAttributeContainers(
            "event_data"
        )
        self.assertEqual(number_of_event_data, 0)

        number_of_warnings = storage_writer.GetNumberOfAttributeContainers(
            "extraction_warning"
        )
        self.assertEqual(number_of_warnings, 1)


if __name__ == "__main__":
    unittest.main()
