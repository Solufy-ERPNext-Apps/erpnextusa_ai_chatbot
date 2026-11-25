from types import SimpleNamespace
from unittest import TestCase

from erpnextusa_ai_chatbot.seed_solufy_knowledge import ARTICLES, _doctype_article


class TestSeedKnowledge(TestCase):
    def test_odoo_comparison_is_seeded(self):
        comparison = next(
            item for item in ARTICLES if item["title"] == "ERPNext Compared with Odoo"
        )

        self.assertIn("ERPNext", comparison["answer"])
        self.assertIn("Odoo", comparison["answer"])
        self.assertIn("required processes", comparison["answer"])

    def test_doctype_article_uses_installed_metadata(self):
        article = _doctype_article(
            SimpleNamespace(
                name="Sales Invoice",
                module="Accounts",
                description="Records customer billing.",
                issingle=0,
                istable=0,
                is_submittable=1,
            )
        )

        self.assertEqual(article["category"], "ERPNext Reference")
        self.assertIn("Accounts", article["answer"])
        self.assertIn("submitted", article["answer"])
