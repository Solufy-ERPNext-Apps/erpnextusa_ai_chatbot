app_name = "erpnextusa_ai_chatbot"
app_title = "ERPNextUSA AI Chatbot"
app_publisher = "ERPNextUSA"
app_description = "Website chatbot with Gemini, OpenAI and Ollama"
app_email = "savan.p.solufy@gmail.com"
app_license = "MIT"
# Embed externally via script tag; do not inject widget into every Desk page.

after_install = "erpnextusa_ai_chatbot.setup_ollama.ensure_ollama_model"
after_migrate = "erpnextusa_ai_chatbot.setup_ollama.ensure_ollama_model"

doc_events = {
    "Website Service": {
        "on_update": "erpnextusa_ai_chatbot.sync_knowledge.sync_website_service",
        "on_trash": "erpnextusa_ai_chatbot.sync_knowledge.delete_synced_knowledge",
    },
    "Website Industry": {
        "on_update": "erpnextusa_ai_chatbot.sync_knowledge.sync_website_industry",
        "on_trash": "erpnextusa_ai_chatbot.sync_knowledge.delete_synced_knowledge",
    },
    "Case Study": {
        "on_update": "erpnextusa_ai_chatbot.sync_knowledge.sync_case_study",
        "on_trash": "erpnextusa_ai_chatbot.sync_knowledge.delete_synced_knowledge",
    },
    "Website Team Member": {
        "on_update": "erpnextusa_ai_chatbot.sync_knowledge.sync_team_member",
        "on_trash": "erpnextusa_ai_chatbot.sync_knowledge.delete_synced_knowledge",
    },
    "Blog Post": {
        "on_update": "erpnextusa_ai_chatbot.sync_knowledge.sync_blog_post",
        "on_trash": "erpnextusa_ai_chatbot.sync_knowledge.delete_synced_knowledge",
    },
}

