# Changelog

All notable changes to ForgeMind are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- A refused request now carries the cross-origin header. The middleware
  order had the credential check outside the cross-origin handling, so a
  refusal never reached it and the response carried no allowed-origin
  header — the browser reported a cross-origin error and hid the real
  reason (the credentials). The cross-origin handling now sits outermost,
  and a refusal says what is wrong.

### Fixed
- The total equity now has one basis. Equity can be read two ways: cash
  plus the cost of the holdings, and cash plus what they are worth. The
  interface used the second, the decision used the first — so as soon as
  a position moved away from its cost, the same "total equity" was two
  different numbers, and the size the agent worked out did not match
  what the user could see. The difference was the whole unrealized
  gain or loss. With the position back at its cost the two agreed,
  which is why no test ever saw it.
  The decision, the HTTP endpoint and the MCP tool now all use the
  market value, taken from the real prices in the library. Where a
  price is missing they stay on the cost basis as a whole — half at
  market value and half at cost is harder to read than either — and the
  report says which basis was used.

- The current weight is now read at market value as well. The equity
  moved to the market value, but the weight still took the cost of the
  holdings as its numerator: two bases in one fraction, so a position
  that moved away from its cost pushed the weight up and the size of the
  order with it. The size now follows the identity that holds under
  either base — the order is the difference between the target value
  and the current value, divided by the price.

### Added
- The Release page is rewritten on every publish. It names the version
  that was just published, lists the artifacts that are actually
  downloadable, and links to the changelog. It used to keep the text
  from the moment the release was created, and the text of the older
  release quoted a backtest result that no longer held.
- Every command the CLI offers is now mentioned in the README, and every
  file the README points at exists. A checker keeps both true: a command
  that exists but is nowhere in the documentation is a door nobody can
  find, and a path that does not exist is a link that opens on a 404.
- The source tree, the tests, the interface and the workflows that gate
  them now live in this repository. It is the only source of truth, the
  only gate and the only release surface; the private repository holds a
  copy of it and nothing else.
- A workflow runs the whole test suite against the published wheel rather
  than against the source tree. It waits for the release to finish and
  checks that the published artifact was built from the commit under
  test, so the tests and the artifact are of the same generation.
- The import target of the test suite is decided in one place. The suite
  no longer puts the source tree in front of the import path when it is
  supposed to test the installed package, and the subprocesses it spawns
  inherit the same decision instead of quietly reverting to the source.
- The strategy list says which strategies the command can run and which
  ones it cannot, with the reason for each. A strategy that exists but
  cannot run is no longer reported as an unknown strategy — the same
  command gave two different answers to the same question, and the
  reader could not tell which one to believe.
- A checker runs the commands and compares their exit codes with the
  table in the README. That table is a promise to the reader, and
  nothing was keeping it true.
- The research example has tests of its own. It had none, and the option
  that makes it useful for a program was broken.

- A checker runs every MCP tool with legal arguments and scans what
  comes back for exception class names, SQL fragments, stack traces and
  local paths. The prompts and the resources are scanned the same way: their
  text reaches the model just as directly as a tool result does.
- A checker runs the commands in several states and compares what they say
  with what they should say. It covers the state where the local store
  cannot be written to, and it covers `etl` while the store is locked.

### Fixed
- The full-scale concurrency tier runs again. A refactor had removed the
  step that executes it, so the workflow checked out the source, read the
  manifest and reported success without running a single case. The first
  real run found four cases that still expected the command to run
  multi-symbol strategies on a single symbol; the command refuses them on
  purpose, and the cases now say so.
- The workflow that runs the tests against the published wheel was
  measuring the source tree. Scripts inserted the repository root into
  the import path when they were imported, so the import found the
  source instead of the installed package — and the job passed while
  checking nothing it claimed to check.
- `scripts/research_demo.py --json` did not work. It crashed on the
  numpy types in the result, its standard output carried the log lines,
  and a value that could not be computed was written as `NaN`, which is
  not valid JSON.
- The exit code table in the README did not match the commands. An
  interrupted run exits with 130, a refused approval exits with 2, and
  an argument error exits with 2 as well — the table said 1 and 5+.
- A release could be triggered from any branch. A push to a branch that
  nobody had reviewed would publish it and point the index at it, so
  `pip install` would hand that code to whoever came for it.
