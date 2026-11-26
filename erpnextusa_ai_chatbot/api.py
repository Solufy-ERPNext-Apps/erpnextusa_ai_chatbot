import hashlib
import hmac
import re
import uuid
from urllib.parse import urlparse

import frappe
import requests
from frappe import _
from frappe.utils import cint
from frappe.utils.password import get_encryption_key

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
    if words & {"odoo", "sap", "netsuite", "dynamics", "comparison", "compare", "versus"}:
        preferred_categories = {"ERP Comparison"}
    elif wants_article:
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


def extract_visitor_name(message: str) -> str:
    if not message:
        return ""
    text = clean(message, 500).strip()
    patterns = [
        r"\b(?:my name is|name is|i am|i'm|im|call me|this is|myself)\s+([A-Za-z]+(?:\s+[A-Za-z]+){0,2})\b",
    ]
    non_names = {
        "a", "an", "the", "here", "there", "asking", "looking", "interested", "trying",
        "wondering", "just", "user", "visitor", "testing", "new", "curious", "not",
        "good", "fine", "ready", "happy", "excited", "sorry", "sure", "having",
        "planning", "thinking", "facing", "running", "using", "working", "building",
        "seeking", "going", "getting", "searching", "calling", "writing", "hoping",
    }
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            raw = match.group(1).strip(" .,!?")
            words = raw.split()
            if words and words[0].lower() not in non_names:
                if len(words) == 1 and words[0].lower() in {
                    "what", "who", "where", "how", "why", "when", "which", "can", "could", "should", "would", "is", "are"
                }:
                    continue
                return " ".join(w.capitalize() for w in words)
    return ""


def issue_session_id() -> str:
    raw = uuid.uuid4().hex
    return f"{raw}.{_session_signature(raw)}"


def verified_session_id(value) -> str:
    """Return the session id when the server signed it, otherwise an empty string."""
    session_id = clean(value, 100)
    raw, _, signature = session_id.partition(".")
    if raw and signature and hmac.compare_digest(signature, _session_signature(raw)):
        return session_id
    return ""


def _session_signature(raw: str) -> str:
    key = get_encryption_key().encode()
    return hmac.new(key, raw.encode(), hashlib.sha256).hexdigest()[:32]


def get_session_visitor_name(session_id: str) -> str:
    if not session_id:
        return ""
    cached = frappe.cache().get_value(f"eu_chatbot:visitor_name:{session_id}")
    if cached:
        return str(cached)
    if frappe.db.has_column("Chatbot Conversation", "visitor_name"):
        val = frappe.db.get_value(
            "Chatbot Conversation",
            filters={"session_id": session_id, "visitor_name": ["is", "set"]},
            fieldname="visitor_name",
            order_by="creation desc",
        )
        if val:
            frappe.cache().set_value(f"eu_chatbot:visitor_name:{session_id}", val, expires_in_sec=86400)
            return str(val)
    return ""


def set_session_visitor_name(session_id: str, name: str):
    if not session_id or not name:
        return
    frappe.cache().set_value(f"eu_chatbot:visitor_name:{session_id}", name, expires_in_sec=86400)


def get_session_history(session_id: str, limit: int = 6) -> list[dict]:
    if not session_id:
        return []
    rows = frappe.get_all(
        "Chatbot Conversation",
        filters={"session_id": session_id},
        fields=["visitor_message", "assistant_message"],
        order_by="creation desc",
        limit_page_length=limit,
    )
    history = []
    for r in reversed(rows):
        if r.get("visitor_message"):
            history.append({"role": "user", "content": clean(r.visitor_message, 1000)})
        if r.get("assistant_message"):
            history.append({"role": "assistant", "content": clean(r.assistant_message, 1000)})
    return history


def _remove_unrequested_greeting(message, answer, visitor_name=""):
    if _is_greeting(message):
        return answer
    if visitor_name and visitor_name.lower() in (answer or "").lower()[:80]:
        return answer
    if any(phrase in message.lower() for phrase in ("my name", "i am", "i'm", "myself", "call me")):
        return answer
    return re.sub(
        r"^(?:hello|hi|hey)(?:\s+there)?[!,.:\s-]*",
        "",
        answer or "",
        count=1,
        flags=re.IGNORECASE,
    ).lstrip()


