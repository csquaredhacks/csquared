# One image for everything: the API, the built web app it serves, and the matcher CronJob.
# Build:  docker build -t hallway .        Run:  docker run --env-file .env -p 8000:8000 hallway

# ---- Stage 1: build the React app (Node is only needed here, not in the final image) ----
FROM node:22-alpine AS web
WORKDIR /web
# Copy the lockfile first so `npm ci` is cached until dependencies change.
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Build the Nuxt welcome experience as static files on the same origin as Hallway.
WORKDIR /welcome
COPY welcome/package.json welcome/package-lock.json ./
RUN npm ci
COPY welcome/ ./
RUN npm run build && mkdir -p /web/dist/welcome && cp -a .output/public/. /web/dist/welcome/

# ---- Stage 2: the runtime image ----
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    WEB_DIST=/app/web/dist
WORKDIR /app

# Install the `hallway` package, then let OpenTelemetry install the instrumentation
# libraries that match what is now installed (fastapi, elasticsearch, httpx, ...).
COPY api/ ./api/
RUN pip install ./api && opentelemetry-bootstrap -a install

COPY --from=web /web/dist ./web/dist

# Numeric UID (not a name) so Kubernetes `runAsNonRoot: true` can verify it.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin hallway
USER 10001

EXPOSE 8000
# The matcher CronJob overrides this with: opentelemetry-instrument python -m hallway.matcher
CMD ["opentelemetry-instrument", "uvicorn", "hallway.main:app", "--host", "0.0.0.0", "--port", "8000"]