- The shell declaration checker reported success when it was run from
  the wrong directory: it found no workflow files and had nothing to
  complain about. It now resolves the path from its own location and
  treats an empty set as a failure.
- The manifest named the frozen private repository as the source of the
  published artifacts.
- The ETL exited with 1 when it finished without fetching a single row
  and had no failure to classify. One means "the approval was refused",
  so the same code covered two unrelated situations, and the table in the
  README could not tell the reader which one had happened.
- A release now fails when the live index does not switch to the new
  build. The index is published by the Pages deployment: when that
  deployment fails, the CDN still serves the old index and users install
  the previous version. The assets were uploaded and the manifest was
  written, so everything looked done, and the release reported success.
- The backtest said "no symbol was given" while the user had given one.
  Both the case where a symbol was passed and the case where it was not
  fell into the same branch, and the branch printed the wording of the
  second one, so the message contradicted the command line in front of
  the reader and pointed them at the wrong next step.
- The research endpoint reports the metrics of the same run that produced
  the signals. The figures came from a random walk of its own while the
  signals came from the research pipeline, so the two halves of one
  answer described two different things.
- The source tree passes the code quality checks the workflow runs, and
  those checks now stop the workflow instead of being reported and
  ignored. The test tree is still reported only; rewriting several
  hundred test files at once would bury the real changes.
- The architecture diagram no longer describes the backtest engine as
  vectorized. It replays the bars one by one to fill the orders and
  compound the equity curve, and the wording pointed at a different
  mental model. The diagram is also aligned now, and the two
  repositories describe the engine the same way.
- An upgraded database no longer keeps a second index on the same columns.
  Older versions created it under a different name, so an upgraded database
  ended up with two of them and every write paid for both.
- The desktop interface now says when it could not reach the backend
  instead of showing an empty panel. An empty panel has two very different
  causes — there is no data, or the data could not be fetched — and the
  interface used to show the same message for both, so a broken backend
  looked like a quiet database.
- Two workflow files could not be parsed at all. A quoted value that
  continued on the next line with the shell operator at the start of that
  line is not valid, so the lint job had been failing to read its own
  configuration; the private repository's own pipeline has not been
  running since the account hit its billing limit, which is why nobody
  noticed.
- The desktop interface reports why a request failed instead of leaving the
  panel empty. One of the two ways the factor list was fetched dereferenced
  a missing value and raised, so the reason never reached the screen; the
  panel looked the same whether there was no data or the backend could not
  be reached.
- The workflow checker now asks the shell whether each inline script is
  valid. Broken quoting and a stray continuation line are invisible in
  the file, and the step only failed when the pipeline reached it.
- The spell check now runs for real. The step passed an option that the
  tool does not have, so it failed on the option and the failure was
  swallowed; the check had never examined a single word. The option is
  gone, the step stops the run when it finds something, and the list of
  ignored words was cut down to the one word that actually needs it.
- Fetching data is bounded even when the connection itself hangs. The
  socket timeout covers a server that accepts the connection and then
  stays silent, but it does not cover a name lookup or a connect that
  never returns; those now meet a hard wall, so a stuck upstream delays
  the run instead of hanging it.
- The macro data source is real now. It used to refuse to do anything and
  say so, while the documentation promised Chinese macro data. It reads
  the public interfaces: the manufacturing purchase managers index, the
  consumer and producer price indices, the broad money supply, the ten
  year government bond yield and the exchange rate. A monthly indicator
  takes effect from the day it is published and holds until the next
  release; an indicator that cannot be fetched is left empty rather than
  filled with something else.
- The numbers the data pipeline reports now say which run they belong to.
  The stock count and the bar count were read back from the database, so
  they kept growing with every run and the last run's data was reported
  as this run's work. The count of this run and the count in the table are
  now reported separately.
- The stock list is fetched from more than one source. The aggregate
  interface is refused on some networks, which left the table of all
  listed companies empty. The exchanges' own lists are used as a fallback
  and the ones that answer are merged, because the list of one exchange
  is not the whole market. The report names the sources it used.
- The check of the published artifact no longer fails on a network hiccup.
  A refused connection or a dropped handshake is not a verdict about the
  artifact, so the download is retried a few times before it is called a
  failure.
- The result table of the end to end pipeline is aligned from now on. The
  frame used to be padded by hand, which made the right hand border wander
  off; the factor, feature and signal rows were not framed at all and
  printed outside the box. The frame is now measured from its content, so
  every line lines up whatever the values are. The heading shows the
  version of the package that is running instead of a release number that
  had nothing to do with it.
