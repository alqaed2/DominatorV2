# AI DOMINATOR — TikTok-First Closed-Loop (MVP)

## What this MVP does
- Manual Mode default (no TikTok account linking required)
- Onboarding -> Daily Brief -> Build Pack -> Submit Metrics -> Lift Report
- Dominance Score v1 (heuristics) + Experiment Engine A/B/C + Genome learning

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=app.py
flask run --port 8000
