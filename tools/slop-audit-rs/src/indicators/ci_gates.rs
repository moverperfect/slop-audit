//! L1.10's reading: which gate categories a repository's CI/CD pipelines cover.
//!
//! Port of l1_analyzer.ci_gates. The unit is the gate, not the file. Six categories,
//! each once however many files, stages or jobs carry it. A step counts for what it
//! RUNS, matched against one declared table; names are never read.

use super::ci_pipelines::{self, Pipelines};
use crate::{band, Indicator};
use fancy_regex::Regex as FancyRegex;
use regex::Regex;
use serde_yaml::{Mapping, Value};
use std::collections::{BTreeSet, HashMap, HashSet};
use std::path::Path;
use std::sync::OnceLock;

const CATEGORIES: &[&str] = &[
    "build",
    "test",
    "static checks",
    "security scan",
    "deploy",
    "post-deploy verification",
];

const COMMANDS: &[(&str, &[&str])] = &[
    ("build", &[
        r"astro build", r"vite build", r"next build", r"nuxi? build", r"ng build", r"svelte-kit build",
        r"remix (?:vite:)?build", r"webpack", r"rollup (?:-c|--config)", r"esbuild", r"tsup",
        r"parcel build", r"turbo (?:run )?build", r"nx (?:run-many [^\n]*build|build)",
        r"tsc(?![^\n]*--noemit)(?=\s|$)", r"go build", r"cargo build", r"dotnet (?:build|publish)",
        r"msbuild", r"mvnw?\b[^\n]*\b(?:package|install|verify)", r"gradlew?\b[^\n]*\b(?:build|assemble)",
        r"docker (?:buildx )?build", r"python -m build", r"poetry build", r"hugo", r"jekyll build",
    ]),
    ("test", &[
        r"vitest", r"jest", r"mocha", r"pytest", r"python -m (?:pytest|unittest)", r"go test",
        r"cargo (?:test|nextest)", r"dotnet test", r"(?:npm|yarn|pnpm|bun) test", r"bun test",
        r"deno test", r"mvnw?\b[^\n]*\btest\b", r"gradlew?\b[^\n]*\btest\b", r"rspec", r"rake test",
        r"phpunit", r"ctest", r"tox", r"nox", r"make (?:test|check)",
    ]),
    ("static checks", &[
        r"eslint", r"oxlint", r"biome (?:check|lint|ci)", r"tsc[^\n]*--noemit", r"vue-tsc",
        r"astro check", r"svelte-check", r"prettier[^\n]*(?:--check|--list-different|\s-[cl]\b)",
        r"oxfmt[^\n]*--check", r"dprint check", r"ruff", r"black[^\n]*--check", r"isort[^\n]*--check",
        r"flake8", r"pylint", r"mypy", r"pyright", r"golangci-lint", r"go vet", r"staticcheck",
        r"gofmt -l", r"cargo clippy", r"cargo fmt[^\n]*--check", r"rubocop", r"stylelint",
        r"markdownlint", r"hadolint", r"shellcheck", r"dotnet format[^\n]*--verify-no-changes",
        r"ktlint", r"spotless:?check", r"pre-commit run", r"make lint",
    ]),
    ("security scan", &[
        r"(?:npm|pnpm|yarn|bun) (?:npm )?audit", r"snyk", r"trivy", r"grype", r"codeql", r"semgrep",
        r"gitleaks", r"trufflehog", r"osv-scanner", r"dependency-check", r"pip-audit",
        r"safety (?:check|scan)", r"bandit", r"cargo (?:audit|deny)", r"govulncheck", r"checkov",
        r"tfsec", r"kics", r"bundler?[- ]audit", r"brakeman", r"audit-ci",
    ]),
    ("deploy", &[
        r"wrangler (?:deploy|publish|versions (?:upload|deploy)|pages deploy)",
        r"kubectl (?:apply|rollout|set image|replace|create)", r"helm (?:upgrade|install)",
        r"(?:terraform|tofu) apply", r"pulumi up",
        r"az (?:webapp (?:deploy|up)|functionapp deployment|containerapp (?:up|update)|deployment group create)",
        r"aws cloudformation deploy", r"sam deploy", r"cdk deploy", r"(?:serverless|sls) deploy",
        r"vercel (?:deploy|--prod)", r"netlify deploy", r"firebase deploy", r"fly(?:ctl)? deploy",
        r"gcloud (?:run|app|functions) deploy", r"eb deploy", r"swa deploy", r"ansible-playbook",
    ]),
];

