
import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import Dict, Any, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'modules'))

from mail_collector import MailCollector, EmailFilter, CollectionOptions
from mail_collector.collectors.microsoftExchange import MicrosoftExchangeCollector
from llm_client.client import LLMClient
from llm_client.types import ChatMessage
from llm_client.providers.openai_compat import OpenAICompatibleProvider

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import Chroma
    RAG_AVAILABLE = True
except ImportError:
    print("RAG dependencies not found. Install with: pip install langchain langchain-community chromadb sentence-transformers")
    RAG_AVAILABLE = False


def extract_keywords(text: str) -> List[str]:
    """Extract Turkish keywords from text for better retrieval"""
    keywords = [
        "toplantı", "duyuru", "bilgilendirme", "katılım", "sunum",
        "görüşme", "planlama", "rapor", "özet", "bilgi", "not", "takvim", "ajanda",
        "vpn", "erişim", "sunucu", "bakım", "sistem", "it destek",
        "güvenlik", "ağ", "şifre", "parola", "veritabanı", "api",
        "deploy", "update", "login", "yazılım", "uygulama",
        "donanım", "cihaz", "hata", "ticket", "destek",
        "proje", "geliştirme", "task", "sprint", "issue",
        "jira", "test", "analiz", "plan", "kod", "pull request",
        "merge", "release", "versiyon", "tasarım", "backlog",
        "roadmap", "öncelik", "takım", "deadline", "hedef"
    ]
    return [kw for kw in keywords if kw in text.lower()]


def build_rag_vectorstore(emails: List[Any], db_dir: str = "./chroma_db") -> Any:
    if not RAG_AVAILABLE:
        print("RAG not available - skipping vector store creation")
        return None
    
    
    email_docs = []
    for email in emails:
        text = f"""
Subject: {email.subject or ''}
From: {email.sender}
Date: {email.date.strftime('%Y-%m-%d %H:%M:%S')}
Body: {email.body_text or email.body_html or ''}
        """.strip()
        
        email_docs.append({
            "id": getattr(email, 'message_id', str(email.date)),
            "subject": email.subject or '',
            "text": text
        })
    
    
    splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=100)
    texts, metas = [], []
    
    for mail in email_docs:
        chunks = splitter.split_text(mail["text"])
        for chunk in chunks:
            metas.append({
                "source_id": mail["id"],
                "subject": mail["subject"],
                "keywords": str(extract_keywords(chunk)),
            })
            texts.append(chunk)
    
    embedding = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    
    os.makedirs(db_dir, exist_ok=True)
    
    vectordb = Chroma(
        collection_name="emails",
        embedding_function=embedding,
        persist_directory=db_dir
    )
    
    try:
        vectordb.delete_collection()
        vectordb = Chroma(
            collection_name="emails",
            embedding_function=embedding,
            persist_directory=db_dir
        )
    except:
        pass
    
    vectordb.add_texts(texts=texts, metadatas=metas)
    
    return vectordb


def retrieve_relevant_context(vectordb: Any, query: str, k: int = 10) -> str:
    """Retrieve relevant email context using RAG"""
    if not vectordb:
        return ""
    
    
    keywords = extract_keywords(query)
    results = vectordb.similarity_search_with_score(query, k=k)
    
    found = []
    for doc, score in results:
        meta = doc.metadata
        # Filter by keywords if present
        if not keywords or any(kw in meta.get("keywords", "").lower() for kw in keywords):
            found.append((doc, score))
    
    if not found:
        print(" No relevant context found")
        return ""
    
    retrieved_context = "\n\n".join([doc.page_content for doc, _ in found[:5]])
    return retrieved_context


def load_config(config_path: str) -> Dict[str, Any]:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at {config_path}. Copy config.example.json to config.json and edit your settings.")
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _load_last_fetch(state_path: str) -> datetime | None:
    try:
        if not os.path.exists(state_path):
            return None
        with open(state_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        last_fetch = data.get('last_fetch_iso')
        return datetime.fromisoformat(last_fetch) if last_fetch else None
    except Exception:
        return None


def _save_last_fetch(state_path: str, last_dt: datetime) -> None:
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, 'w', encoding='utf-8') as f:
        json.dump({"last_fetch_iso": last_dt.isoformat()}, f, indent=2)


