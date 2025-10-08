"""
Microsoft Exchange Email Collector Module

This module provides a complete implementation for collecting emails from
Microsoft Exchange/Outlook using Microsoft Graph API with OAuth2 authentication.

The module includes:
- MicrosoftExchangeCollector: Main collector class implementing BaseCollector
- OAuthHandler: Handles OAuth2 authentication flow
- ExchangeClient: Low-level client for Microsoft Graph API operations

Example usage:
    from modules.mail_collector.collectors.microsoftExchange import MicrosoftExchangeCollector
    from modules.mail_collector.types import EmailFilter
    
    # Initialize collector
    collector = MicrosoftExchangeCollector(
        tenant_id="your-tenant-id",
        client_id="your-client-id"
    )
    
    # Test connection
    if collector.test_connection():
        print("Connected successfully!")
    
    # Collect emails
    filter_criteria = EmailFilter(
        date_from=datetime.now() - timedelta(days=7),
        max_results=100
    )
    
    result = collector.collect_emails(filter_criteria)
    print(f"Collected {len(result.messages)} emails")
"""

from .microsoft_exchange import MicrosoftExchangeCollector
from .oauth_handler import OAuthHandler
from .exchange_client import ExchangeClient

__all__ = [
    'MicrosoftExchangeCollector',
    'OAuthHandler', 
    'ExchangeClient'
]