const AGAINST_A_SYSTEM: &[&str] = &[
    r"playwright test", r"cypress run", r"k6 run", r"newman run", r"artillery run",
    r"lhci autorun", r"lighthouse", r"backstop test", r"testcafe", r"wdio",
];
const HEALTH_CHECKS: &[&str] = &[r"(?:curl|wget)[^\n]*/(?:health|healthz|ready|readyz|ping|status)\b"];

const TASKS: &[(&str, &[&str])] = &[
    ("build", &["vsbuild", "msbuild", "maven", "gradle", "ant", "xcode"]),
    ("test", &["vstest"]),
    ("static checks", &["sonarqubeanalyze", "sonarcloudanalyze"]),
    ("security scan", &[
        "advancedsecurity-codeql-analyze", "advancedsecurity-dependency-scanning",
        "snyksecurityscan", "whitesource", "mend", "dependency-check-build-task",
        "credscan", "microsoftsecuritydevops", "trivy",
    ]),
    ("deploy", &[
        "azurewebapp", "azurermwebappdeployment", "azurefunctionapp", "azurewebappcontainer",
        "azurefunctionappcontainer", "kubernetesmanifest", "kubernetes", "helmdeploy",
        "azurestaticwebapp", "azureresourcemanagertemplatedeployment", "azurecontainerapps",
        "sqlazuredacpacdeployment", "iiswebappdeploymentonmachinegroup",
    ]),
];

const ACTIONS: &[(&str, &[&str])] = &[
    ("build", &["docker/build-push-action"]),
    ("static checks", &[
        "golangci/golangci-lint-action", "github/super-linter", "super-linter/super-linter",
        "astral-sh/ruff-action", "chartboost/ruff-action", "psf/black", "wearerequired/lint-action",
    ]),
    ("security scan", &[
        "github/codeql-action/analyze", "snyk/actions", "aquasecurity/trivy-action",
        "gitleaks/gitleaks-action", "trufflesecurity/trufflehog", "returntocorp/semgrep-action",
        "semgrep/semgrep-action", "actions/dependency-review-action", "ossf/scorecard-action",
        "anchore/scan-action", "google/osv-scanner-action", "zaproxy/",
    ]),
    ("deploy", &[
        "cloudflare/wrangler-action", "cloudflare/pages-action", "azure/webapps-deploy",
        "azure/functions-action", "azure/k8s-deploy", "azure/static-web-apps-deploy",
        "azure/arm-deploy", "aws-actions/amazon-ecs-deploy-task-definition",
        "aws-actions/aws-cloudformation-github-deploy", "google-github-actions/deploy-cloudrun",
        "google-github-actions/deploy-appengine", "peaceiris/actions-gh-pages",
        "jamesives/github-pages-deploy-action", "actions/deploy-pages", "nwtgck/actions-netlify",
        "superfly/flyctl-actions",
    ]),
];

const ACTIONS_AGAINST_A_SYSTEM: &[&str] = &[
    "cypress-io/github-action", "treosh/lighthouse-ci-action",
];

const NOT_STEPS: &[&str] = &[
    "parameters", "variables", "pool", "condition", "displayName", "dependsOn", "env",
    "inputs", "trigger", "pr", "resources", "schedules", "container", "services",
    "workspace", "name", "environment",
];
const INLINE_SCRIPT_INPUTS: &[&str] = &["script", "inlinescript", "inline"];
const GITLAB_RESERVED: &[&str] = &[
    "stages", "variables", "default", "include", "workflow", "image", "services",
    "cache", "before_script", "after_script", "types",
];
const DEPTH: usize = 8;

#[derive(Clone)]
struct Step {
    file: String,
    job: String,
    kind: String,
    text: String,
    url: bool,
}

struct Where {
    file: String,
    job: String,
    url: bool,
}

struct Gates {
    found: Vec<(String, Vec<String>)>,
    definitions: Vec<String>,
    templates: Vec<String>,
    unread: Vec<String>,
}

fn compiled(patterns: &[&str]) -> FancyRegex {
    FancyRegex::new(&format!(
        r"(?i)(?<![\w.-])(?:{})(?![\w-])",
        patterns.join("|")
    ))
    .expect("gate command pattern")
}

