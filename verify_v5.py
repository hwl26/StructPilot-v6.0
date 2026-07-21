"""StructPilot v6.0 self-check entrypoint."""

from pathlib import Path
import runpy


runpy.run_path(str(Path(__file__).with_name("verify_v4.py")), run_name="__main__")
