import re
import frappe
from frappe.utils import strip_html


def clean_text(html_or_text, max_len=1800):
    if not html_or_text:
        return ""
    s = str(html_or_text)
    # Ensure block tags have spacing so words across paragraphs/list items don't merge
    s = re.sub(r"</(?:p|div|li|h[1-6]|tr|br\s*/?)>", " ", s, flags=re.IGNORECASE)
    text = strip_html(s)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def upsert_knowledge(source_key, data):
    """Upsert a single knowledge article tracked by source_url = source_key."""
    try:
        existing_name = frappe.db.get_value("Chatbot Knowledge", {"source_url": source_key}, "name")
        if existing_name:
            doc = frappe.get_doc("Chatbot Knowledge", existing_name)
            doc.title = data.get("title", doc.title)[:140]
            doc.category = data.get("category", doc.category)
            doc.priority = data.get("priority", doc.priority)
            doc.published = data.get("published", doc.published)
            doc.keywords = data.get("keywords", doc.keywords)
            doc.question = data.get("question", doc.question)
            doc.answer = data.get("answer", doc.answer)
            doc.save(ignore_permissions=True)
            return ("updated", doc.name)
        else:
            doc = frappe.get_doc({
                "doctype": "Chatbot Knowledge",
                "source_url": source_key,
                "title": data.get("title")[:140],
                "category": data.get("category", "Website"),
                "priority": data.get("priority", 50),
                "published": data.get("published", 1),
                "keywords": data.get("keywords", ""),
                "question": data.get("question", ""),
                "answer": data.get("answer", ""),
            })
            doc.insert(ignore_permissions=True)
            return ("created", doc.name)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Chatbot Knowledge Upsert Error ({source_key})")
        return ("error", str(e))


