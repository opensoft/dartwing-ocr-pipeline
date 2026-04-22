# Implementation Plan: Evidence Packet Assembly (Trijunction-Ready)

**Branch**: `004-evidence-packet-assembly` | **Date**: 2026-04-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-evidence-packet-assembly/spec.md`

## Summary

Build the next stage 1 slice: a deterministic evidence-packet assembler that reads
the frozen `preprocess_output.json` (003) from a per-document folder and returns
a voter-agnostic, **Trijunction-shaped** Python dict / on-disk JSON object that
downstream model voters can consume as-is. The packet exposes named, typed slots
for all three Trijunction ingestion sources (PaddleOCR-VL, Falcon OCR, Falcon
Perception) even when only PaddleOCR is populated in stage 1, plus a section of
**candidate vendor signals** derived by deterministic regex over `document_text`
(emails, URLs, US phone numbers, EIN-shaped tax IDs). No model calls. No business
inference. No changes to the four existing persisted artifacts.

The assembler is a pure function over one `preprocess_output.json`. Default
behavior is in-memory: the caller receives the validated packet, nothing is
written to disk, and the four existing artifact files in the folder remain
byte-identical. When the `ledgerlinc_ocr` Python logger's effective level is
`DEBUG` or lower at invocation time (or equivalently, the CLI is invoked with
`-v/--verbose`), the assembler also persists the packet as `evidence_packet.json`
into the same folder — governed by a new `evidence_packet.schema.json` and a
`1.1.0` amendment to `folder.schema.json` that legalizes the file as an
**optional** generated artifact.

The slice is schema-first (the packet validates before being returned),
deterministic (byte-identical across runs, insertion-ordered keys, no
wall-clock timestamps in the payload), and forward-compatible for the
three-voter ensemble (slots for Falcon OCR / Falcon Perception are always
present with `not_implemented` status; voter consumers read the same shape
regardless of which model they wrap).

## Technical Context

**Language/Version**: Python 3.12 (devcontainer base image, matches 001/002/003).

**Primary Dependencies**:
- Existing, already in `pyproject.toml`: `jsonschema>=4.22,<5`, `pydantic>=2.7,<3`, Python stdlib (`json`, `re`, `logging`, `argparse`, `pathlib`, `os`).
- **No new runtime dependencies.** Assembly is pure Python over JSON — no PaddleOCR, no pypdfium2, no network, no GPU, no Ollama.
- Reuses 003's serializer convention (see `src/ledgerlinc_ocr/preprocessing/artifact.py::write_atomic` — `json.dump(..., ensure_ascii=False, indent=2, sort_keys=False)`, atomic rename via `.tmp-<pid>` + `os.replace`).
- Reuses 003's schema-validation pattern (`Draft202012Validator`, errors sorted by path).

**Storage**: Filesystem only. Reads one `preprocess_output.json` per invocation from `tests/stage1_vendor_identity/inv_XXX_<difficulty>/`. At default logger level, writes nothing. At `DEBUG` (or lower), writes exactly one `evidence_packet.json` into the same folder. No DB. No network. No model weights.

**Testing**: `pytest` under existing `tests/` layout. New tests split into:
- `tests/unit/evidence_packet/` — pure functions: regex hints, reverse-mapping from `document_text` offsets to `(page_index, block_index, line_index)`, ingestion-source slot assembly, canonical serialization.
- `tests/integration/evidence_packet/` — one file per user-story acceptance scenario; exercises the assembler against fixture `preprocess_output.json` files (some copied from 003's corpus outputs, some hand-crafted to cover edge cases like `not_implemented` sources and partial-failure states).
- `tests/contract_tests/evidence_packet_schema/` — the new `evidence_packet.schema.json` is parsed and exercised against fixture valid/invalid packets; the amended `folder.schema.json` is validated against both presence and absence of the new file.

**Target Platform**: Linux (devcontainer, native WSL Ubuntu 24.04). CPU only. No GPU, no cloud.

**Project Type**: Single Python package — extends the existing `src/ledgerlinc_ocr/` package with a new `evidence_packet/` module, sitting alongside `preprocessing/`, `validator/`, and `pipeline/`. Adds one new console script (`ledgerlinc-evidence-packet`) to `[project.scripts]` in `pyproject.toml`.

**Performance Goals**: Soft only. SC-001: assembly completes in well under one second on the devcontainer reference profile for any 20-document-corpus input. No release gate on latency (constitution §"Stage 1 Scope Constraints"). Determinism, not speed, is the hard requirement.

**Constraints**:
- Byte-identical packet output across reruns (FR-011, SC-002), enforced by insertion-ordered dict assembly + 003's canonical serializer.
- Always-validate against `evidence_packet.schema.json` before return (FR-015a, clarified Q3), even at default logger level.
- Zero writes at default logger level (SC-007), exactly one write at `DEBUG` level.
- Four existing per-document artifacts remain byte-identical before and after (FR-016, SC-006).
- Assembler refuses to produce a packet when `preprocess_output.json` is missing / unreadable / schema-invalid (FR-017); raises + non-zero CLI exit.
- No wall-clock timestamps, no run IDs, no randomness inside the packet payload (FR-012). Any such metadata goes to CLI logs, not the artifact.

**Scale/Scope**: Same 20-document stage 1 corpus as 003 (5 easy / 5 medium / 5 hard / 5 missing_name). One document per invocation. Multi-document orchestration is out of scope.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against `.specify/memory/constitution.md` v1.0.0:

| Principle | Gate | Status |
|-----------|------|--------|
| I. One Repo, Clear Runtime Boundaries | Evidence-packet assembly belongs to the pipeline layer; must not collapse preprocessing, extraction, routing, or harness concerns; must not bundle model runtime. | **PASS** — `src/ledgerlinc_ocr/evidence_packet/` is pipeline code only. Reads 003's artifact, writes at most one new artifact. No model runtime embedded. Harness still owns the corpus and evaluation. Host Ollama untouched. |
| II. Evidence-First, Schema-First Design | The packet IS the shared evidence-first boundary between preprocessing and voters. A new `evidence_packet.schema.json` governs the shape; all outputs (in-memory and persisted) validate against it; the `folder.schema.json` amendment legalizes the file as optional. | **PASS** — FR-015a mandates always-validate; FR-015c files a `1.1.0` amendment via `AMENDMENTS.md`; the packet carries `contract_set_version`. |
| III. Deterministic Control Over Model Output | Assembly is pure deterministic code: regex hints are deterministic; reverse-mapping from `document_text` offsets to `(page_index, block_index, line_index)` is deterministic; key ordering is insertion-based; no model output informs the packet. | **PASS** — FR-011, FR-012, FR-014 enforced by the design. Consensus / routing remain downstream concerns and are explicitly excluded (FR-010). |
| IV. Provenance and Review Safety | Candidate signals are stamped `unverified` so downstream voters know to confirm; the packet does not produce or imply `company_name.present` / `inferred` values. | **PASS** — FR-008 clarified Q2 keeps company-name and address slots empty/`null` in stage 1. Provenance remains a downstream slice's responsibility. Each regex hint carries explicit source refs (FR-008 clarified Q5) so downstream voters can point at evidence. |
| V. Benchmarkable and Reproducible Delivery | One-document execution; per-document folder layout preserved; deterministic output enables cross-run comparison. | **PASS** — CLI `ledgerlinc-evidence-packet <folder>` processes one document. Persisted file (if any) lives in the same per-document folder as the four existing artifacts. SC-002 demands ten identical reruns. |

**Stage 1 Scope Constraints** (constitution §"Stage 1 Scope Constraints"):
- PDF input only ✓ (indirect — consumes `preprocess_output.json` which itself constrains `source_type: "pdf"`).
- Vendor identity focus ✓ (candidate signals are the vendor-identity surface only; no line items).
- No line-item extraction ✓ (regex hints are vendor signals; tables pass through verbatim from 003).
- No cloud execution ✓ (pure Python, no network).
- No latency gate ✓ (SC-001 is soft).

**Quality Gates** (constitution §"Quality Gates"):
1. Pipeline vs. harness boundary — this slice is pipeline-only; harness is untouched.
2. Output contracts — **this slice does add a new contract** (`evidence_packet.schema.json`) and amend `folder.schema.json`. The amendment follows the `AMENDMENTS.md` checklist and bumps the contract set to `1.1.0` (MINOR, additive).
3. Runtime behavior — no change to the Ollama runtime story; `ollama-runtime.md` requires no update.
4. Verifiable through concrete local execution — CLI `ledgerlinc-evidence-packet <folder>` and `python -m ledgerlinc_ocr.evidence_packet <folder>`.
5. Runtime/container changes — none.
6. Evaluation comparison preserved — the harness still compares `final_structured_payload.json` to `expected.json`; the packet sits upstream of extraction.

**Result: PASS. No constitution violations. Complexity Tracking section left empty.**

## Project Structure

### Documentation (this feature)

```text
specs/004-evidence-packet-assembly/
├── plan.md              # This file
├── spec.md              # Feature specification (exists)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── cli-contract.md  # CLI surface (artifact shape lives under contracts/stage1_vendor_identity/v1.1.0/)
├── checklists/          # (spec-kit checklists — created by /speckit.checklist if used)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
contracts/stage1_vendor_identity/
├── AMENDMENTS.md                       # existing — append entry for v1.1.0
├── v1.0.0/                             # existing — frozen, untouched
└── v1.1.0/                             # NEW — copy of v1.0.0 plus:
    ├── contract_set.json               # contract_set_version = "1.1.0"; add "evidence_packet"
    ├── evidence_packet.schema.json     # NEW — Draft 2020-12 JSON Schema for the packet
    ├── folder.schema.json              # UPDATED — reserved_generated_filenames += evidence_packet.json (optional)
    ├── preprocess_output.schema.json   # unchanged bytes from v1.0.0
    ├── edge_extraction_output.schema.json
    ├── routing_decision.schema.json
    ├── final_structured_payload.schema.json
    ├── expected.schema.json
    ├── evaluation_document.schema.json
    └── evaluation_run_summary.schema.json

