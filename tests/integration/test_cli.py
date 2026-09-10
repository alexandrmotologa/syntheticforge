"""Integration tests for SyntheticForge CLI commands."""

from pathlib import Path

from typer.testing import CliRunner

from syntheticforge.cli import app

runner = CliRunner()


def test_cli_inspect() -> None:
    result = runner.invoke(app, ["inspect", "schemas/e-commerce-flow.yaml"])
    assert result.exit_code == 0
    assert "e-commerce-flow" in result.output
    assert "Execution Stages" in result.output
    assert "customers" in result.output
    assert "orders" in result.output


def test_cli_generate_jsonl_and_verify(tmp_path: Path) -> None:
    out_dir = tmp_path / "jsonl_out"

    # 1. Generate JSONL
    gen_result = runner.invoke(
        app,
        [
            "generate",
            "--schema",
            "schemas/e-commerce-flow.yaml",
            "--sink",
            "jsonl",
            "--output-dir",
            str(out_dir),
        ],
    )
    assert gen_result.exit_code == 0
    assert (out_dir / "customers.jsonl").exists()
    assert (out_dir / "orders.jsonl").exists()
    assert (out_dir / "payments.jsonl").exists()
    assert (out_dir / "shipments.jsonl").exists()

    # 2. Verify with DuckDB verifier
    verify_result = runner.invoke(
        app,
        ["verify", "--schema", "schemas/e-commerce-flow.yaml", "--data-dir", str(out_dir)],
    )
    assert verify_result.exit_code == 0
    assert "Relational Verification: PASSED" in verify_result.output


def test_cli_generate_parquet(tmp_path: Path) -> None:
    out_dir = tmp_path / "parquet_out"
    gen_result = runner.invoke(
        app,
        [
            "generate",
            "--schema",
            "schemas/fintech-kyc-flow.yaml",
            "--sink",
            "parquet",
            "--output-dir",
            str(out_dir),
        ],
    )
    assert gen_result.exit_code == 0
    assert (out_dir / "users.parquet").exists()
    assert (out_dir / "accounts.parquet").exists()


def test_cli_stream_mock() -> None:
    stream_result = runner.invoke(
        app,
        [
            "stream",
            "--schema",
            "schemas/e-commerce-flow.yaml",
            "--target",
            "kafka",
            "--mock",
            "--limit",
            "25",
            "--no-dashboard",
            "--speed-factor",
            "1000",
        ],
    )
    assert stream_result.exit_code == 0
    assert "Streaming completed" in stream_result.output
    assert "Total events emitted: 25" in stream_result.output
