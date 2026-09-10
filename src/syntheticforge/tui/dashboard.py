"""Interactive terminal UI dashboard using Rich Live."""

from __future__ import annotations

from datetime import timedelta

from rich.align import Align
from rich.box import ROUNDED
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from syntheticforge.tui.stats import StreamStats


class RichLiveDashboard:
    """Renders a real-time terminal dashboard displaying generation metrics."""

    def __init__(self, schema_name: str, target: str) -> None:
        self.schema_name = schema_name
        self.target = target

    def render(self, stats: StreamStats) -> Layout:
        """Construct the Rich Layout tree based on current StreamStats."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=5),
        )

        layout["main"].split_row(
            Layout(name="entities", ratio=1),
            Layout(name="states", ratio=1),
        )

        # 1. Header
        elapsed = str(timedelta(seconds=int(stats.total_elapsed_seconds)))
        header_text = Text()
        header_text.append(" SYNTHETICFORGE ", style="bold cyan")
        header_text.append(f"| Schema: {self.schema_name} ", style="bold white")
        header_text.append(f"| Target: {self.target} ", style="bold yellow")
        header_text.append(f"| Elapsed: {elapsed} ", style="green")
        header_text.append(
            f"| Rate: {stats.current_eps:.1f} EPS (avg {stats.average_eps:.1f}) ",
            style="bold magenta",
        )
        header_text.append(f"| Total: {stats.events_emitted:,}", style="bold white")
        layout["header"].update(Panel(Align.center(header_text), box=ROUNDED, style="blue"))

        # 2. Entity Distribution Table
        entity_table = Table(title="Entities Dispatched", box=ROUNDED, expand=True)
        entity_table.add_column("Entity", style="cyan", no_wrap=True)
        entity_table.add_column("Count", justify="right", style="green")
        entity_table.add_column("Share", justify="right", style="yellow")

        total = max(1, stats.events_emitted)
        for ent, cnt in sorted(stats.entity_counts.items(), key=lambda x: x[1], reverse=True):
            share = (cnt / total) * 100.0
            entity_table.add_row(ent, f"{cnt:,}", f"{share:.1f}%")

        layout["entities"].update(Panel(entity_table, box=ROUNDED))

        # 3. State Machine Progression Table
        state_table = Table(title="Lifecycle States", box=ROUNDED, expand=True)
        state_table.add_column("State", style="magenta", no_wrap=True)
        state_table.add_column("Count", justify="right", style="green")
        state_table.add_column("Share", justify="right", style="yellow")

        for state, cnt in sorted(stats.state_counts.items(), key=lambda x: x[1], reverse=True):
            share = (cnt / total) * 100.0
            state_table.add_row(state, f"{cnt:,}", f"{share:.1f}%")

        layout["states"].update(Panel(state_table, box=ROUNDED))

        # 4. Footer: Chaos Anomaly Counter
        anomaly_table = Table(box=ROUNDED, expand=True)
        anomaly_table.add_column("Duplicate Keys", justify="center", style="bold red")
        anomaly_table.add_column("Schema Mutations", justify="center", style="bold yellow")
        anomaly_table.add_column("Payload Corruptions", justify="center", style="bold magenta")
        anomaly_table.add_column("Null Injections", justify="center", style="bold cyan")
        anomaly_table.add_column("Out of Order", justify="center", style="bold green")

        anomaly_table.add_row(
            f"{stats.anomaly_counts.get('duplicate_key', 0):,}",
            f"{stats.anomaly_counts.get('schema_mutation', 0):,}",
            f"{stats.anomaly_counts.get('payload_corruption', 0):,}",
            f"{stats.anomaly_counts.get('null_injection', 0):,}",
            f"{stats.anomaly_counts.get('out_of_order', 0):,}",
        )
        layout["footer"].update(
            Panel(anomaly_table, title="Chaos & Anomaly Injections", box=ROUNDED)
        )

        return layout
