"""L1.10's reading: which gate categories a repository's CI/CD pipelines cover.

THE UNIT IS THE GATE, NOT THE FILE. The canon counted pipeline definition files, `>=5` Healthy and
`1-4` Not Healthy. One well-staged pipeline that builds, tests, lints, scans, deploys and checks
the deployment read 1 and Not Healthy, and the same gates split over five files read Healthy.
File count rewards splitting, not coverage. This fork counts six categories, each once however
many files, stages or jobs carry it (research/amendments/amendment-2026-11-13-l1-10-gate-categories.md):

  build                     compiles or bundles the application
  test                      runs an automated test suite
  static checks             lint, type check, format check
  security scan             dependency audit, SAST, secret scanning, container or IaC scanning
  deploy                    deploys to an environment
  post-deploy verification  smoke, end-to-end, health or visual checks against a deployed environment

The bands keep the canon's numbers on the new unit: 5 or 6 Healthy, 1-4 Not Healthy, 0 Slop.

A STEP COUNTS FOR WHAT IT RUNS. Each step's command is matched against one declared table below:
shell commands, Azure Pipelines tasks and GitHub actions, per category. A package-manager call
to a `package.json` script (`pnpm run lint:strict`) is read as the script it runs (`oxlint`).
- Names are never read. A job, stage or step name is prose: "Run tests" over an `echo` runs
  nothing, and a step that runs a test suite counts whatever it is called.
- A command the table does not know counts for nothing rather than being guessed.
- Comments and echo-only lines are dropped before matching, so an echo-only step, the canon's
  "echo-only placeholder pipeline", counts for nothing.

DEPLOY is also read from structure, where a system declares a deployment: an Azure `deployment:`
job with an `environment:`, and a GitHub or GitLab job with an `environment:`, which each
system documents as the environment the job deploys to.

POST-DEPLOY VERIFICATION is a browser, end-to-end, load or health check run against a deployed
environment. It counts as one when a deploy ran earlier in the same job, or when the step is
handed a deployed address: a parameter, variable or env value that is an `http(s)://` URL or
whose name ends in `url`. The same browser run with neither is a test.

What the reader follows: Azure `template:` references, with the parameters they pass and the
template's defaults, at every level; GitHub local composite actions; GitLab `include: local:`
and `extends:`. A template in another repository (`x.yml@repo`) cannot be read and is disclosed.
"""

from __future__ import annotations

import json
import posixpath
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import TypedDict

import yaml

from l1_analyzer import ci_pipelines
from l1_analyzer.boundary import text_or_empty
from l1_analyzer.indicators import band
from l1_analyzer.panel import L1Result

CATEGORIES = ("build", "test", "static checks", "security scan", "deploy", "post-deploy verification")

