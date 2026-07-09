# Infra Ops Text to SQL: QLoRA Fine Tuning with MCP Serving

Python · MLX · License

## 🎯 What Is This?

This project fine-tunes Llama-3.1-8B-Instruct using QLoRA to translate plain-English questions about a company's infrastructure into working SQL queries, execute them, and return the real answer. No engineer has to write the query by hand.

In large engineering organizations, infrastructure data is scattered across many related tables: teams, services, servers, incidents, deployments, alerts, on-call schedules. Answering even a simple operational question means writing a multi-table SQL join.

- Teams own services, and services run on servers spread across multiple regions.
- Incidents, alerts, and config changes are all tied to a specific service, with timestamps that matter (when something broke, when it was acknowledged, when it was resolved).
- On-call shifts and service dependencies add further relationships that make some questions, like "which service caused a cascading failure," genuinely hard to query without SQL expertise.

Most people who need to answer a question like this don't know how to write the SQL required to get it. This project closes that gap by fine-tuning a model specifically for this task, then serving it as a tool an AI agent can call directly.

## 🔍 What It Does?

- Converts a plain-English question into SQL, correctly joining across multiple related tables where needed
- Executes that SQL against a real database and returns the real answer, not just the query text
- Fine-tunes Llama-3.1-8B-Instruct with QLoRA (4-bit quantization plus LoRA adapters), training only 5.24M of the model's 8.03B parameters (0.065%) via MLX
- Evaluates with execution accuracy across three difficulty tiers (easy, medium, hard), comparing actual query results against the correct results, not text similarity
- Serves the fine-tuned model as an MCP server, so any MCP-compatible AI client (Claude Desktop, Cline, MCP Inspector) can call it directly in conversation

## 📊 Model Performance

The model was evaluated on a 375-question held-out test set, before and after QLoRA fine-tuning. Correctness is measured by execution accuracy. For each test question, both the model's generated SQL and the correct SQL are run against the database, and their results are compared. If the two results match, the answer counts as correct, even if the two queries are worded completely differently.

| Tier | Baseline (few-shot) | Fine-tuned (QLoRA) | Delta |
|---|---|---|---|
| Easy | 94.48% | 100.00% | +5.52 pts |
| Medium | 74.62% | 99.23% | +24.61 pts |
| Hard | 20.00% | 97.00% | +77.00 pts |
| **Overall** | **67.73%** | **98.93%** | **+31.20 pts** |

The largest gains are on hard-tier queries: subqueries, self-referencing joins, and date-window logic, where the base model largely failed and the fine-tuned model succeeds almost every time.

## 🖥️ How It Works?

**Database Build:** This project defines a 10-table engineering-operations schema, populated by a script with 24 teams, 96 services, and 384 servers spread across 4 regions, along with incidents, deployments, alerts, on-call shifts, service dependencies, resource usage records, and configuration changes. All data is realistic, randomized, and reproducible.

**Dataset Generation:** 63 hand-written SQL query templates, spanning 23 easy, 25 medium, and 15 hard patterns, are filled in by a script using real entity values pulled directly from the database, producing 2,500 unique question and SQL pairs. Every single one is verified to execute correctly before training begins. The result is split into 1,875 for training, 250 for validation, and 375 held out for testing.

**Baseline Evaluation:** The unmodified base model is tested on all 375 held-out questions using few-shot prompting, establishing the "before" results.

**QLoRA Fine Tuning:** The base model is frozen and quantized to 4-bit, and LoRA adapters are inserted into the last 8 of its 32 transformer layers, then trained for 600 iterations on the training examples via MLX.

**Fine-Tuned Evaluation:** The trained model is tested zero-shot on the same 375 held-out questions, and the results are compared tier by tier against the baseline.

**MCP Serving:** The fine-tuned model is wrapped as an MCP server exposing two tools, one that converts a question into SQL and returns the real answer, and one that returns the database schema, so it can be called live by any MCP-compatible AI client.

## 🛠️ Tech Stack

| Layer | Tools |
|---|---|
| ML Framework | MLX · mlx-lm |
| Base Model | Llama-3.1-8B-Instruct (Meta), 4-bit via mlx-community |
| Fine-Tuning | QLoRA (4-bit quantization plus LoRA adapters) |
| Database | SQLite |
| Serving | MCP (Model Context Protocol) Python SDK, FastMCP |
| Testing Client | MCP Inspector |
| Language | Python 3.11 |

## 📁 Project Structure

