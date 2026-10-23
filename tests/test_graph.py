import importlib.util
import tempfile
import unittest
from pathlib import Path
from sys import path

path.insert(0, str(Path(__file__).resolve().parents[1]))

HAS_LANGGRAPH = importlib.util.find_spec('langgraph') is not None


@unittest.skipUnless(HAS_LANGGRAPH, 'Install requirements.txt to test LangGraph')
class GraphFlowTests(unittest.TestCase):
    def test_approval_revision_dry_run(self):
        from langgraph.checkpoint.sqlite import SqliteSaver
        from langgraph.types import Command
        from drafting import DraftWriter
        from mail_agent import create_agent
        with tempfile.TemporaryDirectory() as tmp:
            with SqliteSaver.from_conn_string(str(Path(tmp) / 'checkpoint.sqlite')) as saver:
                agent = create_agent(saver, DraftWriter(mock=True), Path(tmp) / 'ledger.sqlite')
                config = {'configurable': {'thread_id': 'test-thread', 'allow_live': False}}
                first = agent.invoke({}, config)
                self.assertEqual(first['__interrupt__'][0].value['kind'], 'intake')
                second = agent.invoke(Command(resume={
                    'recipient': 'friend@example.com',
                    'instructions': 'Ask about the project',
                }), config)
                self.assertEqual(second['__interrupt__'][0].value['kind'], 'approval')
                third = agent.invoke(Command(resume={
                    'action': 'edit', 'feedback': 'make it warmer',
                }), config)
                self.assertIn('MOCK REVISION REQUEST', third['__interrupt__'][0].value['body'])
                fourth = agent.invoke(Command(resume={'action': 'to', 'recipient': 'other@example.com'}), config)
                self.assertEqual(fourth['__interrupt__'][0].value['recipient'], 'other@example.com')
                final = agent.invoke(Command(resume={'action': 'send'}), config)
                self.assertEqual(final['status'], 'dry_run')
                self.assertFalse((Path(tmp) / 'ledger.sqlite').exists())

    def test_cancel_never_sends(self):
        from langgraph.checkpoint.sqlite import SqliteSaver
        from langgraph.types import Command
        from drafting import DraftWriter
        from mail_agent import create_agent
        with tempfile.TemporaryDirectory() as tmp:
            with SqliteSaver.from_conn_string(str(Path(tmp) / 'state.sqlite')) as saver:
                graph = create_agent(saver, DraftWriter(mock=True), Path(tmp) / 'ledger.sqlite')
                config = {'configurable': {'thread_id': 'cancel', 'allow_live': False}}
                graph.invoke({}, config)
                graph.invoke(Command(resume={
                    'recipient': 'other@example.com', 'instructions': 'Say hello'
                }), config)
                result = graph.invoke(Command(resume={'action': 'cancel'}), config)
                self.assertEqual(result['status'], 'cancelled')
                self.assertFalse((Path(tmp) / 'ledger.sqlite').exists())


if __name__ == '__main__':
    unittest.main()
