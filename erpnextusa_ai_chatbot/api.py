import re
import uuid
import html
from urllib.parse import urlparse

import frappe
import requests
from frappe import _
from frappe.utils import cint

SETTINGS = "Chatbot Settings"


def clean(value, limit=2000):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", str(value or ""))).strip()[:limit]


def settings_enabled():
    doc = frappe.get_single(SETTINGS)
    if not doc.enabled:
        frappe.throw(_("Chat is unavailable"))
    return doc


def throttle(action, max_requests, seconds):
    # Atomic increment via Redis. Per-IP quota; deploy reverse-proxy limits too.
    ip = getattr(frappe.local, "request_ip", None)
    if not ip:
        try:
            if hasattr(frappe.local, "request") and frappe.local.request:
                ip = frappe.get_request_header("X-Real-IP")
        except Exception:
            pass
    ip = ip or "unknown"
    import hashlib
    token = hashlib.sha256(str(ip).encode()).hexdigest()[:24]
    key = f"eu_chatbot:{action}:{token}"
    redis = frappe.cache()
    count = redis.incr(key)
    if count == 1:
        redis.expire(key, seconds)
    if count > max_requests:
        frappe.throw(_("Too many requests. Please try again later."), frappe.ValidationError)


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "he", "in", "is", "it", "its", "of", "on", "that", "the",
    "to", "was", "were", "will", "with", "you", "your", "know", "can",
    "tell", "what", "who", "where", "how", "when", "why", "about", "does",
    "have", "some", "any", "which", "there", "their", "please"
}


def retrieve(question, limit=5):
    all_words = list(dict.fromkeys(re.findall(r"[a-z0-9]{2,}", question.lower())))
    meaningful = [w for w in all_words if w not in STOP_WORDS and len(w) >= 3]
    terms = meaningful or [w for w in all_words if len(w) >= 3]
    if not terms:
        terms = ["solufy", "erpnext", "services"]

    # Fast database query directly in MariaDB
    conditions = []
    score_parts = []
    params = {}
    for i, t in enumerate(terms[:6]):
        p = f"term_{i}"
        conditions.append(f"(title LIKE %({p})s OR keywords LIKE %({p})s OR question LIKE %({p})s OR answer LIKE %({p})s)")
        score_parts.append(
            f"(CASE WHEN title LIKE %({p})s THEN 5 ELSE 0 END + "
            f"CASE WHEN keywords LIKE %({p})s THEN 4 ELSE 0 END + "
            f"CASE WHEN question LIKE %({p})s THEN 3 ELSE 0 END + "
            f"CASE WHEN answer LIKE %({p})s THEN 1 ELSE 0 END)"
        )
        params[p] = f"%{t}%"

    where_sql = " OR ".join(conditions)
    score_sql = " + ".join(score_parts) if score_parts else "0"

    query = f"""
        SELECT title, answer, content, priority, ({score_sql}) AS match_score
        FROM `tabChatbot Knowledge`
        WHERE published = 1 AND ({where_sql})
        ORDER BY match_score DESC, priority DESC
        LIMIT {int(limit)}
    """
    try:
        rows = frappe.db.sql(query, params, as_dict=True)
        return [dict(title=clean(r.get("title"), 160), answer=clean(r.get("answer") or r.get("content"), 2000)) for r in rows]
    except Exception:
        return []


