# import os
# import asyncio
# import json
# import logging
# import base64
# from fastapi import WebSocket
# from google import genai
# from google.genai import types

# logger = logging.getLogger(__name__)

# GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY")
# LIVE_MODEL      = "gemini-2.0-flash-live-001"
# SAMPLE_RATE     = 24000   # Gemini Live output sample rate (Hz)
# CHUNK_SIZE      = 1024    # audio bytes per chunk


# class LiveSessionManager:
#     """
#     Frontend WebSocket  ↔  Gemini Live API bridge.

#     Frontend se messages:
#         { "type": "audio",    "data": "<base64 PCM>" }   # mic audio
#         { "type": "next" }                                # next segment jao
#         { "type": "pause" }                               # pause karo
#         { "type": "resume" }                              # resume karo
#         { "type": "end" }                                 # session khatam karo

#     Frontend ko messages:
#         { "type": "audio",       "data": "<base64 PCM>" }  # AI voice
#         { "type": "transcript",  "text": "..." }            # AI ka text
#         { "type": "segment",     "index": 0, "title": "..." }
#         { "type": "status",      "status": "speaking"|"listening"|"idle" }
#         { "type": "done" }                                  # lecture khatam
#         { "type": "error",       "message": "..." }
#     """

#     def __init__(self, session_id: str, session_data: dict, websocket: WebSocket, db):
#         self.session_id   = session_id
#         self.session_data = session_data
#         self.websocket    = websocket
#         self.db           = db

#         self.segments        = session_data.get("segments", [])
#         self.current_index   = session_data.get("current_segment", 0)
#         self.total_segments  = len(self.segments)

#         self.gemini_session  = None
#         self.client          = None
#         self._running        = False

#     # ─── Main run loop ────────────────────────────
#     async def run(self):
#         if not GEMINI_API_KEY:
#             await self._send({"type": "error", "message": "GEMINI_API_KEY missing."})
#             return

#         if not self.segments:
#             await self._send({"type": "error", "message": "No segments found."})
#             return

#         self.client  = genai.Client(api_key=GEMINI_API_KEY)
#         self._running = True

#         # System prompt — teacher persona + full lecture plan
#         system_prompt = self._build_system_prompt()

#         config = types.LiveConnectConfig(
#             response_modalities=["AUDIO"],
#             system_instruction=system_prompt,
#             speech_config=types.SpeechConfig(
#                 voice_config=types.VoiceConfig(
#                     prebuilt_voice_config=types.PrebuiltVoiceConfig(
#                         voice_name="Charon"   # natural, clear voice
#                     )
#                 )
#             ),
#         )

#         logger.info(f"Connecting to Gemini Live: session={self.session_id}")

#         async with self.client.aio.live.connect(
#             model=LIVE_MODEL, config=config
#         ) as session:
#             self.gemini_session = session

#             # Pehla segment shuru karo
#             await self._start_segment(self.current_index)

#             # Frontend aur Gemini se messages parallel handle karo
#             await asyncio.gather(
#                 self._receive_from_frontend(),
#                 self._receive_from_gemini(),
#             )

#     # ─── System prompt ────────────────────────────
#     def _build_system_prompt(self) -> str:
#         segments_summary = "\n".join(
#             f"  Segment {s['index']+1}: {s['title']}" for s in self.segments
#         )

#         return f"""You are Leksa, an expert AI teacher. Your job is to teach the student the content from their uploaded document through natural spoken conversation.

# LECTURE PLAN ({self.total_segments} segments):
# {segments_summary}

# TEACHING RULES:
# 1. Speak naturally and conversationally — like a real teacher, not a robot reading text.
# 2. When the student interrupts or asks a question, STOP immediately and answer them clearly.
# 3. After answering, say "Now, where were we..." and continue from where you left off.
# 4. Keep your tone warm, encouraging, and patient.
# 5. If the student seems confused, re-explain using a simpler analogy or example.
# 6. After each segment, ask the comprehension question naturally.
# 7. Wait for the student's response before moving to the next segment.
# 8. If the student says "next", "continue", or "aage", move to the next segment.

# IMPORTANT: You will receive the content of each segment one at a time. Focus only on teaching that segment before moving forward.
# """

