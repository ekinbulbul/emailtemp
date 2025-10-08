from __future__ import annotations

import os
from typing import AsyncGenerator, List, Optional

from .collectors.base import BaseCollector
from .types import EmailFilter, EmailMessage, CollectionResult, CollectionOptions


class MailCollector:
    """
    Main client for collecting emails from various sources.
    
    Provides a unified interface for email collection regardless of the underlying
    mail server or protocol used.
    """
    
    def __init__(self, collector: BaseCollector):
        """
        Initialize the mail collector with a specific collector implementation.
        
        Args:
            collector: The collector implementation (IMAP, POP3, Exchange, etc.)
        """
        self._collector = collector
    
    def collect_emails(
        self, 
        filter_criteria: Optional[EmailFilter] = None,
        options: Optional[CollectionOptions] = None,
        **kwargs
    ) -> CollectionResult:
        """
        Collect emails synchronously based on filter criteria.
        
        Args:
            filter_criteria: Optional filter to apply to email collection
            options: Optional collection and output options
            **kwargs: Additional collector-specific parameters
            
        Returns:
            CollectionResult containing collected emails and metadata
        """
        result = self._collector.collect_emails(filter_criteria=filter_criteria, **kwargs)
        
        # Save emails to files if output options are specified
        if options and options.output_dir:
            self._save_emails(result, options)
        
        return result
    
    async def acollect_emails(
        self, 
        filter_criteria: Optional[EmailFilter] = None,
        options: Optional[CollectionOptions] = None,
        **kwargs
    ) -> CollectionResult:
        """
        Collect emails asynchronously based on filter criteria.
        
        Args:
            filter_criteria: Optional filter to apply to email collection
            options: Optional collection and output options
            **kwargs: Additional collector-specific parameters
            
        Returns:
            CollectionResult containing collected emails and metadata
        """
        result = await self._collector.acollect_emails(filter_criteria=filter_criteria, **kwargs)
        
        # Save emails to files if output options are specified
        if options and options.output_dir:
            self._save_emails(result, options)
        
        return result
    
    async def astream_emails(
        self, 
        filter_criteria: Optional[EmailFilter] = None,
        **kwargs
    ) -> AsyncGenerator[EmailMessage, None]:
        """
        Stream emails asynchronously as they are collected.
        
        Args:
            filter_criteria: Optional filter to apply to email collection
            **kwargs: Additional collector-specific parameters
            
        Yields:
            EmailMessage objects as they are collected
        """
        async for message in self._collector.astream_emails(filter_criteria=filter_criteria, **kwargs):
            yield message
    
    def get_folders(self) -> List[str]:
        """
        Get list of available email folders.
        
        Returns:
            List of folder names
        """
        return self._collector.get_folders()
    
    async def aget_folders(self) -> List[str]:
        """
        Get list of available email folders asynchronously.
        
        Returns:
            List of folder names
        """
        return await self._collector.aget_folders()
    
    def test_connection(self) -> bool:
        """
        Test the connection to the mail server.
        
        Returns:
            True if connection is successful, False otherwise
        """
        return self._collector.test_connection()
    
    async def atest_connection(self) -> bool:
        """
        Test the connection to the mail server asynchronously.
        
        Returns:
            True if connection is successful, False otherwise
        """
        return await self._collector.atest_connection()
    
    def _save_emails(self, result: CollectionResult, options: CollectionOptions) -> None:
        """
        Save collected emails to files based on collection options.
        
        Args:
            result: Collection result containing emails
            options: Collection options specifying output format and location
        """
        for email in result.messages:
            try:
                # Determine output directory
                output_dir = options.output_dir
                
                if options.create_subdirs:
                    # Create subdirectory structure: YYYY-MM-DD/sender_email/
                    date_str = email.date.strftime("%Y-%m-%d")
                    sender_dir = email.sender.email.split("@")[0]  # Get username part
                    safe_sender_dir = "".join(c for c in sender_dir if c.isalnum() or c in ('-', '_'))
                    output_dir = os.path.join(options.output_dir, date_str, safe_sender_dir)
                
                # Save email to file
                filepath = email.save_to_file(output_dir, options.output_format)
                result.saved_files.append(filepath)
                
                # Save attachments if requested
                if options.save_attachments and email.attachments:
                    self._save_attachments(email, options.attachment_dir)
                    
            except Exception as e:
                result.errors.append(f"Failed to save email {email.message_id}: {str(e)}")
    
    def _save_attachments(self, email: EmailMessage, attachment_dir: str) -> None:
        """
        Save email attachments to files.
        
        Args:
            email: Email message containing attachments
            attachment_dir: Directory to save attachments
        """
        os.makedirs(attachment_dir, exist_ok=True)
        
        for attachment in email.attachments:
            try:
                # Create safe filename
                safe_filename = "".join(c for c in attachment.filename if c.isalnum() or c in ('.', '-', '_'))
                filepath = os.path.join(attachment_dir, safe_filename)
                
                # Write attachment content
                with open(filepath, 'wb') as f:
                    f.write(attachment.content)
                    
            except Exception as e:
                # Add error to a general error list - we'd need to modify EmailMessage to track per-attachment errors
                pass
