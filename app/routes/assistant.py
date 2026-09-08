from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user

from app.extensions import db
from app.forms import AskAssistantForm
from app.models import AIConversation, Job
from app.services.auth.decorators import verified_required
from app.services.assistant.chat import start_conversation, ask
from app.services.ai import get_ai_manager

assistant_bp = Blueprint("assistant", __name__, url_prefix="/assistant")

SUGGESTED_QUESTIONS = [
    "What skills do I need for my target role?",
    "What should I learn next?",
    "Which of my skill gaps should I prioritize?",
    "Summarize my resume-job match reports.",
]


def _get_owned_conversation(conversation_id):
    conversation = AIConversation.query.get_or_404(conversation_id)
    if conversation.user_id != current_user.id:
        abort(403)
    return conversation


@assistant_bp.route("/")
@login_required
@verified_required
def index():
    conversations = (
        AIConversation.query.filter_by(user_id=current_user.id)
        .order_by(AIConversation.updated_at.desc())
        .all()
    )
    form = AskAssistantForm()
    manager = get_ai_manager()
    return render_template(
        "assistant/index.html",
        conversations=conversations,
        form=form,
        suggested_questions=SUGGESTED_QUESTIONS,
        provider_available=bool(manager.configured_providers()),
    )


@assistant_bp.route("/start", methods=["POST"])
@login_required
@verified_required
def start():
    form = AskAssistantForm()
    if not form.validate_on_submit():
        for field_errors in form.errors.values():
            for error in field_errors:
                flash(error, "danger")
        return redirect(url_for("assistant.index"))

    specific_job = None
    if form.job_id.data:
        specific_job = Job.query.filter_by(id=form.job_id.data, status="completed").first()

    conversation = start_conversation(current_user, form.question.data.strip(), specific_job=specific_job)
    return redirect(url_for("assistant.conversation", conversation_id=conversation.id))


@assistant_bp.route("/<int:conversation_id>")
@login_required
@verified_required
def conversation(conversation_id):
    conv = _get_owned_conversation(conversation_id)
    messages = conv.messages.all()
    form = AskAssistantForm()
    manager = get_ai_manager()
    return render_template(
        "assistant/conversation.html",
        conversation=conv,
        messages=messages,
        form=form,
        provider_available=bool(manager.configured_providers()),
    )


@assistant_bp.route("/<int:conversation_id>/ask", methods=["POST"])
@login_required
@verified_required
def ask_followup(conversation_id):
    conv = _get_owned_conversation(conversation_id)
    form = AskAssistantForm()
    if not form.validate_on_submit():
        for field_errors in form.errors.values():
            for error in field_errors:
                flash(error, "danger")
        return redirect(url_for("assistant.conversation", conversation_id=conv.id))

    specific_job = None
    if form.job_id.data:
        specific_job = Job.query.filter_by(id=form.job_id.data, status="completed").first()

    ask(current_user, conv, form.question.data.strip(), specific_job=specific_job)
    return redirect(url_for("assistant.conversation", conversation_id=conv.id))


@assistant_bp.route("/<int:conversation_id>/delete", methods=["POST"])
@login_required
@verified_required
def delete(conversation_id):
    conv = _get_owned_conversation(conversation_id)
    db.session.delete(conv)
    db.session.commit()
    flash("Conversation deleted.", "info")
    return redirect(url_for("assistant.index"))
