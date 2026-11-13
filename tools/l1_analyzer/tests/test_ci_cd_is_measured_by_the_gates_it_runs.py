"""L1.10 counts the gate categories a repository's pipelines cover, not the files they fill.

The canon counted pipeline definition files, `>=5` Healthy and `1-4` Not Healthy. One well-staged
pipeline that builds, tests, lints, scans, deploys and smoke-tests the deployment read 1 and Not
Healthy, and the same gates split over five files read Healthy. File count rewards splitting, not
coverage.

This fork counts six categories, each once however many files, stages or jobs carry it: build,
test, static checks, security scan, deploy and post-deploy verification. The bands keep the
canon's numbers on the new unit: 5 or 6 Healthy, 1-4 Not Healthy, 0 Slop.

A step counts for what it RUNS, matched against one declared table of commands, Azure tasks and
GitHub actions. A job or stage name is never read: a display name is prose, and "Run tests" over
an `echo` runs nothing. An unknown command counts for nothing rather than being guessed, and an
echo-only step counts for nothing, which is the spec's echo-only placeholder pipeline.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from l1_analyzer.indicators import compute_config_indicators

_ALL_SIX = """on: push
jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npx tsc --noEmit
      - run: npx vitest run
      - run: npm audit --audit-level=high
      - run: npx vite build
  deploy:
    runs-on: ubuntu-latest
    steps:
      - run: npx wrangler deploy
      - run: npx playwright test --project=smoke
"""


def _l110(tmp_path: pathlib.Path, files: dict[str, str]) -> dict:
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text)
    return compute_config_indicators(tmp_path)["L1.10"]


def test_one_pipeline_covering_every_gate_is_healthy(tmp_path):
    row = _l110(tmp_path, {".github/workflows/ci.yml": _ALL_SIX})
    assert (row["value"], row["band"]) == (6, "Healthy")


def test_five_files_running_one_gate_read_one_category(tmp_path):
    files = {f".github/workflows/w{n}.yml": "on: push\njobs:\n  t:\n    steps:\n      - run: npx vitest run\n"
             for n in range(5)}
    row = _l110(tmp_path, files)
    assert (row["value"], row["band"]) == (1, "Not Healthy")


def test_an_echo_only_pipeline_is_slop(tmp_path):
    row = _l110(tmp_path, {".github/workflows/ci.yml": (
        "on: push\njobs:\n  build:\n    name: Build and test\n    steps:\n"
        "      - name: Run tests\n        run: echo \"tests passed\"\n"
        "      - run: |\n          # vitest would run here\n          echo vitest\n")})
    assert (row["value"], row["band"]) == (0, "Slop")


def test_a_step_counts_for_its_command_and_never_its_name(tmp_path):
    row = _l110(tmp_path, {".github/workflows/ci.yml": (
        "on: push\njobs:\n  test:\n    name: Unit tests\n    steps:\n"
        "      - name: Lint, test and scan\n        run: ./scripts/check.sh\n")})
    assert (row["value"], row["band"]) == (0, "Slop")


def test_no_pipeline_at_all_is_slop_and_says_where_it_looked(tmp_path):
    row = _l110(tmp_path, {})
    assert (row["value"], row["band"]) == (0, "Slop")
    assert ".github/workflows" in row["details"] and "Jenkinsfile" in row["details"]


def test_a_package_script_is_read_for_what_it_runs(tmp_path):
    files = {
        "package.json": json.dumps({"scripts": {"lint:strict": "oxlint --deny-warnings", "check": "pnpm lint:strict",
                                                "build:prod": "cross-env MODE=prod astro build"}}),
        ".github/workflows/ci.yml": ("on: push\njobs:\n  c:\n    steps:\n      - run: pnpm run check\n"
                                     "      - run: pnpm build:prod\n"),
    }
    row = _l110(tmp_path, files)
    assert row["value"] == 2
    assert "build" in row["details"] and "static checks" in row["details"]


_AZURE = """trigger: none
stages:
  - stage: Test
    jobs:
      - job: Checks
        steps:
          - template: templates/check.yml
            parameters:
              script: lint:strict
  - stage: Deploy
    jobs:
      - deployment: Production
        environment: production
        strategy:
          runOnce:
            deploy:
              steps:
                - template: templates/smoke.yml
                  parameters:
                    baseUrl: https://example.com
"""


def test_azure_templates_are_followed_with_their_parameters(tmp_path):
    files = {
        "package.json": json.dumps({"scripts": {"lint:strict": "eslint .", "e2e:smoke": "playwright test --grep @smoke"}}),
        "pipelines/azure-pipelines.yml": _AZURE,
        "pipelines/templates/check.yml": ("parameters:\n  - name: script\n    type: string\n"
                                          "steps:\n  - script: pnpm run ${{ parameters.script }}\n"),
        "pipelines/templates/smoke.yml": ("parameters:\n  - name: baseUrl\n    type: string\n"
                                          "steps:\n  - script: CI=true pnpm run e2e:smoke\n"
                                          "    env:\n      BASE_URL: ${{ parameters.baseUrl }}\n"),
    }
    row = _l110(tmp_path, files)
    assert row["value"] == 3
    for said in ("static checks (pipelines/templates/check.yml)", "deploy (pipelines/azure-pipelines.yml)",
                 "post-deploy verification (pipelines/templates/smoke.yml)", "2 templates"):
        assert said in row["details"]


def test_a_browser_run_is_a_test_until_it_targets_a_deployment(tmp_path):
    row = _l110(tmp_path, {".github/workflows/ci.yml": (
        "on: push\njobs:\n  e2e:\n    steps:\n      - run: npx playwright test\n")})
    assert row["value"] == 1 and "test (.github/workflows/ci.yml)" in row["details"]
    assert "post-deploy" not in row["details"].split("missing")[0]


@pytest.mark.parametrize("step", [
    "uses: github/codeql-action/analyze@v3",
    "run: npx --yes osv-scanner -r .",
    "uses: gitleaks/gitleaks-action@v2",
])
def test_security_scans_are_read_from_commands_and_actions(tmp_path, step):
    row = _l110(tmp_path, {".github/workflows/sec.yml": f"on: push\njobs:\n  s:\n    steps:\n      - {step}\n"})
    assert row["value"] == 1 and "security scan" in row["details"].split("missing")[0]


def test_an_azure_advanced_security_task_is_a_security_scan(tmp_path):
    row = _l110(tmp_path, {"azure-pipelines.yml": (
        "steps:\n  - task: AdvancedSecurity-Codeql-Init@1\n  - task: AdvancedSecurity-Codeql-Analyze@1\n")})
    assert row["value"] == 1 and "security scan" in row["details"].split("missing")[0]


def test_gitlab_and_jenkins_are_read_by_the_same_table(tmp_path):
    files = {
        ".gitlab-ci.yml": ("stages: [test, deploy]\nunit:\n  script:\n    - pytest -q\n"
                           "release:\n  environment: production\n  script:\n    - ./deploy.sh\n"),
        "Jenkinsfile": "pipeline { stages { stage('Lint') { steps { sh 'ruff check .' } } } }\n",
    }
    row = _l110(tmp_path, files)
    assert row["value"] == 3
    assert "deploy (.gitlab-ci.yml)" in row["details"] and "static checks (Jenkinsfile)" in row["details"]


def test_the_details_name_what_is_missing(tmp_path):
    row = _l110(tmp_path, {".github/workflows/ci.yml": "on: push\njobs:\n  t:\n    steps:\n      - run: go test ./...\n"})
    assert "missing: build, static checks, security scan, deploy, post-deploy verification" in row["details"]
