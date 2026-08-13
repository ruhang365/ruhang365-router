from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import urllib.error


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_catalog.py"
MATCHER_MODULE = (
    REPO_ROOT
    / "skills"
    / "ruhang365-router"
    / "scripts"
    / "community_catalog.py"
)
SCHEMA = REPO_ROOT / "schemas" / "community-item.schema.json"


def governance(source_path: str) -> dict[str, object]:
    return {
        "source": {
            "kind": "owned",
            "url": (
                "https://github.com/ruhang365/ruhang365-router/blob/main/"
                f"{source_path}"
            ),
        },
        "license": {"spdx": "CC-BY-4.0", "attribution": "入行365"},
        "rights": {"status": "full"},
        "maintainers": ["ruhang365-maintainers"],
        "review": {"status": "approved", "reviewed_at": "2026-08-12"},
        "updated_at": "2026-08-12",
        "stale_after": "2027-02-12",
        "stale": False,
    }


def applicability(
    *,
    identities: list[str],
    goals: list[str],
    deliverables: list[str],
    constraints: list[str] | None = None,
    excluded_constraints: list[str] | None = None,
) -> dict[str, list[str]]:
    return {
        "identities": identities,
        "goals": goals,
        "experience_levels": ["beginner"],
        "constraints": constraints or [],
        "excluded_constraints": excluded_constraints or [],
        "deliverables": deliverables,
    }


def common_asset(
    asset_type: str,
    slug: str,
    *,
    identities: list[str] | None = None,
    goals: list[str] | None = None,
    deliverables: list[str] | None = None,
) -> dict[str, object]:
    source_path = f"content/{asset_type}s/{slug}.json"
    return {
        "schema_version": "1.0.0",
        "id": f"r365.{asset_type}.{slug}",
        "type": asset_type,
        "slug": slug,
        "version": "1.0.0",
        "title": slug.replace("-", " "),
        "summary": f"Public {asset_type} fixture for {slug}.",
        "status": "current",
        "governance": governance(source_path),
        "applicability": applicability(
            identities=identities or ["local-business"],
            goals=goals or ["content-growth"],
            deliverables=deliverables or ["weekly-content-kit"],
            constraints=["free-only"],
        ),
        "completion_criteria": ["A usable result exists."],
        "tags": [asset_type, "fixture"],
        "match_terms": ["咖啡店", "门店", "一周内容"],
    }


def valid_assets() -> list[dict[str, object]]:
    scenario = common_asset("scenario", "weekly-content-kit")
    scenario.update(
        {
            "deliverable": "7 topics, one draft, and one cover direction.",
            "next_intent": "writing",
            "workflow_ids": ["r365.workflow.weekly-content-kit"],
        }
    )

    workflow = common_asset("workflow", "weekly-content-kit")
    workflow.update(
        {
            "goal": "Create a usable weekly content kit.",
            "estimated_minutes": 60,
            "scenario_ids": ["r365.scenario.weekly-content-kit"],
            "nodes": [
                {
                    "id": "frame-audience",
                    "title": "Frame the audience",
                    "action": "Choose one audience and one business goal.",
                    "resource_ids": ["r365.resource.writing-helper"],
                    "prompt_ids": [],
                    "completion_criteria": ["Audience and goal are explicit."],
                }
            ],
        }
    )

    resource = common_asset("resource", "writing-helper")
    resource.update(
        {
            "resource_kind": "skill",
            "purpose": "Turn a verified outline into natural Chinese copy.",
            "capabilities": ["writing"],
            "repository_url": "https://github.com/ruhang365/writing-helper",
            "source_url": "https://github.com/ruhang365/writing-helper",
            "resource_version": "1.0.0",
        }
    )
    return [resource, workflow, scenario]