# THE TABLE. One place, per category: shell commands as regular expressions over a command line,
# Azure Pipelines task names (lowercase, without the `@version`), and GitHub action prefixes
# (lowercase `owner/name`, without the `@ref`). To teach the reader a tool, add it here.
# Conventional entry points count like the tools they stand for: `npm test` is in the table when
# no package.json script resolves it, and `make test`, `make check` (GNU's name for the self-tests)
# and `make lint` are, because a Makefile target is the same convention a package script is.
COMMANDS: dict[str, tuple[str, ...]] = {
    "build": (
        r"astro build", r"vite build", r"next build", r"nuxi? build", r"ng build", r"svelte-kit build",
        r"remix (?:vite:)?build", r"webpack", r"rollup (?:-c|--config)", r"esbuild", r"tsup",
        r"parcel build", r"turbo (?:run )?build", r"nx (?:run-many [^\n]*build|build)",
        r"tsc(?![^\n]*--noemit)(?=\s|$)", r"go build", r"cargo build", r"dotnet (?:build|publish)",
        r"msbuild", r"mvnw?\b[^\n]*\b(?:package|install|verify)", r"gradlew?\b[^\n]*\b(?:build|assemble)",
        r"docker (?:buildx )?build", r"python -m build", r"poetry build", r"hugo", r"jekyll build",
    ),
    "test": (
        r"vitest", r"jest", r"mocha", r"pytest", r"python -m (?:pytest|unittest)", r"go test",
        r"cargo (?:test|nextest)", r"dotnet test", r"(?:npm|yarn|pnpm|bun) test", r"bun test",
        r"deno test", r"mvnw?\b[^\n]*\btest\b", r"gradlew?\b[^\n]*\btest\b", r"rspec", r"rake test",
        r"phpunit", r"ctest", r"tox", r"nox", r"make (?:test|check)",
    ),
    "static checks": (
        r"eslint", r"oxlint", r"biome (?:check|lint|ci)", r"tsc[^\n]*--noemit", r"vue-tsc",
        r"astro check", r"svelte-check", r"prettier[^\n]*(?:--check|--list-different|\s-[cl]\b)",
        r"oxfmt[^\n]*--check", r"dprint check", r"ruff", r"black[^\n]*--check", r"isort[^\n]*--check",
        r"flake8", r"pylint", r"mypy", r"pyright", r"golangci-lint", r"go vet", r"staticcheck",
        r"gofmt -l", r"cargo clippy", r"cargo fmt[^\n]*--check", r"rubocop", r"stylelint",
        r"markdownlint", r"hadolint", r"shellcheck", r"dotnet format[^\n]*--verify-no-changes",
        r"ktlint", r"spotless:?check", r"pre-commit run", r"make lint",
    ),
    "security scan": (
        r"(?:npm|pnpm|yarn|bun) (?:npm )?audit", r"snyk", r"trivy", r"grype", r"codeql", r"semgrep",
        r"gitleaks", r"trufflehog", r"osv-scanner", r"dependency-check", r"pip-audit",
        r"safety (?:check|scan)", r"bandit", r"cargo (?:audit|deny)", r"govulncheck", r"checkov",
        r"tfsec", r"kics", r"bundler?[- ]audit", r"brakeman", r"audit-ci",
    ),
    "deploy": (
        r"wrangler (?:deploy|publish|versions (?:upload|deploy)|pages deploy)",
        r"kubectl (?:apply|rollout|set image|replace|create)", r"helm (?:upgrade|install)",
        r"(?:terraform|tofu) apply", r"pulumi up",
        r"az (?:webapp (?:deploy|up)|functionapp deployment|containerapp (?:up|update)|deployment group create)",
        r"aws cloudformation deploy", r"sam deploy", r"cdk deploy", r"(?:serverless|sls) deploy",
        r"vercel (?:deploy|--prod)", r"netlify deploy", r"firebase deploy", r"fly(?:ctl)? deploy",
        r"gcloud (?:run|app|functions) deploy", r"eb deploy", r"swa deploy", r"ansible-playbook",
    ),
}
# Runs that exercise a running system. A test, until they are pointed at a deployed one.
AGAINST_A_SYSTEM = (r"playwright test", r"cypress run", r"k6 run", r"newman run", r"artillery run",
                    r"lhci autorun", r"lighthouse", r"backstop test", r"testcafe", r"wdio")
