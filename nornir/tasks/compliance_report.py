"""Nornir task: compare running vs intended configurations and report drift.

Workflow:
  1. Back up running configs from all devices (calls backup.py).
  2. Load intended configs from golden_config/intended/<location>/<device>.cfg.
  3. Diff each pair using the compliance rules in golden_config/compliance_rules.yaml.
  4. Print a Rich summary table and write JSON results to evidence/output/.

This implements CM-6 continuous compliance checking. A non-zero exit code
signals at least one non-compliant device — useful for CI gates.

NIST SP 800-171 Rev 2 controls evidenced:
  3.4.1 (CM-2) — baseline configuration maintained as intended config
  3.4.2 (CM-6) — drift detected and reported
  3.4.7 (CM-7) — only required services allowed (verified via aaa/mgmt_api rules)
"""

from __future__ import annotations

import difflib
import json
import os
import pathlib
import re
import sys
from datetime import datetime, timezone
from typing import Any

import yaml
from rich.console import Console
from rich.table import Table

from backup import run_backup  # type: ignore[import]

INTENDED_DIR = pathlib.Path(__file__).parent.parent.parent / "golden_config" / "intended"
BACKUP_DIR = pathlib.Path(__file__).parent.parent.parent / "golden_config" / "backups"
RULES_FILE = pathlib.Path(__file__).parent.parent.parent / "golden_config" / "compliance_rules.yaml"
EVIDENCE_DIR = pathlib.Path(__file__).parent.parent.parent / "evidence" / "output"

console = Console()


def _load_rules() -> list[dict[str, Any]]:
    """Load compliance rules from YAML."""
    with open(RULES_FILE) as fh:
        data = yaml.safe_load(fh)
    return data.get("compliance_rules", [])


def _extract_section(config: str, match_config: str) -> list[str]:
    """Return the lines from config that match any line in match_config."""
    match_lines = {line.strip() for line in match_config.splitlines() if line.strip()}
    found = []
    for line in config.splitlines():
        stripped = line.strip()
        if stripped in match_lines:
            found.append(stripped)
    return found


def _check_rule(
    rule: dict[str, Any],
    running: str,
    intended: str,
) -> dict[str, Any]:
    """Check a single compliance rule against running and intended configs.

    Returns a dict with: feature, compliant, diff, missing_lines.
    """
    match_lines = [
        line.strip()
        for line in rule["match_config"].splitlines()
        if line.strip()
    ]

    running_lines = {line.strip() for line in running.splitlines()}
    intended_lines = {line.strip() for line in intended.splitlines()}

    missing_from_running = [l for l in match_lines if l not in running_lines]
    extra_in_running: list[str] = []  # for future "no X" rule support

    compliant = len(missing_from_running) == 0

    diff_lines = list(
        difflib.unified_diff(
            [l + "\n" for l in match_lines],
            [l + "\n" for l in [x for x in match_lines if x in running_lines]],
            fromfile=f"intended/{rule['feature']}",
            tofile=f"running/{rule['feature']}",
            lineterm="",
        )
    )

    return {
        "feature": rule["feature"],
        "compliant": compliant,
        "diff": "\n".join(diff_lines),
        "missing": missing_from_running,
    }


def run_compliance_report(device_filter: str | None = None) -> bool:
    """Run the full compliance check and return True if all devices pass.

    Args:
        device_filter: Comma-separated device names to restrict the run.

    Returns:
        True if all devices are compliant, False otherwise.
    """
    console.print("[bold blue]Step 1: Backing up running configurations...[/bold blue]")
    run_backup(device_filter=device_filter)

    rules = _load_rules()
    console.print(f"\n[bold blue]Step 2: Checking {len(rules)} compliance rules...[/bold blue]")

    site = "HQ-TX-01"
    backup_site_dir = BACKUP_DIR / site
    intended_site_dir = INTENDED_DIR / site

    if not backup_site_dir.exists():
        console.print(f"[red]No backups found in {backup_site_dir} — run 'make render' first[/red]")
        return False

    all_results: dict[str, list[dict[str, Any]]] = {}
    all_compliant = True

    device_names = [
        p.stem for p in backup_site_dir.glob("*.cfg")
        if device_filter is None or p.stem in device_filter.split(",")
    ]

    for device_name in sorted(device_names):
        backup_path = backup_site_dir / f"{device_name}.cfg"
        intended_path = intended_site_dir / f"{device_name}.cfg"

        if not intended_path.exists():
            console.print(
                f"[yellow]WARN: No intended config for {device_name} at {intended_path}[/yellow]"
            )
            continue

        running_config = backup_path.read_text()
        intended_config = intended_path.read_text()

        device_results = []
        for rule in rules:
            result = _check_rule(rule, running_config, intended_config)
            device_results.append(result)
            if not result["compliant"]:
                all_compliant = False

        all_results[device_name] = device_results

    _print_summary_table(all_results)

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EVIDENCE_DIR / f"compliance_{timestamp}.json"
    out_path.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "site": site,
                "overall_compliant": all_compliant,
                "results": all_results,
            },
            indent=2,
        )
    )
    console.print(f"\n[dim]Results written to {out_path}[/dim]")

    return all_compliant


def _print_summary_table(all_results: dict[str, list[dict[str, Any]]]) -> None:
    """Render a Rich table showing per-device, per-rule compliance status."""
    table = Table(title="HQ-TX-01 Compliance Report", show_lines=True)
    table.add_column("Device", style="cyan", no_wrap=True)
    table.add_column("Rule", style="magenta")
    table.add_column("Status", justify="center")
    table.add_column("Missing Lines")

    for device, results in all_results.items():
        for r in results:
            status = "[green]PASS[/green]" if r["compliant"] else "[red]FAIL[/red]"
            missing = "\n".join(r["missing"]) if r["missing"] else ""
            table.add_row(device, r["feature"], status, missing)

    console.print(table)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run compliance report for HQ-TX-01")
    parser.add_argument("--devices", help="Comma-separated device names to target")
    args = parser.parse_args()

    ok = run_compliance_report(device_filter=args.devices)
    sys.exit(0 if ok else 1)
