"""GPU MVP Demo CLI (feature 023).

Entry point: ``python -m dartwing_ocr.gpu_demo`` (or the ``dartwing-gpu-demo``
console script). Composes existing pipeline sub-modules (preprocessing →
extract → router → assembler) behind a fixed-order readiness preflight + a
bounded pipeline timeout + a stable-shape DemoRunReport JSON line on stdout.

See specs/023-gpu-mvp-demo-hardening/ for the spec, plan, and contracts.
"""
