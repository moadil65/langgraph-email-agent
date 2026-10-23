"""A LangGraph email agent with durable checkpoints and human send approval."""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from gmail_sender import authorized_gmail, send_using_service
from ledger import mark_sent, mark_uncertain, reserve_send
from security import checked_mail_fields, checked_recipient, mail_fingerprint


class MailState(TypedDict, total=False):
    recipient: str
    instructions: str
    subject: str
    body: str
    feedback: str
    decision: str
    approved_fingerprint: str
    status: str
    gmail_message_id: str


def create_agent(checkpointer, writer, ledger_path):
    """Build the state machine. LLM writes text; only approval permits sending."""

    def collect(state: MailState):
        response = interrupt({
            'kind': 'intake',
            'message': 'Who should I email, and what should the email say?',
        })
        recipient = checked_recipient(response['recipient'])
        instructions = str(response['instructions']).strip()
        if not instructions:
            raise ValueError('Tell the agent what the email should communicate.')
        return {'recipient': recipient, 'instructions': instructions, 'status': 'collected'}

    def draft(state: MailState):
        text = writer.write(state['recipient'], state['instructions'])
        checked_mail_fields(state['recipient'], text['subject'], text['body'])
        return {
            'subject': text['subject'],
            'body': text['body'],
            'status': 'drafted',
            'approved_fingerprint': '',
        }

    def review(state: MailState):
        response = interrupt({
            'kind': 'approval',
            'recipient': state['recipient'],
            'subject': state['subject'],
            'body': state['body'],
            'message': 'Approve this EXACT email, request changes, or cancel?',
        })
        choice = response.get('action')
        if choice == 'send':
            signature = mail_fingerprint(
                state['recipient'], state['subject'], state['body']
            )
            return {
                'decision': 'send',
                'approved_fingerprint': signature,
                'status': 'approved',
            }
        if choice == 'edit':
            feedback = str(response.get('feedback', '')).strip()
            if not feedback:
                raise ValueError('Revision instructions cannot be empty.')
            return {
                'decision': 'edit',
                'feedback': feedback,
                'approved_fingerprint': '',
                'status': 'revision_requested',
            }
        if choice == 'to':
            return {
                'decision': 'to',
                'recipient': checked_recipient(response['recipient']),
                'approved_fingerprint': '',
                'status': 'recipient_changed',
            }
        if choice == 'cancel':
            return {
                'decision': 'cancel',
                'approved_fingerprint': '',
                'status': 'cancelled',
            }
        raise ValueError('Reply with send, edit, to, or cancel.')

    def choose(state: MailState):
        return {
            'send': 'send',
            'edit': 'revise',
            'to': 'review',
            'cancel': END,
        }[state['decision']]

    def revise(state: MailState):
        text = writer.write(
            state['recipient'], state['instructions'],
            current_subject=state['subject'], current_body=state['body'],
            feedback=state['feedback'],
        )
        checked_mail_fields(state['recipient'], text['subject'], text['body'])
        return {
            'subject': text['subject'],
            'body': text['body'],
            'approved_fingerprint': '',
            'status': 'revised',
        }

    def send(state: MailState, config):
        fingerprint = mail_fingerprint(
            state['recipient'], state['subject'], state['body']
        )
        if not state.get('approved_fingerprint') or state['approved_fingerprint'] != fingerprint:
            raise RuntimeError('Send blocked: email differs from approved version.')
        if not config['configurable'].get('allow_live', False):
            return {'status': 'dry_run', 'gmail_message_id': ''}

        # Get a usable Gmail OAuth client before reserving an external side effect.
        service = authorized_gmail()
        thread_id = str(config['configurable']['thread_id'])
        already_sent, old_id = reserve_send(ledger_path, thread_id, fingerprint)
        if already_sent:
            return {'status': 'sent', 'gmail_message_id': old_id}
        try:
            gmail_id = send_using_service(
                service, state['recipient'], state['subject'], state['body']
            )
        except Exception as exc:
            mark_uncertain(ledger_path, thread_id, str(exc))
            raise RuntimeError(
                'Gmail sending failed or outcome is uncertain. Check Gmail Sent; '
                'this thread will not automatically retry.'
            ) from exc
        mark_sent(ledger_path, thread_id, gmail_id)
        return {'status': 'sent', 'gmail_message_id': gmail_id}

    graph = StateGraph(MailState)
    graph.add_node('collect', collect)
    graph.add_node('draft', draft)
    graph.add_node('review', review)
    graph.add_node('revise', revise)
    graph.add_node('send', send)
    graph.add_edge(START, 'collect')
    graph.add_edge('collect', 'draft')
    graph.add_edge('draft', 'review')
    graph.add_conditional_edges('review', choose)
    graph.add_edge('revise', 'review')
    graph.add_edge('send', END)
    return graph.compile(checkpointer=checkpointer)
