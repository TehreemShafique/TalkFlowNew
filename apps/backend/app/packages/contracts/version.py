"""Wire-contract version (Rule R10).

Bump this value whenever the API contract changes, then regenerate the
committed ``openapi.json``::

    python -m scripts.contract generate

The drift gate (CI step 6 / Rule R10) fails if a checked-in change to the API
(delta schema, new route, changed model) is not accompanied by both of these.
"""

CONTRACT_VERSION = "0.6.0"