# A health check: only ever post-deploy verification, and only against a deployed environment.
HEALTH_CHECKS = (r"(?:curl|wget)[^\n]*/(?:health|healthz|ready|readyz|ping|status)\b",)
TASKS: dict[str, tuple[str, ...]] = {
    "build": ("vsbuild", "msbuild", "maven", "gradle", "ant", "xcode"),
    "test": ("vstest",),
    "static checks": ("sonarqubeanalyze", "sonarcloudanalyze"),
    "security scan": ("advancedsecurity-codeql-analyze", "advancedsecurity-dependency-scanning",
                      "snyksecurityscan", "whitesource", "mend", "dependency-check-build-task",
                      "credscan", "microsoftsecuritydevops", "trivy"),
    "deploy": ("azurewebapp", "azurermwebappdeployment", "azurefunctionapp", "azurewebappcontainer",
               "azurefunctionappcontainer", "kubernetesmanifest", "kubernetes", "helmdeploy",
               "azurestaticwebapp", "azureresourcemanagertemplatedeployment", "azurecontainerapps",
               "sqlazuredacpacdeployment", "iiswebappdeploymentonmachinegroup"),
}
ACTIONS: dict[str, tuple[str, ...]] = {
    "build": ("docker/build-push-action",),
    "static checks": ("golangci/golangci-lint-action", "github/super-linter", "super-linter/super-linter",
                      "astral-sh/ruff-action", "chartboost/ruff-action", "psf/black", "wearerequired/lint-action"),
    "security scan": ("github/codeql-action/analyze", "snyk/actions", "aquasecurity/trivy-action",
                      "gitleaks/gitleaks-action", "trufflesecurity/trufflehog", "returntocorp/semgrep-action",
                      "semgrep/semgrep-action", "actions/dependency-review-action", "ossf/scorecard-action",
                      "anchore/scan-action", "google/osv-scanner-action", "zaproxy/"),
    "deploy": ("cloudflare/wrangler-action", "cloudflare/pages-action", "azure/webapps-deploy",
               "azure/functions-action", "azure/k8s-deploy", "azure/static-web-apps-deploy",
               "azure/arm-deploy", "aws-actions/amazon-ecs-deploy-task-definition",
               "aws-actions/aws-cloudformation-github-deploy", "google-github-actions/deploy-cloudrun",
               "google-github-actions/deploy-appengine", "peaceiris/actions-gh-pages",
               "jamesives/github-pages-deploy-action", "actions/deploy-pages", "nwtgck/actions-netlify",
               "superfly/flyctl-actions"),
}
ACTIONS_AGAINST_A_SYSTEM = ("cypress-io/github-action", "treosh/lighthouse-ci-action")


def _compiled(patterns: tuple[str, ...]) -> re.Pattern[str]:
    """One pattern for a list of commands, each matched as a whole word: `vitest` matches in
    `npx vitest run` and `./node_modules/.bin/vitest`, and not in `my-vitest-helper`."""
    return re.compile(r"(?<![\w.-])(?:" + "|".join(patterns) + r")(?![\w-])", re.IGNORECASE)


_COMMAND_RES = {category: _compiled(patterns) for category, patterns in COMMANDS.items()}
_AGAINST_A_SYSTEM_RE = _compiled(AGAINST_A_SYSTEM)
_HEALTH_RE = re.compile("|".join(HEALTH_CHECKS), re.IGNORECASE)
# A line that only prints, or only comments, runs nothing.
_INERT_LINE = re.compile(r"^\s*(?:#|$|(?:echo|printf|write-host|write-output|:|true)(?:\s|$))", re.IGNORECASE)
# A package-manager call to a script: `npm run x`, `npm test`, `pnpm x`, `yarn run x`, `bun run x`.
_SCRIPT_CALL = re.compile(r"(?<![\w.-])(npm|pnpm|yarn|bun)\s+(run(?:-script)?\s+)?([\w:./-]+)")
_PARAMETER = re.compile(r"\$\{\{\s*parameters\.([A-Za-z0-9_]+)\s*\}\}")
_URL = re.compile(r"https?://", re.IGNORECASE)
_JENKINS_STEP = re.compile(r"""\b(?:sh|bat|powershell|pwsh)\s*\(?\s*(?:script\s*:\s*)?('''|\"\"\"|'|")(.*?)\1""",
                           re.DOTALL)
_GITLAB_RESERVED = frozenset({"stages", "variables", "default", "include", "workflow", "image", "services",
                              "cache", "before_script", "after_script", "types"})
_DEPTH = 8


class Step(TypedDict):
    """One thing a pipeline runs, in order: a shell script, an Azure task, a GitHub action, or a
    declared deployment. `job` groups the steps that run one after another on one agent, and
    `url` says the step was handed a deployed environment's address."""
    file: str
    job: str
    kind: str
    text: str
    url: bool


class Gates(TypedDict):
    """What L1.10 publishes from: each category found, with the files its steps are written in;
    the definitions read; the templates followed from them; and template references that name
    another repository, which cannot be read."""
    found: dict[str, list[str]]
    definitions: list[str]
    templates: list[str]
    unread: list[str]


def read(repo: Path) -> Gates:
    """Every definition the repository holds, read for the gates it runs. The reads themselves
    happen at the boundaries it hands work to: ci_pipelines.find and text_or_empty."""
    return gates(ci_pipelines.find(repo), lambda path: text_or_empty(repo / path),
                 text_or_empty(repo / "package.json"))


