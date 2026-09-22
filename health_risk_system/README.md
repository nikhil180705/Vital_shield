# Health Risk Monitoring System — Terminal Prototype

> **IMPORTANT DISCLAIMER**
> This is a **software engineering prototype** for demonstration and research purposes only.
> All thresholds, risk scores, and AI outputs are **NOT medical advice**.
> They are prototype screening parameters, **NOT clinical diagnostic criteria**.
> This system does not diagnose, treat, or replace professional medical evaluation.

---

## 1. Project Purpose

A real-time health-risk monitoring and AI analysis prototype that simulates data from a smartwatch/wearable device.

The system demonstrates a complete pipeline:

```
Mock Wearable Data
        ↓
Data Validation
        ↓
Activity / Context Detection
        ↓
Rule-Based Risk Detection (Deterministic)
        ↓
Risk Event Creation
        ↓
AI Agent 1 — Possible Cause Analysis
        ↓
Cause Validation (Deterministic)
        ↓
AI Agent 2 — Precaution Recommendation
        ↓
Terminal Output
```

**The LLM never determines whether a reading is dangerous. The rule engine is the sole authority.**

---

## 2. Architecture

```
health_risk_system/
│
├── app/
│   ├── config.py              # All thresholds, LM Studio config, baseline
│   │
│   ├── models/
│   │   ├── sensor_models.py   # SensorReading (Pydantic), SensorReadingSequence
│   │   ├── risk_models.py     # ValidationResult, TriggeredRule, RiskScore, RiskEvent
│   │   └── ai_models.py       # CauseAnalysisResult, ValidatedCause, PrecautionResult
│   │
│   ├── mock/
│   │   └── scenarios.py       # 8 deterministic mock scenarios
│   │
│   ├── validation/
│   │   └── sensor_validator.py  # Sanity checking before rule engine
│   │
│   ├── context/
│   │   └── activity_detector.py  # Accelerometer-based activity + fall detection
│   │
│   ├── rules/
│   │   ├── rule_definitions.py   # All individual rule check functions
│   │   ├── rule_engine.py        # Orchestrates all rules + persistence
│   │   └── risk_scorer.py        # Deterministic score aggregation
│   │
│   ├── ai/
│   │   ├── llm_client.py        # LM Studio OpenAI-compatible client
│   │   ├── cause_agent.py       # AI Agent 1 — cause analysis
│   │   ├── cause_validator.py   # Deterministic validation of AI causes
│   │   └── precaution_agent.py  # AI Agent 2 — precaution recommendations
│   │
│   ├── pipeline.py              # End-to-end pipeline orchestrator
│   ├── renderer.py              # Terminal output renderer (ANSI colours)
│   └── logger_setup.py          # Rotating file logger
│
├── tests/
│   ├── conftest.py
│   ├── test_validation.py
│   ├── test_activity_detector.py
│   ├── test_rule_engine.py
│   ├── test_risk_scorer.py
│   ├── test_ai_parsing.py
│   └── test_scenarios.py
│
├── main.py
├── requirements.txt
├── pyproject.toml
└── .env.example
```

---

## 3. Installation

### Python version

Python 3.10 or higher recommended.

### Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. LM Studio Setup

1. Download LM Studio from https://lmstudio.ai
2. Inside LM Studio, search for and download: `Qwen/Qwen3-8B`
3. Load the model in LM Studio
4. Start the local server:
   - Go to the **Local Server** tab
   - Set the port to `1234`
   - Click **Start Server**

The system will connect to: `http://127.0.0.1:1234/v1`

---

## 5. Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Available settings:

