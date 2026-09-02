#!/usr/bin/env python3
# Copyright 2026 The Lynx Authors. All rights reserved.
# Licensed under the Apache License Version 2.0 that can be found in the
# LICENSE file in the root directory of this source tree.

import tempfile
import unittest
from pathlib import Path

from check_action_versions import validate


MANIFEST = """\
schema_version: 1
node_version_file: '.node-version'
actions:
  actions/checkout:
    ref: 'v6'
    sha: 'd23441a48e516b6c34aea4fa41551a30e30af803'
"""


class CheckActionVersionsTest(unittest.TestCase):
    def create_repository(self, workflow: str) -> Path:
        root = Path(self.temporary_directory.name)
        github_dir = root / ".github"
        workflows_dir = github_dir / "workflows"
        workflows_dir.mkdir(parents=True)
        (github_dir / "action-versions.yml").write_text(MANIFEST, encoding="utf-8")
        (workflows_dir / "ci.yml").write_text(workflow, encoding="utf-8")
        return root

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_accepts_matching_external_action_and_local_action(self) -> None:
        root = self.create_repository(
            """\
steps:
  - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6
  - uses: ./local-action
"""
        )

        self.assertEqual(validate(root), [])

    def test_rejects_floating_tag(self) -> None:
        root = self.create_repository(
            """\
steps:
  - uses: actions/checkout@v6
"""
        )

        self.assertEqual(
            validate(root),
            [
                ".github/workflows/ci.yml:2: actions/checkout must use a "
                "40-character SHA"
            ],
        )

    def test_rejects_unregistered_action(self) -> None:
        root = self.create_repository(
            """\
steps:
  - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6
  - uses: actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38 # v6
"""
        )

        self.assertEqual(
            validate(root),
            [
                ".github/workflows/ci.yml:3: actions/setup-node is missing from "
                ".github/action-versions.yml"
            ],
        )

    def test_rejects_mismatched_ref_comment(self) -> None:
        root = self.create_repository(
            """\
steps:
  - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v5
"""
        )

        self.assertEqual(
            validate(root),
            [
                ".github/workflows/ci.yml:2: actions/checkout ref comment does "
                "not match the manifest"
            ],
        )


if __name__ == "__main__":
    unittest.main()