def gates(found: ci_pipelines.Pipelines, source: Callable[[str], str], manifest: str) -> Gates:
    """The categories covered by every definition found, with the files each was seen in. `source`
    gives a file's text by its path from the root, and is asked only for files a definition names."""
    walked: list[Step] = []
    templates: list[str] = []
    unread: list[str] = []
    for path in found["github"]:
        walked += _github(path, source, templates)
    for path in found["gitlab"]:
        walked += _gitlab(path, source, templates)
    for path in found["jenkins"]:
        walked += _jenkins(path, source(path))
    for path in found["azure"]:
        walked += _azure(path, source, {}, False, path, 0, templates, unread)
    return {"found": categorised(walked, _scripts(manifest)), "definitions": ci_pipelines.definitions(found),
            "templates": sorted(set(templates)), "unread": sorted(set(unread))}


def categorised(steps: list[Step], scripts: dict[str, str]) -> dict[str, list[str]]:
    """Each category the steps cover, with the files the covering steps are written in. Steps are
    read job by job, in order, so a browser run after a deploy in the same job is post-deploy
    verification and the same run before it, given no deployed address, is a test."""
    found: dict[str, set[str]] = {}
    deployed: set[str] = set()
    for step in steps:
        covered = covers(step, scripts, step["job"] in deployed)
        for category in covered:
            found.setdefault(category, set()).add(step["file"])
        if "deploy" in covered:
            deployed.add(step["job"])
    return {category: sorted(found[category]) for category in CATEGORIES if category in found}


def covers(step: Step, scripts: dict[str, str], after_a_deploy: bool) -> set[str]:
    """The categories one step covers, from what it runs and nothing else."""
    if step["kind"] == "environment":
        return {"deploy"}
    if step["kind"] == "task":
        return {category for category, names in TASKS.items() if step["text"] in names}
    if step["kind"] == "uses":
        covered = {category for category, prefixes in ACTIONS.items() if step["text"].startswith(prefixes)}
        if step["text"].startswith(ACTIONS_AGAINST_A_SYSTEM):
            covered.add("post-deploy verification" if after_a_deploy or step["url"] else "test")
        return covered
    text = expanded(step["text"], scripts)
    covered = {category for category, pattern in _COMMAND_RES.items() if pattern.search(text)}
    system = _AGAINST_A_SYSTEM_RE.search(text)
    health = _HEALTH_RE.search(text)
    deploy = _COMMAND_RES["deploy"].search(text)
    targeted = after_a_deploy or step["url"] or (deploy is not None and system is not None
                                                 and system.start() > deploy.start())
    if (system or health) and targeted:
        covered.add("post-deploy verification")
    elif system:
        covered.add("test")
    return covered


def expanded(script: str, scripts: dict[str, str]) -> str:
    """A step's script as it runs: comment and echo-only lines dropped, and each package-manager
    call to a `package.json` script replaced by that script's own command, a few calls deep."""
    text = "\n".join(line for line in script.splitlines() if not _INERT_LINE.match(line))
    for _ in range(4):
        replaced = _SCRIPT_CALL.sub(lambda m: _script_body(m, scripts), text)
        if replaced == text:
            break
        text = replaced
    return text


def _script_body(call: re.Match[str], scripts: dict[str, str]) -> str:
    """The command a package-manager call runs, or the call itself when it names no script. npm
    runs a bare name only for its own lifecycle scripts; pnpm, yarn and bun run any script bare."""
    manager, explicit, name = call.group(1), call.group(2), call.group(3)
    bare_allowed = manager != "npm" or name in ("test", "start", "stop", "restart")
    if name in scripts and (explicit or bare_allowed):
        return scripts[name]
    return call.group(0)


def _scripts(manifest: str) -> dict[str, str]:
    """A `package.json`'s scripts, by name. A manifest that does not parse has none."""
    try:
        data = json.loads(manifest) if manifest else {}
    # honest-code-allow: L1.21.8 - a manifest that does not parse declares no scripts, so a package-manager call is read as the call it is and counts only if the call itself is a known command
    except json.JSONDecodeError:
        return {}
    table = data.get("scripts") if isinstance(data, dict) else None
    return {str(k): str(v) for k, v in table.items()} if isinstance(table, dict) else {}


