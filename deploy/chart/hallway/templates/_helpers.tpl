{{/*
Resource names are fixed ("hallway", "hallway-matcher", "hallway-tunnel") rather than derived
from the release name, so the Makefile and the tunnel's http://hallway:8000 can rely on them.
*/}}

{{/* Labels that identify this release. Used in selectors, so they must never change. */}}
{{- define "hallway.selectorLabels" -}}
app.kubernetes.io/name: hallway
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/* Labels for every object's metadata. Each object adds its own app.kubernetes.io/component. */}}
{{- define "hallway.labels" -}}
{{ include "hallway.selectorLabels" . }}
app.kubernetes.io/part-of: hallway
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{/*
Environment shared by the API Deployment and the matcher CronJob, defined once.
Each workload sets its own OTEL_SERVICE_NAME and then includes this.
Order matters: Kubernetes only expands $(VAR) for variables declared earlier in the list.
*/}}
{{- define "hallway.env" -}}
- name: ROOMS
  value: {{ .Values.rooms | quote }}
- name: CHAOS_ENABLED
  value: {{ .Values.chaosEnabled | quote }}
- name: COOKIE_SECURE
  value: "true"  # the public URL is always HTTPS (cloudflared tunnel)
- name: POD_NAME
  valueFrom:
    fieldRef:
      fieldPath: metadata.name
- name: POD_NAMESPACE
  valueFrom:
    fieldRef:
      fieldPath: metadata.namespace
# Telemetry goes straight from the app to Dash0 over OTLP (no collector to operate).
# optional: true, so the pod still starts if the Dash0 keys are not in the Secret yet.
- name: OTEL_EXPORTER_OTLP_ENDPOINT
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secretName }}
      key: DASH0_OTLP_ENDPOINT
      optional: true
- name: DASH0_AUTH_TOKEN  # must come before OTEL_EXPORTER_OTLP_HEADERS, which references it
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secretName }}
      key: DASH0_AUTH_TOKEN
      optional: true
- name: OTEL_EXPORTER_OTLP_HEADERS
  value: "Authorization=Bearer $(DASH0_AUTH_TOKEN)"
- name: OTEL_EXPORTER_OTLP_PROTOCOL
  value: {{ .Values.otel.protocol | quote }}
- name: OTEL_LOGS_EXPORTER  # traces and metrics default to otlp; logs must be asked for
  value: otlp
- name: OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED
  value: "true"
- name: OTEL_RESOURCE_ATTRIBUTES
  value: "k8s.namespace.name=$(POD_NAMESPACE),k8s.pod.name=$(POD_NAME),deployment.environment.name={{ .Values.otel.environment }}"
{{- end }}

{{/* Container hardening shared by all three workloads (passes the "restricted" Pod Security Standard). */}}
{{- define "hallway.containerSecurityContext" -}}
runAsNonRoot: true
allowPrivilegeEscalation: false
capabilities:
  drop: ["ALL"]
seccompProfile:
  type: RuntimeDefault
{{- end }}
