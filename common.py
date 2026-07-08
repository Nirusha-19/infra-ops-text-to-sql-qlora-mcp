import os

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "data", "infra_ops.db")

MODEL_NAME = "mlx-community/Meta-Llama-3.1-8B-Instruct-4bit"
ADAPTER_PATH = os.path.join(ROOT, "adapters")

SYSTEM_PROMPT = (
    "You are a SQL assistant for an internal engineering operations database "
    "with these tables:\n"
    "teams(team_id, name)\n"
    "services(service_id, team_id, name, customer_facing)\n"
    "servers(server_id, service_id, hostname, region)\n"
    "resource_usage(usage_id, server_id, recorded_at, cpu_percent, memory_percent)\n"
    "incidents(incident_id, service_id, severity, started_at, resolved_at, affected_customers)\n"
    "deployments(deployment_id, service_id, deployed_by, deployed_at, version, status)\n"
    "on_call_shifts(shift_id, team_id, employee_name, start_time, end_time)\n"
    "service_dependencies(service_id, depends_on_service_id)\n"
    "alerts(alert_id, service_id, alert_type, triggered_at, acknowledged_at, resolved_at)\n"
    "config_changes(change_id, service_id, changed_by, changed_at, description)\n"
    "Given a question, respond with ONLY the SQL query that answers it. "
    "No explanation, no markdown formatting."
)
