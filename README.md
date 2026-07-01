# overwatch7six-netauto-demo

A fully-working Network to Code (NTC) portfolio demo proving CMMC 2.0 Level 2 compliance automation on a virtual GovCon branch network. No paid dependencies. Everything runs on a single Ubuntu 22.04 host.

## What this proves

| Capability | Tool | NIST SP 800-171 Rev 2 |
|---|---|---|
| Baseline configuration management | Custom Nautobot Job + Jinja2 (`RenderGoldenConfig`) | 3.4.1 (CM-2) |
| Configuration enforcement | Nornir remediation | 3.4.2 (CM-6) |
| Restricted/disabled functions | Compliance rules (aaa, mgmt_api) | 3.4.7 (CM-7) |
| Device inventory | Nautobot DCIM | 3.4.8 (CM-8) |
| Audit log creation | Nautobot job attribution + syslog config | 3.3.1 (AU-2) |
| Audit record content | Operator + timestamp in evidence pack | 3.3.2 (AU-3) |

The demo runs this sequence live:

1. Seed Nautobot SoT with 4 cEOS devices, IPAM, and VLANs.
2. Render intended configurations from Jinja2 templates via a custom Nautobot Job (`RenderGoldenConfig`) — no paid/plugin dependency, see [docs/architecture.md](docs/architecture.md).
3. Deploy the lab (`make lab-up`) — Containerlab boots the cEOS containers with those configs.
4. Run compliance check — all devices pass.
5. Introduce drift (`make drift`) — SNMPv3 is removed from acc1.
6. Re-run compliance — acc1 fails with a diff.
7. Remediate (`make remediate`) — Nornir pushes the intended config back.
8. Re-run compliance — 100% pass restored.
9. Generate evidence pack — a dated Markdown file with device inventory, compliance diffs, and operator attribution.

## Prerequisites

A single Ubuntu 22.04 (or Debian 12) host with:

- Docker Engine 24+ and Docker Compose v2 (`docker compose`)
- [Containerlab](https://containerlab.dev/install/) latest stable
- Python 3.11
- An Arista cEOS-lab image (see [Sideloading cEOS](#sideloading-ceos) below)

## Quickstart (≤10 commands from clone to compliance pass)

```bash
git clone https://github.com/patriot7six/overwatch7six-netauto-demo.git
cd overwatch7six-netauto-demo

# 1. Bootstrap Python environment
make bootstrap
source .venv/bin/activate

# 2. Start Nautobot (Postgres, Redis, Celery, UI)
make nautobot-up
# Wait ~60s for health checks — UI at http://localhost:8080 (admin/admin)

# 3. Seed source of truth
make seed

# 4. Render intended configs
make render

# 5. Bring up virtual topology
make lab-up

# 6. Run compliance check (expect 100% pass)
make compliance

# 7. Introduce drift and detect it
make drift
make compliance

# 8. Remediate and verify
make remediate
make compliance

# 9. Generate evidence pack
make evidence
```

## Sideloading cEOS

Arista distributes cEOS-lab as a `.tar.xz` archive from their [software portal](https://www.arista.com/en/support/software-download).

```bash
# Download cEOS64-lab-<version>.tar.xz from Arista portal (free account required)
docker import cEOS64-lab-<version>.tar.xz ceos:latest
docker images | grep ceos   # verify
```

Containerlab picks up the `ceos:latest` tag automatically from `clab/hq-tx-01.clab.yml`.

## CMMC Mapping Table

| NIST SP 800-171 Rev 2 ID | Control Family | Control Name | Demo Evidence |
|---|---|---|---|
| 3.4.1 | CM-2 | Baseline Configurations | Rendered intended configs in `golden_config/intended/` (`RenderGoldenConfig` job) |
| 3.4.2 | CM-6 | Security Configuration Settings | Compliance rule pass/fail with diffs |
| 3.4.7 | CM-7 | Nonessential Capabilities | `aaa` and `mgmt_api` compliance rules |
| 3.4.8 | CM-8 | System Component Inventory | Nautobot DCIM device inventory |
| 3.3.1 | AU-2 | Event Logging | Syslog config enforced; operator attribution in evidence pack |
| 3.3.2 | AU-3 | Content of Audit Records | Timestamps, device names, operator in evidence pack |
| 3.3.7 | AU-8 | Time Stamps | NTP compliance rule |

## Topology

```
                   ┌─────────┐
                   │  rtr1   │  192.0.2.10   10.255.255.1/32
                   │  edge   │  Et1: 10.0.0.0/31
                   └────┬────┘
                        │ Et1
                   ┌────┴────┐
                   │  dist1  │  192.0.2.11   10.255.255.2/32
                   │  dist   │
                   └──┬───┬──┘
                Et2 ──┘   └── Et3
          ┌──────────┐       ┌──────────┐
          │   acc1   │       │   acc2   │
          │ 192.0.2.12│      │ 192.0.2.13│
          │ VL10/20/30│      │ VL10/20/30│
          └──────────┘       └──────────┘

Management network: 192.0.2.0/24 (OOB, separate from data plane)
mgmt container:  192.0.2.2  (syslog collector, NTP)
ztp  container:  192.0.2.3  (HTTP config server for bootstrap)
```

## Screenshots

> Run `make demo` and paste screenshots here.

- `docs/images/nautobot-devices.png` — Nautobot device list showing HQ-TX-01
- `docs/images/compliance-pass.png` — Nornir compliance report (all green)
- `docs/images/compliance-fail.png` — acc1 failing SNMPv3 rule after drift
- `docs/images/evidence-pack.png` — Generated Markdown evidence pack

## Project layout

```
overwatch7six-netauto-demo/
├── clab/                  Containerlab topology + startup configs
├── data/                  Nautobot SoT seed script and YAML fixtures
├── golden_config/         Jinja2 templates, compliance rules, rendered output
├── nautobot/              Docker Compose stack + Nautobot Jobs
├── nornir/                Nornir config, inventory, backup/compliance/remediate tasks
├── evidence/              Evidence pack template and dated output files
├── tests/                 pytest suite (fixture validation + template render)
└── docs/                  Architecture, CMMC mapping, runbook
```

## Why this exists

Built by Patriot 7Six LLC / Overwatch7Six to demonstrate that compliance automation
for CMMC 2.0 doesn't require proprietary tooling or cloud spend — just a solid NTC stack,
good Jinja2 discipline, and the willingness to actually run the thing.
