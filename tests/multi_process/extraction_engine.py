#!/usr/bin/env python3
"""Tests the multi-process processing engine."""

import collections
import multiprocessing
import os
import time
import unittest

from acstore.containers import interface as containers_interface
from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.path import factory as path_spec_factory

from plaso.containers import artifacts
from plaso.containers import events
from plaso.containers import sessions
from plaso.lib import definitions
from plaso.engine import configurations
from plaso.multi_process import extraction_engine
from plaso.multi_process import merge_helpers
from plaso.storage.fake import writer as fake_writer
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

    def testInternalMergeAttributeContainerWithMissingReference(self):
        """Tests the _MergeAttributeContainer function with a missing reference."""
        # pylint: disable=protected-access

        test_engine = extraction_engine.ExtractionMultiProcessEngine()

        task_storage_writer = fake_writer.FakeStorageWriter()
        task_storage_writer.Open()

        merge_helper = merge_helpers.ExtractionTaskMergeHelper(
            task_storage_writer, "task"
        )

        storage_writer = fake_writer.FakeStorageWriter()
        storage_writer.Open()

        try:
            event_data = events.EventData()
            event_data.SetIdentifier(
                containers_interface.AttributeContainerIdentifier(
                    name="event_data", sequence_number=1
                )
            )
            event_data.SetEventDataStreamIdentifier(
                containers_interface.AttributeContainerIdentifier(
                    name="event_data_stream", sequence_number=1
                )
            )
            test_engine._MergeAttributeContainer(
                storage_writer, merge_helper, event_data
            )

            event_definition = artifacts.WindowsWevtTemplateEvent()
            event_definition.SetIdentifier(
                containers_interface.AttributeContainerIdentifier(
                    name="windows_wevt_template_event", sequence_number=1
                )
            )
            event_definition.SetMessageFileIdentifier(
                containers_interface.AttributeContainerIdentifier(
                    name="windows_eventlog_message_file", sequence_number=1
                )
            )
            test_engine._MergeAttributeContainer(
                storage_writer, merge_helper, event_definition
            )

            number_of_event_data = storage_writer.GetNumberOfAttributeContainers(
                "event_data"
            )
            number_of_event_definitions = storage_writer.GetNumberOfAttributeContainers(
                "windows_wevt_template_event"
            )
            extraction_warnings = list(
                storage_writer.GetAttributeContainers("extraction_warning")
            )

        finally:
            storage_writer.Close()
            task_storage_writer.Close()

        self.assertEqual(number_of_event_data, 0)
        self.assertEqual(number_of_event_definitions, 0)
        self.assertEqual(len(extraction_warnings), 2)

        expected_message = (
            "Unable to merge event_data attribute container: event_data.1 since "
            "corresponding event data stream: event_data_stream.1 could not be found."
        )
        self.assertEqual(extraction_warnings[0].message, expected_message)

        expected_message = (
            "Unable to merge WEVT_TEMPLATE event definition attribute container: "
            "windows_wevt_template_event.1 since corresponding Windows EventLog "
            "message file: windows_eventlog_message_file.1 could not be found."
        )
        self.assertEqual(extraction_warnings[1].message, expected_message)

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
