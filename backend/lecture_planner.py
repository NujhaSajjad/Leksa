import os
import json
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")


async def generate_lecture_script(extracted_text: str, filename: str) -> list[dict]:
    """
    Gemini Flash ko document text do.
    Returns: list of segments, har segment mein:
        {
            "index": 0,
            "title": "Introduction to Photosynthesis",
            "content": "Aaj hum photosynthesis ke baare mein padhenge...",
            "key_points": ["point 1", "point 2"],
            "comprehension_question": "Photosynthesis mein kya hota hai?"
        }
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY environment variable set nahi hai.")

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Document size ke hisaab se segment count decide karo
    char_count = len(extracted_text)
    if char_count < 2000:
        num_segments = 3
    elif char_count < 6000:
        num_segments = 5
    elif char_count < 15000:
        num_segments = 8
    else:
        num_segments = 12

    prompt = f"""
You are an expert teacher. I have a document called "{filename}".
Your job is to convert this document into a structured spoken lecture.

DOCUMENT CONTENT:
{extracted_text[:12000]}  

INSTRUCTIONS:
1. Split the document into exactly {num_segments} logical teaching segments.
2. Each segment should be 60-90 seconds when spoken aloud.
3. Write the content in natural, conversational spoken English — as if a real teacher is explaining.
4. Do NOT just read the document. Explain, elaborate, and make it engaging.
5. Each segment should flow naturally into the next.

Return ONLY a valid JSON array. No extra text. No markdown. No code blocks.
Format:
[
  {{
    "index": 0,
    "title": "Short title of this segment",
    "content": "Full spoken explanation for this segment. Write naturally, like talking to a student. 100-150 words.",
    "key_points": ["key point 1", "key point 2", "key point 3"],
    "comprehension_question": "A question to check if the student understood this segment."
  }}
]
"""

    logger.info(f"Generating lecture script for: {filename}")

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=8192,
        ),
    )

    raw = response.text.strip()

    # JSON parse karo safely
    try:
        # Agar model ne ```json ... ``` wrap kiya to strip karo
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        segments = json.loads(raw)

        # Validate karo
        if not isinstance(segments, list) or len(segments) == 0:
            raise ValueError("Empty segments list")

        for i, seg in enumerate(segments):
            seg["index"] = i  # index ensure karo

        logger.info(f"Script generated: {len(segments)} segments")
        return segments

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"JSON parse error: {e}\nRaw response: {raw[:500]}")
        # Fallback: single segment banao
        return [{
            "index": 0,
            "title": f"Lecture: {filename}",
            "content": extracted_text[:1000],
            "key_points": [],
            "comprehension_question": "Kya aapko ye samajh aaya?",
        }]
