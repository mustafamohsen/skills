#!/usr/bin/env python3
"""Black-box contract tests for the catalog linter."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
LINTER = PACKAGE_ROOT / "scripts" / "afcli_schema_lint.py"
EXAMPLE_CATALOG = PACKAGE_ROOT / "examples" / "command_catalog.example.json"


class CatalogLinterContractTests(unittest.TestCase):
    def run_linter(self, catalog: Any) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog_path = Path(temp_dir) / "catalog.json"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(LINTER), str(catalog_path)],
                text=True,
                capture_output=True,
                check=False,
            )

    def test_non_object_catalog_returns_structured_invalid_catalog_error(self) -> None:
        result = self.run_linter([])

        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["error"]["code"], "CATALOG_INVALID")

    def test_invalid_nested_type_returns_structured_invalid_catalog_error(self) -> None:
        catalog = json.loads(EXAMPLE_CATALOG.read_text(encoding="utf-8"))
        catalog["commands"][-1]["safety"] = "yes"

        result = self.run_linter(catalog)

        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["error"]["code"], "CATALOG_INVALID")
        self.assertEqual(envelope["error"]["details"]["errors"][0]["path"], "$.commands[5].safety")

    def test_null_command_collection_is_structurally_invalid(self) -> None:
        catalog = json.loads(EXAMPLE_CATALOG.read_text(encoding="utf-8"))
        catalog["commands"] = None

        result = self.run_linter(catalog)

        self.assertEqual(result.returncode, 2)
        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["error"]["code"], "CATALOG_INVALID")
        self.assertEqual(envelope["error"]["details"]["errors"][0]["path"], "$.commands")

    def test_extension_metadata_remains_available_to_catalogs(self) -> None:
        catalog = json.loads(EXAMPLE_CATALOG.read_text(encoding="utf-8"))
        catalog["commands"][-1]["safety"]["future_policy"] = {"mode": "strict"}

        result = self.run_linter(catalog)

        self.assertEqual(result.returncode, 0)
        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "success")

    def test_shipped_example_completes_semantic_linting(self) -> None:
        result = subprocess.run(
            [sys.executable, str(LINTER), str(EXAMPLE_CATALOG), "--fail-on", "warning"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "success")
        self.assertEqual(envelope["data"]["summary"]["issue_count"], 0)

    def test_unexpected_runtime_failure_returns_structured_internal_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog_path = Path(temp_dir) / "catalog.json"
            catalog_path.write_text(EXAMPLE_CATALOG.read_text(encoding="utf-8"), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(LINTER), str(catalog_path), "--out", temp_dir],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 13)
        self.assertNotIn("Traceback", result.stderr)
        envelope = json.loads(result.stdout)
        self.assertEqual(envelope["status"], "error")
        self.assertEqual(envelope["error"]["code"], "INTERNAL_ERROR")


if __name__ == "__main__":
    unittest.main()