- The version number is now checked in one place. It is written both in
  the project file and in the package itself, and a version bump that
  touches only one of them makes the installed package report a version
  that does not match the code.
- The installation test no longer repeats the version number. It reads it
  from the project file, so it keeps checking the artifact that is
  actually current after a version bump.
- The release note that sat in the repository root is gone. It carried
  the test count and the build status of the day it was written, which no
  longer matched anything.
- The model context protocol server no longer claims a transport it does not
  have. Its documentation mentioned server-sent events, which were never
  implemented; the HTTP path is served by the endpoints of the web
  interface.
- The documentation of the model context protocol server no longer lists a
  fixed set of resources, tools and prompts. The list it carried named
  things that no longer exist, including a tool that never did, so anyone
  following it would call something that is not there. It now points at
  the listings the server itself returns, which cannot go stale.
- The documentation of the model context protocol is checked now: every
  name it mentions has to be a real tool, resource or prompt.
- The tools that come with the repository now install with the development
  extra. One of them needed a package the extra did not declare, so anyone
  who followed the documented install got an environment where the tools
  failed to import. The check that compares declarations against actual
  imports now covers the scripts as well, so this does not come back.
- The inventory tool asks the release API with the standard library instead
  of a third-party HTTP client, which keeps one more dependency out of the
  project.
- The build tool of the pipeline no longer carries a known vulnerability.
  The image shipped a version of setuptools with an advisory against it, and
  the whitelist only carried the older identifier of that same finding, so
  the scan started failing once the advisory was published under a second
  name. The pipeline installs a fixed version of setuptools now, and the
  entry is gone from the whitelist: a finding that can be fixed does not
  belong in a whitelist.
- The concurrency suite runs at its full scale now. The pipeline always ran
  a sample of it, one representative per file, so the full set of about
  eighteen hundred cases had never been run on any machine: the ones with
  enough memory were never scheduled, and the ones with less were killed.
  The public repository runs it at full scale on its own schedule, and all
  of the cases pass.
- The declared range of polars no longer promises a version the code cannot
  use. It allowed anything from 1.17.1 upwards, but polars 2.0 removed the
  `min_periods` argument that the factor calculation still passes, so a
  fresh installation pulled a version that raised on the first factor. The
  range now stops below 2.0, which is what the code actually supports.
  Installing the released package and running the test suite against it is
  what surfaced this: the other jobs install the pinned version and never
  see it.
- A tool of the model context protocol that fails while it runs now reports
  the failure inside the result and marks it with `isError`. It answered with
  a protocol-level error instead, so the model never saw why the call had
  failed and the conversation stopped there. The protocol keeps the two
  apart: a call that is invalid goes out as a protocol error, a call that ran
  and failed comes back inside the result.
- The HTTP adapter of that endpoint turns the marker back into an error
  status. The desktop client decides on success by the status code, so
  without the translation a failed call would have been shown as a normal
  result.
- A prompt whose arguments are incomplete now fails the whole request. It
  returned a half-rendered prompt with the placeholder still in it and an
  extra field alongside the messages, so the caller sent the unreplaced
  placeholder to the model as content. The method exists, so a wrong prompt
  name is a parameter error rather than a missing method, and it is reported
  as such.
- An unknown resource uses the code the protocol reserves for it. The method
  exists, so the code for a missing method did not describe what happened.
- The two duplicated branches of the request dispatcher are gone. The list of
  resources and the list of prompts were each handled twice; the second copy
  never ran, and its version of the prompt list did not declare the
  arguments.
- A request that fails unexpectedly gets an answer now. The transport printed
  the failure and stayed silent, so the client waited for an answer that was
  never going to come.
- The table definition of the market data has a single source now. The
  extraction job and the initialisation each wrote their own copy of it, and
  the names of the index had drifted apart, so the same index ended up under
  two names and the write cost doubled.
- The backoff of the initialisation waits for the database lock with a
  capped and jittered delay. The exponential delay grew to 51 seconds, so a
  waiting process slept through the very moment the lock was released, and
  with no jitter several of them woke up and collided again until their
  retries ran out. Under load the concurrent initialisation failed with
  "Could not set lock on file".
