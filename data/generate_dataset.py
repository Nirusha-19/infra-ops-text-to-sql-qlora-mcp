"""
Generates train.jsonl, valid.jsonl, test.jsonl with three difficulty tiers:
  easy   -- single table or one simple join
  medium -- 3+ table joins, GROUP BY/HAVING
  hard   -- subqueries, self-referencing joins, date-window logic

Each generated example is tagged with its tier so eval scripts can report
accuracy per tier, not just one blended number.

"""
import json
import random
import os
import sqlite3
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from common import SYSTEM_PROMPT, DB_PATH

random.seed(11)
HERE = os.path.dirname(__file__)

TARGET_TOTAL = 2500
TIER_SHARE = {"easy": 0.40, "medium": 0.35, "hard": 0.25}

# ---------- entity lookups from the built database ----------

def get_entities():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    teams = [r[0] for r in cur.execute("SELECT name FROM teams")]
    services = [r[0] for r in cur.execute("SELECT name FROM services")]
    regions = [r[0] for r in cur.execute("SELECT DISTINCT region FROM servers")]
    severities = [r[0] for r in cur.execute("SELECT DISTINCT severity FROM incidents")]
    employees = [r[0] for r in cur.execute(
        "SELECT DISTINCT employee_name FROM on_call_shifts "
        "UNION SELECT DISTINCT deployed_by FROM deployments")]
    alert_types = [r[0] for r in cur.execute("SELECT DISTINCT alert_type FROM alerts")]
    conn.close()
    return {"team": teams, "service": services, "region": regions,
            "severity": severities, "employee": employees, "alert_type": alert_types}


THRESHOLDS_PCT = [50, 60, 70, 75, 80, 85, 90]
THRESHOLDS_INT = [1, 2, 3, 4, 5]
CUSTOMER_THRESHOLDS = [100, 500, 1000, 2000, 5000]

# ---------- template banks, each: (question, sql, param_keys) ----------

EASY = [
    ("How many services does the {team} team own?",
     "SELECT COUNT(*) FROM services s JOIN teams t ON s.team_id = t.team_id WHERE t.name = '{team}';",
     ["team"]),
    ("List all servers in the {region} region.",
     "SELECT hostname FROM servers WHERE region = '{region}';",
     ["region"]),
    ("How many servers does the {service} service have?",
     "SELECT COUNT(*) FROM servers sv JOIN services s ON sv.service_id = s.service_id WHERE s.name = '{service}';",
     ["service"]),
    ("How many incidents have {severity} severity?",
     "SELECT COUNT(*) FROM incidents WHERE severity = '{severity}';",
     ["severity"]),
    ("List all team names.",
     "SELECT name FROM teams;", []),
    ("How many customer-facing services are there?",
     "SELECT COUNT(*) FROM services WHERE customer_facing = 1;", []),
    ("What is the total number of servers in the company?",
     "SELECT COUNT(*) FROM servers;", []),
    ("How many deployments had status '{status}'?",
     "SELECT COUNT(*) FROM deployments WHERE status = '{status}';", ["status"]),
    ("List the names of services owned by the {team} team.",
     "SELECT s.name FROM services s JOIN teams t ON s.team_id = t.team_id WHERE t.name = '{team}';",
     ["team"]),
    ("How many alerts were of type '{alert_type}'?",
     "SELECT COUNT(*) FROM alerts WHERE alert_type = '{alert_type}';", ["alert_type"]),
    ("How many on-call shifts has {employee} worked?",
     "SELECT COUNT(*) FROM on_call_shifts WHERE employee_name = '{employee}';", ["employee"]),
    ("What is the highest number of affected customers in a single incident?",
     "SELECT MAX(affected_customers) FROM incidents;", []),
    ("How many config changes were made by {employee}?",
     "SELECT COUNT(*) FROM config_changes WHERE changed_by = '{employee}';", ["employee"]),
    ("List all distinct alert types.",
     "SELECT DISTINCT alert_type FROM alerts;", []),
    ("How many incidents are still unresolved?",
     "SELECT COUNT(*) FROM incidents WHERE resolved_at IS NULL;", []),
    ("How many {severity} severity incidents has the {team} team's services had?",
     "SELECT COUNT(*) FROM incidents i JOIN services s ON i.service_id = s.service_id "
     "JOIN teams t ON s.team_id = t.team_id WHERE i.severity = '{severity}' AND t.name = '{team}';",
     ["severity", "team"]),
    ("How many deployments with status '{status}' has the {service} service had?",
     "SELECT COUNT(*) FROM deployments d JOIN services s ON d.service_id = s.service_id "
     "WHERE d.status = '{status}' AND s.name = '{service}';", ["status", "service"]),
    ("How many servers in the {region} region run the {service} service?",
     "SELECT COUNT(*) FROM servers sv JOIN services s ON sv.service_id = s.service_id "
     "WHERE sv.region = '{region}' AND s.name = '{service}';", ["region", "service"]),
    ("How many alerts of type '{alert_type}' occurred on the {service} service?",
     "SELECT COUNT(*) FROM alerts a JOIN services s ON a.service_id = s.service_id "
     "WHERE a.alert_type = '{alert_type}' AND s.name = '{service}';", ["alert_type", "service"]),
    ("How many on-call shifts has {employee} worked for the {team} team?",
     "SELECT COUNT(*) FROM on_call_shifts o JOIN teams t ON o.team_id = t.team_id "
     "WHERE o.employee_name = '{employee}' AND t.name = '{team}';", ["employee", "team"]),
    ("How many config changes did {employee} make to the {service} service?",
     "SELECT COUNT(*) FROM config_changes c JOIN services s ON c.service_id = s.service_id "
     "WHERE c.changed_by = '{employee}' AND s.name = '{service}';", ["employee", "service"]),
    ("How many deployments has {employee} made to services owned by the {team} team?",
     "SELECT COUNT(*) FROM deployments d JOIN services s ON d.service_id = s.service_id "
     "JOIN teams t ON s.team_id = t.team_id WHERE d.deployed_by = '{employee}' AND t.name = '{team}';",
     ["employee", "team"]),
    ("How many incidents affected more than {cust} customers for the {service} service?",
     "SELECT COUNT(*) FROM incidents i JOIN services s ON i.service_id = s.service_id "
     "WHERE i.affected_customers > {cust} AND s.name = '{service}';", ["cust", "service"]),
]

