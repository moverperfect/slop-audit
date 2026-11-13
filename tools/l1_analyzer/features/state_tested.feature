Feature: state_tested — where a value taken from the state reaches a test its own references do not show
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. A local bound from a read of the state and then rebound before the
  # test: which binding reaches the test is a flow question this module does not ask.
  @undecidable @not-implemented
  Scenario: undecidable a local rebound to something else before the test that names it
    Given a local bound from a read of the state, rebound to an unrelated value, and then tested
    When derived_local_tested finds the test by the local's name
    Then it is recorded as a test of the state, which keeps the finding, because the reader cannot tell which binding the test reads
    But nothing is cleared on that doubt, which is the direction the carried-value rule takes

  Scenario: element_tested asks whether a loop over the reference tests the element it binds
    Given one reference to an attribute
    When element_tested finds the loop that walks it and the names its element is bound to, then reads the loop's body
    Then it is true when a reference to one of those names sits in a test expression in the body
    But a reference no loop walks, a loop whose binding this language names no field for, or a body that tests nothing, is false

  Scenario: _walking_loop finds the loop that walks a reference
    Given one reference to an attribute
    When _walking_loop climbs through wrappers and a method chain taken off the reference to the value a loop walks
    Then it returns the loop and the field that binds its element
    But anything else on the way up, or a loop walking something other than this value, gives nothing

  Scenario: derived_local_tested asks whether a local bound from a read of the reference is tested
    Given one reference to an attribute
    When derived_local_tested takes the read off it, finds the local that read is bound to, then reads the function the local lives in
    Then it is true when a reference to that local sits in a test expression, as `let v = S.get(k); if (!v)` does
    But a read bound to nothing, a member target that binds no local, or a local nobody tests is false

  Scenario: _read_of finds the whole of the read taken off a reference
    Given one reference to an attribute
    When _read_of climbs through members, a method called on it, a subscript of it, an await and transparent wrappers
    Then it returns the outermost node of that read, `S.kv.get(k)` for `S`
    But the reference handed to a call as an argument stops the climb, because that is a value given to the callee and not a read of it

  Scenario: _bound_by finds what binds a value whole to a local
    Given a value
    When _bound_by reads the declarator or assignment holding it, unwrapping Go's single-member list first
    Then it returns the declarator's name or pattern, or the assignment's target
    But a value that is not the whole of what a binding binds gives nothing

  Scenario: _names_in lists the local names a binding binds
    Given the name or pattern a binding binds
    When _names_in reads it
    Then a plain name is itself, and a destructuring pattern or a list of targets gives each name in it
    But a member target binds no local, and gives nothing

  Scenario: _enclosing_function finds the function a node sits in
    Given a node
    When _enclosing_function climbs to the nearest node of one of the language's function types
    Then it returns that function, the scope of a local bound inside it
    But a node at module level has none

  Scenario: _outermost finds the root of the tree a node sits in
    Given a node
    When _outermost climbs to the node with no parent
    Then it returns that node, the scope of a local bound at module level
    But a node with no parent is its own root

  Scenario: _within says whether one node holds another
    Given a node and a possible ancestor
    When _within climbs from the node
    Then it is true when it meets the ancestor, the node itself included
    But it is false once it runs out of parents
