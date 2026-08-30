# MedVision Guard — Frontend

React (Vite) frontend for the MedVision Guard triage UI. The backend
(`main.py`, `HealthConsensusEngine`) lives at the repo root — see the root
[README.md](../README.md) for backend setup and architecture.

## Running locally

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173`). By default the
frontend calls the backend at `http://127.0.0.1:8000`; override with a
`VITE_BACKEND_URL` environment variable (e.g. in a `frontend/.env` file).

## Deploying

**Frontend → Vercel.** `frontend/vercel.json` configures the build. In the
Vercel dashboard: New Project → import this repo → set **Root Directory** to
`userweb/frontend`. Add an environment variable `VITE_BACKEND_URL` pointing
at your deployed backend's URL, then redeploy.

Deploy the backend first (see root README) to get its URL for
`VITE_BACKEND_URL`.