MEDIUM = [
    ("What is the average CPU usage across all servers in the {region} region?",
     "SELECT AVG(r.cpu_percent) FROM resource_usage r JOIN servers sv ON r.server_id = sv.server_id "
     "WHERE sv.region = '{region}';", ["region"]),
    ("How many incidents has the {team} team's services had in total?",
     "SELECT COUNT(*) FROM incidents i JOIN services s ON i.service_id = s.service_id "
     "JOIN teams t ON s.team_id = t.team_id WHERE t.name = '{team}';", ["team"]),
    ("What is the average number of affected customers per incident for the {team} team?",
     "SELECT AVG(i.affected_customers) FROM incidents i JOIN services s ON i.service_id = s.service_id "
     "JOIN teams t ON s.team_id = t.team_id WHERE t.name = '{team}';", ["team"]),
    ("How many deployments has the {service} service received?",
     "SELECT COUNT(*) FROM deployments d JOIN services s ON d.service_id = s.service_id "
     "WHERE s.name = '{service}';", ["service"]),
    ("Which teams have more than {n} services?",
     "SELECT t.name FROM services s JOIN teams t ON s.team_id = t.team_id "
     "GROUP BY t.name HAVING COUNT(*) > {n};", ["n"]),
    ("How many failed deployments has the {team} team had?",
     "SELECT COUNT(*) FROM deployments d JOIN services s ON d.service_id = s.service_id "
     "JOIN teams t ON s.team_id = t.team_id WHERE t.name = '{team}' AND d.status = 'failed';", ["team"]),
    ("What is the average memory usage for servers running the {service} service?",
     "SELECT AVG(r.memory_percent) FROM resource_usage r JOIN servers sv ON r.server_id = sv.server_id "
     "JOIN services s ON sv.service_id = s.service_id WHERE s.name = '{service}';", ["service"]),
    ("How many on-call shifts has the {team} team scheduled?",
     "SELECT COUNT(*) FROM on_call_shifts o JOIN teams t ON o.team_id = t.team_id "
     "WHERE t.name = '{team}';", ["team"]),
    ("Which services had more than {n} incidents?",
     "SELECT s.name FROM incidents i JOIN services s ON i.service_id = s.service_id "
     "GROUP BY s.name HAVING COUNT(*) > {n};", ["n"]),
    ("How many alerts of type '{alert_type}' occurred on services owned by the {team} team?",
     "SELECT COUNT(*) FROM alerts a JOIN services s ON a.service_id = s.service_id "
     "JOIN teams t ON s.team_id = t.team_id WHERE a.alert_type = '{alert_type}' AND t.name = '{team}';",
     ["alert_type", "team"]),
    ("What is the total number of affected customers across all {severity} severity incidents?",
     "SELECT SUM(affected_customers) FROM incidents WHERE severity = '{severity}';", ["severity"]),
    ("How many config changes were made to services owned by the {team} team?",
     "SELECT COUNT(*) FROM config_changes c JOIN services s ON c.service_id = s.service_id "
     "JOIN teams t ON s.team_id = t.team_id WHERE t.name = '{team}';", ["team"]),
    ("Which regions have more than {n} servers?",
     "SELECT region FROM servers GROUP BY region HAVING COUNT(*) > {n};", ["n"]),
    ("How many services does the {team} team have that are customer-facing?",
     "SELECT COUNT(*) FROM services s JOIN teams t ON s.team_id = t.team_id "
     "WHERE t.name = '{team}' AND s.customer_facing = 1;", ["team"]),
    ("What is the average time in hours between an incident starting and being resolved for the {service} service?",
     "SELECT AVG((julianday(i.resolved_at) - julianday(i.started_at)) * 24) FROM incidents i "
     "JOIN services s ON i.service_id = s.service_id WHERE s.name = '{service}' "
     "AND i.resolved_at IS NOT NULL;", ["service"]),
    ("Which employees have made more than {n} config changes?",
     "SELECT changed_by FROM config_changes GROUP BY changed_by HAVING COUNT(*) > {n};", ["n"]),
    ("How many servers does each service in the {region} region have on average?",
     "SELECT AVG(cnt) FROM (SELECT service_id, COUNT(*) AS cnt FROM servers "
     "WHERE region = '{region}' GROUP BY service_id);", ["region"]),
    ("List services with an average CPU usage above {pct} percent.",
     "SELECT s.name FROM resource_usage r JOIN servers sv ON r.server_id = sv.server_id "
     "JOIN services s ON sv.service_id = s.service_id GROUP BY s.name "
     "HAVING AVG(r.cpu_percent) > {pct};", ["pct"]),
    ("How many critical incidents affected more than {cust} customers?",
     "SELECT COUNT(*) FROM incidents WHERE severity = 'critical' AND affected_customers > {cust};",
     ["cust"]),
    ("Which services depend on the {service} service?",
     "SELECT s.name FROM service_dependencies sd JOIN services s ON sd.service_id = s.service_id "
     "JOIN services dep ON sd.depends_on_service_id = dep.service_id WHERE dep.name = '{service}';",
     ["service"]),
    ("How many {severity} severity incidents affected more than {cust} customers?",
     "SELECT COUNT(*) FROM incidents WHERE severity = '{severity}' AND affected_customers > {cust};",
     ["severity", "cust"]),
    ("What is the average CPU usage for servers running the {service} service in the {region} region?",
     "SELECT AVG(r.cpu_percent) FROM resource_usage r JOIN servers sv ON r.server_id = sv.server_id "
     "JOIN services s ON sv.service_id = s.service_id WHERE s.name = '{service}' AND sv.region = '{region}';",
     ["service", "region"]),
    ("How many deployments by {employee} to the {service} service failed?",
     "SELECT COUNT(*) FROM deployments d JOIN services s ON d.service_id = s.service_id "
     "WHERE d.deployed_by = '{employee}' AND s.name = '{service}' AND d.status = 'failed';",
     ["employee", "service"]),
    ("Which teams have more than {n} services with severity '{severity}' incidents?",
     "SELECT t.name FROM teams t JOIN services s ON s.team_id = t.team_id "
     "JOIN incidents i ON i.service_id = s.service_id WHERE i.severity = '{severity}' "
     "GROUP BY t.name HAVING COUNT(DISTINCT s.service_id) > {n};", ["n", "severity"]),
    ("What is the average number of affected customers for '{severity}' incidents on the {service} service?",
     "SELECT AVG(affected_customers) FROM incidents i JOIN services s ON i.service_id = s.service_id "
     "WHERE i.severity = '{severity}' AND s.name = '{service}';", ["severity", "service"]),
]

