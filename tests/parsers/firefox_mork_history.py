#!/usr/bin/env python3
"""Tests for the Mozilla Firefox history Mork file parser."""

import unittest

from plaso.lib import errors
from plaso.parsers import firefox_mork_history

from tests.parsers import test_lib


class MorkReaderTest(test_lib.ParserTestCase):
    """Tests for the Mork file reader."""

    def testReadData(self):
        """Tests the ReadData function."""
        mork_reader = firefox_mork_history.MorkReader()
        mork_reader.ReadData(
            b"< <(a=c)> (80=URL)(81=Name)>\n"
            b"<(90=https://www.example.com/)>\n"
            b"{1:^80 [1(^80^90)(^81=a\\)b$41)]}\n"
        )

        self.assertEqual(
            mork_reader.rows,
            {"1": {"Name": b"a)bA", "URL": b"https://www.example.com/"}},
        )

        # Test with a committed group that updates a row.
        mork_reader = firefox_mork_history.MorkReader()
        mork_reader.ReadData(
            b"[1(URL=https://www.example.com/)(VisitCount=1)]\n"
            b"@$${1{@[1(VisitCount=2)]@$$}1}@\n"
        )

        self.assertEqual(mork_reader.rows["1"]["VisitCount"], b"2")

        # Test with an aborted group that updates a row.
        mork_reader = firefox_mork_history.MorkReader()
        mork_reader.ReadData(
            b"[1(URL=https://www.example.com/)(VisitCount=1)]\n"
            b"@$${1{@[1(VisitCount=2)]@$$}~~}@\n"
        )

        self.assertEqual(mork_reader.rows["1"]["VisitCount"], b"1")

        # Test with a cut row that replaces all cells.
        mork_reader = firefox_mork_history.MorkReader()
        mork_reader.ReadData(
            b"[1(URL=https://www.example.com/)(VisitCount=1)]\n[-1(VisitCount=2)]\n"
        )

        self.assertEqual(mork_reader.rows["1"], {"VisitCount": b"2"})

        # Test with an unterminated literal value.
        mork_reader = firefox_mork_history.MorkReader()
        with self.assertRaises(ValueError):
            mork_reader.ReadData(b"[1(URL=https://www.example.com/")

        # Test with an invalid hexadecimal escape.
        mork_reader = firefox_mork_history.MorkReader()
        with self.assertRaises(ValueError):
            mork_reader.ReadData(b"[1(URL=$+1)]")

        # Test with nested row meta data.
        mork_reader = firefox_mork_history.MorkReader()
        with self.assertRaises(ValueError):
            mork_reader.ReadData(b"[1[2[3(URL=a)]]]")


class FirefoxMorkHistoryParserTest(test_lib.ParserTestCase):
    """Tests for the Mozilla Firefox history Mork file parser."""

    def testParse(self):
        """Tests the Parse function."""
        parser = firefox_mork_history.FirefoxMorkHistoryParser()
        storage_writer = self._ParseFile(["firefox_history.dat"], parser)

        number_of_event_data = storage_writer.GetNumberOfAttributeContainers(
            "event_data"
        )
        self.assertEqual(number_of_event_data, 4)

        number_of_warnings = storage_writer.GetNumberOfAttributeContainers(
            "extraction_warning"
        )
        self.assertEqual(number_of_warnings, 1)

        number_of_warnings = storage_writer.GetNumberOfAttributeContainers(
            "recovery_warning"
        )
        self.assertEqual(number_of_warnings, 0)

        # The last visited time and visit count are updated by a committed group.
        expected_event_values = {
            "data_type": "firefox:mork:history_entry",
            "first_visited_time": "2007-12-13T16:10:00.000000+00:00",
            "hidden": False,
            "hostname": "www.example.com",
            "last_visited_time": "2007-12-14T16:00:00.000000+00:00",
            "referrer": None,
            "title": "Example Domain",
            "typed": True,
            "url": "https://www.example.com/",
            "visit_count": 3,
        }

        event_data = storage_writer.GetAttributeContainerByIndex("event_data", 0)
        self.CheckEventData(event_data, expected_event_values)

        # The update in an aborted group is ignored.
        expected_event_values = {
            "data_type": "firefox:mork:history_entry",
            "first_visited_time": "2007-12-13T16:13:20.000000+00:00",
            "hidden": True,
            "hostname": "plaso.example.org",
            "last_visited_time": "2007-12-13T16:13:20.000000+00:00",
            "referrer": "https://www.example.com/",
            "title": "Plaso )",
            "typed": False,
            "url": "https://plaso.example.org/docs/index.html",
            "visit_count": 1,
        }

        event_data = storage_writer.GetAttributeContainerByIndex("event_data", 1)
        self.CheckEventData(event_data, expected_event_values)

        # A title without NUL bytes is decoded with the byte order of the file.
        expected_event_values = {
            "data_type": "firefox:mork:history_entry",
            "last_visited_time": "2007-12-13T16:15:00.000000+00:00",
            "title": "\u65e5\u672c",
            "url": "https://www.example.jp/",
        }

        event_data = storage_writer.GetAttributeContainerByIndex("event_data", 2)
        self.CheckEventData(event_data, expected_event_values)

        expected_event_values = {
            "data_type": "firefox:mork:history_entry",
            "first_visited_time": None,
            "last_visited_time": None,
            "url": "https://broken.example.net/",
        }

        event_data = storage_writer.GetAttributeContainerByIndex("event_data", 3)
        self.CheckEventData(event_data, expected_event_values)

    def testParseFileObjectOnNearMisses(self):
        """Tests the ParseFileObject function on data that is not supported."""
        parser = firefox_mork_history.FirefoxMorkHistoryParser()
        storage_writer = self._CreateStorageWriter()
        parser_mediator = self._CreateParserMediator(storage_writer)

        # Test with a comment that is not a Mork header.
        file_object = self._CreateFileObject(
            "history.dat", b"// <!-- <mdb:mork:y/> -->\n< <(a=c)> (80=URL)>\n"
        )
        with self.assertRaises(errors.WrongParser):
            parser.ParseFileObject(parser_mediator, file_object)

        # Test with an unsupported Mork version.
        file_object = self._CreateFileObject(
            "history.dat", b'// <!-- <mdb:mork:z v="1.3"/> -->\n'
        )
        with self.assertRaises(errors.WrongParser):
            parser.ParseFileObject(parser_mediator, file_object)

        # Test with a Mork file without history rows, such as form history.
        file_object = self._CreateFileObject(
            "formhistory.dat",
            (
                b'// <!-- <mdb:mork:z v="1.4"/> -->\n'
                b"< <(a=c)> (80=Name)(81=Value)>\n"
                b"{1:^80 [1(^80=q)(^81=plaso)]}\n"
            ),
        )
        parser.ParseFileObject(parser_mediator, file_object)

        number_of_event_data = storage_writer.GetNumberOfAttributeContainers(
            "event_data"
        )
        self.assertEqual(number_of_event_data, 0)

        number_of_warnings = storage_writer.GetNumberOfAttributeContainers(
            "extraction_warning"
        )
        self.assertEqual(number_of_warnings, 0)

        # Test with truncated Mork data.
        file_object = self._CreateFileObject(
            "history.dat",
            (
                b'// <!-- <mdb:mork:z v="1.4"/> -->\n'
                b"< <(a=c)> (80=URL)>\n"
                b"{1:^80 [1(^80=https://www.example.com/)] [2(^80=https://www"
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
        self.assertEqual(number_of_warnings, 1)


if __name__ == "__main__":
    unittest.main()
