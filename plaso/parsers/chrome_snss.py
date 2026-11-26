"""Parser for Google Chrome or Chromium session (SNSS) files."""

import os

from dfdatetime import webkit_time as dfdatetime_webkit_time

from dtfabric.runtime import data_maps as dtfabric_data_maps

from plaso.containers import events
from plaso.lib import dtfabric_helper
from plaso.lib import errors
from plaso.lib import specification
from plaso.parsers import interface
from plaso.parsers import manager


class ChromeSessionNavigationEventData(events.EventData):
    """Chrome session navigation event data.

    Attributes:
      http_status_code (int): HTTP status code of the navigation.
      last_visited_time (dfdatetime.DateTimeValues): date and time the navigation
          was committed.
      navigation_index (int): index of the navigation in the navigation history of
          the tab.
      page_transition_type (int): core type of the transition between pages.
      referrer_url (str): URL of the referrer.
      tab_identifier (int): identifier of the tab.
      title (str): title of the page.
      url (str): URL of the page.
      window_identifier (int): identifier of the window that contains the tab.
    """

    DATA_TYPE = "chrome:session:navigation"

    def __init__(self):
        """Initializes event data."""
        super().__init__(data_type=self.DATA_TYPE)
        self.http_status_code = None
        self.last_visited_time = None
        self.navigation_index = None
        self.page_transition_type = None
        self.referrer_url = None
        self.tab_identifier = None
        self.title = None
        self.url = None
        self.window_identifier = None


class ChromeSessionTabClosedEventData(events.EventData):
    """Chrome session tab closed event data.

    Attributes:
      close_time (dfdatetime.DateTimeValues): date and time the tab was closed.
      tab_identifier (int): identifier of the tab.
    """

    DATA_TYPE = "chrome:session:tab_closed"

    def __init__(self):
        """Initializes event data."""
        super().__init__(data_type=self.DATA_TYPE)
        self.close_time = None
        self.tab_identifier = None


class ChromeSessionTabLastActiveEventData(events.EventData):
    """Chrome session tab last active event data.

    Attributes:
      last_active_time (dfdatetime.DateTimeValues): date and time the tab was last
          active.
      tab_identifier (int): identifier of the tab.
    """

    DATA_TYPE = "chrome:session:tab_last_active"

    def __init__(self):
        """Initializes event data."""
        super().__init__(data_type=self.DATA_TYPE)
        self.last_active_time = None
        self.tab_identifier = None


class ChromeSessionWindowClosedEventData(events.EventData):
    """Chrome session window closed event data.

    Attributes:
      close_time (dfdatetime.DateTimeValues): date and time the window was closed.
      window_identifier (int): identifier of the window.
    """

    DATA_TYPE = "chrome:session:window_closed"

    def __init__(self):
        """Initializes event data."""
        super().__init__(data_type=self.DATA_TYPE)
        self.close_time = None
        self.window_identifier = None


