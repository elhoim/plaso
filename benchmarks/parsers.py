#!/usr/bin/env python3
"""Benchmarks for the parsers.

The benchmarks require pytest-benchmark and are not part of the unit tests.
"""

from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.path import factory as path_spec_factory
from dfvfs.resolver import resolver as path_spec_resolver

from plaso import parsers  # pylint: disable=unused-import
from plaso.containers import events
from plaso.parsers import interface
from plaso.parsers import manager
from plaso.parsers import mediator as parsers_mediator
from plaso.storage.fake import writer as fake_writer

from tests import test_lib as shared_test_lib


def _GetParser(parser_filter_expression):
    """Retrieves a parser.

    Args:
      parser_filter_expression (str): parser filter expression of the parser
          and plugins to use.

    Returns:
      BaseParser: parser.
    """
    parser_objects = manager.ParsersManager.GetParserObjects(
        parser_filter_expression=parser_filter_expression
    )
    parser_name = parser_filter_expression.split("/", maxsplit=1)[0]
    return parser_objects[parser_name]


def _ParseFile(parser, path_segments):
    """Parses a file in the test data directory.

    The file is opened and parsed with a new parser mediator and storage writer
    every time, to match how a file is processed during extraction.

    Args:
      parser (BaseParser): parser.
      path_segments (list[str]): path segments inside the test data directory.

    Returns:
      int: number of event data produced by the parser.
    """
    storage_writer = fake_writer.FakeStorageWriter()
    storage_writer.Open()

    parser_mediator = parsers_mediator.ParserMediator()
    parser_mediator.SetStorageWriter(storage_writer)

    test_file_path = shared_test_lib.GetTestFilePath(path_segments)
    path_spec = path_spec_factory.Factory.NewPathSpec(
        dfvfs_definitions.TYPE_INDICATOR_OS, location=test_file_path
    )
    file_entry = path_spec_resolver.Resolver.OpenFileEntry(path_spec)
    parser_mediator.SetFileEntry(file_entry)

    event_data_stream = events.EventDataStream()
    event_data_stream.path_spec = file_entry.path_spec
    parser_mediator.ProduceEventDataStream(event_data_stream)

    if isinstance(parser, interface.FileEntryParser):
        parser.Parse(parser_mediator)
    else:
        file_object = file_entry.GetFileObject()
        parser.Parse(parser_mediator, file_object)

    number_of_event_data = storage_writer.GetNumberOfAttributeContainers("event_data")

    storage_writer.Close()

    return number_of_event_data


def BenchmarkSQLiteParserWithChrome8HistoryPlugin(benchmark):
    """Benchmarks the SQLite parser with the Chrome 8 history plugin."""
    parser = _GetParser("sqlite/chrome_8_history")
    number_of_event_data = benchmark(_ParseFile, parser, ["chrome", "History"])
    assert number_of_event_data == 71


def BenchmarkTextParserWithTraditionalSyslogPlugin(benchmark):
    """Benchmarks the text parser with the traditional syslog plugin."""
    parser = _GetParser("text/syslog_traditional")
    number_of_event_data = benchmark(_ParseFile, parser, ["syslog", "syslog"])
    assert number_of_event_data == 16


def BenchmarkWinEvtxParser(benchmark):
    """Benchmarks the Windows XML EventLog (EVTX) parser."""
    parser = _GetParser("winevtx")
    number_of_event_data = benchmark(_ParseFile, parser, ["evtx", "System2.evtx"])
    assert number_of_event_data == 194