- The budget of the concurrent HTTP request test matches what it verifies.
  It starts a hundred processes at once, and on a loaded machine the start
  alone can take longer than the ten seconds it allowed. The test is about
  all of them succeeding, not about latency.
- The backtest endpoint of the HTTP interface now uses the market data
  stored in DuckDB when the symbol has any, and says which source it used.
  It always generated a random walk, even with the bars sitting in the
  local database, while the command line interface and the model context
  protocol tool have been reading the stored data all along. The response
  carried the label "not real data", so nothing was misrepresented; the
  capability was simply missing.
- The generated prices of the research pipeline endpoint are reproducible
  now. The seed came from the built-in hash, which is salted per process,
  so the same set of symbols produced different bars on every run while
  the response called them deterministic.
- The backtest tool of the model context protocol now uses the market data
  stored in DuckDB when the symbol has any, and says which source it used.
  It always ran a generated random walk, even with the bars sitting in the
  local database, while the command line interface has been reading the
  stored data all along. The response carried the label "not real data",
  so nothing was misrepresented; the capability was simply missing.
- The generated market data of that tool is reproducible now. The seed came
  from the built-in string hash, which is salted per process, so the same
  symbol produced different bars on every call while the response called
  them deterministic.
- The factor information request reports "no data" when the database has no
  price table yet. It raised the storage error to the caller, which reads
  like a broken service instead of a database that was never filled.
- The prompt list declares its arguments now. The list response carried no
  parameter information, so a client could not tell that the stock analysis
  prompt needs a symbol, and the placeholder reached the model untouched.
- The multimodal error carries the conventional name and its own
  documentation. The name lacked the error suffix, and the text describing
  the module sat inside the class body as a statement that did nothing.
- The lint step of the verification script covers the code that ships, with
  the same settings the pipeline uses. It inspected the whole repository
  against stricter settings, so it could never pass, and a gate that is
  always red is a gate nobody reads.
- The data source's exception classifier now reuses the module-level
  implementation. A second, text-only copy had been kept on the class and
  shadowed the module-level one, so DuckDB concurrency, permission, and
  disk-full failures were reported as network problems instead of the
  actionable cause.
- The collection hook that tags the heavy test cases was defined twice in
  the same file. The second definition replaced the first, so the file
  carried a duplicated block that no longer described the behaviour.
- The streaming chat cases reach the provider through a stub client now.
  One of them called the public API with a placeholder key, so it either
  failed or silently degraded into "the SDK is missing" depending on the
  network, and it never covered the streaming path. Another one collected
  the chunks it received and asserted nothing about them.
- The test cases that need PyTorch now skip uniformly when it is not
  installed. Three of them in the same class imported the model without
  the guard the other three used, so the file failed instead of skipping.
- The workflow files are parsed with a strict parser before the pipeline
  runs them. A repeated key makes GitHub refuse the whole file, and the
  failure is reported only on the workflow page: the pipeline shows no
  job at all, which reads like a workflow that has nothing to do.
- The SPDX header of that module was truncated by a leftover code line, which
  also commented out part of the file.
- `.gitignore` no longer matches a `data` directory at any depth. The pattern
  also covered `forgemind/core/data/`, so new source files placed there were
  silently left out of commits. `dist/`, `build/`, `artifacts/`, `builds/`, and
  `catboost_info/` are now anchored to the repository root.
- Test collection is no longer interrupted by a truncated test module. A module
  whose docstring was left unterminated made `pytest` abort before running a
  single test case, which masked every other result.
- Four test cases that were short-circuited with `pass` or `if False` now
  assert the behaviour they describe. The providers and MCP server structure
  checks, the `/health/services` endpoint check, and the API version
  consistency check all ran no assertion at all.
- Assertions that compared two command invocations byte for byte now
  normalise the per-run identifiers first. A backtest run identifier and a
  timestamped signal identifier differ on every run, so the comparisons could
  never hold.
- The per-test timeout in continuous integration now matches the slowest real
  business test case instead of an arbitrary value. Test cases that start
  DuckDB, spawn subprocesses, or invoke the CLI were being killed as hung.
- The `Core imports check` step moved from the code quality job to the test
  job. The former installs only the static analysis tools, so importing
  modules that need the runtime dependencies could never succeed there.
- The `Core imports check` step uses a heredoc, so the workflow file parses
  under strict YAML rules.
