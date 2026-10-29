#!/usr/bin/env python3
"""Tests for the SQLite-based storage."""

import csv
import gzip
import os
import shutil
import unittest

from acstore import sqlite_store
from acstore.containers import interface as containers_interface

from dfdatetime import factory as dfdatetime_factory
from dfdatetime import fat_date_time as dfdatetime_fat_date_time
from dfdatetime import filetime as dfdatetime_filetime
from dfdatetime import ole_automation_date as dfdatetime_ole_automation_date
from dfdatetime import rfc2579_date_time as dfdatetime_rfc2579_date_time
from dfdatetime import semantic_time as dfdatetime_semantic_time
from dfdatetime import systemtime as dfdatetime_systemtime
from dfdatetime import time_elements as dfdatetime_time_elements

from plaso.containers import events
from plaso.engine import configurations
from plaso.engine import profilers
from plaso.lib import definitions
from plaso.storage.sqlite import sqlite_file

from tests import test_lib as shared_test_lib
from tests.containers import test_lib as containers_test_lib
from tests.storage import test_lib


class _TestSQLiteStorageFileV20220716(sqlite_file.SQLiteStorageFile):
    """Test class for testing format compatibility checks."""

    _FORMAT_VERSION = 20220716
    _APPEND_COMPATIBLE_FORMAT_VERSION = 20211121
    _UPGRADE_COMPATIBLE_FORMAT_VERSION = 20211121
    _READ_COMPATIBLE_FORMAT_VERSION = 20211121


class _TestSQLiteStorageFileV20221023(sqlite_file.SQLiteStorageFile):
    """Test class for testing format compatibility checks."""

    _FORMAT_VERSION = 20221023
    _APPEND_COMPATIBLE_FORMAT_VERSION = 20221023
    _UPGRADE_COMPATIBLE_FORMAT_VERSION = 20221023
    _READ_COMPATIBLE_FORMAT_VERSION = 20211121