HARD = [
    ("Which services had an incident start within 24 hours after a deployment to a service they depend on?",
     "SELECT DISTINCT s.name FROM services s "
     "JOIN service_dependencies sd ON s.service_id = sd.service_id "
     "JOIN deployments d ON sd.depends_on_service_id = d.service_id "
     "JOIN incidents i ON i.service_id = s.service_id "
     "WHERE i.started_at BETWEEN d.deployed_at AND datetime(d.deployed_at, '+1 day');", []),
    ("Which teams have more than {n} unresolved incidents across their services?",
     "SELECT t.name FROM incidents i JOIN services s ON i.service_id = s.service_id "
     "JOIN teams t ON s.team_id = t.team_id WHERE i.resolved_at IS NULL "
     "GROUP BY t.name HAVING COUNT(*) > {n};", ["n"]),
    ("What is the average time in minutes between an alert being triggered and acknowledged, "
     "for services owned by the {team} team?",
     "SELECT AVG((julianday(a.acknowledged_at) - julianday(a.triggered_at)) * 24 * 60) "
     "FROM alerts a JOIN services s ON a.service_id = s.service_id "
     "JOIN teams t ON s.team_id = t.team_id WHERE t.name = '{team}' AND a.acknowledged_at IS NOT NULL;",
     ["team"]),
    ("List servers whose average CPU usage exceeded {pct} percent.",
     "SELECT hostname FROM servers sv JOIN resource_usage r ON sv.server_id = r.server_id "
     "GROUP BY sv.server_id HAVING AVG(r.cpu_percent) > {pct};", ["pct"]),
    ("How many incidents occurred within 6 hours of a config change to the same service?",
     "SELECT COUNT(*) FROM incidents i JOIN config_changes c ON i.service_id = c.service_id "
     "WHERE i.started_at BETWEEN c.changed_at AND datetime(c.changed_at, '+6 hours');", []),
    ("Which employees are on-call for teams with more than {n} unresolved incidents?",
     "SELECT DISTINCT o.employee_name FROM on_call_shifts o JOIN teams t ON o.team_id = t.team_id "
     "WHERE t.team_id IN (SELECT s.team_id FROM incidents i JOIN services s ON i.service_id = s.service_id "
     "WHERE i.resolved_at IS NULL GROUP BY s.team_id HAVING COUNT(*) > {n});", ["n"]),
    ("Which services had a failed deployment followed by a {severity} severity incident within 24 hours?",
     "SELECT DISTINCT s.name FROM services s JOIN deployments d ON s.service_id = d.service_id "
     "JOIN incidents i ON i.service_id = s.service_id WHERE d.status = 'failed' "
     "AND i.severity = '{severity}' AND i.started_at BETWEEN d.deployed_at AND datetime(d.deployed_at, '+1 day');",
     ["severity"]),
    ("Which services have more incidents than the company-wide average number of incidents per service?",
     "SELECT s.name FROM services s LEFT JOIN incidents i ON s.service_id = i.service_id "
     "GROUP BY s.name HAVING COUNT(i.incident_id) > "
     "(SELECT AVG(cnt) FROM (SELECT COUNT(*) AS cnt FROM incidents GROUP BY service_id));", []),
    ("List teams whose services have never had a critical incident.",
     "SELECT DISTINCT t.name FROM teams t JOIN services s ON s.team_id = t.team_id "
     "WHERE s.service_id NOT IN (SELECT service_id FROM incidents WHERE severity = 'critical');", []),
    ("Which services depend on a service that itself had more than {n} incidents?",
     "SELECT DISTINCT s.name FROM services s JOIN service_dependencies sd ON s.service_id = sd.service_id "
     "WHERE sd.depends_on_service_id IN "
     "(SELECT service_id FROM incidents GROUP BY service_id HAVING COUNT(*) > {n});", ["n"]),
    ("Does the {team} team have more than {n} unresolved incidents right now?",
     "SELECT CASE WHEN COUNT(*) > {n} THEN 'yes' ELSE 'no' END FROM incidents i "
     "JOIN services s ON i.service_id = s.service_id JOIN teams t ON s.team_id = t.team_id "
     "WHERE t.name = '{team}' AND i.resolved_at IS NULL;", ["team", "n"]),
    ("List servers running the {service} service whose average CPU usage exceeded {pct} percent.",
     "SELECT hostname FROM servers sv JOIN resource_usage r ON sv.server_id = r.server_id "
     "JOIN services s ON sv.service_id = s.service_id WHERE s.name = '{service}' "
     "GROUP BY sv.server_id HAVING AVG(r.cpu_percent) > {pct};", ["service", "pct"]),
    ("Which services owned by the {team} team had a '{severity}' severity incident within 24 hours "
     "of a deployment to a service they depend on?",
     "SELECT DISTINCT s.name FROM services s JOIN teams t ON s.team_id = t.team_id "
     "JOIN service_dependencies sd ON s.service_id = sd.service_id "
     "JOIN deployments d ON sd.depends_on_service_id = d.service_id "
     "JOIN incidents i ON i.service_id = s.service_id "
     "WHERE t.name = '{team}' AND i.severity = '{severity}' "
     "AND i.started_at BETWEEN d.deployed_at AND datetime(d.deployed_at, '+1 day');",
     ["team", "severity"]),
    ("Is {employee} on-call for a team that currently has more than {n} unresolved incidents?",
     "SELECT CASE WHEN COUNT(*) > 0 THEN 'yes' ELSE 'no' END FROM on_call_shifts o "
     "JOIN teams t ON o.team_id = t.team_id WHERE o.employee_name = '{employee}' "
     "AND t.team_id IN (SELECT s.team_id FROM incidents i JOIN services s ON i.service_id = s.service_id "
     "WHERE i.resolved_at IS NULL GROUP BY s.team_id HAVING COUNT(*) > {n});", ["employee", "n"]),
    ("List servers in the {region} region whose average CPU usage exceeded {pct} percent.",
     "SELECT hostname FROM servers sv JOIN resource_usage r ON sv.server_id = r.server_id "
     "WHERE sv.region = '{region}' GROUP BY sv.server_id HAVING AVG(r.cpu_percent) > {pct};",
     ["region", "pct"]),
]

