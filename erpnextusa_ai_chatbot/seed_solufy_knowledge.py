import frappe

ARTICLES = [
    {
        "title": "What is ERPNext USA & About Solufy",
        "keywords": "erpnextusa, erpnext usa, solufy, who is solufy, what is erpnextusa, about us, company, solufyerp, website, erpnextusa.com",
        "question": "What is ERPNext USA? Tell me about Solufy.",
        "priority": 100,
        "answer": (
            "ERPNext USA (https://erpnextusa.com/) is Solufy's dedicated platform for US businesses evaluating "
            "ERPNext consulting, implementation, customization, Frappe development, training, and ongoing support.\n\n"
            "Solufy (Solufy Pvt. Ltd.) is the engineering team behind ERPNext USA, with over 13+ years of continuous "
            "Frappe and ERPNext mastery (since 2014) and 100+ seasoned professionals. Our team delivers remotely from "
            "Gandhinagar, Gujarat, India, with guaranteed US timezone coverage (EST & PST business hours overlap).\n\n"
            "Key Highlights:\n"
            "• Official US Website: https://erpnextusa.com/\n"
            "• Direct US Phone Line: +1 (848) 248-0021\n"
            "• Work Email: contact@solufy.in\n"
            "• Global Headquarters: 501, 5th Floor, Vihaan 273, Sargasan, Gandhinagar, Gujarat 382419, India\n"
            "• Open-Source Freedom: Complete code and data ownership backed by mutual NDA and contract guarantees (no recurring per-user software licensing traps).\n"
            "• Public GitHub: https://github.com/Solufy-ERPNext-Apps"
        )
    },
    {
        "title": "ERPNext Services Offered on ERPNext USA",
        "keywords": "services, consulting, development, implementation, customization, support, training, integration, what do you offer, erpnextusa services",
        "question": "What ERPNext services do you offer on ERPNext USA?",
        "priority": 95,
        "answer": (
            "ERPNext USA provides 7 comprehensive ERPNext services tailored for growing businesses and enterprises:\n\n"
            "1. ERPNext Consulting: Map current workflows, conduct fit-gap analysis, identify operational bottlenecks, and agree on an actionable phased implementation plan.\n"
            "2. ERPNext Development: Build custom Frappe applications, bespoke DocTypes, and backend automations engineered specifically for your business logic.\n"
            "3. ERPNext Implementation: Full-cycle rollout connecting people, processes, and data—covering configuration, legacy data migration, rigorous scenario testing, and go-live handover.\n"
            "4. ERPNext Customization: Tailor forms, approval matrices, role permissions, custom reports, and business rules without adding technical debt or breaking upgrades.\n"
            "5. ERPNext Support & Maintenance: Keep daily operations running smoothly with dedicated named engineers, proactive monitoring, automated daily backups, security patches, and version upgrades.\n"
            "6. ERPNext Training: Role-based training for employees and system administrators to ensure smooth adoption and confident day-to-day operations.\n"
            "7. ERPNext Integration: Connect ERPNext with eCommerce (Shopify, WooCommerce, Amazon), Payment Gateways (Stripe, PayPal), Tax APIs (Avalara AvaTax), Shipping/Logistics (FedEx, eShipz, Delhivery), WhatsApp, and Telephony."
        )
    },
    {
        "title": "Working With US Clients: Remote Delivery, US Hours Overlap & NDA",
        "keywords": "us hours, remote delivery, timezone, overlap, est, pst, nda, contract, us business, delivery model, how we work",
        "question": "How do you work with US clients? Do you have US timezone coverage and NDA?",
        "priority": 90,
        "answer": (
            "We deliver ERPNext projects remotely for businesses across the United States:\n\n"
            "• Dedicated US Hours Overlap: Our delivery team maintains agreed daily overlap with Eastern (EST) and Pacific (PST) business hours for standups, reviews, and real-time collaboration.\n"
            "• Mutual NDA & Contract Ownership: We sign a mutual NDA before discovery begins. All custom applications, configurations, and repository rights belong 100% to your company.\n"
            "• Direct US Phone Line: Reach us directly at +1 (848) 248-0021.\n"
            "• Agreed Scope Before Invoicing: We document requirements, responsibilities, milestone acceptance criteria, and support coverage upfront—so there are never surprise costs.\n"
            "• Direct Senior Lead: You work directly with a senior technical lead and experienced Frappe engineers, avoiding bureaucratic account management layers."
        )
    },
    {
        "title": "How to Request an ERPNext Quote or Consultation on ERPNext USA",
        "keywords": "quote, pricing, consultation, demo, get started, cost, request quote, contact us, how to start",
        "question": "How do US businesses request a quote or get started with ERPNext USA?",
        "priority": 88,
        "answer": (
            "Getting started with ERPNext USA is straightforward:\n\n"
            "1. Share Your Requirements: Tell us about your business through our contact page, email contact@solufy.in, or by clicking the 'Contact Team' tab in this assistant. Include:\n"
            "   - Your industry and core workflows (Manufacturing, Distribution, Retail, Healthcare, etc.)\n"
            "   - Estimated number of users\n"
            "   - Current systems (QuickBooks, SAP, NetSuite, Excel, legacy software)\n"
            "   - Data migration requirements and target launch timeline\n"
            "2. Discovery Call: We schedule a remote discovery session with our senior solution architect during your business hours to review your processes and fit-gap requirements.\n"
            "3. Phased Implementation Proposal: We deliver a transparent, milestone-based proposal detailing project phases, deliverables, timeline, and exact investment before any work begins."
        )
    },
    {
        "title": "Improving and Auditing Existing ERPNext Systems",
        "keywords": "existing setup, audit, fix erpnext, optimize, review, upgrade erpnext, troubleshoot, slow erpnext",
        "question": "Can you review or fix our existing ERPNext setup?",
        "priority": 85,
        "answer": (
            "Yes. We frequently help companies optimize, repair, and upgrade existing ERPNext setups:\n\n"
            "• Architectural Review: Inspect your database, custom scripts, permissions, and server configuration to identify the root cause of performance slowdowns or workflow errors.\n"
            "• Custom App Refactoring: Clean up broken custom apps, deprecated code, and monkey patches so your instance follows Frappe best practices.\n"
            "• Version Upgrades: Test and rehearse safe upgrades between major ERPNext versions (v13, v14, v15, v16) with full database migration rehearsal and zero data loss.\n"
            "• Workflow & Integration Fixes: Re-engineer failed third-party integrations and unblock daily operational transactions."
        )
    },
    {
        "title": "Industries Served on ERPNext USA",
        "keywords": "industries, sectors, manufacturing, distribution, retail, ecommerce, healthcare, pharma, non profit, logistics, agriculture",
        "question": "Which industries do you serve on ERPNext USA?",
        "priority": 82,
        "answer": (
            "ERPNext USA has proven implementations across 20+ specialized industries:\n\n"
            "• Discrete & Process Manufacturing: Work Orders, multi-level BOMs, routing, subcontracting, capacity planning, and shop-floor tracking.\n"
            "• Wholesale & Distribution: Multi-warehouse management, batch/serial tracking, replenishment rules, drop shipping, and logistics.\n"
            "• Retail & E-Commerce: Multi-store POS, omnichannel stock synchronization, WooCommerce, Shopify, and Amazon SP-API integrations.\n"
            "• Supply Chain & 3PL Logistics: Freight tracking, courier dispatch, barcode/QR scanning, automated inventory reconciliation.\n"
            "• Healthcare & Pharmaceuticals: Patient health records, medical billing, clinical orders, and strict batch expiry traceability.\n"
            "• Non-Profit & Education: Donor management, grant accounting, student enrollment, fee collection, and fund tracking.\n"
            "• Hospitality, Real Estate & Services: Property management, recurring leases, maintenance ticketing, and timesheet billing."
        )
    },
    {
        "title": "Why Choose Solufy & ERPNext USA (The Open-Source Advantage)",
        "keywords": "why erpnext usa, why solufy, netsuite vs erpnext, sap vs erpnext, quickbooks vs erpnext, advantage, benefits",
        "question": "Why choose ERPNext USA over NetSuite, SAP, or QuickBooks?",
        "priority": 80,
        "answer": (
            "Why US enterprises partner with ERPNext USA and Solufy:\n\n"
            "• Zero Software License Fees: No recurring per-user subscription traps. You own your code, database, and infrastructure completely.\n"
            "• 13+ Years of Pure Frappe Experience: We don't dabble in 10 different platforms; our entire team has specialized in Frappe and ERPNext since 2014.\n"
            "• Transparent Milestone Pricing: Pay for deliverable milestones agreed in advance, not endless billing surprises.\n"
            "• Scalability Without Lock-In: Host on your own private cloud (AWS, DigitalOcean, GCP) or on-premise with total data sovereignty.\n"
            "• Dedicated Support That Stays: Direct access to experienced engineers who built your system, not generic call centers."
        )
    }
]


def seed():
    for item in ARTICLES:
        existing = frappe.db.get_value("Chatbot Knowledge", {"title": item["title"]}, "name")
        if existing:
            doc = frappe.get_doc("Chatbot Knowledge", existing)
            doc.keywords = item["keywords"]
            doc.question = item["question"]
            doc.answer = item["answer"]
            doc.priority = item["priority"]
            doc.published = 1
            doc.save(ignore_permissions=True)
            print(f"Updated article: {item['title']}")
        else:
            doc = frappe.get_doc({
                "doctype": "Chatbot Knowledge",
                "title": item["title"],
                "keywords": item["keywords"],
                "question": item["question"],
                "answer": item["answer"],
                "priority": item["priority"],
                "published": 1
            })
            doc.insert(ignore_permissions=True)
            print(f"Created article: {item['title']}")
    
    frappe.db.commit()
    print("ERPNextUSA knowledge seeding completed successfully.")