- The dependency vulnerability scan now audits the project dependencies that
  were just installed instead of the packages that come with the runner
  image. The action referenced by name was not published under that name.
- The packaging workflow now removes superseded build directories. Each run
  previously left its own copy of the distribution files in the repository.
- A tool of the model context protocol that fails while it runs now reports the
  failure inside the result and marks it with `isError`. It answered with a
  protocol-level error instead, so the model never saw why the call had failed
  and the conversation stopped there. The protocol keeps the two apart: a call
  that is invalid goes out as a protocol error, a call that ran and failed comes
  back inside the result.
- The HTTP adapter of that endpoint turns the marker back into an error status.
  The desktop client decides on success by the status code, so without the
  translation a failed call would have been shown as a normal result.
- A prompt whose arguments are incomplete now fails the whole request. It
  returned a half-rendered prompt with the placeholder still in it and an extra
  field alongside the messages, so the caller sent the unreplaced placeholder to
  the model as content. The method exists, so a wrong prompt name is a
  parameter error rather than a missing method, and it is reported as such.
- An unknown resource uses the code the protocol reserves for it. The method
  exists, so the code for a missing method did not describe what happened.
- The two duplicated branches of the request dispatcher are gone. The list of
  resources and the list of prompts were each handled twice; the second copy
  never ran, and its version of the prompt list did not declare the arguments.
- A request that fails unexpectedly gets an answer now. The transport printed
  the failure and stayed silent, so the client waited for an answer that was
  never going to come.
- The table definition of the market data has a single source now. The
  extraction job and the initialisation each wrote their own copy of it, and
  the names of the index had drifted apart, so the same index ended up under
  two names and the write cost doubled.
- The isolation of the interface mock is checked now. The mock directory was
  only referenced by the test configuration, but nothing verified that, so a
  build configuration could have started pointing at it and the interface would
  have shown generated data while the tests stayed green.
- Every endpoint of the HTTP interface is called with valid parameters now.
  Sixteen routes were reachable but only a few were exercised, and a wrong
  parameter answers with a structured error that looks like a working
  service. A second test now fails when a route is added without being
  covered, so a new endpoint cannot slip past the checks.
- A tool that runs but does not succeed now reports the failure on the
  failure channel. Fifteen places inside the tools answer with an `error`
  field, and the server wrapped every one of them as a successful result:
  the protocol did not show that anything had gone wrong, and the reason
  only survived inside a block of text. The specification puts a failed
  call in the result and marks it, so that the host hands it back to the
  model and the model can correct itself. "No data" stays a success — the
  tool answered the question, and the answer was that there is nothing.
- The factor panel of the desktop interface no longer spins forever. When
  the decay could not be fetched, the panel stayed on "computing" and
  never stopped: the call threw, nothing caught it, and the reason never
  reached the screen. The reason is shown now, next to the explanation
  that this is a failed fetch rather than a factor without a value.
- The first run of the desktop and of the command line no longer prints the
  internals. The local database does not have the table of daily bars yet
  on a fresh machine, and the commands asked for it with an exception: the
  storage layer answered with a warning that carried the name of the
  table and the query, and the backtest command repeated the name in its
  own message. A first-time reader saw a block of JSON and the inside of
  the implementation instead of the answer. The commands ask whether the
  table is there first, and the fallback says what to run.
- The commands ask whether a table is there instead of finding out with an
  exception. On a machine that has not fetched any data yet, the table is
  simply not there, and that is not a failure — but asking with an exception
  left a warning behind it carrying the name of the table and the query, and
  the storage layer repeated the name of the table in a second warning. The
  name of the table now lives in one place, and the commands use it.
- The warnings of the storage layer no longer carry the text of the error.
  The text of a database error contains the name of the table and the whole
  query, and it was written to the terminal of the user. The type of the
  error stays; the text moved to the debug level.
- The warnings of a third-party library no longer appear in the terminal of
  the user. They arrive with the path of the file they came from, in the
  installation directory of that library, and the user can do nothing about
  them. They cannot be filtered away in the usual way: the library replaces
  the filters of the warnings module while it is imported. The display of
  warnings is intercepted instead, and a warning that comes from our own
  package still shows.
- A checker walks the output of every command on a machine that has nothing
  in it yet, and reports what must not be there: queries, stack traces, the
  names of exception types, local paths. The name of an internal table is
  allowed, but only when the README explains it — so the table list of the
  README is a promise that is checked against the schema.
