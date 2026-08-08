"""Typed views over LINE webhook events.

The raw event dict is what gets persisted (inbox.event_json) so nothing is
lost; these models are parsed views used for routing and handling.
"""

import json

from pydantic import BaseModel, ConfigDict, Field


class LineSource(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: str = "user"
    user_id: str | None = Field(default=None, alias="userId")
    group_id: str | None = Field(default=None, alias="groupId")
    room_id: str | None = Field(default=None, alias="roomId")


class LineMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str
    text: str | None = None
    file_name: str | None = Field(default=None, alias="fileName")
    file_size: int | None = Field(default=None, alias="fileSize")
    duration: int | None = None


class DeliveryContext(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    is_redelivery: bool = Field(default=False, alias="isRedelivery")


class LineEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: str
    webhook_event_id: str | None = Field(default=None, alias="webhookEventId")
    delivery_context: DeliveryContext = Field(
        default_factory=DeliveryContext, alias="deliveryContext"
    )
    timestamp: int | None = None
    source: LineSource = Field(default_factory=LineSource)
    reply_token: str | None = Field(default=None, alias="replyToken")
    message: LineMessage | None = None

    @classmethod
    def from_json(cls, raw: str) -> "LineEvent":
        return cls.model_validate(json.loads(raw))

    def dedup_key(self, chat_key: str) -> str:
        """Stable identity for dedup. LINE redeliveries carry the same webhookEventId."""
        if self.webhook_event_id:
            return self.webhook_event_id
        if self.message is not None:
            return f"msg:{self.message.id}"
        return f"{self.type}:{chat_key}:{self.timestamp}"
