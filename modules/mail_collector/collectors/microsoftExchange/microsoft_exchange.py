"""
Microsoft Exchange Email Collector

This module provides a collector implementation for Microsoft Exchange/Outlook
using Microsoft Graph API with OAuth2 authentication.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime, timedelta
from pathlib import Path

from ...types import EmailFilter, EmailMessage, CollectionResult, EmailAddress, EmailAttachment, EmailPriority, EmailStatus
from ..base import BaseCollector

logger = logging.getLogger(__name__)


class MicrosoftExchangeCollector(BaseCollector):
    """
    Email collector for Microsoft Exchange using Microsoft Graph API.
    
    This collector implements the BaseCollector interface and provides
    functionality to collect emails from Microsoft Exchange/Outlook accounts
    using OAuth2 authentication.
    """
    
    def __init__(self, tenant_id: Optional[str] = None, client_id: Optional[str] = None, 
                 client_secret: Optional[str] = None, token_cache_file: Optional[str] = None):
        """
        Initialize Microsoft Exchange collector.
        
        Args:
            tenant_id: Azure AD tenant ID
            client_id: Azure AD application client ID
            client_secret: Azure AD application client secret
            token_cache_file: Path to token cache file
        """
        self.tenant_id = tenant_id or os.getenv("TENANT_ID")
        self.client_id = client_id or os.getenv("CLIENT_ID")
        self.client_secret = client_secret or os.getenv("CLIENT_SECRET")
        self.token_cache_file = token_cache_file or "token_cache.json"
        
        if not all([self.tenant_id, self.client_id]):
            raise ValueError("Missing required OAuth configuration. Please set TENANT_ID and CLIENT_ID.")
        
        # Initialize OAuth handler and Exchange client
        from .oauth_handler import OAuthHandler
        from .exchange_client import ExchangeClient
        
        self.oauth_handler = OAuthHandler(
            tenant_id=self.tenant_id,
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_cache_file=self.token_cache_file
        )
        self.exchange_client = ExchangeClient(self.oauth_handler)
    
    def collect_emails(
        self, 
        filter_criteria: Optional[EmailFilter] = None,
        **kwargs
    ) -> CollectionResult:
        """
        Collect emails synchronously.
        
        Args:
            filter_criteria: Optional filter to apply to email collection
            **kwargs: Additional collector-specific parameters
            
        Returns:
            CollectionResult containing collected emails and metadata
        """
        logger.info("Starting synchronous email collection from Microsoft Exchange")
        
        start_time = datetime.now()
        messages = []
        errors = []
        
        try:
            # Extract parameters
            folder_id = kwargs.get('folder_id', 'inbox')
            limit = kwargs.get('limit', filter_criteria.max_results if filter_criteria else None)
            include_attachments = kwargs.get('include_attachments', False)
            attachment_dir = kwargs.get('attachment_dir', None)
            
            # Build filter query from criteria
            filter_query = self._build_filter_query(filter_criteria)
            
            # Get emails
            if filter_criteria and filter_criteria.subject_contains:
                result = self.exchange_client.search_messages(
                    query=filter_criteria.subject_contains,
                    folder_id=folder_id,
                    limit=limit or 50
                )
                email_list = result.get("value", [])
            else:
                email_list = list(self.exchange_client.get_all_messages(
                    folder_id=folder_id,
                    limit=limit,
                    filter_query=filter_query
                ))
            
            logger.info(f"Retrieved {len(email_list)} emails")
            
            # Process each email
            for i, email in enumerate(email_list):
                try:
                    processed_email = self._process_email(email, include_attachments, attachment_dir)
                    messages.append(processed_email)
                    
                    if (i + 1) % 10 == 0:
                        logger.info(f"Processed {i + 1} emails...")
                        
                except Exception as e:
                    error_msg = f"Error processing email {email.get('id', 'unknown')}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue
            
            logger.info(f"Successfully collected {len(messages)} emails")
            
            return CollectionResult(
                messages=messages,
                total_count=len(email_list),
                filtered_count=len(messages),
                collection_time=start_time,
                errors=errors
            )
            
        except Exception as e:
            error_msg = f"Error during email collection: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
            return CollectionResult(
                messages=messages,
                total_count=0,
                filtered_count=len(messages),
                collection_time=start_time,
                errors=errors
            )
    
    async def acollect_emails(
        self, 
        filter_criteria: Optional[EmailFilter] = None,
        **kwargs
    ) -> CollectionResult:
        """
        Collect emails asynchronously.
        
        Args:
            filter_criteria: Optional filter to apply to email collection
            **kwargs: Additional collector-specific parameters
            
        Returns:
            CollectionResult containing collected emails and metadata
        """
        # For now, delegate to synchronous version
        # In a real implementation, you might want to use async HTTP clients
        return self.collect_emails(filter_criteria, **kwargs)
    
    async def astream_emails(
        self, 
        filter_criteria: Optional[EmailFilter] = None,
        **kwargs
    ) -> AsyncGenerator[EmailMessage, None]:
        """
        Stream emails asynchronously.
        
        Args:
            filter_criteria: Optional filter to apply to email collection
            **kwargs: Additional collector-specific parameters
            
        Yields:
            EmailMessage objects as they are collected
        """
        folder_id = kwargs.get('folder_id', 'inbox')
        limit = kwargs.get('limit', filter_criteria.max_results if filter_criteria else None)
        include_attachments = kwargs.get('include_attachments', False)
        attachment_dir = kwargs.get('attachment_dir', None)
        
        filter_query = self._build_filter_query(filter_criteria)
        
        try:
            for email in self.exchange_client.get_all_messages(
                folder_id=folder_id,
                limit=limit,
                filter_query=filter_query
            ):
                try:
                    processed_email = self._process_email(email, include_attachments, attachment_dir)
                    yield processed_email
                except Exception as e:
                    logger.error(f"Error processing email {email.get('id', 'unknown')}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error during email streaming: {e}")
    
    def get_folders(self) -> List[str]:
        """
        Get list of available email folders.
        
        Returns:
            List of folder names
        """
        try:
            folders = self.exchange_client.get_mail_folders()
            return [folder.get("displayName", "") for folder in folders if folder.get("displayName")]
        except Exception as e:
            logger.error(f"Error getting folder list: {e}")
            return []
    
    async def aget_folders(self) -> List[str]:
        """
        Get list of available email folders asynchronously.
        
        Returns:
            List of folder names
        """
        return self.get_folders()
    
    def test_connection(self) -> bool:
        """
        Test the connection to the mail server.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try to get user profile to test connection
            user_info = self.exchange_client.get_user_profile()
            return user_info is not None
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    async def atest_connection(self) -> bool:
        """
        Test the connection to the mail server asynchronously.
        
        Returns:
            True if connection is successful, False otherwise
        """
        return self.test_connection()
    
    def _build_filter_query(self, filter_criteria: Optional[EmailFilter]) -> Optional[str]:
        """Build OData filter query from filter criteria."""
        if not filter_criteria:
            return None
        
        filters = []
        
        if filter_criteria.date_from:
            start_str = filter_criteria.date_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            filters.append(f"receivedDateTime ge {start_str}")
        
        if filter_criteria.date_to:
            end_str = filter_criteria.date_to.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            filters.append(f"receivedDateTime le {end_str}")
        
        if filter_criteria.sender:
            filters.append(f"from/emailAddress/address eq '{filter_criteria.sender}'")
        
        if filter_criteria.has_attachments is not None:
            filters.append(f"hasAttachments eq {str(filter_criteria.has_attachments).lower()}")
        
        return " and ".join(filters) if filters else None
    
    def _process_email(self, email: Dict[str, Any], include_attachments: bool,
                      attachment_dir: Optional[str]) -> EmailMessage:
        """
        Process and convert raw email data to EmailMessage object.
        
        Args:
            email: Raw email data from API
            include_attachments: Whether to process attachments
            attachment_dir: Directory for attachment downloads
            
        Returns:
            EmailMessage object
        """
        # Extract sender information
        sender_data = email.get("from", {})
        sender = EmailAddress(
            email=sender_data.get("emailAddress", {}).get("address", ""),
            name=sender_data.get("emailAddress", {}).get("name", "")
        )
        
        # Extract recipients
        recipients = []
        for recipient in email.get("toRecipients", []):
            email_address = recipient.get("emailAddress", {})
            recipients.append(EmailAddress(
                email=email_address.get("address", ""),
                name=email_address.get("name", "")
            ))
        
        # Extract CC recipients
        cc = []
        for recipient in email.get("ccRecipients", []):
            email_address = recipient.get("emailAddress", {})
            cc.append(EmailAddress(
                email=email_address.get("address", ""),
                name=email_address.get("name", "")
            ))
        
        # Extract BCC recipients
        bcc = []
        for recipient in email.get("bccRecipients", []):
            email_address = recipient.get("emailAddress", {})
            bcc.append(EmailAddress(
                email=email_address.get("address", ""),
                name=email_address.get("name", "")
            ))
        
        # Parse date
        date_str = email.get("receivedDateTime")
        if date_str:
            # Parse ISO format date
            date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            date = datetime.now()
        
        # Extract body content
        body_data = email.get("body", {})
        body_text = None
        body_html = None
        
        if body_data:
            content_type = body_data.get("contentType", "text")
            content = body_data.get("content", "")
            
            if content_type == "html":
                body_html = content
                # Simple HTML tag removal for text version
                import re
                body_text = re.sub(r'<[^>]+>', '', content)
            else:
                body_text = content
        
        # Determine priority
        importance = email.get("importance", "normal")
        if importance == "high":
            priority = EmailPriority.HIGH
        elif importance == "low":
            priority = EmailPriority.LOW
        else:
            priority = EmailPriority.NORMAL
        
        # Determine status
        is_read = email.get("isRead", False)
        status = EmailStatus.READ if is_read else EmailStatus.UNREAD
        
        # Process attachments
        attachments = []
        if include_attachments and email.get("hasAttachments"):
            attachments = self._process_attachments(
                email.get("attachments", []),
                email.get("id"),
                attachment_dir
            )
        
        # Extract headers (limited in Graph API)
        headers = {
            "Message-ID": email.get("internetMessageId", ""),
            "Subject": email.get("subject", ""),
            "X-Priority": importance
        }
        
        return EmailMessage(
            message_id=email.get("id", ""),
            subject=email.get("subject", ""),
            sender=sender,
            recipients=recipients,
            cc=cc,
            bcc=bcc,
            date=date,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
            priority=priority,
            status=status,
            headers=headers,
            folder=email.get("parentFolderId", "inbox")
        )
    
    def _process_attachments(self, attachments: List[Dict[str, Any]], 
                           message_id: str, attachment_dir: Optional[str]) -> List[EmailAttachment]:
        """Process email attachments."""
        processed_attachments = []
        
        if not attachment_dir:
            attachment_dir = "attachments"
        
        Path(attachment_dir).mkdir(exist_ok=True)
        
        for attachment in attachments:
            try:
                # Download attachment content
                content = self.exchange_client.download_attachment(
                    message_id, attachment.get("id")
                )
                
                attachment_obj = EmailAttachment(
                    filename=attachment.get("name", "unknown"),
                    content_type=attachment.get("contentType", ""),
                    size=attachment.get("size", 0),
                    content=content,
                    content_id=attachment.get("contentId")
                )
                
                processed_attachments.append(attachment_obj)
                
                # Save to file if directory specified
                if attachment_dir:
                    filename = f"{message_id}_{attachment_obj.filename}"
                    file_path = Path(attachment_dir) / filename
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    logger.info(f"Downloaded attachment: {filename}")
                
            except Exception as e:
                logger.error(f"Error processing attachment {attachment.get('name', 'unknown')}: {e}")
                continue
        
        return processed_attachments