async def analyze_emails(config: Dict[str, Any]):
    print("="*50)

    email_cfg = config.get("emailMicrosoftExchange", {})
    llm_cfg = config.get("llm", {})
    analysis_cfg = config.get("analysis", {})
    collection_cfg = config.get("collection", {})
    rag_cfg = config.get("rag", {})

    # Email configuration - Microsoft Exchange
    exchange_collector = MicrosoftExchangeCollector(
        tenant_id=email_cfg.get("tenant_id", ""),
        client_id=email_cfg.get("client_id", ""),
        client_secret=email_cfg.get("client_secret", ""),
        token_cache_file=email_cfg.get("token_cache_file", "token_cache.json")
    )

    mail_client = MailCollector(exchange_collector)

    # LLM configuration
    llm_provider = OpenAICompatibleProvider(
        base_url=llm_cfg.get("base_url", "http://127.0.0.1:1234"),
        api_key=llm_cfg.get("api_key", ""),
        model=llm_cfg.get("model", None),
    )

    llm_client = LLMClient(llm_provider)

    try:
        print("📧 Testing email connection...")
        if not mail_client.test_connection():
            print("Email connection failed!")
            print("Please check your Microsoft Exchange credentials:")
            print("   - tenant_id: Azure AD tenant ID")
            print("   - client_id: Azure AD application client ID")
            print("   - client_secret: Azure AD application client secret (optional)")
            return
        print("Email connection successful")

        print("Collecting emails...")
        days = int(analysis_cfg.get("days", 7))
        max_results = int(analysis_cfg.get("max_results", 20))

        app_dir = os.path.dirname(__file__)
        state_file = collection_cfg.get("state_file", os.path.join(app_dir, 'state.json'))
        last_fetch_dt = _load_last_fetch(state_file)
        if last_fetch_dt:
            date_from = last_fetch_dt
            print(f"Incremental fetch since: {date_from.isoformat()}")
        else:
            date_from = datetime.now() - timedelta(days=days)
            print(f"First run window: last {days} days (from {date_from.date()})")

        filter_criteria = EmailFilter(
            date_from=date_from,
            max_results=max_results,
        )

        emails_output_dir = collection_cfg.get("output_dir", os.path.join(app_dir, 'collected_emails'))
        output_format = collection_cfg.get("output_format", "json")
        save_attachments = bool(collection_cfg.get("save_attachments", False))
        create_subdirs = bool(collection_cfg.get("create_subdirs", True))
        attachment_dir = collection_cfg.get("attachment_dir", os.path.join(emails_output_dir, 'attachments'))
        options = CollectionOptions(
            output_dir=emails_output_dir,
            output_format=output_format,
            save_attachments=save_attachments,
            attachment_dir=attachment_dir,
            create_subdirs=create_subdirs,
        )

        result = mail_client.collect_emails(
            filter_criteria,
            options=options,
            folder_id="inbox"
        )
        emails = result.messages


        if not emails:
            print("📭 No emails found to analyze")
            return

        vectordb = None
        if RAG_AVAILABLE and rag_cfg.get("enabled", True):
            db_dir = rag_cfg.get("db_dir", os.path.join(app_dir, "chroma_db"))
            vectordb = build_rag_vectorstore(emails, db_dir)
        else:
            print(" RAG disabled or unavailable - using direct analysis")

        
        max_emails_for_llm = analysis_cfg.get("max_emails_for_llm", 50)
        max_body_preview_length = analysis_cfg.get("max_body_preview_length", 200)
        
        print(f"Email processing limits:")
        print(f"   - Max emails for LLM: {max_emails_for_llm}")
        print(f"   - Max body preview length: {max_body_preview_length}")

        if vectordb and rag_cfg.get("use_rag_for_analysis", True):
            print("🔍 Using RAG-enhanced analysis...")
            
            query = rag_cfg.get("analysis_query", "Şirket içi mailler için bir email özeti çıkart")
            retrieved_context = retrieve_relevant_context(
                vectordb, 
                query, 
                k=rag_cfg.get("retrieval_k", 10)
            )
            
        analysis_prompt = f"""
You are a data analyst and communication behavior expert.
Below is a collection of emails from a software company.
Your task is to perform a **comprehensive organizational and communication analysis** based on the given emails.

Follow all instructions carefully and **respond only in structured analytical format** — not raw data or direct quotes.

---

### 📊 DATASET INFORMATION:
- Total emails collected: {len(emails)}
- Analysis period: {date_from.strftime('%Y-%m-%d')} → {datetime.now().strftime('%Y-%m-%d')}

### 📥 EMAIL DATA (Truncated JSON Sample):
{json.dumps(email_data, indent=2)}

---

## 🔍 ANALYSIS REQUIREMENTS

### 1. MAIN TOPICS
Identify and list the **main themes** discussed in the emails.
Present them as a **numbered list with short explanations** for each topic.

### 2. ACTIONS AND RESPONSIBILITIES
List all actionable items mentioned in emails with their responsible persons in a table format:

| # | Action Item | Responsible Person |
|---|--------------|--------------------|
| 2.1 | ... | ... |

### 3. DEADLINES AND IMPORTANT DATES
Extract all important deadlines, meeting dates, and delivery milestones:

| # | Date / Deadline | Description |
|---|------------------|-------------|
| 3.1 | ... | ... |

### 4. COMMUNICATION BEHAVIORS
Analyze corporate communication patterns:
- Most active senders and recipients  
- Frequency and direction of communication (internal, management, external, etc.)  
- Response times and behavioral tendencies  
- Overall tone of internal communication  

### 5. TRENDS
Identify key communication trends:
- Topics or subjects that are increasing in volume  
- Email frequency patterns by time period (daily, weekly, monthly)  
- Repeated or emerging keywords  

### 6. ANOMALIES
Detect and describe unusual or irregular communication behaviors:
- Abnormal spikes or drops in volume  
- Suspicious or unexpected email patterns  
- Duplicate, misrouted, or error-prone messages  

### 7. SENTIMENT & TOPICS
Perform sentiment and thematic analysis:
- Overall emotional tone (positive, neutral, or negative)  
- Key discussion areas (e.g., client issues, product updates, project deadlines)  
- General communication climate and morale  

---

## 🧾 FORMATTING RULES:
1. Structure your response using **clear numbered sections and headers**.  
2. Present tables neatly with consistent alignment.  
3. **Do not copy or quote raw email content.** Summarize only key insights.  
4. Avoid redundancy — do not repeat the same conclusions.  
5. The analysis must be **concise, professional, and insightful.**

---

### 🎯 GOAL:
The purpose of this analysis is to help company leadership understand:
- Communication focus areas and bottlenecks  
- Key responsibilities and deadlines  
- Collaboration dynamics and response behaviors  
- Sentiment and productivity indicators across teams  
"""

        print(f"   - Base URL: {llm_cfg.get('base_url', 'http://127.0.0.1:1234')}")
        print(f"   - Model: {llm_cfg.get('model', 'default')}")
        
        messages = [
            ChatMessage(role="system", content="You are an expert email analyst. Provide detailed, structured analysis in Turkish."),
            ChatMessage(role="user", content=analysis_prompt),
        ]

        
        analysis_parts = []
        token_count = 0
        
        try:
            async for token in llm_client.astream_chat(messages):
                analysis_parts.append(token)
                token_count += 1
                if token_count % 50 == 0:
                    print("AAA")
            analysis = "".join(analysis_parts)
            print(f"✅ LLM analysis completed! Received {token_count} tokens")
            
            if not analysis.strip():
                analysis = "LLM analysis failed - no response received from the model."
        
        except Exception as e:
            print(f" LLM request failed with error: {e}")
            analysis = f"LLM analysis failed due to error: {str(e)}"

        # Compute basic statistical analyses
        print("📊 Computing statistical metrics...")
        sender_counts = Counter()
        sender_domains = Counter()
        hourly_counts = defaultdict(int)
        daily_counts = defaultdict(int)
        weekday_counts = defaultdict(int)
        subject_words = Counter()
        subject_lengths = []
        urgent_keywords = ['urgent', 'asap', 'important', 'emergency', 'critical', 'acil', 'önemli']
        urgent_count = 0

        for email in emails:
            sender_email = getattr(email.sender, 'email', str(email.sender))
            if isinstance(sender_email, str):
                sender_counts[sender_email] += 1
                if '@' in sender_email:
                    sender_domains[sender_email.split('@')[1]] += 1

            hourly_counts[email.date.hour] += 1
            daily_counts[email.date.strftime('%Y-%m-%d')] += 1
            weekday_counts[email.date.strftime('%A')] += 1

            subject = (email.subject or '').lower()
            subject_lengths.append(len(email.subject or ''))
            subject_words.update(subject.split())
            if any(keyword in subject for keyword in urgent_keywords):
                urgent_count += 1

        basic_metrics = {
            "summary": {
                "total_emails": len(emails),
                "analysis_date": datetime.now().isoformat(),
                "rag_enabled": bool(vectordb),
            },
            "senders": {
                "total_unique_senders": len(sender_counts),
                "most_active_senders": sender_counts.most_common(5),
                "sender_domains": sender_domains.most_common(5),
            },
            "timing": {
                "peak_hour": max(hourly_counts.items(), key=lambda x: x[1])[0] if hourly_counts else None,
                "peak_weekday": max(weekday_counts.items(), key=lambda x: x[1])[0] if weekday_counts else None,
            },
            "subjects": {
                "average_subject_length": (sum(subject_lengths) / len(subject_lengths)) if subject_lengths else 0,
                "most_common_words": subject_words.most_common(10),
                "urgent_emails": urgent_count,
            },
        }

        # Save results
        base_dir_for_outputs = os.path.dirname(emails_output_dir)
        configured_analysis_dir = analysis_cfg.get("output_dir")
        if configured_analysis_dir:
            output_dir = configured_analysis_dir if os.path.isabs(configured_analysis_dir) else os.path.join(base_dir_for_outputs, configured_analysis_dir)
        else:
            output_dir = os.path.join(base_dir_for_outputs, "email_analysis_results")
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        analysis_file = os.path.join(output_dir, f"email_analysis_{timestamp}.md")
        with open(analysis_file, 'w', encoding='utf-8') as f:
            f.write("# Email Analysis Report (RAG-Enhanced)\n\n")
            f.write(f"**Analysis Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Emails Analyzed:** {len(emails)}\n")
            f.write(f"**RAG Enabled:** {'Yes' if vectordb else 'No'}\n")
            f.write(f"**Date Range:** {date_from.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}\n\n")
            
            f.write("## LLM Analysis Results\n\n")
            f.write(analysis)
            f.write("\n\n")
            
            f.write("## Basic Metrics\n\n")
            f.write(f"- **Unique Senders:** {basic_metrics['senders']['total_unique_senders']}\n")
            f.write(f"- **Peak Hour:** {basic_metrics['timing']['peak_hour']}:00\n")
            f.write(f"- **Urgent Emails:** {basic_metrics['subjects']['urgent_emails']}\n")

        metrics_file = os.path.join(output_dir, f"metrics_{timestamp}.json")
        with open(metrics_file, 'w', encoding='utf-8') as f:
            json.dump(basic_metrics, f, indent=2, default=str)

        print("\n" + "="*60)
        print("📊 ANALYSIS SUMMARY")
        print("="*60)
        print(f"📧 Emails analyzed: {len(emails)}")
        print(f"🔍 RAG enabled: {'Yes' if vectordb else 'No'}")
        print(f"💾 Results saved to: {output_dir}")

        # Update state
        try:
            latest_dt = max((e.date for e in emails), default=None)
            if latest_dt:
                _save_last_fetch(state_file, latest_dt)
        except Exception:
            pass

        print("\n✅ Analysis completed successfully!")

    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()


def main():
    app_dir = os.path.dirname(__file__)
    config_path = os.path.join(app_dir, 'config.json')
    try:
        config = load_config(config_path)
        asyncio.run(analyze_emails(config))
    except KeyboardInterrupt:
        print("\n⏹️  Analysis interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()