- The FAQ of the README quotes the wording of the commands. A checker reads
  those quotes back against the source: a wording that changed without the
  FAQ being updated leaves the reader searching for a message that is no
  longer printed.
- The tables of the local database are documented now. Which tables exist is
  read from the schema itself, so the list cannot drift away from it.
- A release that cannot be completed says which platform is missing and
  which version the reader still has. The step was skipped, so the page
  showed a single "skipped" and did not distinguish a broken build from a
  platform that never handed out a runner.
- The exit codes of the command line follow the table again. Three paths
  that are plainly a mistake in the arguments — no command at all, a
  strategy that needs more parameters, and the demo data missing a column —
  left with the code that the table reserves for the refusal of an
  approval. The reader saw a code that said "the approval was refused" and
  looked in the wrong place. They are usage problems, and usage problems
  have their own code. The codes are named constants now, so the table and
  the code cannot drift apart silently, and the checker runs three more
  commands to see the codes with its own eyes.
- The checker that watches the checkers now counts a mention in a comment
  as nothing. The gate before a release is a script, and the script was
  named in the comment next to the step that calls it — so deleting the
  call and keeping the comment was enough to make the checker report that
  everything was still wired, while the gate had stopped gating. The
  judgment is a file of its own now, and the test file that goes with it
  is watched the same way.
- The gate before a release asks the platform for the runs of the whole
  repository. It asked for the runs of one workflow instead, and without
  naming that workflow the platform answered that there is no such thing
  — so the gate failed at once, and every release was skipped. It failed
  safely: nothing reached the users that had not been checked. But a gate
  that never opens is not a gate, and now the call is made through a mock
  in the tests, so the name of the call is part of what is checked.
- A release waits for the gates now. The gates and the release used to run
  side by side, so a commit whose tests and lint failed was published all
  the same: the release finished, the index pointed at it, and half of the
  pipeline was green. A version that nobody checked had reached the people
  who install it. The release now looks at the conclusion of the gates
  before it publishes anything, and the reasoning about it lives in the
  repository where it can be tested on its own — a gate that lets through
  what it should stop is worse than no gate at all.
- The list of strategies and the tool that runs a backtest say the same
  thing now. The list tells the model which strategies exist and which ones
  this command cannot feed; the tool used to parse the name on its own and
  knew only five of them, and it called the rest unknown — including the
  ones the list had just named as usable. A model that trusted the list was
  told it had never heard of a strategy; a model that trusted the tool was
  told the list was wrong. The parsing is one piece of code now, used by
  both, and a test holds the two against each other.
- The options in the README are checked now, not only the commands. A reader
  who copies a line with a misspelled option gets an error from the parser
  in the middle of their first hour with the tool, and nothing in the
  repository noticed it before. The check asks the parser itself which
  options a command takes, and it accepts the abbreviations the parser
  accepts — a unique prefix is fine, an ambiguous one is not.
- The index now points at the release assets instead of a directory inside
  the repository. The two hold the same file, and the index now names the
  same thing the reader sees on the releases page — there is no second
  place where "the current version" lives. The repository copy is only the
  CDN for the repository's own content, and a shaky connection to it
  breaks the installation half way through (it did here: the transfer was
  cut off by the network twice before the package was in place). The
  check that the index and the manifest point at the same artifact now
  compares the version in the file name, which works whichever shape the
  link has.
- The bundled sample prices are checked against the upstream source now.
  The demo promises that the market data inside the package is real and not
  made up, and that promise used to be a sentence in the documentation that
  nobody could check. The checker now fetches the same series from the
  public quote interface and compares it: the sequence of trading days has
  to match exactly, the volume of every single bar has to match exactly —
  adjustment moves prices, not volumes, so a matching volume series cannot
  be faked — and the closing prices have to stay within half a percent,
  because the adjusted prices are recalculated when a dividend is paid.
- The three checks that run after a release no longer share one concurrency
  group. A concurrency group keeps a single pending run, so a new run
  cancels the one that was waiting: two of the three checks were cancelled
  on every release, and which two survived depended on which one queued
  first. The cancellations happened before any job was created, so they
  said nothing about the artifacts — every check that did get a runner
  finished. Each check now has its own group, and a checker keeps two
  workflows from sharing one.
