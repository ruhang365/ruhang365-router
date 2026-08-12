from __future__ import annotations

import json
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = (
    REPO_ROOT
    / "skills"
    / "ruhang365-router"
    / "catalog"
    / "catalog.json"
)
EXPORT_SCRIPT = REPO_ROOT / "scripts" / "export_rhzl_import.py"


def load_exporter():
    spec = importlib.util.spec_from_file_location("export_rhzl_import", EXPORT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load RHZL exporter")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RhzlImportContractTests(unittest.TestCase):
    def test_exports_deterministic_read_only_rows_for_existing_runtime_indexes(self):
        command = [
            sys.executable,
            str(EXPORT_SCRIPT),
            "--catalog",
            str(CATALOG),
        ]
        first = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        second = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)

        payload = json.loads(first.stdout)
        self.assertFalse(payload["execution"]["writePerformed"])
        self.assertEqual(
            payload["source"]["source_key"],
            "github:ruhang365/ruhang365-router",
        )
        self.assertTrue(payload["indexes"]["scenarios"])
        self.assertTrue(payload["indexes"]["knowledge_base"])
        self.assertTrue(payload["indexes"]["skills"])

        workflow = next(
            row
            for row in payload["indexes"]["knowledge_base"]
            if row["content_type"] == "workflow"
        )
        self.assertEqual(
            workflow["source_uid"],
            "github:ruhang365/ruhang365-router:r365.workflow.creator-ip-industry-cognition@1.0.0",
        )
        self.assertEqual(workflow["source_kind"], "github")
        self.assertEqual(workflow["review_status"], "approved")
        self.assertEqual(workflow["source_repo"], "ruhang365/ruhang365-router")
        self.assertTrue(workflow["content"])
        self.assertEqual(workflow["status"], "published")
        self.assertIsNone(workflow["internal_body"])

        skill = payload["indexes"]["skills"][0]
        self.assertEqual(skill["creator_ref"], "official:ruhang365")
        self.assertNotIn("creator_id", skill)
        self.assertEqual(skill["pricing_mode"], "free")
        self.assertEqual(skill["price"], 0)
        self.assertFalse(skill["is_featured"])
        self.assertNotIn("registry", skill)

        serialized = first.stdout.casefold()
        self.assertNotIn("user_id", serialized)
        self.assertNotIn("owner_user_id", serialized)
        self.assertNotIn("result_id", serialized)

    def test_does_not_publish_archived_or_stale_catalog_items(self):
        exporter = load_exporter()
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        scenario = next(item for item in catalog["items"] if item["type"] == "scenario")
        scenario["status"] = "archived"
        another = dict(scenario)
        another["id"] = "r365.scenario.stale-fixture"
        another["slug"] = "stale-fixture"
        another["status"] = "current"
        another["governance"] = dict(scenario["governance"])
        another["governance"]["stale"] = True
        catalog["items"] = [scenario, another]

        payload = exporter.export_contract(catalog)

        self.assertEqual(payload["indexes"]["scenarios"], [])


if __name__ == "__main__":
    unittest.main()
