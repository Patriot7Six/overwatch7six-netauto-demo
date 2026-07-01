SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON := python3.11
VENV   := .venv
PIP    := $(VENV)/bin/pip
PY     := $(VENV)/bin/python

NAUTOBOT_DIR  := nautobot
CLAB_TOPO     := clab/hq-tx-01.clab.yml
EVIDENCE_DIR  := evidence/output
DATE          := $(shell date +%Y%m%d_%H%M%S)

.PHONY: help bootstrap nautobot-up nautobot-down seed render \
        lab-up lab-down compliance drift remediate evidence demo clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' | sort

bootstrap: ## Create venv and install all Python dependencies
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip wheel
	$(PIP) install -e ".[dev]"
	@echo "✓ Bootstrap complete — activate with: source $(VENV)/bin/activate"

nautobot-up: ## Start the Nautobot stack (Postgres, Redis, Celery, UI)
	@cp -n $(NAUTOBOT_DIR)/environment/creds.env.example $(NAUTOBOT_DIR)/environment/creds.env 2>/dev/null || true
	@cp -n $(NAUTOBOT_DIR)/environment/local.env.example $(NAUTOBOT_DIR)/environment/local.env 2>/dev/null || true
	@mkdir -p golden_config/intended
	@chmod -R 0777 golden_config/intended
	docker compose -f $(NAUTOBOT_DIR)/docker-compose.yml \
	               -f $(NAUTOBOT_DIR)/docker-compose.override.yml \
	               --env-file $(NAUTOBOT_DIR)/environment/local.env \
	               up -d
	@echo "Waiting for Nautobot (first-boot migrations can take 2-3 min)..."
	@until curl -sf http://localhost:8080/health/ > /dev/null 2>&1; do printf '.'; sleep 5; done
	@echo ""
	@echo "✓ Nautobot reachable at http://localhost:8080 (admin/admin)"

nautobot-down: ## Tear down the Nautobot stack (volumes kept)
	docker compose -f $(NAUTOBOT_DIR)/docker-compose.yml \
	               -f $(NAUTOBOT_DIR)/docker-compose.override.yml \
	               down
	@echo "✓ Nautobot stack stopped"

seed: ## Seed Nautobot with HQ-TX-01 site, devices, IPAM, VLANs
	$(PY) data/load_sot.py
	@echo "✓ SoT seeded"

render: ## Run the RenderGoldenConfig job via Nautobot API and wait for it to finish
	$(PY) golden_config/trigger_render.py
	@echo "✓ Golden Config render complete (see golden_config/intended/HQ-TX-01/)"

lab-up: ## Deploy Containerlab topology (requires cEOS image)
	sudo containerlab deploy --topo $(CLAB_TOPO) --reconfigure
	@echo "✓ Lab is up — use 'sudo containerlab inspect --topo $(CLAB_TOPO)' to view"

lab-down: ## Destroy Containerlab topology
	sudo containerlab destroy --topo $(CLAB_TOPO) --cleanup
	@echo "✓ Lab destroyed"

compliance: ## Run Nornir compliance report (backup + diff vs intended)
	$(PY) nornir/tasks/compliance_report.py
	@echo "✓ Compliance report complete — see evidence/output/"

drift: ## Intentionally remove SNMPv3 from acc1 to create a compliance drift
	@echo "Removing SNMPv3 config from acc1..."
	ssh -o StrictHostKeyChecking=no admin@192.0.2.13 \
	  "enable\nconfigure\nno snmp-server group OW7SIX-GRP v3 priv\nno snmp-server user OW7SIX-USER OW7SIX-GRP v3 auth sha OW7SIX-AUTH-PASS priv aes OW7SIX-PRIV-PASS\nexit"
	@echo "✓ Drift introduced on acc1 — run 'make compliance' to detect"

remediate: ## Push intended config to non-compliant devices
	$(PY) nornir/tasks/remediate.py
	@echo "✓ Remediation complete"

evidence: ## Generate dated Markdown evidence pack
	$(PY) -c "\
import subprocess, datetime, pathlib; \
date = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S'); \
out = pathlib.Path('evidence/output') / f'evidence_pack_{date}.md'; \
subprocess.run(['$(PY)', 'evidence/generate_evidence.py', '--output', str(out)], check=True); \
print(f'✓ Evidence written to {out}')"

demo: ## Run the full 5-minute demo end-to-end
	@echo "=== OVERWATCH7SIX NETAUTO DEMO ==="
	@echo "Step 1: Verify SoT..."
	$(MAKE) seed
	@echo "Step 2: Render intended configs..."
	$(MAKE) render
	@sleep 10
	@echo "Step 3: Baseline compliance check..."
	$(MAKE) compliance
	@echo "Step 4: Introduce drift..."
	$(MAKE) drift
	@echo "Step 5: Detect drift..."
	$(MAKE) compliance
	@echo "Step 6: Remediate..."
	$(MAKE) remediate
	@echo "Step 7: Confirm compliance restored..."
	$(MAKE) compliance
	@echo "Step 8: Generate evidence pack..."
	$(MAKE) evidence
	@echo "=== DEMO COMPLETE ==="

clean: ## Remove venv, caches, and generated output (keeps evidence .gitkeep)
	rm -rf $(VENV) .pytest_cache .ruff_cache __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find evidence/output -name "*.md" -delete 2>/dev/null || true
	find golden_config/intended -name "*.cfg" -delete 2>/dev/null || true
	@echo "✓ Clean"
