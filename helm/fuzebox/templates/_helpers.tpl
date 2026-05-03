{{/* Common helpers. */}}

{{- define "fuzebox.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "fuzebox.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "fuzebox.databaseUrl" -}}
postgresql+asyncpg://fuzebox:{{ .Values.postgres.password }}@{{ .Release.Name }}-postgres:5432/fuzebox
{{- end -}}
