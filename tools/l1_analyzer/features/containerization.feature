Feature: containerization — whether a repository ships a container config, or deploys somewhere none applies, for L1.11
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. A deployment target named somewhere other than a root Wrangler
  # config leaves nothing at the root this module reads.
  @undecidable @not-implemented
  Scenario: undecidable a serverless deployment named by a config this module does not read
    Given a repository deployed to a serverless platform other than Cloudflare, such as Vercel, Netlify or AWS SAM, with no container file
    When find looks at the root for container files and Wrangler configs and finds neither
    Then it is recorded as a target this module has no rule for rather than as the absent container a repository that should ship one receives, so Slop means a container was due and never could-not-tell
    But nothing is decided on a guess about which file proves a target, because each platform is a decision of its own

  Scenario: find looks at the repository root for container files and Wrangler configs
    Given the repository root
    When find checks for a Dockerfile, a docker-compose.yml and each Wrangler config by name
    Then it returns whether any container file is there and which Wrangler configs are, in the order they are looked for
    But it looks at the root only, so a config kept in a subdirectory is not the repository's deployment

  Scenario: reading turns what the root holds into L1.11
    Given whether a container file is at the root and which Wrangler configs are
    When reading decides the row
    Then a container file reads present and Healthy, whatever else is there
    And a Wrangler config with no container file reads n/a, with a sentence naming the config and saying containerization does not apply to that deployment target
    But neither reads absent and Slop, as L1.11 always has
