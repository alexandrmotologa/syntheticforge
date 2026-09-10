"""Command-line interface for SyntheticForge."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

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
    """Inspect declarative schema, display topological ordering, and entity relationship graph."""
    config = load_config(schema)
    graph = SchemaGraph(config)

    console.print(
        Panel.fit(
            f"[bold cyan]{config.name}[/] (v{config.version})\n"
            f"[dim]{config.description or 'No description provided.'}[/]",
            title="SyntheticForge Schema Definition",
            border_style="cyan",
        )
    )

    table = Table(title="Topological Generation Order & Entities", show_header=True)
    table.add_column("Stage", justify="right", style="cyan", no_wrap=True)
    table.add_column("Entity", style="bold green")
    table.add_column("Count", justify="right", style="yellow")
    table.add_column("Primary Key", style="magenta")
    table.add_column("Foreign Keys / Dependencies", style="blue")
    table.add_column("Lifecycle States", style="white")

    for stage_idx, stage in enumerate(graph.topological_stages, 1):
        for ent_name in stage:
            ent = config.entities[ent_name]
            fks = (
                ", ".join(f"{fk_field} -> {fk.entity}" for fk_field, fk in ent.foreign_keys.items())
                or "None"
            )
            states = "None"
            if ent.lifecycle and ent.lifecycle.states:
                states = " -> ".join(ent.lifecycle.states[:4])
                if len(ent.lifecycle.states) > 4:
                    states += f" (+{len(ent.lifecycle.states) - 4} more)"

            pk_type = ent.fields[ent.primary_key].type if ent.primary_key in ent.fields else "id"
            table.add_row(
                str(stage_idx),
                ent_name,
                f"{ent.count:,}",
                f"{ent.primary_key} ({pk_type})",
                fks,
                states,
            )

    console.print(table)
    console.print(f"\n[bold]Execution Stages:[/] {len(graph.topological_stages)}")
    console.print(f"[bold]Total Entities:[/] {len(config.entities)}")
    total_records = sum(e.count for e in config.entities.values())
    console.print(f"[bold]Total Records to Generate:[/] {total_records:,}")


@app.command()
def generate(
    schema: Path = typer.Option(..., "--schema", "-s", help="Path to YAML schema.", exists=True),
    sink: str = typer.Option("jsonl", "--sink", help="Output sink: jsonl, parquet, or postgres."),
    output_dir: Path = typer.Option(
        Path("./output"), "--output-dir", "-o", help="Directory for file outputs."
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
        "kafka", "--target", "-t", help="Target dispatcher: kafka, postgres, or webhook."
    ),
    kafka_bootstrap: str = typer.Option(
        "localhost:9092", "--kafka-bootstrap", help="Kafka broker bootstrap servers."
    ),
    webhook_url: str | None = typer.Option(
        None, "--webhook-url", help="HTTP endpoint URL for webhook target."
    ),
    webhook_secret: str | None = typer.Option(
        None, "--webhook-secret", help="HMAC secret key for webhook payload signing."
    ),
    rate: float = typer.Option(1000.0, "--rate", "-r", help="Base event rate (events/sec)."),
    speed_factor: float = typer.Option(
        1.0, "--speed-factor", help="Virtual clock acceleration factor."
    ),
    prometheus_port: int | None = typer.Option(
        None, "--prometheus-port", help="Expose Prometheus metrics on this port (e.g. 9100)."
    ),
    checkpoint_file: Path | None = typer.Option(
        None, "--checkpoint-file", help="Path to save simulation state snapshot upon completion."
    ),
    resume_from: Path | None = typer.Option(
        None, "--resume-from", help="Resume simulation state from an existing checkpoint."
    ),
    dashboard: bool = typer.Option(
        True, "--dashboard/--no-dashboard", help="Display interactive Rich Live dashboard."
    ),
    mock: bool = typer.Option(
        False,
        "--mock",
        help="Run with mock dispatcher (does not require local Kafka/Postgres/Webhook).",
    ),
    limit: int | None = typer.Option(None, "--limit", "-n", help="Stop after streaming N events."),
) -> None:
    """Stream continuous lifecycle events with chaos injection and traffic curves."""
    from syntheticforge.checkpoint import SimulationCheckpoint
    from syntheticforge.metrics import PrometheusExporter
    from syntheticforge.streaming.webhook_streamer import WebhookStreamer

    config = load_config(schema)
    sim = LifecycleSimulator(config, speed_factor=speed_factor)
    anomaly_injector = AnomalyInjector(config.anomalies)
    traffic_curve = DiurnalTrafficCurve(base_rate=rate)
    stats = StreamStats()
    tui = RichLiveDashboard(config.name, target.upper())

    if resume_from and resume_from.exists():
        ckpt = SimulationCheckpoint.load(resume_from)
        ckpt.restore_into(sim.generator.pool, stats)
        console.print(
            f"[bold green]Resumed state from {resume_from} ({stats.events_emitted} prior events).[/]"
        )

    async def _run_stream() -> None:
        dispatcher: Any = None
        target_lower = target.lower()
        if target_lower == "kafka":
            dispatcher = KafkaStreamer(
                bootstrap_servers=kafka_bootstrap,
                mock_mode=mock,
            )
            await dispatcher.start()
        elif target_lower == "webhook":
            url = webhook_url or "http://localhost:8080/webhook"
            dispatcher = WebhookStreamer(
                endpoint_url=url,
                secret_key=webhook_secret,
                mock_mode=mock,
            )
            await dispatcher.start()

        prom_exporter: PrometheusExporter | None = None
        if prometheus_port:
            prom_exporter = PrometheusExporter(port=prometheus_port)
            await prom_exporter.start()

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
                        if prom_exporter:
                            prom_exporter.registry.update_from_stats(stats, target=target)
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
                    if prom_exporter:
                        prom_exporter.registry.update_from_stats(stats, target=target)
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
            if prom_exporter:
                await prom_exporter.stop()

    asyncio.run(_run_stream())

    if checkpoint_file:
        ckpt = SimulationCheckpoint.create(
            virtual_seconds=stats.total_elapsed_seconds,
            pool=sim.generator.pool,
            stats=stats,
        )
        saved = ckpt.save(checkpoint_file)
        console.print(f"[bold green]Saved simulation state checkpoint to {saved}[/]")

    console.print(
        f"\n[bold green]Streaming completed.[/] Total events emitted: {stats.events_emitted:,}"
    )


@app.command()
def studio(
    schema: Path = typer.Option(
        ..., "--schema", "-s", help="Path to YAML schema file.", exists=True
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Server host."),
    port: int = typer.Option(8000, "--port", "-p", help="Server port."),
) -> None:
    """Launch the interactive SyntheticForge Web Studio in your browser."""
    import uvicorn

    from syntheticforge.studio.app import create_studio_app

    console.print(f"[bold cyan]Launching SyntheticForge Web Studio on http://{host}:{port}...[/]")
    studio_app = create_studio_app(schema)
    uvicorn.run(studio_app, host=host, port=port)


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
