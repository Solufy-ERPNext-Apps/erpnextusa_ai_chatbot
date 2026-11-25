from unittest import TestCase

from erpnextusa_ai_chatbot.setup_ollama import choose_ollama_model


class TestOllamaModelSelection(TestCase):
    def test_keeps_configured_model_when_it_is_installed(self):
        model, should_pull = choose_ollama_model(
            ("llama3.2:1b", "custom:latest"), "custom:latest"
        )

        self.assertEqual(model, "custom:latest")
        self.assertFalse(should_pull)

    def test_uses_an_existing_model_instead_of_pulling_another(self):
        model, should_pull = choose_ollama_model(("custom:latest",), "missing:latest")

        self.assertEqual(model, "custom:latest")
        self.assertFalse(should_pull)

    def test_pulls_only_llama_when_no_model_is_installed(self):
        model, should_pull = choose_ollama_model((), "custom:latest")

        self.assertEqual(model, "llama3.2:1b")
        self.assertTrue(should_pull)
