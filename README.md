# Azimuth

Self-hosted personal AI chat assistant with a FastAPI backend and React frontend, deployed via Docker Compose.

## Stack

- Backend: Python 3.12 + FastAPI + aiosqlite
- Frontend: React 18 + TypeScript + Vite + Tailwind CSS
- AI Provider: OpenRouter (OpenAI-compatible API)
- Database: SQLite (`backend/data/azimuth.db`)

## Prerequisites

- Docker Desktop with Compose v2
- OpenRouter API key

## Configuration

1. Copy `.env.example` to `.env`.
2. Set `OPENROUTER_API_KEY`.
3. Optionally set `DEFAULT_MODEL` to any valid model from `GET /api/settings/models`.

Example `.env`:

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
DEFAULT_MODEL=anthropic/claude-sonnet-4.5
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

## Run

```bash
docker compose up -d --build
```

Services:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Health: `http://localhost:8000/api/health`

## Deployment Verification

1. Confirm containers are running:

```bash
docker compose ps
```

2. Verify backend health:

```bash
curl http://localhost:8000/api/health
```

3. Verify frontend API proxy:

```bash
curl http://localhost:3000/api/health
```

4. Verify persistence:

- Create a conversation in UI.
- Restart containers:

```bash
docker compose restart backend frontend
```

- Refresh UI and confirm conversation still exists.

## Access From Another Device (Phone/Tablet)

1. Find your server LAN IP (Windows PowerShell):

```powershell
Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -ne $null } | Select-Object InterfaceAlias,IPv4Address
```

2. On phone (same network), open:

```text
http://<server-lan-ip>:3000
```

Example on this machine during verification:

```text
http://192.168.1.16:3000
```

## Troubleshooting

### Invalid model ID (400)

If you see errors like `is not a valid model ID`, update `DEFAULT_MODEL` in `.env` to a currently valid model and restart backend:

```bash
docker compose up -d --build backend
```

You can list available models at:

```text
http://localhost:8000/api/settings/models
```

### Container name conflict

If Docker reports a container name already in use:

```bash
docker rm -f azimuth-backend azimuth-frontend
docker compose up -d
```

## Stop

```bash
docker compose down
```