def _loaded(text: str) -> object:
    """A YAML document, or None when it does not parse: a file the reader cannot read runs
    nothing it can see."""
    try:
        return yaml.safe_load(text) if text else None
    # honest-code-allow: L1.21.8 - YAML that does not parse is a pipeline this reader cannot read, so it contributes no gate, which is the direction that never credits what was not seen
    except yaml.YAMLError:
        return None


def names_a_url(values: object) -> bool:
    """Whether parameters, variables or env values hand over a deployed address: a value that
    is an http(s) URL, or a non-empty value under a name ending in `url`."""
    pairs: list[tuple[str, object]] = []
    if isinstance(values, dict):
        pairs = [(str(k), v) for k, v in values.items()]
    elif isinstance(values, list):
        pairs = [(str(item.get("name", "")), item.get("value")) for item in values if isinstance(item, dict)]
    return any((name.lower().endswith("url") and value not in (None, "")) or bool(_URL.match(str(value)))
               for name, value in pairs)


def _relative(base: str, reference: str) -> str:
    """A referenced file's path from the root: from the referring file's directory, or from the
    root for a path starting with a slash. A path leaving the repository is nothing."""
    target = posixpath.normpath(reference.lstrip("/") if reference.startswith("/")
                                else str(PurePosixPath(base).parent / reference))
    return "" if target.startswith("..") else target


def _azure(path: str, source: Callable[[str], str], passed: dict[str, object], url: bool, job: str,
           depth: int, templates: list[str], unread: list[str]) -> list[Step]:
    """The steps one Azure file runs, its template references followed. A template's
    `${{ parameters.x }}` is replaced by the value passed, or the template's default, when that
    value is a scalar, so `pnpm run ${{ parameters.script }}` reads as the script it names."""
    raw = _loaded(source(path))
    if not isinstance(raw, dict) or depth > _DEPTH:
        return []
    values = {**_defaults(raw.get("parameters")), **passed}
    text = _PARAMETER.sub(lambda m: _scalar(values.get(m.group(1)), m.group(0)), source(path))
    data = _loaded(text) if values else raw
    if not isinstance(data, dict):
        return []
    url = url or names_a_url(values)
    return _azure_node({k: v for k, v in data.items() if k != "parameters"},
                       {"file": path, "job": job, "url": url}, source, depth, templates, unread)


class _Where(TypedDict):
    file: str
    job: str
    url: bool


# Keys that never hold steps, so the walk does not descend into them.
_NOT_STEPS = frozenset({"parameters", "variables", "pool", "condition", "displayName", "dependsOn", "env",
                        "inputs", "trigger", "pr", "resources", "schedules", "container", "services",
                        "workspace", "name", "environment"})
_INLINE_SCRIPT_INPUTS = ("script", "inlinescript", "inline")


def _azure_node(node: object, at: _Where, source: Callable[[str], str], depth: int,
                templates: list[str], unread: list[str]) -> list[Step]:
    """The steps under one node of an Azure document, in order."""
    if isinstance(node, list):
        return [step for item in node for step in _azure_node(item, at, source, depth, templates, unread)]
    if not isinstance(node, dict):
        return []
    reference = node.get("template")
    if isinstance(reference, str):
        target = "" if "@" in reference or "${{" in reference else _relative(at["file"], reference)
        if not target:
            unread.append(reference)
            return []
        templates.append(target)
        passed = node.get("parameters")
        passed = passed if isinstance(passed, dict) else {}
        return _azure(target, source, passed, at["url"] or names_a_url(passed), at["job"], depth + 1,
                      templates, unread)
    for key in ("script", "bash", "pwsh", "powershell"):
        if isinstance(node.get(key), str):
            return [_step(at, "run", node[key], names_a_url(node.get("env")))]
    if isinstance(node.get("task"), str):
        return _azure_task(node, at)
    named = node.get("job") or node.get("deployment")
    if named is not None:
        at = {"file": at["file"], "job": f"{at['file']}#{named}", "url": at["url"] or names_a_url(node.get("variables"))}
    steps = [_step(at, "environment", str(node["environment"]), False)] if node.get("deployment") and node.get("environment") else []
    return steps + [step for key, value in node.items() if key not in _NOT_STEPS
                    for step in _azure_node(value, at, source, depth, templates, unread)]


