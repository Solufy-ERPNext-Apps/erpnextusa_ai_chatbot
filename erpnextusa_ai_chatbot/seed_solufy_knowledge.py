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
    {
        "title": "ERPNext Compared with Odoo",
        "category": "ERP Comparison",
        "keywords": "erpnext vs odoo, odoo or erpnext, compare odoo erpnext, erp choice",
        "question": "Should I choose ERPNext or Odoo?",
        "priority": 108,
        "answer": (
            "ERPNext and Odoo are both established business-management platforms. ERPNext "
            "is often a strong fit when a business wants one integrated, open-source ERP with "
            "accounting, selling, buying, stock, manufacturing, projects, HR, and support in a "
            "consistent interface. Odoo has a broad application marketplace and multiple product "
            "editions, which can suit organizations that prefer its particular apps and partner "
            "ecosystem. The right choice depends on required processes, localization, users, "
            "integrations, implementation capacity, and total ownership cost. Compare both with "
            "the same process list and a working demonstration before deciding."
        ),
    },
)


def seed():
    """Seed curated articles and installed ERPNext metadata knowledge."""
    for item in ARTICLES:
        _upsert_article(item)
    metadata_count = seed_erpnext_doctype_knowledge()
    print(
        f"Curated knowledge and {metadata_count} ERPNext DocType articles are up to date."
    )


def seed_erpnext_doctype_knowledge():
    """Create factual knowledge from DocTypes shipped by the installed ERPNext app."""
    modules = frappe.get_all(
        "Module Def",
        filters={"app_name": "erpnext"},
        pluck="name",
        limit_page_length=1000,
    )
    if not modules:
        return 0

    doctypes = frappe.get_all(
        "DocType",
        filters={"custom": 0, "module": ["in", modules]},
        fields=["name", "module", "description", "issingle", "istable", "is_submittable"],
        order_by="module asc, name asc",
        limit_page_length=2000,
    )
    for row in doctypes:
        _upsert_erpnext_doctype(row)
    return len(doctypes)


def _upsert_erpnext_doctype(row):
    item = _doctype_article(row)
    source_url = f"builtin:erpnext:doctype:{row.name}"[:140]
    name = frappe.db.get_value(
        "Chatbot Knowledge", {"source_url": source_url}, "name"
    )
    doc = (
        frappe.get_doc("Chatbot Knowledge", name)
        if name
        else frappe.new_doc("Chatbot Knowledge")
    )
    doc.update(item)
    doc.source_url = source_url
    doc.published = 1
    doc.save(ignore_permissions=True)


def _doctype_article(row):
    record_type = "child table" if row.istable else "single settings record" if row.issingle else "business record"
    lifecycle = (
        "It supports draft, submitted, and cancelled document states."
        if row.is_submittable
        else "It is saved without a submit-and-cancel lifecycle."
    )
    description = str(row.description or "").strip()
    detail = f" {description}" if description else ""
    return {
        "title": f"ERPNext DocType: {row.name}",
        "category": "ERPNext Reference",
        "keywords": f"ERPNext, {row.name}, {row.module}, DocType, standard feature",
        "question": f"What is {row.name} in ERPNext?",
        "priority": 45,
        "answer": (
            f"**{row.name}** is a standard ERPNext {record_type} in the **{row.module}** "
            f"module.{detail} {lifecycle} Its available fields and behavior depend on the "
            "installed ERPNext version and enabled business features."
        ),
    }


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
    doc.category = item.get("category", "ERPNext Fundamentals")
    doc.published = 1
    doc.save(ignore_permissions=True)