TEMPLATES = {"easy": EASY, "medium": MEDIUM, "hard": HARD}


def fill(template, entities):
    q, sql, keys = template
    params = {}
    for k in keys:
        if k == "team":
            params["team"] = random.choice(entities["team"])
        elif k == "service":
            params["service"] = random.choice(entities["service"])
        elif k == "region":
            params["region"] = random.choice(entities["region"])
        elif k == "severity":
            params["severity"] = random.choice(entities["severity"])
        elif k == "employee":
            params["employee"] = random.choice(entities["employee"])
        elif k == "alert_type":
            params["alert_type"] = random.choice(entities["alert_type"])
        elif k == "n":
            params["n"] = random.choice(THRESHOLDS_INT)
        elif k == "pct":
            params["pct"] = random.choice(THRESHOLDS_PCT)
        elif k == "cust":
            params["cust"] = random.choice(CUSTOMER_THRESHOLDS)
        elif k == "status":
            params["status"] = random.choice(["success", "failed", "rolled_back"])
    return q.format(**params), sql.format(**params)


def to_chat_example(question, sql):
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
            {"role": "assistant", "content": sql},
        ]
    }


def generate_tier(tier_name, count, entities):
    templates = TEMPLATES[tier_name]
    examples, seen = [], set()
    attempts = 0
    max_attempts = count * 40
    while len(examples) < count and attempts < max_attempts:
        attempts += 1
        template = random.choice(templates)
        q, sql = fill(template, entities)
        key = (q, sql)
        if key in seen:
            continue
        seen.add(key)
        examples.append({"question": q, "sql": sql, "tier": tier_name})
    return examples


