from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import yaml

from .config import get_settings
from .models import GenerateRequest
from .orchestrator import TestGenerationOrchestrator


def _safe_write(root: Path, relative_path: str, content: str) -> None:
    destination = (root / relative_path).resolve()
    resolved_root = root.resolve()
    if resolved_root not in destination.parents and destination != resolved_root:
        raise ValueError(f"artifact path escapes output directory: {relative_path}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, mode="w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        os.replace(temporary_path, destination)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _write_with_progress(
    *,
    root: Path,
    relative_path: str,
    content: str,
    current: int,
    total: int,
) -> None:
    size_kib = len(content.encode("utf-8")) / 1024
    print(
        f"[{current}/{total}] Writing {relative_path} ({size_kib:.1f} KiB)",
        file=sys.stderr,
        flush=True,
    )
    _safe_write(root, relative_path, content)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-soap",
        description="Generate an evidence-linked SOAP integration test suite.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    generate = subcommands.add_parser("generate", help="generate tests from YAML or JSON context")
    generate.add_argument(
        "--context", required=True, type=Path, help="GenerateRequest YAML/JSON file"
    )
    generate.add_argument("--output", required=True, type=Path, help="artifact output directory")
    generate.add_argument(
        "--result-json",
        type=Path,
        help="optional path for the complete API result, including trace and evidence",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    raw = args.context.read_text(encoding="utf-8")
    payload = json.loads(raw) if args.context.suffix.lower() == ".json" else yaml.safe_load(raw)
    request = GenerateRequest.model_validate(payload)
    result = TestGenerationOrchestrator(get_settings()).generate(request)
    args.output.mkdir(parents=True, exist_ok=True)
    total_writes = len(result.artifacts) + (1 if args.result_json else 0)
    for index, artifact in enumerate(result.artifacts, start=1):
        _write_with_progress(
            root=args.output,
            relative_path=artifact.path,
            content=artifact.content,
            current=index,
            total=total_writes,
        )
    if args.result_json:
        _write_with_progress(
            root=args.result_json.parent,
            relative_path=args.result_json.name,
            content=result.model_dump_json(indent=2) + "\n",
            current=total_writes,
            total=total_writes,
        )
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "status": result.status,
                "scenarios": len(result.scenarios),
                "artifacts": len(result.artifacts),
                "output": str(args.output.resolve()),
            },
            indent=2,
        )
    )
    return 0 if result.status != "failed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
