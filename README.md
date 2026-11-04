# ERPNextUSA AI Chatbot

Frappe custom app for a website chatbot with Gemini, OpenAI, or Ollama, MariaDB-backed knowledge and opt-in ERPNext Lead creation.

## Install on staging first

```bash
cd ~/frappe-bench
bench get-app /absolute/path/to/erpnextusa_ai_chatbot
bench --site YOUR-SITE install-app erpnextusa_ai_chatbot
bench --site YOUR-SITE migrate
bench build --app erpnextusa_ai_chatbot
bench restart
```

If `bench get-app` does not support your local directory layout, put the extracted project in `apps/erpnextusa_ai_chatbot`, then install in the bench Python environment using `./env/bin/pip install -e apps/erpnextusa_ai_chatbot` before `install-app`.

In Desk, open **Chatbot Settings**, configure provider and credentials, test connectivity, then enable the chatbot. Create **Chatbot Knowledge** entries and publish them.

## Website embed

```html
<script src="https://YOUR-SITE/assets/erpnextusa_ai_chatbot/js/chatbot.js"
  data-api-base="https://YOUR-SITE"
  data-title="ERPNextUSA Assistant"
  data-privacy-url="https://YOUR-WEBSITE/privacy-policy" defer></script>
```

The Contact team tab contains an **unchecked, required consent checkbox**. Lead creation only happens after consent is submitted. No CRM record identifier is exposed to the public.

## Deployment notes

- Requires an installed ERPNext instance for Lead creation.
- For cross-origin embedding, configure the site's CORS policy for the exact trusted website origin and verify preflight requests. Avoid wildcard CORS.
- Set a real, published privacy-policy URL and retention policy before going live.
- Public chat and lead endpoints use basic Redis per-IP limits; add WAF/reverse-proxy limits and CAPTCHA if abused.
- Only System Managers can access Settings, Knowledge and Conversations.
- Password fields use Frappe's encrypted password storage.
- Ollama must be accessible from the Frappe worker. Loopback HTTP or remote HTTPS is allowed. For remote hosts, use an allowlisted private endpoint and network egress controls to prevent SSRF.
- The widget does not persist conversation history across page reloads; server logs are per message and include a session identifier.
- Knowledge retrieval is keyword-based, not vector search. No website crawler or training pipeline is included.
- Consider deleting conversation logs after the configured retention period; the field is informational until a cleanup job is implemented.
- Do not place API keys in website JavaScript.
- Validate the precise Frappe/ERPNext version and provider API behavior on staging before production.
