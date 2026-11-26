#!/usr/bin/env python3
"""Tests for the Windows boot status data (bootstat.dat) file parser."""

import unittest

from plaso.lib import errors
from plaso.parsers import windows_bootstat

from tests.parsers import test_lib


class WindowsBootStatusDataParserTest(test_lib.ParserTestCase):
    """Tests for the Windows boot status data (bootstat.dat) file parser."""

    def _ReadTestFileData(self, path_segments):
        """Reads the data of a test file.

        Args:
          path_segments (list[str]): path segments inside the test data directory.

        Returns:
          bytes: data of the test file.
        """
        test_file_path = self._GetTestFilePath(path_segments)
        self._SkipIfPathNotExists(test_file_path)

        with open(test_file_path, "rb") as file_object:
            return file_object.read()

    def testParse(self):
        """Tests the Parse function on a Windows directory bootstat.dat file."""
        parser = windows_bootstat.WindowsBootStatusDataParser()
        storage_writer = self._ParseFile(["bootstat.dat"], parser)

        number_of_event_data = storage_writer.GetNumberOfAttributeContainers(
            "event_data"
        )
        self.assertEqual(number_of_event_data, 11)

        number_of_warnings = storage_writer.GetNumberOfAttributeContainers(
            "extraction_warning"
        )
        self.assertEqual(number_of_warnings, 0)

        number_of_warnings = storage_writer.GetNumberOfAttributeContainers(
            "recovery_warning"
        )
        self.assertEqual(number_of_warnings, 0)

        expected_event_values = {
            "application_identifier": "858812b2-dcdf-11f1-8d81-f9e2c889fcff",
            "application_type": 3,
            "boot_time": "2026-11-10T00:20:52",
            "data_type": "windows:bootstat:boot",
            "last_boot_identifier": 0,
            "level": 1,
        }

        event_data = storage_writer.GetAttributeContainerByIndex("event_data", 0)
        self.CheckEventData(event_data, expected_event_values)

        expected_boot_values = [
            (7, "2026-11-26T11:31:16"),
            (8, "2026-11-26T11:37:37"),
            (9, "2026-11-26T12:04:51"),
            (10, "2026-11-26T12:14:36"),
        ]
        for event_data_index, (last_boot_identifier, boot_time) in enumerate(
            expected_boot_values, start=7
        ):
            expected_event_values = {
                "application_type": 3,
                "boot_time": boot_time,
                "data_type": "windows:bootstat:boot",
                "last_boot_identifier": last_boot_identifier,
            }

            event_data = storage_writer.GetAttributeContainerByIndex(
                "event_data", event_data_index
            )
            self.CheckEventData(event_data, expected_event_values)

        self.assertTrue(event_data.boot_time.is_local_time)

    def testParseWithEFISystemPartitionFile(self):
        """Tests the Parse function on an EFI system partition bootstat.dat file."""
        parser = windows_bootstat.WindowsBootStatusDataParser()
        storage_writer = self._ParseFile(["bootstat_esp.dat"], parser)

        number_of_event_data = storage_writer.GetNumberOfAttributeContainers(
            "event_data"
        )
        self.assertEqual(number_of_event_data, 11)

        number_of_warnings = storage_writer.GetNumberOfAttributeContainers(
            "extraction_warning"
        )
        self.assertEqual(number_of_warnings, 0)

        number_of_warnings = storage_writer.GetNumberOfAttributeContainers(
            "recovery_warning"
        )
        self.assertEqual(number_of_warnings, 0)

        expected_event_values = {
            "application_identifier": "9dea862c-5cdd-4e70-acc1-f32b344d4795",
            "application_type": 2,
            "boot_time": "2026-11-26T12:14:35",
            "data_type": "windows:bootstat:boot",
            "last_boot_identifier": None,
            "level": 1,
        }

        event_data = storage_writer.GetAttributeContainerByIndex("event_data", 10)
        self.CheckEventData(event_data, expected_event_values)

    def testParseWithTruncatedFile(self):
        """Tests the Parse function on a truncated bootstat.dat file."""
        parser = windows_bootstat.WindowsBootStatusDataParser()

        data = self._ReadTestFileData(["bootstat.dat"])

        for data_size in (0x804, 0x8000, 0x10000, len(data) - 1):
            storage_writer = self._CreateStorageWriter()
            parser_mediator = self._CreateParserMediator(storage_writer)

            file_object = self._CreateFileObject("bootstat.dat", data[:data_size])

            with self.assertRaises(errors.WrongParser):
                parser.Parse(parser_mediator, file_object)

    def testParseWithUnsupportedFormat(self):
        """Tests the Parse function on files of an unsupported format."""
        parser = windows_bootstat.WindowsBootStatusDataParser()

        for path_segments in (["Document.doc"], ["image.vmdk"], ["rp.log"]):
            data = self._ReadTestFileData(path_segments)

            storage_writer = self._CreateStorageWriter()
            parser_mediator = self._CreateParserMediator(storage_writer)

            file_object = self._CreateFileObject("bootstat.dat", data)

            with self.assertRaises(errors.WrongParser):
                parser.Parse(parser_mediator, file_object)


if __name__ == "__main__":
    unittest.main()
