"""Rule R10 wire-contract tooling (``apps/backend/scripts``).

Generates the committed OpenAPI document from the live FastAPI app and
provides the ``contract`` CI gate (talkflow_backend.md:575): regenerate and
fail on any diff. Runs fully offline -- schema generation never executes a
handler or opens a connection.

Run::

    python -m scripts.contract generate   # rewrite openapi.json
    python -m scripts.contract check      # drift gate (CI step 6)

Every API change therefore requires a regeneration plus a ``CONTRACT_VERSION``
bump in ``app/packages/contracts/version.py`` (the bump is baked into the
document's ``info.version``, so a reviewable diff accompanies every contract
change).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections.abc import Sequence
from typing import Any

OPENAPI_PATH = pathlib.Path(__file__).resolve().parents[1] / "openapi.json"

CONTRACT_GUIDANCE = f"""
The API has drifted from the committed openapi.json (Rule R10).
Fix it by regenerating the document and bumping the contract version:

    python -m scripts.contract generate
    # then bump CONTRACT_VERSION in app/packages/contracts/version.py
    # and commit app/packages/contracts/version.py + {OPENAPI_PATH.name}
"""


def contract_json() -> str:
    """Serialized OpenAPI document for the current app + CONTRACT_VERSION."""
    from app.main import app
    from app.packages.contracts.version import CONTRACT_VERSION

    schema: dict[str, Any] = app.openapi()
    schema["info"]["version"] = CONTRACT_VERSION
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def load_committed() -> str | None:
    try:
        return OPENAPI_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def cmd_generate(_args: argparse.Namespace) -> int:
    OPENAPI_PATH.write_text(contract_json(), encoding="utf-8")
    from app.packages.contracts.version import CONTRACT_VERSION

    print(f"wrote {OPENAPI_PATH} (contract v{CONTRACT_VERSION})")
    return 0


def cmd_check(_args: argparse.Namespace) -> int:
    fresh = contract_json()
    committed = load_committed()
    if committed is None:
        print(f"FAIL: {OPENAPI_PATH} is not committed (Rule R10).")
        print(CONTRACT_GUIDANCE)
        return 1
    if fresh != committed:
        print("FAIL: contract drift detected (Rule R10).")
        print(CONTRACT_GUIDANCE)
        return 1
    from app.packages.contracts.version import CONTRACT_VERSION

    print(f"OK: openapi.json current (contract v{CONTRACT_VERSION})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="contract", description=__doc__.splitlines()[0]
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("generate", help="regenerate and commit openapi.json")
    sub.add_parser("check", help="fail if openapi.json has drifted (CI gate)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "generate":
        return cmd_generate(args)
    return cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
