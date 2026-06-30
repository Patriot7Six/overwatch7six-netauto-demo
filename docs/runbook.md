# Runbook — 5-Minute Demo Walkthrough

This runbook walks through the full demo sequence. Expected output snippets
are included so you can verify each step succeeded before moving on.

## Prerequisites checklist

- [ ] Docker Engine + Compose v2 installed: `docker compose version` → `Docker Compose version v2.x`
- [ ] Containerlab installed: `containerlab version` → `v0.xx.x`
- [ ] Python 3.11 installed: `python3.11 --version` → `Python 3.11.x`
- [ ] cEOS image loaded: `docker images | grep ceos` → `ceos   latest   ...`
- [ ] Repo cloned: `ls` shows `Makefile`, `clab/`, `nautobot/`, etc.

## Step 0 — Bootstrap (one time only)

```bash
make bootstrap
source .venv/bin/activate
```

Expected output ends with:
```
✓ Bootstrap complete — activate with: source .venv/bin/activate
```

## Step 1 — Start Nautobot

```bash
make nautobot-up
```

Wait for the stack to become healthy (~60 seconds):

```
[+] Running 6/6
 ✔ Container nautobot-postgres  Healthy
 ✔ Container nautobot-redis     Healthy
 ✔ Container nautobot           Healthy
 ✔ Container nautobot-worker    Healthy
 ✔ Container nautobot-beat      Started
✓ Nautobot reachable at http://localhost:8080 (admin/admin)
```

Open `http://localhost:8080` — log in with `admin` / `admin`.

## Step 2 — Seed the Source of Truth

```bash
make seed
```

Expected (truncated):
```
Connecting to Nautobot at http://localhost:8080

--- Location Types ---
  location_type [+] Region
  location_type [+] Site

--- Devices ---
  device [+] rtr1
  device [+] dist1
  device [+] acc1
  device [+] acc2

✓ SoT seed complete.
```

Verify in the UI: **Inventory → Devices** shows 4 devices under location HQ-TX-01.

## Step 3 — Render Intended Configurations

```bash
make render
```

Golden Config renders Jinja2 templates for all 4 devices. The intended configs
land in `golden_config/intended/HQ-TX-01/`:

```
golden_config/intended/HQ-TX-01/
├── rtr1.cfg
├── dist1.cfg
├── acc1.cfg
└── acc2.cfg
```

You can inspect any of them: `cat golden_config/intended/HQ-TX-01/acc1.cfg`

## Step 4 — Bring Up the Virtual Lab

```bash
make lab-up
```

Containerlab deploys the cEOS topology:

```
+---+-------------------+--------------+------------------------------+-------+
| # |       Name        | Container ID |            Image             | State |
+---+-------------------+--------------+------------------------------+-------+
| 1 | clab-hq-tx-01-rtr1 | abc123      | ceos:latest                  | running |
| 2 | clab-hq-tx-01-dist1| def456      | ceos:latest                  | running |
| 3 | clab-hq-tx-01-acc1 | ghi789      | ceos:latest                  | running |
| 4 | clab-hq-tx-01-acc2 | jkl012      | ceos:latest                  | running |
| 5 | clab-hq-tx-01-mgmt | mno345      | alpine:3.19                  | running |
| 6 | clab-hq-tx-01-ztp  | pqr678      | python:3.11-alpine           | running |
+---+-------------------+--------------+------------------------------+-------+
```

Test connectivity: `ping 192.0.2.10` (rtr1 management IP) should respond.

## Step 5 — Baseline Compliance Check (Expect 100% Pass)

```bash
make compliance
```

Expected output:
```
Step 1: Backing up running configurations...
  [+] rtr1  — backed up
  [+] dist1 — backed up
  [+] acc1  — backed up
  [+] acc2  — backed up

Step 2: Checking 6 compliance rules...

┌──────────────────────────────────────────────────────────────────────┐
│                    HQ-TX-01 Compliance Report                        │
├────────┬──────────┬────────┬──────────────────────────────────────── │
│ Device │ Rule     │ Status │ Missing Lines                           │
├────────┼──────────┼────────┼──────────────────────────────────────── │
│ acc1   │ snmpv3   │ PASS   │                                         │
│ acc1   │ ntp      │ PASS   │                                         │
│ acc1   │ logging  │ PASS   │                                         │
│ acc1   │ aaa      │ PASS   │                                         │
│ acc1   │ banner   │ PASS   │                                         │
│ acc1   │ mgmt_api │ PASS   │                                         │
│ ...    │ ...      │ ...    │ ...                                     │
└────────┴──────────┴────────┴──────────────────────────────────────── ┘
Results written to evidence/output/compliance_<timestamp>.json
✓ Compliance report complete
```

## Step 6 — Introduce Drift

```bash
make drift
```

This SSH's into acc1 and removes the SNMPv3 group and user config:
```
Removing SNMPv3 config from acc1...
✓ Drift introduced on acc1 — run 'make compliance' to detect
```

## Step 7 — Detect Drift

```bash
make compliance
```

Expected: acc1 now shows FAIL on the `snmpv3` rule with a diff:

```
│ acc1   │ snmpv3   │ FAIL   │ snmp-server group OW7SIX-GRP v3 priv  │
│        │          │        │ snmp-server user OW7SIX-USER ...       │
```

## Step 8 — Remediate

```bash
make remediate
```

Nornir pushes the intended config to acc1 via NAPALM `load_replace_candidate`:

```
Remediating 1 device(s): ['acc1']
Using full config replace (load_replace_candidate + commit)
[+] acc1 — Pushed 1842 chars
All devices remediated successfully.
✓ Remediation complete
```

Run `make compliance` again — acc1 returns to PASS.

## Step 9 — Generate Evidence Pack

```bash
make evidence
```

Output:
```
Evidence pack written to: evidence/output/evidence_pack_20240115_143022.md
```

Open the file — it contains:
- Device inventory table (4 devices, CM-8)
- Compliance results table with diffs (CM-2, CM-6)
- Operator attribution and timestamp (AU-2)
- NIST SP 800-171 Rev 2 control mapping table

## Sideloading cEOS

1. Create a free account at `https://www.arista.com/en/login`
2. Navigate to Software → cEOS-lab → download the latest `.tar.xz`
3. Import: `docker import cEOS64-lab-<version>.tar.xz ceos:latest`
4. Verify: `docker images | grep ceos`

## Tear Down

```bash
make lab-down      # destroy Containerlab topology
make nautobot-down # stop Nautobot stack (volumes preserved)
make clean         # remove venv, caches, generated output
```

## Troubleshooting

**`make nautobot-up` hangs or health check fails**
- Check Docker has enough memory: `docker system info | grep Memory` — needs ~4 GB.
- Check logs: `docker logs nautobot | tail -50`

**`make seed` gets a connection error**
- Nautobot isn't ready yet. Wait 30 more seconds and retry.
- The superuser token must be `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` — it's
  set in `nautobot/environment/creds.env.example`. If you changed it, set
  `NAUTOBOT_TOKEN` in your shell.

**`make lab-up` fails with "image not found"**
- cEOS hasn't been imported. Follow [Sideloading cEOS](#sideloading-ceos) above.

**NAPALM connection refused on compliance check**
- cEOS eAPI may still be starting. Wait 30 seconds after `make lab-up` and retry.
- Verify eAPI: `curl -s -u admin:admin http://192.0.2.10/command-api` should return JSON.
