import hashlib
import re
import uuid
import html
from urllib.parse import urlparse

import frappe
import requests
from frappe import _
from frappe.utils import cint

from erpnextusa_ai_chatbot.setup_ollama import DEFAULT_OLLAMA_MODEL

SETTINGS = "Chatbot Settings"
CONSULTANT_LIMIT = 4
DEFAULT_CONTACT_EMAIL = "contact@solufy.in"
DEFAULT_CONTACT_PHONE = "+1 (848) 248-0021"


def clean(value, limit=8000, preserve_lines=False):
    if not value:
        return ""
    val = re.sub(
        r"<(script|style)[^>]*>.*?</\1>",
        "",
        str(value),
        flags=re.DOTALL | re.IGNORECASE,
    )
    val = re.sub(r"<[^>]*>", " ", val)
    if preserve_lines:
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in val.splitlines()]
        val = "\n".join(lines)
        val = re.sub(r"\n{3,}", "\n\n", val).strip()
    else:
        val = re.sub(r"\s+", " ", val).strip()
    return val[:limit]


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
        frappe.throw(
            _("Too many requests. Please try again later."), frappe.ValidationError
        )


STOP_WORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "also",
    "an",
    "and",
    "any",
    "are",
    "aren't",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can",
    "can't",
    "cannot",
    "could",
    "couldn't",
    "company",
    "did",
    "didn't",
    "do",
    "does",
    "doesn't",
    "doing",
    "don't",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "get",
    "gets",
    "getting",
    "give",
    "gives",
    "giving",
    "good",
    "had",
    "hadn't",
    "has",
    "hasn't",
    "have",
    "haven't",
    "having",
    "he",
    "he'd",
    "he'll",
    "he's",
    "help",
    "her",
    "here",
    "here's",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "how's",
    "i",
    "i'd",
    "i'll",
    "i'm",
    "i've",
    "if",
    "in",
    "into",
    "is",
    "isn't",
    "it",
    "it's",
    "its",
    "itself",
    "just",
    "know",
    "let's",
    "like",
    "make",
    "makes",
    "making",
    "many",
    "me",
    "more",
    "most",
    "much",
    "mustn't",
    "my",
    "myself",
    "need",
    "no",
    "nor",
    "not",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "ought",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "please",
    "same",
    "say",
    "says",
    "see",
    "shall",
    "shan't",
    "she",
    "she'd",
    "she'll",
    "she's",
    "should",
    "shouldn't",
    "so",
    "some",
    "solufy",
    "such",
    "summarize",
    "summarized",
    "summary",
    "summurized",
    "tell",
    "than",
    "that",
    "that's",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "there's",
    "these",
    "they",
    "they'd",
    "they'll",
    "they're",
    "they've",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "use",
    "uses",
    "using",
    "very",
    "was",
    "wasn't",
    "we",
    "we'd",
    "we'll",
    "we're",
    "we've",
    "were",
    "weren't",
    "what",
    "what's",
    "when",
    "when's",
    "where",
    "where's",
    "which",
    "while",
    "who",
    "who's",
    "whom",
    "why",
    "why's",
    "will",
    "with",
    "won't",
    "work",
    "works",
    "working",
    "would",
    "wouldn't",
    "you",
    "you'd",
    "you'll",
    "you're",
    "you've",
    "your",
    "yours",
}


def retrieve(question, limit=5):
    knowledge = frappe.qb.DocType("Chatbot Knowledge")
    question = _normalize_search_question(question)
    normalized_question = " ".join(question.lower().split())
    learned = (
        frappe.qb.from_(knowledge)
        .select(
            knowledge.title,
            knowledge.answer,
            knowledge.content,
            knowledge.category,
            knowledge.keywords,
            knowledge.question,
            knowledge.priority,
            knowledge.likes,
        )
        .where(
            (knowledge.published == 1)
            & (knowledge.category == "Chat Feedback")
            & (knowledge.question == normalized_question)
        )
        .orderby(knowledge.modified, order=frappe.qb.desc)
        .limit(1)
    ).run(as_dict=True)
    if learned:
        return [_knowledge_result(learned[0], match_score=1000)]

    all_words = list(dict.fromkeys(re.findall(r"[a-z0-9]{3,}", question.lower())))
    meaningful = [w for w in all_words if w not in STOP_WORDS and len(w) >= 3]
    if not meaningful:
        return []

    terms = meaningful[:6]
    matches = None
    for term in terms:
        pattern = f"%{term}%"
        term_match = (
            knowledge.title.like(pattern)
            | knowledge.keywords.like(pattern)
            | knowledge.question.like(pattern)
            | knowledge.answer.like(pattern)
        )
        matches = term_match if matches is None else matches | term_match

    rows = (
        frappe.qb.from_(knowledge)
        .select(
            knowledge.title,
            knowledge.answer,
            knowledge.content,
            knowledge.category,
            knowledge.keywords,
            knowledge.question,
            knowledge.priority,
            knowledge.likes,
        )
        .where((knowledge.published == 1) & matches)
        .limit(200)
    ).run(as_dict=True)
    ranked = sorted(
        (_knowledge_result(row, _knowledge_score(row, terms)) for row in rows),
        key=lambda row: (row["match_score"], row["priority"]),
        reverse=True,
    )
    relevant = [row for row in ranked if row["match_score"] >= 4]
    return _prioritize_knowledge_results(question, relevant)[:limit]


