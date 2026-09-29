# AI Interior Design Assistant

Upload a room photo → pick a style → answer 2–3 questions → get an AI-redesigned
room image plus a shopping list of matching products.

```
interior-design-assistant/
├── backend/     FastAPI + Anthropic (vision) + OpenAI (image) + local product DB
└── frontend/    React (Vite) single-page app
```

## How the flow works

| Step | Endpoint | What happens |
|------|----------|--------------|
| 1. Upload | `POST /api/upload` (multipart: `style`, `image`) | Saves the photo, sends it to **Claude vision** to analyze existing furniture / layout / lighting, then asks Claude for 2–3 follow-up questions (budget, priorities, colors). Returns a `session_id`. |
| 2. Answer | `POST /api/chat` (`session_id`, `answers[]`) | Merges answers into the session. Replies `ready_to_generate` once every question is answered. |
| 3. Generate | `POST /api/generate` (`session_id`) | Claude combines analysis + style + answers into a **DALL·E prompt** and a planned furniture list → **OpenAI image API** renders the redesign → planned furniture is matched against `backend/app/data/products.json` for purchase links. |
| — | `POST /api/products/match` | Match an arbitrary furniture list against the catalogue (used internally, exposed for testing). |
| — | `GET /api/config` | Reports whether real API keys are present or the app is on mock data. |
| — | `GET /api/session/{id}` | Full session state (debug). |

## API keys — not required yet

`backend/.env` holds `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`. **Both are blank
for now on purpose.** With a key missing (or `FORCE_MOCK=true`), that provider's
calls return deterministic **mock** data so the entire flow is testable today.
Drop real keys into `backend/.env`, restart the backend, and the same code path
makes real API calls — nothing else to change. The frontend shows a banner
whenever it's running on mock data.

## Running it

### Backend (port 8000)

```powershell
cd backend
venv\Scripts\pip install -r requirements.txt        # deps already in venv; run if needed
venv\Scripts\uvicorn app.main:app --reload
```

Docs: http://127.0.0.1:8000/docs
Smoke test (server must be running): `venv\Scripts\python scripts\smoke_test.py`

### Frontend (port 5173)

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api` and `/media` to
the backend on port 8000, so start the backend first.

## Notes / scaffold limitations

- **Sessions are in-memory** (`backend/app/store.py`) — they reset when the
  backend reloads and won't work across multiple workers. Swap for Redis / a DB
  later; every caller goes through `get_session` / `update_session`.
- Uploaded images are stored under `backend/app/storage/uploads/` and served at
  `/media/uploads/<file>`.
- The product catalogue is a hand-written JSON file with placeholder
  `example.com` URLs and `picsum.photos` images.
- Model defaults: `claude-opus-5` (vision) and `dall-e-3` (image) — override via
  `backend/.env`.
