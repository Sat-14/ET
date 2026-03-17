"""WhatsApp Business API Integration.

Handles:
- Sending messages via WhatsApp Cloud API
- Receiving webhook events
- Template message support for proactive nudges
"""

from __future__ import annotations

import os
import httpx
from typing import Optional


WHATSAPP_API_URL = "https://graph.facebook.com/v18.0"


class WhatsAppClient:
    """Client for WhatsApp Business Cloud API."""

    def __init__(
        self,
        token: Optional[str] = None,
        phone_number_id: Optional[str] = None,
    ):
        self.token = token or os.environ.get("WHATSAPP_TOKEN", "")
        self.phone_number_id = phone_number_id or os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
        self.base_url = f"{WHATSAPP_API_URL}/{self.phone_number_id}/messages"

    @property
    def headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def send_text_message(self, to: str, text: str) -> dict:
        """Send a text message to a WhatsApp number.

        Args:
            to: Recipient phone number with country code (e.g., "919876543210")
            text: Message text (max 4096 characters)
        """
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text[:4096]},
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                json=payload,
                headers=self.headers,
            )
            return response.json()

    async def send_template_message(
        self,
        to: str,
        template_name: str,
        language_code: str = "en",
        parameters: Optional[list[str]] = None,
    ) -> dict:
        """Send a template message (for proactive nudges).

        Template messages must be pre-approved by Meta.
        """
        components = []
        if parameters:
            components.append({
                "type": "body",
                "parameters": [
                    {"type": "text", "text": p} for p in parameters
                ],
            })

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components,
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                json=payload,
                headers=self.headers,
            )
            return response.json()

    async def send_interactive_buttons(
        self,
        to: str,
        body_text: str,
        buttons: list[dict],
    ) -> dict:
        """Send an interactive message with buttons.

        Args:
            buttons: List of {"id": "btn_1", "title": "Option 1"} (max 3)
        """
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {"id": btn["id"], "title": btn["title"][:20]},
                        }
                        for btn in buttons[:3]
                    ]
                },
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                json=payload,
                headers=self.headers,
            )
            return response.json()

    @staticmethod
    def parse_webhook_message(payload: dict) -> Optional[dict]:
        """Parse incoming webhook payload and extract message details.

        Returns dict with: sender, message_text, message_type, timestamp
        Or None if payload doesn't contain a user message.
        """
        try:
            entry = payload.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])

            if not messages:
                return None

            msg = messages[0]
            return {
                "sender": msg.get("from", ""),
                "message_id": msg.get("id", ""),
                "timestamp": msg.get("timestamp", ""),
                "message_type": msg.get("type", "text"),
                "message_text": msg.get("text", {}).get("body", ""),
                "button_reply": msg.get("interactive", {}).get("button_reply", {}),
            }
        except (IndexError, KeyError):
            return None

    @staticmethod
    def verify_webhook(params: dict, verify_token: str) -> Optional[str]:
        """Verify webhook subscription from Meta.

        Returns the challenge string if verification succeeds, None otherwise.
        """
        mode = params.get("hub.mode")
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")

        if mode == "subscribe" and token == verify_token:
            return challenge
        return None
