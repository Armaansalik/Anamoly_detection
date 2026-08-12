# SentinelAgent — Software Project Management Plan

_A stakeholder-friendly plan following standard software engineering practice
(initiation → planning → execution → testing → launch → operations)._

---

## 1. Project charter (one page)

| Item | Details |
|---|---|
| **Project name** | SentinelAgent — Autonomous Anomaly Detection & Self-Healing Agent |
| **Goal** | Give small manufacturers (MSMEs) enterprise-grade machine protection at low cost, no ML expertise, offline-capable, explainable, and safe |
| **Sponsor / owner** | MSME factory owner / operations head |
| **Success criteria** | ① System detects anomalies before breakdown (demo: 8% of simulated data flagged) ② Actions are safe (all high-risk actions need human approval) ③ New use case onboarded in <30 min without code changes |
| **Budget (prototype)** | ~₹10–15k (1 PC + 5 sensor boxes) |
| **Timeline** | 12 weeks to production prototype (see Milestones) |
| **Team (minimum)** | 1 backend dev, 1 frontend dev, 1 domain expert (operator), 1 PM/QA |

---

## 2. Stakeholders & their needs

| Stakeholder | What they care about | What they get |
|---|---|---|
| **Factory owner** | Money: downtime costs, ROI | Lower downtime, longer machine life, low price |
| **Operator** | Simple, trustworthy, doesn't add work | One dashboard, plain-language alerts, Approve buttons |
| **Technician / maintenance** | Knows machine details | Plugin rulebook they can edit (thresholds per machine) |
| **IT person** | Easy to install/maintain | Docker one-command install, works offline |
| **Judges / investors** | Innovation + feasibility + safety | Plugin architecture, explainability, audit log |
| **End-users (workers)** | Not disturbed by false alarms | Accurate alerts only (self-learning reduces false alarms over time) |

---

## 3. Requirements — plain business language

### Business requirements (BR)
- BR-1: Continuously watch machines with cheap sensors; no human monitoring required.
- BR-2: Detect problems early — before breakdown — with minimal false alarms.
- BR-3: Respond automatically to safe fixes; always ask a human before risky actions.
- BR-4: Explain every decision in language a non-technical person understands.
- BR-5: Work with unreliable internet (factory floors).
- BR-6: Support a new machine/sensor type without rewriting the system.
- BR-7: Keep a complete record (audit) of everything detected and done.

### Functional requirements (FR) — mapped to built features
| ID | Requirement | Where it's built |
|---|---|---|
| FR-1 | Ingest events via REST + WebSocket | `POST /api/v1/events`, `/ws` |
| FR-2 | Plugin loader: folder = one domain | `core/plugin_loader.py` |
| FR-3 | Anomaly scoring (0–1) | `backend/detection.py` |
| FR-4 | Drift monitoring + retrain API | `backend/detection.py`, `POST /api/v1/models/retrain` |
| FR-5 | Agent with tools, guardrails, reasoning trace | `backend/agent.py` |
| FR-6 | Risk-tiered executor + rollback + audit | `backend/actions_executor.py` |
| FR-7 | Live dashboard (no polling) | `frontend/` (WebSockets) |
| FR-8 | Conversational copilot reusing the same agent | `POST /api/v1/chat` |
| FR-9 | Explainability panel (SHAP-style) | `backend/explanations.py` |
| FR-10 | 3D digital twin view | `frontend/src/components/DigitalTwin.jsx` |

### Non-functional requirements (NFR)
- NFR-1: **Reliability** — JSON structured logging; failures never silently ignored.
- NFR-2: **Security** — no hardcoded secrets (`.env`); actions restricted to manifest list.
- NFR-3: **Performance** — handles ~1 event/sec easily (SQLite WAL; scale to TimescaleDB).
- NFR-4: **Portability** — Docker Compose; Windows & Linux.
- NFR-5: **Testability** — 22 automated tests; CI-able.

