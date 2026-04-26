# START_MODULE_CONTRACT
#   PURPOSE: Test helpers for asserting on GRACE LDD log emissions. Captures
#            stdlib logging records emitted via shared.grace.logging into a
#            structured object that tests can grep, filter, and assert against.
#   SCOPE:   GraceLogCapture (context manager / fixture-friendly), parse_belief
#            for one-line parsing, BeliefLine record. Pure-python; no pytest
#            dependency at import time so this module can be reused outside
#            pytest contexts.
#   DEPENDS: stdlib logging, dataclasses, re.
#   LINKS:   docs/verification-plan.xml GlobalPolicy/log-format,
#            docs/development-plan.xml M-SHARED, packages/shared/src/shared/grace/logging.py.
#   ROLE:    TEST
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   GraceLogCapture - context manager that records GRACE log lines for assertion
#   BeliefLine      - dataclass for one parsed BELIEF/ACTUAL/STATUS emission
#   parse_belief    - parse one log message into a BeliefLine, or None
# END_MODULE_MAP

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable, Optional

_BELIEF_RE = re.compile(
    r"\[(?P<module>[^\[\]]+)\]\[(?P<fn>[^\[\]]+)\]\[(?P<blk>[^\[\]]+)\]"
    r"\s+BELIEF:\s+(?P<belief>\S+)\s+ACTUAL:\s+(?P<actual>\S+)\s+STATUS:\s+(?P<status>\w+)"
)

_BLOCK_RE = re.compile(
    r"\[(?P<module>[^\[\]]+)\]\[(?P<fn>[^\[\]]+)\]\[(?P<blk>[^\[\]]+)\]"
)


@dataclass
class BeliefLine:
    module: str
    fn: str
    blk: str
    belief: str
    actual: str
    status: str  # "MATCH" | "MISMATCH"


# START_CONTRACT: parse_belief
#   PURPOSE: Parse a single log message into a BeliefLine if it follows the
#            GRACE belief-state format, otherwise return None.
#   INPUTS:  line: str — the full log message text.
#   OUTPUTS: BeliefLine | None
#   SIDE_EFFECTS: none
#   LINKS:   docs/verification-plan.xml GlobalPolicy/belief-state.
# END_CONTRACT: parse_belief
def parse_belief(line: str) -> Optional[BeliefLine]:
    m = _BELIEF_RE.search(line)
    if m is None:
        return None
    return BeliefLine(**m.groupdict())


# START_CONTRACT: GraceLogCapture
#   PURPOSE: Capture GRACE LDD log emissions (block + belief markers) so tests
#            can assert on the trajectory of log lines a code path produced.
#   INPUTS:  optional logger: logging.Logger — defaults to the root logger so
#            emissions from any GraceLogger instance are captured.
#   OUTPUTS: instance with .lines, .blocks(...), .beliefs(...), .assert_trajectory(...).
#   SIDE_EFFECTS: install() attaches a logging.Handler to the target logger and
#                 raises its level to INFO if higher; uninstall() reverts.
#                 Use as a context manager to scope automatically.
#   LINKS:   shared.grace.logging.GraceLogger, docs/verification-plan.xml.
# END_CONTRACT: GraceLogCapture
class GraceLogCapture:
    def __init__(self) -> None:
        self._records: list[logging.LogRecord] = []
        self._handler: Optional[logging.Handler] = None
        self._target: Optional[logging.Logger] = None
        self._old_level: int = logging.NOTSET

    def install(self, target: Optional[logging.Logger] = None) -> "GraceLogCapture":
        # START_BLOCK_INSTALL
        self._target = target if target is not None else logging.getLogger()
        self._old_level = self._target.level
        records = self._records

        class _Handler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        self._handler = _Handler(level=logging.INFO)
        self._target.addHandler(self._handler)
        if self._target.level == logging.NOTSET or self._target.level > logging.INFO:
            self._target.setLevel(logging.INFO)
        return self
        # END_BLOCK_INSTALL

    def uninstall(self) -> None:
        # START_BLOCK_UNINSTALL
        if self._handler is not None and self._target is not None:
            self._target.removeHandler(self._handler)
            if self._old_level != logging.NOTSET:
                self._target.setLevel(self._old_level)
        self._handler = None
        self._target = None
        # END_BLOCK_UNINSTALL

    def __enter__(self) -> "GraceLogCapture":
        return self.install()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.uninstall()

    @property
    def lines(self) -> list[str]:
        return [r.getMessage() for r in self._records]

    def blocks(
        self,
        fn: Optional[str] = None,
        blk: Optional[str] = None,
        module: Optional[str] = None,
    ) -> list[str]:
        out: list[str] = []
        for line in self.lines:
            m = _BLOCK_RE.search(line)
            if m is None:
                continue
            if module is not None and m.group("module") != module:
                continue
            if fn is not None and m.group("fn") != fn:
                continue
            if blk is not None and m.group("blk") != blk:
                continue
            out.append(line)
        return out

    def beliefs(
        self,
        fn: Optional[str] = None,
        blk: Optional[str] = None,
        module: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[BeliefLine]:
        out: list[BeliefLine] = []
        for line in self.lines:
            parsed = parse_belief(line)
            if parsed is None:
                continue
            if module is not None and parsed.module != module:
                continue
            if fn is not None and parsed.fn != fn:
                continue
            if blk is not None and parsed.blk != blk:
                continue
            if status is not None and parsed.status != status:
                continue
            out.append(parsed)
        return out

    def assert_trajectory(self, *expected: tuple[str, str]) -> None:
        # START_BLOCK_ASSERT_TRAJECTORY
        idx = 0
        captured = self.lines
        for line in captured:
            if idx == len(expected):
                break
            fn, blk = expected[idx]
            pat = re.compile(rf"\[[^\[\]]+\]\[{re.escape(fn)}\]\[{re.escape(blk)}\]")
            if pat.search(line):
                idx += 1
        if idx < len(expected):
            missing = list(expected[idx:])
            joined = "\n  ".join(captured) if captured else "(no GRACE log lines captured)"
            raise AssertionError(
                "GRACE LDD trajectory missing markers (in order):\n  expected next: "
                f"{missing[0]}\n  remaining: {missing[1:]}\n"
                f"Captured lines:\n  {joined}"
            )
        # END_BLOCK_ASSERT_TRAJECTORY


def _summarize(lines: Iterable[str]) -> str:
    # GRACE-LDD: helper for friendlier assertion messages; private (skip contract).
    return "\n  ".join(lines) if lines else "(no GRACE log lines captured)"
