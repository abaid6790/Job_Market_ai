"""
AI Career Assistant chat orchestration.

Ties the context builder (grounding) to AIProviderManager (Phase 7). If no
provider is configured or every provider fails, this stores a clear,
honest assistant message explaining that rather than crashing the
request or pretending to answer — consistent with how the rest of the
app treats "insufficient data" (see Phase 5's analytics, Phase 6's
scoring): say so plainly instead of faking it.
"""
from app.extensions import db
from app.models import AIConversation, AIMessage
from app.services.ai import get_ai_manager
from app.services.ai.base import AIProviderError
from app.services.assistant.context_builder import build_system_prompt

MAX_HISTORY_MESSAGES = 10  # prior turns included for conversational continuity
NO_PROVIDER_MESSAGE = (
    "The AI assistant isn't available right now — no AI provider is configured "
    "for this deployment. An administrator can set one up under AI provider "
    "status; once configured, this conversation will work normally."
)
GENERIC_FAILURE_MESSAGE = (
    "Sorry, I couldn't get a response from the AI provider just now. "
    "This has been logged — please try again in a moment."
)


def _conversation_history_as_prompt(conversation, exclude_last=True):
    # Query AIMessage directly rather than via conversation.messages —
    # chaining .order_by() on a dynamic relationship APPENDS to the
    # relationship's own configured order_by (ascending by id) rather
    # than replacing it, which silently defeated an explicit .desc()
    # here and fed the model history in the wrong order. Querying the
    # model directly avoids that trap entirely.
    messages = (
        AIMessage.query.filter_by(conversation_id=conversation.id)
        .order_by(AIMessage.id.desc())
        .limit(MAX_HISTORY_MESSAGES + (1 if exclude_last else 0))
        .all()
    )
    messages.reverse()
    if exclude_last and messages:
        messages = messages[:-1]
    if not messages:
        return ""
    lines = [f"{m.role.upper()}: {m.content}" for m in messages]
    return "Prior conversation in this thread:\n" + "\n".join(lines) + "\n"


def ask(user, conversation, question, specific_job=None):
    """Adds the user's question and the assistant's reply to the
    conversation, and returns the assistant AIMessage."""
    user_message = AIMessage(conversation_id=conversation.id, role="user", content=question)
    db.session.add(user_message)
    db.session.flush()

    if conversation.title is None:
        conversation.title = question[:150]

    system_prompt, context_note = build_system_prompt(user, specific_job=specific_job)
    history = _conversation_history_as_prompt(conversation)
    full_prompt = f"{history}USER: {question}" if history else question

    manager = get_ai_manager()

    try:
        response = manager.generate(
            full_prompt, system=system_prompt, user_id=user.id, max_tokens=800
        )
        reply_text = response.text
    except AIProviderError:
        reply_text = NO_PROVIDER_MESSAGE if not manager.configured_providers() else GENERIC_FAILURE_MESSAGE

    assistant_message = AIMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=reply_text,
        context_note=context_note,
    )
    db.session.add(assistant_message)
    db.session.commit()

    return assistant_message


def start_conversation(user, question, specific_job=None):
    conversation = AIConversation(user_id=user.id)
    db.session.add(conversation)
    db.session.flush()
    ask(user, conversation, question, specific_job=specific_job)
    return conversation
