#!/usr/bin/env python3
"""Tests the multi-process processing engine."""

import collections
import multiprocessing
import os
import time
import unittest

from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.path import factory as path_spec_factory

from plaso.containers import sessions
from plaso.lib import definitions
from plaso.engine import configurations
from plaso.multi_process import extraction_engine
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

    def _MergeTaskStorageWithInvalidTaskStorage(self, task_storage_data):
        """Merges an invalid task storage with the _MergeTaskStorage function.

        Args:
          task_storage_data (bytes): data of the invalid task storage file.
        """
        # pylint: disable=protected-access
        session = sessions.Session()

        test_engine = extraction_engine.ExtractionMultiProcessEngine()
        test_engine._processing_configuration = configurations.ProcessingConfiguration()
        test_engine._task_storage_format = definitions.STORAGE_FORMAT_SQLITE

        with shared_test_lib.TempDirectory() as temp_directory:
            test_engine._storage_file_path = os.path.join(
                temp_directory, "storage.plaso"
            )
            test_engine._StartTaskStorage(definitions.STORAGE_FORMAT_SQLITE)

            task = test_engine._task_manager.CreateTask(session.identifier)
            test_engine._task_manager.UpdateTaskAsProcessingByIdentifier(
                task.identifier
            )

            task_storage_path = test_engine._GetProcessedStorageFilePath(task)
            with open(task_storage_path, "wb") as file_object:
                file_object.write(task_storage_data)

            storage_writer = sqlite_writer.SQLiteStorageWriter()
            storage_writer.Open(path=test_engine._storage_file_path)

            try:
                test_engine._MergeTaskStorage(storage_writer, session.identifier)
            finally:
                storage_writer.Close()

            self.assertIsNone(test_engine._merge_task)
            self.assertIsNone(test_engine._task_merge_helper)
            self.assertFalse(test_engine._task_manager.HasPendingTasks())

            self.assertFalse(os.path.exists(task_storage_path))

            merge_task_storage_path = test_engine._GetMergeTaskStorageFilePath(
                definitions.STORAGE_FORMAT_SQLITE, task
            )
            self.assertFalse(os.path.exists(merge_task_storage_path))

            # Stopping the task storage without abort fails if a task storage file
            # was left behind.
            test_engine._StopTaskStorage(
                definitions.STORAGE_FORMAT_SQLITE, session.identifier
            )

    def testInternalMergeTaskStorageWithEmptyTaskStorage(self):
        """Tests the _MergeTaskStorage function with an empty task storage."""
        self._MergeTaskStorageWithInvalidTaskStorage(b"")

    def testInternalMergeTaskStorageWithNonSQLiteTaskStorage(self):
        """Tests the _MergeTaskStorage function with a non-SQLite task storage."""
        self._MergeTaskStorageWithInvalidTaskStorage(
            b"This is not a SQLite database file.\n" * 4
        )

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
