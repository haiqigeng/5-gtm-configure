# Contributing

Keep the runtime skill agent-neutral and focused on GTM configuration for expert
web analysts. Do not commit client containers, tracking plans, screenshots,
domains, credentials, personal data, browser traces, or generated reports.

Before opening a pull request, run:

~~~powershell
python -m pip install -e ".[dev]"
python -m ruff format --no-cache --check scripts tests
python -m ruff check --no-cache scripts tests
python scripts/check_release.py --tag v6.2.0 --release-notes CHANGELOG.md
python -m unittest discover -s tests -v
python -m compileall -q scripts
python scripts/build_skill_package.py --output dist/configure-gtm-test.zip
~~~

Changes to consent, schema mapping, platform playbooks, template governance,
reuse, adapter behavior, evidence grades, or acceptance rules should include a
focused contract test and, when a deterministic configuration decision changes,
an explicit configuration scenario. Scenarios validate the packaged contract;
they must not claim to test model reasoning or browser runtime behavior. Keep
live event catalogues in official vendor documentation rather than copying them
into the skill. Keep server-side GTM and deduplication changes marked as deferred
until that capability is formally added to the skill.
