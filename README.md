# 🎓 Leksa — Your AI Voice Teacher

> **Stop reading alone. Start learning out loud.**

Leksa transforms any uploaded document into an **immersive, real-time voice lecture** powered by Gemini Live API. Upload your PDF or PPT — and an AI teacher begins explaining it to you naturally, just like a real classroom. Ask questions mid-lecture, get instant answers, and never feel stuck again.

<br/>

## 🏆 Built for the Gemini Live Agent Challenge

**Category:** Live Agents 🗣️
**Hackathon:** [Gemini Live Agent Challenge on Devpost](https://geminiliveagentchallenge.devpost.com)

<br/>

---

## 🎬 Demo Video

[![Leksa Demo](https://img.shields.io/badge/▶%20Watch%20Demo-YouTube-red?style=for-the-badge&logo=youtube)](https://youtube.com/your-demo-link)

---

## ❓ The Problem

Students, researchers, and professionals are drowning in documents — lecture slides, research papers, onboarding manuals. But reading alone is **passive**. There's no one to explain, no one to ask, and no way to know if you actually understood.

> 📖 Reading a 40-slide deck ≠ Understanding it.

---

## ✅ The Solution

**Leksa** takes your document and turns it into a **live, spoken lecture** — with a real AI teacher that:

- 🗣️ **Explains concepts naturally** in a conversational voice
- ✋ **Handles interruptions** — you can speak anytime, mid-sentence
- 🔄 **Adapts in real-time** — if you don't understand, it explains again
- 🧠 **Checks your comprehension** — asks you questions after each segment
- 📄 **Works with PDF & PPT** — just upload and go

---

## ✨ Features

| Feature | Description |
|--------|-------------|
| 🎤 **Real-time Voice Lecture** | AI reads and explains your document out loud |
| ✋ **Barge-in / Interruption** | Speak anytime — AI pauses and listens instantly |
| 📄 **PDF & PPT Support** | Upload any lecture slides or research paper |
| 🔁 **Adaptive Explanation** | AI re-explains in a different way if you're confused |
| 🧠 **Comprehension Checks** | AI asks you questions to verify understanding |
| ☁️ **Cloud-powered** | Fully hosted on Google Cloud — fast and reliable |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│                  FRONTEND (React)               │
│   File Upload  │  Mic Input  │  Audio Output    │
└────────────────────┬────────────────────────────┘
                     │ WebSocket
┌────────────────────▼────────────────────────────┐
│               BACKEND (FastAPI)                 │
│         hosted on Google Cloud Run              │
│                                                 │
│  ┌──────────────┐    ┌──────────────────────┐  │
│  │ Doc Parser   │    │  Live Session Manager │  │
│  │ PyMuPDF      │    │  WebSocket Handler    │  │
│  │ python-pptx  │    └──────────┬───────────┘  │
│  └──────┬───────┘               │               │
│         │                       │               │
│  ┌──────▼───────┐    ┌──────────▼───────────┐  │
│  │ Gemini Flash │    │  Gemini Live API      │  │
│  │ Script Gen   │    │  Real-time Voice      │  │
│  └──────┬───────┘    │  Barge-in Detection   │  │
│         │            │  Turn Management      │  │
│  ┌──────▼───────┐    └───────────────────────┘  │
│  │  Firestore   │                               │
│  │ Session State│                               │
│  └──────────────┘                               │
└─────────────────────────────────────────────────┘
         │
┌────────▼────────┐
│  Cloud Storage  │
│  (File Uploads) │
└─────────────────┘
```

---

## 🔄 How It Works — Step by Step

```
1. 📤  User uploads PDF or PPT
           ↓
2. 📝  Python parses document → extracts text (PyMuPDF / python-pptx)
           ↓
3. 🤖  Gemini Flash converts text → structured lecture script (segments)
           ↓
4. 💾  Segments saved to Firestore
           ↓
5. 🎙️  Gemini Live API starts real-time voice session
           ↓
6. 🗣️  AI teacher explains Segment 1 out loud
           ↓
7. ✋  User interrupts anytime → AI pauses → listens → answers → resumes
           ↓
8. 🔁  Next segment fetched → lecture continues
```

---

## 🛠️ Tech Stack

### 🤖 AI / Gemini
| Model | Purpose |
|-------|---------|
| `gemini-2.0-flash` | Document → Lecture script generation |
| `gemini-2.0-flash-live-001` | Real-time voice lecture + interruption |

### ☁️ Google Cloud Services
| Service | Purpose |
|---------|---------|
| **Cloud Run** | Backend hosting |
| **Cloud Storage** | Uploaded file storage |
| **Firestore** | Session state & segment tracking |
| **Cloud Build** | Automated deployment (IaC) |

### 🐍 Python Libraries
| Library | Purpose |
|---------|---------|
| `google-genai` | Gemini Flash + Live API SDK |
| `google-cloud-storage` | File upload to GCS |
| `google-cloud-firestore` | Session management |
| `PyMuPDF (fitz)` | PDF text extraction |
| `python-pptx` | PPT/PPTX slide extraction |
| `FastAPI` | REST API + WebSocket server |
| `uvicorn` | ASGI server |
| `websockets` | Real-time frontend connection |
| `python-dotenv` | Environment variable management |

### 🌐 Frontend
| Tech | Purpose |
|------|---------|
| React | UI framework |
| WebRTC / Web Audio API | Mic input & audio output |
| WebSocket | Real-time backend connection |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Google Cloud account with billing enabled
- Gemini API key

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/your-username/leksa.git
cd leksa
```

### 2️⃣ Set Up Environment Variables

```bash
cp .env.example .env
```

Fill in your `.env`:

```env
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_CLOUD_PROJECT=your_gcp_project_id
GCS_BUCKET_NAME=leksa-uploads
FIRESTORE_COLLECTION=sessions
```

### 3️⃣ Install Backend Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 4️⃣ Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 5️⃣ Run Locally

**Backend:**
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) 🎉

---

## ☁️ Deploy to Google Cloud

### Automated Deployment (Cloud Run)

```bash
# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Deploy backend
./scripts/deploy.sh
```

The `deploy.sh` script will:
- Build Docker image
- Push to Google Container Registry
- Deploy to Cloud Run
- Set environment variables automatically

### Manual Deployment

```bash
# Build and push Docker image
docker build -t gcr.io/YOUR_PROJECT_ID/leksa-backend .
docker push gcr.io/YOUR_PROJECT_ID/leksa-backend

# Deploy to Cloud Run
gcloud run deploy leksa-backend \
  --image gcr.io/YOUR_PROJECT_ID/leksa-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=your_key
```

---

## 📁 Project Structure

```
leksa/
├── backend/
│   ├── main.py                # FastAPI app entry point
│   ├── document_parser.py     # PDF & PPT text extraction
│   ├── lecture_planner.py     # Gemini Flash script generation
│   ├── live_session.py        # Gemini Live API handler
│   ├── firestore_manager.py   # Session state management
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── FileUpload.jsx
│   │   │   ├── AudioPlayer.jsx
│   │   │   └── MicInput.jsx
│   │   └── hooks/
│   │       └── useLiveSession.js
│   └── package.json
├── scripts/
│   └── deploy.sh              # Automated Cloud Run deployment
├── architecture/
│   └── diagram.png            # System architecture diagram
├── .env.example
└── README.md
```

---

## 🎯 Judging Criteria Alignment

| Criteria | How Leksa Delivers |
|----------|-------------------|
| **Beyond the Text Box (40%)** | Pure voice interaction — no typing needed. Real-time barge-in feels like talking to a real teacher |
| **Technical Implementation (30%)** | Gemini Live API + GenAI SDK + Cloud Run + Firestore — fully Google Cloud native |
| **Demo & Presentation (30%)** | Live demo shows real interruptions, real document parsing, real voice output |

---

## 👥 Team

| Name | Role |
|------|------|
| Your Name | Full Stack + AI Integration |
| Teammate Name | Frontend + Demo |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

- [Google Gemini Live API](https://ai.google.dev/gemini-api/docs/live) — the magic behind real-time voice
- [Google Cloud Run](https://cloud.google.com/run) — serverless backend hosting
- Built with ❤️ for the [Gemini Live Agent Challenge](https://geminiliveagentchallenge.devpost.com)

---

<p align="center">
  <strong>Leksa — Because every document deserves to be heard. 🎓</strong>
</p>
