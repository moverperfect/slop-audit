# Amendment 2026-11-13: L1.10 counts the gate categories a pipeline covers, not the files it is spread over

An amendment in the moverperfect/slop-audit fork. L1.10 used to count CI/CD pipeline definition files. It now counts which of six gate categories those pipelines cover. The bands keep their numbers on the new unit. The analyzer's reading, the canon row in `../../spec/03-layer1-indicators.md` and the CI/CD dimension in `../../spec/dimensions/10-cicd.md` move together in this change.

## What was wrong

The row read "count of CI/CD pipeline definition files", `≥5` Healthy, `1–4` Not Healthy, `0` Slop. A file count measures how a team splits its YAML, not what its pipelines do.

- **One well-staged pipeline read Not Healthy.** An Astro site deployed to Cloudflare Workers by Azure Pipelines builds, unit-tests, lints, format-checks and type-checks every change. It deploys on every release tag and smoke-, regression- and visual-tests the deployment. All of that lives in two pipeline definitions that pull in twenty templates. It read 2 and Not Healthy.
- **The same gates split over five files read Healthy.** Five workflows that each run the unit tests cover one gate between them, and read 5.
- **A placeholder counted in full.** A workflow that runs `echo "Build successful"`, the dimension's own named antipattern, counted the same as one that builds and tests.

File count rewards splitting, not coverage. The good-pattern note already said what a pipeline is for: "automated quality gates (testing, security scanning, integration validation)". The indicator now counts those gates.

## The new rule

Six categories, each counted once however many files, stages or jobs carry it:

| Category | What counts |
|---|---|
| build | compiles or bundles the application |
| test | runs an automated test suite |
| static checks | lint, type check, format check |
| security scan | dependency audit (SCA), SAST, secret scanning, container or IaC scanning |
| deploy | deploys to an environment |
| post-deploy verification | smoke, end-to-end, health or visual checks against a deployed environment |

**Healthy is 5 or 6 categories, Not Healthy 1–4, Slop 0.** Slop means no pipeline, or pipelines that do nothing meaningful. The value is the category count. The details sentence names each category found, with the files its steps are written in. It also names the categories that are missing, and how many pipeline definitions and templates were read.

## How a step is classified

**By the command it runs, matched against one declared table.** The table is the `COMMANDS`, `TASKS` and `ACTIONS` block at the top of `tools/l1_analyzer/l1_analyzer/ci_gates.py`. It lists shell commands, Azure Pipelines tasks and GitHub actions per category. Teaching the reader a tool is one line there.

**Names are never read.** A job, stage or step name is prose: a step called "Run tests" over `echo` runs nothing, and a step that runs `vitest` is a test whatever it is called. Reading names would credit labels rather than work, and a label is the cheapest thing in a pipeline to write. So a category is never inferred from a name, and the details sentence says so.

**An unknown command counts for nothing.** A repository's own `./scripts/check.sh` runs something this reader cannot see into, so it credits no category. The reader never guesses from the file name.

**Comments and echo-only lines are dropped before matching.** An echo-only step therefore counts for nothing, which is the dimension's echo-only placeholder pipeline.

**Package scripts are read for what they run.** A step that runs `pnpm run lint:strict` is read as the `package.json` script it calls, `oxlint --deny-warnings`, a few calls deep. npm runs a bare name only for its lifecycle scripts; pnpm, yarn and bun run any script bare. `make test`, `make check` and `make lint` count like the tools they conventionally stand for. A Makefile target is the same convention a package script is, and GNU names the self-tests `check`.

**Deploy is also read from structure where a system declares a deployment:**
- an Azure `deployment:` job with an `environment:`
- a GitHub or GitLab job with an `environment:`, which each system documents as the environment the job deploys to

**Post-deploy verification is a browser, end-to-end, load or health check against a deployed environment.** It counts when a deploy ran earlier in the same job, or when the step is handed a deployed address: a parameter, variable or env value that is an `http(s)://` URL or whose name ends in `url`. The same Playwright run with neither is a test.

**What the reader follows:**
- Azure `template:` references at every level, with the parameters they pass laid over the template's defaults. So `pnpm run ${{ parameters.script }}` reads as the script named.
- GitHub local composite actions.
- GitLab `include: local:` and `extends:`.
- The `sh`, `bat`, `powershell` and `pwsh` steps of a Jenkinsfile.

A template in another repository (`x.yml@repo`) cannot be read; the sentence says how many were not.

Pipeline YAML is parsed with PyYAML, a new runtime dependency of the Python reference. Azure's `${{ }}` expressions parse as plain strings.

## What moves

- **The Astro site above:** 2 files, Not Healthy, becomes 5 of 6 categories, Healthy. Security scanning is the missing category. Its grade's hygiene term moves from 0.650 to 0.750, and the letter stays B.
- **This repository:** five workflows, Healthy, becomes 4 of 6, Not Healthy. Build, test, static checks and a secret scan are present. Deploy and post-deploy verification are absent, because the release workflow attaches binaries to a GitHub release and deploys to no environment.
- **The repository's own tests** asserted file counts on fixtures whose pipelines run little or nothing:
  - `test_a_pipeline_outside_github_is_still_a_pipeline.py` now asserts what was read and what it covers, including that five definitions which run nothing read 0 and Slop.
  - `test_basic.py::test_config_indicators_present` gives its workflow a step.
  - `test_ci_cd_is_measured_by_the_gates_it_runs.py` holds the new rule.

## What this cannot see

- **A pipeline defined in the CI service rather than the repository.** Every classic Azure DevOps release and every Jenkins job configured in its UI reads zero, as before.
- **A tool the table does not list, or one run by a script it cannot open.** A repository's own shell script is opaque. Such a step credits nothing, so the reading under-counts rather than guessing.
- **A deployment with no address in reach.** A smoke test that finds its target from a secret or a config file, with no deploy earlier in its job and no URL-shaped parameter or variable, is read as a test.
- **The Rust port** still reads L1.10 as a file count. It has not been brought along.