def _normalize_search_question(question: str) -> str:
    text = clean(question, 1000).lower()
    corrections = {
        "chemicle": "chemical",
        "summurized": "summarized",
        "takel": "tackle",
    }
    for typo, correction in corrections.items():
        text = re.sub(rf"\b{typo}\b", correction, text)
    return text


def _prioritize_knowledge_results(question: str, results: list[dict]) -> list[dict]:
    words = set(re.findall(r"[a-z0-9]+", question.lower()))
    wants_article = bool(words & {"article", "blog", "guide", "insight", "read"})
    if wants_article:
        preferred_categories = {"Blog"}
    elif words & {"team", "consultant", "consultants", "staff", "person", "people"}:
        preferred_categories = {"Team"}
    elif words & {"industry", "industries", "manufacturing", "chemical"}:
        preferred_categories = {"Industry"}
    else:
        preferred_categories = {"Service", "Industry", "Team", "Case Study"}

    return sorted(
        results,
        key=lambda row: (
            row.get("category") in preferred_categories,
            row.get("category") != "Blog" if not wants_article else True,
            row.get("match_score", 0),
            row.get("priority", 0),
        ),
        reverse=True,
    )


def _knowledge_score(row, terms):
    fields = {
        "title": str(row.get("title") or "").lower(),
        "keywords": str(row.get("keywords") or "").lower(),
        "question": str(row.get("question") or "").lower(),
        "answer": str(row.get("answer") or row.get("content") or "").lower(),
    }
    score = 0
    for term in terms:
        word = re.compile(rf"\b{re.escape(term)}\b")
        score += 15 if word.search(fields["title"]) else 0
        score += 10 if word.search(fields["keywords"]) else 0
        score += 8 if word.search(fields["question"]) else 0
        score += 2 if word.search(fields["answer"]) else 0
        if row.get("category") in ("Industry", "Service") and word.search(
            fields["title"]
        ):
            score += 5
    return score + min(cint(row.get("likes")) * 0.5, 3)


def _knowledge_result(row, match_score=None):
    return {
        "title": clean(row.get("title"), 160),
        "question": clean(row.get("question"), 300),
        "answer": clean(
            row.get("answer") or row.get("content"), 8000, preserve_lines=True
        ),
        "category": clean(row.get("category"), 140),
        "priority": cint(row.get("priority")),
        "likes": cint(row.get("likes")),
        "match_score": float(
            match_score if match_score is not None else row.get("match_score") or 0
        ),
    }


def _is_greeting(message):
    return clean(message).lower().strip(" .!?,") in {
        "hi",
        "hello",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
        "greetings",
        "howdy",
        "hola",
        "namaste",
        "what's up",
        "whats up",
    }


def _remove_unrequested_greeting(message, answer):
    if _is_greeting(message):
        return answer
    return re.sub(
        r"^(?:hello|hi|hey)(?:\s+there)?[!,.:\s-]*",
        "",
        answer or "",
        count=1,
        flags=re.IGNORECASE,
    ).lstrip()


