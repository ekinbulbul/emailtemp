"""
Microsoft Exchange Collector Usage Example

This example demonstrates how to use the MicrosoftExchangeCollector
to collect emails from Microsoft Exchange/Outlook using Microsoft Graph API.
"""

import os
from datetime import datetime, timedelta

# Import the collector and types
from modules.mail_collector.collectors.microsoftExchange import MicrosoftExchangeCollector
from modules.mail_collector.types import EmailFilter, CollectionOptions


def main():
    """Example usage of MicrosoftExchangeCollector."""
    
    # Set up OAuth credentials (you can also use environment variables)
    tenant_id = os.getenv("TENANT_ID")  # Your Azure AD tenant ID
    client_id = os.getenv("CLIENT_ID")  # Your Azure AD application client ID
    client_secret = os.getenv("CLIENT_SECRET")  # Optional: client secret
    
    try:
        # Initialize the collector
        print("Initializing Microsoft Exchange Collector...")
        collector = MicrosoftExchangeCollector(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            token_cache_file="token_cache.json"
        )
        
        # Test connection
        print("Testing connection...")
        if collector.test_connection():
            print("✓ Connected successfully!")
        else:
            print("✗ Connection failed!")
            return
        
        # Get available folders
        print("\nGetting available folders...")
        folders = collector.get_folders()
        print(f"Available folders: {folders}")
        
        # Create email filter
        filter_criteria = EmailFilter(
            date_from=datetime.now() - timedelta(days=7),  # Last 7 days
            max_results=50,  # Limit to 50 emails
            has_attachments=False,  # Only emails without attachments
            folder="inbox"  # Only from inbox
        )
        
        # Collect emails
        print(f"\nCollecting emails with filter: {filter_criteria.to_dict()}")
        result = collector.collect_emails(filter_criteria)
        
        print(f"✓ Collected {len(result.messages)} emails")
        print(f"Total emails found: {result.total_count}")
        print(f"Collection time: {result.collection_time}")
        
        if result.errors:
            print(f"Errors encountered: {len(result.errors)}")
            for error in result.errors[:3]:  # Show first 3 errors
                print(f"  - {error}")
        
        # Display sample emails
        print(f"\nSample emails:")
        for i, email in enumerate(result.messages[:3]):  # Show first 3 emails
            print(f"\nEmail {i+1}:")
            print(f"  Subject: {email.subject}")
            print(f"  From: {email.sender}")
            print(f"  Date: {email.date}")
            print(f"  Priority: {email.priority.value}")
            print(f"  Status: {email.status.value}")
            if email.body_text:
                preview = email.body_text[:100] + "..." if len(email.body_text) > 100 else email.body_text
                print(f"  Preview: {preview}")
        
        # Save emails to files
        if result.messages:
            print(f"\nSaving emails to files...")
            output_dir = "collected_emails"
            os.makedirs(output_dir, exist_ok=True)
            
            saved_files = []
            for email in result.messages:
                file_path = email.save_to_file(output_dir, format="json")
                saved_files.append(file_path)
            
            print(f"✓ Saved {len(saved_files)} emails to {output_dir}/")
        
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please set TENANT_ID and CLIENT_ID environment variables or pass them directly.")
    except Exception as e:
        print(f"Error: {e}")


def async_example():
    """Example of async usage."""
    import asyncio
    
    async def collect_emails_async():
        """Async email collection example."""
        collector = MicrosoftExchangeCollector()
        
        # Test connection asynchronously
        if await collector.atest_connection():
            print("✓ Async connection test successful!")
        
        # Get folders asynchronously
        folders = await collector.aget_folders()
        print(f"Async folders: {folders}")
        
        # Stream emails asynchronously
        filter_criteria = EmailFilter(max_results=10)
        count = 0
        
        async for email in collector.astream_emails(filter_criteria):
            count += 1
            print(f"Streamed email {count}: {email.subject}")
            if count >= 5:  # Limit for demo
                break
        
        print(f"✓ Streamed {count} emails asynchronously")
    
    # Run async example
    asyncio.run(collect_emails_async())


if __name__ == "__main__":
    print("Microsoft Exchange Collector Example")
    print("=" * 50)
    
    # Run synchronous example
    main()
    
    print("\n" + "=" * 50)
    print("Async Example")
    print("=" * 50)
    
    # Run async example
    async_example()
