"""Typer CLI for audioscope.

Usage:
    audioscope analyze <file|dir> [--json] [--no-llm] [--agent] [-o OUT]
"""

from __future__ import annotations

from pathlib import Path

import typer

from .batch import analyze_directory
from .config import load_config
from .insight import generate_insight
from .pipeline import analyze_file
from .render import render_batch, render_report

app = typer.Typer(
    add_completion=False,
    help="Audio quality analysis for any audio file (ffmpeg + LLM).",
)


@app.command()
def analyze(
    path: Path = typer.Argument(..., help="Audio file or directory to analyse."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of text."),
    no_llm: bool = typer.Option(False, "--no-llm", help="Skip the LLM; use rule-based insight."),
    use_agent: bool = typer.Option(
        False, "--agent", help="Use the tool-calling agent to drive analysis (single file)."
    ),
    config_path: Path | None = typer.Option(
        None, "--config", help="JSON file overriding detection thresholds."
    ),
    output: Path | None = typer.Option(None, "-o", "--output", help="Write report to a file."),
    workers: int = typer.Option(4, help="Concurrent workers for directory mode."),
) -> None:
    """Analyse an audio file or every audio file in a directory."""

    use_llm = not no_llm
    config = load_config(config_path)

    if path.is_dir():
        batch = analyze_directory(path, use_llm=use_llm, max_workers=workers, config=config)
        text = batch.model_dump_json(indent=2) if json_out else render_batch(batch)
    else:
        if use_agent:
            from .insight.agent import analyze_with_agent

            report = analyze_with_agent(path, use_llm=use_llm, config=config)
        else:
            report = analyze_file(path, config=config)
            report.insight = generate_insight(report, use_llm=use_llm)
        text = report.model_dump_json(indent=2) if json_out else render_report(report)

    if output:
        output.write_text(text + "\n")
        typer.echo(f"Wrote report to {output}")
    else:
        typer.echo(text)


@app.command()
def version() -> None:
    """Print the package version."""

    from . import __version__

    typer.echo(__version__)


def main() -> None:  # pragma: no cover - entrypoint shim
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
