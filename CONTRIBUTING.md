# Contributing

Keep the runtime skill agent-neutral and focused on GTM configuration for expert
web analysts. Do not commit client containers, tracking plans, screenshots,
domains, credentials, personal data, browser traces, or generated reports.

Before opening a pull request, run:

~~~powershell
python -m pip install -e ".[dev]"
python -m ruff format --no-cache --check scripts tests
python -m ruff check --no-cache scripts tests
python scripts/check_release.py --tag v9.0.0 --release-notes CHANGELOG.md
python -m unittest discover -s tests -v
python -m compileall -q scripts
python scripts/build_skill_package.py --output dist/configure-gtm-test.zip
~~~

Changes to consent, transport, Client/Event Data shape, deduplication, schema mapping, platform
playbooks, template governance, reuse, adapter behavior, evidence grades, or acceptance rules should include a
focused contract test and, when a deterministic configuration decision changes,
an explicit configuration scenario. Scenarios validate the packaged contract;
they must not claim to test model reasoning or browser runtime behavior. Keep
live event catalogues in official vendor documentation rather than copying them into the skill.
Preserve web-only v8 behavior with regression tests, keep platform-specific server rules in their
conditional counterparts, and never add publication or runtime-certification behavior.

The v5 contract validator and run@2.1 schema/runtime remain packaged only for explicit historical
read and safe migration compatibility. New behavior belongs in contract 6.0/run 3.0. Do not add new
features to the compatibility formats, and do not remove them until a future major release defines
and tests a migration/sunset policy for retained historical artifacts. `run_validation_web.py`
remains the active shared authority for web-domain semantics through the run@3 adapter; only its
run@2.1 state/CLI surface is compatibility-only.