struct Patterns {
    commands: HashMap<&'static str, FancyRegex>,
    against: FancyRegex,
    health: Regex,
    inert: Regex,
    script_call: FancyRegex,
    parameter: Regex,
    url: Regex,
    jenkins: FancyRegex,
}

fn patterns() -> &'static Patterns {
    static P: OnceLock<Patterns> = OnceLock::new();
    P.get_or_init(|| Patterns {
        commands: COMMANDS.iter().map(|(cat, pats)| (*cat, compiled(pats))).collect(),
        against: compiled(AGAINST_A_SYSTEM),
        health: Regex::new(&format!("(?i){}", HEALTH_CHECKS.join("|"))).unwrap(),
        inert: Regex::new(r"(?i)^\s*(?:#|$|(?:echo|printf|write-host|write-output|:|true)(?:\s|$))").unwrap(),
        script_call: FancyRegex::new(r"(?i)(?<![\w.-])(npm|pnpm|yarn|bun)\s+(run(?:-script)?\s+)?([\w:./-]+)").unwrap(),
        parameter: Regex::new(r"\$\{\{\s*parameters\.([A-Za-z0-9_]+)\s*\}\}").unwrap(),
        url: Regex::new(r"(?i)^https?://").unwrap(),
        // Backreference `\1` closes the same quote the opener captured. The `regex`
        // crate cannot compile that; fancy-regex can, and a Jenkinsfile must not
        // panic the audit.
        jenkins: FancyRegex::new(r#"(?s)\b(?:sh|bat|powershell|pwsh)\s*\(?\s*(?:script\s*:\s*)?('''|"""|'|")(.*?)\1"#)
            .expect("jenkins step pattern"),
    })
}

/// Replace `${{ ... }}` so YAML parsers that treat `{` as a flow map still load the file.
///
/// Unquoted, because a workflow that already wrote `"${{ secrets.TOKEN }}"` would
/// become `""__CI_EXPR__""` and fail to parse, which silently dropped every gate
/// in that file.
fn quote_ci_expressions(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    let mut rest = text;
    while let Some(start) = rest.find("${{") {
        out.push_str(&rest[..start]);
        let after = &rest[start + 3..];
        if let Some(end) = after.find("}}") {
            out.push_str("__CI_EXPR__");
            rest = &after[end + 2..];
        } else {
            out.push_str("${{");
            rest = after;
        }
    }
    out.push_str(rest);
    out
}

fn loaded(text: &str) -> Option<Value> {
    if text.is_empty() {
        return None;
    }
    serde_yaml::from_str(&quote_ci_expressions(text)).ok()
}

fn map_get<'a>(map: &'a Mapping, key: &str) -> Option<&'a Value> {
    map.get(Value::String(key.to_string()))
}

fn as_map(value: &Value) -> Option<&Mapping> {
    value.as_mapping()
}

fn as_seq(value: &Value) -> Option<&Vec<Value>> {
    value.as_sequence()
}

fn yaml_str(value: &Value) -> String {
    match value {
        Value::String(s) => s.clone(),
        Value::Bool(b) => if *b { "True".into() } else { "False".into() },
        Value::Number(n) => n.to_string(),
        Value::Null => "None".into(),
        other => format!("{other:?}"),
    }
}

fn names_a_url(values: Option<&Value>) -> bool {
    let Some(values) = values else {
        return false;
    };
    let pairs: Vec<(String, Option<&Value>)> = match values {
        Value::Mapping(m) => m
            .iter()
            .map(|(k, v)| (yaml_str(k), Some(v)))
            .collect(),
        Value::Sequence(s) => s
            .iter()
            .filter_map(|item| {
                let m = as_map(item)?;
                Some((
                    map_get(m, "name").map(yaml_str).unwrap_or_default(),
                    map_get(m, "value"),
                ))
            })
            .collect(),
        _ => return false,
    };
    pairs.iter().any(|(name, value)| {
        let empty = match value {
            None | Some(Value::Null) => true,
            Some(Value::String(s)) if s.is_empty() => true,
            _ => false,
        };
        (name.to_lowercase().ends_with("url") && !empty)
            || value
                .map(|v| patterns().url.is_match(&yaml_str(v)))
                .unwrap_or(false)
    })
}