def provider_reply(cfg, question, knowledge, requested_model=None, country=""):
    import time

    provider = cfg.active_provider
    if requested_model:
        rm = str(requested_model).lower()
        if "gemini" in rm:
            provider = "Gemini"
        elif "llama" in rm or "ollama" in rm:
            provider = "Ollama"
        elif "openai" in rm or "gpt" in rm:
            provider = "OpenAI"

    timeout = min(90, max(5, cint(cfg.request_timeout) or 45))
    temperature = max(0, min(1, float(cfg.temperature or 0.3)))
    max_tokens = min(2000, max(100, cint(cfg.max_output_tokens) or 700))
    context = (
        "\n".join(f"- {r['title']}: {r['answer']}" for r in knowledge)
        if knowledge
        else ""
    )
    if knowledge and knowledge[0].get("category") == "Chat Feedback":
        learned_answer = knowledge[0].get("answer") or knowledge[0].get("content")
        if learned_answer:
            return learned_answer
    instruction = (
        "You are the official AI Assistant for ERPNext USA. "
        "Explain the approved website content clearly and in plain language.\n\n"
        "RESPONSE RULES:\n"
        "• APPROVED KNOWLEDGE is the only source for factual claims. Never add facts from general model knowledge or memory.\n"
        "• If APPROVED KNOWLEDGE does not answer the question, say that the information is not available in the published website knowledge.\n"
        "• Tone: Enthusiastic, witty, friendly, and charmingly passionate about ERPNext and Frappe!\n"
        "• Answer the user's actual question. Do not reuse an unrelated industry or module answer.\n"
        "• Limit the scope to the supplied published ERPNext USA website knowledge.\n"
        "• Never write or generate source code, scripts, commands, formulas, or implementation snippets.\n"
        "• Do not recommend configurations, settings, custom fields, workflows, integrations, architecture, or implementation ideas.\n"
        "• If asked for code or configuration advice, politely state that you can explain the relevant standard Frappe or ERPNext concept, then give only that explanation.\n"
        "• If a question is unrelated to Frappe, ERPNext, or Solufy, say that your scope is Frappe and ERPNext knowledge and ask for a related question.\n"
        "• Keep answers concise and vary the wording to suit the question without changing the approved facts.\n"
        "• Formatting: Use clean markdown, bold highlights, and friendly bullet points."
    )
    if country:
        instruction += (
            f"\n\nVISITOR COUNTRY: {country}. Use relevant country terminology and approved "
            "country-specific knowledge when available. Do not invent tax, legal, pricing, office, "
            "partner, or compliance claims. Include a relevant approved source link when the knowledge provides one."
        )

    is_greeting = _is_greeting(question)
    if is_greeting:
        return (
            "Hello! I am your AI ERP Assistant for **ERPNext USA** (https://erpnextusa.com/) and **Solufy** (https://www.solufyerp.com/).\n\n"
            "I can explain Frappe, ERPNext, their standard modules, and Solufy's approved services. "
            "I do not provide code or configuration recommendations. What would you like to learn?"
        )

    def _call_openai():
        key = cfg.get_password(
            "openai_api_key", raise_exception=False
        ) or frappe.conf.get("openai_api_key")
        if not key:
            raise ValueError("OpenAI key missing")
        sys_msg = instruction + ("\nAPPROVED KNOWLEDGE:\n" + context if context else "")
        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": question},
        ]
        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": "Bearer " + key},
            json={
                "model": cfg.openai_model or "gpt-4o-mini",
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=timeout,
        )
        if not res.ok:
            try:
                err_msg = res.json().get("error", {}).get("message")
            except Exception:
                err_msg = res.text
            raise ValueError(
                f"OpenAI error ({res.status_code}): {err_msg or res.reason}"
            )
        return res.json()["choices"][0]["message"]["content"]

    def _call_gemini():
        key = cfg.get_password(
            "gemini_api_key", raise_exception=False
        ) or frappe.conf.get("gemini_api_key")
        if not key:
            raise ValueError("Gemini key missing")
        configured_model = cfg.gemini_model or "gemini-3.5-flash-lite"
        candidate_models = [
            configured_model,
            "gemini-3.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-flash-latest",
            "gemini-2.0-flash",
        ]
        models_to_try = list(
            dict.fromkeys(
                [
                    m
                    for m in candidate_models
                    if m and re.fullmatch(r"[A-Za-z0-9._-]+", m)
                ]
            )
        )
        last_error = None
        for m in models_to_try:
            try:
                sys_text = instruction + (
                    "\nAPPROVED KNOWLEDGE:\n" + context if context else ""
                )
                res = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                    headers={"x-goog-api-key": key},
                    json={
                        "systemInstruction": {"parts": [{"text": sys_text}]},
                        "contents": [{"role": "user", "parts": [{"text": question}]}],
                        "generationConfig": {
                            "temperature": temperature,
                            "maxOutputTokens": max_tokens,
                        },
                    },
                    timeout=min(timeout, 30),
                )
                if res.ok:
                    parts = res.json()["candidates"][0]["content"]["parts"]
                    return "\n".join(p.get("text", "") for p in parts)
                try:
                    err_msg = res.json().get("error", {}).get("message")
                except Exception:
                    err_msg = res.text
                last_error = ValueError(
                    f"Gemini error ({res.status_code}) on {m}: {err_msg or res.reason}"
                )
            except requests.RequestException as e:
                last_error = e
        if last_error:
            raise last_error

    def _call_ollama():
        base = (cfg.ollama_url or "http://127.0.0.1:11434").rstrip("/")
        parsed = urlparse(base)
        if not (
            (parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost"))
            or parsed.scheme == "https"
        ):
            raise ValueError("Ollama URL must be local HTTP or remote HTTPS")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Invalid Ollama URL")

        model = cfg.ollama_model or DEFAULT_OLLAMA_MODEL

        ollama_instruction = (
            "You are the official AI assistant for Solufy and ERPNext USA. "
            "Give clear, accurate knowledge about Frappe, ERPNext, their standard modules, and approved Solufy services.\n"
            "Answer the user's exact question and do not repeat an unrelated answer. "
            "Never generate source code, scripts, commands, formulas, or implementation snippets. "
            "Do not suggest configurations, settings, custom fields, workflows, integrations, architecture, or implementation ideas. "
            "When asked for code or configuration help, politely offer only a factual explanation of the relevant standard concept. "
            "For unrelated questions, state that your scope is Frappe and ERPNext knowledge. "
            "Keep the answer friendly, specific, and under 140 words."
        )
        if country:
            ollama_instruction += (
                f"\nVisitor country: {country}. Use country-relevant approved context only; "
                "do not invent tax, legal, pricing, or compliance claims."
            )
        if context:
            compact_snippets = []
            for item in knowledge[:2]:
                ans_text = clean(item.get("answer") or item.get("content") or "", 160)
                if ans_text:
                    compact_snippets.append(f"• {item['title']}: {ans_text}")
            ollama_instruction += f"\n\nRELEVANT CONTEXT:\n" + "\n".join(
                compact_snippets
            )

        ollama_messages = [
            {"role": "system", "content": ollama_instruction},
            {"role": "user", "content": question},
        ]

        # Keep enough context and output space for distinct, question-specific answers.
        res = requests.post(
            base + "/api/chat",
            json={
                "model": model,
                "messages": ollama_messages,
                "stream": False,
                "think": True,
                "keep_alive": "60m",
                "options": {
                    "temperature": 0.2,
                    "num_predict": 768,
                    "num_ctx": 4096,
                    "num_thread": 4,
                },
            },
            timeout=max(timeout, 180),
        )
        if res.ok:
            return res.json()["message"]["content"]
        raise ValueError(f"Ollama error: {res.text}")

    if provider == "OpenAI":
        try:
            return _call_openai()
        except Exception:
            if frappe.conf.get("gemini_api_key") or cfg.get_password(
                "gemini_api_key", raise_exception=False
            ):
                return _call_gemini()
            raise
    elif provider == "Gemini":
        try:
            return _call_gemini()
        except Exception:
            try:
                return _call_ollama()
            except Exception:
                raise
    elif provider == "Ollama":
        try:
            return _call_ollama()
        except Exception:
            if frappe.conf.get("gemini_api_key") or cfg.get_password(
                "gemini_api_key", raise_exception=False
            ):
                try:
                    return _call_gemini()
                except Exception:
                    pass
            raise

    raise ValueError("Unsupported provider")


def format_answer_links(text):
    if not text:
        return text

    # Transform explicit lines like "Explore the solution at: https://erpnextusa.com/industries/xyz"
    def _rep_labeled(match):
        url = match.group(1).strip()
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        slug = path.split("/")[-1] if path else "Solution"
        friendly = (
            slug.replace("erpnext-for-", "")
            .replace("erpnext-", "")
            .replace("-", " ")
            .title()
        )
        friendly_label = (
            f"ERPNext for {friendly}"
            if not friendly.lower().startswith("erpnext")
            else friendly
        )
        return f"👉 **[{friendly_label}](/{path})**"

    text = re.sub(
        r"(?:Explore the solution at|Read full case study|Read full guide at|Learn more at)[:\s]+(https?://(?:www\.)?erpnextusa\.com/([a-zA-Z0-9_\-\/]+))",
        _rep_labeled,
        text,
        flags=re.IGNORECASE,
    )

    # Transform any remaining bare erpnextusa.com URLs that are NOT preceded by ](
    def _rep_bare(match):
        url = match.group(0).strip()
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        if not path:
            return "[ERPNext USA](/)"
        slug = path.split("/")[-1]
        friendly = (
            slug.replace("erpnext-for-", "")
            .replace("erpnext-", "")
            .replace("-", " ")
            .title()
        )
        return f"[👉 {friendly}](/{path})"

    text = re.sub(
        r"(?<!\]\()(https?://(?:www\.)?erpnextusa\.com/([a-zA-Z0-9_\-\/]+))",
        _rep_bare,
        text,
    )
    return text


def detect_lead_intent(message, answer=""):
    combined = (str(message or "") + " " + str(answer or "")).lower()
    keywords = [
        "quote",
        "estimate",
        "pricing",
        "cost",
        "implement",
        "proposal",
        "demo",
        "contact",
        "hire",
        "consultation",
        "discovery",
        "talk to",
        "speak with",
        "reach out",
        "call me",
        "get in touch",
        "custom app",
        "start project",
        "services",
        "support",
        "help",
        "yes",
        "sure",
        "schedule",
        "need",
    ]
    return any(k in combined for k in keywords)


FOLLOW_UP_TOPICS = (
    (
        ("manufactur", "bom", "shop floor", "mrp", "work order", "routing"),
        (
            "How would ERPNext map our manufacturing workflow?",
            "Which manufacturing data should we prepare before implementation?",
        ),
    ),
    (
        ("inventory", "stock", "warehouse", "barcode", "serial", "batch"),
        (
            "How can ERPNext improve our inventory accuracy?",
            "Which warehouse and item details are needed to plan this setup?",
        ),
    ),
    (
        ("account", "finance", "invoice", "payment", "tax", "bookkeep"),
        (
            "How would ERPNext fit our accounting and invoicing process?",
            "What financial data can Solufy migrate into ERPNext?",
        ),
    ),
    (
        ("crm", "sales", "lead", "customer", "pipeline"),
        (
            "How can ERPNext automate our sales and CRM workflow?",
            "Which reports would help us track leads and customers?",
        ),
    ),
    (
        ("human resource", "payroll", "employee", "attendance", "leave"),
        (
            "How can ERPNext streamline our HR and payroll process?",
            "Which employee records are required for migration?",
        ),
    ),
    (
        ("tea", "coffee", "recipe", "food", "beverage", "dairy", "cook", "bake"),
        (
            "How would ERPNext manage our recipes, batches, and expiry dates?",
            "Which food manufacturing and quality checks can be automated?",
        ),
    ),
    (
        ("bottle", "mobile", "gadget", "product", "item", "hardware", "device"),
        (
            "How would ERPNext track our products, serial numbers, and barcodes?",
            "Can our ecommerce channels be connected with ERPNext inventory?",
        ),
    ),
    (
        ("quote", "price", "cost", "pricing", "estimate", "budget"),
        (
            "What details do you need to prepare an implementation estimate?",
            "Which factors affect the ERPNext project cost and timeline?",
        ),
    ),
    (
        ("implement", "setup", "rollout", "migration", "start"),
        (
            "What does an ERPNext implementation mean?",
            "What is data migration in ERPNext?",
        ),
    ),
    (
        ("custom", "develop", "app", "workflow", "integration", "frappe", "api"),
        (
            "What is the Frappe Framework?",
            "What is the difference between Frappe and ERPNext?",
        ),
    ),
    (
        ("support", "sla", "maintain", "issue", "bug", "error"),
        (
            "How would Solufy investigate this issue in our ERPNext setup?",
            "What ongoing support would fit our team and system?",
        ),
    ),
)


def build_follow_up_options(message, knowledge=None):
    """Return questions from the matched website-owned knowledge."""
    questions = [
        clean(item.get("question"), 300)
        for item in (knowledge or [])
        if clean(item.get("question"), 300)
    ]
    return list(
        dict.fromkeys(
            [*questions[:2], "What is ERPNext?", "What is the Frappe Framework?"]
        )
    )[:3]


def _follow_up_topic(message, knowledge):
    words = re.findall(r"[a-z0-9]+", clean(message, 300).lower())
    meaningful = [word for word in words if word not in STOP_WORDS and len(word) > 2]
    if meaningful:
        return " ".join(meaningful[:4])

    for item in knowledge:
        title = clean(item.get("title"), 80).lower()
        if title:
            return title
    return ""


def is_consultant_request(message: str) -> bool:
    text = str(message or "").lower()
    phrases = (
        "sales person",
        "salesperson",
        "sales representative",
        "sales rep",
        "sales team",
        "contact sales",
        "talk to sales",
        "speak to sales",
        "talk to a consultant",
        "speak to a consultant",
        "consultant profile",
        "show consultants",
        "meet consultants",
        "erp consultant",
        "consulting team",
        "consulting staff",
    )
    return any(phrase in text for phrase in phrases)


def is_restricted_technical_request(message: str) -> bool:
    text = clean(message, 1000).lower()
    action_terms = (
        "write code",
        "generate code",
        "source code",
        "code for",
        "code to",
        "python code",
        "javascript code",
        "script for",
        "create a script",
        "implement this",
        "how to configure",
        "how do i configure",
        "configuration idea",
        "configuration suggestion",
        "suggest a configuration",
        "which setting",
        "custom field",
        "custom workflow",
    )
    return any(term in text for term in action_terms)


def restricted_technical_answer(message: str) -> str:
    text = clean(message, 1000).lower()
    if "workflow" in text:
        concept = (
            "In Frappe and ERPNext, a workflow represents controlled document states and "
            "role-based transitions, such as Draft, Pending Approval, and Approved."
        )
    elif "field" in text:
        concept = (
            "A field stores one defined piece of data on a Frappe DocType, while the DocType "
            "describes the complete business record."
        )
    else:
        concept = (
            "Frappe is the application framework, and ERPNext is the business application "
            "built on it."
        )
    return (
        "I can explain standard Frappe and ERPNext concepts, but I cannot provide code, "
        f"scripts, or configuration recommendations. {concept}"
    )


def canonical_knowledge_answer(message: str, knowledge: list[dict]) -> str:
    normalized = re.sub(r"[^a-z0-9 ]", " ", clean(message, 300).lower())
    normalized = " ".join(normalized.split())
    expected_title = ""
    if normalized in (
        "what is erpnext",
        "explain erpnext",
        "define erpnext",
        "tell me about erpnext",
    ):
        expected_title = "What ERPNext Is"
    elif normalized in (
        "what is frappe",
        "what is frappe framework",
        "what is the frappe framework",
        "explain frappe",
        "tell me about frappe",
    ):
        expected_title = "What the Frappe Framework Is"

    for item in knowledge:
        if item.get("title") == expected_title:
            return item.get("answer") or ""
    return ""


def get_public_consultants() -> list[dict]:
    required_doctypes = ("Website Team Member", "Website Team Member Role")
    if not all(frappe.db.exists("DocType", doctype) for doctype in required_doctypes):
        return []

    consultant_names = frappe.get_all(
        "Website Team Member Role",
        filters={"team_role": "Consultant", "parenttype": "Website Team Member"},
        pluck="parent",
        limit_page_length=100,
    )
    if not consultant_names:
        return []

    fields = [
        "full_name",
        "designation",
        "photo",
        "photo_alt_text",
        "email",
        "phone",
        "whatsapp_number",
        "slug",
    ]
    rows = frappe.get_all(
        "Website Team Member",
        filters={"published": 1, "name": ["in", consultant_names]},
        fields=fields,
        order_by="display_order asc, full_name asc",
        limit_page_length=CONSULTANT_LIMIT,
    )
    return [
        {
            "name": clean(row.full_name, 140),
            "designation": clean(row.designation, 160) or "ERPNext Consultant",
            "photo": row.photo or "",
            "photo_alt_text": clean(row.photo_alt_text, 160)
            or clean(row.full_name, 140),
            "email": clean(row.email, 140) or DEFAULT_CONTACT_EMAIL,
            "phone": clean(row.phone or row.whatsapp_number, 40)
            or DEFAULT_CONTACT_PHONE,
            "profile_url": f"/team#{row.slug}",
        }
        for row in rows
    ]


def is_page_context_request(message: str) -> bool:
    text = clean(message, 500).lower()
    return any(
        phrase in text
        for phrase in (
            "this page",
            "current page",
            "summarize page",
            "summarize the page",
            "page summary",
            "page summarized",
        )
    )


def is_company_summary_request(message: str) -> bool:
    text = clean(message, 500).lower()
    asks_for_summary = any(stem in text for stem in ("summar", "summur"))
    asks_about_solufy = "solufy" in text or "company" in text
    return asks_for_summary and asks_about_solufy


def company_summary_answer() -> str:
    return (
        "**Solufy is an ERPNext and Frappe consulting and implementation team.**\n\n"
        "It helps businesses plan, implement, customize, integrate, and support ERPNext "
        "around their operating workflows, with working-hour overlap for US businesses.\n\n"
        "👉 [Learn more about Solufy](/about)"
    )


def get_page_knowledge(page: str) -> list[dict]:
    source_url = _page_source_url(page)
    if not source_url:
        return []

    rows = frappe.get_all(
        "Chatbot Knowledge",
        filters={"published": 1, "source_url": source_url},
        fields=[
            "title",
            "answer",
            "content",
            "category",
            "keywords",
            "question",
            "priority",
            "likes",
        ],
        limit_page_length=1,
    )
    return [_knowledge_result(rows[0], match_score=1000)] if rows else []


def _page_source_url(page: str) -> str:
    path = urlparse(clean(page, 500)).path.strip("/")
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        return ""

    source_doctype = {
        "industries": "Website Industry",
        "services": "Website Service",
        "case-studies": "Case Study",
        "blog": "Blog Post",
    }.get(parts[0])
    if not source_doctype:
        return ""
    return f"auto:{source_doctype}:{parts[-1]}"[:140]


def summarize_page_answer(answer: str) -> str:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", answer) if block.strip()]
    if len(blocks) <= 3:
        return answer

    summary = blocks[:3]
    if re.search(r"\[[^\]]+\]\([^)]+\)", blocks[-1]):
        summary.append(blocks[-1])
    return "\n\n".join(summary)


def page_metadata_answer(title: str, heading: str, description: str) -> str:
    title = clean(title, 200)
    heading = clean(heading, 300)
    description = clean(description, 700)
    if not any((title, heading, description)):
        return (
            "I cannot identify enough published content on this page to summarize it."
        )

    blocks = [f"**{heading or title}**"]
    if description:
        blocks.append(description)
    elif title and heading and title != heading:
        blocks.append(title)
    return "\n\n".join(blocks)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def chat(
    message=None,
    session_id=None,
    model=None,
    country=None,
    page=None,
    page_title=None,
    page_heading=None,
    page_description=None,
    **kwargs,
):
    throttle("chat", 60, 60)
    message = clean(message)
    if not message:
        frappe.throw(_("Enter a message"))
    cfg = settings_enabled()
    country = _visitor_country(country)
    kb = []
    answer = ""
    page_context = is_page_context_request(message)
    consultant_profiles = (
        get_public_consultants() if is_consultant_request(message) else []
    )
    if consultant_profiles:
        answer = "Here is Solufy's consulting team."
    elif is_company_summary_request(message):
        answer = company_summary_answer()
    elif _is_greeting(message):
        answer = (
            "Hello! I can help with information published on ERPNext USA about "
            "ERPNext and Frappe. What would you like to know?"
        )
    else:
        limit = min(10, max(1, cint(cfg.max_knowledge_results) or 5))
        kb = get_page_knowledge(page) if page_context else []
        if page_context and kb:
            answer = summarize_page_answer(kb[0].get("answer") or "")
        elif page_context:
            answer = page_metadata_answer(
                page_title, page_heading, page_description
            )
        else:
            kb = _retrieve_for_country(message, country, limit)
            answer = canonical_knowledge_answer(message, kb)
    if not answer and kb:
        answer = kb[0].get("answer") or kb[0].get("content") or ""
    if not answer:
        answer = (
            "I can help with Solufy, ERPNext, Frappe, services, industries, case studies, "
            "and other published ERPNext USA website content. I could not match that "
            "message to this knowledge, so please ask a related question."
        )

    answer = _remove_unrequested_greeting(message, answer)
    answer = format_answer_links(answer)
    sid = clean(session_id, 100) if session_id else uuid.uuid4().hex
    try:
        frappe.get_doc(
            {
                "doctype": "Chatbot Conversation",
                "session_id": sid,
                "visitor_message": message,
                "assistant_message": clean(answer, 8000),
                "provider": cfg.active_provider,
            }
        ).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "ERPNextUSA Chat Logging")

    res_data = {"answer": answer, "session_id": sid}
    if consultant_profiles:
        res_data["consultant_profiles"] = consultant_profiles
        res_data["consultant_batch_size"] = CONSULTANT_LIMIT
        res_data["suggest_lead"] = False
        return res_data

    res_data["suggest_lead"] = False
    res_data["lead_prompt"] = "Related website knowledge:"
    res_data["lead_options"] = build_follow_up_options(message, kb)
    return res_data


