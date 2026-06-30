"""Nornir task: back up running configurations from all HQ-TX-01 devices.

Connects via NAPALM (EOS eAPI), retrieves the running config, and writes
each device's config to golden_config/backups/<location>/<device>.cfg.

This implements the backup leg of Golden Config's workflow — the "actual"
config stored for compliance comparison.

NAPALM EOS driver reference: https://napalm.readthedocs.io/en/latest/support/
nornir-napalm reference: https://github.com/nautobot/nornir-napalm
"""

from __future__ import annotations

import os
import pathlib
from typing import Any

from nornir import InitNornir
from nornir.core.task import Result, Task
from nornir_napalm.plugins.tasks import napalm_get
from nornir_utils.plugins.functions import print_result
from rich.console import Console
from rich.table import Table

BACKUP_DIR = pathlib.Path(__file__).parent.parent.parent / "golden_config" / "backups"
NORNIR_CONFIG = pathlib.Path(__file__).parent.parent / "config.yaml"

console = Console()


def backup_device_config(task: Task) -> Result:
    """Retrieve and store the running configuration for a single device."""
    result = task.run(
        task=napalm_get,
        getters=["config"],
        retrieve="running",
    )
    config_text: str = result[0].result["config"]["running"]

    location = task.host.get("location", "unknown")
    out_dir = BACKUP_DIR / location
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{task.host.name}.cfg"
    out_path.write_text(config_text)

    return Result(
        host=task.host,
        result=f"Backed up {len(config_text)} chars to {out_path}",
    )


def run_backup(device_filter: str | None = None) -> dict[str, Any]:
    """Run the backup task against all (or filtered) HQ-TX-01 devices.

    Args:
        device_filter: Comma-separated device names to restrict the run.
                       None means run against all inventory devices.

    Returns:
        Dict mapping device name to backup path.
    """
    nr = InitNornir(config_file=str(NORNIR_CONFIG))

    if device_filter:
        names = [d.strip() for d in device_filter.split(",")]
        nr = nr.filter(filter_func=lambda h: h.name in names)

    console.print(f"[bold]Backing up {len(nr.inventory.hosts)} device(s)...[/bold]")
    results = nr.run(task=backup_device_config, name="backup_running_config")
    print_result(results)

    summary: dict[str, Any] = {}
    for host, result in results.items():
        summary[host] = {
            "failed": result.failed,
            "result": str(result[0].result) if not result.failed else str(result[0].exception),
        }
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Back up running configs from HQ-TX-01 devices")
    parser.add_argument("--devices", help="Comma-separated device names to target")
    args = parser.parse_args()

    run_backup(device_filter=args.devices)