class ChromeSNSSParser(interface.FileObjectParser, dtfabric_helper.DtFabricHelper):
    """Parser for Google Chrome or Chromium session (SNSS) files.

    SNSS files are used by the session service, which stores the open windows and tabs,
    in files named "Session_<timestamp>", "Current Session" or "Last Session", and by
    the tab restore service, which stores the recently closed windows and tabs, in files
    named "Tabs_<timestamp>", "Current Tabs" or "Last Tabs". Both services use their own
    set of command identifiers.
    """

    NAME = "chrome_snss"
    DATA_FORMAT = "Google Chrome or Chromium session (SNSS) file"

    _DEFINITION_FILE = os.path.join(os.path.dirname(__file__), "chrome_snss.yaml")

    # Format version 1 was used before 2021 and format version 3 is used since.
    # Format versions 2 and 4 contain encrypted commands and are not supported.
    _SUPPORTED_FORMAT_VERSIONS = frozenset([1, 3])

    # WebKit timestamp of 2008-09-02 00:00:00, the release date of Chrome 0.2.
    _MINIMUM_WEBKIT_TIMESTAMP = 12864787200000000

    _PAGE_TRANSITION_CORE_MASK = 0xFF

    # Command identifiers used by the session service.
    _SESSION_COMMAND_SET_TAB_WINDOW = 0
    _SESSION_COMMAND_UPDATE_TAB_NAVIGATION = 6
    _SESSION_COMMAND_TAB_CLOSED = 16
    _SESSION_COMMAND_WINDOW_CLOSED = 17
    _SESSION_COMMAND_LAST_ACTIVE_TIME = 21

    # Command identifiers used by the tab restore service.
    _TAB_RESTORE_COMMAND_UPDATE_TAB_NAVIGATION = 1
    _TAB_RESTORE_COMMAND_SELECTED_NAVIGATION_IN_TAB = 4
    _TAB_RESTORE_COMMAND_WINDOW = 9

    _SESSION_COMMANDS = frozenset(
        [
            _SESSION_COMMAND_LAST_ACTIVE_TIME,
            _SESSION_COMMAND_SET_TAB_WINDOW,
            _SESSION_COMMAND_TAB_CLOSED,
            _SESSION_COMMAND_UPDATE_TAB_NAVIGATION,
            _SESSION_COMMAND_WINDOW_CLOSED,
        ]
    )

    _TAB_RESTORE_COMMANDS = frozenset(
        [
            _TAB_RESTORE_COMMAND_SELECTED_NAVIGATION_IN_TAB,
            _TAB_RESTORE_COMMAND_UPDATE_TAB_NAVIGATION,
            _TAB_RESTORE_COMMAND_WINDOW,
        ]
    )

    _TAB_RESTORE_FILENAMES = frozenset(["Current Tabs", "Last Tabs"])

    def __init__(self):
        """Initializes a Chrome SNSS file parser."""
        super().__init__()
        self._closed_payload_data_type_map = self._GetDataTypeMap(
            "chrome_snss_closed_payload"
        )
        self._command_header_data_type_map = self._GetDataTypeMap(
            "chrome_snss_command_header"
        )
        self._last_active_time_payload_data_type_map = self._GetDataTypeMap(
            "chrome_snss_last_active_time_payload"
        )
        self._navigation_pickle_data_type_map = self._GetDataTypeMap(
            "chrome_snss_navigation_pickle"
        )
        self._navigation_pickle_extension_data_type_map = self._GetDataTypeMap(
            "chrome_snss_navigation_pickle_extension"
        )
        self._selected_navigation_in_tab_payload_data_type_map = self._GetDataTypeMap(
            "chrome_snss_selected_navigation_in_tab_payload"
        )
        self._set_tab_window_payload_data_type_map = self._GetDataTypeMap(
            "chrome_snss_set_tab_window_payload"
        )
        self._window_pickle_data_type_map = self._GetDataTypeMap(
            "chrome_snss_window_pickle"
        )

    def _GetDateTimeValue(self, timestamp):
        """Retrieves a date and time value.

        Args:
          timestamp (int): WebKit timestamp.

        Returns:
          dfdatetime.WebKitTime: date and time value or None if the timestamp is
              not set.
        """
        if not timestamp:
            return None

        return dfdatetime_webkit_time.WebKitTime(timestamp=timestamp)

    def _ParseClosedCommand(
        self, parser_mediator, command_identifier, file_offset, payload_data
    ):
        """Parses a session service tab or window closed command.

        Args:
          parser_mediator (ParserMediator): mediates interactions between parsers
              and other components, such as storage and dfVFS.
          command_identifier (int): command identifier.
          file_offset (int): offset of the command payload relative to the start
              of the file.
          payload_data (bytes): command payload data.

        Raises:
          ParseError: if the command payload cannot be parsed.
        """
        payload = self._ReadStructureFromByteStream(
            payload_data, file_offset, self._closed_payload_data_type_map
        )

        if command_identifier == self._SESSION_COMMAND_TAB_CLOSED:
            event_data = ChromeSessionTabClosedEventData()
            event_data.tab_identifier = payload.identifier
        else:
            event_data = ChromeSessionWindowClosedEventData()
            event_data.window_identifier = payload.identifier

        event_data.close_time = self._GetDateTimeValue(payload.close_time)

        parser_mediator.ProduceEventData(event_data)

    def _ParseCommand(
        self,
        parser_mediator,
        command_identifier,
        file_offset,
        payload_data,
        is_tab_restore,
        window_per_tab,
    ):
        """Parses a command.

        Args:
          parser_mediator (ParserMediator): mediates interactions between parsers
              and other components, such as storage and dfVFS.
          command_identifier (int): command identifier.
          file_offset (int): offset of the command payload relative to the start
              of the file.
          payload_data (bytes): command payload data.
          is_tab_restore (bool): True if the command was stored by the tab restore
              service, False if stored by the session service.
          window_per_tab (dict[int, int]): window identifier per tab identifier.

        Raises:
          ParseError: if the command payload cannot be parsed.
        """
        if is_tab_restore:
            if command_identifier == self._TAB_RESTORE_COMMAND_UPDATE_TAB_NAVIGATION:
                self._ParseUpdateTabNavigationCommand(
                    parser_mediator, file_offset, payload_data, window_per_tab
                )

            elif (
                command_identifier
                == self._TAB_RESTORE_COMMAND_SELECTED_NAVIGATION_IN_TAB
            ):
                self._ParseSelectedNavigationInTabCommand(
                    parser_mediator, file_offset, payload_data
                )

            elif command_identifier == self._TAB_RESTORE_COMMAND_WINDOW:
                self._ParseWindowCommand(parser_mediator, file_offset, payload_data)

        elif command_identifier == self._SESSION_COMMAND_UPDATE_TAB_NAVIGATION:
            self._ParseUpdateTabNavigationCommand(
                parser_mediator, file_offset, payload_data, window_per_tab
            )

        elif command_identifier == self._SESSION_COMMAND_SET_TAB_WINDOW:
            payload = self._ReadStructureFromByteStream(
                payload_data, file_offset, self._set_tab_window_payload_data_type_map
            )
            window_per_tab[payload.tab_identifier] = payload.window_identifier

        elif command_identifier in (
            self._SESSION_COMMAND_TAB_CLOSED,
            self._SESSION_COMMAND_WINDOW_CLOSED,
        ):
            self._ParseClosedCommand(
                parser_mediator, command_identifier, file_offset, payload_data
            )

        elif command_identifier == self._SESSION_COMMAND_LAST_ACTIVE_TIME:
            self._ParseLastActiveTimeCommand(parser_mediator, file_offset, payload_data)

    def _ParseLastActiveTimeCommand(self, parser_mediator, file_offset, payload_data):
        """Parses a session service last active time command.

        Args:
          parser_mediator (ParserMediator): mediates interactions between parsers
              and other components, such as storage and dfVFS.
          file_offset (int): offset of the command payload relative to the start
              of the file.
          payload_data (bytes): command payload data.

        Raises:
          ParseError: if the command payload cannot be parsed.
        """
        payload = self._ReadStructureFromByteStream(
            payload_data, file_offset, self._last_active_time_payload_data_type_map
        )

        # Before Chrome 130 the last active time was stored as a monotonic time
        # (base::TimeTicks), which cannot be converted into a date and time value.
        if payload.last_active_time < self._MINIMUM_WEBKIT_TIMESTAMP:
            return

        event_data = ChromeSessionTabLastActiveEventData()
        event_data.last_active_time = self._GetDateTimeValue(payload.last_active_time)
        event_data.tab_identifier = payload.tab_identifier

        parser_mediator.ProduceEventData(event_data)

    def _ParseSelectedNavigationInTabCommand(
        self, parser_mediator, file_offset, payload_data
    ):
        """Parses a tab restore service selected navigation in tab command.

        Args:
          parser_mediator (ParserMediator): mediates interactions between parsers
              and other components, such as storage and dfVFS.
          file_offset (int): offset of the command payload relative to the start
              of the file.
          payload_data (bytes): command payload data.

        Raises:
          ParseError: if the command payload cannot be parsed.
        """
        payload = self._ReadStructureFromByteStream(
            payload_data,
            file_offset,
            self._selected_navigation_in_tab_payload_data_type_map,
        )

        event_data = ChromeSessionTabClosedEventData()
        event_data.close_time = self._GetDateTimeValue(payload.timestamp)
        event_data.tab_identifier = payload.tab_identifier

        parser_mediator.ProduceEventData(event_data)

    def _ParseUpdateTabNavigationCommand(
        self, parser_mediator, file_offset, payload_data, window_per_tab
    ):
        """Parses an update tab navigation command.

        Args:
          parser_mediator (ParserMediator): mediates interactions between parsers
              and other components, such as storage and dfVFS.
          file_offset (int): offset of the command payload relative to the start
              of the file.
          payload_data (bytes): command payload data.
          window_per_tab (dict[int, int]): window identifier per tab identifier.

        Raises:
          ParseError: if the command payload cannot be parsed.
        """
        context = dtfabric_data_maps.DataTypeMapContext()

        navigation = self._ReadStructureFromByteStream(
            payload_data,
            file_offset,
            self._navigation_pickle_data_type_map,
            context=context,
        )

        event_data = ChromeSessionNavigationEventData()
        event_data.navigation_index = navigation.navigation_index
        event_data.page_transition_type = (
            navigation.page_transition_type & self._PAGE_TRANSITION_CORE_MASK
        )
        event_data.tab_identifier = navigation.tab_identifier
        event_data.title = navigation.title or None
        event_data.url = navigation.url or None
        event_data.window_identifier = window_per_tab.get(navigation.tab_identifier)

        extension_offset = context.byte_size
        extension_data = payload_data[extension_offset:]

        # The fields in the extension were added in later versions of Chrome and
        # are not present in navigations written by older versions.
        extension = None
        if extension_data:
            try:
                extension = self._ReadStructureFromByteStream(
                    extension_data,
                    file_offset + extension_offset,
                    self._navigation_pickle_extension_data_type_map,
                )
            except errors.ParseError:
                extension = None

        if extension:
            event_data.http_status_code = extension.http_status_code
            event_data.last_visited_time = self._GetDateTimeValue(extension.timestamp)
            event_data.referrer_url = extension.referrer_url or None

        parser_mediator.ProduceEventData(event_data)

    def _ParseWindowCommand(self, parser_mediator, file_offset, payload_data):
        """Parses a tab restore service window command.

        Args:
          parser_mediator (ParserMediator): mediates interactions between parsers
              and other components, such as storage and dfVFS.
          file_offset (int): offset of the command payload relative to the start
              of the file.
          payload_data (bytes): command payload data.

        Raises:
          ParseError: if the command payload cannot be parsed.
        """
        window = self._ReadStructureFromByteStream(
            payload_data, file_offset, self._window_pickle_data_type_map
        )

        event_data = ChromeSessionWindowClosedEventData()
        event_data.close_time = self._GetDateTimeValue(window.timestamp)
        event_data.window_identifier = window.window_identifier

        parser_mediator.ProduceEventData(event_data)

    @classmethod
    def GetFormatSpecification(cls):
        """Retrieves the format specification.

        Returns:
          FormatSpecification: format specification.
        """
        format_specification = specification.FormatSpecification(cls.NAME)
        format_specification.AddNewSignature(b"SNSS", offset=0)
        return format_specification

    def ParseFileObject(self, parser_mediator, file_object):
        """Parses a Chrome SNSS file-like object.

        Args:
          parser_mediator (ParserMediator): mediates interactions between parsers
              and other components, such as storage and dfVFS.
          file_object (dfvfs.FileIO): a file-like object to parse.

        Raises:
          WrongParser: when the file cannot be parsed.
        """
        file_header_map = self._GetDataTypeMap("chrome_snss_file_header")

        try:
            file_header, file_offset = self._ReadStructureFromFileObject(
                file_object, 0, file_header_map
            )
        except (ValueError, errors.ParseError) as exception:
            raise errors.WrongParser(
                f"Unable to parse file header with error: {exception!s}"
            )

        if file_header.format_version not in self._SUPPORTED_FORMAT_VERSIONS:
            raise errors.WrongParser(
                f"Unsupported format version: {file_header.format_version:d}"
            )

        filename = parser_mediator.GetFilename() or ""
        is_tab_restore = (
            filename.startswith("Tabs_") or filename in self._TAB_RESTORE_FILENAMES
        )

        if is_tab_restore:
            supported_command_identifiers = self._TAB_RESTORE_COMMANDS
        else:
            supported_command_identifiers = self._SESSION_COMMANDS

        command_header_size = self._command_header_data_type_map.GetSizeHint()
        file_size = file_object.get_size()
        window_per_tab = {}

        while file_offset < file_size:
            if parser_mediator.abort:
                break

            try:
                command_header, _ = self._ReadStructureFromFileObject(
                    file_object, file_offset, self._command_header_data_type_map
                )
            except (ValueError, errors.ParseError) as exception:
                parser_mediator.ProduceWarning(
                    f"unable to parse command header at offset: 0x{file_offset:08x} "
                    f"with error: {exception!s}"
                )
                break

            # The command size includes the 1 byte command identifier.
            if command_header.command_size == 0:
                parser_mediator.ProduceWarning(
                    f"invalid command size: 0 at offset: 0x{file_offset:08x}"
                )
                break

            payload_offset = file_offset + command_header_size
            payload_size = command_header.command_size - 1

            if payload_offset + payload_size > file_size:
                parser_mediator.ProduceWarning(
                    f"truncated command at offset: 0x{file_offset:08x}"
                )
                break

            command_identifier = command_header.command_identifier

            if command_identifier in supported_command_identifiers:
                try:
                    payload_data = self._ReadData(
                        file_object, payload_offset, payload_size
                    )
                    self._ParseCommand(
                        parser_mediator,
                        command_identifier,
                        payload_offset,
                        payload_data,
                        is_tab_restore,
                        window_per_tab,
                    )

                except (ValueError, errors.ParseError) as exception:
                    parser_mediator.ProduceWarning(
                        f"unable to parse command: {command_identifier:d} at "
                        f"offset: 0x{file_offset:08x} with error: {exception!s}"
                    )

            file_offset = payload_offset + payload_size


manager.ParsersManager.RegisterParser(ChromeSNSSParser)
