import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]

from zorix_core_model import Adapter
from zorix_mock_adapter import MockAdapter
from zorix_plugin_loader import PluginLoader


class PluginLoaderTest(unittest.TestCase):
    def test_loads_mock_adapter(self) -> None:
        adapters = PluginLoader().load(ROOT / "modules" / "mock_adapter")

        self.assertEqual(len(adapters), 1)
        self.assertIsInstance(adapters[0], MockAdapter)
        self.assertIsInstance(adapters[0], Adapter)

    def test_avoids_duplicate_exports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory) / "duplicate_adapter"
            plugin_dir.mkdir()
            (plugin_dir / "__init__.py").write_text(
                textwrap.dedent(
                    """
                    from zorix_core_model import Adapter as BaseAdapter


                    class MockAdapter(BaseAdapter):
                        def discover(self):
                            return []


                    Adapter = MockAdapter
                    """
                ).strip(),
                encoding="utf-8",
            )

            adapters = PluginLoader().load(directory)

        self.assertEqual(len(adapters), 1)

    def test_import_error_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory) / "broken_adapter"
            plugin_dir.mkdir()
            (plugin_dir / "__init__.py").write_text(
                "import missing_zorix_dependency\n",
                encoding="utf-8",
            )

            with self.assertRaises(ImportError):
                PluginLoader().load(directory)

    def test_invalid_class_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory) / "invalid_adapter"
            plugin_dir.mkdir()
            (plugin_dir / "__init__.py").write_text(
                textwrap.dedent(
                    """
                    class MockAdapter:
                        def discover(self):
                            return []
                    """
                ).strip(),
                encoding="utf-8",
            )

            with self.assertRaises(TypeError):
                PluginLoader().load(directory)


if __name__ == "__main__":
    unittest.main()
