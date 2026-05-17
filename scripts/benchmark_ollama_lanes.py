#!/usr/bin/env python3
"""Benchmark stage 1 preprocessing + extraction across Ollama lanes.

The helper is intentionally folder-oriented and runs on a temporary copy of the
requested per-document folder so the committed corpus is never mutated.

Current stage 1 benchmark flow:
1. `python -m dartwing_ocr.preprocessing --document-folder <temp-folder>`
2. `python -m dartwing_ocr.extract --folder <temp-folder> --voter gemma-edge`

The top-level `dartwing-pipeline` CLI is not used here because it is still
the frozen contract/stub runner rather than the fully wired vertical slice.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_GPU_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_CPU_URL = os.environ.get("OLLAMA_CPU_URL", "http://localhost:11435")

GENERATED_FILES = (
    "preprocess_output.json",
    "edge_extraction_output.json",
    "routing_decision.json",
    "final_structured_payload.json",
    "evaluation_document.json",
    "evidence_packet.json",
    "evaluation_run_summary.json",
    "evaluation_run_summary.md",
)
GENERATED_DIRS = ("votes",)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _derive_document_id(folder: Path) -> str:
    match = re.match(r"^(inv_\d{3})", folder.name)
    if match:
        return match.group(1)
    return folder.name


def _text_or_none(text: str) -> str | None:
    stripped = text.strip()
    return stripped or None


def _load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _artifact_summary(path: Path) -> dict[str, Any] | None:
    payload = _load_json_if_exists(path)
    if payload is None:
        return None

    summary: dict[str, Any] = {
        "path": str(path),
        "document_id": payload.get("document_id"),
        "warnings_count": len(payload.get("warnings", [])),
    }

    if "page_count" in payload:
        summary["page_count"] = payload.get("page_count")
    if "status" in payload:
        summary["status"] = payload.get("status")
    if "contract_set_version" in payload:
        summary["contract_set_version"] = payload.get("contract_set_version")

    return summary


def _clean_generated_outputs(folder: Path) -> None:
    for name in GENERATED_FILES:
        target = folder / name
        if target.exists():
            target.unlink()
    for name in GENERATED_DIRS:
        target = folder / name
        if target.is_dir():
            shutil.rmtree(target)


def _child_env(repo_root: Path, ollama_url: str | None) -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(repo_root / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        src_path if not existing else f"{src_path}{os.pathsep}{existing}"
    )
    if ollama_url is not None:
        env["OLLAMA_BASE_URL"] = ollama_url
    return env


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> dict[str, Any]:
    started_at = _utc_now_iso()
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    finished_at = _utc_now_iso()
    elapsed_s = time.monotonic() - started

    stdout_text = _text_or_none(completed.stdout)
    stderr_text = _text_or_none(completed.stderr)

    stdout_json: dict[str, Any] | None = None
    if stdout_text is not None:
        try:
            stdout_json = json.loads(stdout_text)
        except json.JSONDecodeError:
            stdout_json = None

    return {
        "command": shlex.join(command),
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_s": round(elapsed_s, 3),
        "exit_code": completed.returncode,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "stdout_json": stdout_json,
    }


def _lane_url(lane: str, args: argparse.Namespace) -> str:
    if lane == "gpu":
        return args.gpu_url
    if lane == "cpu":
        return args.cpu_url
    raise ValueError(f"unsupported lane {lane!r}")


def _benchmark_lane(
    *,
    lane: str,
    source_folder: Path,
    repo_root: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    lane_started_at = _utc_now_iso()
    lane_started = time.monotonic()
    work_root = (
        Path(tempfile.mkdtemp(prefix=f"benchmark_{source_folder.name}_{lane}_"))
        if args.work_root is None
        else Path(
            tempfile.mkdtemp(
                prefix=f"benchmark_{source_folder.name}_{lane}_",
                dir=str(args.work_root),
            )
        )
    )
    work_folder = work_root / source_folder.name

    preprocess_result: dict[str, Any] | None = None
    extract_result: dict[str, Any] | None = None
    error_message: str | None = None

    try:
        shutil.copytree(source_folder, work_folder)
        _clean_generated_outputs(work_folder)

        preprocess_command = [
            sys.executable,
            "-m",
            "dartwing_ocr.preprocessing",
            "--document-folder",
            str(work_folder),
        ]
        preprocess_result = _run_command(
            preprocess_command,
            cwd=repo_root,
            env=_child_env(repo_root, None),
        )
        preprocess_result["artifact"] = _artifact_summary(
            work_folder / "preprocess_output.json"
        )

        if preprocess_result["exit_code"] == 0:
            extract_command = [
                sys.executable,
                "-m",
                "dartwing_ocr.extract",
                "--folder",
                str(work_folder),
                "--voter",
                args.voter,
                "--log-level",
                args.extract_log_level,
            ]
            extract_result = _run_command(
                extract_command,
                cwd=repo_root,
                env=_child_env(repo_root, _lane_url(lane, args)),
            )
            extract_result["artifact"] = _artifact_summary(
                work_folder / "edge_extraction_output.json"
            )
    except Exception as exc:  # noqa: BLE001
        error_message = f"{type(exc).__name__}: {exc}"

    lane_finished_at = _utc_now_iso()
    lane_elapsed_s = time.monotonic() - lane_started

    completed = (
        error_message is None
        and preprocess_result is not None
        and preprocess_result["exit_code"] == 0
        and extract_result is not None
        and extract_result["exit_code"] == 0
    )

    result = {
        "lane": lane,
        "ollama_url": _lane_url(lane, args),
        "source_folder": str(source_folder),
        "document_id": _derive_document_id(source_folder),
        "started_at": lane_started_at,
        "finished_at": lane_finished_at,
        "elapsed_total_s": round(lane_elapsed_s, 3),
        "completed": completed,
        "work_folder": str(work_folder),
        "work_folder_preserved": bool(args.keep_workdir),
        "preprocess": preprocess_result,
        "extract": extract_result,
    }
    if error_message is not None:
        result["error"] = error_message

    if not args.keep_workdir:
        shutil.rmtree(work_root, ignore_errors=True)

    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmark_ollama_lanes.py",
        description=(
            "Run stage 1 preprocessing + extraction against the GPU host Ollama "
            "lane, the CPU container Ollama lane, or both."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--folder",
        required=True,
        type=Path,
        help="Per-document folder to benchmark (e.g. tests/stage1_vendor_identity/inv_003_easy).",
    )
    parser.add_argument(
        "--lane",
        required=True,
        choices=("gpu", "cpu", "both"),
        help="Benchmark the host GPU lane, the container CPU lane, or both sequentially.",
    )
    parser.add_argument(
        "--voter",
        default="gemma-edge",
        help="Extractor voter name passed to dartwing_ocr.extract.",
    )
    parser.add_argument(
        "--gpu-url",
        default=DEFAULT_GPU_URL,
        help="Ollama URL for the GPU lane.",
    )
    parser.add_argument(
        "--cpu-url",
        default=DEFAULT_CPU_URL,
        help="Ollama URL for the CPU lane.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSONL file to append one benchmark-run record to.",
    )
    parser.add_argument(
        "--work-root",
        type=Path,
        default=None,
        help="Optional parent directory for temporary benchmark copies.",
    )
    parser.add_argument(
        "--keep-workdir",
        action="store_true",
        help="Keep the temporary working copy after the run finishes.",
    )
    parser.add_argument(
        "--extract-log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Log level forwarded to dartwing_ocr.extract.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    source_folder = args.folder.resolve()
    if not source_folder.is_dir():
        parser.error(f"--folder is not a directory: {source_folder}")
    if not (source_folder / "source.pdf").is_file():
        parser.error(f"--folder does not contain source.pdf: {source_folder}")
    if args.work_root is not None:
        args.work_root.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parents[1]
    lanes = ("gpu", "cpu") if args.lane == "both" else (args.lane,)

    started_at = _utc_now_iso()
    started = time.monotonic()
    results = [
        _benchmark_lane(
            lane=lane,
            source_folder=source_folder,
            repo_root=repo_root,
            args=args,
        )
        for lane in lanes
    ]
    finished_at = _utc_now_iso()
    elapsed_total_s = time.monotonic() - started

    summary = {
        "record_type": "stage1_ollama_lane_benchmark",
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_total_s": round(elapsed_total_s, 3),
        "folder": str(source_folder),
        "document_id": _derive_document_id(source_folder),
        "requested_lane": args.lane,
        "voter": args.voter,
        "results": results,
    }

    sys.stdout.write(json.dumps(summary, indent=2, ensure_ascii=False))
    sys.stdout.write("\n")

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(summary, ensure_ascii=False))
            handle.write("\n")

    return 0 if all(result["completed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
