# Nesshield AI

Nesshield AI is a React and FastAPI financial intelligence prototype. It reads a Capital One Nessie sandbox account, reconciles transactions into a shared ledger, forecasts cash, simulates liquidity risk, attributes risk to events, and compares illustrative interventions. Gemini briefing support is optional.

## Requirements

- Python 3.10+
- Node.js 20+
- A Nessie sandbox API key (`NESSIE_API_KEY`)
- Optional Gemini API key (`GEMINI_API_KEY`)

## Setup

Create a `.env` in the repository root:

```env
NESSIE_API_KEY=your_nessie_key
GEMINI_API_KEY=your_gemini_key
```

Install and start the API:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.api:app --reload
```

Install and start the dashboard in a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

The API listens at `http://127.0.0.1:8000`; the dashboard defaults to `http://localhost:5173`.

## Risk and decision assumptions

The simulation horizon is 14 days and uses 10,000 paths by default. A 0.35 systemic shock correlation links adverse payment delays and unexpected-expense likelihood in the default simulation. Payment settlement labels are not available from the Nessie records, so no real-world payment-timing model is claimed. Synthetic timing model results, clearance, expense shocks, and intervention costs remain explicit illustrative assumptions. The dashboard labels intervention pricing as a placeholder; replace it with actual bank or vendor quotes before relying on a comparison.

## Tests and build

```powershell
python -m pytest -q
cd frontend
npm run build
```