def _azure_task(node: dict[object, object], at: _Where) -> list[Step]:
    """An Azure task, and the script it carries: an inline script, or the command a dotnet,
    Docker or npm task runs, which the command table then reads like any other."""
    name = str(node["task"]).split("@")[0].lower()
    inputs = node.get("inputs")
    inputs = {str(k).lower(): v for k, v in inputs.items()} if isinstance(inputs, dict) else {}
    steps = [_step(at, "task", name, names_a_url(node.get("env")))]
    command = str(inputs.get("command", ""))
    runs = [str(inputs[key]) for key in _INLINE_SCRIPT_INPUTS if isinstance(inputs.get(key), str)]
    if name == "dotnetcorecli":
        runs.append(f"dotnet {command or 'build'}")
    if name == "docker" and command.lower() in ("", "build", "buildandpush"):
        runs.append("docker build")
    if name == "npm":
        runs.append(f"npm {inputs.get('customcommand', '') if command == 'custom' else command}")
    return steps + [_step(at, "run", text, names_a_url(node.get("env"))) for text in runs]


def _defaults(declared: object) -> dict[str, object]:
    """A template's parameter defaults, from either spelling Azure accepts: a list of
    `{name, default}` or a mapping of name to default."""
    if isinstance(declared, list):
        return {str(p["name"]): p["default"] for p in declared if isinstance(p, dict) and "name" in p and "default" in p}
    if isinstance(declared, dict):
        return {str(k): v for k, v in declared.items() if not isinstance(v, (dict, list))}
    return {}


def _scalar(value: object, unchanged: str) -> str:
    """A parameter value as Azure writes it into the text, or the expression unchanged when the
    value is a list or mapping, which no text substitution can stand for."""
    if value is None or isinstance(value, (dict, list)):
        return unchanged
    return str(value)


def _step(at: _Where, kind: str, text: str, url: bool) -> Step:
    return {"file": at["file"], "job": at["job"], "kind": kind, "text": text, "url": at["url"] or url}


def _github(path: str, source: Callable[[str], str], templates: list[str]) -> list[Step]:
    """The steps one GitHub workflow runs, job by job. A job with an `environment:` deploys to
    it. A local composite action (`uses: ./path`) is read for the steps it runs."""
    data = _loaded(source(path))
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, dict):
        return []
    steps: list[Step] = []
    for name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        at: _Where = {"file": path, "job": f"{path}#{name}", "url": names_a_url(job.get("env"))}
        if job.get("environment"):
            steps.append(_step(at, "environment", str(job["environment"]), False))
        steps += _github_steps(job.get("steps"), at, source, templates, 0)
    return steps


def _github_steps(listed: object, at: _Where, source: Callable[[str], str], templates: list[str],
                  depth: int) -> list[Step]:
    """A GitHub step list, a local composite action's steps read in place."""
    steps: list[Step] = []
    for item in listed if isinstance(listed, list) else []:
        if not isinstance(item, dict):
            continue
        url = names_a_url(item.get("env")) or names_a_url(item.get("with"))
        if isinstance(item.get("run"), str):
            steps.append(_step(at, "run", item["run"], url))
        uses = item.get("uses")
        if isinstance(uses, str) and uses.startswith("./") and depth < _DEPTH:
            steps += _composite(uses, {**at, "url": at["url"] or url}, source, templates, depth)
        elif isinstance(uses, str):
            steps.append(_step(at, "uses", uses.split("@")[0].lower(), url))
    return steps


def _composite(uses: str, at: _Where, source: Callable[[str], str], templates: list[str], depth: int) -> list[Step]:
    """A local composite action's steps, from its `action.yml` or `action.yaml`."""
    for name in ("action.yml", "action.yaml"):
        path = posixpath.normpath(f"{uses[2:]}/{name}")
        data = _loaded(source(path))
        if isinstance(data, dict):
            templates.append(path)
            runs = data.get("runs")
            listed = runs.get("steps") if isinstance(runs, dict) else None
            return _github_steps(listed, {**at, "file": path}, source, templates, depth + 1)
    return []


