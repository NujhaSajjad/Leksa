
import os
import uuid
import asyncio
import logging
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from document_parser import parse_document
from live_session import LiveSessionManager
from firestore_manager import FirestoreManager

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Leksa backend starting up (Native Audio Mode)...")
    yield
    logger.info("Leksa backend shutting down...")

app = FastAPI(title="Leksa API", version="2.0.0 (Native)", lifespan=lifespan)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production mein frontend URL se replace karein
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = FirestoreManager()

# ─── Health Check ────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "leksa-native-backend"}

# ─── Upload & Process Document ───────────────────
@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    1. File upload aur validation.
    2. Text extraction (Native Context ke liye).
    3. Firestore mein raw context save karna (No pre-scripting to save quota).
    """
    allowed_ext = {"pdf", "ppt", "pptx", "doc", "docx"}
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail="Sirf PDF, PPTX, aur DOCX allowed hain.")

    try:
        file_bytes = await file.read()
        logger.info(f"File received: {file.filename} ({len(file_bytes)} bytes)")

        # Step 1: Text extraction
        extracted_text = parse_document(file_bytes, file.filename)
        if not extracted_text.strip():
            raise HTTPException(status_code=422, detail="Document khali hai ya read nahi ho saka.")

        logger.info(f"Context extracted: {len(extracted_text)} characters")

        # Step 2: Session creation
        # Hum 'extracted_text' ko save kar rahe hain taake LiveSessionManager isay use kar sake
        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "filename": file.filename,
            "extracted_text": extracted_text,
            "status": "ready",
            "created_at": str(asyncio.get_event_loop().time())
        }
        
        await db.create_session(session_id, session_data)

        return {
            "session_id": session_id,
            "filename": file.filename,
            "message": "Document processed successfully for Native Audio session."
        }

    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

# ─── Get Session Info ─────────────────────────────
@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nahi mili.")
    
    return {
        "session_id": session_id,
        "filename": session.get("filename"),
        "status": session.get("status"),
    }

# ─── WebSocket: Live Session ──────────────────────
@app.websocket("/ws/live/{session_id}")
async def websocket_live(websocket: WebSocket, session_id: str):
    """
    Native Audio WebSocket Bridge.
    Connects the user directly to Leksa's multimodal brain.
    """
    await websocket.accept()
    logger.info(f"WebSocket connected: session={session_id}")

    # Fetch session context from DB
    session = await db.get_session(session_id)
    if not session:
        await websocket.send_json({"type": "error", "message": "Session context missing."})
        await websocket.close()
        return

    # Initialize Native Audio Manager
    manager = LiveSessionManager(
        session_id=session_id,
        session_data=session, # Is mein 'extracted_text' maujood hai
        websocket=websocket,
        db=db,
    )

    try:
        await manager.run()
    except WebSocketDisconnect:
        logger.info(f"User disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error in {session_id}: {e}")
        try:
            await websocket.send_json({"type": "error", "message": "Connection lost."})
        except:
            pass
    finally:
        await manager.cleanup()