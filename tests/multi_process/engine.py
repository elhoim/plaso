#!/usr/bin/env python3
"""Tests the multi-process processing engine."""

import os
import unittest

from plaso.engine import process_info
from plaso.lib import definitions
from plaso.multi_process import extraction_engine
from plaso.multi_process import plaso_xmlrpc

from tests.multi_process import test_lib


class TestEngine(extraction_engine.ExtractionMultiProcessEngine):
    """Multi-process engine that does not start worker processes.

    Attributes:
      started_process_names (list[str]): names of the worker processes that
          were requested to be started.
    """

    def __init__(self):
        """Initializes a multi-process engine."""
        super().__init__(worker_memory_limit=0)
        self.started_process_names = []

    def _StartWorkerProcess(self, process_name):
        """Creates, starts, monitors and registers a worker process.

        Args:
          process_name (str): process name.

        Returns:
          TestProcess: stand-in for the worker process.
        """
        self.started_process_names.append(process_name)
        return test_lib.TestProcess(process_name, 0)


class MultiProcessEngineTest(test_lib.MultiProcessingTestCase):
    """Tests for the multi-process engine."""

    # pylint: disable=protected-access

    def _CreateTestEngine(self, alive=True):
        """Creates an engine with a registered and monitored worker process.

        The RPC client of the worker process connects to a port without a RPC
        server, therefore querying the process status via RPC fails.

        Args:
          alive (Optional[bool]): True if the worker process is alive.

        Returns:
          tuple[TestEngine, TestProcess]: engine and worker process.
        """
        pid = os.getpid()
        process = test_lib.TestProcess("Worker_00", pid, alive=alive)

        rpc_client = plaso_xmlrpc.XMLProcessStatusRPCClient()
        rpc_client.Open("localhost", process.rpc_port.value)

        test_engine = TestEngine()
        test_engine._processes_per_pid[pid] = process
        test_engine._process_information_per_pid[pid] = process_info.ProcessInfo(pid)
        test_engine._rpc_clients_per_pid[pid] = rpc_client

        return test_engine, process

    # TODO: add test for _AbortJoin
    # TODO: add test for _AbortKill
    # TODO: add test for _AbortTerminate

    def testCheckStatusWorkerProcessWithRPCError(self):
        """Tests _CheckStatusWorkerProcess with a RPC error."""
        test_engine, process = self._CreateTestEngine()

        test_engine._CheckStatusWorkerProcess(process.pid)

        worker_status = test_engine._processing_status.workers_status[0]
        self.assertEqual(worker_status.status, "RPC error")
        self.assertEqual(test_engine._rpc_errors_per_pid[process.pid], 1)
        self.assertFalse(process.terminated)
        self.assertEqual(test_engine.started_process_names, [])

    def testCheckStatusWorkerProcessWithMaximumRPCErrors(self):
        """Tests _CheckStatusWorkerProcess with too many RPC errors."""
        test_engine, process = self._CreateTestEngine()
        test_engine._rpc_errors_per_pid[process.pid] = test_engine._MAXIMUM_RPC_ERRORS

        test_engine._CheckStatusWorkerProcess(process.pid)

        worker_status = test_engine._processing_status.workers_status[0]
        self.assertEqual(worker_status.status, definitions.STATUS_INDICATOR_KILLED)
        self.assertTrue(process.terminated)
        self.assertEqual(test_engine.started_process_names, ["Worker_00"])

    def testCheckStatusWorkerProcessWithStoppedProcess(self):
        """Tests _CheckStatusWorkerProcess with a process that is not alive."""
        test_engine, process = self._CreateTestEngine(alive=False)

        test_engine._CheckStatusWorkerProcess(process.pid)

        worker_status = test_engine._processing_status.workers_status[0]
        self.assertEqual(worker_status.status, definitions.STATUS_INDICATOR_KILLED)
        self.assertEqual(test_engine.started_process_names, ["Worker_00"])

    # TODO: add test for _KillProcess
    # TODO: add test for _LogMemoryUsage
    # TODO: add test for _QueryProcessStatus
    # TODO: add test for _RaiseIfNotMonitored
    # TODO: add test for _RaiseIfNotRegistered
    # TODO: add test for _RegisterProcess
    # TODO: add test for _StartMonitoringProcess
    # TODO: add test for _StartStatusUpdateThread
    # TODO: add test for _StopMonitoringProcess
    # TODO: add test for _StopMonitoringProcesses
    # TODO: add test for _StopStatusUpdateThread
    # TODO: add test for _TerminateProcess


if __name__ == "__main__":
    unittest.main()
