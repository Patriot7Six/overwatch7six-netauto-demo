"""Nautobot Job: DeployIntendedConfig.

Triggers Golden Config to render intended configurations for all devices
in HQ-TX-01, then dispatches Nornir to push the rendered configs to
non-compliant devices.

This job implements the CM-6 control: configuration settings are enforced
on managed systems by comparing current state to the SoT-derived intended
config and pushing diffs where needed.

Golden Config Job API reference:
  https://docs.nautobot.com/projects/golden-config/en/latest/user/navigating-golden/
Nautobot Jobs API:
  https://docs.nautobot.com/projects/core/en/stable/user-guide/platform-functionality/jobs/
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from nautobot.apps.jobs import Job, register_jobs
from nautobot.dcim.models import Device

try:
    from nautobot_golden_config.jobs import AllGoldenConfig
except ImportError:
    AllGoldenConfig = None  # type: ignore[assignment,misc]

# Path to Nornir remediation task relative to the repo root
REMEDIATE_SCRIPT = Path(__file__).parent.parent.parent / "nornir" / "tasks" / "remediate.py"


class DeployIntendedConfig(Job):
    """Render intended configs and push them to non-compliant devices.

    Step 1: Run Golden Config generate-all to refresh intended configs.
    Step 2: Run Golden Config compliance check to identify drift.
    Step 3: Call Nornir remediate.py for devices with compliance failures.
    """

    class Meta:
        name = "Deploy Intended Config"
        description = (
            "Render Golden Config templates and push to non-compliant devices (CM-6)"
        )
        has_sensitive_variables = False

    def run(self) -> str:
        """Execute the deploy sequence."""
        self.logger.info("Step 1: Triggering Golden Config generate-all")
        self._run_golden_config_generate()

        self.logger.info("Step 2: Running compliance check")
        non_compliant = self._check_compliance()

        if not non_compliant:
            self.logger.info("All devices compliant — nothing to deploy")
            return "All devices compliant. No deployment needed."

        self.logger.warning(f"Non-compliant devices: {non_compliant}")

        self.logger.info("Step 3: Running Nornir remediation")
        result = self._run_nornir_remediate(non_compliant)

        return f"Deployed to: {non_compliant}\nNornir output:\n{result}"

    def _run_golden_config_generate(self) -> None:
        """Trigger the Golden Config AllGoldenConfig job synchronously."""
        if AllGoldenConfig is None:
            self.logger.warning("nautobot_golden_config not available — skipping generate")
            return
        # Golden Config's AllGoldenConfig job generates intended configs for all
        # devices that match the GoldenConfigSetting scope.
        # https://docs.nautobot.com/projects/golden-config/en/latest/user/navigating-golden/
        job = AllGoldenConfig()
        job.run(data={}, commit=True)

    def _check_compliance(self) -> list[str]:
        """Return names of devices with compliance failures."""
        try:
            from nautobot_golden_config.models import ConfigCompliance
        except ImportError:
            return []

        non_compliant = (
            ConfigCompliance.objects.filter(compliance=False)
            .select_related("device")
            .values_list("device__name", flat=True)
            .distinct()
        )
        return list(non_compliant)

    def _run_nornir_remediate(self, device_names: list[str]) -> str:
        """Invoke nornir/tasks/remediate.py as a subprocess with device filter."""
        env_filter = ",".join(device_names)
        result = subprocess.run(
            [sys.executable, str(REMEDIATE_SCRIPT), "--devices", env_filter],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            self.logger.error(f"Nornir remediation failed:\n{result.stderr}")
        return result.stdout + result.stderr


register_jobs(DeployIntendedConfig)
