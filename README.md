# GSEA Dashboard — Green Software Engineering Analysis
**Student ID: 25942008 | Animashaun Taiwo Ibrahim**
**MSc Computer Science | 6G7V0007 | Manchester Metropolitan University | 2026**
**Supervisor: Samuel Atwood**

---

## What This Project Does

The GSEA Dashboard is an interactive web application that analyses how Green Software Engineering (GSE) practices are being discussed and adopted in the developer community, using the [dev.to](https://dev.to) public API as a grey literature corpus.

It also provides a full implementation of the [ISO/IEC 21031 Software Carbon Intensity (SCI)](https://greensoftware.foundation/articles/sci-specification-achieves-iso-standard-status/) formula:

```
SCI = (E × I + M) / R
```

Where:
- **E** = Energy consumed (kWh)
- **I** = Carbon intensity of the grid (gCO₂eq/kWh)
- **M** = Embodied hardware carbon (gCO₂eq)
- **R** = Functional unit (e.g. per API call)

---

## Primary Academic Contribution

**NLP-based GSE adoption analysis from dev.to grey literature**

The dashboard fetches developer blog articles from dev.to using the public API, strips markdown/HTML, and analyses each article for five GSE adoption signal dimensions:

| Dimension | What it measures |
|-----------|----------------|
| Energy Efficiency | Discussion of power consumption, kWh, TDP, profiling |
| Carbon Awareness | CO₂ emissions, carbon intensity, net-zero, scope 1/2/3 |
| Hardware Efficiency | Embodied carbon, e-waste, server utilisation, PUE |
| Green Practices | SCI, GSF, CodeCarbon, green coding principles |
| Measurement & Tooling | RAPL, Prometheus, carbon dashboards, monitoring |

Each article receives a **Green Software Engineering Adoption Score (GSEAS, 0–100)** and an adoption level assigned via equal quartile bands:

| Score | Level |
|-------|-------|
| 75–100 | **Strong** |
| 50–74 | **Moderate** |
| 25–49 | **Emerging** |
| 0–24 | **Low** |

Dimension weights (sum to 1.0): Energy Efficiency 25%, Carbon Awareness 20%, Hardware Efficiency 15%, Green Practices 25%, Measurement & Tooling 15%.

**Software-relevance filter.** Tag-based dev.to corpus collection (e.g. the `sustainability` and `carbon` tags) can pull in off-topic content from agriculture, climate policy, and other non-software domains that happen to mention "carbon footprint" once. Every article is checked for general software-engineering vocabulary or a domain-specific tool/standard signal (e.g. CodeCarbon, RAPL, SCI); articles that match neither are excluded from corpus-level statistics (mean score, dimension means, top articles) but are **not** silently dropped — their score remains fully computed and visible in the full results table, flagged as off-topic, for auditability.

---

## How to Run

### Quick start (no PyTorch required)

```bash
# 1. Extract the zip and open the gsea_dashboard folder in PyCharm
# 2. Open the Terminal and run:

pip install -r requirements_deploy.txt
streamlit run app.py
```

Then open **http://localhost:8501** in your browser.

### Full installation (includes transformer NLP)

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## Project Structure

```
gsea_dashboard/
├── app.py                          # Main Streamlit entry point
├── streamlit_app.py                # Streamlit Cloud entry point
├── backend/
│   ├── main.py                     # FastAPI REST API (8 endpoints)
│   ├── config.py                   # Pydantic settings
│   ├── services/
│   │   ├── sci_calculator.py       # ISO/IEC 21031 SCI engine (100% test coverage)
│   │   └── sci_data_service.py     # Database service layer
│   └── models/database.py          # SQLAlchemy ORM models
├── frontend/
│   ├── pages/
│   │   ├── nlp_extraction.py       # PRIMARY: dev.to GSE adoption analysis
│   │   ├── sci_calculator.py       # SCI score calculator
│   │   ├── energy_trend.py         # Longitudinal SCI trend analysis
│   │   ├── proxy_metrics.py        # CPU/memory proxy metric visualisation
│   │   ├── carbon_map.py           # Regional carbon intensity map
│   │   ├── data_ingestion.py       # GMT/CodeCarbon data ingestion
│   │   ├── comparative_analysis.py # Multi-config SCI comparison
│   │   └── reports.py              # CSV/JSON export
│   └── components/data_manager.py  # Vectorised SCI pipeline
├── nlp/
│   ├── devto_fetcher.py            # dev.to API client with caching
│   ├── gse_analyser.py             # GSE adoption signal extraction
│   └── pipelines/gsea_pipeline.py  # Legacy entity extraction pipeline
├── tests/
│   ├── unit/                       # 86 unit tests
│   └── integration/                # 23 integration tests
├── data/
│   └── devto_cache/                # Cached dev.to API responses
├── .github/workflows/ci.yml        # GitHub Actions CI pipeline
├── requirements.txt                # Full dependencies (includes PyTorch)
├── requirements_deploy.txt         # Slim dependencies (Streamlit Cloud)
└── packages.txt                    # System packages for Streamlit Cloud
```

---

## Dashboard Pages

| Page | Description |
|------|-------------|
| 🏠 Home | Live KPIs, SCI trend chart, quick start |
| 🔬 NLP Extraction | **Primary** — dev.to GSE adoption analysis |
| 📊 SCI Calculator | ISO/IEC 21031 SCI score calculation |
| 📉 Energy Trend | Longitudinal SCI trend with moving average |
| 📈 Proxy Metrics | CPU/memory proxy metric visualisation |
| 🗺️ Carbon Map | Regional carbon intensity world map |
| 📂 Data Ingestion | GMT CSV and CodeCarbon CSV ingestion |
| ⚖️ Comparative | Side-by-side SCI configuration comparison |
| 📋 Reports | CSV/JSON export |

---

## Tests

```bash
# Run all unit tests
python -m pytest tests/unit/ -v

# Run with coverage
python -m pytest tests/unit/ --cov=backend/services --cov=nlp --cov-report=term-missing
```

**Current status: 86 unit tests passing**

---

## Deployment (Streamlit Community Cloud)

1. Push this repository to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app
3. Set **Main file**: `streamlit_app.py`
4. Set **Requirements file**: `requirements_deploy.txt`
5. Deploy

Live URL: *(update after deployment)*

---

## Key References

- Green Software Foundation (2023). *State of Green Software Report*
- ISO/IEC 21031 (2024). *Software Carbon Intensity Specification*
- Guldner et al. (2024). *Systematic literature review of GSE tools (2010–2023)*
- Pang et al. (2016). *Practitioners' perspectives on green software engineering. ICSE 2016*
- Kanso, Noureddine & Exposito (2024). *Automated energy management framework. J. AISE*
- Spillias et al. (2025). *Human-AI collaboration in systematic reviews*

---

## Ethics

User study conducted under MMU ethics approval (reference: *insert before submission*).
All participants anonymised. Data stored securely and deleted after examination.

---

## License

MIT License — Copyright (c) 2026 Animashaun Taiwo Ibrahim
