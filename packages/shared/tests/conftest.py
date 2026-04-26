# GRACE-LDD: this conftest exposes the `grace_logs` pytest fixture so any
# test in this package can capture and assert on GRACE LDD log emissions.
# See docs/verification-plan.xml GlobalPolicy/log-format and CP6 of
# MIGRATION_LOG.md for the rollout history.

from __future__ import annotations

from typing import Iterator

import pytest

from shared.grace.testing import GraceLogCapture


@pytest.fixture
def grace_logs() -> Iterator[GraceLogCapture]:
    """Capture GRACE LDD log lines emitted during a test.

    Usage:
        def test_something(grace_logs):
            ... run code under test ...
            assert grace_logs.beliefs(fn="orders.create", status="MATCH")
            grace_logs.assert_trajectory(
                ("orders.create", "BLOCK_TX_BEGIN"),
                ("orders.create", "BLOCK_STATE_TRANSITION"),
                ("orders.create", "BLOCK_TX_COMMIT"),
            )
    """
    capture = GraceLogCapture()
    capture.install()
    try:
        yield capture
    finally:
        capture.uninstall()
