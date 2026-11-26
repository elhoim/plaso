#!/usr/bin/env python3
"""Tests for the Google Chrome or Chromium session (SNSS) file parser."""

import unittest

from plaso.lib import errors
from plaso.parsers import chrome_snss

from tests.parsers import test_lib


class ChromeSNSSParserTest(test_lib.ParserTestCase):
    """Tests for the Google Chrome or Chromium session (SNSS) file parser."""

    # Set tab window command of window 1 and tab 2.
    _SET_TAB_WINDOW_COMMAND = b"\x09\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00"

    def testParseFileObjectWithInvalidData(self):
        """Tests the ParseFileObject function with invalid data."""
        parser = chrome_snss.ChromeSNSSParser()

        storage_writer = self._CreateStorageWriter()
        parser_mediator = self._CreateParserMediator(storage_writer)

        # Test with invalid signature.
        file_object = self._CreateFileObject("snss", b"SSNS\x03\x00\x00\x00")

        with self.assertRaises(errors.WrongParser):
            parser.ParseFileObject(parser_mediator, file_object)

        # Test with unsupported, encrypted, format version.
        file_object = self._CreateFileObject("snss", b"SNSS\x04\x00\x00\x00")

        with self.assertRaises(errors.WrongParser):
            parser.ParseFileObject(parser_mediator, file_object)

        # Test with a truncated command.
        file_object = self._CreateFileObject(
            "snss",
            b"".join([b"SNSS\x03\x00\x00\x00", self._SET_TAB_WINDOW_COMMAND[:-1]]),
        )
        parser.ParseFileObject(parser_mediator, file_object)

        number_of_warnings = storage_writer.GetNumberOfAttributeContainers(
            "extraction_warning"
        )
        self.assertEqual(number_of_warnings, 1)

        # Test with a command size of 0.
        file_object = self._CreateFileObject(
            "snss",
            b"".join(
                [b"SNSS\x03\x00\x00\x00", b"\x00\x00\x00", self._SET_TAB_WINDOW_COMMAND]
            ),
        )
        parser.ParseFileObject(parser_mediator, file_object)

        number_of_warnings = storage_writer.GetNumberOfAttributeContainers(
            "extraction_warning"
        )
        self.assertEqual(number_of_warnings, 2)

        number_of_event_data = storage_writer.GetNumberOfAttributeContainers(
            "event_data"
        )
        self.assertEqual(number_of_event_data, 0)

    def testParseFileObjectWithLastActiveTime(self):
        """Tests the ParseFileObject function with last active time commands."""
        parser = chrome_snss.ChromeSNSSParser()

        storage_writer = self._CreateStorageWriter()
        parser_mediator = self._CreateParserMediator(storage_writer)

        # Format version 1 file with a last active time command written by Chrome
        # 130 or later and one written by an earlier version of Chrome, which
        # contains a monotonic time.
        file_object = self._CreateFileObject(
            "snss",
            b"".join(
                [
                    b"SNSS\x01\x00\x00\x00",
                    b"\x11\x00\x15\x02\x00\x00\x00\x00\x00\x00\x00",
                    b"\xcd\xf9\x16\x03\xc2\xbf\x2f\x00",
                    b"\x11\x00\x15\x03\x00\x00\x00\x00\x00\x00\x00",
                    b"\x00\x10\x00\x00\x00\x00\x00\x00",
                ]
            ),
        )
        parser.ParseFileObject(parser_mediator, file_object)

        number_of_event_data = storage_writer.GetNumberOfAttributeContainers(
            "event_data"
        )
        self.assertEqual(number_of_event_data, 1)

        number_of_warnings = storage_writer.GetNumberOfAttributeContainers(
            "extraction_warning"
        )
        self.assertEqual(number_of_warnings, 0)

        expected_event_values = {
            "data_type": "chrome:session:tab_last_active",
            "last_active_time": "2026-11-26T10:51:41.798861+00:00",
            "tab_identifier": 2,
        }

        event_data = storage_writer.GetAttributeContainerByIndex("event_data", 0)
        self.CheckEventData(event_data, expected_event_values)

    def testParseNonSNSSFile(self):
        """Tests the Parse function on a file that is not a SNSS file."""
        parser = chrome_snss.ChromeSNSSParser()

        with self.assertRaises(errors.WrongParser):
            self._ParseFile(["chrome", "History"], parser)

    def testParseSession(self):
        """Tests the Parse function on a session file."""
        parser = chrome_snss.ChromeSNSSParser()
        storage_writer = self._ParseFile(
            ["chrome", "Sessions", "Session_13440163903006940"], parser
        )

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
            "data_type": "chrome:session:navigation",
            "http_status_code": 200,
            "last_visited_time": "2026-11-26T10:51:43.158970+00:00",
            "navigation_index": 1,
            "page_transition_type": 1,
            "referrer_url": None,
            "tab_identifier": 740591214,
            "title": "Plaso SNSS test page 1",
            "url": "http://127.0.0.1:8765/page1.html",
            "window_identifier": 740591213,
        }

        event_data = storage_writer.GetAttributeContainerByIndex("event_data", 4)
        self.CheckEventData(event_data, expected_event_values)

        expected_event_values = {
            "data_type": "chrome:session:navigation",
            "http_status_code": 200,
            "last_visited_time": "2026-11-26T10:51:46.329590+00:00",
            "navigation_index": 2,
            "page_transition_type": 0,
            "referrer_url": "http://127.0.0.1:8765/page1.html",
            "tab_identifier": 740591214,
            "title": None,
            "url": "http://127.0.0.1:8765/page2.html",
            "window_identifier": 740591213,
        }

        event_data = storage_writer.GetAttributeContainerByIndex("event_data", 5)
        self.CheckEventData(event_data, expected_event_values)

        expected_event_values = {
            "close_time": "2026-11-26T10:51:48.900368+00:00",
            "data_type": "chrome:session:tab_closed",
            "tab_identifier": 740591215,
        }

        event_data = storage_writer.GetAttributeContainerByIndex("event_data", 9)
        self.CheckEventData(event_data, expected_event_values)

        expected_event_values = {
            "data_type": "chrome:session:tab_last_active",
            "last_active_time": "2026-11-26T10:51:48.912342+00:00",
            "tab_identifier": 740591214,
        }

        event_data = storage_writer.GetAttributeContainerByIndex("event_data", 10)
        self.CheckEventData(event_data, expected_event_values)

    def testParseTabRestore(self):
        """Tests the Parse function on a tab restore file."""
        parser = chrome_snss.ChromeSNSSParser()
        storage_writer = self._ParseFile(
            ["chrome", "Sessions", "Tabs_13440163911400787"], parser
        )

        number_of_event_data = storage_writer.GetNumberOfAttributeContainers(
            "event_data"
        )
        self.assertEqual(number_of_event_data, 8)

        number_of_warnings = storage_writer.GetNumberOfAttributeContainers(
            "extraction_warning"
        )
        self.assertEqual(number_of_warnings, 0)

        number_of_warnings = storage_writer.GetNumberOfAttributeContainers(
            "recovery_warning"
        )
        self.assertEqual(number_of_warnings, 0)

        expected_event_values = {
            "close_time": "2026-11-26T10:51:48.899151+00:00",
            "data_type": "chrome:session:tab_closed",
            "tab_identifier": 740591216,
        }

        event_data = storage_writer.GetAttributeContainerByIndex("event_data", 0)
        self.CheckEventData(event_data, expected_event_values)

        expected_event_values = {
            "data_type": "chrome:session:navigation",
            "http_status_code": 200,
            "last_visited_time": "2026-11-26T10:51:47.795537+00:00",
            "navigation_index": 1,
            "page_transition_type": 1,
            "referrer_url": None,
            "tab_identifier": 740591216,
            "title": "Plaso SNSS test page 3",
            "url": "http://127.0.0.1:8765/page3.html",
            "window_identifier": None,
        }

        event_data = storage_writer.GetAttributeContainerByIndex("event_data", 2)
        self.CheckEventData(event_data, expected_event_values)

        expected_event_values = {
            "close_time": "2026-11-26T10:51:52.168134+00:00",
            "data_type": "chrome:session:window_closed",
            "window_identifier": 740591217,
        }

        event_data = storage_writer.GetAttributeContainerByIndex("event_data", 3)
        self.CheckEventData(event_data, expected_event_values)


if __name__ == "__main__":
    unittest.main()
