import frappe
from frappe.model.document import Document
from frappe.utils import add_days, cint, now_datetime


class ChatbotConversation(Document):
    pass


def delete_expired_conversations():
    """Delete conversations older than Chatbot Settings retention_days; 0 keeps them forever."""
    retention_days = cint(frappe.db.get_single_value("Chatbot Settings", "retention_days"))
    if retention_days <= 0:
        return
    cutoff = add_days(now_datetime(), -retention_days)
    frappe.db.delete("Chatbot Conversation", {"creation": ["<", cutoff]})
