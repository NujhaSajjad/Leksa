



# import os
# import asyncio
# import json
# import logging
# import base64
# from fastapi import WebSocket
# from google import genai
# from google.genai import types

# logger = logging.getLogger(__name__)

# # Environment Variables
# GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# # Native Audio Preview Model (Experimental)
# LIVE_MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"
# class LiveSessionManager:
#     """
#     Leksa Native Audio Manager.
#     Directly feeds document context into the live multimodal stream.
#     """

#     def __init__(self, session_id: str, session_data: dict, websocket: WebSocket, db):
#         self.session_id = session_id
#         self.session_data = session_data  # Is mein ab poora 'extracted_text' hoga
#         self.websocket = websocket
#         self.db = db

#         self.client = None
#         self.gemini_session = None
#         self._running = False

#     async def run(self):
#         if not GEMINI_API_KEY:
#             await self._send({"type": "error", "message": "API Key missing!"})
#             return

#         # Initialize Client without explicit version to avoid 1008 errors
#         self.client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1alpha'})
#         self._running = True

#         # System Instruction: Leksa as a Native Audio Teacher
#         # Hum poora document yahan context mein bhej rahe hain
#         doc_text = self.session_data.get("extracted_text", "No document content found.")
        
#         system_prompt = f"""
#         PRIORITY: You are in a high-stakes live conversation. If you detect ANY audio \
# from the user, stop speaking immediately. Do not finish your sentence. \
# Keep each explanation under 30 seconds. Never speak for longer than 30 seconds without pausing.

#         You are Leksa, an expert AI Teacher.
#         You have NATIVE AUDIO capabilities. You can hear emotions and speak naturally.

#         CONTEXT DOCUMENT:
#         {doc_text[:15000]}

#         INSTRUCTIONS:
#         1. Start by greeting the student and briefly mentioning what the document is about.
#         2. Teach the document topic by topic, in short bursts of under 30 seconds.
#         3. After every explanation, pause and ask a follow-up question to ensure the student is following.
#         4. If the student interrupts at ANY point, stop immediately and answer their query.
#         5. Use a warm, friendly tone. You can use occasional filler words like 'Right?' or 'Okay?' to sound human.
#         6. Never deliver a monologue. Always leave space for the student to respond.
#         """

#         config = types.LiveConnectConfig(
#             response_modalities=["AUDIO"], # Forces Native Audio output
#             system_instruction=types.Content(
#                 parts=[types.Part(text=system_prompt)]
#             ),
#             speech_config=types.SpeechConfig(
#                 voice_config=types.VoiceConfig(
#                     prebuilt_voice_config=types.PrebuiltVoiceConfig(
#                         voice_name="Charon" # Best voice for teaching persona
#                     )
#                 )
#             ),
#         )

#         logger.info(f"Starting Native Audio Session: {self.session_id}")

#         try:
#             async with self.client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
#                 self.gemini_session = session
                
#                 # Initial trigger to start the conversation
#                 await self.gemini_session.send(input="Hello Leksa, I am ready to learn. Please start the lesson.", end_of_turn=True)

#                 # Parallel processing for Frontend and Gemini
#                 await asyncio.gather(
#                     self._receive_from_frontend(),
#                     self._receive_from_gemini(),
#                 )
#         except Exception as e:
#             logger.error(f"Native Audio Connection Error: {e}")
#             await self._send({"type": "error", "message": str(e)})
#         finally:
#             await self.cleanup()

#     async def _receive_from_frontend(self):
#         try:
#             while self._running:
#                 raw = await self.websocket.receive_text()
#                 msg = json.loads(raw)
#                 msg_type = msg.get("type")

#                 if msg_type == "audio":
#                     audio_data = base64.b64decode(msg["data"])
#                     await self.gemini_session.send(
#                         input=types.LiveClientRealtimeInput(
#                             media_chunks=[types.Blob(data=audio_data, mime_type="audio/pcm;rate=24000")]
#                         )
#                     )

#                 elif msg_type == "interrupt":
#                     # Barge-in: user bolna shuru kiya — Gemini ki generation rok do
#                     await self.gemini_session.send(
#                         input=types.LiveClientRealtimeInput(
#                             activity_start=types.ActivityStart()
#                         )
#                     )
#                     logger.info("Barge-in ActivityStart sent — Gemini generation stopped")

#                 elif msg_type == "speech_end":
#                     # User ruk gaya — Gemini ko respond karne ka signal do
#                     await self.gemini_session.send(
#                         input=types.LiveClientRealtimeInput(
#                             activity_end=types.ActivityEnd()
#                         )
#                     )
#                     logger.info("ActivityEnd sent — Gemini respond karega")

#                 elif msg_type == "turn_end":
#                     # Sirf end_of_turn — koi fake text nahi
#                     await self.gemini_session.send(end_of_turn=True)
#                     logger.info("Turn end sent to Gemini")

#                 elif msg_type == "end":
#                     self._running = False
#         except Exception as e:
#             logger.error(f"Frontend bridge error: {e}")
#             self._running = False

# async def _receive_from_gemini(self):
#         try:
#             is_interrupted = False  # ← interrupt state track karo