def _gitlab(path: str, source: Callable[[str], str], templates: list[str]) -> list[Step]:
    """The scripts every GitLab job runs, local includes and `extends:` read in. A hidden job
    (`.name`) runs only where another job extends it; a job with an `environment:` deploys."""
    document = _gitlab_document(path, source, templates, 0)
    defaults = document.get("default")
    defaults = defaults if isinstance(defaults, dict) else {}
    steps: list[Step] = []
    for name, job in document.items():
        if name in _GITLAB_RESERVED or name.startswith(".") or not isinstance(job, dict):
            continue
        merged = _extended(job, document)
        at: _Where = {"file": path, "job": f"{path}#{name}", "url": names_a_url(merged.get("variables"))}
        if merged.get("environment"):
            steps.append(_step(at, "environment", str(merged["environment"]), False))
        for key in ("before_script", "script", "after_script"):
            lines = merged.get(key, document.get(key, defaults.get(key)))
            steps += [_step(at, "run", line, False) for line in _flattened(lines)]
    return steps


def _gitlab_document(path: str, source: Callable[[str], str], templates: list[str], depth: int) -> dict[str, object]:
    """A GitLab file with its local includes merged under it, the including file winning."""
    data = _loaded(source(path))
    if not isinstance(data, dict) or depth > _DEPTH:
        return {}
    merged: dict[str, object] = {}
    includes = data.get("include")
    for item in includes if isinstance(includes, list) else [includes]:
        local = item.get("local") if isinstance(item, dict) else item
        if isinstance(local, str) and local.endswith((".yml", ".yaml")):
            target = _relative("", local)
            templates.append(target)
            merged.update(_gitlab_document(target, source, templates, depth + 1))
    merged.update({str(k): v for k, v in data.items()})
    return merged


def _extended(job: dict[object, object], document: dict[str, object]) -> dict[str, object]:
    """A job with the hidden jobs it extends laid under it, one level, the job winning."""
    names = job.get("extends")
    base: dict[str, object] = {}
    for name in names if isinstance(names, list) else [names]:
        parent = document.get(str(name)) if name else None
        if isinstance(parent, dict):
            base.update({str(k): v for k, v in parent.items()})
    return {**base, **{str(k): v for k, v in job.items()}}


def _flattened(lines: object) -> list[str]:
    """A GitLab script, which may be a string, a list, or lists nested by YAML anchors."""
    if isinstance(lines, str):
        return [lines]
    if isinstance(lines, list):
        return [line for item in lines for line in _flattened(item)]
    return []


def _jenkins(path: str, text: str) -> list[Step]:
    """The `sh`, `bat`, `powershell` and `pwsh` steps of a Jenkinsfile, in order, as one job."""
    at: _Where = {"file": path, "job": path, "url": False}
    return [_step(at, "run", match.group(2), False) for match in _JENKINS_STEP.finditer(text)]


def reading(found: Gates) -> L1Result:
    """L1.10 from the gates found: the number of categories covered, its band on the canon's
    numbers, and a sentence naming each category with its files, what is missing, and what was
    read."""
    covered = len(found["found"])
    return {"value": covered, "band": band(covered, 5, 1, higher_is_better=True), "details": details(found)}


def details(found: Gates) -> str:
    """The sentence beside the number."""
    if not found["definitions"]:
        return ("no pipeline definition files: no .yml or .yaml workflow files in .github/workflows, "
                "no .gitlab-ci.yml, no Jenkinsfile and no Azure Pipelines YAML")
    named = "; ".join(f"{category} ({', '.join(files)})" for category, files in found["found"].items())
    missing = [category for category in CATEGORIES if category not in found["found"]]
    said = f"{len(found['found'])} of {len(CATEGORIES)} gate categories: {named or 'none'}"
    if missing:
        said += f"; missing: {', '.join(missing)}"
    count = len(found["definitions"])
    said += f". Read from {count} pipeline definition{'s' if count != 1 else ''} ({', '.join(found['definitions'])})"
    templates = len(found["templates"])
    if templates:
        said += f" and the {templates} template{'s' if templates != 1 else ''} they include"
    if found["unread"]:
        said += f"; {len(found['unread'])} template reference(s) to another repository were not read"
    return said + ". A step counts for the command it runs, never for its name."