def write_assets(root: Path, assets: list[dict[str, object]]) -> None:
    for directory_name in ("scenarios", "workflows", "resources", "prompts"):
        (root / "content" / directory_name).mkdir(parents=True, exist_ok=True)
    for asset in assets:
        directory = root / "content" / f"{asset['type']}s"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{asset['slug']}.json"
        path.write_text(
            json.dumps(asset, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def run_builder(root: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(BUILD_SCRIPT),
            "--content-root",
            str(root / "content"),
            "--schema",
            str(SCHEMA),
            "--catalog-version",
            "1.0.0",
            "--output",
            str(output),
            "--write",
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def load_matcher():
    spec = importlib.util.spec_from_file_location("community_catalog", MATCHER_MODULE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load community catalog matcher")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CatalogBuildTests(unittest.TestCase):
    def test_builds_a_deterministic_sorted_catalog(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "catalog.json"
            write_assets(root, valid_assets())

            first = run_builder(root, output)
            first_bytes = output.read_bytes() if output.exists() else b""
            second = run_builder(root, output)

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(first_bytes, output.read_bytes())

            catalog = json.loads(first_bytes)
            self.assertEqual(catalog["schemaVersion"], "1.0.0")
            self.assertEqual(catalog["catalogVersion"], "1.0.0")
            self.assertEqual(
                [item["id"] for item in catalog["items"]],
                [
                    "r365.scenario.weekly-content-kit",
                    "r365.workflow.weekly-content-kit",
                    "r365.resource.writing-helper",
                ],
            )
            self.assertEqual(len(catalog["contentDigest"]), 64)
            self.assertNotIn("generatedAt", catalog)

    def test_catalog_digest_is_independent_of_the_build_location(self):
        with tempfile.TemporaryDirectory() as first_directory, tempfile.TemporaryDirectory() as second_directory:
            first_root = Path(first_directory)
            second_root = Path(second_directory)
            write_assets(first_root, valid_assets())
            write_assets(second_root, valid_assets())

            first = run_builder(first_root, first_root / "catalog.json")
            second = run_builder(second_root, second_root / "catalog.json")

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(
                (first_root / "catalog.json").read_bytes(),
                (second_root / "catalog.json").read_bytes(),
            )

    def test_check_mode_rejects_a_stale_generated_catalog(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "catalog.json"
            write_assets(root, valid_assets())
            built = run_builder(root, output)
            self.assertEqual(built.returncode, 0, built.stderr)
            output.write_text("{}\n", encoding="utf-8")

            checked = subprocess.run(
                [
                    sys.executable,
                    str(BUILD_SCRIPT),
                    "--content-root",
                    str(root / "content"),
                    "--schema",
                    str(SCHEMA),
                    "--catalog-version",
                    "1.0.0",
                    "--output",
                    str(output),
                    "--check",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("stale", checked.stderr.casefold())

    def test_rejects_missing_governance_duplicate_ids_and_dangling_references(self):
        mutations: list[tuple[str, str, object]] = [
            ("missing license", "license", None),
            ("missing rights", "rights", None),
            ("dangling reference", "workflow_ids", ["r365.workflow.missing"]),
            ("internal path", "source_url", "file:///private/example.md"),
            ("sensitive field", "user_id", "00000000-0000-0000-0000-000000000000"),
        ]

        for label, field, value in mutations:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory)
                assets = valid_assets()
                if field in {"license", "rights"}:
                    del assets[2]["governance"][field]  # type: ignore[index]
                elif field == "workflow_ids":
                    assets[2][field] = value
                elif field == "user_id":
                    assets[0][field] = value
                else:
                    assets[0][field] = value
                write_assets(root, assets)

                result = run_builder(root, root / "catalog.json")

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(label.split()[0], result.stderr.casefold())

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            assets = valid_assets()
            duplicate = dict(assets[2])
            duplicate["slug"] = "duplicate-file"
            assets.append(duplicate)
            write_assets(root, assets)

            result = run_builder(root, root / "catalog.json")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate", result.stderr.casefold())


class CatalogMatcherTests(unittest.TestCase):
    def test_online_catalog_request_contains_no_profile_or_private_data(self):
        matcher = load_matcher()
        snapshot = matcher.load_catalog()
        requests = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self):
                return json.dumps(snapshot, ensure_ascii=False).encode("utf-8")

        def opener(request, timeout):
            requests.append((request, timeout))
            return Response()

        resolved = matcher.resolve_catalog(
            "https://rhzl.ruhang365.cn",
            timeout=3,
            opener=opener,
        )

        self.assertEqual(resolved["source"], "online")
        self.assertEqual(len(requests), 1)
        request, timeout = requests[0]
        self.assertEqual(request.full_url, "https://rhzl.ruhang365.cn/api/community/catalog")
        self.assertEqual(timeout, 3)
        serialized = json.dumps(dict(request.header_items()), ensure_ascii=False).casefold()
        for forbidden in ("identity", "goal", "constraint", "deliverable", "cookie", "authorization"):
            self.assertNotIn(forbidden, serialized)

    def test_catalog_network_and_contract_failures_use_the_stable_snapshot(self):
        matcher = load_matcher()
        snapshot = matcher.load_catalog()

        failures = {
            "timeout": lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError()),
            "5xx": lambda request, *_args, **_kwargs: (_ for _ in ()).throw(
                urllib.error.HTTPError(request.full_url, 503, "down", {}, None)
            ),
            "invalid_json": lambda *_args, **_kwargs: _Response(b"not json"),
            "unknown_schema": lambda *_args, **_kwargs: _Response(
                json.dumps({**snapshot, "schemaVersion": "9.0.0"}).encode()
            ),
            "tampered_digest": lambda *_args, **_kwargs: _Response(
                json.dumps({**snapshot, "contentDigest": "0" * 64}).encode()
            ),
        }

        for label, opener in failures.items():
            with self.subTest(label=label):
                resolved = matcher.resolve_catalog(
                    "https://rhzl.ruhang365.cn",
                    timeout=1,
                    opener=opener,
                )
                self.assertEqual(resolved["source"], "offline_fallback")
                self.assertEqual(resolved["catalog"], snapshot)
                self.assertTrue(resolved["warning"])

    def test_online_and_snapshot_catalogs_use_the_identical_matcher(self):
        matcher = load_matcher()
        snapshot = matcher.load_catalog()
        online = matcher.resolve_catalog(
            "https://rhzl.ruhang365.cn",
            opener=lambda *_args, **_kwargs: _Response(
                json.dumps(snapshot, ensure_ascii=False).encode("utf-8")
            ),
        )
        offline = matcher.resolve_catalog(
            "https://rhzl.ruhang365.cn",
            offline=True,
        )
        profile = {
            "identity": "local-business",
            "goal": "content-growth",
            "experience": "beginner",
            "constraints": ["free-only"],
            "deliverable": "weekly-content-kit",
        }

        self.assertEqual(
            matcher.match_catalog(online["catalog"], profile),
            matcher.match_catalog(offline["catalog"], profile),
        )

    def test_matches_all_asset_types_from_profile_fields(self):
        matcher = load_matcher()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "catalog.json"
            write_assets(root, valid_assets())
            built = run_builder(root, output)
            self.assertEqual(built.returncode, 0, built.stderr)
            catalog = matcher.load_catalog(output)

        result = matcher.match_catalog(
            catalog,
            {
                "identity": "local-business",
                "goal": "为咖啡店做一周获客内容",
                "experience": "beginner",
                "constraints": ["free-only"],
                "deliverable": "weekly-content-kit",
            },
            limit_per_type=3,
        )

        self.assertEqual(
            result["scenarios"][0]["id"],
            "r365.scenario.weekly-content-kit",
        )
        self.assertEqual(
            result["workflows"][0]["id"],
            "r365.workflow.weekly-content-kit",
        )
        self.assertEqual(
            result["resources"][0]["id"],
            "r365.resource.writing-helper",
        )
        self.assertIn("identity", result["scenarios"][0]["matchReasons"])
        self.assertIn("deliverable", result["scenarios"][0]["matchReasons"])

    def test_excluded_constraint_removes_an_otherwise_relevant_item(self):
        matcher = load_matcher()
        assets = valid_assets()
        blocked = assets[2]
        blocked["applicability"]["excluded_constraints"] = ["offline-only"]  # type: ignore[index]
        catalog = {
            "schemaVersion": "1.0.0",
            "catalogVersion": "1.0.0",
            "contentDigest": "fixture",
            "items": assets,
        }

        result = matcher.match_catalog(
            catalog,
            {
                "identity": "local-business",
                "goal": "咖啡店一周内容",
                "experience": "beginner",
                "constraints": ["offline-only"],
                "deliverable": "weekly-content-kit",
            },
        )

        self.assertEqual(result["scenarios"], [])

    def test_recommendation_weight_does_not_create_an_unrelated_match(self):
        matcher = load_matcher()
        scenario = valid_assets()[2]
        scenario["recommendation_weight"] = 20
        catalog = {
            "schemaVersion": "1.0.0",
            "catalogVersion": "1.0.0",
            "contentDigest": "fixture",
            "items": [scenario],
        }

        result = matcher.match_catalog(
            catalog,
            {
                "identity": "job-seeker",
                "goal": "prepare interview evidence",
                "experience": "advanced",
                "constraints": ["offline-only"],
                "deliverable": "interview-scorecard",
            },
        )

        self.assertEqual(result["scenarios"], [])

    def test_catalog_loader_rejects_tampered_content(self):
        matcher = load_matcher()
        catalog = {
            "schemaVersion": "1.0.0",
            "catalogVersion": "1.0.0",
            "contentDigest": "0" * 64,
            "items": valid_assets(),
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "catalog.json"
            path.write_text(json.dumps(catalog), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "contentDigest mismatch"):
                matcher.load_catalog(path)

    def test_archived_or_stale_items_are_never_recommended(self):
        matcher = load_matcher()
        for state in ("archived", "stale"):
            with self.subTest(state=state):
                scenario = valid_assets()[2]
                if state == "archived":
                    scenario["status"] = "archived"
                else:
                    scenario["governance"]["stale"] = True  # type: ignore[index]
                catalog = {
                    "schemaVersion": "1.0.0",
                    "catalogVersion": "1.0.0",
                    "contentDigest": "fixture",
                    "items": [scenario],
                }

                result = matcher.match_catalog(
                    catalog,
                    {
                        "identity": "local-business",
                        "goal": "content-growth",
                        "experience": "beginner",
                        "constraints": ["free-only"],
                        "deliverable": "weekly-content-kit",
                    },
                )

                self.assertEqual(result["scenarios"], [])


if __name__ == "__main__":
    unittest.main()


class _Response:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.body
