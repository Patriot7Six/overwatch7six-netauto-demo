"""Nautobot Job: RenderGoldenConfig.

Renders per-device intended configurations from the Jinja2 templates in
golden_config/templates/ and writes them to
golden_config/intended/<location>/<device>.cfg.

This repo does not install the nautobot-golden-config plugin (see
docs/runbook.md) — this job reproduces just the "render intended config"
piece of that plugin as a plain Nautobot Job, using the same `obj` (Django
Device instance) template context the plugin would provide, so the existing
templates under golden_config/templates/ needed no changes.

Nautobot Jobs API reference:
  https://docs.nautobot.com/projects/core/en/stable/user-guide/platform-functionality/jobs/
"""

from __future__ import annotations

import pathlib

from jinja2 import Environment, FileSystemLoader

from nautobot.apps.jobs import Job, register_jobs
from nautobot.dcim.models import Device

# golden_config/ is bind-mounted read-write into the container at this path
# (see nautobot/docker-compose.yml) so rendered output lands back on the host.
TEMPLATE_DIR = pathlib.Path("/opt/nautobot/golden_config/templates")
INTENDED_DIR = pathlib.Path("/opt/nautobot/golden_config/intended")


class RenderGoldenConfig(Job):
    """Render Jinja2 intended configs for all in-scope HQ-TX-01 devices."""

    class Meta:
        name = "Render Golden Config"
        description = "Render Jinja2 intended configs for HQ-TX-01 devices (CM-2)"
        has_sensitive_variables = False

    def run(self) -> str:
        """Render one intended config file per device."""
        env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

        devices = Device.objects.filter(
            location__name="HQ-TX-01",
            platform__slug="eos",
            status__name="Active",
        ).select_related("location", "role", "platform")

        rendered: list[str] = []
        for device in devices:
            if device.role is None:
                raise RuntimeError(f"{device.name} has no role assigned — cannot select a template")

            # Resolved by role slug (not name) per docs/assumptions.md — devices
            # with an unmapped role fail the job intentionally, to catch
            # misconfiguration early rather than silently skipping a device.
            template_name = f"roles/{device.role.slug}.j2"
            try:
                template = env.get_template(template_name)
            except Exception as exc:
                raise RuntimeError(f"{device.name}: template {template_name} not found") from exc

            config = template.render(obj=device)

            out_dir = INTENDED_DIR / device.location.name
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{device.name}.cfg"
            out_path.write_text(config)

            self.logger.info(f"Rendered {out_path}")
            rendered.append(device.name)

        if not rendered:
            return "No devices rendered — check location/platform/status scope."
        return f"Rendered intended configs for: {', '.join(rendered)}"


register_jobs(RenderGoldenConfig)
