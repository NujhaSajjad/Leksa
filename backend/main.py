# import os
# import uuid
# import asyncio
# from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# from contextlib import asynccontextmanager
# import logging
# from dotenv import load_dotenv
# load_dotenv()
# from document_parser import parse_document
# from lecture_planner import generate_lecture_script
# from live_session import LiveSessionManager
# from firestore_manager import FirestoreManager

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     logger.info("Leksa backend starting up...")
#     yield
#     logger.info("Leksa backend shutting down...")

# app = FastAPI(title="Leksa API", version="1.0.0", lifespan=lifespan)

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # production mein apna frontend URL dena
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# db = FirestoreManager()

# # ─── Health Check ────────────────────────────────
# @app.get("/health")
# async def health():
#     return {"status": "ok", "service": "leksa-backend"}

# # ─── Upload & Process Document ───────────────────
# @app.post("/api/upload")
# async def upload_document(file: UploadFile = File(...)):
#     """
#     1. File upload karo
#     2. Text extract karo (PDF / PPT / DOCX)
#     3. Gemini Flash se lecture script banao
#     4. Firestore mein save karo
#     5. session_id return karo
#     """
#     allowed = {
#         "application/pdf",
#         "application/vnd.openxmlformats-officedocument.presentationml.presentation",
#         "application/vnd.ms-powerpoint",
#         "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
#         "application/msword",
#     }

#     # extension se bhi check karo (some browsers send wrong mime)
#     ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
#     allowed_ext = {"pdf", "ppt", "pptx", "doc", "docx"}

#     if file.content_type not in allowed and ext not in allowed_ext:
#         raise HTTPException(status_code=400, detail="Sirf PDF, PPT, PPTX, DOC, DOCX allowed hain.")

#     try:
#         file_bytes = await file.read()
#         logger.info(f"File received: {file.filename} ({len(file_bytes)} bytes)")

#         # Step 1: Text extract
#         extracted = parse_document(file_bytes, file.filename)
#         if not extracted.strip():
#             raise HTTPException(status_code=422, detail="Document se koi text extract nahi hua.")

#         logger.info(f"Text extracted: {len(extracted)} characters")

#         # Step 2: Lecture script generate
#         segments = await generate_lecture_script(extracted, file.filename)
#         logger.info(f"Lecture script ready: {len(segments)} segments")

#         # Step 3: Firestore mein save
#         session_id = str(uuid.uuid4())
#         await db.create_session(session_id, {
#             "filename": file.filename,
#             "total_segments": len(segments),
#             "current_segment": 0,
#             "segments": segments,
#             "status": "ready",
#         })

#         return {
#             "session_id": session_id,
#             "filename": file.filename,
#             "total_segments": len(segments),
#             "preview": segments[0]["title"] if segments else "",
#         }

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Upload error: {e}")
#         raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


# # ─── Get Session Info ─────────────────────────────
# @app.get("/api/session/{session_id}")
# async def get_session(session_id: str):
#     session = await db.get_session(session_id)
#     if not session:
#         raise HTTPException(status_code=404, detail="Session nahi mili.")
#     # segments ka content wapas mat bhejo (heavy) — sirf metadata
#     return {
#         "session_id": session_id,
#         "filename": session.get("filename"),
#         "total_segments": session.get("total_segments"),
#         "current_segment": session.get("current_segment"),
#         "status": session.get("status"),
#     }


# # ─── WebSocket: Live Session ──────────────────────
# @app.websocket("/ws/live/{session_id}")
# async def websocket_live(websocket: WebSocket, session_id: str):
#     """
#     Frontend se WebSocket connection.
#     Flow:
#       1. Session data lo Firestore se
#       2. Gemini Live API se connect karo
#       3. Audio in/out stream karo frontend ke saath
#       4. Barge-in automatically handle hota hai Gemini Live se
#     """
#     await websocket.accept()
#     logger.info(f"WebSocket connected: session={session_id}")

#     session = await db.get_session(session_id)
#     if not session:
#         await websocket.send_json({"type": "error", "message": "Session nahi mili."})
#         await websocket.close()
#         return

#     manager = LiveSessionManager(
#         session_id=session_id,
#         session_data=session,
#         websocket=websocket,
#         db=db,
#     )

#     try:
#         await manager.run()
#     except WebSocketDisconnect:
#         logger.info(f"WebSocket disconnected: session={session_id}")
#     except Exception as e:
#         logger.error(f"WebSocket error: {e}")
#         try:
#             await websocket.send_json({"type": "error", "message": str(e)})
#         except:
#             pass
#     finally:
#         await manager.cleanup()
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