src/ledgerlinc_ocr/
├── __init__.py                         # existing
├── preprocessing/                      # existing
├── pipeline/                           # existing
├── validator/                          # existing — contract_set_version-aware; uses v1.0.0 today, v1.1.0 after amendment lands
└── evidence_packet/                    # NEW — this slice
    ├── __init__.py                     # public API: assemble_from_folder, assemble_from_preprocess, PacketAssemblyError
    ├── __main__.py                     # `python -m ledgerlinc_ocr.evidence_packet`
    ├── cli.py                          # argparse entry point; -v/--verbose → logging.DEBUG
    ├── assembler.py                    # orchestrates: load → validate-input → build sections → validate-output → [maybe-persist]
    ├── sections/
    │   ├── __init__.py
    │   ├── structural.py               # pages / blocks / reading_order / document_text passthrough
    │   ├── tables.py                   # tables passthrough (no re-interpretation)
    │   ├── trijunction.py              # paddleocr_vl / falcon_ocr / falcon_perception slot assembly
    │   ├── perceptual.py               # logos/stamps/header/footer candidates (stage 1 = empty, not_implemented)
    │   └── candidate_signals.py        # regex hints + company/address null slots
    ├── regex_hints.py                  # EMAIL_RE, URL_RE, US_PHONE_RE, EIN_RE + find_matches_in_order()
    ├── offset_mapping.py               # document_text offset → (page_index, block_index, line_index); mirrors join_document_text
    ├── serialization.py                # validate + write_atomic (wraps/reuses 003's helper)
    ├── schema.py                       # loads evidence_packet.schema.json, caches Draft202012Validator
    ├── errors.py                       # PacketAssemblyError, PreprocessInputMissing, PreprocessInputInvalid, PacketInvalid
    └── version.py                      # CONTRACT_SET_VERSION = "1.1.0"

