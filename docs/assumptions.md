# Assumptions and Design Decisions

This file documents every assumption made during repo construction that isn't
directly stated in the mission brief. If any of these turn out to be wrong,
the relevant files to update are noted.

## Nautobot version

**Assumption:** Nautobot 3.1.x (latest 3.1 patch).
**Rationale:** The brief specifies "3.1.x". The Docker image tag is pinned to
`3.1` in `nautobot/environment/local.env.example`. Update `NAUTOBOT_VERSION`
to bump.

## Nautobot API token

**Assumption:** The demo superuser API token is the 40-char string
`aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` (all-a's) set via
`NAUTOBOT_SUPERUSER_API_TOKEN` in `creds.env.example`.
**Rationale:** Simplifies `make seed` and `make compliance` — no token
discovery step. For a production deployment, generate a real token and store
it in a secrets manager. Change it in `creds.env` and set `NAUTOBOT_TOKEN`
in your shell.

## cEOS image tag

**Assumption:** The cEOS image is tagged `ceos:latest` after import.
**Rationale:** The `clab.yml` references `ceos:latest`. If your import produces
a different tag, update the `image:` field in `clab/hq-tx-01.clab.yml`.

## eAPI transport

**Assumption:** NAPALM connects to cEOS via HTTPS on port 443 (eAPI).
**Rationale:** This is the default for the `napalm-eos` driver. cEOS enables
eAPI on Management0 by default when `management api http-commands / no shutdown`
is in the startup config. No additional NAPALM args needed.

## Compliance rule matching

**Assumption:** The `match_config` sections in `golden_config/compliance_rules.yaml`
use exact string matching on stripped lines (no regex).
**Rationale:** The brief doesn't specify a matching algorithm. Exact match on
stripped lines is the simplest approach that works for these cEOS config
patterns and avoids false positives from line-order variance.
If partial/regex matching is needed, update `_check_rule()` in
`nornir/tasks/compliance_report.py`.

## Nornir inventory source

**Assumption:** Nornir pulls inventory from Nautobot at runtime via
`nornir-nautobot`'s `NautobotInventory` plugin, not from static YAML files.
**Rationale:** Dynamic inventory keeps Nornir in sync with Nautobot. The
`nornir/inventory/` directory exists but is empty — it's the mount point
for any future static fallback.

## Golden Config plugin vs. custom Job

**Assumption:** This stack does not install the `nautobot-golden-config`
plugin. `nautobot/jobs/render_golden_config.py` reimplements just the
"render intended config" piece as a plain Nautobot Job (`RenderGoldenConfig`),
using the same `obj` (Django Device instance) template context the plugin
would have provided.
**Rationale:** The plugin was never added to `pyproject.toml`, the Docker
image, or `PLUGINS`, and `golden_config/` was never mounted into the
container — `make render` originally called a Job endpoint
(`GoldenConfigJobAll`) that didn't exist. `golden_config/settings.yml`
documents the equivalent plugin scope/paths for reference only, in case a
future maintainer wants to swap in the real plugin.
**Files to update:** `nautobot/jobs/render_golden_config.py`,
`golden_config/trigger_render.py`, `nautobot/docker-compose.yml` (volume mount).

## Golden Config template path

**Assumption:** `RenderGoldenConfig` resolves templates by role slug:
`roles/{{ obj.role.slug }}.j2`.
**Rationale:** This mirrors the most common pattern in the
nautobot-golden-config documentation. Three role slugs map to three
templates: `edge`, `distribution`, `access`. If a device has an unmapped role
or the template file is missing, the job raises and fails loudly —
intentionally, to catch misconfiguration early rather than silently
producing a partial render.

## Drift demo mechanism

**Assumption:** `make drift` uses SSH (with `StrictHostKeyChecking=no`) to
log into acc1 and manually issue config removal commands.
**Rationale:** The brief requires a drift demo. SSH is the most direct way to
introduce drift on a live cEOS container without modifying Nautobot. In
production you'd use Nornir for this too, but for demo clarity a raw SSH
command makes the "human error" scenario obvious.
**Files to update:** `Makefile` target `drift` — change the SSH commands if
acc1's management IP or credentials change.

## Evidence pack operator attribution

**Assumption:** When running outside Nautobot (CLI via `make evidence`), the
operator is read from `$NAUTOBOT_OPERATOR` env var, falling back to `$USER`,
then `admin`.
**Rationale:** The CLI evidence generator can't query the Nautobot session.
For audit purposes, set `NAUTOBOT_OPERATOR=your.name` in your shell before
running `make evidence`.

## VLAN SVI addressing

**Assumption:** SVIs on dist1 use `10.10.10.1/24`, `10.20.20.1/24`,
`10.30.30.1/24` for VLANs 10, 20, 30 respectively.
**Rationale:** These subnets are defined in `data/fixtures/ip_addresses.yml`
as VLAN prefixes and are consistent with the addressing plan in the brief.
They're hardcoded in the distribution template because no per-VLAN IP
assignments exist in the fixture data — adding them would require Nautobot
IPAM prefix-to-VLAN associations which are outside the brief's scope.

## ZTP service

**Assumption:** The `ztp` container serves startup configs over HTTP using
a minimal Flask app on port 8000.
**Rationale:** The brief mentions a ZTP container but doesn't specify the
protocol. HTTP is the simplest option compatible with cEOS's ZTP capability.
In a real deployment you'd use DHCP option 67 + ZTP script; that's out of
scope for a single-host lab demo.

## nautobot_plugin_nornir vs nornir-nautobot

**Assumption:** `nautobot-plugin-nornir` is the Nautobot app (installs
into Nautobot's Django), while `nornir-nautobot` is the standalone PyPI
package used by the Nornir scripts outside of Nautobot.
**Rationale:** These are two separate packages that serve different roles.
The Docker container lists `nautobot_plugin_nornir` in `NAUTOBOT_INSTALLED_APPS`.
The venv installs `nornir-nautobot` for the CLI scripts.
