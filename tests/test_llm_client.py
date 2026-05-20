from unittest.mock import MagicMock, patch

import pytest

from utils.llm_client import chat_completion_with_retry


def test_chat_completion_succeeds_first_try():
    client = MagicMock()
    client.chat.completions.create.return_value = "ok"

    result = chat_completion_with_retry(
        client,
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
        timeout=5,
        max_retries=3,
    )
    assert result == "ok"
    assert client.chat.completions.create.call_count == 1


@patch("utils.llm_client.time.sleep")
def test_chat_completion_retries_then_succeeds(mock_sleep):
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        RuntimeError("rate limit"),
        "ok",
    ]

    result = chat_completion_with_retry(
        client,
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
        timeout=5,
        max_retries=3,
    )
    assert result == "ok"
    assert client.chat.completions.create.call_count == 2
    mock_sleep.assert_called_once()


@patch("utils.llm_client.time.sleep")
def test_chat_completion_raises_after_max_retries(mock_sleep):
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("fail")

    with pytest.raises(RuntimeError, match="fail"):
        chat_completion_with_retry(
            client,
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "hi"}],
            timeout=5,
            max_retries=2,
        )
    assert client.chat.completions.create.call_count == 2
