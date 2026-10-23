"""Interactive terminal app: python main.py [--live] [--resume THREAD_ID]."""

import argparse
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from drafting import DraftWriter
from mail_agent import create_agent
from security import checked_recipient

BASE = Path(__file__).resolve().parent


def ask_intake():
    print('\nWho should I email?')
    while True:
        try:
            recipient = checked_recipient(input('Recipient email: ').strip())
            break
        except ValueError as exc:
            print('Please try again:', exc)
    print('\nWhat should the email say? You can describe tone, context, and key points.')
    while True:
        instructions = input('Your requirements: ').strip()
        if instructions:
            break
        print('Please describe the email you want to write.')
    return {'recipient': recipient, 'instructions': instructions}


def ask_approval(payload):
    print('\n' + '=' * 60)
    print('PLEASE REVIEW THE EXACT MESSAGE BELOW')
    print('TO:     ' + payload['recipient'])
    print('SUBJECT:' + ' ' + payload['subject'])
    print('BODY:\n' + payload['body'])
    print('=' * 60)
    print('Options: send | edit | to | cancel')
    while True:
        action = input('Your decision: ').strip().lower()
        if action == 'send':
            return {'action': 'send'}
        if action == 'edit':
            while True:
                feedback = input('What should I change? ').strip()
                if feedback:
                    return {'action': 'edit', 'feedback': feedback}
        if action == 'to':
            while True:
                try:
                    to = checked_recipient(input('New recipient: ').strip())
                    return {'action': 'to', 'recipient': to}
                except ValueError as exc:
                    print(exc)
        if action == 'cancel':
            return {'action': 'cancel'}
        print('Please enter one of: send, edit, to, cancel.')


def pending_interruption(graph, config):
    """Find a paused interaction after a restart."""
    snapshot = graph.get_state(config)
    for task in snapshot.tasks:
        for item in task.interrupts:
            return item
    return None


def run():
    parser = argparse.ArgumentParser(description='LangGraph approval-first email agent')
    parser.add_argument('--live', action='store_true', help='Allow real Gmail sending after approval')
    parser.add_argument('--resume', metavar='THREAD_ID', help='Resume a paused conversation')
    parser.add_argument('--mock', action='store_true', help='Placeholder drafting (no LLM; copies request text)')
    args = parser.parse_args()
    if args.mock and args.live:
        parser.error('Use real LLM drafting for live email. --mock is dry-run only.')

    load_dotenv(BASE / '.env')

    thread_id = args.resume or str(uuid.uuid4())
    config = {
        'configurable': {
            'thread_id': thread_id,
            'allow_live': bool(args.live),
        }
    }
    print('\nLangGraph Email Agent')
    print('Thread ID:', thread_id)
    print('Mode:', 'LIVE SEND (after approval)' if args.live else 'DRY RUN (never sends)')
    if args.mock:
        print('Drafting: MOCK PLACEHOLDER (not AI-generated)')
    if not args.mock:
        print('Drafting: Local Llama via Ollama')
    if args.live:
        print('WARNING: Approving a draft with "send" WILL send the email.')

    try:
        writer = DraftWriter(mock=args.mock)
        with SqliteSaver.from_conn_string(str(BASE / 'checkpoints.sqlite')) as saver:
            graph = create_agent(saver, writer, BASE / 'send_ledger.sqlite')
            if args.resume:
                checkpoint = graph.get_state(config)
                if not checkpoint.values and not checkpoint.tasks:
                    raise ValueError('Thread not found. Check the thread ID.')
                pending = pending_interruption(graph, config)
                if pending is None:
                    print('Thread is not waiting for input. Last status:', checkpoint.values.get('status'))
                    return
                result = {'__interrupt__': [pending]}
            else:
                result = graph.invoke({}, config)

            while result.get('__interrupt__'):
                event = result['__interrupt__'][0].value
                if event['kind'] == 'intake':
                    response = ask_intake()
                elif event['kind'] == 'approval':
                    response = ask_approval(event)
                else:
                    raise RuntimeError('Unknown pause type: ' + str(event.get('kind')))
                print('\nWorking...')
                result = graph.invoke(Command(resume=response), config)

            status = result.get('status', 'unknown')
            if status == 'sent':
                print('\nSENT! Gmail message ID:', result.get('gmail_message_id'))
            elif status == 'dry_run':
                print('\nAPPROVED DRY RUN: NO email was sent.')
                print('Run a NEW thread with --live to send a real email.')
            elif status == 'cancelled':
                print('\nCancelled. No email was sent.')
            else:
                print('\nFinished with status:', status)
    except (KeyboardInterrupt, EOFError):
        print('\nPaused without sending. Resume with:')
        print(f'  python main.py --resume {thread_id}' + (' --live' if args.live else ''))
    except Exception as exc:
        print('\nERROR:', exc, file=sys.stderr)
        print('Thread ID for investigation:', thread_id, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    run()
