# START_MODULE_CONTRACT
#   PURPOSE: Lightweight LDD logging helper that emits canonical GRACE markers
#            ``[Module][function][BLOCK_NAME]`` and belief-state pairs around
#            PDD §6 state-machine transitions. Wraps stdlib logging — does not
#            replace it, so existing logger.info/.warning/.error calls keep working.
#   SCOPE:   Used by all backend modules (core-api, payment-worker, sms-worker)
#            for verification-grade observability. See docs/verification-plan.xml
#            GlobalPolicy/log-format and INV-013 redaction guidance.
#   DEPENDS: stdlib logging only.
#   LINKS:   docs/verification-plan.xml, docs/development-plan.xml M-SHARED.
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   GraceLogger        - thin wrapper around logging.Logger with .block() and .belief()
#   get_grace_logger   - factory that returns a GraceLogger bound to a module name
# END_MODULE_MAP

from __future__ import annotations

import logging
from typing import Any, Optional


# START_CONTRACT: GraceLogger
#   PURPOSE: Emit GRACE-format log lines bound to a module label, so downstream
#            agents (and the verification plan) can grep by [Module][fn][BLOCK].
#   INPUTS:  module: str — module label like "CoreApi" or "PaymentWorker"
#            base:   logging.Logger | None — optional underlying logger; defaults
#                    to logging.getLogger(module).
#   OUTPUTS: GraceLogger instance.
#   SIDE_EFFECTS: none on construction; .block()/.belief() emit through stdlib logging.
#   LINKS:   docs/verification-plan.xml GlobalPolicy/log-format
# END_CONTRACT: GraceLogger
class GraceLogger:
    def __init__(self, module: str, base: Optional[logging.Logger] = None) -> None:
        self._module = module
        self._logger = base if base is not None else logging.getLogger(module)

    # START_CONTRACT: GraceLogger.block
    #   PURPOSE: Emit a block-marker log line at INFO level.
    #   INPUTS:  fn: str  — function or step label
    #            blk: str — BLOCK_NAME (UPPER_SNAKE) — see development-plan critical-block lists
    #            msg: str — short human-readable message (optional)
    #            **fields — extra structured key=value pairs appended to the line
    #   OUTPUTS: None
    #   SIDE_EFFECTS: emits through underlying stdlib logger at INFO
    # END_CONTRACT: GraceLogger.block
    def block(self, fn: str, blk: str, msg: str = "", **fields: Any) -> None:
        # START_BLOCK_LDD_EMIT
        prefix = f"[{self._module}][{fn}][{blk}]"
        body = msg.strip()
        extras = " ".join(f"{k}={v}" for k, v in fields.items()) if fields else ""
        line = " ".join(part for part in (prefix, body, extras) if part)
        self._logger.info(line)
        # END_BLOCK_LDD_EMIT

    # START_CONTRACT: GraceLogger.belief
    #   PURPOSE: Emit a belief-state log line at INFO comparing the agent's hypothesis
    #            against the observed runtime value. Required at PDD §6.x state-machine
    #            boundaries (INV-016).
    #   INPUTS:  fn: str
    #            blk: str
    #            belief: Any — the hypothesis (typically expected status enum value)
    #            actual: Any — the runtime value
    #            **fields — extra key=value annotations
    #   OUTPUTS: None
    #   SIDE_EFFECTS: emits through underlying stdlib logger at INFO; never raises.
    #   NOTE: Comparison is by str() so enum/string mixes still work cleanly.
    # END_CONTRACT: GraceLogger.belief
    def belief(self, fn: str, blk: str, belief: Any, actual: Any, **fields: Any) -> None:
        # START_BLOCK_LDD_BELIEF
        status = "MATCH" if str(belief) == str(actual) else "MISMATCH"
        prefix = f"[{self._module}][{fn}][{blk}]"
        core = f"BELIEF: {belief} ACTUAL: {actual} STATUS: {status}"
        extras = " ".join(f"{k}={v}" for k, v in fields.items()) if fields else ""
        line = " ".join(part for part in (prefix, core, extras) if part)
        self._logger.info(line)
        # END_BLOCK_LDD_BELIEF


# START_CONTRACT: get_grace_logger
#   PURPOSE: Factory for module-bound GraceLogger; preferred entry point so
#            callers do not need to import the class directly.
#   INPUTS:  module: str
#            base:   logging.Logger | None
#   OUTPUTS: GraceLogger
#   SIDE_EFFECTS: none
# END_CONTRACT: get_grace_logger
def get_grace_logger(module: str, base: Optional[logging.Logger] = None) -> GraceLogger:
    return GraceLogger(module, base)