- The scheduled run of the check that tests the published wheel tests the
  artifact against the source that produced it. It compared the commit in
  the manifest with the head of the branch, and the two differ as soon as
  anything is pushed after a release, so the run failed on every attempt.
  The commit under test now comes from the manifest, and the run checks
  that the commit is part of the history of the branch.
- Reading the manifest returns the manifest. The contents endpoint returns
  the file base64-encoded unless a different media type is asked for, and
  the parser read the envelope instead of the file, so every field came
  back empty.

- The desktop UI workflow no longer fails at parse time. `hashFiles` is
  only usable in a step condition; at job level it made the workflow fail
  before it could run anything.
- The code quality workflow no longer imports project modules that need
  the runtime dependencies it does not install. The import check moved to
  the test workflow, where those dependencies are present.
- The release workflow parses again. A block of embedded Python was
  written flush against the left margin, which ended the YAML block
  scalar and broke the file.
- The dependency vulnerability scan audits the project dependencies that
  were just installed instead of the packages that come with the runner
  image. The action referenced by name was not published under that name.
- The test pipeline installs the dependencies listed in
  `requirements-ci.txt`, whose versions match the combination verified
  locally. Resolving by range installed releases above the project's own
  upper bounds, so the code was running against a different API than it
  was written for.
- The pipeline keeps a record of the dependency installation and of any
  test failure in the repository, so a cause does not have to be dug out
  of the workflow logs.

- A command that cannot read the local store no longer reports
  success. It used to fall back to synthetic prices, print a Sharpe ratio
  that looked like a result and exit with 0; it now exits with 4 and says
  the store is unavailable. A store that cannot be written to is recognized
  as well - the failure happens while connecting, before any query runs.
- The interface tells "not computed" apart from "no data". The backend
  computes a limited number of factors per call, and the factors it
  skipped used to show up as "no data".
- Switching the symbol in the interface no longer leaves the previous
  symbol's IC on the factors that were not computed for the new one.
- The IC and the ICIR the interface shows come from the same definition
  as the factor monitor: the time series of the cross-sectional IC per
  period. The tool used to average the IC across horizons and call the
  spread of those numbers an ICIR, which is a different quantity.
- The heavy test tier samples across the whole file instead of the first
  few cases in it. The cases at the end of a file used to run only in the
  full-scale job, which happens twice a day.
- The release body and the checkers read the published manifest with a
  retry, and they tell a missing manifest apart from a manifest that could
  not be read. A manifest that could not be read used to be taken for
  "there was no previous release", which made the next release compute an
  older version number than the one already online.
- The command that resumes a failed release accepts a run whose commit is
  an ancestor of the main branch. It used to insist on the head of the
  branch, which the release itself moves, so the normal case was refused.

### Fixed
- The failure response of the API no longer carries the name of the
  exception class, and the diagnostic context is cleaned before it goes
  out. The text we wrote ourselves is kept — that is what lets a caller
  correct the request — while the original message of a third-party
  library is replaced with a pointer to the service log. The wording and
  the cleaning rules live in one place, shared with the command line and
  MCP.
- A decision no longer runs on an account that was made up. The cash
  carried a default value of a hundred thousand, so a caller who knew
  nothing about the account still got a decision that looked normal,
  with the positions computed from an account that did not exist. Cash is
  required now, the equity is computed from the cash and the positions
  when it is not given, and the desktop application passes the snapshot
  the portfolio really has — and says plainly when there is none.

- The command line no longer makes up an account for the decision. The
  cash, the equity and the held position all carried default values, so
  `forgemind agent --symbol 600519.SH` ran on an account of eighty
  thousand cash holding a hundred shares — and after the approval that
  account went into the portfolio snapshot, turning a made-up state into
  a stored one. The account now comes from the portfolio the library
  really holds, or from the arguments; when neither is there, the command
  says so and exits with a usage error.

### Added
- `GET /api/v1/portfolio` returns the portfolio the library really holds —
  cash, equity and positions. It is where a caller gets the account state
  that a decision is computed from. When nothing has been stored yet it
  says so, with the next step, instead of handing out an account nobody
  had.

### Fixed
- The decision now reports the account it was computed from. The
  positions are worked out from the cash, the equity and the holdings,
  and those are normally invisible: without the report, the reader can
  only take the conclusion on trust and cannot tell which state it came
  from. The command line, the HTTP endpoint and the MCP tool all say it.
