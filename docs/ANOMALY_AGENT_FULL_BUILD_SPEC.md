# Autonomous Anomaly Detection & Self-Healing Agent
## Full Production Build — Technical Architecture & Extension Specification

---

## 1. What Changes Between "Demo" and "Real Prototype"

| Aspect | Hackathon Demo | Real Working Prototype |
|---|---|---|
| Data | Simulated / CSV replay | Live sensor stream, buffered & persisted |
| ML | One pre-trained model, static | Continuously retrained, versioned, monitored for drift |
| Reasoning | Hardcoded if/else "agent" | Real LLM agent with tool-calling, memory, and guardrails |
| Actions | Print to console | Real actuator calls with rollback & safety interlocks |
| Interface | Static slides | Live dashboard, conversational copilot, voice, digital twin |
| Scope | One machine, one domain | Plugin architecture — any sensor, any industry |
| Reliability | None | Logging, retries, alerting, uptime monitoring |

This document covers the second column — a system engineered to actually run continuously and be extended to new use cases without rewriting the core.

---

## 2. Full System Architecture (8 Layers)

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 8 — EXPERIENCE LAYER                                      │
│  Live Dashboard · Conversational Copilot · Voice · Digital Twin  │
└───────────────────────────┬───────────────────────────────────────┘
                             │
┌───────────────────────────▼───────────────────────────────────────┐
│  LAYER 7 — ACTION & ORCHESTRATION                                 │
│  Action executor · Safety interlocks · Rollback · Audit log       │
└───────────────────────────┬───────────────────────────────────────┘
                             │
┌───────────────────────────▼───────────────────────────────────────┐
│  LAYER 6 — AGENTIC REASONING                                      │
│  LLM agent · Tool-calling · RAG over logs · Root-cause memory     │
└───────────────────────────┬───────────────────────────────────────┘
                             │
┌───────────────────────────▼───────────────────────────────────────┐
│  LAYER 5 — ML DETECTION                                           │
│  Isolation Forest · LSTM Autoencoder · Drift monitor · Retraining │
└───────────────────────────┬───────────────────────────────────────┘
                             │
┌───────────────────────────▼───────────────────────────────────────┐
│  LAYER 4 — FEATURE STORE & TIME-SERIES DB                         │
│  Rolling windows · Feature engineering · Historical replay        │
└───────────────────────────┬───────────────────────────────────────┘
                             │
┌───────────────────────────▼───────────────────────────────────────┐
│  LAYER 3 — STREAMING & INGESTION                                  │
│  MQTT / Kafka broker · Schema validation · Buffering               │
└───────────────────────────┬───────────────────────────────────────┘
                             │
┌───────────────────────────▼───────────────────────────────────────┐
│  LAYER 2 — EDGE SENSING                                           │
│  Sensors · Microcontroller · Local pre-filtering · Offline buffer │
└───────────────────────────┬───────────────────────────────────────┘
                             │
