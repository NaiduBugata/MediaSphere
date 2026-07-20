"""Legacy shim — canonical YouTube collector lives in ``sources.youtube``."""

from sources.youtube.collector import get_output_path, run

__all__ = ["get_output_path", "run"]
