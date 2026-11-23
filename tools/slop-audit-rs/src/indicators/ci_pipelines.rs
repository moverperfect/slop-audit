//! Finding the files in a repository that define a CI/CD pipeline, for L1.10.
//!
//! Port of l1_analyzer.ci_pipelines. L1.10 reads what those pipelines run (ci_gates);
//! this module finds them. GitHub workflows sit in `.github/workflows`; GitLab and
//! Jenkins each have one file at the root; Azure Pipelines has no fixed path.

use crate::in_ignored_dir;
use regex::Regex;
use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

const AZURE_DIRS: &[&str] = &["pipelines", ".azure-pipelines"];

fn azure_top_level() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?m)^(?:trigger|pr|schedules|resources|stages|jobs|steps|extends)\s*:").unwrap())
}

fn template_ref() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(r#"(?m)^\s*(?:-\s*)?template:\s*['"]?([^'"\s#@$]+)['"]?\s*(?:#.*)?$"#).unwrap()
    })
}

/// The pipeline definitions found, by the system that runs them.
#[derive(Default)]
pub struct Pipelines {
    pub github: Vec<String>,
    pub gitlab: Vec<String>,
    pub jenkins: Vec<String>,
    pub azure: Vec<String>,
    pub azure_templates: Vec<String>,
}

/// Every pipeline definition file in the repository, by system.
pub fn find(repo: &Path) -> Pipelines {
    let (azure, azure_templates) = azure_pipeline_definitions(&azure_candidates(repo));
    Pipelines {
        github: github_workflows(repo),
        gitlab: if repo.join(".gitlab-ci.yml").is_file() {
            vec![".gitlab-ci.yml".into()]
        } else {
            vec![]
        },
        jenkins: if repo.join("Jenkinsfile").is_file() {
            vec!["Jenkinsfile".into()]
        } else {
            vec![]
        },
        azure,
        azure_templates,
    }
}

/// Every pipeline definition found, from every system, in a fixed order.
pub fn definitions(found: &Pipelines) -> Vec<String> {
    let mut out = Vec::new();
    out.extend(found.github.iter().cloned());
    out.extend(found.gitlab.iter().cloned());
    out.extend(found.jenkins.iter().cloned());
    out.extend(found.azure.iter().cloned());
    out
}

fn github_workflows(repo: &Path) -> Vec<String> {
    let dir = repo.join(".github").join("workflows");
    let Ok(entries) = std::fs::read_dir(&dir) else {
        return Vec::new();
    };
    let mut names: Vec<String> = entries
        .filter_map(Result::ok)
        .filter_map(|e| {
            let name = e.file_name();
            let s = name.to_string_lossy();
            if s.ends_with(".yml") || s.ends_with(".yaml") {
                Some(format!(".github/workflows/{s}"))
            } else {
                None
            }
        })
        .collect();
    names.sort();
    names
}

fn azure_candidates(repo: &Path) -> HashMap<String, String> {
    let mut found = HashMap::new();
    for entry in crate::walk_repo(repo) {
        let path = entry.path();
        let Some(name) = path.file_name().and_then(|n| n.to_str()) else {
            continue;
        };
        let lower = name.to_lowercase();
        if !(lower.ends_with(".yml") || lower.ends_with(".yaml")) {
            continue;
        }
        if in_ignored_dir(path) {
            continue;
        }
        let Ok(rel) = path.strip_prefix(repo) else {
            continue;
        };
        let relative = posix(rel);
        let parent_hit = rel
            .parent()
            .map(|p| {
                p.components().any(|c| {
                    c.as_os_str()
                        .to_str()
                        .map(|s| AZURE_DIRS.contains(&s))
                        .unwrap_or(false)
                })
            })
            .unwrap_or(false);
        if lower.starts_with("azure-pipelines") || parent_hit {
            let text = std::fs::read_to_string(path).unwrap_or_default();
            found.insert(relative, text);
        }
    }
    found
}

fn azure_pipeline_definitions(files: &HashMap<String, String>) -> (Vec<String>, Vec<String>) {
    let mut included: HashSet<String> = HashSet::new();
    for (path, text) in files {
        let directory = parent_posix(path);
        for cap in template_ref().captures_iter(text) {
            let reference = cap.get(1).map(|m| m.as_str()).unwrap_or("");
            let target = if reference.starts_with('/') {
                reference.trim_start_matches('/').to_string()
            } else if directory.is_empty() {
                reference.to_string()
            } else {
                posixpath_join(&directory, reference)
            };
            included.insert(posixpath_norm(&target));
        }
    }
    let mut definitions: Vec<String> = files
        .iter()
        .filter(|(path, text)| {
            !included.contains(*path)
                && (file_name_posix(path).to_lowercase().starts_with("azure-pipelines")
                    || azure_top_level().is_match(text))
        })
        .map(|(path, _)| path.clone())
        .collect();
    definitions.sort();
    let mut templates: Vec<String> = files.keys().filter(|p| included.contains(*p)).cloned().collect();
    templates.sort();
    (definitions, templates)
}

fn posix(path: &Path) -> String {
    path.components()
        .filter_map(|c| c.as_os_str().to_str())
        .collect::<Vec<_>>()
        .join("/")
}

fn parent_posix(path: &str) -> String {
    match path.rsplit_once('/') {
        Some((parent, _)) => parent.to_string(),
        None => String::new(),
    }
}

fn file_name_posix(path: &str) -> &str {
    path.rsplit_once('/').map(|(_, name)| name).unwrap_or(path)
}

pub(crate) fn posixpath_join(base: &str, child: &str) -> String {
    if base.is_empty() {
        child.to_string()
    } else {
        format!("{base}/{child}")
    }
}

pub(crate) fn posixpath_norm(path: &str) -> String {
    let mut out: Vec<&str> = Vec::new();
    for part in path.split('/') {
        match part {
            "" | "." => {}
            ".." => {
                out.pop();
            }
            other => out.push(other),
        }
    }
    out.join("/")
}

pub(crate) fn relative_from(base: &str, reference: &str) -> String {
    let target = if reference.starts_with('/') {
        posixpath_norm(reference.trim_start_matches('/'))
    } else {
        posixpath_norm(&posixpath_join(&parent_posix(base), reference))
    };
    if target.starts_with("..") {
        String::new()
    } else {
        target
    }
}

/// Read a file under `repo` as text, or empty when it cannot be read.
pub fn text_or_empty(repo: &Path, relative: &str) -> String {
    let mut path = PathBuf::from(repo);
    for part in relative.split('/') {
        if !part.is_empty() {
            path.push(part);
        }
    }
    std::fs::read_to_string(path).unwrap_or_default()
}
