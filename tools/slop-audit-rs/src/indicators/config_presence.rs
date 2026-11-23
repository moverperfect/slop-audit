//! L1.9-L1.11 config presence (language-agnostic file/dir existence checks). Ported from
//! l1_analyzer.indicators.compute_config_indicators; validated equal.
//!
//! Shape: L1.9 asks whether a path exists at the repository root.
//!   present_at(repo, PRECOMMIT) -> pre-commit hooks   (present/absent -> Healthy/Slop)
//!   l1_10(repo)                 -> CI/CD pipelines    (gate categories, see ci_gates)
//!   l1_11(repo)                 -> containerization   (present, Wrangler n/a, or absent)

use crate::Indicator;
use std::path::Path;


/// One indicator that asks whether any of a set of paths exists at the repository root.
pub struct Presence {
    pub code: &'static str,
    pub label: &'static str,
    pub paths: &'static [&'static str],
    pub present_value: &'static str,
    pub present_details: &'static str,
    pub absent_details: &'static str,
}

/// L1.9 pre-commit hooks: a `.pre-commit-config.yaml` file or a `.husky` dir at the root.
pub const PRECOMMIT: Presence = Presence {
    code: "L1.9",
    label: "pre-commit hooks",
    paths: &[".pre-commit-config.yaml", ".husky"],
    present_value: "present",
    present_details: "a pre-commit hook config is present",
    absent_details: "no .pre-commit-config.yaml and no .husky directory at the repository root",
};

/// L1.11 containerization: a `Dockerfile` or `docker-compose.yml` file at the root.
pub const CONTAINER: Presence = Presence {
    code: "L1.11",
    label: "containerization",
    paths: &["Dockerfile", "docker-compose.yml"],
    present_value: "present and parameterized",
    present_details: "a Dockerfile or docker-compose.yml is present at the repository root",
    absent_details: "no Dockerfile and no docker-compose.yml at the repository root",
};

/// Both rows read by one body. These shipped a band and a value with no sentence, in both
/// tools, until the reference's result type was made total on 2026-08-19. A reader got Slop
/// with nothing saying what was looked for or where.
pub fn present_at(repo: &Path, what: &Presence) -> Indicator {
    let found = what.paths.iter().any(|p| repo.join(p).exists());
    Indicator {
        code: what.code.into(),
        label: what.label.into(),
        value: (if found { what.present_value } else { "absent" }).into(),
        band: (if found { "Healthy" } else { "Slop" }).into(),
        details: (if found { what.present_details } else { what.absent_details }).into(),
    }
}

/// L1.10 CI/CD pipelines: the gate categories the repository's pipelines cover.
pub fn l1_10(repo: &Path) -> Indicator {
    crate::indicators::ci_gates::l1_10(repo)
}

const WRANGLER_CONFIGS: &[&str] = &["wrangler.toml", "wrangler.json", "wrangler.jsonc"];

/// L1.11 containerization: a Dockerfile or compose file at the root, or n/a when the
/// root holds a Wrangler config and no container file, because that target runs none.
pub fn l1_11(repo: &Path) -> Indicator {
    if CONTAINER.paths.iter().any(|p| repo.join(p).exists()) {
        return present_at(repo, &CONTAINER);
    }
    if let Some(name) = WRANGLER_CONFIGS.iter().copied().find(|n| repo.join(n).exists()) {
        return Indicator {
            code: CONTAINER.code.into(),
            label: CONTAINER.label.into(),
            value: "n/a".into(),
            band: "n/a".into(),
            details: format!(
                "{name} at the repository root deploys this app with Wrangler to Cloudflare \
                 Workers or Pages, which runs no container, so containerization does not apply \
                 to this deployment target"
            ),
        };
    }
    present_at(repo, &CONTAINER)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn scratch(name: &str) -> std::path::PathBuf {
        let root = std::env::temp_dir().join(format!("slop-{name}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(&root).unwrap();
        root
    }

    #[test]
    fn a_wrangler_config_without_a_container_reads_not_applicable() {
        let root = scratch("wrangler");
        fs::write(root.join("wrangler.toml"), "name = 'site'\n").unwrap();
        let row = l1_11(&root);
        assert_eq!(row.value, "n/a");
        assert_eq!(row.band, "n/a");
        assert!(row.details.contains("wrangler.toml"));
        assert!(row.details.contains("does not apply"));
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn one_pipeline_covering_every_gate_is_healthy() {
        let root = scratch("gates");
        fs::create_dir_all(root.join(".github/workflows")).unwrap();
        fs::write(
            root.join(".github/workflows/ci.yml"),
            concat!(
                "on: push\n",
                "jobs:\n",
                "  ci:\n",
                "    runs-on: ubuntu-latest\n",
                "    steps:\n",
                "      - uses: actions/checkout@v4\n",
                "      - run: npm ci\n",
                "      - run: npx tsc --noEmit\n",
                "      - run: npx vitest run\n",
                "      - run: npm audit --audit-level=high\n",
                "      - run: npx vite build\n",
                "  deploy:\n",
                "    runs-on: ubuntu-latest\n",
                "    steps:\n",
                "      - run: npx wrangler deploy\n",
                "      - run: npx playwright test --project=smoke\n",
            ),
        )
        .unwrap();
        let row = l1_10(&root);
        assert_eq!(row.value, "6");
        assert_eq!(row.band, "Healthy");
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn an_echo_only_pipeline_is_slop() {
        let root = scratch("echo");
        fs::create_dir_all(root.join(".github/workflows")).unwrap();
        fs::write(
            root.join(".github/workflows/ci.yml"),
            concat!(
                "on: push\n",
                "jobs:\n",
                "  build:\n",
                "    name: Build and test\n",
                "    steps:\n",
                "      - name: Run tests\n",
                "        run: echo \"tests passed\"\n",
            ),
        )
        .unwrap();
        let row = l1_10(&root);
        assert_eq!(row.value, "0");
        assert_eq!(row.band, "Slop");
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn a_jenkinsfile_is_read_for_the_command_it_runs() {
        let root = scratch("jenkins");
        fs::write(
            root.join("Jenkinsfile"),
            "pipeline { stages { stage('Lint') { steps { sh 'ruff check .' } } } }\n",
        )
        .unwrap();
        let row = l1_10(&root);
        assert_eq!(row.value, "1");
        assert!(row.details.contains("static checks (Jenkinsfile)"));
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn a_quoted_github_expression_does_not_drop_the_workflow() {
        let root = scratch("quoted-expr");
        fs::create_dir_all(root.join(".github/workflows")).unwrap();
        fs::write(
            root.join(".github/workflows/ci.yml"),
            concat!(
                "on: push\n",
                "jobs:\n",
                "  t:\n",
                "    env:\n",
                "      TOKEN: \"${{ secrets.TOKEN }}\"\n",
                "    steps:\n",
                "      - run: pytest -q\n",
            ),
        )
        .unwrap();
        let row = l1_10(&root);
        assert_eq!(row.value, "1");
        assert!(row.details.contains("test (.github/workflows/ci.yml)"));
        let _ = fs::remove_dir_all(&root);
    }
}
