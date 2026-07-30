from core.ai.conversation import Conversation


def test_conversation_adds_messages() -> None:
    conversation = Conversation()

    conversation.add_user_message("Create a trend-following strategy.")
    conversation.add_assistant_message("Which trend definition do you prefer?")

    assert conversation.message_count() == 2
    assert conversation.message_count("user") == 1
    assert conversation.message_count("assistant") == 1
    assert conversation.last_message() is not None
    assert conversation.last_message().role == "assistant"


def test_conversation_builds_title_from_first_user_message() -> None:
    conversation = Conversation()

    conversation.add_user_message("Build an RSI strategy for AAPL.")

    assert conversation.title == "Build an RSI strategy for AAPL."


def test_conversation_serialization_round_trip() -> None:
    conversation = Conversation()
    conversation.add_system_message("System prompt")
    conversation.add_user_message("Create a strategy.")

    restored = Conversation.from_dict(conversation.to_dict())

    assert restored.id == conversation.id
    assert restored.title == conversation.title
    assert restored.message_count() == 2
    assert restored.last_message("user") is not None
    assert restored.last_message("user").content == "Create a strategy."


def test_clear_can_preserve_system_messages() -> None:
    conversation = Conversation()
    conversation.add_system_message("System prompt")
    conversation.add_user_message("Hello")

    conversation.clear(preserve_system_messages=True)

    assert conversation.message_count() == 1
    assert conversation.last_message().role == "system"