def main():
    entities = get_entities()
    all_examples = []
    for tier, share in TIER_SHARE.items():
        target = int(TARGET_TOTAL * share)
        tier_examples = generate_tier(tier, target, entities)
        print(f"  {tier}: generated {len(tier_examples)} / target {target}")
        all_examples.extend(tier_examples)

    random.shuffle(all_examples)
    n = len(all_examples)
    n_train = int(n * 0.75)
    n_valid = int(n * 0.10)
    train = all_examples[:n_train]
    valid = all_examples[n_train:n_train + n_valid]
    test = all_examples[n_train + n_valid:]

    with open(os.path.join(HERE, "train.jsonl"), "w") as f:
        for ex in train:
            f.write(json.dumps(to_chat_example(ex["question"], ex["sql"])) + "\n")

    with open(os.path.join(HERE, "valid.jsonl"), "w") as f:
        for ex in valid:
            f.write(json.dumps(to_chat_example(ex["question"], ex["sql"])) + "\n")

    # mlx_lm.lora's loader expects a chat-format test.jsonl alongside train/valid
    with open(os.path.join(HERE, "test.jsonl"), "w") as f:
        for ex in test:
            f.write(json.dumps(to_chat_example(ex["question"], ex["sql"])) + "\n")

    # our own eval scripts need question/sql/tier fields -- kept under a different filename so it never collides with mlx_lm's expectations
    with open(os.path.join(HERE, "held_out_eval.jsonl"), "w") as f:
        for ex in test:
            f.write(json.dumps(ex) + "\n")

    print(f"\nTotal: {len(train)} train / {len(valid)} valid / {len(test)} test")
    for tier in ["easy", "medium", "hard"]:
        c = sum(1 for ex in test if ex["tier"] == tier)
        print(f"  test set -- {tier}: {c}")


if __name__ == "__main__":
    main()
