Feature: ci_pipelines — finding the files that define a repository's CI/CD pipelines, for L1.10
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. A pipeline defined in the CI service rather than in the repository
  # leaves nothing in the tree to read.
  @undecidable @not-implemented
  Scenario: undecidable a pipeline defined in the CI service rather than in the repository
    Given a repository built by a classic Azure DevOps release or a Jenkins job configured in its web interface, with no definition file in the tree
    When find walks the repository for pipeline definition files
    Then it is recorded as unread rather than as the zero a repository with no pipeline receives, so a count means looked-and-found and never could-not-see
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: find lists every pipeline definition file in the repository by the system that runs it
    Given a repository
    When find looks in .github/workflows, at the root for .gitlab-ci.yml and a Jenkinsfile, and through the tree for Azure Pipelines YAML
    Then it returns each system's definitions as paths from the root, and the Azure files set aside as templates
    And ci_gates reads what each definition runs, so finding a file and crediting it are separate questions
    But a GitLab or Jenkins file anywhere but the root is not read, because the root is where both look

  Scenario: _azure_candidates reads every YAML file that could be an Azure pipeline
    Given a repository
    When _azure_candidates walks it for .yml and .yaml files through the shared walk
    Then it returns each file named azure-pipelines-something, or sitting under a pipelines or .azure-pipelines directory, with its text
    But a gitignored or vendored tree is not read, because the shared walk and the vendored list already decline it

  Scenario: azure_pipeline_definitions separates pipeline definitions from the templates they include
    Given the candidate files' paths and texts
    When azure_pipeline_definitions resolves every template reference, from the including file's directory or from the root for a path starting with a slash
    Then a file another candidate includes is a template whatever its keys say
    And of the rest, a file named azure-pipelines-something is a definition, and so is one that opens a pipeline key at its top level
    But a reference into another repository or built from an expression names no file here and is not followed

  Scenario: definitions lists every pipeline definition found, from every system
    Given what find returned
    When definitions puts the systems' definitions in one list
    Then it returns GitHub's, GitLab's, Jenkins's and Azure's, in that order
    But the Azure templates are not in it, because a template is read where a definition includes it
