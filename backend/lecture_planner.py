
import os
import json
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

async def generate_lecture_script(extracted_text: str, filename: str) -> list[dict]:
    """
    Gemini 2.0 Flash use kar ke lecture script generate karna.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY environment variable set nahi hai.")

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Token management taake 429 error na aaye
    truncated_text = extracted_text[:12000] 
    char_count = len(truncated_text)
    
    # Decide number of segments
    num_segments = 4 if char_count < 5000 else 6

    prompt = f"""
    You are Leksa's core brain. Convert this document "{filename}" into a lecture script.
    
    DOCUMENT CONTENT:
    {truncated_text}

    INSTRUCTIONS:
    1. Create exactly {num_segments} teaching segments.
    2. Tone: Helpful, expert teacher, engaging.
    3. Return ONLY a JSON array. No markdown, no ```json tags.
    
    Format:
    [
      {{
        "title": "Segment Title",
        "content": "Spoken explanation (100 words)",
        "key_points": ["point 1", "point 2"],
        "comprehension_question": "One question for the student"
      }}
    ]
    """

    logger.info(f"Generating lecture script for: {filename} (chars sent: {len(truncated_text)})")

    try:
        # Use Gemini 2.0 Flash directly
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                response_mime_type="application/json",
            ),
        )
        
        # Parsed response handle karna
        segments = response.parsed
        
        if not isinstance(segments, list):
            if isinstance(segments, dict) and "segments" in segments:
                segments = segments["segments"]
            else:
                raise ValueError("Response is not a list")

        for i, seg in enumerate(segments):
            seg["index"] = i
            
        logger.info(f"Successfully generated {len(segments)} segments.")
        return segments

    except Exception as e:
        logger.error(f"Generation failed: {str(e)}")
        # Fallback taake frontend crash na ho
        return [{
            "index": 0,
            "title": "Introduction",
            "content": "Welcome! Let's start by discussing the main concepts of this document.",
            "key_points": ["Overview"],
            "comprehension_question": "Shall we proceed?"
        }]