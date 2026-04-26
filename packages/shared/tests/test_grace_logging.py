# GRACE-LDD: smoke tests for the LDD logger and the test-capture fixture.
# Verifies the canonical [Module][fn][BLOCK] format and the BELIEF/ACTUAL/
# STATUS=MATCH|MISMATCH parser. See docs/verification-plan.xml V-M-SHARED.

from __future__ import annotations

import logging

import pytest

from shared.grace.logging import GraceLogger, get_grace_logger
from shared.grace.testing import GraceLogCapture, parse_belief


def test_block_marker_format(grace_logs: GraceLogCapture) -> None:
    log = get_grace_logger("Smoke")
    log.block("smoke.fn", "BLOCK_HELLO", "msg", k="v")

    lines = grace_logs.lines
    assert any("[Smoke][smoke.fn][BLOCK_HELLO]" in line for line in lines)
    blocks = grace_logs.blocks(fn="smoke.fn", blk="BLOCK_HELLO")
    assert len(blocks) == 1
    assert "k=v" in blocks[0]


def test_belief_match(grace_logs: GraceLogCapture) -> None:
    log = get_grace_logger("Smoke")
    log.belief("smoke.fn", "BLOCK_TX", belief="PAID", actual="PAID")

    beliefs = grace_logs.beliefs(fn="smoke.fn", blk="BLOCK_TX")
    assert len(beliefs) == 1
    assert beliefs[0].status == "MATCH"
    assert beliefs[0].belief == "PAID"
    assert beliefs[0].actual == "PAID"


def test_belief_mismatch(grace_logs: GraceLogCapture) -> None:
    log = get_grace_logger("Smoke")
    log.belief("smoke.fn", "BLOCK_TX", belief="PAID", actual="FAILED")

    mismatches = grace_logs.beliefs(status="MISMATCH")
    assert len(mismatches) == 1
    assert mismatches[0].belief == "PAID"
    assert mismatches[0].actual == "FAILED"


def test_assert_trajectory_in_order(grace_logs: GraceLogCapture) -> None:
    log = get_grace_logger("Smoke")
    log.block("smoke.fn", "BLOCK_A")
    log.block("smoke.fn", "BLOCK_B")
    log.block("smoke.fn", "BLOCK_C")

    grace_logs.assert_trajectory(
        ("smoke.fn", "BLOCK_A"),
        ("smoke.fn", "BLOCK_B"),
        ("smoke.fn", "BLOCK_C"),
    )


def test_assert_trajectory_missing_marker(grace_logs: GraceLogCapture) -> None:
    log = get_grace_logger("Smoke")
    log.block("smoke.fn", "BLOCK_A")

    with pytest.raises(AssertionError, match="missing markers"):
        grace_logs.assert_trajectory(
            ("smoke.fn", "BLOCK_A"),
            ("smoke.fn", "BLOCK_NEVER_EMITTED"),
        )


def test_parse_belief_standalone() -> None:
    line = "[CoreApi][orders.create][BLOCK_STATE_TRANSITION] BELIEF: CREATED ACTUAL: CREATED STATUS: MATCH order_id=abc"
    parsed = parse_belief(line)
    assert parsed is not None
    assert parsed.module == "CoreApi"
    assert parsed.fn == "orders.create"
    assert parsed.blk == "BLOCK_STATE_TRANSITION"
    assert parsed.status == "MATCH"


def test_parse_belief_returns_none_for_non_belief_lines() -> None:
    assert parse_belief("[CoreApi][orders.create][BLOCK_TX_BEGIN] user_id=abc") is None
    assert parse_belief("plain log message") is None


def test_module_label_from_logger_name() -> None:
    base = logging.getLogger("payment_worker.tasks")
    log = GraceLogger("PaymentWorker", base=base)
    assert log._module == "PaymentWorker"
    assert log._logger is base
