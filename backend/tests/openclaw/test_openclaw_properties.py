from __future__ import annotations

from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.openclaw.context_manager import ContextManager
from backend.app.openclaw.models import ConversationMessage, UserContext


@given(
    messages=st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=120),
    window=st.integers(min_value=1, max_value=50),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_context_window_maintenance(messages: list[str], window: int) -> None:
    context = UserContext(user_id="u1")
    for text in messages:
        context.add_message(
            ConversationMessage(role="user", content=text, user_id="u1"),
            max_messages=window,
        )
    assert len(context.messages) <= window
    if len(messages) >= window:
        assert context.messages[0].content == messages[-window]


@pytest.mark.asyncio
@given(count=st.integers(min_value=1, max_value=80))
@settings(max_examples=50, deadline=7000)
@pytest.mark.property_test
async def test_property_context_persistence_round_trip(count: int) -> None:
    with TemporaryDirectory() as tmp:
        manager = ContextManager(data_dir=tmp, max_messages=50)
        for index in range(count):
            await manager.add_message("u1", "user", f"msg-{index}")

        restored = ContextManager(data_dir=tmp, max_messages=50)
        await restored.load_contexts_from_disk()
        loaded = await restored.get_context("u1")
        assert len(loaded.messages) == min(count, 50)