#             async for response in self.gemini_session.receive():
#                 if not self._running:
#                     break

#                 # PRIORITY 1: Interruption event — turant flush karo
#                 if response.server_content and response.server_content.interrupted:
#                     is_interrupted = True
#                     logger.info("Gemini interrupted — suppressing stale audio")
#                     # Frontend ko batao ke audio flush kare
#                     await self._send({"type": "flush"})
#                     continue

#                 # PRIORITY 2: Turn complete — interrupted state reset karo
#                 if response.server_content and response.server_content.turn_complete:
#                     is_interrupted = False  # ← ab nayi content allow hai
#                     await self._send({"type": "status", "status": "listening"})
#                     logger.info("Turn complete — ready for next input")
#                     continue

#                 # PRIORITY 3: Interrupted hai to stale content skip karo
#                 if is_interrupted:
#                     logger.info("Suppressed stale content after interrupt")
#                     continue

#                 # PRIORITY 4: Normal audio aur transcript
#                 if response.data:
#                     audio_b64 = base64.b64encode(response.data).decode("utf-8")
#                     await self._send({"type": "audio", "data": audio_b64})

#                 if response.text:
#                     await self._send({"type": "transcript", "text": response.text})

#         except Exception as e:
#             logger.error(f"Gemini Native stream error: {e}")
#             self._running = False

#         async def _send(self, data: dict):
#             try:
#                 await self.websocket.send_json(data)
#             except:
#                 pass

#         async def cleanup(self):
#             self._running = False
#             if self.db:
#                await self.db.update_session(self.session_id, {"status": "completed"})
#             logger.info(f"Native Session {self.session_id} ended.")


import os
import asyncio
import json
import logging
import base64
import re
from fastapi import WebSocket
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Environment Variables
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# Native Audio Preview Model (Experimental)
LIVE_MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"


# ─── Segment detector ─────────────────────────────────────────────────────────
# Gemini ke responses mein patterns dhundo aur key points extract karo.
# Jab Leksa naya topic start kare, frontend ko "segment" message bhejo.

TOPIC_MARKERS = [
    r"(?i)\blet'?s (now |)talk about\b",
    r"(?i)\bmoving on to\b",
    r"(?i)\bnext[, ] (we|let'?s|I'?ll)\b",
    r"(?i)\bnow[, ] (let'?s |)discuss\b",
    r"(?i)\btoday we'?ll? (cover|learn|look at)\b",
    r"(?i)\bfirst[,.]? (let'?s |)(talk|discuss|cover|look)\b",
    r"(?i)\bsecond(ly)?[,.]?\b",
    r"(?i)\bthird(ly)?[,.]?\b",
    r"(?i)\bin (this|our) (next|first|second|third) (segment|section|part|topic)\b",
]

_TOPIC_RE = re.compile("|".join(TOPIC_MARKERS))


def _detect_segment_change(text: str) -> bool:
    """Kya ye text naye segment ki shuruat lag rahi hai?"""
    return bool(_TOPIC_RE.search(text or ""))


def _extract_key_points(text: str) -> list[str]:
    """
    Text se bullet-point style key points nikalo.
    Simple heuristic: sentences jo facts/definitions/concepts contain karte hain.
    """
    if not text:
        return []

    # Pehle numbered / bulleted lines dhundo
    lines = text.split("\n")
    bullet_points = []
    for line in lines:
        line = line.strip()
        # "1. xyz" ya "- xyz" ya "• xyz" pattern
        m = re.match(r'^[\d]+[.)]\s+(.+)$|^[-•*]\s+(.+)$', line)
        if m:
            point = (m.group(1) or m.group(2) or "").strip()
            if len(point) > 10:
                bullet_points.append(point)

    if bullet_points:
        return bullet_points[:5]

    # Fallback: important sentences (definitions, facts)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    key = []
    for s in sentences:
        s = s.strip()
        if len(s) < 20 or len(s) > 200:
            continue
        # Definition / important fact patterns
        if re.search(r'(?i)\b(is|are|means|refers to|defined as|known as|called|stands for)\b', s):
            key.append(s)
        elif re.search(r'(?i)\b(important|key|main|primary|critical|essential|must|should|always)\b', s):
            key.append(s)
        if len(key) >= 4:
            break

    # Agar kuch nahi mila toh first 3 sentences
    if not key:
        key = [s.strip() for s in sentences[:3] if len(s.strip()) > 15]

    return key[:5]