def provider_reply(
    cfg,
    question,
    knowledge,
    country="",
    history=None,
    visitor_name="",
):

    provider = cfg.active_provider

    timeout = min(90, max(5, cint(cfg.request_timeout) or 45))
    temperature = max(0, min(1, float(cfg.temperature or 0.45)))
    max_tokens = min(2000, max(100, cint(cfg.max_output_tokens) or 700))
    context = (
        "\n".join(f"- {r['title']}: {r['answer']}" for r in knowledge)
        if knowledge
        else ""
    )
    grounded_question = question
    if knowledge and knowledge[0].get("category") == "ERP Comparison":
        grounded_question = (
            f"{question}\n\nAnswer using only these approved comparison facts. Do not add "
            f"other product claims:\n{knowledge[0].get('answer') or ''}"
        )
    if knowledge and knowledge[0].get("category") == "Chat Feedback":
        learned_answer = knowledge[0].get("answer") or knowledge[0].get("content")
        if learned_answer:
            return learned_answer

    instruction = (
        "You are the official AI consultant for Solufy and ERPNext USA (https://erpnextusa.com/). "
        "Talk like a warm, helpful, friendly human being in a natural conversational tone. "
        "Never give dry, robotic, or overly stiff textbook answers.\n\n"
        "CONVERSATIONAL GUIDELINES:\n"
        "• Be welcoming, courteous, and genuinely passionate about helping businesses succeed with ERPNext and Frappe.\n"
        "• If you know the visitor's name or if they introduce themselves, greet and address them warmly by name.\n"
        "• APPROVED KNOWLEDGE is your factual foundation for ERPNext, Frappe, and Solufy services. Blend this knowledge naturally into your conversational answers instead of just copying raw text.\n"
        "• Keep ERPNext as the primary subject. You may compare it with other ERP products when asked, but explain the tradeoffs fairly and bring the decision back to the visitor's business requirements.\n"
        "• For ERP product comparisons, use only the supplied APPROVED KNOWLEDGE. Do not invent claims about product age, market size, popularity, editions, pricing, or which product is more customizable.\n"
        "• If APPROVED KNOWLEDGE does not contain the answer, politely let them know that the specific detail is not available on the website, and invite them to connect with Solufy's consulting team.\n"
        "• Never write or generate raw source code, scripts, commands, formulas, or implementation snippets.\n"
        "• Do not recommend unvetted custom configurations, custom fields, or architecture; explain standard Frappe/ERPNext concepts and features conceptually.\n"
        "• If a question is unrelated to Frappe, ERPNext, or business operations, politely and warmly steer the conversation back to how ERPNext or Solufy can help their business.\n"
        "• Keep answers concise, clear, and easy to read using clean markdown and friendly bullet points."
    )
    if visitor_name:
        instruction += (
            f"\n\nVISITOR NAME: {visitor_name}. Greet them and address them warmly by name."
        )
    if country:
        instruction += (
            f"\n\nVISITOR COUNTRY: {country}. Use relevant country terminology and approved "
            "country-specific knowledge when available. Do not invent tax, legal, pricing, office, "
            "partner, or compliance claims. Include a relevant approved source link when the knowledge provides one."
        )

    if _is_greeting(question):
        name_part = f" {visitor_name}" if visitor_name else ""
        return (
            f"Hello{name_part}! 😊 It's wonderful to connect with you! I'm your AI consultant for "
            "**ERPNext USA** (https://erpnextusa.com/) and **Solufy** (https://www.solufyerp.com/).\n\n"
            "How can I help you today? I'd love to tell you more about ERPNext, Frappe, or our implementation and consulting services."
        )

    def _call_openai():
        key = cfg.get_password(
            "openai_api_key", raise_exception=False
        ) or frappe.conf.get("openai_api_key")
        if not key:
            raise ValueError("OpenAI key missing")
        sys_msg = instruction + ("\n\nAPPROVED KNOWLEDGE:\n" + context if context else "")
        messages = [{"role": "system", "content": sys_msg}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": grounded_question})
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
                    "\n\nAPPROVED KNOWLEDGE:\n" + context if context else ""
                )
                contents = []
                if history:
                    for h in history:
                        role = "user" if h.get("role") == "user" else "model"
                        contents.append({"role": role, "parts": [{"text": h.get("content") or ""}]})
                contents.append({"role": "user", "parts": [{"text": grounded_question}]})
                res = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                    headers={"x-goog-api-key": key},
                    json={
                        "systemInstruction": {"parts": [{"text": sys_text}]},
                        "contents": contents,
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

        configured_model = (cfg.ollama_model or DEFAULT_OLLAMA_MODEL).strip()
        models_to_try = [configured_model]

        ollama_instruction = (
            "You are the official AI consultant for Solufy and ERPNext USA. "
            "Talk like a warm, helpful, friendly human being in a natural conversational tone. "
            "Never give dry, robotic, or overly stiff textbook answers.\n"
            "If you know the visitor's name, greet and address them warmly by name.\n"
            "Approved website knowledge is your foundation for facts about Frappe, ERPNext, standard modules, and Solufy's services. "
            "Explain them conversationally rather than just dumping raw text.\n"
            "Keep ERPNext as the primary subject. When asked about another ERP, compare it fairly with ERPNext and relate the answer to the visitor's requirements.\n"
            "For ERP product comparisons, use only RELEVANT APPROVED KNOWLEDGE. Do not add claims about product age, popularity, market size, pricing, or which product is more customizable.\n"
            "Never write or generate raw source code, scripts, commands, or formulas. "
            "Do not suggest custom unvetted configurations or workflows; explain standard Frappe/ERPNext concepts conceptually.\n"
            "Keep the answer friendly, engaging, and concise (under 160 words)."
        )
        if visitor_name:
            ollama_instruction += f"\nVISITOR NAME: {visitor_name}. Greet them and refer to them naturally by name."
        if country:
            ollama_instruction += (
                f"\nVisitor country: {country}. Use country-relevant approved context only; "
                "do not invent tax, legal, pricing, or compliance claims."
            )
        if context:
            compact_snippets = []
            for item in knowledge[:3]:
                ans_text = clean(item.get("answer") or item.get("content") or "", 700)
                if ans_text:
                    compact_snippets.append(f"• {item['title']}: {ans_text}")
            if compact_snippets:
                ollama_instruction += "\n\nRELEVANT APPROVED KNOWLEDGE:\n" + "\n".join(
                    compact_snippets
                )

        ollama_messages = [
            {"role": "system", "content": ollama_instruction},
        ]
        if history:
            ollama_messages.extend(history)
        ollama_messages.append({"role": "user", "content": grounded_question})

        last_ollama_err = None
        for m in models_to_try:
            try:
                m_timeout = min(timeout, 35) if m == configured_model and len(models_to_try) > 1 else max(timeout, 60)
                res = requests.post(
                    base + "/api/chat",
                    json={
                        "model": m,
                        "messages": ollama_messages,
                        "stream": False,
                        "options": {
                            "temperature": 0.45,
                            "num_predict": 350,
                            "num_ctx": 4096,
                            "num_thread": 4,
                        },
                    },
                    timeout=m_timeout,
                )
                if res.ok:
                    msg = res.json().get("message", {})
                    content = msg.get("content") or ""
                    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                    if content:
                        return content
                last_ollama_err = ValueError(f"Ollama error on {m}: {res.text}")
            except Exception as e:
                last_ollama_err = e

        if last_ollama_err:
            raise last_ollama_err

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
    asks_which_page = "page" in text and any(
        phrase in text
        for phrase in ("where am i", "where i am", "which page", "what page", "page am i")
    )
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
    ) or asks_which_page


