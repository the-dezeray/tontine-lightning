"""Deterministic end-to-end demo/test (delegates to demo.py).

Usage:
    python test_demo.py
"""

import runpy


if __name__ == "__main__":
    runpy.run_module("demo", run_name="__main__")

