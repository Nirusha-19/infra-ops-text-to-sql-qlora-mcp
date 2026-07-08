"""
Builds infra_ops.db: a 10-table synthetic engineering-operations database
(teams, services, servers, resource usage, incidents, deployments,
on-call shifts, service dependencies, alerts, config changes).

Run this once, before generate_dataset.py.
"""
import sqlite3
import random
import os
from datetime import datetime, timedelta

random.seed(42)
DB_PATH = os.path.join(os.path.dirname(__file__), "infra_ops.db")

TEAM_NAMES = ["Compute Platform", "Search", "API Gateway", "Identity", "Notifications",
              "Billing", "Recommendations", "Platform", "Data Pipeline",
              "Device Provisioning", "Fleet Management", "Security", "Observability", "Storage", "Networking",
              "Anomaly Detection", "Messaging", "Analytics", "Workflow Orchestration", "Configuration Management",
              "Resource Provisioning", "Customer Support", "Localization", "Partner Integrations"]

SERVICE_WORDS = ["api", "worker", "gateway", "indexer", "cache", "scheduler",
                 "processor", "router", "database", "queue"]

REGIONS = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
SEVERITIES = ["low", "medium", "high", "critical"]
DEPLOY_STATUSES = ["success", "failed", "rolled_back"]
ALERT_TYPES = ["high_cpu", "high_latency", "error_rate_spike", "disk_full", "memory_pressure"]

FIRST_NAMES = ["James", "Maria", "Wei", "Aisha", "Carlos", "Priya", "David", "Sofia",
               "Liam", "Noor", "Ethan", "Yuki", "Omar", "Elena", "Ravi", "Grace",
               "Marcus", "Lina", "Tomas", "Zara"]
LAST_NAMES = ["Smith", "Garcia", "Chen", "Khan", "Rossi", "Patel", "Johnson", "Kim",
              "Novak", "Ali", "Brown", "Tanaka", "Hassan", "Silva", "Nguyen", "Clark"]