def is_page_identity_request(message: str) -> bool:
    text = clean(message, 500).lower()
    return "page" in text and any(
        phrase in text
        for phrase in ("where am i", "where i am", "which page", "what page", "page am i")
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


def page_metadata_answer(
    title: str, heading: str, description: str, content: str = ""
) -> str:
    title = clean(title, 200)
    heading = clean(heading, 300)
    description = clean(description, 700)
    content = clean(content, 3000)
    if not any((title, heading, description, content)):
        return (
            "I cannot identify enough published content on this page to summarize it."
        )

    blocks = [f"**{heading or title}**"]
    if description:
        blocks.append(description)
    elif title and heading and title != heading:
        blocks.append(title)
    if content and content not in blocks:
        blocks.append(content)
    return "\n\n".join(blocks)


def page_identity_answer(page: str, title: str, heading: str) -> str:
    path = urlparse(clean(page, 500)).path or "/"
    name = clean(heading, 300) or clean(title, 200) or "this page"
    return f"You are on **{name}** (`{path}`)."


@frappe.whitelist(allow_guest=True, methods=["POST"])
def chat(
    message=None,
    session_id=None,
    country=None,
    page=None,
    page_title=None,
    page_heading=None,
    page_description=None,
    page_content=None,
    **kwargs,
):
    throttle("chat", 60, 60)
    message = clean(message)
    if not message:
        frappe.throw(_("Enter a message"))
    cfg = settings_enabled()
    sid = verified_session_id(session_id) or issue_session_id()

    # Detect and persist visitor name for this session
    detected_name = extract_visitor_name(message)
    if detected_name:
        set_session_visitor_name(sid, detected_name)
    visitor_name = detected_name or get_session_visitor_name(sid)

    # Retrieve prior conversation turns for multi-turn conversational context
    history = get_session_history(sid, limit=6)

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
    elif page_context:
        kb = get_page_knowledge(page)
        if is_page_identity_request(message):
            answer = page_identity_answer(page, page_title, page_heading)
        elif kb:
            answer = summarize_page_answer(kb[0].get("answer") or "")
        else:
            answer = page_metadata_answer(
                page_title, page_heading, page_description, page_content
            )
    else:
        limit = min(10, max(1, cint(cfg.max_knowledge_results) or 5))
        kb = _retrieve_for_country(message, country, limit)
        try:
            answer = provider_reply(
                cfg,
                message,
                kb,
                country=country,
                history=history,
                visitor_name=visitor_name,
            )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "ERPNextUSA Chat Provider")
            if kb:
                answer = kb[0].get("answer") or kb[0].get("content") or ""

    if not answer:
        name_greeting = f" {visitor_name}" if visitor_name else ""
        answer = (
            f"Hello{name_greeting}! 😊 I'm here to help with information about ERPNext, Frappe, and Solufy's "
            "consulting and implementation services. What would you like to know?"
        )

    answer = _remove_unrequested_greeting(message, answer, visitor_name=visitor_name)
    answer = format_answer_links(answer)

    doc_data = {
        "doctype": "Chatbot Conversation",
        "session_id": sid,
        "visitor_message": message,
        "assistant_message": clean(answer, 8000),
        "provider": cfg.active_provider,
    }
    if visitor_name and frappe.db.has_column("Chatbot Conversation", "visitor_name"):
        doc_data["visitor_name"] = visitor_name

    try:
        frappe.get_doc(doc_data).insert(ignore_permissions=True)
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
    session_id = verified_session_id(session_id)
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
    """Record a guest like as an unpublished draft; a System Manager reviews and publishes it."""
    normalized_question = " ".join(_normalize_search_question(message).split())
    feedback_key = hashlib.sha256(normalized_question.encode()).hexdigest()[:24]
    source_url = f"chat-feedback:{feedback_key}"
    knowledge = frappe.qb.DocType("Chatbot Knowledge")
    existing_rows = (
        frappe.qb.from_(knowledge)
        .select(knowledge.name, knowledge.answer)
        .where(knowledge.source_url == source_url)
        .limit(1)
    ).run(as_dict=True)
    existing = existing_rows[0] if existing_rows else None

    if not liked:
        return existing.name if existing else None

    if existing:
        if existing.answer == answer:
            (
                frappe.qb.update(knowledge)
                .set(knowledge.likes, knowledge.likes + 1)
                .where(knowledge.name == existing.name)
            ).run()
        return existing.name

    terms = list(
        dict.fromkeys(
            word
            for word in re.findall(r"[a-z0-9]{3,}", normalized_question)
            if word not in STOP_WORDS
        )
    )
    draft = frappe.get_doc(
        {
            "doctype": "Chatbot Knowledge",
            "title": clean(message, 140),
            "published": 0,
            "priority": 100,
            "category": "Chat Feedback",
            "keywords": ", ".join(terms[:20]),
            "question": normalized_question,
            "answer": answer,
            "content": answer,
            "source_url": source_url,
            "likes": 1,
        }
    )
    draft.insert(ignore_permissions=True)
    return draft.name


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
