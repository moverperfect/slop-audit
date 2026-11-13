"""L1.10 counted only GitHub's workflows, and the canon names more than GitHub.

spec/03-layer1-indicators.md defined L1.10 as the "count of CI/CD pipeline definition files
(`.github/workflows/*.yml`, `.gitlab-ci.yml`, `Jenkinsfile`, etc.)". The reader looked in
`.github/workflows` and nowhere else, so a GitLab or Jenkins project read zero pipelines and
banded Slop, and so did an Azure DevOps project: an Astro site built, tested and deployed by
Azure Pipelines on every change was told every merge was "a manual act of faith".

Azure Pipelines has no fixed path. A definition is `azure-pipelines*.yml` by convention, or a
YAML file under a `pipelines/` or `.azure-pipelines/` directory that opens a pipeline at its
top level. Those directories also hold TEMPLATES, steps and jobs another pipeline includes
with `template:`, and a template is a piece of a pipeline rather than a definition of one. On
the Astro site, 20 of the 22 YAML files under `pipelines/` are templates. They are disclosed
and not counted as pipelines: each is read where a definition includes it.

Since 2026-11-13 L1.10 counts the gate categories those pipelines run rather than the files
(test_ci_cd_is_measured_by_the_gates_it_runs.py). These tests keep the part that is still about
finding: every system's definitions are read, and templates are followed, not counted.
"""

from __future__ import annotations

from pathlib import Path

from l1_analyzer import ci_pipelines, indicators


def _write(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


def _l110(root: Path):
    return indicators.compute_config_indicators(root)["L1.10"]


def test_an_azure_pipeline_is_counted_and_the_templates_it_includes_are_not(tmp_path):
    repo = _write(tmp_path, {
        "pipelines/azure-pipelines.deployment.yml": (
            "trigger:\n  - main\nstages:\n  - stage: Build\n    jobs:\n"
            "      - template: templates/build-job.yml\n"),
        "pipelines/azure-pipelines.tagging.yml": (
            "trigger: none\njobs:\n  - job: Tag\n    steps:\n"
            "      - template: /pipelines/templates/tagging.yml\n"),
        "pipelines/templates/build-job.yml": "parameters:\n  - name: env\njobs:\n  - job: Build\n",
        "pipelines/templates/tagging.yml": "steps:\n  - script: echo tag\n",
    })
    row = _l110(repo)
    # Both definitions are read and both templates followed. Neither runs a gate: one template
    # holds an empty job and the other only echoes, so nothing is counted.
    assert row["value"] == 0, row
    assert "Read from 2 pipeline definitions" in row["details"], row["details"]
    assert "2 templates" in row["details"], row["details"]


def test_the_conventional_azure_file_name_is_a_pipeline_wherever_it_sits(tmp_path):
    repo = _write(tmp_path, {
        "azure-pipelines.yml": "trigger:\n  - main\nsteps:\n  - script: npm test\n",
        ".azure-pipelines/nightly.yaml": "schedules:\n  - cron: '0 3 * * *'\nsteps:\n  - script: x\n",
        "pipelines/variables.yml": "variables:\n  node: 22\n",
    })
    row = _l110(repo)
    # Two definitions: `npm test` is a test, and `x` runs nothing the table knows.
    assert row["value"] == 1, row
    assert "Read from 2 pipeline definitions" in row["details"], row["details"]


def test_the_two_files_the_canon_names_besides_github_are_counted(tmp_path):
    repo = _write(tmp_path, {
        ".gitlab-ci.yml": "test:\n  script: make test\n",
        "Jenkinsfile": "pipeline { agent any\n stages { stage('t') { steps { sh 'make test' } } } }\n",
    })
    row = _l110(repo)
    assert row["value"] == 1, row
    assert "test (.gitlab-ci.yml, Jenkinsfile)" in row["details"], row["details"]


def test_five_definitions_that_run_nothing_are_slop(tmp_path):
    """Five files read Healthy when L1.10 counted files. They run no gate, which is what the
    count could not see, so they read 0 and Slop."""
    repo = _write(tmp_path, {
        **{f".github/workflows/w{n}.yml": "on: push\njobs: {}\n" for n in range(3)},
        ".gitlab-ci.yml": "test:\n  script: make\n",
        "azure-pipelines.yml": "trigger:\n  - main\nsteps: []\n",
    })
    row = _l110(repo)
    assert (row["value"], row["band"]) == (0, "Slop")
    assert "Read from 5 pipeline definitions" in row["details"], row["details"]


def test_a_repository_with_none_names_every_place_it_looked(tmp_path):
    row = _l110(tmp_path)
    assert (row["value"], row["band"]) == (0, "Slop")
    for place in (".github/workflows", ".gitlab-ci.yml", "Jenkinsfile", "Azure Pipelines"):
        assert place in row["details"], row["details"]


def test_a_template_resolution_is_a_question_about_paths_alone():
    """The decision needs no files, so it is exercised as strings."""
    definitions, templates = ci_pipelines.azure_pipeline_definitions({
        "ci/azure-pipelines.yml": "trigger: [main]\nsteps:\n  - template: ../pipelines/steps.yml\n",
        "pipelines/steps.yml": "steps:\n  - script: x\n",
        "pipelines/remote.yml": "trigger: [main]\nsteps:\n  - template: steps.yml@shared\n",
    })
    assert definitions == ["ci/azure-pipelines.yml", "pipelines/remote.yml"]
    assert templates == ["pipelines/steps.yml"]