fn scripts_from(manifest: &str) -> HashMap<String, String> {
    let data: serde_json::Value = match serde_json::from_str(manifest) {
        Ok(v) => v,
        Err(_) => return HashMap::new(),
    };
    let Some(table) = data.get("scripts").and_then(|s| s.as_object()) else {
        return HashMap::new();
    };
    table
        .iter()
        .map(|(k, v)| {
            (
                k.clone(),
                match v {
                    serde_json::Value::String(s) => s.clone(),
                    other => other.to_string(),
                },
            )
        })
        .collect()
}

fn expanded(script: &str, scripts: &HashMap<String, String>) -> String {
    let mut text: String = script
        .split('\n')
        .filter(|line| !patterns().inert.is_match(line))
        .collect::<Vec<_>>()
        .join("\n");
    for _ in 0..4 {
        let mut replaced = String::new();
        let mut last = 0;
        let mut any = false;
        for caps in patterns().script_call.captures_iter(&text).flatten() {
            let m = caps.get(0).unwrap();
            replaced.push_str(&text[last..m.start()]);
            replaced.push_str(&script_body(&caps, scripts));
            last = m.end();
            any = true;
        }
        if !any {
            break;
        }
        replaced.push_str(&text[last..]);
        if replaced == text {
            break;
        }
        text = replaced;
    }
    text
}

fn script_body(call: &fancy_regex::Captures<'_>, scripts: &HashMap<String, String>) -> String {
    let manager = call.get(1).map(|m| m.as_str()).unwrap_or("");
    let explicit = call.get(2).map(|m| m.as_str()).unwrap_or("");
    let name = call.get(3).map(|m| m.as_str()).unwrap_or("");
    let bare_allowed = manager != "npm" || matches!(name, "test" | "start" | "stop" | "restart");
    if scripts.contains_key(name) && (!explicit.is_empty() || bare_allowed) {
        scripts[name].clone()
    } else {
        call.get(0).map(|m| m.as_str().to_string()).unwrap_or_default()
    }
}

fn fancy_search(re: &FancyRegex, text: &str) -> Option<usize> {
    re.find(text).ok().flatten().map(|m| m.start())
}

fn covers(step: &Step, scripts: &HashMap<String, String>, after_a_deploy: bool) -> HashSet<String> {
    if step.kind == "environment" {
        return ["deploy".into()].into();
    }
    if step.kind == "task" {
        return TASKS
            .iter()
            .filter(|(_, names)| names.contains(&step.text.as_str()))
            .map(|(cat, _)| (*cat).to_string())
            .collect();
    }
    if step.kind == "uses" {
        let mut covered: HashSet<String> = ACTIONS
            .iter()
            .filter(|(_, prefixes)| prefixes.iter().any(|p| step.text.starts_with(p)))
            .map(|(cat, _)| (*cat).to_string())
            .collect();
        if ACTIONS_AGAINST_A_SYSTEM.iter().any(|p| step.text.starts_with(p)) {
            covered.insert(if after_a_deploy || step.url {
                "post-deploy verification".into()
            } else {
                "test".into()
            });
        }
        return covered;
    }
    let text = expanded(&step.text, scripts);
    let res = &patterns().commands;
    let mut covered: HashSet<String> = res
        .iter()
        .filter(|(_, pattern)| fancy_search(pattern, &text).is_some())
        .map(|(cat, _)| (*cat).to_string())
        .collect();
    let system = fancy_search(&patterns().against, &text);
    let health = patterns().health.find(&text).is_some();
    let deploy = res.get("deploy").and_then(|p| fancy_search(p, &text));
    let targeted = after_a_deploy
        || step.url
        || matches!((deploy, system), (Some(d), Some(s)) if s > d);
    if (system.is_some() || health) && targeted {
        covered.insert("post-deploy verification".into());
    } else if system.is_some() {
        covered.insert("test".into());
    }
    covered
}

fn categorised(steps: &[Step], scripts: &HashMap<String, String>) -> Vec<(String, Vec<String>)> {
    let mut found: HashMap<String, BTreeSet<String>> = HashMap::new();
    let mut deployed: HashSet<String> = HashSet::new();
    for step in steps {
        let covered = covers(step, scripts, deployed.contains(&step.job));
        for category in &covered {
            found
                .entry(category.clone())
                .or_default()
                .insert(step.file.clone());
        }
        if covered.contains("deploy") {
            deployed.insert(step.job.clone());
        }
    }
    CATEGORIES
        .iter()
        .filter_map(|cat| {
            found.get(*cat).map(|files| {
                ((*cat).to_string(), files.iter().cloned().collect())
            })
        })
        .collect()
}

