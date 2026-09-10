"""Command-line interface for SyntheticForge."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from syntheticforge.config import load_config
from syntheticforge.generator.anomaly import AnomalyInjector
from syntheticforge.generator.entity_generator import EntityGenerator
from syntheticforge.generator.lifecycle_simulator import LifecycleSimulator
from syntheticforge.graph.schema_graph import SchemaGraph
from syntheticforge.inspector.introspect import SchemaIntrospector
from syntheticforge.inspector.verifier import RelationalVerifier
from syntheticforge.streaming.file_sink import JsonlSink, ParquetSink
from syntheticforge.streaming.kafka_streamer import KafkaStreamer
from syntheticforge.streaming.postgres_loader import PostgresLoader
from syntheticforge.streaming.traffic_curve import DiurnalTrafficCurve
from syntheticforge.tui.dashboard import RichLiveDashboard
from syntheticforge.tui.stats import StreamStats

app = typer.Typer(
    name="syntheticforge",
    help="Graph-driven relational and event stream generator with probabilistic lifecycle simulation.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def inspect(
    schema: Path = typer.Argument(..., help="Path to declarative YAML schema file.", exists=True),
) -> None:
    """Inspect entity dependency graph, execution stages, and lifecycle rules."""
    config = load_config(schema)
    graph = SchemaGraph(config)

    console.print(
        Panel.fit(
            f"[bold cyan]Schema:[/] {config.name} (v{config.version})\n"
            f"[bold white]Description:[/] {config.description or 'No description provided.'}",
            title="SyntheticForge Schema",
            border_style="cyan",
        )
    )

    # Dependency Tree
    console.print("\n[bold yellow]Execution Stages & Dependency Hierarchy:[/]")
    console.print(graph.to_ascii_tree())

    # Entities summary table
    table = Table(title="Configured Entities", expand=True)
    table.add_column("Entity", style="cyan")
    table.add_column("Count", justify="right", style="green")
    table.add_column("Primary Key", style="yellow")
    table.add_column("Dependencies", style="magenta")
    table.add_column("Has Lifecycle", justify="center")

    for name, ent in config.entities.items():
        deps = ", ".join(ent.depends_on) if ent.depends_on else "-"
        has_lc = "[green]Yes[/]" if ent.lifecycle else "[dim]No[/]"
        table.add_row(name, f"{ent.count:,}", ent.primary_key, deps, has_lc)

    console.print("\n", table)


@app.command()
def generate(
    schema: Path = typer.Option(..., "--schema", "-s", help="Path to YAML schema.", exists=True),
    sink: str = typer.Option("jsonl", "--sink", help="Output sink: jsonl, parquet, or postgres."),
    output_dir: Path = typer.Option(
        Path("./output"), "--output-dir", "-o", help="Directory for output files."
    ),
    postgres_dsn: str | None = typer.Option(
        None, "--postgres-dsn", help="PostgreSQL DSN if using postgres sink."
    ),
) -> None:
    """Generate coherent relational datasets with 100% referential integrity."""
    config = load_config(schema)
    graph = SchemaGraph(config)
    generator = EntityGenerator(config, graph=graph)

    with console.status("[bold green]Generating relational entity dataset..."):
        dataset = generator.generate_all()

    sink_type = sink.lower()
    if sink_type == "jsonl":
        file_sink = JsonlSink(output_dir)
        written = file_sink.write_all(dataset)
        console.print(f"[bold green]Successfully wrote JSONL files to {output_dir}:[/]")
        for ent, p in written.items():
            console.print(f"  - {ent}: {p} ({len(dataset[ent])} records)")

    elif sink_type == "parquet":
        file_sink = ParquetSink(output_dir)
        written = file_sink.write_all(dataset)
        console.print(f"[bold green]Successfully wrote Parquet files to {output_dir}:[/]")
        for ent, p in written.items():
            console.print(f"  - {ent}: {p} ({len(dataset[ent])} records)")

    elif sink_type == "postgres":
        if not postgres_dsn:
            console.print(
                "[bold red]Error:[/] --postgres-dsn required for postgres sink.", file=sys.stderr
            )
            raise typer.Exit(code=1)

        async def _load_pg() -> None:
            loader = PostgresLoader(postgres_dsn)
            await loader.connect()
            for ent_name, records in dataset.items():
                await loader.create_table(ent_name, config.entities[ent_name])
                await loader.bulk_load(ent_name, records)
            await loader.close()

        asyncio.run(_load_pg())
        console.print(
            f"[bold green]Successfully loaded {sum(len(r) for r in dataset.values())} records into PostgreSQL.[/]"
        )


@app.command()
def stream(
    schema: Path = typer.Option(..., "--schema", "-s", help="Path to YAML schema.", exists=True),
    target: str = typer.Option(
        "kafka", "--target", "-t", help="Target dispatcher: kafka or postgres."
    ),
    kafka_bootstrap: str = typer.Option(
        "localhost:9092", "--kafka-bootstrap", help="Kafka broker bootstrap servers."
    ),
    rate: float = typer.Option(1000.0, "--rate", "-r", help="Base event rate (events/sec)."),
    speed_factor: float = typer.Option(
        1.0, "--speed-factor", help="Virtual clock acceleration factor."
    ),
    dashboard: bool = typer.Option(
        True, "--dashboard/--no-dashboard", help="Display interactive Rich Live dashboard."
    ),
    mock: bool = typer.Option(
        False, "--mock", help="Run with mock dispatcher (does not require local Kafka/Postgres)."
    ),
    limit: int | None = typer.Option(None, "--limit", "-n", help="Stop after streaming N events."),
) -> None:
    """Stream continuous lifecycle events with chaos injection and traffic curves."""
    config = load_config(schema)
    sim = LifecycleSimulator(config, speed_factor=speed_factor)
    anomaly_injector = AnomalyInjector(config.anomalies)
    traffic_curve = DiurnalTrafficCurve(base_rate=rate)
    stats = StreamStats()
    tui = RichLiveDashboard(config.name, target.upper())

    async def _run_stream() -> None:
        dispatcher: KafkaStreamer | None = None
        if target.lower() == "kafka":
            dispatcher = KafkaStreamer(
                bootstrap_servers=kafka_bootstrap,
                mock_mode=mock,
            )
            await dispatcher.start()

        events_generator = sim.stream_events()
        event_count = 0

        try:
            if dashboard:
                with Live(tui.render(stats), refresh_per_second=4, console=console) as live:
                    async for raw_event in events_generator:
                        _target_rate = traffic_curve.get_rate()
                        event, anomaly = anomaly_injector.inject(raw_event)
                        if dispatcher:
                            await dispatcher.send_event(event)

                        stats.record_event(event.entity_name, event.state, anomaly)
                        live.update(tui.render(stats))
                        event_count += 1
                        if limit and event_count >= limit:
                            break
            else:
                async for raw_event in events_generator:
                    _target_rate = traffic_curve.get_rate()
                    event, anomaly = anomaly_injector.inject(raw_event)
                    if dispatcher:
                        await dispatcher.send_event(event)
                    stats.record_event(event.entity_name, event.state, anomaly)
                    event_count += 1
                    if event_count % 500 == 0:
                        console.print(
                            f"Emitted {event_count:,} events ({stats.current_eps:.1f} EPS, target: {_target_rate:.0f})"
                        )
                    if limit and event_count >= limit:
                        break
        finally:
            if dispatcher:
                await dispatcher.stop()

    asyncio.run(_run_stream())
    console.print(
        f"\n[bold green]Streaming completed.[/] Total events emitted: {stats.events_emitted:,}"
    )


@app.command()
def verify(
    schema: Path = typer.Option(..., "--schema", "-s", help="Path to YAML schema.", exists=True),
    data_dir: Path = typer.Option(
        ..., "--data-dir", "-d", help="Directory with generated .jsonl files.", exists=True
    ),
) -> None:
    """Audit relational referential integrity on generated outputs using in-memory DuckDB."""
    config = load_config(schema)
    verifier = RelationalVerifier(config)

    with console.status("[bold green]Running DuckDB referential integrity queries..."):
        report = verifier.verify_jsonl_directory(data_dir)

    console.print(
        Panel.fit(
            report.summary(),
            title="Integrity Verification Audit",
            border_style="green" if report.passed else "red",
        )
    )

    if not report.passed:
        raise typer.Exit(code=1)


@app.command()
def introspect(
    db: str = typer.Option(
        ..., "--db", help="PostgreSQL connection URI (e.g. postgresql://user:pass@host:5432/db)."
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="File to write generated YAML schema to."
    ),
) -> None:
    """Reverse engineer existing PostgreSQL schema into SyntheticForge YAML definition."""
    introspector = SchemaIntrospector(db)

    async def _do_introspect() -> str:
        schema_dict = await introspector.introspect()
        return introspector.to_yaml(schema_dict)

    yaml_content = asyncio.run(_do_introspect())
    if output:
        output.write_text(yaml_content, encoding="utf-8")
        console.print(f"[bold green]Wrote introspected schema to {output}[/]")
    else:
        console.print(yaml_content)


if __name__ == "__main__":
    app()