┌───────────────────────────▼───────────────────────────────────────┐
│  LAYER 1 — DOMAIN PLUGIN LAYER (Extensibility)                    │
│  Adapter SDK · Config-driven onboarding · Domain plugin manifest  │
└─────────────────────────────────────────────────────────────────┘
```

### Layer-by-layer technical detail

**Layer 1 — Domain Plugin Layer (the "fits any problem" part)**
This is what turns the project from a single manufacturing demo into a reusable platform. Every domain (manufacturing, banking fraud, healthcare vitals, cold-chain logistics) is a **plugin**, not a rewrite.

- Each plugin is a folder with:
  - `manifest.yaml` — declares data schema, thresholds, units, and which actions are permitted
  - `adapter.py` — translates domain-specific raw input into the platform's standard event format
  - `actions.py` — defines what "safe automated response" means in that domain
  - `dashboard.json` — declares which widgets/metrics this domain's dashboard shows
- The core engine (Layers 2–8) never changes — it only talks to the standard event schema
- New domain onboarding becomes: write a config + adapter, not rebuild the pipeline

**Layer 2 — Edge Sensing**
- Hardware: ESP32 / Raspberry Pi + relevant sensors (temperature, vibration, current, pressure)
- Local pre-filtering (basic threshold checks) to reduce noise before it hits the network
- Local buffering (SQLite/flash) so data isn't lost if connectivity drops — critical for real MSME factory floors with unreliable internet

**Layer 3 — Streaming & Ingestion**
- MQTT broker (Mosquitto) for lightweight edge devices → Kafka (or Redpanda for lower ops overhead) for backend durability and replay
- Schema validation at ingestion (Pydantic/JSON Schema) so malformed sensor data doesn't corrupt downstream models

**Layer 4 — Feature Store & Time-Series DB**
- TimescaleDB or InfluxDB for time-series storage
- Rolling feature computation (mean, std dev, rate-of-change over 1/5/15-min windows) — this is what actually feeds the ML models, not raw readings
- Historical replay capability so new ML models can be backtested against past incidents

**Layer 5 — ML Detection (the core intelligence)**
- **Isolation Forest** — fast, unsupervised, good for point anomalies, cheap to retrain
- **LSTM Autoencoder** — sequence modeling, catches gradual drift Isolation Forest misses
- **Drift monitor** — tracks whether incoming data distribution is diverging from training data (using something like Evidently AI or a custom KL-divergence check) — this is what separates a "real" ML system from a demo; models silently rot without this
- **Scheduled retraining** — weekly/monthly retrain job using accumulated labeled incidents

**Layer 6 — Agentic Reasoning (this is the "agent," not a lookup table)**
- LLM agent framework: LangGraph (stateful, good for multi-step reasoning + tool calls)
- **Tools available to the agent:**
  - `get_machine_history(machine_id, window)` — pulls recent readings
  - `get_similar_past_incidents(embedding)` — RAG lookup over a vector store of past resolved incidents
  - `check_maintenance_schedule(machine_id)` — cross-references whether this is expected wear
  - `propose_action(action_type, risk_level)` — drafts the action, does not execute it directly
- **Memory:** vector store (pgvector or Chroma) of past incidents + resolutions, so the agent's reasoning improves over time instead of resetting each time
- **Guardrails:** the agent can only select from a pre-approved action list per plugin manifest — it cannot invent arbitrary system commands

**Layer 7 — Action & Orchestration**
- Executes the agent's proposed action only after a **risk check** (low-risk = auto-execute, high-risk = queue for human approval)
- Rollback capability — every automated action has a defined "undo" step
- Full audit log — what was detected, why, what action, who/what approved it, outcome

**Layer 8 — Experience Layer (the "futuristic and interactive" part)**
- **Live Dashboard:** React + WebSockets (not polling) for true real-time updates; charts via Recharts/D3
- **Digital Twin View:** Three.js 3D representation of the factory floor / machine layout, color-coded live by health score — operators see problems spatially, not just as a table row
- **Conversational Copilot:** a chat panel where an operator can ask "why did machine 3 flag an anomaly at 2 AM?" and the agent answers using its own reasoning trace and RAG memory — this reuses Layer 6, doesn't duplicate logic
- **Voice Interface:** Whisper (speech-to-text) for voice queries on the factory floor where typing isn't practical, plus TTS for spoken alerts
- **Explainability Panel:** live SHAP value visualization showing *why* the ML layer flagged a specific reading — builds operator trust, addresses the "black box AI" objection judges/evaluators often raise
- **What-if Simulation:** operators can drag a slider ("what if temperature keeps rising for 10 more minutes?") and see the agent's projected reasoning — a genuinely differentiating, demo-able feature

---

## 3. Recommended Tech Stack Summary

| Layer | Technology | Why |
|---|---|---|
| Edge | ESP32, MicroPython/C++ | Cheap, WiFi-native, huge community support |
| Streaming | MQTT (Mosquitto) → Kafka/Redpanda | Industry standard for IoT; durable replay |
| Storage | TimescaleDB, PostgreSQL + pgvector | Time-series + vector search in one engine |
| ML | scikit-learn, PyTorch | Isolation Forest + LSTM implementation |
| Drift monitoring | Evidently AI | Open source, purpose-built for this |
| Agent framework | LangGraph + an LLM API | Stateful multi-step reasoning with tools |
| Backend | FastAPI | Async, fast, great for streaming endpoints |
| Frontend | React + WebSockets + Three.js | Real-time UI + 3D digital twin |
| Voice | Whisper (STT) + a TTS API | Practical for floor use |
| Deployment | Docker Compose (prototype) → AWS ECS/K8s (scale) | Portable, cloud-ready path |
| Auth/Multi-tenant | Keycloak or Auth0 | Needed once multiple MSME clients onboard |

---

## 4. The Build Prompt

Copy the block below into an AI coding assistant (e.g., Claude Code, Cursor) as the starting instruction to scaffold the full system. It's written so the assistant builds the **plugin-based core first**, then implements the manufacturing use case as the first plugin — proving the extensibility claim rather than just asserting it.

```
Build a production-grade, extensible anomaly detection and autonomous response
platform called "SentinelAgent." The platform must be domain-agnostic at its
core and support new use cases (manufacturing, banking fraud, healthcare
vitals, logistics cold-chain, etc.) as plugins, without modifying core code.