fn make_step(at: &Where, kind: &str, text: String, url: bool) -> Step {
    Step {
        file: at.file.clone(),
        job: at.job.clone(),
        kind: kind.into(),
        text,
        url: at.url || url,
    }
}

fn defaults(declared: Option<&Value>) -> HashMap<String, Value> {
    match declared {
        Some(Value::Sequence(list)) => list
            .iter()
            .filter_map(|p| {
                let m = as_map(p)?;
                let name = map_get(m, "name").map(yaml_str)?;
                let default = map_get(m, "default")?.clone();
                Some((name, default))
            })
            .collect(),
        Some(Value::Mapping(m)) => m
            .iter()
            .filter(|(_, v)| !v.is_mapping() && !v.is_sequence())
            .map(|(k, v)| (yaml_str(k), v.clone()))
            .collect(),
        _ => HashMap::new(),
    }
}

fn scalar(value: Option<&Value>, unchanged: &str) -> String {
    match value {
        None | Some(Value::Null) | Some(Value::Mapping(_)) | Some(Value::Sequence(_)) => {
            unchanged.to_string()
        }
        Some(v) => yaml_str(v),
    }
}

fn azure(
    path: &str,
    source: &dyn Fn(&str) -> String,
    passed: &HashMap<String, Value>,
    mut url: bool,
    job: &str,
    depth: usize,
    templates: &mut Vec<String>,
    unread: &mut Vec<String>,
) -> Vec<Step> {
    let raw = loaded(&source(path));
    let Some(raw_map) = raw.as_ref().and_then(as_map) else {
        return Vec::new();
    };
    if depth > DEPTH {
        return Vec::new();
    }
    let mut values = defaults(map_get(raw_map, "parameters"));
    values.extend(passed.iter().map(|(k, v)| (k.clone(), v.clone())));
    let original = source(path);
    let substituted = patterns().parameter.replace_all(&original, |caps: &regex::Captures| {
        scalar(values.get(&caps[1]), &caps[0])
    });
    let data = if values.is_empty() {
        raw
    } else {
        loaded(&substituted)
    };
    let Some(data_map) = data.as_ref().and_then(as_map) else {
        return Vec::new();
    };
    url = url || names_a_url(Some(&Value::Mapping(
        values
            .iter()
            .map(|(k, v)| (Value::String(k.clone()), v.clone()))
            .collect(),
    )));
    let mut node = data_map.clone();
    node.remove(Value::String("parameters".into()));
    azure_node(
        &Value::Mapping(node),
        &Where {
            file: path.into(),
            job: job.into(),
            url,
        },
        source,
        depth,
        templates,
        unread,
    )
}

fn azure_node(
    node: &Value,
    at: &Where,
    source: &dyn Fn(&str) -> String,
    depth: usize,
    templates: &mut Vec<String>,
    unread: &mut Vec<String>,
) -> Vec<Step> {
    if let Some(list) = as_seq(node) {
        return list
            .iter()
            .flat_map(|item| azure_node(item, at, source, depth, templates, unread))
            .collect();
    }
    let Some(map) = as_map(node) else {
        return Vec::new();
    };
    if let Some(Value::String(reference)) = map_get(map, "template") {
        let target = if reference.contains('@') || reference.contains("${{") {
            String::new()
        } else {
            ci_pipelines::relative_from(&at.file, reference)
        };
        if target.is_empty() {
            unread.push(reference.clone());
            return Vec::new();
        }
        templates.push(target.clone());
        let passed = match map_get(map, "parameters") {
            Some(Value::Mapping(m)) => m
                .iter()
                .map(|(k, v)| (yaml_str(k), v.clone()))
                .collect(),
            _ => HashMap::new(),
        };
        let url = at.url || names_a_url(map_get(map, "parameters"));
        return azure(&target, source, &passed, url, &at.job, depth + 1, templates, unread);
    }
    for key in ["script", "bash", "pwsh", "powershell"] {
        if let Some(Value::String(text)) = map_get(map, key) {
            return vec![make_step(at, "run", text.clone(), names_a_url(map_get(map, "env")))];
        }
    }
    if let Some(Value::String(_)) = map_get(map, "task") {
        return azure_task(map, at);
    }
    let mut at_job = Where {
        file: at.file.clone(),
        job: at.job.clone(),
        url: at.url,
    };
    let named = map_get(map, "job").or_else(|| map_get(map, "deployment"));
    if let Some(named) = named {
        at_job.job = format!("{}#{}", at.file, yaml_str(named));
        at_job.url = at.url || names_a_url(map_get(map, "variables"));
    }
    let mut steps = Vec::new();
    if map_get(map, "deployment").is_some() {
        if let Some(env) = map_get(map, "environment") {
            steps.push(make_step(&at_job, "environment", yaml_str(env), false));
        }
    }
    for (key, value) in map {
        let name = yaml_str(key);
        if NOT_STEPS.contains(&name.as_str()) {
            continue;
        }
        steps.extend(azure_node(value, &at_job, source, depth, templates, unread));
    }
    steps
}

