# Local Deploy (5-minute bootstrap)

## 1) API

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install fastapi uvicorn
uvicorn apps.api.app.main:app --reload --port 8000
```

## 2) Dashboard

```bash
cd apps/dashboard
npm install
npm run dev
```

## 3) Hooks

```bash
git config core.hooksPath .githooks
```
