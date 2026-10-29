#!/usr/bin/env python3
"""Tests for the analysis mediator."""

import unittest

from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.path import factory as path_spec_factory

from plaso.analysis import interface
from plaso.analysis import mediator
from plaso.containers import artifacts
from plaso.storage.fake import writer as fake_writer

from tests.analysis import test_lib


class TestAnalysisPlugin(interface.AnalysisPlugin):
    """Analysis plugin for testing."""

    NAME = "test_plugin"

    def __init__(self, generate_report=True):
        """Initializes an analysis plugin for testing.

        Args:
          generate_report (Optional[bool]): True if the plugin should generate
              an analysis report.
        """
        super().__init__()
        self._generate_report = generate_report

    def CompileReport(self, analysis_mediator):
        """Compiles a report of the analysis.

        Args:
          analysis_mediator (AnalysisMediator): mediates interactions between
              analysis plugins and other components, such as storage and dfVFS.

        Returns:
          AnalysisReport: report or None if no report was generated.
        """
        if not self._generate_report:
            return None

        return super().CompileReport(analysis_mediator)

    # pylint: disable=unused-argument
    def ExamineEvent(self, analysis_mediator, event, event_data, event_data_stream):
        """Analyzes an event.

        Args:
          analysis_mediator (AnalysisMediator): mediates interactions between
              analysis plugins and other components, such as storage and dfVFS.
          event (EventObject): event.
          event_data (EventData): event data.
          event_data_stream (EventDataStream): event data stream.
        """
        return


class AnalysisMediatorTest(test_lib.AnalysisPluginTestCase):
    """Tests for the analysis mediator."""

    def testGetDisplayNameForPathSpec(self):
        """Tests the GetDisplayNameForPathSpec function."""
        analysis_mediator = mediator.AnalysisMediator()

        test_path = self._GetTestFilePath(["syslog.gz"])
        os_path_spec = path_spec_factory.Factory.NewPathSpec(
            dfvfs_definitions.TYPE_INDICATOR_OS, location=test_path
        )

        display_name = analysis_mediator.GetDisplayNameForPathSpec(os_path_spec)
        self.assertEqual(display_name, f"OS:{test_path:s}")

    def testGetUsernameForPath(self):
        """Tests the GetUsernameForPath function."""
        test_user1 = artifacts.UserAccountArtifact(
            identifier="1000",
            path_separator="\\",
            user_directory="C:\\Users\\testuser1",
            username="testuser1",
        )

        analysis_mediator = mediator.AnalysisMediator(user_accounts=[test_user1])

        username = analysis_mediator.GetUsernameForPath(
            "C:\\Users\\testuser1\\Downloads"
        )
        self.assertEqual(username, "testuser1")

        username = analysis_mediator.GetUsernameForPath(
            "C:\\Users\\testuser2\\Downloads"
        )
        self.assertIsNone(username)

    def testProduceAnalysisReport(self):
        """Tests the ProduceAnalysisReport function."""
        storage_writer = fake_writer.FakeStorageWriter()
        storage_writer.Open()

        analysis_mediator = mediator.AnalysisMediator()
        analysis_mediator.SetStorageWriter(storage_writer)

        plugin = TestAnalysisPlugin()
        analysis_mediator.ProduceAnalysisReport(plugin)

        self.assertEqual(analysis_mediator.number_of_produced_analysis_reports, 1)

        number_of_reports = storage_writer.GetNumberOfAttributeContainers(
            "analysis_report"
        )
        self.assertEqual(number_of_reports, 1)

        number_of_warnings = storage_writer.GetNumberOfAttributeContainers(
            "analysis_warning"
        )
        self.assertEqual(number_of_warnings, 0)

        storage_writer.Close()

        # Test with a plugin that does not generate a report.
        storage_writer = fake_writer.FakeStorageWriter()
        storage_writer.Open()

        analysis_mediator = mediator.AnalysisMediator()
        analysis_mediator.SetStorageWriter(storage_writer)

        plugin = TestAnalysisPlugin(generate_report=False)
        analysis_mediator.ProduceAnalysisReport(plugin)

        self.assertEqual(analysis_mediator.number_of_produced_analysis_reports, 0)

        number_of_reports = storage_writer.GetNumberOfAttributeContainers(
            "analysis_report"
        )
        self.assertEqual(number_of_reports, 0)

        warnings = list(storage_writer.GetAttributeContainers("analysis_warning"))
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].message, "Unable to generate analysis report.")
        self.assertEqual(warnings[0].plugin_name, "test_plugin")

        storage_writer.Close()

    # TODO: add test for ProduceEventTag.

    def testSignalAbort(self):
        """Tests the SignalAbort function."""
        analysis_mediator = mediator.AnalysisMediator()

        analysis_mediator.SignalAbort()


if __name__ == "__main__":
    unittest.main()
