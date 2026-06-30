"""Nautobot Job: GenerateEvidencePack.

Renders an evidence pack Markdown file from the Golden Config compliance
data stored in Nautobot. The output satisfies CMMC 2.0 control families
CM-2, CM-6, CM-8, AU-2 by capturing:

  - Device inventory (CM-8)
  - Intended vs. running configuration diffs (CM-2, CM-6)
  - Compliance pass/fail status per device (CM-6)
  - Operator identity and job timestamp (AU-2)

Nautobot Jobs API reference:
  https://docs.nautobot.com/projects/core/en/stable/user-guide/platform-functionality/jobs/
"""

from __future__ import annotations

import datetime
import os
import pathlib
from typing import Any

from jinja2 import Environment, FileSystemLoader

# Nautobot 3.x Job base class
# https://docs.nautobot.com/projects/core/en/stable/user-guide/platform-functionality/jobs/
from nautobot.apps.jobs import Job, register_jobs
from nautobot.dcim.models import Device
from nautobot.extras.models import JobResult

# nautobot_golden_config models
# https://docs.nautobot.com/projects/golden-config/en/latest/
try:
    from nautobot_golden_config.models import GoldenConfig, ComplianceRule, ConfigCompliance
except ImportError:
    GoldenConfig = None  # type: ignore[assignment,misc]
    ComplianceRule = None  # type: ignore[assignment,misc]
    ConfigCompliance = None  # type: ignore[assignment,misc]

TEMPLATE_DIR = pathlib.Path(__file__).parent.parent.parent / "evidence" / "templates"
OUTPUT_DIR = pathlib.Path(__file__).parent.parent.parent / "evidence" / "output"


class GenerateEvidencePack(Job):
    """Generate a dated Markdown evidence pack for CMMC 2.0 audit.

    Queries Nautobot for current compliance state and renders
    evidence/templates/evidence_pack.md.j2 to evidence/output/.
    """

    class Meta:
        name = "Generate Evidence Pack"
        description = "Render CMMC 2.0 evidence pack (CM-2, CM-6, CM-8, AU-2)"
        has_sensitive_variables = False

    def run(self) -> None:
        """Execute the evidence generation job."""
        self.logger.info("Starting evidence pack generation")

        timestamp = datetime.datetime.utcnow()
        date_str = timestamp.strftime("%Y%m%d_%H%M%S")
        operator = self._get_operator()

        devices = self._collect_device_inventory()
        compliance_data = self._collect_compliance_data()

        context: dict[str, Any] = {
            "timestamp": timestamp.isoformat() + "Z",
            "date_str": date_str,
            "operator": operator,
            "site": "HQ-TX-01",
            "devices": devices,
            "compliance": compliance_data,
            "control_mapping": self._control_mapping(),
        }

        output_path = self._render_evidence(context, date_str)
        self.logger.info(f"Evidence pack written to {output_path}")
        return f"Evidence pack: {output_path}"

    def _get_operator(self) -> str:
        """Return the job submitter's username for AU-2 attribution."""
        if hasattr(self, "request") and self.request and hasattr(self.request, "user"):
            return str(self.request.user)
        return os.getenv("NAUTOBOT_OPERATOR", "admin")

    def _collect_device_inventory(self) -> list[dict[str, Any]]:
        """Return structured device inventory for CM-8."""
        results = []
        for dev in Device.objects.filter(location__name="HQ-TX-01").order_by("name"):
            results.append(
                {
                    "name": dev.name,
                    "role": str(dev.role) if dev.role else "unknown",
                    "platform": str(dev.platform) if dev.platform else "unknown",
                    "primary_ip": str(dev.primary_ip4) if dev.primary_ip4 else "unset",
                    "status": str(dev.status),
                }
            )
        return results

    def _collect_compliance_data(self) -> list[dict[str, Any]]:
        """Return per-device compliance results with diffs for CM-2/CM-6."""
        results = []
        if ConfigCompliance is None:
            self.logger.warning("nautobot_golden_config not installed — skipping compliance data")
            return results

        for cc in ConfigCompliance.objects.select_related("device", "rule").order_by("device__name"):
            results.append(
                {
                    "device": cc.device.name,
                    "rule": cc.rule.feature if hasattr(cc, "rule") else str(cc),
                    "compliant": cc.compliance,
                    "diff": cc.diff or "",
                    "actual": cc.actual or "",
                    "intended": cc.intended or "",
                }
            )
        return results

    def _control_mapping(self) -> list[dict[str, str]]:
        """Map NIST SP 800-171 Rev 2 control IDs to this job's outputs."""
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
                "evidence": "Compliance diffs — compliant column in this report",
            },
            {
                "control_id": "3.4.8",
                "family": "CM-8",
                "description": "Maintain a current inventory of organizational systems",
                "evidence": "Device inventory table in this report",
            },
            {
                "control_id": "3.3.1",
                "family": "AU-2",
                "description": "Create and retain audit logs",
                "evidence": "Operator field + job timestamp in this report",
            },
        ]

    def _render_evidence(self, context: dict[str, Any], date_str: str) -> str:
        """Render the Jinja2 evidence template and write output file."""
        env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        template = env.get_template("evidence_pack.md.j2")
        rendered = template.render(**context)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / f"evidence_pack_{date_str}.md"
        output_path.write_text(rendered)
        return str(output_path)


register_jobs(GenerateEvidencePack)
