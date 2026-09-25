import pytest


def pytest_collection_modifyitems(config, items):
    for item in items:
        marker_names = {marker.name for marker in item.iter_markers()}
        if "unit" not in marker_names and "integration" not in marker_names:
            raise pytest.UsageError(
                f"{item.nodeid} must be marked @pytest.mark.unit or "
                "@pytest.mark.integration"
            )
