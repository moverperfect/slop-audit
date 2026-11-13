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
    Then it returns the packages the manifest declares, the project's own import aliases, and empty caches for the files and parameters this run will read
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
    Given the run's project, one file's path and parse tree, and whether its helpers may be followed
    When context reads the file's imports and its top-level functions
    Then it returns them beside the project, for the argument rows to consult
    But it reads nothing outside the file it is given, and inside a helper already being read following is switched off

  Scenario: functions_in lists the functions a module declares at its top level
    Given a module's parse tree
    When functions_in reads its function declarations and its constants bound to a function
    Then each name maps to the function with a body it declares
    But a name declared twice with a body maps to nothing, because which one runs is not a question this reader answers

  Scenario: _declared_functions reads the functions one declaration binds
    Given one top-level declaration
    When _declared_functions reads it as a function declaration or as declarators bound to functions
    Then it returns each name with its function, when that function has a body
    But a declarator bound to anything else binds no function here

  Scenario: exports_in lists the functions a module exports
    Given a module's parse tree
    When exports_in reads its export statements, named, default and through an export clause
    Then each exported name maps to its function
    But a re-export from another module maps to nothing, because reading it would be a second hop

  Scenario: _exported_value finds the function a default export names
    Given the value of an export default statement and the module's own functions
    When _exported_value reads it
    Then a function with a body is itself, and a name is the module's function of that name
    But anything else exports no function this reader follows

  Scenario: _plain_callee names a call's callee when it is a plain identifier
    Given a call
    When _plain_callee reads its function field
    Then it returns the name when the callee is a plain identifier
    But a member access, a computed callee or a flat-call grammar gives nothing

  Scenario: callee_function finds the function in this repository a call reaches
    Given a call and the file's call context
    When callee_function looks up the plain-name callee among the file's own functions, then its imports
    Then a same-file function, or an import resolving to a repository file that exports a function of that name, comes back with the context its body is read in, following switched off
    But a package's callee, a namespace import, an import that resolves to nothing and a re-export all come back as nothing, and the call keeps its silence

  Scenario: _tree parses one repository file once per run
    Given a path in the repository and the run's project
    When _tree is asked for its parse tree
    Then the file is parsed once and the tree kept for the rest of the run
    But a file that cannot be read, or parses with an error, is nothing, because a body the reader cannot parse is not read

  Scenario: _source reads one file's bytes
    Given a path
    When _source reads it
    Then it returns the file's bytes
    But a file that cannot be read gives nothing, and the helper in it is not followed

  Scenario: _parsed parses one file's bytes
    Given a file's bytes, its suffix and the run's language
    When _parsed parses them with the grammar for that suffix
    Then it returns the parse tree
    But a tree the grammar reports an error in gives nothing, because a body the reader cannot parse is not read

  Scenario: candidates lists every file an import could name
    Given an import specifier, the importing file and the run's project
    When candidates builds paths relative to the importer or through the project's aliases, as written, with each source suffix and as a directory's index
    Then it returns them in the order a bundler tries them
    But never a path under node_modules or outside the repository, and it asks nothing of the disk

  Scenario: _first_on_disk finds which candidate exists
    Given a list of paths
    When _first_on_disk asks the filesystem about each in turn
    Then it returns the first that is a file
    But it returns nothing when none is, and the import resolves to nothing

  Scenario: parameter names the parameter a function binds an argument to
    Given a function and an argument position
    When parameter reads that position's parameter, through a type or a default
    Then it returns the one name the argument is bound to
    But a destructured parameter, a rest parameter or a position the function does not take gives nothing

  Scenario: binds says whether a function takes a parameter of a name
    Given a function and a name
    When binds reads each of its parameters
    Then it answers yes when one of them is that name, so a reference to the name inside it means its own parameter
    But a function that takes no such parameter answers no

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