```
infra-ops-text-to-sql-qlora-mcp/
├── README.md                    ← project documentation
├── requirements.txt              ← Python dependencies (mlx, mlx-lm, mcp)
├── train.sh                      ← runs QLoRA fine-tuning via MLX
├── common.py                     ← shared constants (model name, paths, schema prompt)
├── data/
│   ├── build_db.py               ← builds the engineering-operations database
│   └── generate_dataset.py       ← generates the tiered training and evaluation data
├── scripts/
│   ├── eval_utils.py              ← executes SQL and compares results for execution accuracy
│   ├── baseline_eval.py           ← evaluates the base model with few-shot prompting
│   ├── baseline_results.json      ← saved baseline accuracy results
│   ├── finetuned_eval.py          ← evaluates the fine-tuned model, zero-shot
│   ├── finetuned_results.json     ← saved fine-tuned accuracy results
│   └── compare_results.py         ← prints the before and after comparison table
└── mcp_server/
    └── server.py                  ← exposes the fine-tuned model as MCP tools
```

Running `data/build_db.py` and `data/generate_dataset.py` produces the database and dataset files locally. Running `train.sh` produces the trained adapter weights in `adapters/`. These generated files are not committed to the repository, since the project is fully reproducible from the source above.

## 💡 What Makes This Different?

**Execution accuracy, not text matching:** correctness is measured by running the generated SQL and comparing actual results, not by comparing SQL text to a reference query. This avoids penalizing a differently worded but equally correct query, and avoids rewarding a similar-looking query that is actually wrong.

**QLoRA fine-tuning trains the model directly on the target schema and query patterns.** Measured on this project's own held-out test set, this improved hard-tier query accuracy from 20% (prompting alone) to 97%.

**Serving via MCP makes it callable live** by any MCP-compatible AI agent, not just runnable from a script. Tested with MCP Inspector.

**Tiered evaluation (easy, medium, hard)** shows exactly where fine-tuning helped most, instead of hiding the picture behind one blended accuracy number.

## 🔬 Evaluation Methodology

All 2,500 training examples were generated from 63 hand-written query patterns, filled in with real values pulled directly from the database. Every generated SQL query was **verified to execute correctly** against the database before training.

98.93% reflects the model correctly applying its **63 learned query patterns** to **new entity combinations** it hadn't seen in that exact combination before, rather than generalization to entirely novel query structures or a different schema.

## 🚀 Run Locally

```bash
git clone https://github.com/<your-username>/infra-ops-text-to-sql-qlora-mcp
cd infra-ops-text-to-sql-qlora-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Build the data:
```bash
python data/build_db.py
python data/generate_dataset.py
```

Establish the baseline, then fine-tune:
```bash
python scripts/baseline_eval.py     # downloads the base model (about 4.5GB)
bash train.sh                       # took about 5 hours on 16GB RAM in practice
```

Evaluate and compare:
```bash
python scripts/finetuned_eval.py
python scripts/compare_results.py
```

Serve it live:
```bash
npx @modelcontextprotocol/inspector python mcp_server/server.py
```

This opens a browser UI to call the `text_to_sql` tool directly. Example from an actual run:

**Q:** "which teams have more than 2 unresolved incidents?"

**Generated SQL:**
```sql
SELECT t.name FROM incidents i JOIN services s ON i.service_id = s.service_id
JOIN teams t ON s.team_id = t.team_id WHERE i.resolved_at IS NULL
GROUP BY t.name HAVING COUNT(*) > 2;
```

**Result:** 12 teams returned, including Compute Platform, Security, Storage, and Workflow Orchestration.

A harder example, involving date arithmetic:

**Q:** "what is the average time in minutes between an alert being triggered and acknowledged for services owned by the Security team?"

**Result:** approximately 34 minutes, computed by a correctly generated query joining `alerts`, `services`, and `teams`.

## 🔑 Secrets Required

None. This project runs entirely locally. No API keys, no cloud services, no external accounts needed.

## 🔮 Future Work

- Run a plain LoRA (8-bit, cloud GPU) comparison arm to complete a three-way comparison against this project's existing base model and QLoRA results, showing specifically the accuracy cost of 4-bit versus 8-bit quantization.
- Expand the hard-tier template set to test deeper multi-hop reasoning.

## 👩‍💻 Author

Nirusha Mantralaya Ramesh

🐙 GitHub: Nirusha-19

## 📄 License

MIT. Free to use, fork, and build upon.
