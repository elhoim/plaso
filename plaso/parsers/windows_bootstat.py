"""Parser for Windows boot status data (bootstat.dat) files."""

import os

from dfdatetime import time_elements as dfdatetime_time_elements

from plaso.containers import events
from plaso.lib import dtfabric_helper
from plaso.lib import errors
from plaso.parsers import interface
from plaso.parsers import manager


class WindowsBootStatusDataBootEventData(events.EventData):
    """Windows boot status data boot event data.

    Attributes:
      application_identifier (str): identifier (GUID) of the boot application.
      application_type (int): type of the boot application, where 2 represents
          the Windows boot manager and 3 the Windows boot loader.
      boot_time (dfdatetime.DateTimeValues): date and time the boot application
          was initialized, in local time.
      last_boot_identifier (int): last boot identifier, which corresponds to
          the LastBootId value of Microsoft-Windows-Kernel-Boot event 20, or None
          if not available.
      level (int): event level.
    """

    DATA_TYPE = "windows:bootstat:boot"

    def __init__(self):
        """Initializes event data."""
        super().__init__(data_type=self.DATA_TYPE)
        self.application_identifier = None
        self.application_type = None
        self.boot_time = None
        self.last_boot_identifier = None
        self.level = None


class WindowsBootStatusDataParser(
    interface.FileObjectParser, dtfabric_helper.DtFabricHelper
):
    """Parser for Windows boot status data (bootstat.dat) files.

    The boot status data file contains a circular boot log, that is preceded by a boot
    status data block of 2048 bytes in the bootstat.dat file in the Windows directory.
    The bootstat.dat file in the EFI system partition only contains the boot log.
    """

    NAME = "windows_bootstat"
    DATA_FORMAT = "Windows boot status data (bootstat.dat) file"

    FILTERS = frozenset([interface.FileNameFileEntryFilter("bootstat.dat")])

    _DEFINITION_FILE = os.path.join(os.path.dirname(__file__), "windows_bootstat.yaml")

    _APPLICATION_TYPE_WINDOWS_BOOT_LOADER = 3

    _BOOT_LOG_HEADER_OFFSETS = (0, 2048)

    _EVENT_CODE_INITIALIZED = 1

    _SUPPORTED_FORMAT_VERSIONS = frozenset([4])

    def __init__(self):
        """Initializes a Windows boot status data (bootstat.dat) parser."""
        super().__init__()
        self._boot_log_entry_header_data_size = self._GetDataTypeMap(
            "bootstat_boot_log_entry_header"
        ).GetSizeHint()
        self._boot_log_header_data_size = self._GetDataTypeMap(
            "bootstat_boot_log_header"
        ).GetSizeHint()

    def _CheckBootLogHeader(self, boot_log_header, boot_log_offset, file_size):
        """Checks if a boot log header is valid.

        Args:
          boot_log_header (bootstat_boot_log_header): boot log header.
          boot_log_offset (int): offset of the boot log relative to the start of
              the file.
          file_size (int): size of the file.

        Returns:
          bool: True if the boot log header is valid.
        """
        if boot_log_header.format_version not in self._SUPPORTED_FORMAT_VERSIONS:
            return False

        if boot_log_offset + boot_log_header.boot_log_size != file_size:
            return False

        boot_log_start_offset = boot_log_header.boot_log_start_offset
        boot_log_size = boot_log_header.boot_log_size

        if (
            boot_log_start_offset < self._boot_log_header_data_size
            or boot_log_start_offset >= boot_log_size
        ):
            return False

        for entry_offset in (
            boot_log_header.first_boot_log_entry_offset,
            boot_log_header.next_boot_log_entry_offset,
        ):
            if entry_offset < boot_log_start_offset or entry_offset >= boot_log_size:
                return False

        return True

    def _ParseInitializedEvent(
        self, parser_mediator, file_object, file_offset, entry_header
    ):
        """Parses an initialized event boot log entry.

        Args:
          parser_mediator (ParserMediator): mediates interactions between parsers and
              other components, such as storage and dfVFS.
          file_object (dfvfs.FileIO): file-like object.
          file_offset (int): offset of the boot log entry relative to the start of
              the file.
          entry_header (bootstat_boot_log_entry_header): boot log entry header.
        """
        data_offset = file_offset + self._boot_log_entry_header_data_size
        data_size = entry_header.entry_size - self._boot_log_entry_header_data_size

        if entry_header.application_type == self._APPLICATION_TYPE_WINDOWS_BOOT_LOADER:
            data_type_map = self._GetDataTypeMap(
                "bootstat_boot_loader_initialized_event_data"
            )
        else:
            data_type_map = self._GetDataTypeMap("bootstat_time_fields")

        if data_size < data_type_map.GetSizeHint():
            parser_mediator.ProduceExtractionWarning(
                f"unsupported initialized event data size at offset: "
                f"0x{data_offset:08x}"
            )
            return

        try:
            event_values, _ = self._ReadStructureFromFileObject(
                file_object, data_offset, data_type_map
            )
        except (ValueError, errors.ParseError) as exception:
            parser_mediator.ProduceExtractionWarning(
                (
                    f"unable to parse initialized event data at offset: "
                    f"0x{data_offset:08x} with error: {exception!s}"
                )
            )
            return

        event_data = WindowsBootStatusDataBootEventData()
        event_data.application_identifier = str(entry_header.application_identifier)
        event_data.application_type = entry_header.application_type
        event_data.level = entry_header.level

        if entry_header.application_type == self._APPLICATION_TYPE_WINDOWS_BOOT_LOADER:
            event_data.last_boot_identifier = event_values.last_boot_identifier
            time_fields = event_values.time_fields
        else:
            time_fields = event_values

        time_elements_tuple = (
            time_fields.year,
            time_fields.month,
            time_fields.day_of_month,
            time_fields.hours,
            time_fields.minutes,
            time_fields.seconds,
        )

        try:
            event_data.boot_time = dfdatetime_time_elements.TimeElements(
                time_elements_tuple=time_elements_tuple
            )
            # The time fields contain a date and time in local time.
            event_data.boot_time.is_local_time = True

        except ValueError:
            parser_mediator.ProduceExtractionWarning(
                f"invalid boot date and time value: {time_elements_tuple!s}"
            )

        parser_mediator.ProduceEventData(event_data)

    def _ReadBootLogHeader(self, file_object, file_size):
        """Reads a boot log header.

        Args:
          file_object (dfvfs.FileIO): file-like object.
          file_size (int): size of the file.

        Returns:
          tuple[bootstat_boot_log_header, int]: boot log header and offset of the
              boot log relative to the start of the file.

        Raises:
          WrongParser: when the file does not contain a supported boot log header.
        """
        data_type_map = self._GetDataTypeMap("bootstat_boot_log_header")

        for boot_log_offset in self._BOOT_LOG_HEADER_OFFSETS:
            if boot_log_offset + self._boot_log_header_data_size > file_size:
                continue

            try:
                boot_log_header, _ = self._ReadStructureFromFileObject(
                    file_object, boot_log_offset, data_type_map
                )
            except (ValueError, errors.ParseError) as exception:
                raise errors.WrongParser(
                    f"Unable to parse boot log header with error: {exception!s}"
                )

            if self._CheckBootLogHeader(boot_log_header, boot_log_offset, file_size):
                return boot_log_header, boot_log_offset

        raise errors.WrongParser("Unsupported boot log header")

    def ParseFileObject(self, parser_mediator, file_object):
        """Parses a Windows boot status data (bootstat.dat) file-like object.

        Args:
          parser_mediator (ParserMediator): mediates interactions between parsers and
              other components, such as storage and dfVFS.
          file_object (dfvfs.FileIO): file-like object.

        Raises:
          WrongParser: when the file cannot be parsed.
        """
        file_size = file_object.get_size()

        boot_log_header, boot_log_offset = self._ReadBootLogHeader(
            file_object, file_size
        )

        boot_log_end_offset = boot_log_header.boot_log_size
        boot_log_start_offset = boot_log_header.boot_log_start_offset
        next_entry_offset = boot_log_header.next_boot_log_entry_offset

        entry_offset = boot_log_header.first_boot_log_entry_offset

        # When the first entry is stored after the next entry the boot log has
        # wrapped around and the oldest entries are stored at the end of the log.
        is_wrapped = entry_offset > next_entry_offset

        entry_header_map = self._GetDataTypeMap("bootstat_boot_log_entry_header")

        while is_wrapped or entry_offset < next_entry_offset:
            if parser_mediator.abort:
                break

            file_offset = boot_log_offset + entry_offset

            entry_header = None
            if (
                entry_offset + self._boot_log_entry_header_data_size
                <= boot_log_end_offset
            ):
                try:
                    entry_header, _ = self._ReadStructureFromFileObject(
                        file_object, file_offset, entry_header_map
                    )
                except (ValueError, errors.ParseError) as exception:
                    parser_mediator.ProduceExtractionWarning(
                        (
                            f"unable to parse boot log entry header at offset: "
                            f"0x{file_offset:08x} with error: {exception!s}"
                        )
                    )
                    break

            # The remainder of a wrapped boot log, that is too small to contain
            # an entry or that contains an empty entry, is unused.
            if is_wrapped and (not entry_header or not entry_header.entry_size):
                entry_offset = boot_log_start_offset
                is_wrapped = False
                continue

            if (
                not entry_header
                or entry_header.entry_size < self._boot_log_entry_header_data_size
                or entry_offset + entry_header.entry_size > boot_log_end_offset
            ):
                parser_mediator.ProduceExtractionWarning(
                    f"invalid boot log entry at offset: 0x{file_offset:08x}"
                )
                break

            if entry_header.event_code == self._EVENT_CODE_INITIALIZED:
                self._ParseInitializedEvent(
                    parser_mediator, file_object, file_offset, entry_header
                )

            entry_offset += entry_header.entry_size


manager.ParsersManager.RegisterParser(WindowsBootStatusDataParser)
