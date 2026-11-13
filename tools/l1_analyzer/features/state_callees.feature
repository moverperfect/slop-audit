Feature: state_callees — where a plain-name callee lives, for the state reader's argument rows
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. An import whose specifier this module cannot place, a package the
  # manifest does not declare or a scheme no package provides, stays where it was.
  @undecidable @not-implemented
  Scenario: undecidable an import this module cannot place in a package or in the project
    Given a call to a name imported from a specifier no declared package, Node module or project alias accounts for
    When the argument rows ask whether the callee is a package's
    Then it is recorded as unread under the reason it already had rather than moved to the adopter's boundary, so an external boundary means code this reader knows it cannot open
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: project reads what one run needs to know about the repository
    Given a repository and a language
    When project reads the repository's package.json and tsconfig.json
    Then it returns the packages the manifest declares and the project's own import aliases
    But for a language whose module system this module does not read it returns nothing, and every callee keeps the silence it had

  Scenario: packages_in lists every package a manifest declares
    Given the text of a package.json
    When packages_in reads its dependencies, devDependencies, peerDependencies and optionalDependencies
    Then it returns every package name across the four tables
    But a manifest that does not parse declares nothing, which leaves every import the project's

  Scenario: _aliases reads the project's import aliases from its tsconfig
    Given the repository root
    When _aliases reads compilerOptions.paths, following extends through files in the repository
    Then each alias comes back as the prefix it matches and the directories it maps to, resolved from baseUrl or from the config's own directory
    But it never follows an extends into node_modules, and a config with no paths gives no aliases

  Scenario: _config reads a tsconfig as data
    Given the text of a tsconfig, which may carry comments and trailing commas
    When _config removes both outside strings and parses what is left
    Then it returns the configuration as a mapping
    But a file that still does not parse says nothing rather than raising

  Scenario: _without_trailing_commas drops the comma before a closing bracket
    Given JSON text with its comments already removed
    When _without_trailing_commas looks at each comma before a closer
    Then a comma followed only by whitespace and the closer is removed
    But every other comma is left where it is

  Scenario: context makes one file's calls readable
    Given the run's project and one file's parse tree
    When context reads the file's imports
    Then it returns them beside the project, for the argument rows to consult
    But it reads nothing outside the file it is given

  Scenario: imports_in lists what an ES module imports
    Given a module's parse tree
    When imports_in reads its import statements
    Then each local name maps to the specifier and the name it was imported as, default for a default import and a star for a namespace
    But a statement with no source is skipped

  Scenario: imported_from_a_package says whether a call's callee is a package's
    Given a call and the file's call context
    When imported_from_a_package looks up the callee's plain name among the file's imports
    Then it answers yes when that import names a declared package or one of Node's own modules
    But a callee that is not a plain name, or a name the file does not import, answers no

  Scenario: is_external decides whether a specifier names code under node_modules or Node's own
    Given an import specifier and the run's project
    When is_external compares it with the project's aliases, Node's modules and the manifest's packages
    Then a node: specifier, a bare Node module and a declared package are external
    But a path, or a specifier one of the project's own aliases matches, is the project's whatever its name looks like

  Scenario: package_of names the package a bare specifier imports from
    Given a bare import specifier
    When package_of takes its leading segments
    Then a scoped specifier names its scope and package, any other names its first segment, and a bundler's virtual module names the package before its colon
    But it says nothing about whether that package is declared, which is is_external's question
