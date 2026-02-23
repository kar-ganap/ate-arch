"""CLI entry point for ate-arch."""

import typer

app = typer.Typer(name="ate-arch", help="Agent Teams Eval: Architecture Design")


@app.callback()
def main() -> None:
    """Agent Teams Eval — Architecture Design experiment tooling."""


if __name__ == "__main__":
    app()
