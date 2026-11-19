from unittest import TestCase
from unittest.mock import patch

from erpnextusa_ai_chatbot.api import (
    _page_source_url,
    _prioritize_knowledge_results,
    _remove_unrequested_greeting,
    _retrieve_for_country,
    company_summary_answer,
    extract_visitor_name,
    is_consultant_request,
    is_company_summary_request,
    is_page_context_request,
    page_metadata_answer,
    summarize_page_answer,
)


class TestChatRelevance(TestCase):
    def test_sales_team_is_a_consultant_request(self):
        self.assertTrue(is_consultant_request("Sales team of Solufy"))

    def test_current_page_summary_request_is_detected(self):
        self.assertTrue(is_page_context_request("what in this page summarized"))

    def test_misspelled_company_summary_request_is_detected(self):
        self.assertTrue(is_company_summary_request("Summurized the company solufy"))

    def test_company_summary_does_not_use_an_article(self):
        answer = company_summary_answer()

        self.assertIn("ERPNext and Frappe consulting", answer)
        self.assertNotIn("Euro India Foods", answer)

    def test_general_manufacturing_question_prefers_industry_over_blog(self):
        industry = {
            "title": "Industry: Manufacturing",
            "category": "Industry",
            "match_score": 40,
            "priority": 70,
        }
        repeated_article = {
            "title": "Article: Euro India Foods",
            "category": "Blog",
            "match_score": 70,
            "priority": 50,
        }

        results = _prioritize_knowledge_results(
            "What is manufacturing?", [repeated_article, industry]
        )

        self.assertEqual(results[0], industry)

    def test_explicit_article_question_prefers_blog(self):
        service = {
            "title": "Service: ERP Implementation",
            "category": "Service",
            "match_score": 80,
            "priority": 70,
        }
        article = {
            "title": "Article: ERP Implementation Guide",
            "category": "Blog",
            "match_score": 60,
            "priority": 50,
        }

        results = _prioritize_knowledge_results(
            "Show the ERP implementation guide", [service, article]
        )

        self.assertEqual(results[0], article)

    def test_industry_page_maps_to_exact_knowledge_source(self):
        self.assertEqual(
            _page_source_url("/industries/erpnext-for-manufacturing"),
            "auto:Website Industry:erpnext-for-manufacturing",
        )

    def test_page_summary_keeps_overview_and_link(self):
        answer = "**Title**\n\nOverview\n\n• Key modules\n\nChallenges\n\n➡ [Open](/page)"

        self.assertEqual(
            summarize_page_answer(answer),
            "**Title**\n\nOverview\n\n• Key modules\n\n➡ [Open](/page)",
        )

    def test_homepage_summary_uses_page_metadata(self):
        self.assertEqual(
            page_metadata_answer(
                "ERPNext USA",
                "We're Solufy. We Support.",
                "ERPNext implementation, consulting and support for US businesses.",
            ),
            "**We're Solufy. We Support.**\n\n"
            "ERPNext implementation, consulting and support for US businesses.",
        )

    @patch("erpnextusa_ai_chatbot.api.retrieve")
    def test_country_enrichment_does_not_outrank_direct_match(self, retrieve):
        team = {"title": "Team: Ishan Donga", "answer": "Team profile"}
        country_article = {
            "title": "Article: Euro India Foods",
            "answer": "Food manufacturing article",
        }
        retrieve.side_effect = [[team], [country_article, team]]

        results = _retrieve_for_country("Sales team of Solufy", "India", 5)

        self.assertEqual(results, [team, country_article])

    @patch("erpnextusa_ai_chatbot.api.retrieve")
    def test_country_does_not_create_match_for_unrelated_message(self, retrieve):
        retrieve.return_value = []

        results = _retrieve_for_country("Now", "India", 5)

        self.assertEqual(results, [])
        retrieve.assert_called_once_with("Now", 5)

    def test_extract_visitor_name_from_intro(self):
        self.assertEqual(extract_visitor_name("i am savan patel"), "Savan Patel")
        self.assertEqual(extract_visitor_name("I'm Savan Patel"), "Savan Patel")
        self.assertEqual(extract_visitor_name("my name is Savan"), "Savan")
        self.assertEqual(extract_visitor_name("call me Savan Patel"), "Savan Patel")
        self.assertEqual(extract_visitor_name("this is Savan"), "Savan")

    def test_extract_visitor_name_ignores_non_names(self):
        self.assertEqual(extract_visitor_name("I am looking for ERP software"), "")
        self.assertEqual(extract_visitor_name("I am interested in Solufy"), "")
        self.assertEqual(extract_visitor_name("What is ERPNext?"), "")

    def test_remove_unrequested_greeting_preserves_named_greeting(self):
        answer = "Hello Savan! It is fantastic to meet you."
        self.assertEqual(
            _remove_unrequested_greeting("i am savan patel", answer, visitor_name="Savan Patel"),
            answer,
        )
