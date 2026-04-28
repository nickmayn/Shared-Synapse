"""
synapse CLI – second-brain agent for your terminal.

Commands
--------
synapse connect <server-url>    Save connection config
synapse search <query>          Semantic knowledge search
synapse add <file>              Push a file as knowledge
synapse activate <name>         Activate a synapse
synapse deactivate <name>       Deactivate a synapse
synapse synapses                List all synapses
synapse agent                   Start a local stdio MCP agent
synapse sync                    Pull remote knowledge to local ChromaDB
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from .config import set_profile, get_server_url, get_profile
from .client import SynapseClient

app = typer.Typer(help="Shared Synapse CLI – connect your second brain.", add_completion=False)
console = Console()


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------

@app.command()
def connect(
    server_url: str = typer.Argument(..., help="Base URL of the Shared Synapse API"),
    username: Optional[str] = typer.Option(None, "--username", "-u", help="Username to authenticate"),
    password: Optional[str] = typer.Option(None, "--password", "-p", help="Password (prompted if omitted)"),
    token: Optional[str] = typer.Option(None, "--token", "-t", help="Provide an existing JWT access token"),
    profile: str = typer.Option("default", "--profile", help="Config profile name"),
) -> None:
    """Save connection config and optionally authenticate."""
    import httpx

    url = server_url.rstrip("/")
    values: dict = {"server_url": url}

    if token:
        values["access_token"] = token
        set_profile(values, profile)
        console.print(f"[green]Connected to {url} (token stored)[/green]")
        return

    if username:
        pw = password or typer.prompt("Password", hide_input=True)
        try:
            resp = httpx.post(f"{url}/auth/login", json={"username": username, "password": pw}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            values["access_token"] = data["access_token"]
            values["refresh_token"] = data.get("refresh_token", "")
            values["username"] = username
        except httpx.HTTPStatusError as exc:
            console.print(f"[red]Login failed: {exc.response.text}[/red]")
            raise typer.Exit(1)

    set_profile(values, profile)
    console.print(f"[green]Connected to {url}[/green]")


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    filters: Optional[str] = typer.Option(None, "--filters", "-f", help="JSON filter string"),
    profile: str = typer.Option("default", "--profile"),
) -> None:
    """Semantic knowledge search."""
    client = SynapseClient(profile)
    try:
        parsed_filters = json.loads(filters) if filters else None
        data = client.search(query, parsed_filters)
    except Exception as exc:
        console.print(f"[red]Search failed: {exc}[/red]")
        raise typer.Exit(1)

    results = data.get("results", [])
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    for idx, r in enumerate(results, 1):
        console.print(Panel(
            f"[bold]{r.get('document_id', '')}[/bold]  "
            f"[dim]{r.get('document_type', '')}[/dim]\n\n"
            f"{r.get('chunk_content', '')[:400]}",
            title=f"#{idx}  score={r.get('score', 0):.3f}",
        ))


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

@app.command()
def add(
    path: Path = typer.Argument(..., help="File to push as knowledge, or - for stdin"),
    doc_type: str = typer.Option("document", "--type", "-t", help="Knowledge type"),
    doc_id: Optional[str] = typer.Option(None, "--id", help="Document ID (defaults to filename stem)"),
    profile: str = typer.Option("default", "--profile"),
) -> None:
    """Push a file (or stdin) to the knowledge base."""
    if str(path) == "-":
        content = sys.stdin.read()
        resolved_id = doc_id or "stdin-input"
    else:
        if not path.exists():
            console.print(f"[red]File not found: {path}[/red]")
            raise typer.Exit(1)
        content = path.read_text(encoding="utf-8")
        resolved_id = doc_id or path.stem

    client = SynapseClient(profile)
    try:
        result = client.add_knowledge(resolved_id, doc_type, content)
        console.print(f"[green]Indexed '{resolved_id}' ({result.get('chunks', 0)} chunks)[/green]")
    except Exception as exc:
        console.print(f"[red]Add failed: {exc}[/red]")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# synapses
# ---------------------------------------------------------------------------

@app.command()
def synapses(
    profile: str = typer.Option("default", "--profile"),
) -> None:
    """List all synapses and their activation status."""
    client = SynapseClient(profile)
    try:
        items = client.list_synapses()
    except Exception as exc:
        console.print(f"[red]Failed: {exc}[/red]")
        raise typer.Exit(1)

    table = Table(title="Synapses", show_header=True, header_style="bold")
    table.add_column("Name", style="bold")
    table.add_column("Activation")
    table.add_column("Active")
    table.add_column("Description")

    for s in items:
        active_icon = "[green]●[/green]" if s.get("active") else "[dim]○[/dim]"
        table.add_row(
            s.get("name", ""),
            s.get("activation", ""),
            active_icon,
            s.get("description", "")[:60],
        )
    console.print(table)


# ---------------------------------------------------------------------------
# activate / deactivate
# ---------------------------------------------------------------------------

@app.command()
def activate(
    name: str = typer.Argument(..., help="Synapse name to activate"),
    profile: str = typer.Option("default", "--profile"),
) -> None:
    """Activate an optional synapse."""
    client = SynapseClient(profile)
    try:
        client.activate_synapse(name)
        console.print(f"[green]Activated: {name}[/green]")
    except Exception as exc:
        console.print(f"[red]Failed: {exc}[/red]")
        raise typer.Exit(1)


@app.command()
def deactivate(
    name: str = typer.Argument(..., help="Synapse name to deactivate"),
    profile: str = typer.Option("default", "--profile"),
) -> None:
    """Deactivate an optional synapse."""
    client = SynapseClient(profile)
    try:
        client.deactivate_synapse(name)
        console.print(f"[yellow]Deactivated: {name}[/yellow]")
    except Exception as exc:
        console.print(f"[red]Failed: {exc}[/red]")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# agent  – local stdio MCP bridge
# ---------------------------------------------------------------------------

@app.command()
def agent(
    backend_dir: Optional[Path] = typer.Option(
        None,
        "--backend",
        "-b",
        help="Path to the backend directory (auto-detected from config if omitted)",
    ),
) -> None:
    """
    Start a local stdio MCP agent.

    Spawns `python -m src.mcp_server.server` from the backend directory so that
    MCP-aware editors (Copilot, Cursor, Continue) can connect to Shared Synapse
    without a hosted server.
    """
    resolved = backend_dir or Path(__file__).resolve().parents[5] / "backend"
    if not (resolved / "src" / "mcp_server" / "server.py").exists():
        console.print(f"[red]Backend not found at {resolved}. Use --backend to specify.[/red]")
        raise typer.Exit(1)

    console.print(f"[dim]Starting local MCP agent from {resolved}…[/dim]")
    try:
        subprocess.run(
            [sys.executable, "-m", "src.mcp_server.server"],
            cwd=str(resolved),
            check=True,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Agent stopped.[/yellow]")
    except subprocess.CalledProcessError as exc:
        console.print(f"[red]Agent exited with code {exc.returncode}[/red]")
        raise typer.Exit(exc.returncode)


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------

@app.command()
def sync(
    profile: str = typer.Option("default", "--profile"),
) -> None:
    """Trigger a full re-ingestion of knowledge files on the server."""
    client = SynapseClient(profile)
    try:
        result = client.post("/api/reindex")
        total = result.get("total", 0)
        success = result.get("success", 0)
        failed = result.get("failed", 0)
        console.print(f"[green]Sync complete: {success}/{total} files ingested, {failed} failed[/green]")
    except Exception as exc:
        console.print(f"[red]Sync failed: {exc}[/red]")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app()


if __name__ == "__main__":
    main()
