"""Nornir task: push intended configuration to non-compliant devices.

Loads the intended config for each non-compliant device from
golden_config/intended/ and pushes it via NAPALM's load_replace_candidate
followed by commit_config. This enforces CM-6: configuration settings
are enforced on managed systems.

NAPALM load_replace_candidate replaces the entire running configuration,
which guarantees the device matches the intended config exactly rather than
trying to merge partial changes. Suitable for GovCon environments where
config drift must be fully eradicated, not just partially corrected.

NAPALM reference: https://napalm.readthedocs.io/en/latest/base.html
nornir-napalm: https://github.com/nautobot/nornir-napalm
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

from nornir import InitNornir
from nornir.core.task import Result, Task
from nornir_napalm.plugins.tasks import napalm_configure
from nornir_utils.plugins.functions import print_result
from rich.console import Console

INTENDED_DIR = pathlib.Path(__file__).parent.parent.parent / "golden_config" / "intended"
NORNIR_CONFIG = pathlib.Path(__file__).parent.parent / "config.yaml"

console = Console()


def push_intended_config(task: Task) -> Result:
    """Replace running config with the intended config for this device.

    Reads the intended config from disk and calls napalm_configure with
    replace=True, which calls load_replace_candidate + commit_config.
    """
    location = task.host.get("location", "HQ-TX-01")
    intended_path = INTENDED_DIR / location / f"{task.host.name}.cfg"

    if not intended_path.exists():
        return Result(
            host=task.host,
            result=f"No intended config found at {intended_path} — skipping",
            failed=True,
        )

    config_text = intended_path.read_text()

    result = task.run(
        task=napalm_configure,
        configuration=config_text,
        replace=True,  # full config replace, not merge
        dry_run=False,
    )

    return Result(
        host=task.host,
        result=f"Pushed {len(config_text)} chars to {task.host.name}",
        changed=result[0].changed,
    )


def run_remediate(device_filter: str | None = None) -> dict[str, Any]:
    """Push intended configs to non-compliant (or all targeted) devices.

    Args:
        device_filter: Comma-separated device names to target.
                       If None, targets all inventory devices — use with care.

    Returns:
        Dict mapping device name to remediation result.
    """
    nr = InitNornir(config_file=str(NORNIR_CONFIG))

    if device_filter:
        names = [d.strip() for d in device_filter.split(",")]
        nr = nr.filter(filter_func=lambda h: h.name in names)

    if not nr.inventory.hosts:
        console.print("[yellow]No devices matched the filter — nothing to remediate[/yellow]")
        return {}

    console.print(
        f"[bold red]Remediating {len(nr.inventory.hosts)} device(s): "
        f"{list(nr.inventory.hosts.keys())}[/bold red]"
    )
    console.print("[dim]Using full config replace (load_replace_candidate + commit)[/dim]")

    results = nr.run(task=push_intended_config, name="push_intended_config")
    print_result(results)

    summary: dict[str, Any] = {}
    for host, result in results.items():
        summary[host] = {
            "failed": result.failed,
            "changed": result[0].changed if not result.failed else False,
            "result": str(result[0].result) if not result.failed else str(result[0].exception),
        }

    failed = [h for h, r in summary.items() if r["failed"]]
    if failed:
        console.print(f"\n[red]FAILED on: {failed}[/red]")
    else:
        console.print("\n[green]All devices remediated successfully.[/green]")

    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Push intended config to non-compliant devices")
    parser.add_argument("--devices", help="Comma-separated device names to target")
    args = parser.parse_args()

    results = run_remediate(device_filter=args.devices)
    failed = [h for h, r in results.items() if r["failed"]]
    sys.exit(1 if failed else 0)
