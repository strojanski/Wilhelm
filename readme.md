# Wilhelm

Wilhelm is an AI-assisted clinical workflow platform that unifies patient intake, triage PDFs, X-ray fracture detection, and auto-generated medical notes in one web app that can be hosted localy to accelerate emergency care decisions.
<!-- Clinical workflow platform for patient intake, visit documentation, X-ray fracture analysis, and LLM-assisted report generation. -->

Our motivation is to deliver a practical, high-impact product that can compete across almost every prize track: vision, Flare, AI, APIs, greater good, web/mobile UX, innovation, code quality, growth potential, teamwork, and sponsor technologies including Gemini, and Flare.

This repository combines a React frontend, a Spring Boot backend, a multimodal LLM API, and a vision inference stack.

## What this project does

- Manages patients and visits (create, browse, delete).
- Uploads and serves triage PDFs, medical reports, and X-ray images.
- Runs fracture analysis on uploaded X-rays.
- Uses an LLM service to generate or improve clinical notes from text + documents.

## Architecture

```text
Frontend (Vite + React)  -->  Backend (Spring Boot + PostgreSQL)
	|                               |
	|                               +--> Vision API (fracture segmentation/classification)
	|
	+-------------------------------> LLM API (FastAPI, multimodal analyze/transcribe)
```

## Repository map

- `frontend/` React + TypeScript app (Vite + Tailwind)
- `backend/WilhelmBackend/` Spring Boot backend (Kotlin)
- `llm_api/` FastAPI multimodal service (`/analyze`, `/transcribe`)
- `vision/` Vision inference API and TEE extension logic
- `vision_classifier/` classifier scripts and assets
- `vision_segmentation/` segmentation pipeline and model assets
- `use_cases/` sample patient materials and scenario data

## Prerequisites

Install these tools before running locally:

- Node.js 20+
- npm 10+
- JDK 21
- Maven 3.9+ (or use `mvnw` if available)
- Python 3.11+
- PostgreSQL 14+
- Docker Desktop (optional, for containerized startup)

## Quick start (recommended local dev flow)

Run each service in its own terminal.

### 1. Start PostgreSQL and create database

Create a database and credentials, then point backend config to it.

Example SQL:

```sql
CREATE DATABASE wilhelm;
CREATE USER wilhelm_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE wilhelm TO wilhelm_user;
```

### 2. Configure and run backend

Edit `backend/WilhelmBackend/src/main/resources/application.properties`:

```properties
spring.datasource.url=jdbc:postgresql://localhost:5432/wilhelm
spring.datasource.username=wilhelm_user
spring.datasource.password=your_password
app.reports.directory=reports

# Vision service endpoint
app.ai.api-url=http://localhost:8000

# Public backend URL used to build image download URLs for vision analysis
app.base-url=http://localhost:8080
```

Run backend:

```bash
cd backend/WilhelmBackend
./mvnw spring-boot:run
```

Backend base URL: `http://localhost:8080`

### 3. Configure and run LLM API

```bash
cd llm_api
cp .env.example .env
```

Adjust `.env` for your provider (Google OpenAI-compatible, local vLLM, or OpenAI).

Then run:

```bash
docker compose up --build
```

or locally:

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

LLM API URL from project root Docker setup: `http://localhost:8082`

### 4. Configure and run vision API

The backend calls the vision API for X-ray analysis at `/analyze-url`.

From repository root:

```bash
docker compose up --build vision-api
```

or run from `vision/` manually (after installing `vision/requirements.txt`) with your model paths configured.

Vision API URL: `http://localhost:8000`

### 5. Configure and run frontend

Create `frontend/.env` with:

```env
VITE_API_URL=http://localhost:8080/api
VITE_LLM_URL=http://localhost:8082
```

Run frontend:

```bash
cd frontend
npm install
npm run dev
```

Frontend URL: `http://localhost:5173`

## Build commands

### Frontend build

```bash
cd frontend
npm run build
```

Output: `frontend/dist/`

### Backend build

```bash
cd backend/WilhelmBackend
./mvnw package
```

Output JAR: `backend/WilhelmBackend/target/Wilhelm-0.0.1-SNAPSHOT.jar`

### LLM API image build

```bash
cd llm_api
docker build -t gemma-api .
```

### Vision image build

From repository root:

```bash
docker build -t wilhelm-vision .
```

## Run with Docker (service-specific)

There are multiple compose files in this repo. Use the one that matches the service you want to run:

- Root `docker-compose.yml`: vision API + TEE extension
- `llm_api/docker-compose.yml`: multimodal LLM API (exposes host port 8082)
- `backend/WilhelmBackend/docker-compose.yml`: backend app container template

Examples:

```bash
# Vision services from repo root
docker compose up --build

# LLM API
cd llm_api
docker compose up --build
```

## API and UI endpoints

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8080/api`
- Backend health/docs: Spring Boot default actuator/docs only if configured
- LLM API health: `http://localhost:8082/health`
- LLM API Swagger: `http://localhost:8082/docs`
- Vision API health: `http://localhost:8000/health`

## Typical development workflow

1. Start PostgreSQL.
2. Start backend (`8080`).
3. Start vision API (`8000`) for X-ray analysis features.
4. Start LLM API (`8082`) for report generation features.
5. Start frontend (`5173`).

If one AI service is down, only the dependent feature set is affected; patient/visit CRUD still works through backend + database.

## Troubleshooting

- CORS issues: backend currently allows broad origins; verify frontend env URLs are correct.
- `POST /analyze` failing from frontend: check `VITE_LLM_URL` points to `http://localhost:8082`.
- X-ray analyze failing: ensure backend `app.ai.api-url` matches vision API URL and that image files are reachable via backend `app.base-url`.
- Docker on Linux and host model servers: for `host.docker.internal`, add `extra_hosts` mapping as noted in `llm_api/docker-compose.yml`.

## Additional docs

- Backend details: `backend/WilhelmBackend/README.md`
- LLM API details: `llm_api/README.md`
- Vision details: `vision/README.md`
- Flare deployment notes: `flare_deploy.md`

## Hackathon Feedback and Submission Answers

- Share feedback about any technology you interacted with at this hackathon. Remember to mention what tech you're reviewing: We reviewed Gemini API, Gemma, Flare, FastAPI, Spring Boot, and Docker. Gemini/Gemma gave fast iteration for structured medical-text outputs, Flare added a strong trust layer for verifiable workflows, and Docker made our multi-service setup reproducible. The main friction points were cross-service env configuration and model endpoint tuning, but overall the stack was reliable and production-minded.
- Which of the following GenAI tools did you use this weekend? (Required Dropdown Multiselect): OpenAI, Gemini, Gemma, Hugging Face.
- Did you implement a generative AI model or API in your hack this weekend? (Required Long text): Yes. We integrated a generative AI API through our llm_api service to process clinician notes, optional PDF context, and metadata, then generate structured medical summaries/reports for faster triage and documentation. We used it to reduce manual writing time, improve consistency, and support decision-making with clear, contextual outputs.
- If you are submitting to the Best Use of Gemini API prize category, please provide your Gemini API Key Project Number. (Optional, Short text): To be provided by the team lead from Gemini AI Studio Project Number before final submission.
