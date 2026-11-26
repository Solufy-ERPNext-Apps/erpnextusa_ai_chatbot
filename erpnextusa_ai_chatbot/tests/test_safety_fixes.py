import inspect
from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe

from erpnextusa_ai_chatbot import api, hooks, sync_knowledge


def mock_knowledge_lookup(qb, rows):
    lookup = qb.from_.return_value.select.return_value.where.return_value.limit.return_value
    lookup.run.return_value = rows


class TestInstallHooks(TestCase):
    def test_install_and_migrate_only_refresh_knowledge(self):
        for hook in (hooks.after_install, hooks.after_migrate):
            self.assertEqual(hook, "erpnextusa_ai_chatbot.sync_knowledge.refresh_knowledge")


class TestGuestCannotPickProvider(TestCase):
    def test_chat_has_no_model_argument(self):
        self.assertNotIn("model", inspect.signature(api.chat).parameters)

    def test_provider_reply_has_no_model_override(self):
        self.assertNotIn("requested_model", inspect.signature(api.provider_reply).parameters)


class TestSessionHistory(TestCase):
    @patch.object(api.frappe, "get_all")
    def test_uses_latest_turns_in_chronological_order(self, get_all):
        get_all.return_value = [
            frappe._dict(visitor_message="third", assistant_message="answer three"),
            frappe._dict(visitor_message="second", assistant_message="answer two"),
        ]
        history = api.get_session_history("session", limit=2)

        self.assertEqual(get_all.call_args.kwargs["order_by"], "creation desc")
        self.assertEqual(
            [turn["content"] for turn in history],
            ["second", "answer two", "third", "answer three"],
        )


@patch.object(api.frappe, "get_doc")
@patch.object(api.frappe, "qb", new_callable=MagicMock)
class TestLikedResponses(TestCase):
    def test_new_like_creates_unpublished_draft(self, qb, get_doc):
        mock_knowledge_lookup(qb, [])
        get_doc.return_value.name = "KB-1"

        name = api._sync_learned_response("What is ERPNext?", "An ERP.", 1)

        values = get_doc.call_args.args[0]
        self.assertEqual(name, "KB-1")
        self.assertEqual(values["published"], 0)
        self.assertEqual(values["question"], "what is erpnext?")
        get_doc.return_value.insert.assert_called_once()

    def test_like_never_rewrites_existing_answer(self, qb, get_doc):
        mock_knowledge_lookup(qb, [frappe._dict(name="KB-1", answer="Approved answer.")])

        name = api._sync_learned_response("What is ERPNext?", "Injected answer.", 1)

        self.assertEqual(name, "KB-1")
        qb.update.assert_not_called()
        get_doc.assert_not_called()

    def test_matching_like_only_counts_a_like(self, qb, get_doc):
        mock_knowledge_lookup(qb, [frappe._dict(name="KB-1", answer="Approved answer.")])

        api._sync_learned_response("What is ERPNext?", "Approved answer.", 1)

        update = qb.update.return_value
        update.set.assert_called_once()
        update.set.return_value.where.return_value.run.assert_called_once()
        get_doc.assert_not_called()

    def test_dislike_does_not_unpublish_knowledge(self, qb, get_doc):
        mock_knowledge_lookup(qb, [frappe._dict(name="KB-1", answer="Approved answer.")])

        name = api._sync_learned_response("What is ERPNext?", "Approved answer.", 0)

        self.assertEqual(name, "KB-1")
        qb.update.assert_not_called()
        get_doc.assert_not_called()


class TestPruneKeepsChatFeedback(TestCase):
    @patch.object(sync_knowledge.frappe, "delete_doc")
    @patch.object(sync_knowledge.frappe, "get_all")
    @patch.object(sync_knowledge.frappe, "db", new=MagicMock(**{"exists.return_value": False}))
    def test_chat_feedback_survives_prune(self, get_all, delete_doc):
        get_all.return_value = [
            frappe._dict(name="KB-1", title="Liked", source_url="chat-feedback:abc"),
            frappe._dict(name="KB-2", title="Stale", source_url="auto:Website Service:old"),
        ]

        removed = sync_knowledge.prune_non_website_knowledge()

        self.assertEqual(removed, 1)
        delete_doc.assert_called_once_with("Chatbot Knowledge", "KB-2", ignore_permissions=True)