def delete_synced_knowledge(doc, method=None):
    """Hook on_trash to clean up synced knowledge when the parent website doc is deleted."""
    source_key = f"auto:{doc.doctype}:{doc.name}"[:140]
    try:
        existing_name = frappe.db.get_value("Chatbot Knowledge", {"source_url": source_key}, "name")
        if existing_name:
            frappe.delete_doc("Chatbot Knowledge", existing_name, ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Chatbot Knowledge Delete Error ({source_key})")


# -------------------------------------------------------------------------
# Entity Sync Handlers (called on on_update or in bulk)
# -------------------------------------------------------------------------

def sync_website_service(doc, method=None):
    if isinstance(doc, str):
        doc = frappe.get_doc("Website Service", doc)

    source_key = f"auto:Website Service:{doc.name}"[:140]
    service_name = doc.service_name or doc.name
    overview = clean_text(doc.overview or doc.short_description or "")
    problem = clean_text(doc.problem_statement or "")
    solution = clean_text(doc.solution or "")

    parts = [f"**{service_name} by Solufy / ERPNext USA:**"]
    if overview:
        parts.append(overview)
    if problem:
        parts.append(f"• Challenge addressed: {problem}")
    if solution:
        parts.append(f"• Solufy approach: {solution}")
    
    route = getattr(doc, "route", None) or f"services/{doc.slug or doc.name}"
    parts.append(f"👉 [Explore {service_name}](/{route.lstrip('/')})")

    answer = "\n\n".join(parts)
    keywords = f"{service_name}, {doc.slug or ''}, ERPNext {service_name}, service, consulting, implementation"

    return upsert_knowledge(source_key, {
        "title": f"Service: {service_name}",
        "category": "Service",
        "priority": 75,
        "published": 1 if doc.published else 0,
        "keywords": keywords,
        "question": f"What is your {service_name} service? Tell me about {service_name}.",
        "answer": answer,
    })


def sync_website_industry(doc, method=None):
    if isinstance(doc, str):
        doc = frappe.get_doc("Website Industry", doc)

    source_key = f"auto:Website Industry:{doc.name}"[:140]
    industry_name = doc.industry_name or doc.name
    overview = clean_text(doc.overview or doc.short_description or "")
    challenges = clean_text(doc.industry_challenges or "")
    solufy_sol = clean_text(doc.solufy_solution or "")
    key_modules = clean_text(doc.key_modules or "")

    parts = [f"**ERPNext for {industry_name} by Solufy / ERPNext USA:**"]
    if overview:
        parts.append(overview)
    if key_modules:
        parts.append(f"• Key Modules & Features: {key_modules}")
    if challenges:
        parts.append(f"• Industry Challenges: {challenges}")
    if solufy_sol:
        parts.append(f"• Our Solution: {solufy_sol}")

    route = getattr(doc, "route", None) or f"industries/{doc.slug or doc.name}"
    parts.append(f"👉 [Explore {industry_name} Solution](/{route.lstrip('/')})")

    answer = "\n\n".join(parts)
    keywords = f"{industry_name}, {doc.slug or ''}, ERPNext for {industry_name}, industry, ERP solution"

    return upsert_knowledge(source_key, {
        "title": f"Industry: {industry_name}",
        "category": "Industry",
        "priority": 70,
        "published": 1 if doc.published else 0,
        "keywords": keywords,
        "question": f"Do you offer ERPNext for {industry_name}? Tell me about {industry_name} solutions.",
        "answer": answer,
    })


def sync_case_study(doc, method=None):
    if isinstance(doc, str):
        doc = frappe.get_doc("Case Study", doc)

    source_key = f"auto:Case Study:{doc.name}"[:140]
    title = doc.title or doc.name
    client = doc.client or "Enterprise Client"
    industry = doc.industry or "General"
    challenge = clean_text(doc.challenge or doc.short_description or "")
    solution = clean_text(doc.solution or doc.implementation or "")
    results = clean_text(doc.results or "")

    parts = [f"**Case Study: {title} ({client} — {industry})**"]
    if challenge:
        parts.append(f"• The Challenge: {challenge}")
    if solution:
        parts.append(f"• Solufy Solution: {solution}")
    if results:
        parts.append(f"• Business Impact & Results: {results}")

    route = getattr(doc, "route", None) or f"insights/{doc.slug or doc.name}"
    parts.append(f"👉 [Read Full Case Study: {title}](/{route.lstrip('/')})")

    answer = "\n\n".join(parts)
    keywords = f"{title}, {client}, {industry}, case study, client story, success story, results"

    return upsert_knowledge(source_key, {
        "title": f"Case Study: {title}",
        "category": "Case Study",
        "priority": 65,
        "published": 1 if doc.published else 0,
        "keywords": keywords,
        "question": f"Tell me about the case study for {client} / {industry}.",
        "answer": answer,
    })


def sync_team_member(doc, method=None):
    if isinstance(doc, str):
        doc = frappe.get_doc("Website Team Member", doc)

    source_key = f"auto:Website Team Member:{doc.name}"[:140]
    full_name = doc.full_name or doc.name
    designation = doc.designation or "Solution Specialist"
    department = doc.department or "Frappe & ERPNext Architecture"
    bio = clean_text(doc.short_bio or "")

    parts = [f"**{full_name} — {designation} ({department})**"]
    parts.append(f"{full_name} is part of the executive and engineering team at Solufy / ERPNext USA.")
    if bio:
        parts.append(f"Bio: {bio}")
    if doc.linkedin_url:
        parts.append(f"LinkedIn: {doc.linkedin_url}")
    parts.append("👉 [Meet Our Engineering Team](/about)")

    answer = "\n\n".join(parts)
    keywords = f"{full_name}, {designation}, {department}, team member, leadership, who is {full_name}"

    return upsert_knowledge(source_key, {
        "title": f"Team: {full_name} ({designation})",
        "category": "Team",
        "priority": 60,
        "published": 1 if doc.published else 0,
        "keywords": keywords,
        "question": f"Who is {full_name}? What is {full_name}'s role at Solufy?",
        "answer": answer,
    })


def sync_blog_post(doc, method=None):
    if isinstance(doc, str):
        doc = frappe.get_doc("Blog Post", doc)

    source_key = f"auto:Blog Post:{doc.name}"[:140]
    title = doc.title or doc.name
    category = doc.blog_category or "Insights"
    intro = clean_text(doc.blog_intro or doc.meta_description or "")
    if not intro:
        body = doc.content_md or doc.content or doc.content_html or ""
        intro = clean_text(body, 400)

    parts = [f"**Article: {title} ({category})**"]
    if intro:
        parts.append(intro)
    
    route = getattr(doc, "route", None) or doc.name
    parts.append(f"👉 [Read Full Guide: {title}](/{route.lstrip('/')})")

    answer = "\n\n".join(parts)
    keywords = f"{title}, {category}, {doc.blogger or ''}, blog, article, erpnext guide"

    return upsert_knowledge(source_key, {
        "title": f"Article: {title}",
        "category": "Blog",
        "priority": 50,
        "published": 1 if doc.published else 0,
        "keywords": keywords,
        "question": f"What is the article '{title}' about?",
        "answer": answer,
    })


# -------------------------------------------------------------------------
# Bulk Initial Synchronization Script
# -------------------------------------------------------------------------

def sync_all():
    """Sync all existing Services, Industries, Case Studies, Team Members, and Blogs into Chatbot Knowledge."""
    counts = {"Service": 0, "Industry": 0, "Case Study": 0, "Team": 0, "Blog": 0}

    # 1. Services
    if frappe.db.exists("DocType", "Website Service"):
        for name in frappe.db.get_all("Website Service", pluck="name"):
            res, _ = sync_website_service(name)
            if res in ("created", "updated"):
                counts["Service"] += 1

    # 2. Industries
    if frappe.db.exists("DocType", "Website Industry"):
        for name in frappe.db.get_all("Website Industry", pluck="name"):
            res, _ = sync_website_industry(name)
            if res in ("created", "updated"):
                counts["Industry"] += 1

    # 3. Case Studies
    if frappe.db.exists("DocType", "Case Study"):
        for name in frappe.db.get_all("Case Study", pluck="name"):
            res, _ = sync_case_study(name)
            if res in ("created", "updated"):
                counts["Case Study"] += 1

    # 4. Team Members
    if frappe.db.exists("DocType", "Website Team Member"):
        for name in frappe.db.get_all("Website Team Member", pluck="name"):
            res, _ = sync_team_member(name)
            if res in ("created", "updated"):
                counts["Team"] += 1

    # 5. Blog Posts
    if frappe.db.exists("DocType", "Blog Post"):
        for name in frappe.db.get_all("Blog Post", pluck="name"):
            res, _ = sync_blog_post(name)
            if res in ("created", "updated"):
                counts["Blog"] += 1

    frappe.db.commit()
    print("Bulk Knowledge Sync Completed:")
    for k, v in counts.items():
        print(f"  • {k}: {v} synced")
    return counts

