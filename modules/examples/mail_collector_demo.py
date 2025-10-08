#!/usr/bin/env python3
"""
Test script for mail collector with output folder functionality.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mail_collector import MailCollector, EmailFilter, CollectionOptions
from mail_collector.collectors.imap import IMAPCollector

def main():
    print("🚀 Testing Mail Collector Library with Output")
    print("=" * 60)

    # Initialize collector
    imap_collector = IMAPCollector(
        host="outlook.office365.com",
        username=
        password=
        use_ssl=True
    )

    # Create client
    mail_client = MailCollector(imap_collector)

    print("Testing connection...")
    if mail_client.test_connection():
        print("✅ Connection successful!")
        
        # Get folders
        folders = mail_client.get_folders()
        print(f"📁 Available folders: {folders}")
        
        # Create output directory
        output_dir = "collected_emails"
        print(f"📂 Output directory: {output_dir}")
        
        # Create collection options
        options = CollectionOptions(
            output_dir=output_dir,
            output_format="json",  # Can be "json", "txt", or "eml"
            save_attachments=True,
            create_subdirs=True  # Create date/sender subdirectories
        )
        
        # Create filter for recent emails
        filter_criteria = EmailFilter(
            max_results=5  # Limit to 5 emails for testing
        )
        
        print("📧 Collecting emails with output...")
        result = mail_client.collect_emails(filter_criteria, options, folder="INBOX")
        
        print(f"📧 Collected {len(result.messages)} emails")
        print(f"📊 Total emails found: {result.total_count}")
        print(f"💾 Saved {len(result.saved_files)} files")
        
        if result.errors:
            print(f"⚠️  Errors: {result.errors}")
        
        # Show saved files
        if result.saved_files:
            print(f"\n📁 Saved files:")
            for filepath in result.saved_files:
                print(f"  - {filepath}")
        
        # Show email details
        print(f"\n📧 Email Details:")
        for i, email in enumerate(result.messages, 1):
            print(f"\n--- Email {i} ---")
            print(f"Subject: {email.subject}")
            print(f"From: {email.sender}")
            print(f"Date: {email.date}")
            print(f"Attachments: {len(email.attachments)}")
            
        # Test different output formats
        print(f"\n🔄 Testing different output formats...")
        
        # Test TXT format
        txt_options = CollectionOptions(
            output_dir=os.path.join(output_dir, "txt_format"),
            output_format="txt",
            create_subdirs=False
        )
        
        txt_result = mail_client.collect_emails(filter_criteria, txt_options, folder="INBOX")
        print(f"📄 Saved {len(txt_result.saved_files)} TXT files")
        
        # Test EML format
        eml_options = CollectionOptions(
            output_dir=os.path.join(output_dir, "eml_format"),
            output_format="eml",
            create_subdirs=False
        )
        
        eml_result = mail_client.collect_emails(filter_criteria, eml_options, folder="INBOX")
        print(f"📧 Saved {len(eml_result.saved_files)} EML files")
        
        print(f"\n✅ All emails saved successfully!")
        print(f"📂 Check the '{output_dir}' directory for saved files")
        
    else:
        print("❌ Connection failed!")
        print("This might be due to:")
        print("- Invalid credentials")
        print("- Gmail requiring app-specific passwords")
        print("- Two-factor authentication not properly configured")
        print("- IMAP access not enabled in Gmail settings")

if __name__ == "__main__":
    main()
