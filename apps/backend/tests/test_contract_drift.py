"""Rule R10 wire-contract drift gate (CI step 6, talkflow_backend.md:575).

The committed ``openapi.json`` must exactly match the schema regenerated from
the live FastAPI app. Runs fully offline: schema generation never executes a
handler or opens a connection.
"""

from __future__ import annotations

import json

from scripts.contract import contract_json, load_committed


def test_committed_openapi_is_current() -> None:
    committed = load_committed()
    assert committed is not None, (
        "openapi.json is missing - run `python -m scripts.contract generate` (Rule R10)"
    )
    assert committed == contract_json(), (
        "openapi.json has drifted - run `python -m scripts.contract generate` "
        "and bump CONTRACT_VERSION in app/packages/contracts/version.py (Rule R10)"
    )


def test_openapi_version_matches_contract_version() -> None:
    from app.packages.contracts.version import CONTRACT_VERSION

    schema = json.loads(contract_json())
    assert schema["info"]["version"] == CONTRACT_VERSION