fn azure_task(node: &Mapping, at: &Where) -> Vec<Step> {
    let name = yaml_str(map_get(node, "task").unwrap())
        .split('@')
        .next()
        .unwrap_or("")
        .to_lowercase();
    let inputs: HashMap<String, Value> = match map_get(node, "inputs") {
        Some(Value::Mapping(m)) => m
            .iter()
            .map(|(k, v)| (yaml_str(k).to_lowercase(), v.clone()))
            .collect(),
        _ => HashMap::new(),
    };
    let mut steps = vec![make_step(
        at,
        "task",
        name.clone(),
        names_a_url(map_get(node, "env")),
    )];
    let command = inputs.get("command").map(yaml_str).unwrap_or_default();
    let mut runs: Vec<String> = INLINE_SCRIPT_INPUTS
        .iter()
        .filter_map(|key| {
            inputs.get(*key).and_then(|v| {
                if let Value::String(s) = v {
                    Some(s.clone())
                } else {
                    None
                }
            })
        })
        .collect();
    if name == "dotnetcorecli" {
        runs.push(format!("dotnet {}", if command.is_empty() { "build" } else { &command }));
    }
    if name == "docker" && matches!(command.to_lowercase().as_str(), "" | "build" | "buildandpush") {
        runs.push("docker build".into());
    }
    if name == "npm" {
        let cmd = if command == "custom" {
            inputs.get("customcommand").map(yaml_str).unwrap_or_default()
        } else {
            command
        };
        runs.push(format!("npm {cmd}"));
    }
    steps.extend(
        runs.into_iter()
            .map(|text| make_step(at, "run", text, names_a_url(map_get(node, "env")))),
    );
    steps
}

fn github(path: &str, source: &dyn Fn(&str) -> String, templates: &mut Vec<String>) -> Vec<Step> {
    let data = loaded(&source(path));
    let jobs = data
        .as_ref()
        .and_then(as_map)
        .and_then(|m| map_get(m, "jobs"))
        .and_then(as_map);
    let Some(jobs) = jobs else {
        return Vec::new();
    };
    let mut steps = Vec::new();
    for (name, job) in jobs {
        let Some(job_map) = as_map(job) else {
            continue;
        };
        let at = Where {
            file: path.into(),
            job: format!("{}#{}", path, yaml_str(name)),
            url: names_a_url(map_get(job_map, "env")),
        };
        if map_get(job_map, "environment").is_some() {
            steps.push(make_step(
                &at,
                "environment",
                yaml_str(map_get(job_map, "environment").unwrap()),
                false,
            ));
        }
        steps.extend(github_steps(
            map_get(job_map, "steps"),
            &at,
            source,
            templates,
            0,
        ));
    }
    steps
}