def provider_reply(cfg, question, knowledge):
    import time
    provider = cfg.active_provider
    timeout = min(90, max(5, cint(cfg.request_timeout) or 45))
    temperature = max(0, min(1, float(cfg.temperature or 0.3)))
    max_tokens = min(2000, max(100, cint(cfg.max_output_tokens) or 700))
    context = "\n".join(f"- {r['title']}: {r['answer']}" for r in knowledge) or "No approved information available."
    instruction = (
        "You are the official AI Assistant for ERPNext USA (https://erpnextusa.com/) and Solufy (Solufy Pvt. Ltd. / Solufy ERP — https://www.solufyerp.com/). "
        "You proudly represent ERPNext USA and Solufy as your company.\n\n"
        "ABOUT ERPNEXT USA & SOLUFY:\n"
        "• ERPNext USA (https://erpnextusa.com/) is Solufy's dedicated platform for US businesses evaluating ERPNext consulting, implementation, customization, Frappe development, training, and ongoing support.\n"
        "• Team & Mastery: Solufy is the engineering team behind ERPNext USA, with over 13+ years of continuous ERPNext & Frappe Framework engineering (since 2014) and 100+ seasoned professionals.\n"
        "• Headquarters & Delivery: 501, 5th Floor, Vihaan 273, Sargasan, Gandhinagar, Gujarat 382419, India.\n"
        "• Dedicated US Timezone Overlap: Serving US businesses remotely with guaranteed daily overlap in Eastern (EST) and Pacific (PST) business hours, a direct US phone line (+1 848-248-0021), and direct technical lead communication.\n"
        "• Trust & Ownership: Complete code and data ownership with mutual NDA and contract-backed delivery. No recurring per-user software licensing traps, no vendor lock-in.\n"
        "• Contact Information: Direct US Line: +1 (848) 248-0021 | Email: contact@solufy.in | Website: https://erpnextusa.com/\n"
        "• Public GitHub: https://github.com/Solufy-ERPNext-Apps\n\n"
        "7 CORE SERVICES ON ERPNEXT USA:\n"
        "1. ERPNext Consulting: Process discovery, fit-gap analysis, existing system review, and phased roadmap design.\n"
        "2. ERPNext Development: Bespoke Frappe applications, custom DocTypes, and business logic automation.\n"
        "3. ERPNext Implementation: Full-cycle rollout connecting people, processes, and data—configuration, migration, testing, and training.\n"
        "4. ERPNext Customization: Tailoring forms, approval workflows, custom scripts, and reports without adding technical debt.\n"
        "5. ERPNext Support & Maintenance: SLA-backed support, dedicated named engineers, proactive monitoring, regular security updates, and version upgrades.\n"
        "6. ERPNext Training: Role-based training for employees and system administrators for confident daily operations.\n"
        "7. ERPNext Integration: Connecting ERPNext with eCommerce (Shopify, WooCommerce, Amazon SP-API), Payment Gateways (Stripe, PayPal), Tax APIs (Avalara AvaTax), Logistics & Shipping (FedEx, eShipz, Delhivery), WhatsApp, and Telephony.\n\n"
        "INDUSTRIES SERVED ON ERPNEXT USA:\n"
        "Discrete & Process Manufacturing, Wholesale & Distribution, Retail & E-Commerce, Supply Chain & 3PL Logistics, Healthcare & Pharmaceuticals, Agriculture & Dairy, Non-Profits, Hospitality, and Professional Services.\n\n"
        "CRITICAL GUIDELINES:\n"
        "1. When asked about ERPNext USA, Solufy, who you are, what services you offer, or how to get a quote, enthusiastically introduce ERPNext USA (https://erpnextusa.com/) and Solufy as your company, highlighting the 13+ years of experience, US hours overlap (EST/PST), direct US phone line (+1 848-248-0021), and full code ownership.\n"
        "2. NEVER say you don't know what 'ERPNext USA' or 'Solufy' refers to! You are the official assistant for both.\n"
        "3. For general ERPNext topics (modules like Manufacturing, Accounting, CRM, HRMS, Stock, Buying, Selling, Assets, POS, etc.), answer authoritatively, helpfully, and concisely using your deep built-in ERPNext knowledge.\n"
        "4. Format answers cleanly with bullet points and bold headers for readability.\n"
        "5. For personalized consultations, quotes, or demos, warmly encourage visitors to use the 'Contact Team' tab or email contact@solufy.in / call +1 (848) 248-0021."
    )
    messages = [{"role": "system", "content": instruction + "\nAPPROVED KNOWLEDGE:\n" + context},
                {"role": "user", "content": question}]
    if provider == "OpenAI":
        key = cfg.get_password("openai_api_key", raise_exception=False) or frappe.conf.get("openai_api_key")
        if not key: raise ValueError("OpenAI key missing")
        res = requests.post("https://api.openai.com/v1/chat/completions",
            headers={"Authorization": "Bearer " + key},
            json={"model": cfg.openai_model or "gpt-4o-mini", "messages": messages,
                  "temperature": temperature, "max_tokens": max_tokens}, timeout=timeout)
        if not res.ok:
            try:
                err_msg = res.json().get("error", {}).get("message")
            except Exception:
                err_msg = res.text
            raise ValueError(f"OpenAI error ({res.status_code}): {err_msg or res.reason}")
        return res.json()["choices"][0]["message"]["content"]
    if provider == "Gemini":
        key = cfg.get_password("gemini_api_key", raise_exception=False) or frappe.conf.get("gemini_api_key")
        if not key: raise ValueError("Gemini key missing")
        configured_model = cfg.gemini_model or "gemini-3.5-flash-lite"
        candidate_models = [configured_model, "gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-2.5-flash"]
        models_to_try = list(dict.fromkeys([m for m in candidate_models if m and re.fullmatch(r"[A-Za-z0-9._-]+", m)]))
        
        last_error = None
        for m in models_to_try:
            try:
                res = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                    headers={"x-goog-api-key": key},
                    json={"systemInstruction": {"parts": [{"text": instruction + "\nAPPROVED KNOWLEDGE:\n" + context}]},
                          "contents": [{"role": "user", "parts": [{"text": question}]}],
                          "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}}, timeout=timeout)
                if res.ok:
                    parts = res.json()["candidates"][0]["content"]["parts"]
                    return "\n".join(p.get("text", "") for p in parts)
                try:
                    err_msg = res.json().get("error", {}).get("message")
                except Exception:
                    err_msg = res.text
                last_error = ValueError(f"Gemini error ({res.status_code}) on {m}: {err_msg or res.reason}")
            except requests.RequestException as e:
                last_error = e
        if last_error:
            raise last_error
    if provider == "Ollama":
        base = (cfg.ollama_url or "http://127.0.0.1:11434").rstrip("/")
        parsed = urlparse(base)
        # Restrict to loopback or HTTPS remote endpoints to reduce SSRF exposure.
        if not ((parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost")) or parsed.scheme == "https"):
            raise ValueError("Ollama URL must be local HTTP or remote HTTPS")
        if parsed.username or parsed.password or parsed.query or parsed.fragment: raise ValueError("Invalid Ollama URL")
        
        model = cfg.ollama_model or "llama3.2:1b"
        
        # Auto-check if model is installed in Ollama; if not, automatically run pull!
        from erpnextusa_ai_chatbot.setup_ollama import is_model_installed, pull_ollama_model
        if not is_model_installed(base, model):
            pulled, pull_msg = pull_ollama_model(model, base, block=True)
            if not pulled:
                raise ValueError(f"Ollama model '{model}' is missing and auto-pull failed: {pull_msg}")

        ollama_timeout = max(timeout, 120)

        # For Ollama on CPU: Keep context ultra-compact (< 200 tokens) so CPU prompt evaluation is near-instant (< 0.2s)
        is_greeting = question.lower().strip(" .!?,") in {
            "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
            "greetings", "howdy", "hola", "namaste", "what's up", "whats up"
        }
        if is_greeting:
            ollama_context = "Solufy (https://www.solufyerp.com/) & ERPNext USA (https://erpnextusa.com/) provide ERPNext implementation, consulting, customization, and support."
            num_predict = 40
        else:
            compact_snippets = []
            for item in knowledge[:2]:
                ans_text = clean(item.get("answer") or "", 300)
                if ans_text:
                    compact_snippets.append(f"• {item['title']}: {ans_text}")
            ollama_context = "\n".join(compact_snippets) or "Solufy provides ERPNext Consulting, Implementation, Development, and Support."
            num_predict = min(max_tokens, 140)

        ollama_instruction = (
            "You are the official AI Assistant for ERPNext USA (https://erpnextusa.com/) and Solufy (https://www.solufyerp.com/). "
            "Company highlights: 13+ years continuous Frappe/ERPNext mastery, 100+ engineers, EST/PST US hours overlap, direct US line +1 (848) 248-0021. "
            "Provide a helpful, direct, and concise answer (2-3 bullet points or short sentences) using the context below."
        )
        ollama_messages = [
            {"role": "system", "content": f"{ollama_instruction}\nCONTEXT:\n{ollama_context}"},
            {"role": "user", "content": question}
        ]

        res = requests.post(base + "/api/chat", json={
            "model": model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
                "num_thread": 6
            }
        }, timeout=ollama_timeout)
        if not res.ok:
            try:
                err_msg = res.json().get("error")
            except Exception:
                err_msg = res.text
            raise ValueError(f"Ollama error ({res.status_code}): {err_msg or res.reason}")
        return res.json()["message"]["content"]
    raise ValueError("Unsupported provider")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def chat(message=None, session_id=None):
    throttle("chat", 15, 60)
    message = clean(message)
    if not message: frappe.throw(_("Enter a message"))
    cfg = settings_enabled()
    kb = retrieve(message, min(10, max(1, cint(cfg.max_knowledge_results) or 5)))
    try:
        answer = provider_reply(cfg, message, kb)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "ERPNextUSA Chat Provider")
        frappe.throw(_("The assistant is temporarily unavailable"))
    sid = clean(session_id, 100) if session_id else uuid.uuid4().hex
    try:
        frappe.get_doc({"doctype": "Chatbot Conversation", "session_id": sid,
            "visitor_message": message, "assistant_message": clean(answer, 8000),
            "provider": cfg.active_provider}).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "ERPNextUSA Chat Logging")
    return {"answer": answer, "session_id": sid}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def submit_lead(name=None, email=None, phone=None, message=None, consent=0):
    throttle("lead", 3, 3600)
    cfg = settings_enabled()
    if not cint(consent): frappe.throw(_("Consent is required"))
    name, email, phone, message = clean(name, 140), clean(email, 140), clean(phone, 40), clean(message)
    if not name or not frappe.utils.validate_email_address(email, throw=False):
        frappe.throw(_("Enter a name and valid email"))
    if not frappe.db.exists("DocType", "Lead"):
        frappe.throw(_("ERPNext Lead is not installed"))
    values = {"doctype": "Lead", "lead_name": name, "email_id": email, "mobile_no": phone}
    if message:
        user = getattr(getattr(frappe, "session", None), "user", None)
        if not user or user == "Guest":
            user = "Administrator"
        values["notes"] = [{
            "note": frappe.utils.escape_html(message),
            "added_by": user,
            "added_on": frappe.utils.now(),
        }]
    source = cfg.lead_source or "Website"
    if frappe.db.has_column("Lead", "source"):
        values["source"] = source
    lead = frappe.get_doc(values)
    lead.insert(ignore_permissions=True)
    # Do not return a predictable CRM record ID to unauthenticated visitors.
    return {"success": True}


@frappe.whitelist(methods=["POST"])
def test_provider():
    if not frappe.has_permission(SETTINGS, "write"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    cfg = frappe.get_single(SETTINGS)
    try:
        reply = provider_reply(cfg, "Reply with: connection successful", [])
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "ERPNextUSA Provider Test")
        frappe.throw(_("Provider test failed: {0}").format(str(e)))
    return {"success": True, "response": clean(reply, 300)}
