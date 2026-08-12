# SentinelAgent — Plain English Guide (for Non-Technical Readers)

_No engineering background needed. Read this in 5 minutes._

---

## What is this project? (one paragraph)

Imagine a **very smart security guard for machines**. Normal security guards only
shout when something is already broken. SentinelAgent is a guard that:

1. **Watches** every machine continuously (temperature, vibration, power, speed)
2. **Learns what "normal" looks like** by itself — no technician has to program it
3. **Spots trouble early** — often hours or days before the machine actually breaks
4. **Explains its thinking** in plain language ("motor is running 30% hotter than usual")
5. **Acts safely** — fixes small problems automatically, and **asks a human before**
   doing anything risky
6. **Remembers** everything it does, so there is always proof of what happened and why

---

## How it works — a story, not a diagram

**Morning, a small factory.** Five machines are running. Small boxes with sensors
(₹500 each) are attached to them. They send readings every few seconds over WiFi.

**11:42 AM** — Machine 3's motor temperature starts climbing. Nothing is broken yet.

1. **The system notices**: "the temperature pattern is unusual compared to the last
   100 readings" → suspicion level rises.
2. **The AI thinks**: it pulls Machine 3's history, checks whether this happened
   before and how it was fixed, and confirms the machine's own rulebook (the
   "plugin") allows it to slow the motor.
3. **It acts**: automatically reduces motor speed 20% — this is **low risk**, so it
   does it instantly and logs it.
4. **An operator sees**: a notification with the reasoning written out in normal
   words — "temperature crossed the warning line, I throttled the motor by 20%,
   motor speed restored when readings returned to normal."
5. **Something riskier** (like restarting the production line) → the system **waits
   for a human to press Approve** on the dashboard. It never does risky things alone.

---

## The ML terms — translated for stakeholders

| Technical term | What it really means | Where it appears |
|---|---|---|
| **Isolation Forest** | A "smart alarm" that learns what normal looks like and spots odd single readings | The main detector |
| **Anomaly score (0–1)** | **Suspicion level** — 0 = "totally normal", 1 = "almost certainly wrong" | Every alert shows it |
| **Rolling z-score** | "How far is this reading from the machine's usual range?" — like a fever thermometer for machines | Behind the scenes |
| **LSTM Autoencoder** | A "pattern learner" that watches the shape of the data over time — catches slow, sneaky changes single readings miss | Gradual drift detector |
| **Drift monitor** | A **"behavior change watch"** — if the machine's data slowly shifts (e.g. it starts wearing out), the system notices and recommends retraining itself | Alerts "data changed — retrain" |
| **Training window / warmup** | **Learning period** — the first ~40 readings teach the system what's normal for this machine | Startup only |
| **Threshold / critical line** | **Danger line** — set per machine in the plugin manifest; "warning" and "critical" levels | Plugins config |
| **KL divergence** | "How different is today's data from yesterday's?" — bigger number = bigger change | Drift monitor |
| **Confidence** | How sure the AI is (0–100%) | Agent decision |
| **Reasoning trace** | The AI's **explanation trail** — every alert comes with a written "I did X because Y" list | Every incident |
| **RAG / memory** | The AI **remembers past incidents** and uses them to reason about new ones | Agent |
| **Guardrails** | **Safety rules** — the AI can only do things the plugin rulebook allows. It cannot invent actions | Everywhere |
| **Rollback** | **Undo button** — every automatic action has a defined way to reverse it | Action layer |
| **Audit log** | **Digital diary** — who/what did what, when, and what happened after | Every action |

---

## What's genuinely NEW (not just "another monitoring tool")

| Existing approach (enterprise systems, ₹10L–50L) | What SentinelAgent adds |
|---|---|
| Only **alerts** you after a breakdown | **Acts** — fixes small problems automatically, safely |
| Needs data scientists to tune | **Self-learning** — learns "normal" from live data, no labels needed |
| Fixed to one machine type | **Plugin architecture** — any sensor setup = a config folder, no code rewrite. New use case onboarded in ~30 minutes |
| Black box ("trust us, it's AI") | **Explains every decision** in plain language + reasoning trail |
| Cloud-dependent, breaks offline | **Works on unreliable internet** (edge buffering design) |
| Costs lakhs + annual fees | Runs on a ₹10–15k PC; sensors cost ₹500 each |
| Silent model rot over time | **Drift monitor** — notices when its knowledge goes stale and says "retrain me" |
| No audit trail for actions | Full **digital diary** — who approved, what happened, what was undone |

---

## Where this fits in real life

| Place | How it helps |
|---|---|
| **Small factory (MSME)** | Motor/compressor failure detection → avoid ₹50k–5L downtime per incident |
| **Server room / IT** | CPU/memory/latency watch → auto-restart services safely (plugin #2) |
| **Cold storage / logistics** | Temperature/humidity watch → avoid spoiling stock |
| **Any machine owner** | One operator can watch 20 machines instead of 5 |

---

## How to demo it to judges in 60 seconds

1. Show the dashboard with live charts ("these are 5 machines streaming right now")
2. Wait for a machine to turn orange/red (simulator injects trouble every ~minute)
3. Click the incident → show the **reasoning trace** written in plain words
4. Show a high-risk action with **Approve** button ("see — it asks permission for risky things")
5. Type in the chat: "why did machine_01 flag an anomaly?" → it answers using its own memory
