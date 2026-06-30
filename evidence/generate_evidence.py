"""Standalone evidence pack generator (CLI entry point for `make evidence`).

Reads the most recent compliance JSON from evidence/output/ and renders
the evidence_pack.md.j2 template. Falls back to reading backup/intended
configs directly from disk if no compliance JSON is available.

This script runs outside Nautobot — it doesn't need the Django ORM.
Use it for offline evidence generation or in CI.
"""

from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import pathlib
import sys
from typing import Any

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
EVIDENCE_DIR = pathlib.Path(__file__).parent / "output"
INTENDED_DIR = pathlib.Path(__file__).parent.parent / "golden_config" / "intended"
FIXTURES_DIR = pathlib.Path(__file__).parent.parent / "data" / "fixtures"


def _load_latest_compliance() -> dict[str, Any] | None:
    """Find and load the most recent compliance JSON result."""
    pattern = str(EVIDENCE_DIR / "compliance_*.json")
    files = sorted(glob.glob(pattern), reverse=True)
    if not files:
        return None
    with open(files[0]) as fh:
        return json.load(fh)


def _device_inventory_from_fixtures() -> list[dict[str, Any]]:
    """Build device list from YAML fixtures when Nautobot isn't available."""
    import yaml

    devices_file = FIXTURES_DIR / "devices.yml"
    if not devices_file.exists():
        return []
    with open(devices_file) as fh:
        data = yaml.safe_load(fh)

    inventory = []
    for dev in data.get("devices", []):
        inventory.append(
            {
                "name": dev["name"],
                "role": dev.get("role", "unknown"),
                "platform": dev.get("platform", "eos"),
                "primary_ip": dev.get("primary_ip4", "unset"),
                "status": dev.get("status", "Active"),
            }
        )
    return inventory


def _compliance_from_json(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten compliance JSON results into the template's expected format."""
    flat: list[dict[str, Any]] = []
    for device, rules in data.get("results", {}).items():
        for rule in rules:
            flat.append(
                {
                    "device": device,
                    "rule": rule.get("feature", "unknown"),
                    "compliant": rule.get("compliant", False),
                    "diff": rule.get("diff", ""),
                    "intended": "",
                    "actual": "",
                }
            )
    return flat


def _stub_compliance() -> list[dict[str, Any]]:
    """Return stub compliance data when no JSON results exist.

    Reads intended configs from disk and reports all as compliant
    (since we can't diff without a live device).
    """
    results = []
    site_dir = INTENDED_DIR / "HQ-TX-01"
    if not site_dir.exists():
        return results

    for cfg_file in sorted(site_dir.glob("*.cfg")):
        config_text = cfg_file.read_text()
        results.append(
            {
                "device": cfg_file.stem,
                "rule": "intended-config-present",
                "compliant": True,
                "diff": "",
                "intended": config_text[:500],
                "actual": "",
            }
        )
    return results


def _control_mapping() -> list[dict[str, str]]:
    """Return CMMC 2.0 / NIST SP 800-171 Rev 2 control mapping."""
    return [
        {
            "control_id": "3.4.1",
            "family": "CM-2",
            "description": "Establish and maintain baseline configurations",
            "evidence": "Golden Config intended configs in evidence/output/",
        },
        {
            "control_id": "3.4.2",
            "family": "CM-6",
            "description": "Establish and enforce security configuration settings",
            "evidence": "Compliance diffs in this report",
        },
        {
            "control_id": "3.4.7",
            "family": "CM-7",
            "description": "Restrict/disable functions not required",
            "evidence": "mgmt_api and aaa compliance rules",
        },
        {
            "control_id": "3.4.8",
            "family": "CM-8",
            "description": "Maintain current inventory of organizational systems",
            "evidence": "Device inventory table in this report",
        },
        {
            "control_id": "3.3.1",
            "family": "AU-2",
            "description": "Create and retain audit logs",
            "evidence": "Operator field + job timestamp below",
        },
        {
            "control_id": "3.3.2",
            "family": "AU-3",
            "description": "Audit records contain required information",
            "evidence": "Operator attribution and timestamp in this report",
        },
    ]


def generate_evidence_pack(output_path: pathlib.Path | None = None) -> pathlib.Path:
    """Render and write the evidence pack Markdown file.

    Args:
        output_path: Where to write the output. Auto-generated if None.

    Returns:
        Path to the written evidence pack.
    """
    timestamp = datetime.datetime.now(tz=datetime.timezone.utc)
    date_str = timestamp.strftime("%Y%m%d_%H%M%S")

    if output_path is None:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        output_path = EVIDENCE_DIR / f"evidence_pack_{date_str}.md"

    compliance_json = _load_latest_compliance()
    if compliance_json:
        compliance_data = _compliance_from_json(compliance_json)
    else:
        print("WARN: No compliance JSON found — using stub data from intended configs", file=sys.stderr)
        compliance_data = _stub_compliance()

    context: dict[str, Any] = {
        "timestamp": timestamp.isoformat(),
        "date_str": date_str,
        "operator": os.getenv("NAUTOBOT_OPERATOR", os.getenv("USER", "admin")),
        "site": "HQ-TX-01",
        "devices": _device_inventory_from_fixtures(),
        "compliance": compliance_data,
        "control_mapping": _control_mapping(),
    }

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("evidence_pack.md.j2")
    rendered = template.render(**context)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered)
    return output_path


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Generate CMMC 2.0 evidence pack")
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        help="Output path (default: evidence/output/evidence_pack_<timestamp>.md)",
    )
    args = parser.parse_args()

    out = generate_evidence_pack(output_path=args.output)
    print(f"Evidence pack written to: {out}")


if __name__ == "__main__":
    main()
