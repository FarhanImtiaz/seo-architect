# Smoke tests

Run `python3 tests/run_tests.py`. It exercises state creation, XML/robots/JSON-LD parsing, regression detection, the reproducible scoring engine, schema-per-type validation, the link graph and image scans, framework-aware metadata extraction, hreflang, the winning-patterns citation registry, and the worked-example before/after integration test.

The behavioral safety scenarios in `workflow-tests.md` are also captured as structured prompts in `tests/agent-evals/*.json`. Run them with `python3 tests/run_agent_evals.py` when the `claude` CLI is available — it prints each scenario's response for human/agent judgment rather than a mechanical assertion, and is never part of the default `run_tests.py` gate.
