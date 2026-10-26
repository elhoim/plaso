#!/usr/bin/env python3
"""Tests the multi-process processing engine."""

import collections
import multiprocessing
import os
import time
import unittest

from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.path import factory as path_spec_factory

from plaso.containers import artifacts
from plaso.containers import sessions
from plaso.containers import tasks
from plaso.lib import definitions
from plaso.engine import configurations
from plaso.multi_process import extraction_engine
from plaso.multi_process import merge_helpers
from plaso.storage import factory as storage_factory
from plaso.storage.sqlite import writer as sqlite_writer

from tests import test_lib as shared_test_lib


class ExtractionMultiProcessEngineTest(shared_test_lib.BaseTestCase):
    """Tests for the task-based multi-process extraction engine."""

    def _ProcessSource(self, source_path_spec):
        """Tests the PreprocessSource and ProcessSource functions.

        Args:
          path_spec (dfvfs.PathSpec): path specification of the source.
        """
        test_artifacts_path = shared_test_lib.GetTestFilePath(["artifacts"])
        self._SkipIfPathNotExists(test_artifacts_path)

        test_engine = extraction_engine.ExtractionMultiProcessEngine(
            maximum_number_of_tasks=100
        )
        test_engine.BuildArtifactsRegistry(test_artifacts_path, None)

        session = sessions.Session()

        processing_configuration = configurations.ProcessingConfiguration()
        processing_configuration.data_location = shared_test_lib.DATA_PATH
        processing_configuration.parser_filter_expression = "filestat"
        processing_configuration.task_storage_format = definitions.STORAGE_FORMAT_SQLITE

        with shared_test_lib.TempDirectory() as temp_directory:
            temp_file = os.path.join(temp_directory, "storage.plaso")
            storage_writer = sqlite_writer.SQLiteStorageWriter()
            storage_writer.Open(path=temp_file)

            try:
                system_configurations = test_engine.PreprocessSource(
                    [source_path_spec], storage_writer
                )
                # The method is named ProcessSourceMulti because pylint 2.6.0 and later
                # gets confused about keyword arguments when ProcessSource is used.
                processing_status = test_engine.ProcessSourceMulti(
                    storage_writer,
                    session.identifier,
                    processing_configuration,
                    system_configurations,
                    [source_path_spec],
                    storage_file_path=temp_directory,
                )
                number_of_events = storage_writer.GetNumberOfAttributeContainers(
                    "event"
                )
                number_of_extraction_warnings = (
                    storage_writer.GetNumberOfAttributeContainers("extraction_warning")
                )
                number_of_recovery_warnings = (
                    storage_writer.GetNumberOfAttributeContainers("recovery_warning")
                )
                parsers_counter = collections.Counter(
                    {
                        parser_count.name: parser_count.number_of_events
                        for parser_count in storage_writer.GetAttributeContainers(
                            "parser_count"
                        )
                    }
                )

            finally:
                storage_writer.Close()

        self.assertFalse(processing_status.aborted)

        self.assertEqual(number_of_events, 15)
        self.assertEqual(number_of_extraction_warnings, 0)
        self.assertEqual(number_of_recovery_warnings, 0)

        expected_parsers_counter = collections.Counter({"filestat": 15, "total": 15})
        self.assertEqual(parsers_counter, expected_parsers_counter)

    def testInternalMergeAttributeContainers(self):
        """Tests the _MergeAttributeContainers function."""
        # pylint: disable=protected-access
        session = sessions.Session()
        task = tasks.Task(session_identifier=session.identifier)

        test_engine = extraction_engine.ExtractionMultiProcessEngine()

        with shared_test_lib.TempDirectory() as temp_directory:
            task_storage_path = os.path.join(temp_directory, "task.plaso")
            task_storage_writer = (
                storage_factory.StorageFactory.CreateTaskStorageWriter(
                    definitions.STORAGE_FORMAT_SQLITE
                )
            )
            task_storage_writer.Open(path=task_storage_path)

            try:
                message_file = artifacts.WindowsEventLogMessageFileArtifact(
                    path="\\Windows\\System32\\test.dll"
                )
                task_storage_writer.AddAttributeContainer(message_file)

                message_table = artifacts.WindowsEventLogMessageTableArtifact(
                    language_identifier=0x00000409
                )
                message_table.SetMessageFileIdentifier(message_file.GetIdentifier())
                task_storage_writer.AddAttributeContainer(message_table)

                message_string = artifacts.WindowsEventLogMessageStringArtifact(
                    message_identifier=0xB0010001, string="A test value"
                )
                message_string.SetMessageTableIdentifier(message_table.GetIdentifier())
                task_storage_writer.AddAttributeContainer(message_string)

            finally:
                task_storage_writer.Close()

            storage_path = os.path.join(temp_directory, "storage.plaso")
            storage_writer = sqlite_writer.SQLiteStorageWriter()
            storage_writer.Open(path=storage_path)

            try:
                # Add a message file and table to the session store so that the
                # identifiers of the merged containers differ from those in the
                # task store.
                storage_writer.AddAttributeContainer(
                    artifacts.WindowsEventLogMessageFileArtifact(
                        path="\\Windows\\System32\\other.dll"
                    )
                )
                storage_writer.AddAttributeContainer(
                    artifacts.WindowsEventLogMessageTableArtifact(
                        language_identifier=0x00000409
                    )
                )

                task_storage_reader = (
                    storage_factory.StorageFactory.CreateTaskStorageReader(
                        definitions.STORAGE_FORMAT_SQLITE, task, task_storage_path
                    )
                )
                merge_helper = merge_helpers.ExtractionTaskMergeHelper(
                    task_storage_reader, task.identifier
                )

                try:
                    test_engine._MergeAttributeContainers(storage_writer, merge_helper)
                finally:
                    merge_helper.Close()

                self.assertTrue(merge_helper.fully_merged)

                number_of_message_tables = (
                    storage_writer.GetNumberOfAttributeContainers(
                        "windows_eventlog_message_table"
                    )
                )
                self.assertEqual(number_of_message_tables, 2)

                number_of_message_strings = (
                    storage_writer.GetNumberOfAttributeContainers(
                        "windows_eventlog_message_string"
                    )
                )
                self.assertEqual(number_of_message_strings, 1)

                message_string = storage_writer.GetAttributeContainerByIndex(
                    "windows_eventlog_message_string", 0
                )
                message_table = storage_writer.GetAttributeContainerByIdentifier(
                    "windows_eventlog_message_table",
                    message_string.GetMessageTableIdentifier(),
                )
                self.assertIsNotNone(message_table)

                message_file = storage_writer.GetAttributeContainerByIdentifier(
                    "windows_eventlog_message_file",
                    message_table.GetMessageFileIdentifier(),
                )
                self.assertIsNotNone(message_file)
                self.assertEqual(message_file.path, "\\Windows\\System32\\test.dll")

            finally:
                storage_writer.Close()

    def testInternalUpdateProcessingStatus(self):
        """Tests the _UpdateProcessingStatus function."""
        # pylint: disable=protected-access

        # The worker timeout is specified in minutes.
        test_engine = extraction_engine.ExtractionMultiProcessEngine(worker_timeout=5.0)

        process = multiprocessing.Process(name="Worker_00")
        test_engine._processes_per_pid[1] = process
        test_engine._process_information_per_pid[1] = None

        process_status = {
            "last_activity_timestamp": time.time() - 60.0,
            "processing_status": definitions.STATUS_INDICATOR_RUNNING,
        }
        test_engine._UpdateProcessingStatus(1, process_status, 0)

        worker_status = test_engine._processing_status.workers_status[0]
        self.assertEqual(worker_status.status, definitions.STATUS_INDICATOR_RUNNING)

        process_status = {
            "last_activity_timestamp": time.time() - 600.0,
            "processing_status": definitions.STATUS_INDICATOR_RUNNING,
        }
        test_engine._UpdateProcessingStatus(1, process_status, 0)

        worker_status = test_engine._processing_status.workers_status[0]
        self.assertEqual(
            worker_status.status, definitions.STATUS_INDICATOR_NOT_RESPONDING
        )

    def testProcessSource(self):
        """Tests the PreprocessSource and ProcessSource functions."""
        test_file_path = self._GetTestFilePath(["ímynd.dd"])
        self._SkipIfPathNotExists(test_file_path)

        os_path_spec = path_spec_factory.Factory.NewPathSpec(
            dfvfs_definitions.TYPE_INDICATOR_OS, location=test_file_path
        )
        source_path_spec = path_spec_factory.Factory.NewPathSpec(
            dfvfs_definitions.TYPE_INDICATOR_EXT, location="/", parent=os_path_spec
        )
        self._ProcessSource(source_path_spec)

    def testProcessSourceWithTsk(self):
        """Tests the PreprocessSource and ProcessSource functions."""
        # Testing with TSK helps catch potential issues with TSKTime.
        test_file_path = self._GetTestFilePath(["ímynd.dd"])
        self._SkipIfPathNotExists(test_file_path)

        os_path_spec = path_spec_factory.Factory.NewPathSpec(
            dfvfs_definitions.TYPE_INDICATOR_OS, location=test_file_path
        )
        source_path_spec = path_spec_factory.Factory.NewPathSpec(
            dfvfs_definitions.TYPE_INDICATOR_TSK, location="/", parent=os_path_spec
        )
        self._ProcessSource(source_path_spec)


if __name__ == "__main__":
    unittest.main()
