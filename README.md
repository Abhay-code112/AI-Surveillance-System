# AI CCTV Surveillance Platform 👁️🛡️

An enterprise-grade, real-time AI video surveillance and analytics platform. Built to automatically detect violence, suspicious activities, and specific crimes (like vandalism, burglary, assault, robbery, and fighting) across multiple live RTSP camera streams or uploaded video files.

---

## 📖 Table of Contents
- [Architecture](#architecture)
- [Machine Learning Engine](#machine-learning-engine)
- [Features](#features)
- [Security](#security)
- [API Documentation](#api-documentation)
- [Setup \& Installation (Docker)](#setup--installation)
- [Local Development Setup](#local-development-setup)
- [Future Scope](#future-scope)

## 🏗️ Architecture

The platform is designed using a modern decoupled architecture, allowing individual components to scale independently.

* **Frontend:** React + TypeScript + Vite. Modern SPA with real-time WebSocket integrations.
* **Backend:** FastAPI (Python 3.12). Handles async task queuing, RTSP stream processing, and REST API routing.
* **Database:** SQLite (Default, containerized) / PostgreSQL Ready.
* **Orchestration:** Docker \& Docker Compose (Multi-stage builds, non-root users, Nginx reverse proxy).

## 🧠 Machine Learning Engine

Our ML pipeline uses a highly optimized two-stage inference engine designed for high accuracy and low latency:

1. **Stage 1 (Violence Detection):** 
   - Powered by a custom **MaxViT / VideoMAE** transformer architecture. 
   - Analyzes temporal frame sequences (16-frame clips) to determine if a scene contains violent anomalies.
2. **Stage 2 (Crime Classification):** 
   - If violence is detected, the engine routes the clip to specialized binary classifiers (Fighting, Assault, Vandalism, Arrest, Robbery, Burglary).
   - If no violence is detected but the activity is anomalous, it falls back to a **UCF-101** activity recognition model to classify the exact action.

## ✨ Features

- **Live Multi-Camera Monitoring:** Connect and analyze multiple RTSP/IP camera streams simultaneously.
- **Real-Time Dashboard:** View live stats, recent events, and a 24-hour activity breakdown chart.
- **Automated Alerting:** Configurable Email and Telegram notifications with evidence attachments.
- **Evidence Storage:** Automatically extracts and securely stores video clips and screenshots of anomalous events.
- **Role-Based Access Control (RBAC):** Admin and Operator roles for secure system management.
- **Asynchronous Processing:** Video uploads are processed in the background, keeping the API fast and responsive.

## 🔒 Security

This platform implements strict security best practices:
- **Authentication:** JWT-based stateless authentication (`HS256`).
- **Container Security:** Both Frontend and Backend Docker containers run strictly as unprivileged/non-root users (`appuser` / `nginx`).
- **Environment Isolation:** Secrets and database credentials are fully isolated via `.env` files with strict fail-fast validation.

## 📚 API Documentation

Once the backend is running, fully interactive OpenAPI (Swagger) documentation is available automatically.

- **Swagger UI:** `http://localhost/api/docs`
- **ReDoc:** `http://localhost/api/redoc`

## 🐳 Setup & Installation (Docker)

The recommended way to deploy this application is using Docker Compose.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/ai-surveillance.git
   cd ai-surveillance
   ```

2. **Configure Environment:**
   Copy the example environment file and update the `JWT_SECRET_KEY` with a strong random string.
   ```bash
   cp .env.example .env
   ```

3. **Start the Platform:**
   ```bash
   docker-compose up --build -d
   ```

4. **Access the Dashboard:**
   Open your browser and navigate to `http://localhost`. The first time you run the system, you can create a new Admin account directly from the login page.

## 💻 Local Development Setup

If you wish to run the project outside of Docker:

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # (or venv\Scripts\activate on Windows)
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## 🚀 Future Scope

- **Edge Deployment:** Optimization using TensorRT and ONNX for deployment directly on edge devices (Jetson Nano, Coral TPU).
- **Face Recognition:** Integrating facial recognition pipelines to track known threats or VIPs across cameras.
- **Kubernetes (K8s):** Providing standard Helm charts for enterprise cloud orchestration.
- **Multi-Tenant Architecture:** Extending the database schema to support isolated multi-tenant workspaces for commercial SaaS offerings.

---
*Developed with a focus on Clean Architecture, SOLID principles, and Production Readiness.*