fn github_steps(
    listed: Option<&Value>,
    at: &Where,
    source: &dyn Fn(&str) -> String,
    templates: &mut Vec<String>,
    depth: usize,
) -> Vec<Step> {
    let Some(list) = listed.and_then(as_seq) else {
        return Vec::new();
    };
    let mut steps = Vec::new();
    for item in list {
        let Some(map) = as_map(item) else {
            continue;
        };
        let url = names_a_url(map_get(map, "env")) || names_a_url(map_get(map, "with"));
        if let Some(Value::String(run)) = map_get(map, "run") {
            steps.push(make_step(at, "run", run.clone(), url));
        }
        if let Some(Value::String(uses)) = map_get(map, "uses") {
            if uses.starts_with("./") && depth < DEPTH {
                let nested = Where {
                    file: at.file.clone(),
                    job: at.job.clone(),
                    url: at.url || url,
                };
                steps.extend(composite(uses, &nested, source, templates, depth));
            } else {
                let name = uses.split('@').next().unwrap_or(uses).to_lowercase();
                steps.push(make_step(at, "uses", name, url));
            }
        }
    }
    steps
}

fn composite(
    uses: &str,
    at: &Where,
    source: &dyn Fn(&str) -> String,
    templates: &mut Vec<String>,
    depth: usize,
) -> Vec<Step> {
    for name in ["action.yml", "action.yaml"] {
        let path = ci_pipelines::posixpath_norm(&format!("{}/{name}", &uses[2..]));
        if let Some(data) = loaded(&source(&path)) {
            if let Some(map) = as_map(&data) {
                templates.push(path.clone());
                let listed = map_get(map, "runs")
                    .and_then(as_map)
                    .and_then(|r| map_get(r, "steps"));
                let nested = Where {
                    file: path,
                    job: at.job.clone(),
                    url: at.url,
                };
                return github_steps(listed, &nested, source, templates, depth + 1);
            }
        }
    }
    Vec::new()
}

fn gitlab(path: &str, source: &dyn Fn(&str) -> String, templates: &mut Vec<String>) -> Vec<Step> {
    let document = gitlab_document(path, source, templates, 0);
    let defaults = document
        .get("default")
        .and_then(as_map)
        .cloned()
        .unwrap_or_default();
    let mut steps = Vec::new();
    for (name_val, job) in &document {
        let name = yaml_str(name_val);
        if GITLAB_RESERVED.contains(&name.as_str()) || name.starts_with('.') {
            continue;
        }
        let Some(job_map) = as_map(job) else {
            continue;
        };
        let merged = extended(job_map, &document);
        let at = Where {
            file: path.into(),
            job: format!("{path}#{name}"),
            url: names_a_url(map_get(&merged, "variables")),
        };
        if map_get(&merged, "environment").is_some() {
            steps.push(make_step(
                &at,
                "environment",
                yaml_str(map_get(&merged, "environment").unwrap()),
                false,
            ));
        }
        for key in ["before_script", "script", "after_script"] {
            let lines = map_get(&merged, key)
                .or_else(|| document.get(&Value::String(key.into())))
                .or_else(|| defaults.get(&Value::String(key.into())));
            steps.extend(
                flattened(lines)
                    .into_iter()
                    .map(|line| make_step(&at, "run", line, false)),
            );
        }
    }
    steps
}

fn gitlab_document(
    path: &str,
    source: &dyn Fn(&str) -> String,
    templates: &mut Vec<String>,
    depth: usize,
) -> Mapping {
    let data = loaded(&source(path));
    let Some(map) = data.as_ref().and_then(as_map) else {
        return Mapping::new();
    };
    if depth > DEPTH {
        return Mapping::new();
    }
    let mut merged = Mapping::new();
    let includes = map_get(map, "include");
    let items: Vec<&Value> = match includes {
        Some(Value::Sequence(s)) => s.iter().collect(),
        Some(other) => vec![other],
        None => Vec::new(),
    };
    for item in items {
        let local = match item {
            Value::Mapping(m) => map_get(m, "local").and_then(Value::as_str),
            Value::String(s) => Some(s.as_str()),
            _ => None,
        };
        if let Some(local) = local {
            if local.ends_with(".yml") || local.ends_with(".yaml") {
                let target = ci_pipelines::relative_from("", local);
                templates.push(target.clone());
                for (k, v) in gitlab_document(&target, source, templates, depth + 1) {
                    merged.insert(k, v);
                }
            }
        }
    }
    for (k, v) in map {
        merged.insert(k.clone(), v.clone());
    }
    merged
}

