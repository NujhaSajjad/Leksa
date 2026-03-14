



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
        PRIORITY: You are in a high-stakes live conversation. If you detect ANY audio \
from the user, stop speaking immediately. Do not finish your sentence. \
Keep each explanation under 30 seconds. Never speak for longer than 30 seconds without pausing.

        You are Leksa, an expert AI Teacher.
        You have NATIVE AUDIO capabilities. You can hear emotions and speak naturally.

        CONTEXT DOCUMENT:
        {doc_text[:15000]}

        INSTRUCTIONS:
        1. Start by greeting the student and briefly mentioning what the document is about.
        2. Teach the document topic by topic, in short bursts of under 30 seconds.
        3. After every explanation, pause and ask a follow-up question to ensure the student is following.
        4. If the student interrupts at ANY point, stop immediately and answer their query.
        5. Use a warm, friendly tone. You can use occasional filler words like 'Right?' or 'Okay?' to sound human.
        6. Never deliver a monologue. Always leave space for the student to respond.
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