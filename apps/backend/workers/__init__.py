"""Background worker entrypoints for the TalkFlow control plane.

Each worker is a standalone async daemon (run with ``python -m workers.<name>``)
or a handler class that the test-suite drives directly against the suite
engine (no live broker required).
"""