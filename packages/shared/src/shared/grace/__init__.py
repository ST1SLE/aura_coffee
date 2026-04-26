"""GRACE methodology helpers for aura_coffee.

This subpackage provides Log-Driven Development (LDD) helpers that emit
log markers in the canonical GRACE format: ``[Module][function][BLOCK_NAME]``.
See ``docs/verification-plan.xml`` for conventions and ``MIGRATION_LOG.md``
for rollout history.
"""

from shared.grace.logging import GraceLogger, get_grace_logger

__all__ = ["GraceLogger", "get_grace_logger"]