| Variable | Default | Description |
|---|---|---|
| `LM_STUDIO_BASE_URL` | `http://127.0.0.1:1234/v1` | LM Studio server URL |
| `LM_STUDIO_MODEL` | `qwen3-8b` | Model identifier |
| `LM_STUDIO_TIMEOUT` | `60` | Request timeout seconds |
| `LM_STUDIO_MAX_TOKENS` | `1024` | Max response tokens |
| `LM_STUDIO_TEMPERATURE` | `0.2` | LLM temperature |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FILE` | `health_risk_system.log` | Log file path |

---

## 6. How to Run

```bash
cd health_risk_system
python main.py
```

The system will:
1. Check LM Studio availability
2. Run all 8 mock scenarios
3. Print a quick summary table
4. Print full detailed output for each scenario

---

## 7. Mock Scenarios

| # | Scenario | Expected Outcome |
|---|---|---|
| 1 | Normal Rest | NORMAL — No AI call |
| 2 | Normal Exercise | NORMAL_PHYSIOLOGICAL_ACTIVITY — No AI call |
| 3 | Elevated Resting HR | RISK EVENT → AI analysis |
| 4 | Low SpO2 | HIGH/CRITICAL → AI analysis |
| 5 | Heat Stress | POSSIBLE_HEAT_STRESS → AI analysis |
| 6 | Elevated Temp + Resting HR | Possible illness pattern → AI analysis |
| 7 | Possible Fall | POSSIBLE_FALL → HIGH risk → AI analysis |
| 8 | High Altitude SpO2 | Altitude context → AI analysis |

---

## 8. Rule Engine

All rules are in `app/rules/rule_definitions.py`. Each rule:
- Returns a `TriggeredRule` with `rule_id`, `rule_name`, `severity`, `reason`, `evidence`, `score_contribution`
- Is completely self-contained and inspectable
- Uses only thresholds from `app/config.py`

Key rules:
- `HR_REST_HIGH_001` — Elevated resting HR
- `SPO2_CRITICAL_001` — Critical SpO2
- `HEAT_STRESS_001` — Combined heat stress composite
- `ILLNESS_PATTERN_001` — Temp + resting HR pattern
- `FALL_POSSIBLE_001` — Possible fall from accelerometer pattern
- `MULTI_SPO2_HR_001` — Combined SpO2 + HR anomaly at rest
- `EXERCISE_NORMAL_001` — Normalises HR elevation during exercise

---

## 9. AI Agent 1 — Cause Analysis

Agent 1 receives the `RiskEvent` (sensor data + triggered rules + baseline).

It identifies plausible explanations with confidence scores. It is **forbidden** from:
- Diagnosing diseases
- Claiming certainty
- Inventing data

It must always use hedged language: *"possible", "may be consistent with", "candidate explanation"*.

Output is validated JSON (schema in `app/models/ai_models.py`).

---

## 10. Cause Validation

After Agent 1, a **deterministic validator** (`app/ai/cause_validator.py`) checks each proposed cause against the actual sensor readings.

Each cause receives:
- `SUPPORTED` — Strong sensor evidence backs it
- `PARTIALLY_SUPPORTED` — Some evidence, incomplete
- `NOT_SUPPORTED` — Evidence contradicts or is absent
- `INSUFFICIENT_DATA` — Cannot evaluate

Only `SUPPORTED` and `PARTIALLY_SUPPORTED` causes proceed to Agent 2.

---

## 11. AI Agent 2 — Precaution Recommendations

Agent 2 receives validated causes and generates conservative precautionary guidance.

It is **strictly forbidden** from:
- Prescribing medication
- Diagnosing disease
- Inventing symptoms or readings
- Claiming certainty

Output is structured JSON with immediate precautions, monitoring steps, and escalation conditions.

---

## 12. Safety Limitations

This prototype explicitly distinguishes:
- **ANOMALY** — A sensor reading outside expected range
- **RISK** — A pattern identified by the rule engine
- **POSSIBLE CAUSE** — A candidate explanation proposed by the AI
- **CONFIRMED DIAGNOSIS** — NOT possible from this system

The system never:
- Diagnoses any medical condition
- Prescribes treatment
- Replaces professional medical evaluation

For any real health concern, consult a qualified medical professional.

---

## 13. Replacing Mock Data with Real Wearable Data

The pipeline processes one `SensorReading` at a time via:

```python
for reading in provider.stream():
    pipeline.process_reading(reading, scenario_id=..., scenario_name=...)
```

To connect a real wearable (e.g., Bluetooth BLE):
1. Implement a `BluetoothSensorDataProvider` that yields `SensorReading` objects
2. Pass it to the pipeline instead of the mock scenario data
3. The rule engine, AI agents, and renderer require no modification

---

## 14. Running Tests

```bash
cd health_risk_system
pytest
```

Test coverage includes:
- Data validation (missing, invalid, boundary values)
- Activity detection (REST, WALKING, RUNNING, fall sequence)
- All individual rule functions
- Risk scoring (multi-sensor bonus, persistence, bands)
- AI JSON parsing (direct, markdown, embedded, malformed)
- LM Studio unavailability handling
- All 8 mock scenarios (integration)
