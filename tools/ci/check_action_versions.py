#!/usr/bin/env python3
# Copyright 2026 The Lynx Authors. All rights reserved.
# Licensed under the Apache License Version 2.0 that can be found in the
# LICENSE file in the root directory of this source tree.

"""Validate external GitHub Action revisions against action-versions.yml."""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from pathlib import Path


SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
ACTION_PATTERN = re.compile(
    r"^\s*(?:-\s+)?uses:\s*([^\s@]+)@([^\s#]+)(?:\s+#\s*(.*?))?\s*$"
)
ACTION_KEY_PATTERN = re.compile(r"^  ([^:\s]+):\s*$")
FIELD_PATTERN = re.compile(r"^    (ref|sha):\s*(.*?)\s*$")


def parse_manifest(path: Path) -> dict[str, dict[str, str | None]]:
    """Parse the small, deliberately constrained manifest format."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if "schema_version: 1" not in lines:
        raise ValueError(f"{path}: expected schema_version: 1")

    actions: dict[str, dict[str, str | None]] = {}
    current_action: str | None = None
    in_actions = False

    for line_number, line in enumerate(lines, 1):
        if line == "actions:":
            in_actions = True
            continue

        if not in_actions or not line or line.lstrip().startswith("#"):
            continue

        action_match = ACTION_KEY_PATTERN.match(line)
        if action_match:
            current_action = action_match.group(1)
            actions[current_action] = {}
            continue

        field_match = FIELD_PATTERN.match(line)
        if field_match and current_action:
            name, value = field_match.groups()
            actions[current_action][name] = (
                None if value == "null" else value.strip("'")
            )
            continue

        raise ValueError(f"{path}:{line_number}: unsupported manifest syntax")

    if not actions:
        raise ValueError(f"{path}: missing actions mapping")

    for action, entry in actions.items():
        if set(entry) != {"ref", "sha"}:
            raise ValueError(f"{path}: {action} must define ref and sha")
        if not isinstance(entry["sha"], str) or not SHA_PATTERN.fullmatch(entry["sha"]):
            raise ValueError(f"{path}: {action} must use a 40-character lowercase SHA")

    return actions


def iter_action_references(root: Path) -> Iterable[tuple[Path, int, str, str, str | None]]:
    """Yield external Action references in workflow and composite Action files."""
    for path in sorted(root.joinpath(".github").rglob("*.y*ml")):
        if path.name == "action-versions.yml":
            continue
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            match = ACTION_PATTERN.match(line)
            if not match:
                continue
            action, revision, comment = match.groups()
            if not action.startswith("./"):
                yield path, line_number, action, revision, comment


def validate(root: Path) -> list[str]:
    """Return all manifest and workflow reference validation errors."""
    manifest_path = root / ".github" / "action-versions.yml"
    try:
        manifest = parse_manifest(manifest_path)
    except (OSError, ValueError) as error:
        return [str(error)]

    errors: list[str] = []
    referenced_actions: set[str] = set()
    for path, line_number, action, revision, comment in iter_action_references(root):
        display_path = path.relative_to(root)
        entry = manifest.get(action)
        if entry is not None:
            referenced_actions.add(action)

        if not SHA_PATTERN.fullmatch(revision):
            errors.append(
                f"{display_path}:{line_number}: {action} must use a 40-character SHA"
            )
            continue

        if entry is None:
            errors.append(
                f"{display_path}:{line_number}: {action} is missing from "
                ".github/action-versions.yml"
            )
            continue

        if revision != entry["sha"]:
            errors.append(
                f"{display_path}:{line_number}: {action} SHA does not match the manifest"
            )

        if comment != entry["ref"]:
            errors.append(
                f"{display_path}:{line_number}: {action} ref comment does not match "
                "the manifest"
            )

    for action in sorted(set(manifest) - referenced_actions):
        errors.append(
            f".github/action-versions.yml: {action} is not referenced by a workflow "
            "or composite Action"
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repository root to validate",
    )
    args = parser.parse_args()

    errors = validate(args.root.resolve())
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    print("Action version manifest is consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