fn extended(job: &Mapping, document: &Mapping) -> Mapping {
    let names = match map_get(job, "extends") {
        Some(Value::Sequence(s)) => s.clone(),
        Some(other) => vec![other.clone()],
        None => Vec::new(),
    };
    let mut base = Mapping::new();
    for name in names {
        if let Some(Value::Mapping(parent)) = document.get(Value::String(yaml_str(&name))) {
            for (k, v) in parent {
                base.insert(k.clone(), v.clone());
            }
        }
    }
    for (k, v) in job {
        base.insert(k.clone(), v.clone());
    }
    base
}

fn flattened(lines: Option<&Value>) -> Vec<String> {
    match lines {
        Some(Value::String(s)) => vec![s.clone()],
        Some(Value::Sequence(s)) => s.iter().flat_map(|item| flattened(Some(item))).collect(),
        _ => Vec::new(),
    }
}

fn jenkins(path: &str, text: &str) -> Vec<Step> {
    let at = Where {
        file: path.into(),
        job: path.into(),
        url: false,
    };
    patterns().jenkins
        .captures_iter(text)
        .flatten()
        .filter_map(|cap| {
            cap.get(2)
                .map(|m| make_step(&at, "run", m.as_str().to_string(), false))
        })
        .collect()
}

fn details(found: &Gates) -> String {
    if found.definitions.is_empty() {
        return "no pipeline definition files: no .yml or .yaml workflow files in .github/workflows, \
                no .gitlab-ci.yml, no Jenkinsfile and no Azure Pipelines YAML"
            .into();
    }
    let named = found
        .found
        .iter()
        .map(|(category, files)| format!("{category} ({})", files.join(", ")))
        .collect::<Vec<_>>()
        .join("; ");
    let missing: Vec<&str> = CATEGORIES
        .iter()
        .copied()
        .filter(|cat| found.found.iter().all(|(c, _)| c != cat))
        .collect();
    let mut said = format!(
        "{} of {} gate categories: {}",
        found.found.len(),
        CATEGORIES.len(),
        if named.is_empty() { "none".into() } else { named }
    );
    if !missing.is_empty() {
        said.push_str(&format!("; missing: {}", missing.join(", ")));
    }
    let count = found.definitions.len();
    said.push_str(&format!(
        ". Read from {count} pipeline definition{} ({})",
        if count == 1 { "" } else { "s" },
        found.definitions.join(", ")
    ));
    let templates = found.templates.len();
    if templates > 0 {
        said.push_str(&format!(
            " and the {templates} template{} they include",
            if templates == 1 { "" } else { "s" }
        ));
    }
    if !found.unread.is_empty() {
        said.push_str(&format!(
            "; {} template reference(s) to another repository were not read",
            found.unread.len()
        ));
    }
    said.push_str(". A step counts for the command it runs, never for its name.");
    said
}

fn gates(found: Pipelines, source: &dyn Fn(&str) -> String, manifest: &str) -> Gates {
    let mut walked: Vec<Step> = Vec::new();
    let mut templates: Vec<String> = Vec::new();
    let mut unread: Vec<String> = Vec::new();
    for path in &found.github {
        walked.extend(github(path, source, &mut templates));
    }
    for path in &found.gitlab {
        walked.extend(gitlab(path, source, &mut templates));
    }
    for path in &found.jenkins {
        walked.extend(jenkins(path, &source(path)));
    }
    for path in &found.azure {
        walked.extend(azure(
            path,
            source,
            &HashMap::new(),
            false,
            path,
            0,
            &mut templates,
            &mut unread,
        ));
    }
    let templates: Vec<String> = templates.into_iter().collect::<BTreeSet<_>>().into_iter().collect();
    let unread: Vec<String> = unread.into_iter().collect::<BTreeSet<_>>().into_iter().collect();
    Gates {
        found: categorised(&walked, &scripts_from(manifest)),
        definitions: ci_pipelines::definitions(&found),
        templates,
        unread,
    }
}

/// L1.10 from the gates found.
pub fn l1_10(repo: &Path) -> Indicator {
    let found_files = ci_pipelines::find(repo);
    let source = |path: &str| ci_pipelines::text_or_empty(repo, path);
    let manifest = ci_pipelines::text_or_empty(repo, "package.json");
    let found = gates(found_files, &source, &manifest);
    let covered = found.found.len();
    Indicator {
        code: "L1.10".into(),
        label: "CI/CD pipelines".into(),
        value: covered.to_string(),
        band: band(covered as f64, 5.0, 1.0, true).into(),
        details: details(&found),
    }
}
