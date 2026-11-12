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

  Scenario: find counts every pipeline definition file in the repository by the system that runs it
    Given a repository
    When find looks in .github/workflows, at the root for .gitlab-ci.yml and a Jenkinsfile, and through the tree for Azure Pipelines YAML
    Then it returns how many definitions each system has, and how many Azure templates were set aside
    And GitHub's count is read exactly as it was before the other systems were added, so a GitHub repository's figure does not move
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

  Scenario: count gives the number L1.10 publishes
    Given what find returned
    When count adds the definitions from every system
    Then it returns their total, which the canon's bands are applied to unchanged
    But the Azure templates are not in it, because a template is a piece of a pipeline and not a definition of one

  Scenario: details says what was found where, or every place that was looked in
    Given what find returned
    When details writes the sentence beside the number
    Then it names each system that had a definition and how many, and how many Azure templates were not counted
    And a repository with GitHub workflows alone reads the sentence it always did
    But a repository with none names all four places it looked, so a zero says where it is a zero
