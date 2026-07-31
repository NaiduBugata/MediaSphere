"""Facade for invoking the Telugu AI news analyzer as a subprocess.

The analyzer is a standalone script (telugu_ai_news_analyzer.py) that reads
article.txt and produces categorized JSON output. Pipeline runners call it
via subprocess to isolate its heavy dependencies and long runtime.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ANALYZER_SCRIPT = Path(__file__).resolve().parent / "telugu_ai_news_analyzer.py"


def run_analyzer(
    *,
    input_path: Path | str,
    output_dir: Path | str,
    checkpoint_file: Path | str | None = None,
    timeout: int = 300,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the Telugu AI news analyzer as a subprocess.

    Args:
        input_path: Path to the article.txt input file.
        output_dir: Directory for analyzer output (news_output.json, etc.).
        checkpoint_file: Optional checkpoint file path for incremental processing.
        timeout: Subprocess timeout in seconds.
        env_overrides: Additional environment variables to set.

    Returns:
        CompletedProcess with stdout, stderr, and returncode.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        str(ANALYZER_SCRIPT),
        "--input",
        str(input_path),
        "--output-dir",
        str(output_dir),
    ]

    env = os.environ.copy()
    if checkpoint_file:
        env["CHECKPOINT_FILE"] = str(checkpoint_file)
    env["OUTPUT_DIR"] = str(output_dir)
    if env_overrides:
        env.update(env_overrides)

    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        env=env,
    )
