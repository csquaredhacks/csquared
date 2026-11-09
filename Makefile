# Hallway: every command the team needs. Run `make` to list them.
# Deploy to the cluster in three commands:  make secrets && make deploy && make url

NS       ?= hallway
IMAGE    ?= ghcr.io/csquaredhacks/hallway
TAG      ?= latest
API      ?= http://localhost:8000
# Most clusters run amd64 nodes; without this an Apple Silicon laptop builds an arm64 image.
PLATFORM ?= linux/amd64

# Load .env (if it exists) and pass its keys to every command below.
-include .env
export

.DEFAULT_GOAL := help
.PHONY: help dash0 dev test lint types seed seed-before seed-live image image-ttl secrets deploy url logs matcher-now oom-demo oom-fix

help: ## List the targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'

# ---- Local development ----

dev: ## Run the API (:8000, auto-reload) and Vite (:5173) together; Ctrl-C stops both
	@trap 'kill 0' INT TERM EXIT; \
	uvicorn hallway.main:app --reload --reload-dir api --port 8000 & \
	(cd web && npm run dev -- --port 5173) & \
	wait

test: ## Run the API tests
	cd api && pytest -q

lint: ## Lint the Python code
	ruff check api seed

types: ## Regenerate web/src/api/schema.d.ts from the API models (CI fails if it is stale)
	python -c "import json; from hallway.main import app; print(json.dumps(app.openapi()))" > web/openapi.json
	cd web && npm run types

seed: ## Load 60 synthetic attendees, plans, meetings and check-ins (API=<url>)
	python seed/seed.py --api $(API) --checkins

seed-before: ## Act one, the week before: 60 attendees, invitations, plans and arrival groups. Nobody has met.
	python seed/seed.py --api $(API) --phase before

seed-live: ## Act two, the day itself: plans become meetings, plus check-ins (run seed-before first)
	python seed/seed.py --api $(API) --phase live --checkins

# ---- Image ----

image: ## Build and push IMAGE:TAG (needs `docker login ghcr.io` first)
	docker buildx build --platform $(PLATFORM) -t $(IMAGE):$(TAG) --push .

image-ttl: ## No-login fallback: push to ttl.sh (anonymous, image expires after 8h)
	@ref=ttl.sh/hallway-$$(od -An -N6 -tx1 /dev/urandom | tr -d ' \n'); \
	docker buildx build --platform $(PLATFORM) -t $$ref:8h --push . && \
	echo "Pushed $$ref:8h" && \
	echo "Deploy it with: make deploy IMAGE=$$ref TAG=8h"

# ---- Cluster ----

secrets: ## Create or update the Secret hallway-secrets from .env
	kubectl create namespace $(NS) 2>/dev/null || true  # "already exists" is fine
	kubectl -n $(NS) create secret generic hallway-secrets --from-env-file=.env --dry-run=client -o yaml | kubectl apply -f -

deploy: ## Install or upgrade the Helm release, then wait for the API to be ready
	helm upgrade --install hallway deploy/chart/hallway -n $(NS) --create-namespace \
		--set image.repository=$(IMAGE) --set image.tag=$(TAG)
	kubectl -n $(NS) rollout status deploy/hallway --timeout=180s

url: ## Print the public https URL (read from the tunnel pod's log)
	@kubectl -n $(NS) logs deploy/hallway-tunnel | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1

logs: ## Follow the API logs
	kubectl -n $(NS) logs deploy/hallway -f --tail=100

matcher-now: ## Run the matcher once, right now, instead of waiting for the schedule
	kubectl -n $(NS) create job hallway-matcher-now-$$(date +%s) --from=cronjob/hallway-matcher

# ---- Dash0 ----

dash0: ## Put the Hallway dashboard, check rules and SLO into Dash0 (needs DASH0_API_URL in .env)
	deploy/dash0/apply.sh

# ---- Planned incident for the Radar demo ----
# --reuse-values keeps whatever image the release is already running.
# The request is lowered too because Kubernetes rejects a request above the limit.

oom-demo: ## Break it on purpose: 48Mi memory limit, so the new API pod gets OOMKilled
	helm upgrade hallway deploy/chart/hallway -n $(NS) --reuse-values \
		--set resources.requests.memory=48Mi --set resources.limits.memory=48Mi

oom-fix: ## Undo oom-demo: back to the values.yaml defaults (128Mi request, 256Mi limit)
	helm upgrade hallway deploy/chart/hallway -n $(NS) --reuse-values \
		--set resources.requests.memory=128Mi --set resources.limits.memory=256Mi
	kubectl -n $(NS) rollout status deploy/hallway --timeout=180s