#     # ─── Start a segment ──────────────────────────
#     async def _start_segment(self, index: int):
#         if index >= self.total_segments:
#             await self._send({"type": "done"})
#             await self._send({"type": "status", "status": "idle"})
#             return

#         seg = self.segments[index]
#         logger.info(f"Starting segment {index+1}/{self.total_segments}: {seg['title']}")

#         # Frontend ko segment info bhejo
#         await self._send({
#             "type":   "segment",
#             "index":  index,
#             "title":  seg["title"],
#             "key_points": seg.get("key_points", []),
#         })
#         await self._send({"type": "status", "status": "speaking"})

#         # Gemini ko is segment ka content do aur bolne kaho
#         teaching_prompt = f"""
# Now teach Segment {index+1}: "{seg['title']}"

# Content to teach:
# {seg['content']}

# Key points to cover:
# {chr(10).join(f"- {kp}" for kp in seg.get("key_points", []))}

# After finishing this explanation, ask this question naturally:
# "{seg.get('comprehension_question', 'Kya ye samajh aaya?')}"
# """
#         await self.gemini_session.send(
#             input=teaching_prompt,
#             end_of_turn=True,
#         )

#         # Firestore mein current segment update karo
#         await self.db.update_session(self.session_id, {
#             "current_segment": index,
#             "status": "active",
#         })
#         self.current_index = index

#     # ─── Receive from frontend ────────────────────
#     async def _receive_from_frontend(self):
#         try:
#             while self._running:
#                 raw = await self.websocket.receive_text()
#                 msg = json.loads(raw)
#                 msg_type = msg.get("type")

#                 if msg_type == "audio":
#                     # User ka mic audio → Gemini ko bhejo (barge-in handle hoga automatically)
#                     audio_bytes = base64.b64decode(msg["data"])
#                     await self.gemini_session.send(
#                         input=types.LiveClientRealtimeInput(
#                             media_chunks=[
#                                 types.Blob(
#                                     data=audio_bytes,
#                                     mime_type=f"audio/pcm;rate={SAMPLE_RATE}",
#                                 )
#                             ]
#                         )
#                     )
#                     await self._send({"type": "status", "status": "listening"})

#                 elif msg_type == "next":
#                     # User ne next segment manga
#                     await self._start_segment(self.current_index + 1)

#                 elif msg_type == "pause":
#                     await self._send({"type": "status", "status": "idle"})

#                 elif msg_type == "resume":
#                     await self.gemini_session.send(
#                         input="Please continue the lecture from where you left off.",
#                         end_of_turn=True,
#                     )
#                     await self._send({"type": "status", "status": "speaking"})

#                 elif msg_type == "end":
#                     self._running = False
#                     break

#         except Exception as e:
#             logger.error(f"Frontend receive error: {e}")
#             self._running = False

#     # ─── Receive from Gemini ──────────────────────
#     async def _receive_from_gemini(self):
#         try:
#             while self._running:
#                 async for response in self.gemini_session.receive():

#                     # Audio data → frontend ko bhejo
#                     if (
#                         hasattr(response, "data")
#                         and response.data
#                     ):
#                         audio_b64 = base64.b64encode(response.data).decode("utf-8")
#                         await self._send({"type": "audio", "data": audio_b64})
#                         await self._send({"type": "status", "status": "speaking"})

#                     # Text transcript → frontend ko bhejo
#                     if (
#                         hasattr(response, "text")
#                         and response.text
#                     ):
#                         await self._send({"type": "transcript", "text": response.text})

#                     # Turn complete → listening state
#                     if (
#                         hasattr(response, "server_content")
#                         and response.server_content
#                         and hasattr(response.server_content, "turn_complete")
#                         and response.server_content.turn_complete
#                     ):
#                         await self._send({"type": "status", "status": "listening"})

#         except Exception as e:
#             logger.error(f"Gemini receive error: {e}")
#             self._running = False

#     # ─── Helpers ──────────────────────────────────
#     async def _send(self, data: dict):
#         try:
#             await self.websocket.send_json(data)
#         except Exception as e:
#             logger.warning(f"Send error: {e}")

#     async def cleanup(self):
#         self._running = False
#         try:
#             await self.db.update_session(self.session_id, {"status": "ended"})
#         except:
#             pass
#         logger.info(f"Session cleaned up: {self.session_id}")