ARCHITECTURE TO IMPLEMENT (build in this order):

1. Core Event Schema
   - Define a standard Pydantic event model: {source_id, domain, timestamp,
     metric_name, value, unit, metadata}
   - All domain plugins must translate their raw data into this schema

2. Plugin System
   - Design a plugin loader that reads a `plugins/<domain_name>/manifest.yaml`
     declaring: data schema mapping, anomaly thresholds, permitted actions,
     and dashboard widget config
   - Each plugin folder contains: adapter.py (raw data -> standard event),
     actions.py (safe action definitions), manifest.yaml
   - Core engine must never import anything domain-specific directly

3. Ingestion Layer
   - FastAPI service with a WebSocket and REST endpoint for incoming events
   - Validate against the core event schema before accepting
   - Publish validated events to a Kafka/Redpanda topic (or MQTT for edge
     devices), with a fallback to an in-memory queue for local dev

4. Storage Layer
   - TimescaleDB (or SQLite for local dev) for time-series event storage
   - pgvector-backed table for storing incident embeddings + resolutions
     (used later by the reasoning agent for RAG)

5. ML Detection Layer
   - Implement an Isolation Forest and an LSTM Autoencoder, both trained on
     a rolling window of normal data per source_id
   - Combine both scores into a single anomaly confidence score
   - Implement a drift monitor that flags when live data distribution
     diverges from training distribution, and logs a retraining
     recommendation (do not auto-retrain silently)

6. Agentic Reasoning Layer
   - Build a LangGraph agent with tools:
     get_machine_history(source_id, window),
     get_similar_past_incidents(embedding_query),
     propose_action(action_type, risk_level)
   - The agent must only propose actions from the current plugin's
     manifest-defined allowed action list — never invent new action types
   - Every agent decision must produce a human-readable reasoning trace
     that gets stored alongside the incident record

7. Action & Orchestration Layer
   - Implement a risk-tiered executor: low-risk actions auto-execute,
     high-risk actions are queued for human approval via the dashboard
   - Every executed action must have a corresponding rollback function
   - Full audit log: what was detected, agent's reasoning, action taken,
     who approved (if applicable), and outcome

8. Experience Layer
   - React frontend with a live dashboard (WebSocket-fed, not polling)
   - A conversational chat panel that lets a user ask natural-language
     questions about any incident, answered by the Layer 6 agent using its
     stored reasoning trace and RAG memory — do not build a second,
     separate chatbot; reuse the same agent
   - A simple Three.js visualization showing sources as nodes color-coded
     by current health/anomaly score
   - An explainability panel showing feature-level contribution to each
     anomaly score (e.g., using SHAP)

9. First Plugin: Manufacturing
   - Implement `plugins/manufacturing/` as the reference plugin:
     adapter for temperature/vibration/current sensor data, thresholds
     tuned for typical MSME machinery, and actions: throttle_motor,
     restart_process, alert_operator
   - This plugin must be built ENTIRELY through the plugin interface —
     if it requires touching core engine code, the plugin architecture
     has failed and must be redesigned

10. Second Plugin (proof of extensibility)
    - Implement a second, structurally different plugin (e.g., a simple
      "server health" plugin monitoring CPU/memory/latency) using only
      the plugin interface, to prove the core is genuinely domain-agnostic

NON-FUNCTIONAL REQUIREMENTS:
- All services containerized via Docker Compose for local development
- Structured logging throughout (JSON logs), not print statements
- Config via environment variables / .env, no hardcoded secrets
- Basic test coverage for the ML scoring function and the plugin loader
- README documenting how to add a new plugin in under 30 minutes

Do not skip the plugin abstraction to "save time" on the manufacturing
demo — the entire point of this build is that the manufacturing use case
is provably just one interchangeable plugin, not a special case.
```

---

## 5. Suggested Build Order for a Solo/Small Team (10–12 weeks)

| Weeks | Focus |
|---|---|
| 1–2 | Core event schema, plugin loader, ingestion API |
| 3–4 | Storage layer, feature engineering, ML detection (Isolation Forest first, simpler) |
| 5 | LSTM Autoencoder, drift monitor |
| 6–7 | Agentic reasoning layer (LangGraph agent + tools) |
| 8 | Action/orchestration layer with risk tiers and rollback |
| 9–10 | Dashboard + WebSocket live updates + conversational copilot |
| 11 | Digital twin visualization + explainability panel |
| 12 | Second plugin (proof of extensibility) + polish + demo rehearsal |

This gives you a genuinely working, demoable, and technically defensible system — one where a judge asking "what if I tried this on a completely different sensor setup" has an honest, working answer instead of a hypothetical one.