- The approval defaults to not approving. `agent_approve` treated a
  missing `approved` as approval, so a caller that forgot the argument
  had the gate open — while the command line refuses to approve without
  an explicit yes. The tool now says so in its description as well.
- The API validation error for a missing cash now says where to get the
  account, instead of naming a field and stopping there.
- The verification script now walks the two decision tools — they were
  listed in the tool set but never actually called — and takes its list
  of runnable strategies from the registry instead of a hand-written
  exclusion list, which had been dropping strategies that the command
  cannot feed.
- The desktop evidence script declares the origin it needs. The default
  set of allowed origins is deliberately narrow, and the page the script
  serves comes from its own address; it now asks for that address
  explicitly rather than the product opening itself up.

### Security
- The local endpoints that can write to the database or run a decision now
  refuse a caller that does not carry the desktop client's marker header.
  They are exempt from the API key check — the sidecar carries no key — and
  until now nothing else stood between them and the caller: a page open in
  the user's browser could reach them across origins, because the allowed
  origins included every origin.
- The allowed origins no longer include every origin by default. Set
  `FORGEMIND_API_CORS_ORIGINS` to open the API to a browser on purpose.
- A missing or wrong API key is now answered with 401 or 403. The check
  sits in middleware, which runs outside FastAPI's exception handlers, so
  the refusal used to reach the client as a 500 — the service looked broken
  instead of asking for credentials.

### Changed
- Dependencies are now checked against what the code actually imports, in
  both directions. Thirteen packages that nothing in the source imported
  (`sqlalchemy`, `alembic`, `prefect`, `langgraph-prebuilt`,
  `langchain-openai`, `langchain-anthropic`, `llama-index`, `chromadb`,
  `quantstats`, `tenacity`, `python-jose`, `passlib`, `python-multipart`)
  are no longer installed for every user. `empyrical-reloaded` is only used
  by the third-party metric cross-check, so it moved to the `dev` extra.
  `lightgbm` now requires `4.6.0`, the first release without
  `PYSEC-2024-231`.
- The continuous integration lock file now covers the whole set of
  declared runtime dependencies. It installs the project with `--no-deps`,
  so a dependency missing from the lock file was never installed in the
  pipeline: the corresponding code paths were not executed and the cases
  that would have covered them were skipped, while the job still reported
  success. Two new checks keep the lock file and the declaration in step.
- Test file names are at most 130 characters long. The renamed files keep
  their original word order and gain a short hash, so every name stays
  unique and the tier a file belongs to is unchanged.
- Million-scale concurrency test cases are tagged `heavy` and run in a
  dedicated job on a schedule, keeping the regular pipeline fast:
  `pytest tests/ -m "not heavy"` for regular cases, `pytest tests/ -m heavy`
  for the concurrency tier. Test cases that take tens of seconds to minutes
  for their own reasons join the same tier, so "heavy" has one definition.
- Duplicate test modules that differed only in a version suffix were
  consolidated. Each series keeps its earliest, middle, and latest variant.
- Every Python source file carries the same two-line licence header.
- The workflow writes the outcome of each job to `ci-status.json` in the
  repository, so the state of the pipeline is a queryable fact rather than
  something only visible on the CI page.
- The test count in the README is now the measured value.
- The pipeline is split into four workflows with one responsibility each
  (security scan, Python tests, desktop UI, code quality). Each one's
  outcome can be queried and re-run on its own, and one failing workflow
  no longer hides the state of the others.

### Removed
- Build outputs and the internal trigger file are no longer tracked in the
  source repository.
- The generated `next-env.d.ts` and `tsconfig.tsbuildinfo` are no longer
  tracked. The build rewrites them on every run, which left the working tree
  permanently dirty.
- The packaging workflow no longer keeps every superseded build in the
  distribution repository. Each run used to leave its own copy of the
  distribution files behind.

## [v2026.09] - 2026-09-20

Initial public release.

### Added
- AI Quant Trading Agent framework with 6-agent collaborative decision pipeline
- Multi-source data registry with 9 LLM provider routing
- 17 backtest strategies across base, library, and extended tiers
- MCP server with Anthropic JSON-RPC 2.0 protocol, 10 tools, 6 resources, 3 prompts
- Observability stack: OpenTelemetry + Prometheus + structured logging
- Desktop application via Tauri 2.11.5
- Apache 2.0 licensed

[ForgeMind]: https://github.com/bin1732/forgemind
