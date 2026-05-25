"""Readiness checks for the GPU MVP demo (FR-016, FR-026).

The 8 named checks are defined in ``contracts/readiness-vocabulary.md`` and
executed in fixed declaration order by the runner. ``base.py`` defines the
Protocol and result shapes; per-check modules implement individual probes.
"""