import os
import asyncio
import json
import logging
import base64
from fastapi import WebSocket
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Environment Variables
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# Native Audio Preview Model (Experimental)
LIVE_MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"
class LiveSessionManager:
    """
    Leksa Native Audio Manager.
    Directly feeds document context into the live multimodal stream.
    """

    def __init__(self, session_id: str, session_data: dict, websocket: WebSocket, db):
        self.session_id = session_id
        self.session_data = session_data  # Is mein ab poora 'extracted_text' hoga
        self.websocket = websocket
        self.db = db

        self.client = None
        self.gemini_session = None
        self._running = False

    async def run(self):
        if not GEMINI_API_KEY:
            await self._send({"type": "error", "message": "API Key missing!"})
            return

        # Initialize Client without explicit version to avoid 1008 errors
        self.client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1alpha'})
        self._running = True

        # System Instruction: Leksa as a Native Audio Teacher
        # Hum poora document yahan context mein bhej rahe hain
        doc_text = self.session_data.get("extracted_text", "No document content found.")
        
        system_prompt = f"""
        You are Leksa, an expert AI Teacher. 
        You have NATIVE AUDIO capabilities. You can hear emotions and speak naturally.
        
        CONTEXT DOCUMENT:
        {doc_text[:15000]} 

        INSTRUCTIONS:
        1. Start by greeting the student and briefly mentioning what the document is about.
        2. Teach the document topic by topic.
        3. Since you are in a LIVE session, keep your explanations concise (30-45 seconds max at a time).
        4. After every explanation, ask a follow-up question to ensure the student is following.
        5. If the student interrupts, stop and answer their query.
        6. Use a warm, friendly tone. You can use occasional filler words like 'Right?' or 'Theek hai?' to sound human.
        """

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"], # Forces Native Audio output
            system_instruction=types.Content(
                parts=[types.Part(text=system_prompt)]
            ),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Charon" # Best voice for teaching persona
                    )
                )
            ),
        )

        logger.info(f"Starting Native Audio Session: {self.session_id}")

        try:
            async with self.client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
                self.gemini_session = session
                
                # Initial trigger to start the conversation
                await self.gemini_session.send(input="Hello Leksa, I am ready to learn. Please start the lesson.", end_of_turn=True)

                # Parallel processing for Frontend and Gemini
                await asyncio.gather(
                    self._receive_from_frontend(),
                    self._receive_from_gemini(),
                )
        except Exception as e:
            logger.error(f"Native Audio Connection Error: {e}")
            await self._send({"type": "error", "message": str(e)})
        finally:
            await self.cleanup()

    async def _receive_from_frontend(self):
        """Receive Mic audio or Text commands from user's browser."""
        try:
            while self._running:
                raw = await self.websocket.receive_text()
                msg = json.loads(raw)
                msg_type = msg.get("type")

                if msg_type == "audio":
                    # Raw PCM 16-bit 24kHz audio from frontend
                    audio_data = base64.b64decode(msg["data"])
                    await self.gemini_session.send(
                        input=types.LiveClientRealtimeInput(
                            media_chunks=[types.Blob(data=audio_data, mime_type="audio/pcm;rate=24000")]
                        )
                    )
                elif msg_type == "end":
                    self._running = False
        except Exception as e:
            logger.error(f"Frontend bridge error: {e}")
            self._running = False

    async def _receive_from_gemini(self):
        """Handle Native Audio and Transcripts coming FROM Gemini."""
        try:
            while self._running:
                async for response in self.gemini_session.receive():
                    # 1. Native Audio Chunk
                    if response.data:
                        audio_b64 = base64.b64encode(response.data).decode("utf-8")
                        await self._send({"type": "audio", "data": audio_b64})

                    # 2. Text Transcript (for UI captions)
                    if response.text:
                        await self._send({"type": "transcript", "text": response.text})

                    # 3. Server Status
                    if response.server_content and response.server_content.turn_complete:
                        await self._send({"type": "status", "status": "listening"})
        except Exception as e:
            logger.error(f"Gemini Native stream error: {e}")
            self._running = False

    async def _send(self, data: dict):
        try:
            await self.websocket.send_json(data)
        except:
            pass

    async def cleanup(self):
        self._running = False
        if self.db:
            await self.db.update_session(self.session_id, {"status": "completed"})
        logger.info(f"Native Session {self.session_id} ended.")