import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def page_with_ld(payload, extra_body: str = "") -> str:
    return (
        "<html><head><title>Job</title>"
        f'<script type="application/ld+json">{json.dumps(payload)}</script>'
        f"</head><body>{extra_body}</body></html>"
    )


@pytest.fixture
def make_page():
    return page_with_ld