class SQLiteStorageFileTest(test_lib.StorageTestCase):
    """Tests for the SQLite-based storage file object."""

    # pylint: disable=protected-access

    def testInitialization(self):
        """Tests the __init__ function."""
        test_store = sqlite_file.SQLiteStorageFile()
        self.assertIsNotNone(test_store)

    def testCacheAttributeContainerByIndex(self):
        """Tests the _CacheAttributeContainerByIndex function."""
        event_data_stream = events.EventDataStream()

        with shared_test_lib.TempDirectory():
            test_store = sqlite_file.SQLiteStorageFile()

            self.assertEqual(len(test_store._attribute_container_cache), 0)

            test_store._CacheAttributeContainerByIndex(event_data_stream, 0)
            self.assertEqual(len(test_store._attribute_container_cache), 1)

    def testCheckStorageMetadata(self):
        """Tests the _CheckStorageMetadata function."""
        with shared_test_lib.TempDirectory():
            test_store = sqlite_file.SQLiteStorageFile()

            metadata_values = {
                "compression_format": definitions.COMPRESSION_FORMAT_ZLIB,
                "format_version": f"{test_store._FORMAT_VERSION:d}",
                "serialization_format": definitions.SERIALIZER_FORMAT_JSON,
            }
            test_store._CheckStorageMetadata(metadata_values)

            metadata_values["format_version"] = "bogus"
            with self.assertRaises(OSError):
                test_store._CheckStorageMetadata(metadata_values)

            metadata_values["format_version"] = "1"
            with self.assertRaises(OSError):
                test_store._CheckStorageMetadata(metadata_values)

            metadata_values["format_version"] = f"{test_store._FORMAT_VERSION:d}"
            metadata_values["compression_format"] = None
            with self.assertRaises(OSError):
                test_store._CheckStorageMetadata(metadata_values)

            metadata_values["compression_format"] = definitions.COMPRESSION_FORMAT_ZLIB
            metadata_values["serialization_format"] = None
            with self.assertRaises(OSError):
                test_store._CheckStorageMetadata(metadata_values)

            metadata_values["serialization_format"] = definitions.SERIALIZER_FORMAT_JSON
            with self.assertRaises(OSError):
                test_store._CheckStorageMetadata(metadata_values)

    def testCreateAttributeContainerTable(self):
        """Tests the _CreateAttributeContainerTable function."""
        event_data_stream = events.EventDataStream()

        with shared_test_lib.TempDirectory() as temp_directory:
            test_path = os.path.join(temp_directory, "plaso.sqlite")
            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path, read_only=False)

            try:
                test_store._CreateAttributeContainerTable(
                    event_data_stream.CONTAINER_TYPE
                )

                with self.assertRaises(OSError):
                    test_store._CreateAttributeContainerTable(
                        event_data_stream.CONTAINER_TYPE
                    )

            finally:
                test_store.Close()

    # TODO: add tests for _CreateAttributeContainerFromRow
    # TODO: add tests for _DeserializeAttributeContainer

    def testGetAttributeContainersWithFilter(self):
        """Tests the _GetAttributeContainersWithFilter function."""
        event_data_stream = events.EventDataStream()
        event_data_stream.md5_hash = "8f0bf95a7959baad9666b21a7feed79d"

        column_names = ["md5_hash"]

        with shared_test_lib.TempDirectory() as temp_directory:
            test_path = os.path.join(temp_directory, "plaso.sqlite")
            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path, read_only=False)

            try:
                containers = list(
                    test_store._GetAttributeContainersWithFilter(
                        event_data_stream.CONTAINER_TYPE, column_names=column_names
                    )
                )
                self.assertEqual(len(containers), 0)

                test_store.AddAttributeContainer(event_data_stream)

                containers = list(
                    test_store._GetAttributeContainersWithFilter(
                        event_data_stream.CONTAINER_TYPE, column_names=column_names
                    )
                )
                self.assertEqual(len(containers), 1)

                filter_expression = 'md5_hash == "8f0bf95a7959baad9666b21a7feed79d"'
                containers = list(
                    test_store._GetAttributeContainersWithFilter(
                        event_data_stream.CONTAINER_TYPE,
                        column_names=column_names,
                        filter_expression=filter_expression,
                    )
                )
                self.assertEqual(len(containers), 1)

                filter_expression = 'md5_hash != "8f0bf95a7959baad9666b21a7feed79d"'
                containers = list(
                    test_store._GetAttributeContainersWithFilter(
                        event_data_stream.CONTAINER_TYPE,
                        column_names=column_names,
                        filter_expression=filter_expression,
                    )
                )
                self.assertEqual(len(containers), 0)

                containers = list(
                    test_store._GetAttributeContainersWithFilter(
                        "bogus", column_names=column_names
                    )
                )
                self.assertEqual(len(containers), 0)

            finally:
                test_store.Close()

    def testGetCachedAttributeContainer(self):
        """Tests the _GetCachedAttributeContainer function."""
        event_data_stream = events.EventDataStream()

        with shared_test_lib.TempDirectory():
            test_store = sqlite_file.SQLiteStorageFile()

            attribute_container = test_store._GetCachedAttributeContainer(
                event_data_stream.CONTAINER_TYPE, 1
            )
            self.assertIsNone(attribute_container)

            test_store._CacheAttributeContainerByIndex(event_data_stream, 1)

            attribute_container = test_store._GetCachedAttributeContainer(
                event_data_stream.CONTAINER_TYPE, 1
            )
            self.assertIsNotNone(attribute_container)

    def testHasTable(self):
        """Tests the _HasTable function."""
        with shared_test_lib.TempDirectory() as temp_directory:
            test_path = os.path.join(temp_directory, "plaso.sqlite")
            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path, read_only=False)

            try:
                test_store._CreateAttributeContainerTable(
                    events.EventDataStream.CONTAINER_TYPE
                )

                result = test_store._HasTable(events.EventDataStream.CONTAINER_TYPE)
                self.assertTrue(result)

                result = test_store._HasTable("bogus")
                self.assertFalse(result)

            finally:
                test_store.Close()

    # TODO: add tests for _RaiseIfNotReadable
    # TODO: add tests for _RaiseIfNotWritable
    # TODO: add tests for _ReadAndCheckStorageMetadata
    # TODO: add tests for _SerializeAttributeContainer
    # TODO: add tests for _UpdateEventAfterDeserialize
    # TODO: add tests for _UpdateEventBeforeSerialize
    # TODO: add tests for _UpdateEventDataAfterDeserialize
    # TODO: add tests for _UpdateEventDataBeforeSerialize
    # TODO: add tests for _UpdateEventTagAfterDeserialize
    # TODO: add tests for _UpdateEventTagBeforeSerialize
    # TODO: add tests for _UpdateStorageMetadataFormatVersion

    def testWriteExistingAttributeContainer(self):
        """Tests the _WriteExistingAttributeContainer function."""
        event_data_stream = events.EventDataStream()

        with shared_test_lib.TempDirectory() as temp_directory:
            test_path = os.path.join(temp_directory, "plaso.sqlite")
            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path, read_only=False)

            try:
                number_of_containers = test_store._GetNumberOfAttributeContainerRows(
                    event_data_stream.CONTAINER_TYPE
                )
                self.assertEqual(number_of_containers, 0)

                test_store._WriteNewAttributeContainer(event_data_stream)

                number_of_containers = test_store._GetNumberOfAttributeContainerRows(
                    event_data_stream.CONTAINER_TYPE
                )
                self.assertEqual(number_of_containers, 1)

                test_store._WriteExistingAttributeContainer(event_data_stream)

                number_of_containers = test_store._GetNumberOfAttributeContainerRows(
                    event_data_stream.CONTAINER_TYPE
                )
                self.assertEqual(number_of_containers, 1)

            finally:
                test_store.Close()

    # TODO: add tests for _WriteMetadata
    # TODO: add tests for _WriteMetadataValue

    def testWriteNewAttributeContainer(self):
        """Tests the _WriteNewAttributeContainer function."""
        event_data_stream = events.EventDataStream()

        with shared_test_lib.TempDirectory() as temp_directory:
            test_path = os.path.join(temp_directory, "plaso.sqlite")
            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path, read_only=False)

            try:
                number_of_containers = test_store._GetNumberOfAttributeContainerRows(
                    event_data_stream.CONTAINER_TYPE
                )
                self.assertEqual(number_of_containers, 0)

                test_store._WriteNewAttributeContainer(event_data_stream)

                number_of_containers = test_store._GetNumberOfAttributeContainerRows(
                    event_data_stream.CONTAINER_TYPE
                )
                self.assertEqual(number_of_containers, 1)

            finally:
                test_store.Close()

    def testWriteNewAttributeContainerWithStorageProfiler(self):
        """Tests the _WriteNewAttributeContainer function with a storage profiler."""
        event_data = events.EventData()
        event_data.data_type = "test:event_data"
        event_data.body = "test" * 256

        profiling_configuration = configurations.ProfilingConfiguration()

        with shared_test_lib.TempDirectory() as temp_directory:
            profiling_configuration.directory = temp_directory

            test_profiler = profilers.StorageProfiler("test", profiling_configuration)
            test_profiler.Start()

            test_path = os.path.join(temp_directory, "plaso.sqlite")
            test_store = sqlite_file.SQLiteStorageFile()
            test_store.SetStorageProfiler(test_profiler)
            test_store.Open(path=test_path, read_only=False)

            try:
                test_store._WriteNewAttributeContainer(event_data)
            finally:
                test_store.Close()
                test_profiler.Stop()

            sample_path = os.path.join(temp_directory, "storage-test.csv.gz")
            with gzip.open(sample_path, "rt", encoding="utf-8") as file_object:
                rows = list(csv.reader(file_object, delimiter="\t"))

        write_rows = [row for row in rows if row[1] == "write_new"]
        self.assertEqual(len(write_rows), 1)

        data_size = int(write_rows[0][5])
        compressed_data_size = int(write_rows[0][6])

        self.assertGreater(data_size, compressed_data_size)

    def testWriteNewEventWithTypedColumns(self):
        """Tests the _WriteNewAttributeContainer function with typed event columns."""
        local_time_date_time = dfdatetime_filetime.Filetime(timestamp=2)
        local_time_date_time.is_local_time = True

        time_zone_date_time = dfdatetime_filetime.Filetime(timestamp=3)
        time_zone_date_time.time_zone_hint = "Europe/Brussels"
        time_zone_date_time.time_zone_offset = 60

        test_date_time_values = [
            dfdatetime_factory.Factory.NewDateTimeValues(class_name, timestamp=1)
            for class_name in (
                "APFSTime",
                "CocoaTime",
                "DelphiDateTime",
                "DotNetDateTime",
                "FATTimestamp",
                "Filetime",
                "HFSTime",
                "JavaTime",
                "OLEAutomationDate",
                "PosixTime",
                "PosixTimeInMicroseconds",
                "PosixTimeInMilliseconds",
                "PosixTimeInNanoseconds",
                "TSKTime",
                "UUIDTime",
                "WebKitTime",
            )
        ]
        test_date_time_values.extend(
            [
                dfdatetime_filetime.Filetime(timestamp=-1),
                local_time_date_time,
                time_zone_date_time,
                dfdatetime_ole_automation_date.OLEAutomationDate(timestamp=1.5),
                dfdatetime_fat_date_time.FATDateTime(fat_date_time=0xA8D03D0C),
                dfdatetime_rfc2579_date_time.RFC2579DateTime(
                    rfc2579_date_time_tuple=(2010, 8, 12, 20, 6, 31, 6, "+", 2, 0)
                ),
                dfdatetime_semantic_time.Never(),
                dfdatetime_semantic_time.NotSet(),
                dfdatetime_systemtime.Systemtime(
                    system_time_tuple=(2010, 8, 4, 12, 20, 6, 31, 142)
                ),
                dfdatetime_time_elements.TimeElements(
                    time_elements_tuple=(2010, 8, 12, 20, 6, 31)
                ),
                dfdatetime_time_elements.TimeElementsInMicroseconds(
                    time_elements_tuple=(2010, 8, 12, 20, 6, 31, 546875)
                ),
                None,
            ]
        )

        with shared_test_lib.TempDirectory() as temp_directory:
            test_path = os.path.join(temp_directory, "plaso.sqlite")
            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path, read_only=False)

            try:
                for sequence_number, date_time in enumerate(test_date_time_values):
                    event = events.EventObject()
                    event.date_time = date_time
                    event.timestamp = sequence_number
                    event.timestamp_desc = "Test Time"
                    event.SetEventDataIdentifier(
                        containers_interface.AttributeContainerIdentifier(
                            name="event_data", sequence_number=sequence_number + 1
                        )
                    )
                    test_store._WriteNewAttributeContainer(event)

                event = events.EventObject()
                event.timestamp = len(test_date_time_values)
                event.SetEventDataIdentifier(
                    containers_interface.AttributeContainerIdentifier(
                        name="bogus", sequence_number=1
                    )
                )
                test_store._WriteNewAttributeContainer(event)

                test_store._CommitWriteCache("event")

                test_store._cursor.execute(
                    "SELECT _event_data_identifier, date_time FROM event "
                    "WHERE rowid IN (6, 20, 28)"
                )
                rows = [tuple(row) for row in test_store._cursor.fetchall()]

            finally:
                test_store.Close()

            self.assertEqual(rows[0], (6, "Filetime:1"))
            self.assertEqual(rows[1][0], 20)
            self.assertTrue(rows[1][1].startswith('{"__class_name__": "OLEAuto'))
            self.assertEqual(rows[2], (28, None))

            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path)

            try:
                self.assertEqual(test_store.format_version, test_store._FORMAT_VERSION)

                test_events = list(test_store.GetSortedEvents())

            finally:
                test_store.Close()

        self.assertEqual(len(test_events), len(test_date_time_values) + 1)

        schema_helper = sqlite_store.SQLiteSchemaHelper()

        for sequence_number, date_time in enumerate(test_date_time_values):
            event = test_events[sequence_number]

            event_data_identifier = event.GetEventDataIdentifier()
            self.assertEqual(event_data_identifier.name, "event_data")
            self.assertEqual(event_data_identifier.sequence_number, sequence_number + 1)

            if date_time is None:
                self.assertIsNone(event.date_time)
                continue

            # The date and time values must be identical to the earlier JSON form.
            expected_date_time = schema_helper.DeserializeValue(
                "dfdatetime.DateTimeValues",
                schema_helper.SerializeValue("dfdatetime.DateTimeValues", date_time),
            )
            self.assertIs(type(event.date_time), type(expected_date_time))
            self.assertEqual(
                event.date_time.CopyToSerializableDict(),
                expected_date_time.CopyToSerializableDict(),
            )
            self.assertEqual(
                event.date_time.is_local_time, expected_date_time.is_local_time
            )

        event_data_identifier = test_events[-1].GetEventDataIdentifier()
        self.assertEqual(event_data_identifier.CopyToString(), "bogus.1")

    def testWriteNewEventWithEarlierFormatVersion(self):
        """Tests writing an event in a storage file of an earlier format version."""
        test_file_path = self._GetTestFilePath(["psort_test.plaso"])
        self._SkipIfPathNotExists(test_file_path)

        with shared_test_lib.TempDirectory() as temp_directory:
            test_path = os.path.join(temp_directory, "plaso.sqlite")
            shutil.copyfile(test_file_path, test_path)

            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path, read_only=False)

            try:
                number_of_events = test_store.GetNumberOfAttributeContainers("event")

                event = events.EventObject()
                event.date_time = dfdatetime_filetime.Filetime(timestamp=1)
                event.timestamp = 0
                event.timestamp_desc = "Test Time"
                event.SetEventDataIdentifier(
                    containers_interface.AttributeContainerIdentifier(
                        name="event_data", sequence_number=1
                    )
                )
                test_store.AddAttributeContainer(event)

            finally:
                test_store.Close()

            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path)

            try:
                self.assertEqual(test_store.format_version, 20260516)

                test_store._cursor.execute(
                    f"SELECT _event_data_identifier, date_time FROM event "
                    f"WHERE rowid = {number_of_events + 1:d}"
                )
                row = test_store._cursor.fetchone()

                test_events = list(test_store.GetSortedEvents())

            finally:
                test_store.Close()

        self.assertEqual(
            tuple(row),
            (
                "event_data.1",
                '{"__class_name__": "Filetime", "__type__": "DateTimeValues", '
                '"timestamp": 1}',
            ),
        )

        self.assertEqual(len(test_events), number_of_events + 1)

        event = test_events[0]
        self.assertEqual(event.GetEventDataIdentifier().CopyToString(), "event_data.1")
        self.assertEqual(
            event.date_time.CopyToSerializableDict(),
            {
                "__class_name__": "Filetime",
                "__type__": "DateTimeValues",
                "timestamp": 1,
            },
        )

    def testAddAttributeContainer(self):
        """Tests the AddAttributeContainer function."""
        event_data_stream = events.EventDataStream()

        with shared_test_lib.TempDirectory() as temp_directory:
            test_path = os.path.join(temp_directory, "plaso.sqlite")
            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path, read_only=False)

            try:
                number_of_containers = test_store.GetNumberOfAttributeContainers(
                    event_data_stream.CONTAINER_TYPE
                )
                self.assertEqual(number_of_containers, 0)

                test_store.AddAttributeContainer(event_data_stream)

                number_of_containers = test_store.GetNumberOfAttributeContainers(
                    event_data_stream.CONTAINER_TYPE
                )
                self.assertEqual(number_of_containers, 1)

            finally:
                test_store.Close()

            with self.assertRaises(OSError):
                test_store.AddAttributeContainer(event_data_stream)

    # TODO: add tests for CheckSupportedFormat

    def testGetAttributeContainers(self):
        """Tests the GetAttributeContainers function."""
        event_data_stream = events.EventDataStream()
        event_data_stream.md5_hash = "8f0bf95a7959baad9666b21a7feed79d"

        with shared_test_lib.TempDirectory() as temp_directory:
            test_path = os.path.join(temp_directory, "plaso.sqlite")
            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path, read_only=False)

            try:
                containers = list(
                    test_store.GetAttributeContainers(event_data_stream.CONTAINER_TYPE)
                )
                self.assertEqual(len(containers), 0)

                test_store.AddAttributeContainer(event_data_stream)

                containers = list(
                    test_store.GetAttributeContainers(event_data_stream.CONTAINER_TYPE)
                )
                self.assertEqual(len(containers), 1)

                filter_expression = 'md5_hash == "8f0bf95a7959baad9666b21a7feed79d"'
                containers = list(
                    test_store.GetAttributeContainers(
                        event_data_stream.CONTAINER_TYPE,
                        filter_expression=filter_expression,
                    )
                )
                self.assertEqual(len(containers), 1)

                filter_expression = 'md5_hash != "8f0bf95a7959baad9666b21a7feed79d"'
                containers = list(
                    test_store.GetAttributeContainers(
                        event_data_stream.CONTAINER_TYPE,
                        filter_expression=filter_expression,
                    )
                )
                self.assertEqual(len(containers), 0)

                containers = list(test_store.GetAttributeContainers("bogus"))
                self.assertEqual(len(containers), 0)

            finally:
                test_store.Close()

    def testGetAttributeContainerByIdentifier(self):
        """Tests the GetAttributeContainerByIdentifier function."""
        event_data_stream = events.EventDataStream()

        with shared_test_lib.TempDirectory() as temp_directory:
            test_path = os.path.join(temp_directory, "plaso.sqlite")
            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path, read_only=False)

            try:
                test_store.AddAttributeContainer(event_data_stream)

                identifier = event_data_stream.GetIdentifier()

                container = test_store.GetAttributeContainerByIdentifier(
                    event_data_stream.CONTAINER_TYPE, identifier
                )
                self.assertIsNotNone(container)

                identifier.sequence_number = 99

                container = test_store.GetAttributeContainerByIdentifier(
                    event_data_stream.CONTAINER_TYPE, identifier
                )
                self.assertIsNone(container)

            finally:
                test_store.Close()

    def testGetAttributeContainerByIndex(self):
        """Tests the GetAttributeContainerByIndex function."""
        event_data_stream = events.EventDataStream()

        with shared_test_lib.TempDirectory() as temp_directory:
            test_path = os.path.join(temp_directory, "plaso.sqlite")
            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path, read_only=False)

            try:
                container = test_store.GetAttributeContainerByIndex(
                    event_data_stream.CONTAINER_TYPE, 0
                )
                self.assertIsNone(container)

                test_store.AddAttributeContainer(event_data_stream)

                container = test_store.GetAttributeContainerByIndex(
                    event_data_stream.CONTAINER_TYPE, 0
                )
                self.assertIsNotNone(container)

                container = test_store.GetAttributeContainerByIndex("bogus", 0)
                self.assertIsNone(container)

            finally:
                test_store.Close()

    def testGetAttributeContainerByIndexWithEventData(self):
        """Tests the GetAttributeContainerByIndex function with event data."""
        event_data = events.EventData(data_type="test:event")
        event_data._corrupted = True
        event_data._recovered = True

        with shared_test_lib.TempDirectory() as temp_directory:
            test_path = os.path.join(temp_directory, "plaso.sqlite")
            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path, read_only=False)

            try:
                test_store.AddAttributeContainer(event_data)
            finally:
                test_store.Close()

            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path)

            try:
                container = test_store.GetAttributeContainerByIndex(
                    event_data.CONTAINER_TYPE, 0
                )
                self.assertIsNotNone(container)
                self.assertTrue(container._corrupted)
                self.assertTrue(container._recovered)

            finally:
                test_store.Close()

    def testGetNumberOfAttributeContainers(self):
        """Tests the GetNumberOfAttributeContainers function."""
        event_data_stream = events.EventDataStream()

        with shared_test_lib.TempDirectory() as temp_directory:
            test_path = os.path.join(temp_directory, "plaso.sqlite")
            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path, read_only=False)

            try:
                number_of_containers = test_store.GetNumberOfAttributeContainers(
                    event_data_stream.CONTAINER_TYPE
                )
                self.assertEqual(number_of_containers, 0)

                test_store.AddAttributeContainer(event_data_stream)

                number_of_containers = test_store.GetNumberOfAttributeContainers(
                    event_data_stream.CONTAINER_TYPE
                )
                self.assertEqual(number_of_containers, 1)

                number_of_containers = test_store.GetNumberOfAttributeContainers(
                    "bogus"
                )
                self.assertEqual(number_of_containers, 0)

            finally:
                test_store.Close()

    def testGetSortedEvents(self):
        """Tests the GetSortedEvents function."""
        with shared_test_lib.TempDirectory() as temp_directory:
            test_path = os.path.join(temp_directory, "plaso.sqlite")
            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path, read_only=False)

            try:
                for (
                    event,
                    event_data,
                    event_data_stream,
                ) in containers_test_lib.CreateEventsFromValues(self._TEST_EVENTS):
                    test_store.AddAttributeContainer(event_data_stream)

                    event_data.SetEventDataStreamIdentifier(
                        event_data_stream.GetIdentifier()
                    )
                    test_store.AddAttributeContainer(event_data)

                    event.SetEventDataIdentifier(event_data.GetIdentifier())
                    test_store.AddAttributeContainer(event)

            finally:
                test_store.Close()

            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path)

            try:
                test_events = list(test_store.GetSortedEvents())
                self.assertEqual(len(test_events), 4)

            finally:
                test_store.Close()

        # TODO: add test with time range.

    def testHasAttributeContainers(self):
        """Tests the HasAttributeContainers function."""
        event_data_stream = events.EventDataStream()

        with shared_test_lib.TempDirectory() as temp_directory:
            test_path = os.path.join(temp_directory, "plaso.sqlite")
            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path, read_only=False)

            try:
                result = test_store.HasAttributeContainers(
                    event_data_stream.CONTAINER_TYPE
                )
                self.assertFalse(result)

                test_store.AddAttributeContainer(event_data_stream)

                result = test_store.HasAttributeContainers(
                    event_data_stream.CONTAINER_TYPE
                )
                self.assertTrue(result)

                result = test_store.HasAttributeContainers("bogus")
                self.assertFalse(result)

            finally:
                test_store.Close()

    # TODO: add tests for Open and Close

    def testUpdateAttributeContainer(self):
        """Tests the UpdateAttributeContainer function."""
        event_data_stream = events.EventDataStream()

        with shared_test_lib.TempDirectory() as temp_directory:
            test_path = os.path.join(temp_directory, "plaso.sqlite")
            test_store = sqlite_file.SQLiteStorageFile()
            test_store.Open(path=test_path, read_only=False)

            try:
                number_of_containers = test_store.GetNumberOfAttributeContainers(
                    event_data_stream.CONTAINER_TYPE
                )
                self.assertEqual(number_of_containers, 0)

                test_store.AddAttributeContainer(event_data_stream)

                number_of_containers = test_store.GetNumberOfAttributeContainers(
                    event_data_stream.CONTAINER_TYPE
                )
                self.assertEqual(number_of_containers, 1)

                test_store.UpdateAttributeContainer(event_data_stream)

                number_of_containers = test_store.GetNumberOfAttributeContainers(
                    event_data_stream.CONTAINER_TYPE
                )
                self.assertEqual(number_of_containers, 1)

            finally:
                test_store.Close()

    def testVersionCompatibility(self):
        """Tests the version compatibility methods."""
        with shared_test_lib.TempDirectory() as temp_directory:
            v1_storage_path = os.path.join(temp_directory, "v20220716.sqlite")
            v1_test_store = _TestSQLiteStorageFileV20220716()
            v1_test_store.Open(path=v1_storage_path, read_only=False)
            v1_test_store.Close()

            v2_test_store_rw = _TestSQLiteStorageFileV20221023()

            with self.assertRaises(OSError):
                v2_test_store_rw.Open(path=v1_storage_path, read_only=False)

            v2_test_store_ro = _TestSQLiteStorageFileV20221023()
            v2_test_store_ro.Open(path=v1_storage_path, read_only=True)
            v2_test_store_ro.Close()


if __name__ == "__main__":
    unittest.main()
