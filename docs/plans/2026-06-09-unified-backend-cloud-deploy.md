# Unified Backend Cloud Deploy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship one lightweight backend for news, specialization, PVE, simulator, and LLM-assisted analysis, then deploy it to the Tencent Lighthouse server.

**Architecture:** Keep the existing Python HTTP backend as the public service. Reuse the existing JS payload modules from Python through a small Node bridge so the structured specialization/PVE data stays single-sourced. The mini program reads remote APIs with local fallback data for development and legal-domain gaps.

**Tech Stack:** Python `http.server`, SQLite, Node CommonJS payload modules, WeChat Mini Program `wx.request`, Tencent Lighthouse Ubuntu service, optional SimCraft CLI.

### Task 1: Backend API Tests

**Files:**
- Modify: `tests/news_backend_test.py`

**Step 1:** Add failing tests for builds, PVE, simulator home, and simulator analysis payloads.

**Step 2:** Run `python3 -m unittest tests/news_backend_test.py -v`.

**Expected:** Tests fail because the new backend functions do not exist.

### Task 2: Unified Backend Endpoints

**Files:**
- Modify: `server/news_backend.py`
- Create: `server/simulator_payload.py`

**Step 1:** Implement JS payload loading with `node -e` and JSON stdout.

**Step 2:** Add routes:
- `GET /api/builds/home`
- `GET /api/builds/intel`
- `GET /api/builds/detail?id=...`
- `GET /api/pve/home`
- `GET /api/pve/module?key=...`
- `GET /api/simulator/home`
- `POST /api/simulator/analyze`

**Step 3:** Run Python tests and backend smoke checks.

### Task 3: Mini Program API Adaptation

**Files:**
- Create: `pages/common/api-client.js`
- Create: `pages/builds/builds-api.js`
- Create: `pages/pve/pve-api.js`
- Create: `pages/simulator/simulator-api.js`
- Modify: `pages/news/news-api.js`
- Modify: `pages/builds/*.js`
- Modify: `pages/pve/*.js`
- Modify: `pages/simulator/simulator.js`

**Step 1:** Add failing Node tests for API base URL reuse and fallback behavior.

**Step 2:** Implement shared API URL resolution and request wrappers.

**Step 3:** Update pages to render fallback first, then replace with remote payload.

### Task 4: Deployment

**Files:**
- Create: `server/wow-backend.service`
- Create: `server/deploy_lighthouse.sh`
- Modify: `README.md`

**Step 1:** Add service and deployment docs.

**Step 2:** Install/verify Python, Node, and SimCraft on the Lighthouse host.

**Step 3:** Upload the repo service files, start `wow-backend`, and smoke test `/health`.

### Task 5: Review And Finish

**Step 1:** Run JS and Python test suites.

**Step 2:** Run local diff/code review before commit/push.

**Step 3:** Address valid feedback, verify again, then commit and push.
