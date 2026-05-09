from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


pytest_plugins = [
    "pytest_homeassistant_custom_component",
]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations,
):
    """Automatically enable loading custom integrations."""
    yield