class LiveSessionManager:
    """
    Leksa Native Audio Manager.
    Directly feeds document context into the live multimodal stream.
    Sends: audio, transcript, user_transcript, segment, status, done, error
    """

    def __init__(self, session_id: str, session_data: dict, websocket: WebSocket, db):
        self.session_id = session_id
        self.session_data = session_data
        self.websocket = websocket
        self.db = db

        self.client = None
        self.gemini_session = None
        self._running = False

        # Segment tracking
        self._segment_index = 0
        self._full_transcript_buffer = ""  # Leksa ki poori conversation

    async def run(self):
        if not GEMINI_API_KEY:
            await self._send({"type": "error", "message": "API Key missing!"})
            return

        self.client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1alpha'})
        self._running = True

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
        3. Clearly announce each new topic with a phrase like "Now let's talk about..." or "Moving on to...".
        4. After every explanation, pause and ask a follow-up question to ensure the student is following.
        5. If the student interrupts at ANY point, stop immediately and answer their query.
        6. Use a warm, friendly tone. You can use occasional filler words like 'Right?' or 'Okay?' to sound human.
        7. Never deliver a monologue. Always leave space for the student to respond.
        8. When listing key facts, use numbered points: "First... Second... Third..."
        """

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(
                parts=[types.Part(text=system_prompt)]
            ),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Charon"
                    )
                )
            ),
        )

        logger.info(f"Starting Native Audio Session: {self.session_id}")

        try:
            async with self.client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
                self.gemini_session = session

                await self.gemini_session.send(
                    input="Hello Leksa, I am ready to learn. Please start the lesson.",
                    end_of_turn=True
                )

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
        try:
            while self._running:
                raw = await self.websocket.receive_text()
                msg = json.loads(raw)
                msg_type = msg.get("type")

                if msg_type == "audio":
                    audio_data = base64.b64decode(msg["data"])
                    await self.gemini_session.send(
                        input=types.LiveClientRealtimeInput(
                            media_chunks=[types.Blob(data=audio_data, mime_type="audio/pcm;rate=24000")]
                        )
                    )
                elif msg_type == "turn_end":
                    await self.gemini_session.send(input=".", end_of_turn=True)
                    logger.info("Turn end signal sent to Gemini")
                elif msg_type == "end":
                    self._running = False
        except Exception as e:
            logger.error(f"Frontend bridge error: {e}")
            self._running = False

    async def _receive_from_gemini(self):
        """
        Handle Native Audio, Transcripts, and Segment detection FROM Gemini.
        Messages sent to frontend:
          - audio       : PCM audio chunk
          - transcript  : Leksa ki latest spoken text (live subtitle)
          - segment     : Naya topic detect hua, key points ke saath
          - status      : speaking / listening
          - done        : lecture khatam
        """
        try:
            # Running text buffer for current turn
            turn_text_buffer = ""

            while self._running:
                async for response in self.gemini_session.receive():

                    # ── 1. Audio chunk ────────────────────────────
                    if response.data:
                        audio_b64 = base64.b64encode(response.data).decode("utf-8")
                        await self._send({"type": "audio", "data": audio_b64})

                    # ── 2. Text transcript (from Gemini) ──────────
                    if response.text:
                        text = response.text
                        turn_text_buffer += " " + text
                        self._full_transcript_buffer += " " + text

                        # Live subtitle — send immediately
                        await self._send({"type": "transcript", "text": text.strip()})

                        # Segment change detection
                        if _detect_segment_change(text):
                            await self._send_segment(text, turn_text_buffer)
                            turn_text_buffer = ""  # reset for new segment

                    # ── 3. Turn complete ──────────────────────────
                    if response.server_content and response.server_content.turn_complete:
                        # If turn ended with unsent text, send segment update
                        if turn_text_buffer.strip():
                            # Only send if we have key content (>30 chars)
                            if len(turn_text_buffer.strip()) > 30:
                                await self._send_segment(
                                    turn_text_buffer,
                                    turn_text_buffer,
                                    force=False,  # don't bump index unless detected
                                )
                            turn_text_buffer = ""

                        await self._send({"type": "status", "status": "listening"})

        except Exception as e:
            logger.error(f"Gemini Native stream error: {e}")
            self._running = False

    async def _send_segment(self, trigger_text: str, full_text: str, force: bool = True):
        """
        Segment message frontend ko bhejo.
        force=True  → segment index badao (naya topic)
        force=False → same index, sirf key points update karo
        """
        if force:
            self._segment_index += 1

        key_points = _extract_key_points(full_text)

        # Title: first non-trivial sentence ya "Topic N"
        title = self._extract_title(trigger_text) or f"Topic {self._segment_index + 1}"

        await self._send({
            "type": "segment",
            "index": self._segment_index,
            "title": title,
            "key_points": key_points,
        })
        logger.info(f"Segment {self._segment_index} sent: '{title}' with {len(key_points)} key points")

    def _extract_title(self, text: str) -> str:
        """Text ki pehli meaningful sentence nikalo title ke liye."""
        if not text:
            return ""
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        for s in sentences:
            s = s.strip()
            # Greetings skip karo
            if re.match(r'(?i)^(hello|hi|okay|alright|great|sure|now|so)[,!.]?\s*$', s):
                continue
            if 8 < len(s) < 80:
                # Remove "Let's talk about" prefix to get clean title
                clean = re.sub(r'(?i)^(now\s+)?(let\'?s\s+)?(talk about|discuss|cover|look at|move to)\s+', '', s)
                return clean.strip().rstrip('.')
        return ""

    async def _send(self, data: dict):
        try:
            await self.websocket.send_json(data)
        except Exception:
            pass

    async def cleanup(self):
        self._running = False
        if self.db:
            await self.db.update_session(self.session_id, {"status": "completed"})
        logger.info(f"Native Session {self.session_id} ended.")