### Out of scope (v1)
- Multi-tenant authentication (planned: Keycloak)
- Real voice interface (planned: Whisper)
- Kafka-scale ingestion (planned: Redpanda)

---

## 4. Milestones & timeline (12 weeks)

| Phase | Weeks | Deliverable | Exit criteria |
|---|---|---|---|
| **1. Discovery** | 1 | Needs analysis, plugin spec | Stakeholders agree on the 3 metrics + 3 actions per domain |
| **2. Core build** | 2–4 | Event schema, plugin loader, ingestion API | 2 plugins load; events accepted & stored |
| **3. Intelligence** | 5–7 | Detection (Isolation Forest), drift monitor, retraining | Tests: spike flagged, drift detected |
| **4. Autonomy** | 8 | Agent reasoning + action executor (risk tiers, rollback, audit) | High-risk actions require approval; rollback works |
| **5. Experience** | 9–10 | Dashboard, WebSockets, chat copilot, digital twin | Live demo on 5 sources; chat answers correctly |
| **6. Proof of extensibility** | 11 | Second plugin (server health) without core changes | 30-min onboarding demo passes |
| **7. QA & launch** | 12 | Test suite, docs, docker, demo rehearsal | 22/22 tests pass; stakeholder demo accepted |

_Status today: Phases 1–7 code is built and passing tests; live demo running locally._

---

## 5. Risk register

| Risk | Likelihood | Impact | Mitigation | Status |
|---|---|---|---|---|
| Sensors send noisy/garbage data | Medium | Medium | Schema validation at ingestion; adapters ignore unknown keys | Built-in |
| False alarms annoy operators | Medium | Medium | Self-learning thresholds + confidence scores; explainability panel | Built-in |
| Model goes stale over time | High | High | **Drift monitor** flags behavior change + retrain API | Built-in |
| Agent does something dangerous | Low | High | **Guardrails** (manifest-only actions) + approval gate for high risk + rollback | Built-in |
| Bad internet on factory floor | High | Medium | Offline buffering design; optional MQTT; local-first storage | Designed |
| Stakeholder doesn't trust AI | High | High | Plain-language reasoning traces + audit log + live explainability | Built-in |
| Scope creep (judges ask for new domain) | Medium | Low | Plugin architecture — demo a new plugin in <30 min | Built-in |

---

## 6. Quality & acceptance criteria

| Check | Criteria | How verified |
|---|---|---|
| Detection works | Spike value → score > normal; incident created | `tests/test_detection.py` (22 tests) |
| Safety works | High-risk action never executes without approval | Manual demo: Approve/Reject buttons |
| Accountability works | Every action has audit rows (who/what/why/outcome) | `GET /api/v1/incidents/{id}/audit` |
| Extensibility works | Second domain onboarded with zero core changes | `plugins/server_health/` demo |
| Explainability works | Each incident has human-readable reasoning trace | Dashboard + chat |
| Performance | Event ingested + scored in <1s | Live test |

---

## 7. Communication plan

| Audience | How we communicate | How often |
|---|---|---|
| Owner / sponsor | 1-page status (KPIs: incidents, auto-actions, downtime saved) | Weekly |
| Operators | 30-min training: dashboard tour + approve/rollback practice | At launch |
| Team | Standup + kanban board (Todo/In-progress/Verify/Done) | Daily |
| Judges | 60-second demo script (see PLAIN_ENGLISH_GUIDE.md) | On demand |

---

## 8. KPIs (how we prove it works)

| KPI | Target |
|---|---|
| Anomalies detected before breakdown | ≥90% of injected anomalies flagged |
| Auto-resolved incidents | ≥70% resolved without human touch |
| Time to onboard a new plugin | <30 minutes |
| Downtime reduction (pilot) | ≥30% in 3-month pilot |
| False alarm rate (after learning) | <1 per machine per week |
