# CMMC 2.0 / NIST SP 800-171 Rev 2 Control Mapping

This document maps each relevant NIST SP 800-171 Rev 2 control to the specific
tool, job, or file in this repo that produces or enforces the evidence.

Control IDs are the verbatim NIST SP 800-171 Rev 2 requirement identifiers
(3.x.y format). CMMC 2.0 Level 2 aligns 1:1 with these requirements.

## CM — Configuration Management

| NIST 800-171 Rev 2 ID | CMMC Family | Requirement Text (abbreviated) | Evidence Source |
|---|---|---|---|
| 3.4.1 | CM-2 | Establish and maintain baseline configurations and inventories of organizational systems | `golden_config/intended/HQ-TX-01/*.cfg` — rendered by `make render` via Golden Config |
| 3.4.2 | CM-6 | Establish and enforce security configuration settings | `golden_config/compliance_rules.yaml` — rules enforced by `make compliance`; diffs written to `evidence/output/compliance_*.json` |
| 3.4.3 | CM-3 | Track, review, approve/disapprove, and log changes to systems | Nautobot change log (every SoT write is attributed to an authenticated user via the API token) |
| 3.4.6 | CM-7 | Employ the principle of least functionality | `mgmt_api` and `aaa` compliance rules in `golden_config/compliance_rules.yaml`; enforcement via `make remediate` |
| 3.4.7 | CM-7 | Prohibit or restrict use of functions, ports, protocols, and services | Same as 3.4.6 — `aaa` rule enforces local-only auth; `mgmt_api` rule ensures eAPI is intentional and documented |
| 3.4.8 | CM-8 | Maintain a current inventory of system components | Nautobot DCIM — `data/load_sot.py` seeds device inventory; `make evidence` exports it to the evidence pack |
| 3.4.9 | CM-10 | Control and monitor user-installed software | Out of scope for this network-layer demo (host OS controls) |

## AU — Audit and Accountability

| NIST 800-171 Rev 2 ID | CMMC Family | Requirement Text (abbreviated) | Evidence Source |
|---|---|---|---|
| 3.3.1 | AU-2 | Create and retain system audit logs | `logging` compliance rule in `golden_config/compliance_rules.yaml` enforces syslog to 192.0.2.2; operator identity captured in Nautobot job metadata and evidence pack |
| 3.3.2 | AU-3 | Ensure audit records contain required information | Evidence pack includes operator name, timestamp, device list, and diff output — see `evidence/templates/evidence_pack.md.j2` |
| 3.3.7 | AU-8 | Use internal system clocks for generating timestamps | `ntp` compliance rule enforces NTP server 192.0.2.1 on all devices |
| 3.3.8 | AU-9 | Protect audit information | Not directly evidenced here — evidence output is gitignored; only a human operator can run `make evidence` |

## IA — Identification and Authentication

| NIST 800-171 Rev 2 ID | CMMC Family | Requirement Text (abbreviated) | Evidence Source |
|---|---|---|---|
| 3.5.3 | IA-2 | Use multifactor authentication for local and network access | `aaa` compliance rule enforces `aaa authentication login default local` — all access requires credentials; SNMPv3 auth enforced by `snmpv3` rule |

## AC — Access Control

| NIST 800-171 Rev 2 ID | CMMC Family | Requirement Text (abbreviated) | Evidence Source |
|---|---|---|---|
| 3.1.9 | AC-8 | Notify users when accessing CUI systems | `banner` compliance rule enforces the MOTD banner on all devices |

## How to use this mapping in an audit

1. Run `make demo` — this produces timestamped evidence in `evidence/output/`.
2. Point auditors at `evidence/output/evidence_pack_<date>.md` for CM-8 inventory and AU-2 attribution.
3. Point auditors at `evidence/output/compliance_<date>.json` for CM-2 and CM-6 diff evidence.
4. The Nautobot job history (Admin → Jobs → Results) shows operator attribution for every config generation.
5. `golden_config/compliance_rules.yaml` is the policy document — it's version-controlled and change-tracked via git.