tests/
├── contract_tests/
│   └── evidence_packet_schema/        # NEW — schema-level fixtures
│       ├── test_schema_valid_packet.py
│       ├── test_schema_rejects_missing_slot.py
│       ├── test_folder_schema_amendment.py    # folder validates with AND without evidence_packet.json
│       └── fixtures/                           # small hand-crafted packets
├── unit/evidence_packet/               # NEW
│   ├── test_regex_hints.py             # ordering, duplicates, no-dedup (SC-009, Q4)
│   ├── test_offset_mapping.py          # reverse-mapping determinism (Q5)
│   ├── test_trijunction_slots.py       # all three sources always present with correct status
│   ├── test_candidate_signals_nulls.py # company/address stay null in stage 1
│   ├── test_serialization.py           # byte-identical serialization, no trailing newline
│   └── test_null_discipline.py         # FR-014 — null scalars, empty arrays, never empty string
├── integration/evidence_packet/        # NEW — per-acceptance-scenario files
│   ├── conftest.py                     # fixture preprocess_output.json builders
│   ├── test_us1_schema_valid_packet.py # US1 AC#1
│   ├── test_us1_determinism.py         # US1 AC#2 (ten identical reruns)
│   ├── test_us1_ingestion_slots.py     # US1 AC#3 (not_implemented preserved)
│   ├── test_us1_regex_hints.py         # US1 AC#4
│   ├── test_us1_logging_persistence.py # US1 AC#5 (DEBUG writes, default does not)
│   ├── test_us2_pluggable_slots.py     # US2 AC#1..2
│   ├── test_us3_voter_agnostic.py      # US3 AC#1..2 (no voter/model/prompt keys in packet)
│   ├── test_us4_folder_integration.py  # US4 AC#1..3 (folder contract amendment)
│   ├── test_edge_partial_failure.py    # partial-failure sources preserved
│   ├── test_edge_zero_page.py          # zero-page document
│   ├── test_edge_invalid_preprocess.py # FR-017 error path
│   ├── test_edge_readonly_folder.py    # DEBUG + read-only folder → clear error
│   └── test_no_ollama_no_cloud.py      # pytest-socket-gated
└── fixtures/evidence_packet/           # NEW — hand-crafted small preprocess_output.json samples
    ├── minimal_valid.json              # one page, one block, one line
    ├── with_regex_hits.json            # contains email, URL, US phone, EIN in document_text
    ├── all_sources_not_implemented.json
    ├── paddleocr_vl_failure.json
    ├── zero_pages.json                 # edge case: zero-page
    ├── empty_document_text.json        # blocks present, text empty
    └── multi_match.json                # same email twice, two phones, etc. for Q4 duplicate semantics
```

**Structure Decision**: Single-project Python package. The new slice lives at
`src/ledgerlinc_ocr/evidence_packet/`, sibling to `preprocessing/`, `validator/`,
and `pipeline/`. This preserves the "pipeline code owns preprocessing and
extraction orchestration" boundary from the constitution while keeping the
packet-assembly concern cleanly separable so 005 (single-voter extraction)
can import it without touching preprocessing internals. The CLI is exposed
both as a module (`python -m ledgerlinc_ocr.evidence_packet`) and as a console
script (`ledgerlinc-evidence-packet`) — matching 003's `ledgerlinc-preprocess`
pattern. The new contract version `v1.1.0` is copied verbatim from `v1.0.0`
and the `evidence_packet.schema.json` plus `folder.schema.json` delta applied
inside the new directory (per `AMENDMENTS.md` step 3).

## Complexity Tracking

> No constitution violations to justify. Section intentionally empty.
