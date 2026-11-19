import frappe


ARTICLES = (
    {
        "title": "What ERPNext Is",
        "keywords": "erpnext, what is erpnext, enterprise resource planning, erp software",
        "question": "What is ERPNext?",
        "priority": 110,
        "answer": (
            "ERPNext is an open-source enterprise resource planning system. It brings "
            "important business areas such as accounting, sales, purchasing, inventory, "
            "manufacturing, projects, and support into one connected application. Shared "
            "business records help teams work with consistent, up-to-date information. "
            "ERPNext is accessed through a web browser and is built on the Frappe Framework."
        ),
    },
    {
        "title": "What the Frappe Framework Is",
        "keywords": "frappe, frappe framework, what is frappe, web application framework",
        "question": "What is the Frappe Framework?",
        "priority": 109,
        "answer": (
            "Frappe Framework is the open-source web application framework on which ERPNext "
            "is built. It provides the foundation for browser-based business applications, "
            "including their user interface, security, data management, reports, and common "
            "application services. Frappe is the technology platform, while ERPNext is the "
            "business application created with that platform."
        ),
    },
)


def seed():
    """Keep the two approved introductory knowledge articles up to date."""
    for item in ARTICLES:
        _upsert_article(item)
    print("ERPNext and Frappe introductions are up to date.")


def _upsert_article(item):
    name = frappe.db.get_value(
        "Chatbot Knowledge",
        {"title": item["title"]},
        "name",
    )
    doc = (
        frappe.get_doc("Chatbot Knowledge", name)
        if name
        else frappe.new_doc("Chatbot Knowledge")
    )
    doc.update(item)
    doc.published = 1
    doc.save(ignore_permissions=True)
