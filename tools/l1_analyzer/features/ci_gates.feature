Feature: ci_gates — which gate categories a repository's CI/CD pipelines cover, for L1.10
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. A step that runs a command the table does not name, such as a
  # repository's own script, runs something this module cannot see into.
  @undecidable @not-implemented
  Scenario: undecidable a step that runs a script the gate table has no entry for
    Given a pipeline step that runs ./scripts/check.sh, a Makefile target other than test, check or lint, or a tool the table does not list
    When covers matches the step's command against the table and finds nothing
    Then it is recorded as a step this module could not classify rather than as one that runs no gate, so a missing category means looked-and-absent and never could-not-tell
    But nothing is credited on a guess from the step's name or the script's file name

  Scenario: _compiled builds one pattern for a list of commands
    Given a list of command patterns
    When _compiled joins them
    Then each matches only as a whole word, so vitest matches in npx vitest run and in a node_modules bin path
    But not inside a longer name such as my-vitest-helper

  Scenario: read reads every pipeline definition in a repository for the gates it runs
    Given a repository
    When read finds the definitions and hands their text, and the root package.json, to gates
    Then it returns the categories covered, with the files each was seen in
    But it reads a file only when a definition names it

  Scenario: gates collects the steps of every definition from every system
    Given the definitions found, a way to read a file by its path, and the package.json text
    When gates walks GitHub, GitLab, Jenkins and Azure definitions in turn
    Then it returns each category covered with its files, the definitions read, the templates followed and the template references it could not read
    But a template is read only where a definition includes it, never as a pipeline of its own

  Scenario: categorised turns steps into the categories they cover
    Given the steps, in order, and the package.json scripts
    When categorised reads them job by job
    Then it returns each category with the files of the steps that cover it, in the canon's order
    And a browser run after a deploy in the same job is post-deploy verification
    But the same run in a job with no deploy and no deployed address is a test

  Scenario: covers decides the categories one step covers from what it runs
    Given one step and whether a deploy ran earlier in its job
    When covers matches a script against the command table, a task against the task table, or an action against the action table
    Then it returns every category matched, a declared deployment being a deploy
    And a browser, end-to-end, load or health run against a deployed environment is post-deploy verification
    But a step's name is never read, and a command the table does not know covers nothing

  Scenario: expanded writes a step's script as it runs
    Given a script and the package.json scripts
    When expanded drops comment and echo-only lines and replaces package-manager calls by the scripts they run
    Then pnpm run lint:strict reads as the oxlint command it runs, a few calls deep
    But an echo-only script expands to nothing, which is the canon's echo-only placeholder pipeline

  Scenario: _script_body gives the command a package-manager call runs
    Given one package-manager call and the package.json scripts
    When _script_body looks the called name up
    Then a call to a script is that script's command, pnpm, yarn and bun running any script bare
    But npm runs a bare name only for its lifecycle scripts, and a name that is no script stays the call it is

  Scenario: _scripts reads a package.json's scripts
    Given the text of a package.json
    When _scripts parses it
    Then it returns each script's command by name
    But a manifest that does not parse, or has no scripts, has none

  Scenario: _loaded reads a YAML document
    Given a file's text
    When _loaded parses it safely
    Then it returns the document
    But YAML that does not parse, or no text, is nothing, so a file this reader cannot read credits no gate

  Scenario: names_a_url says whether values hand over a deployed address
    Given parameters, variables or env values, as a mapping or as Azure's name and value list
    When names_a_url reads each name and value
    Then a value that is an http or https URL, or a non-empty value under a name ending in url, is an address
    But anything else is not

  Scenario: _relative resolves a referenced file to its path from the root
    Given the referring file's path and a reference
    When _relative resolves it from the referring file's directory, or from the root for a path starting with a slash
    Then it returns the normalised path
    But a path leaving the repository is nothing

  Scenario: _azure reads the steps one Azure file runs
    Given an Azure file, the parameters passed to it, and the job it runs in
    When _azure lays the passed values over the template's defaults and writes each scalar into the template's parameter expressions
    Then pnpm run with a parameter for the script reads as the script it names, and its steps are walked in order
    But a list or mapping value is left as the expression, because no text can stand for it

  Scenario: _azure_node walks one node of an Azure document for its steps
    Given a node, where it sits, and how deep the template chain is
    When _azure_node follows templates, reads scripts and tasks, and opens a new job at each job or deployment
    Then it returns every step in order, a deployment job with an environment first declaring its deployment
    But a template in another repository or built from an expression is recorded as unread and not followed

  Scenario: _azure_task reads an Azure task and the script it carries
    Given a task step
    When _azure_task reads its name and inputs
    Then it returns the task, and any inline script, dotnet command, Docker build or npm command it runs as a script step
    But a task the table does not name contributes only what its scripts run

  Scenario: _defaults reads a template's parameter defaults
    Given a template's parameters block
    When _defaults reads either spelling Azure accepts
    Then it returns each parameter's default by name
    But a parameter with no default has none

  Scenario: _scalar writes a parameter value into template text
    Given a parameter value and the expression it replaces
    When _scalar converts it
    Then a scalar is its text
    But a missing value, a list or a mapping leaves the expression unchanged

  Scenario: _step builds one step
    Given where a step sits, its kind, its text and whether it is handed an address
    When _step records it
    Then it carries its file, its job, its kind and its text
    But a step in a job handed an address is handed it too

  Scenario: _github reads the steps one GitHub workflow runs
    Given a workflow
    When _github reads each job's steps
    Then it returns them in order, a job with an environment declaring its deployment
    But a file with no jobs runs nothing

  Scenario: _github_steps reads a GitHub step list
    Given a list of steps
    When _github_steps reads each run and uses step
    Then a run is a script, an action is its owner and name, and a local composite action is read in place
    But the action's version is dropped, because the table names actions and not their releases

  Scenario: _composite reads a local composite action's steps
    Given a local action reference
    When _composite reads its action.yml or action.yaml
    Then it returns the steps the action runs
    But an action that cannot be read runs nothing this reader can see

  Scenario: _gitlab reads the scripts every GitLab job runs
    Given a .gitlab-ci.yml
    When _gitlab reads each job's before_script, script and after_script, with the defaults and the jobs it extends
    Then it returns them in order, a job with an environment declaring its deployment
    But a hidden job runs only where another job extends it

  Scenario: _gitlab_document merges a GitLab file with its local includes
    Given a GitLab file
    When _gitlab_document reads each local include beneath it
    Then it returns one document, the including file winning
    But a remote or project include is not read

  Scenario: _extended lays the jobs a GitLab job extends beneath it
    Given a job and the document it is in
    When _extended reads its extends names
    Then it returns the job with each extended job's keys beneath its own
    But it reads one level, which is how far a hidden job usually sits

  Scenario: _flattened reads a GitLab script
    Given a script as a string, a list or nested lists
    When _flattened flattens it
    Then it returns each line in order
    But anything else is no script

  Scenario: _jenkins reads a Jenkinsfile's shell steps
    Given a Jenkinsfile's text
    When _jenkins finds each sh, bat, powershell and pwsh step
    Then it returns their scripts in order as one job
    But a step built in Groovy code rather than written as a string is not read

  Scenario: reading turns the gates found into L1.10
    Given the gates found
    When reading counts the categories covered
    Then the value is that count, 5 or 6 Healthy, 1 to 4 Not Healthy and 0 Slop
    But the count is of categories, never of files, stages or jobs

  Scenario: details writes the sentence beside the number
    Given the gates found
    When details names each category with its files and what is missing
    Then it says how many definitions were read and how many templates they include, and that names are never read
    But a repository with no definition names all four places it looked, so a zero says where it is a zero