def _visitor_country(country):
    country = re.sub(r"[^A-Za-z .'-]", "", clean(country, 60)).strip()
    if country:
        return country
    request = getattr(frappe, "request", None)
    if request and getattr(request, "cookies", None):
        return re.sub(
            r"[^A-Za-z .'-]",
            "",
            clean(request.cookies.get("solufy_country"), 60),
        ).strip()
    return ""


def _retrieve_for_country(message, country, limit):
    knowledge = retrieve(message, limit)
    if not country or not knowledge:
        return knowledge

    country_knowledge = retrieve(f"{message} {country}", limit)
    merged = []
    seen = set()
    # The visitor's question is the primary signal. Country enrichment must not
    # outrank a relevant result merely because a company or article contains the
    # country name.
    for item in [*knowledge, *country_knowledge]:
        key = (item.get("title"), item.get("answer"))
        if key not in seen:
            seen.add(key)
            merged.append(item)
    return merged[:limit]


@frappe.whitelist(allow_guest=True, methods=["POST"])
def submit_lead(name=None, email=None, phone=None, message=None, consent=0):
    throttle("lead", 20, 3600)
    cfg = settings_enabled()
    if not cint(consent):
        frappe.throw(_("Consent is required"))
    name, email, phone, message = (
        clean(name, 140),
        clean(email, 140),
        clean(phone, 40),
        clean(message),
    )
    if not name or not frappe.utils.validate_email_address(email, throw=False):
        frappe.throw(_("Enter a name and valid email"))
    if not frappe.db.exists("DocType", "Lead"):
        frappe.throw(_("ERPNext Lead is not installed"))
    values = {
        "doctype": "Lead",
        "lead_name": name,
        "email_id": email,
        "mobile_no": phone,
    }
    if message:
        user = getattr(getattr(frappe, "session", None), "user", None)
        if not user or user == "Guest":
            user = "Administrator"
        values["notes"] = [
            {
                "note": frappe.utils.escape_html(message),
                "added_by": user,
                "added_on": frappe.utils.now(),
            }
        ]
    source = cfg.lead_source or "Website"
    if frappe.db.has_column("Lead", "source"):
        values["source"] = source
    lead = frappe.get_doc(values)
    lead.insert(ignore_permissions=True)
    # Do not return a predictable CRM record ID to unauthenticated visitors.
    return {"success": True}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def like_response(session_id=None, message=None, answer=None, liked=1):
    throttle("like", 60, 60)
    session_id = clean(session_id, 100)
    message = clean(message, 1000)
    answer = clean(answer, 2000)
    is_liked = cint(liked)
    conversation = _get_feedback_conversation(session_id, message, answer)
    if not conversation:
        frappe.throw(
            _("The chat response could not be verified"), frappe.ValidationError
        )

    conversation_table = frappe.qb.DocType("Chatbot Conversation")
    (
        frappe.qb.update(conversation_table)
        .set(conversation_table.liked, is_liked)
        .where(conversation_table.name == conversation.name)
    ).run()
    matched_id = _sync_learned_response(message, answer, is_liked)

    return {"success": True, "liked": is_liked, "knowledge_id": matched_id}


