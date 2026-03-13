import os
import logging

logger = logging.getLogger(__name__)

# Firestore available hai ya nahi
_USE_FIRESTORE = os.environ.get("USE_FIRESTORE", "true").lower() == "true"


class FirestoreManager:
    """
    Session state manage karo.
    - Production: Google Cloud Firestore
    - Local dev:  in-memory dict (Firestore ke bina bhi kaam kare)
    """

    def __init__(self):
        self._local_store: dict = {}  # fallback for local dev
        self._db = None

        if _USE_FIRESTORE:
            try:
                from google.cloud import firestore
                project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
                self._db = firestore.AsyncClient(project=project_id)
                logger.info("Firestore connected.")
            except Exception as e:
                logger.warning(f"Firestore unavailable, using in-memory store. Error: {e}")
                self._db = None
        else:
            logger.info("Using in-memory store (USE_FIRESTORE=false).")

    # ─── Create ───────────────────────────────────
    async def create_session(self, session_id: str, data: dict):
        if self._db:
            await self._db.collection("sessions").document(session_id).set(data)
        else:
            self._local_store[session_id] = dict(data)
        logger.info(f"Session created: {session_id}")

    # ─── Read ─────────────────────────────────────
    async def get_session(self, session_id: str) -> dict | None:
        if self._db:
            doc = await self._db.collection("sessions").document(session_id).get()
            return doc.to_dict() if doc.exists else None
        else:
            return self._local_store.get(session_id)

    # ─── Update ───────────────────────────────────
    async def update_session(self, session_id: str, updates: dict):
        if self._db:
            await self._db.collection("sessions").document(session_id).update(updates)
        else:
            if session_id in self._local_store:
                self._local_store[session_id].update(updates)
        logger.debug(f"Session updated: {session_id} → {updates}")

    # ─── Delete ───────────────────────────────────
    async def delete_session(self, session_id: str):
        if self._db:
            await self._db.collection("sessions").document(session_id).delete()
        else:
            self._local_store.pop(session_id, None)
        logger.info(f"Session deleted: {session_id}")