EMPLOYEES = list({f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}" for _ in range(40)})

START_DATE = datetime(2025, 1, 1)


def rand_dt(days_range=180):
    return START_DATE + timedelta(days=random.randint(0, days_range),
                                   hours=random.randint(0, 23),
                                   minutes=random.randint(0, 59))


def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def build():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE teams (
            team_id INTEGER PRIMARY KEY, name TEXT NOT NULL
        );
        CREATE TABLE services (
            service_id INTEGER PRIMARY KEY, team_id INTEGER NOT NULL,
            name TEXT NOT NULL, customer_facing INTEGER NOT NULL,
            FOREIGN KEY (team_id) REFERENCES teams(team_id)
        );
        CREATE TABLE servers (
            server_id INTEGER PRIMARY KEY, service_id INTEGER NOT NULL,
            hostname TEXT NOT NULL, region TEXT NOT NULL,
            FOREIGN KEY (service_id) REFERENCES services(service_id)
        );
        CREATE TABLE resource_usage (
            usage_id INTEGER PRIMARY KEY, server_id INTEGER NOT NULL,
            recorded_at TEXT NOT NULL, cpu_percent INTEGER NOT NULL,
            memory_percent INTEGER NOT NULL,
            FOREIGN KEY (server_id) REFERENCES servers(server_id)
        );
        CREATE TABLE incidents (
            incident_id INTEGER PRIMARY KEY, service_id INTEGER NOT NULL,
            severity TEXT NOT NULL, started_at TEXT NOT NULL, resolved_at TEXT,
            affected_customers INTEGER NOT NULL,
            FOREIGN KEY (service_id) REFERENCES services(service_id)
        );
        CREATE TABLE deployments (
            deployment_id INTEGER PRIMARY KEY, service_id INTEGER NOT NULL,
            deployed_by TEXT NOT NULL, deployed_at TEXT NOT NULL,
            version TEXT NOT NULL, status TEXT NOT NULL,
            FOREIGN KEY (service_id) REFERENCES services(service_id)
        );
        CREATE TABLE on_call_shifts (
            shift_id INTEGER PRIMARY KEY, team_id INTEGER NOT NULL,
            employee_name TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL,
            FOREIGN KEY (team_id) REFERENCES teams(team_id)
        );
        CREATE TABLE service_dependencies (
            service_id INTEGER NOT NULL, depends_on_service_id INTEGER NOT NULL,
            FOREIGN KEY (service_id) REFERENCES services(service_id),
            FOREIGN KEY (depends_on_service_id) REFERENCES services(service_id)
        );
        CREATE TABLE alerts (
            alert_id INTEGER PRIMARY KEY, service_id INTEGER NOT NULL,
            alert_type TEXT NOT NULL, triggered_at TEXT NOT NULL,
            acknowledged_at TEXT, resolved_at TEXT,
            FOREIGN KEY (service_id) REFERENCES services(service_id)
        );
        CREATE TABLE config_changes (
            change_id INTEGER PRIMARY KEY, service_id INTEGER NOT NULL,
            changed_by TEXT NOT NULL, changed_at TEXT NOT NULL, description TEXT NOT NULL,
            FOREIGN KEY (service_id) REFERENCES services(service_id)
        );
    """)

    # teams
    for i, name in enumerate(TEAM_NAMES, start=1):
        cur.execute("INSERT INTO teams VALUES (?, ?)", (i, name))

    # services (3 per team)
    service_id = 1
    services = []
    for team_id in range(1, len(TEAM_NAMES) + 1):
        for _ in range(4):
            name = f"{TEAM_NAMES[team_id-1].lower().replace(' ', '-')}-{random.choice(SERVICE_WORDS)}"
            customer_facing = random.choice([0, 1])
            cur.execute("INSERT INTO services VALUES (?, ?, ?, ?)",
                        (service_id, team_id, name, customer_facing))
            services.append(service_id)
            service_id += 1

    # servers (4 per service)
    server_id = 1
    servers_by_service = {}
    for sid in services:
        servers_by_service[sid] = []
        for _ in range(4):
            hostname = f"host-{sid}-{server_id}"
            region = random.choice(REGIONS)
            cur.execute("INSERT INTO servers VALUES (?, ?, ?, ?)",
                        (server_id, sid, hostname, region))
            servers_by_service[sid].append(server_id)
            server_id += 1

    # resource usage (10 readings per server)
    usage_id = 1
    for sid, srv_list in servers_by_service.items():
        for srv in srv_list:
            for _ in range(10):
                dt = fmt(rand_dt())
                cpu = random.randint(10, 98)
                mem = random.randint(15, 95)
                cur.execute("INSERT INTO resource_usage VALUES (?, ?, ?, ?, ?)",
                            (usage_id, srv, dt, cpu, mem))
                usage_id += 1

    # incidents (~300)
    incident_id = 1
    for _ in range(300):
        sid = random.choice(services)
        severity = random.choice(SEVERITIES)
        start = rand_dt()
        resolved = None if random.random() < 0.15 else fmt(start + timedelta(hours=random.randint(1, 48)))
        affected = random.randint(0, 8000)
        cur.execute("INSERT INTO incidents VALUES (?, ?, ?, ?, ?, ?)",
                    (incident_id, sid, severity, fmt(start), resolved, affected))
        incident_id += 1

    # deployments (~400)
    deployment_id = 1
    for _ in range(400):
        sid = random.choice(services)
        deployer = random.choice(EMPLOYEES)
        dt = fmt(rand_dt())
        version = f"v{random.randint(1,9)}.{random.randint(0,20)}.{random.randint(0,9)}"
        status = random.choices(DEPLOY_STATUSES, weights=[0.85, 0.1, 0.05])[0]
        cur.execute("INSERT INTO deployments VALUES (?, ?, ?, ?, ?, ?)",
                    (deployment_id, sid, deployer, dt, version, status))
        deployment_id += 1

    # on-call shifts (~100)
    shift_id = 1
    for _ in range(100):
        team_id = random.randint(1, len(TEAM_NAMES))
        emp = random.choice(EMPLOYEES)
        start = rand_dt()
        end = start + timedelta(hours=random.choice([8, 12, 24]))
        cur.execute("INSERT INTO on_call_shifts VALUES (?, ?, ?, ?, ?)",
                    (shift_id, team_id, emp, fmt(start), fmt(end)))
        shift_id += 1

    # service dependencies (~60, avoid self-loops)
    dep_pairs = set()
    while len(dep_pairs) < 60:
        a, b = random.choice(services), random.choice(services)
        if a != b:
            dep_pairs.add((a, b))
    for a, b in dep_pairs:
        cur.execute("INSERT INTO service_dependencies VALUES (?, ?)", (a, b))

    # alerts (~250)
    alert_id = 1
    for _ in range(250):
        sid = random.choice(services)
        atype = random.choice(ALERT_TYPES)
        trig = rand_dt()
        ack = None if random.random() < 0.2 else fmt(trig + timedelta(minutes=random.randint(1, 120)))
        resolved = None if random.random() < 0.3 else fmt(trig + timedelta(minutes=random.randint(10, 300)))
        cur.execute("INSERT INTO alerts VALUES (?, ?, ?, ?, ?, ?)",
                    (alert_id, sid, atype, fmt(trig), ack, resolved))
        alert_id += 1

    # config changes (~200)
    change_id = 1
    descs = ["increased memory limit", "updated timeout threshold", "rotated API keys",
             "changed autoscaling policy", "updated feature flag", "modified rate limit",
             "patched dependency version", "adjusted retry policy"]
    for _ in range(200):
        sid = random.choice(services)
        changer = random.choice(EMPLOYEES)
        dt = fmt(rand_dt())
        desc = random.choice(descs)
        cur.execute("INSERT INTO config_changes VALUES (?, ?, ?, ?, ?)",
                    (change_id, sid, changer, dt, desc))
        change_id += 1

    conn.commit()
    conn.close()
    print(f"Built {DB_PATH}")
    print(f"  {len(TEAM_NAMES)} teams, {len(services)} services, {server_id-1} servers")
    print(f"  {usage_id-1} usage records, {incident_id-1} incidents, {deployment_id-1} deployments")
    print(f"  {shift_id-1} on-call shifts, {len(dep_pairs)} dependencies, {alert_id-1} alerts, {change_id-1} config changes")


if __name__ == "__main__":
    build()
