#!/usr/bin/env python3
"""Tests for the preprocess plugins manager."""

import unittest

from artifacts import reader as artifacts_reader
from artifacts import registry as artifacts_registry

from plaso.preprocessors import interface
from plaso.preprocessors import manager
from plaso.preprocessors import windows  # pylint: disable=unused-import

from tests import test_lib as shared_test_lib


class TestArtifactPreprocessorPlugin(interface.ArtifactPreprocessorPlugin):
    """Test artifact preprocessor plugin."""

    ARTIFACT_DEFINITION_NAME = "TestArtifactDefinition"

    # pylint: disable=unused-argument
    def ParseValueData(self, value_data):
        """Parses artifact value data for a preprocessing attribute.

        Args:
          value_data (object): artifact value data.
        """
        return


class TestKnowledgeBasePreprocessorPlugin(interface.KnowledgeBasePreprocessorPlugin):
    """Test knowledge base preprocessor plugin."""

    def __init__(self, dependencies):
        """Initializes a test knowledge base preprocessor plugin.

        Args:
          dependencies (list[str]): names of the preprocessor plugins that need to
              run before this plugin.
        """
        super().__init__()
        self.DEPENDENCIES = frozenset(dependencies)  # pylint: disable=invalid-name

    # pylint: disable=unused-argument
    def Collect(self, mediator):
        """Collects values from the knowledge base.

        Args:
          mediator (PreprocessMediator): mediates interactions between preprocess
              plugins and other components, such as storage.
        """
        return


class PreprocessPluginsManagerTest(shared_test_lib.BaseTestCase):
    """Tests for the preprocess plugins manager."""

    # pylint: disable=protected-access

    def testGetPluginsInDependencyOrder(self):
        """Tests the _GetPluginsInDependencyOrder function."""
        first_plugin = TestKnowledgeBasePreprocessorPlugin(["Third", "Missing"])
        second_plugin = TestKnowledgeBasePreprocessorPlugin([])
        third_plugin = TestKnowledgeBasePreprocessorPlugin(["Second"])

        plugins_per_name = {
            "first": first_plugin,
            "second": second_plugin,
            "third": third_plugin,
        }
        ordered_plugins = manager.PreprocessPluginsManager._GetPluginsInDependencyOrder(
            plugins_per_name
        )
        self.assertEqual(ordered_plugins, [second_plugin, third_plugin, first_plugin])

        # Test with a circular dependency.
        first_plugin = TestKnowledgeBasePreprocessorPlugin(["Second"])
        second_plugin = TestKnowledgeBasePreprocessorPlugin(["First"])

        plugins_per_name = {"first": first_plugin, "second": second_plugin}
        ordered_plugins = manager.PreprocessPluginsManager._GetPluginsInDependencyOrder(
            plugins_per_name
        )
        self.assertEqual(ordered_plugins, [second_plugin, first_plugin])

    def testGetPluginsInDependencyOrderWithWindowsRegistryPlugins(self):
        """Tests the _GetPluginsInDependencyOrder function with Windows plugins."""
        plugins_per_name = dict(
            reversed(manager.PreprocessPluginsManager._windows_registry_plugins.items())
        )
        ordered_plugins = manager.PreprocessPluginsManager._GetPluginsInDependencyOrder(
            plugins_per_name
        )
        plugin_names = [plugin.ARTIFACT_DEFINITION_NAME for plugin in ordered_plugins]

        self.assertLess(
            plugin_names.index("WindowsAvailableTimeZones"),
            plugin_names.index("WindowsTimezone"),
        )

    def testCollectFromFileSystem(self):
        """Tests the CollectFromFileSystem function."""
        artifacts_path = self._GetTestFilePath(["artifacts"])
        self._SkipIfPathNotExists(artifacts_path)

        registry = artifacts_registry.ArtifactDefinitionsRegistry()
        reader = artifacts_reader.YamlArtifactsReader()
        registry.ReadFromDirectory(reader, artifacts_path)

        # TODO: implement.
        # manager.PreprocessPluginsManager.CollectFromFileSystem(
        #     registry, None, None)

    # TODO: add tests for CollectFromWindowsRegistry
    # TODO: add tests for GetNames

    def testRegistrationPlugin(self):
        """Tests RegisterPlugin and DeregisterPlugin functions."""
        number_of_plugins = len(manager.PreprocessPluginsManager._plugins)

        manager.PreprocessPluginsManager.RegisterPlugin(TestArtifactPreprocessorPlugin)
        self.assertEqual(
            len(manager.PreprocessPluginsManager._plugins), number_of_plugins + 1
        )

        with self.assertRaises(KeyError):
            manager.PreprocessPluginsManager.RegisterPlugin(
                TestArtifactPreprocessorPlugin
            )

        manager.PreprocessPluginsManager.DeregisterPlugin(
            TestArtifactPreprocessorPlugin
        )
        self.assertEqual(
            len(manager.PreprocessPluginsManager._plugins), number_of_plugins
        )

    # TODO: add tests for RegisterPlugins

    # TODO: add tests for RunPlugins


if __name__ == "__main__":
    unittest.main()
