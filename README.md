# infra-feasibility-ai

> **Production-grade AI-powered SaaS platform for infrastructure and green energy investment analysis.**

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What It Does

A fully automated AI-powered infrastructure investment platform capable of:

- Evaluating green energy projects globally (solar, wind)
- Fetching live real-world data from World Bank + NASA POWER APIs
- Simulating energy systems using PyPSA (with pure-Python fallback)
- Calculating NPV, IRR, LCOE, payback period, Monte Carlo distributions
- Assessing country-level macroeconomic and political risk
- Running best/base/worst scenario analysis and sensitivity (tornado) charts
- Producing investor-grade structured JSON reports
- Generating Claude-ready prompts for AI narrative report writing
- Operating as a scalable SaaS platform with JWT authentication

---

## Architecture

```
infra-feasibility-ai/
├── app/
│   ├── main.py                    # FastAPI SaaS backend
│   ├── data/
│   │   ├── api_clients.py         # World Bank, NASA POWER, ElectricityMap
│   │   └── cleaners.py            # Data cleaning and normalisation
│   ├── models/
│   │   ├── pypsa_model.py         # PyPSA energy network simulation
│   │   ├── finance_advanced.py    # NPV, IRR, LCOE, Monte Carlo
│   │   ├── country_risk.py        # Country risk scoring engine
│   │   └── scenarios.py           # Best/Base/Worst + sensitivity
│   └── services/
│       └── reporter.py            # AI-ready report builder + Claude prompts
├── example_run.py                 # Sample end-to-end analysis (no server needed)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Quick Start

### Option 1: Run Example Locally

```bash
git clone https://github.com/Masim34/infra-feasibility-ai.git
cd infra-feasibility-ai
pip install -r requirements.txt
python example_run.py
```

### Option 2: Run API Server

```bash
cp .env.example .env
# Edit .env with your settings
uvicorn app.main:app --reload --port 8000
# API docs at: http://localhost:8000/docs
```

### Option 3: Docker Compose

```bash
cp .env.example .env
docker-compose up --build
# API at: http://localhost:8000
# Docs at: http://localhost:8000/docs
```

---

## API Usage

### 1. Get Access Token

```bash
curl -X POST http://localhost:8000/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"username": "analyst", "password": "any"}'
```

### 2. Run Full Project Analysis

```bash
curl -X POST http://localhost:8000/analyze \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "project_name": "Baghdad Solar Farm",
    "country_code": "IQ",
    "lat": 33.34,
    "lon": 44.40,
    "capacity_mw": 100,
    "technology": "solar",
    "electricity_price_usd_mwh": 70,
    "capex_per_mw": 800000,
    "opex_per_mw_year": 15000,
    "project_life_years": 25,
    "run_monte_carlo": true,
    "include_scenarios": true,
    "include_sensitivity": true,
    "include_claude_prompt": false
  }'
```

---

## Report Output Structure

```json
{
  "project": { "name", "technology", "country", "capacity_mw" },
  "energy": { "annual_production_mwh", "capacity_factor", "curtailment_mwh" },
  "financials": { "lcoe_usd_mwh", "npv_usd", "irr", "payback_years", "capex_breakdown" },
  "risk": { "composite_risk_score", "risk_category", "risk_adjusted_discount_rate" },
  "scenarios": { "best_npv", "base_npv", "worst_npv", "viable_scenarios" },
  "monte_carlo": { "npv_mean", "npv_p10", "npv_p90", "probability_positive_npv" },
  "sensitivity": { "electricity_price", "capex_per_mw", "annual_mwh", "discount_rate" },
  "investment_recommendation": { "verdict", "confidence", "summary" }
}
```

---

## Supported Countries (Risk Engine)

Built-in risk profiles for 35+ countries including:
`IQ` `KZ` `SL` `MG` `PK` `AE` `SA` `NG` `KE` `ZA` `IN` `CN` `BR` `EG` `MA` `GB` `DE` `US` and more.

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Backend API | FastAPI + Uvicorn |
| Energy Modelling | PyPSA + NumPy (fallback included) |
| Financial Engine | Pure Python (NPV, IRR, LCOE, Monte Carlo) |
| Real Data APIs | World Bank API, NASA POWER API, ElectricityMap |
| Database | PostgreSQL + SQLAlchemy + Alembic |
| Authentication | JWT (PyJWT) |
| Caching | Local JSON / Redis-ready |
| Containerisation | Docker + Docker Compose |
| AI Integration | Claude (Anthropic) / OpenAI |

---

## Environment Variables

Copy `.env.example` to `.env`:

```env
JWT_SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://postgres:password@localhost:5432/infraai
ELECTRICITYMAP_API_KEY=optional
ANTHROPIC_API_KEY=optional-for-claude-reports
```

---

## Built by GGC

**Global Group of Companies** | [ggcuk.com](https://www.ggcuk.com)

Built for evaluating large-scale infrastructure and renewable energy investments across Iraq, Kazakhstan, Sierra Leone, Madagascar, Pakistan, and beyond.

---

## License

MIT License. See [LICENSE](LICENSE).
