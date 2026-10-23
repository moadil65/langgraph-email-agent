import io
import json
import unittest
from pathlib import Path
from sys import path
from unittest.mock import patch

path.insert(0, str(Path(__file__).resolve().parents[1]))
from drafting import check_ollama


class FakeHttpResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps({'models': [{'name': 'llama3.2:latest'}]}).encode()


class LocalOllamaTests(unittest.TestCase):
    def test_ollama_model_is_available(self):
        with patch('drafting.urlopen', return_value=FakeHttpResponse()):
            check_ollama('http://localhost:11434', 'llama3.2')

    def test_missing_model_has_clear_instruction(self):
        with patch('drafting.urlopen', return_value=FakeHttpResponse()):
            with self.assertRaisesRegex(RuntimeError, 'ollama pull llama3.1:8b'):
                check_ollama('http://localhost:11434', 'llama3.1:8b')

    def test_unreachable_ollama_has_clear_instruction(self):
        with patch('drafting.urlopen', side_effect=OSError('connection refused')):
            with self.assertRaisesRegex(RuntimeError, 'Cannot reach Ollama'):
                check_ollama('http://localhost:11434', 'llama3.2')


if __name__ == '__main__':
    unittest.main()