def _get_feedback_conversation(session_id: str, message: str, answer: str):
    if not session_id or not message or not answer:
        return None

    conversation = frappe.qb.DocType("Chatbot Conversation")
    rows = (
        frappe.qb.from_(conversation)
        .select(conversation.name)
        .where(
            (conversation.session_id == session_id)
            & (conversation.visitor_message == message)
            & (conversation.assistant_message == answer)
        )
        .orderby(conversation.creation, order=frappe.qb.desc)
        .limit(1)
    ).run(as_dict=True)
    return rows[0] if rows else None


def _sync_learned_response(message: str, answer: str, liked: int) -> str | None:
    normalized_question = " ".join(message.lower().split())
    feedback_key = hashlib.sha256(normalized_question.encode()).hexdigest()[:24]
    source_url = f"chat-feedback:{feedback_key}"
    knowledge = frappe.qb.DocType("Chatbot Knowledge")
    existing_rows = (
        frappe.qb.from_(knowledge)
        .select(knowledge.name)
        .where(knowledge.source_url == source_url)
        .limit(1)
    ).run(as_dict=True)
    existing = existing_rows[0].name if existing_rows else None

    if not liked:
        if existing:
            (
                frappe.qb.update(knowledge)
                .set(knowledge.published, 0)
                .set(knowledge.likes, 0)
                .where(knowledge.name == existing)
            ).run()
        return existing

    terms = list(
        dict.fromkeys(
            word
            for word in re.findall(r"[a-z0-9]{3,}", normalized_question)
            if word not in STOP_WORDS
        )
    )
    values = {
        "title": clean(message, 140),
        "published": 1,
        "priority": 100,
        "category": "Chat Feedback",
        "keywords": ", ".join(terms[:20]),
        "question": message,
        "answer": answer,
        "content": answer,
        "source_url": source_url,
        "likes": 1,
    }
    if existing:
        update = frappe.qb.update(knowledge).where(knowledge.name == existing)
        for fieldname, value in values.items():
            update = update.set(getattr(knowledge, fieldname), value)
        update.run()
        return existing

    learned = frappe.get_doc({"doctype": "Chatbot Knowledge", **values})
    learned.insert(ignore_permissions=True)
    return learned.name


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
