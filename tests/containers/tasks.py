#!/usr/bin/env python3
"""Tests for the tasks attribute containers."""

import unittest
import uuid

from plaso.containers import tasks

from tests import test_lib as shared_test_lib


class TaskTest(shared_test_lib.BaseTestCase):
    """Tests for the task attribute container."""

    # TODO: replace by GetAttributeNames test
    def testCopyToDict(self):
        """Tests the CopyToDict function."""
        session_identifier = f"{uuid.uuid4().hex:s}"
        task = tasks.Task(session_identifier=session_identifier)

        self.assertIsNotNone(task.identifier)
        self.assertIsNotNone(task.start_time)
        self.assertIsNone(task.completion_time)

        expected_dict = {
            "aborted": False,
            "has_retry": False,
            "identifier": task.identifier,
            "number_of_retries": 0,
            "session_identifier": task.session_identifier,
            "start_time": task.start_time,
        }

        test_dict = task.CopyToDict()

        self.assertEqual(test_dict, expected_dict)

    def testCreateRetryTask(self):
        """Tests the CreateRetryTask function."""
        session_identifier = f"{uuid.uuid4().hex:s}"
        task = tasks.Task(session_identifier=session_identifier)
        task.path_spec = "test_path_spec"

        retry_task = task.CreateRetryTask()
        self.assertNotEqual(retry_task.identifier, task.identifier)
        self.assertEqual(retry_task.number_of_retries, task.number_of_retries + 1)
        self.assertEqual(retry_task.path_spec, task.path_spec)
        self.assertIsNone(retry_task.path_specs)

        task.path_specs = ["test_path_spec", "test_path_spec2"]

        retry_task = task.CreateRetryTask()
        self.assertEqual(retry_task.path_specs, task.path_specs)

    def testCreateRetryTasks(self):
        """Tests the CreateRetryTasks function."""
        session_identifier = f"{uuid.uuid4().hex:s}"
        task = tasks.Task(session_identifier=session_identifier)
        task.path_spec = "test_path_spec"

        retry_tasks = task.CreateRetryTasks()
        self.assertEqual(len(retry_tasks), 1)
        self.assertEqual(retry_tasks[0].path_spec, "test_path_spec")
        self.assertIsNone(retry_tasks[0].path_specs)

        task.path_specs = ["test_path_spec", "test_path_spec2"]

        retry_tasks = task.CreateRetryTasks()
        self.assertEqual(len(retry_tasks), 2)

        retry_task_identifiers = set()
        for retry_task, path_spec in zip(retry_tasks, task.path_specs):
            self.assertNotEqual(retry_task.identifier, task.identifier)
            self.assertEqual(retry_task.number_of_retries, task.number_of_retries + 1)
            self.assertEqual(retry_task.path_spec, path_spec)
            self.assertIsNone(retry_task.path_specs)
            retry_task_identifiers.add(retry_task.identifier)

        self.assertEqual(len(retry_task_identifiers), 2)

    def testGetPathSpecs(self):
        """Tests the GetPathSpecs function."""
        session_identifier = f"{uuid.uuid4().hex:s}"
        task = tasks.Task(session_identifier=session_identifier)
        task.path_spec = "test_path_spec"

        self.assertEqual(task.GetPathSpecs(), ["test_path_spec"])

        task.path_specs = ["test_path_spec", "test_path_spec2"]

        self.assertEqual(task.GetPathSpecs(), ["test_path_spec", "test_path_spec2"])

    def testUpdateProcessingTime(self):
        """Tests the UpdateProcessingTime function."""
        session_identifier = f"{uuid.uuid4().hex:s}"
        task = tasks.Task(session_identifier=session_identifier)

        self.assertIsNone(task.last_processing_time)

        task.UpdateProcessingTime()
        self.assertIsNotNone(task.last_processing_time)


if __name__ == "__main__":
    unittest.main()
