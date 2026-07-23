"""Smoke tests for Fase 0 packaging.

These deliberately avoid instantiating ``tk.Tk()`` or opening any real
video/webcam device so they can run headless in CI (Risco R7).
"""

import importlib.metadata

from src.Modules.ExportModule.jsonUtils import (
    export_data_to_file,
    import_data_from_file,
)


def test_json_utils_importable():
    assert callable(export_data_to_file)
    assert callable(import_data_from_file)


def test_package_metadata():
    assert importlib.metadata.version("animaltrack")
