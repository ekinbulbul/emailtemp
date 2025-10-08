from __future__ import annotations

import email
import imaplib
import ssl
from datetime import datetime
from email.header import decode_header
from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import unquote

from ..types import EmailAddress, EmailAttachment, EmailFilter, EmailMessage, EmailPriority, EmailStatus, CollectionResult


class IMAPCollector:
    """
    IMAP-based email collector.
    
    Supports IMAP servers with SSL/TLS encryption. Handles authentication,
    folder listing, and email retrieval with filtering capabilities.
    """
    
    def __init__(
        self,
        host: str,
        port: int = 993,
        username: str = "",
        password: str = "",
        use_ssl: bool = True,
        timeout: int = 30,
    ):
        """
        Initialize IMAP collector.
        
        Args:
            host: IMAP server hostname
            port: IMAP server port (default: 993 for SSL)
            username: Email username
            password: Email password
            use_ssl: Whether to use SSL/TLS encryption
            timeout: Connection timeout in seconds
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.timeout = timeout
        self._connection: Optional[imaplib.IMAP4_SSL] = None
    
    def _connect(self) -> imaplib.IMAP4_SSL:
        """Establish connection to IMAP server."""
        if self.use_ssl:
            # Create SSL context for secure connection
            context = ssl.create_default_context()
            connection = imaplib.IMAP4_SSL(self.host, self.port, ssl_context=context)
        else:
            connection = imaplib.IMAP4(self.host, self.port)
        
        connection.socket().settimeout(self.timeout)
        connection.login(self.username, self.password)
        return connection
    
    def _decode_header(self, header_value: str) -> str:
        """Decode email header value."""
        if not header_value:
            return ""
        
        decoded_parts = decode_header(header_value)
        decoded_string = ""
        
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                if encoding:
                    decoded_string += part.decode(encoding)
                else:
                    decoded_string += part.decode('utf-8', errors='ignore')
            else:
                decoded_string += part
        
        return decoded_string
    
    def _parse_email_addresses(self, address_string: str) -> List[EmailAddress]:
        """Parse email address string into EmailAddress objects."""
        if not address_string:
            return []
        
        addresses = []
        # Simple parsing - in production, use email.utils.parseaddr
        for addr in address_string.split(','):
            addr = addr.strip()
            if '<' in addr and '>' in addr:
                name, email = addr.split('<', 1)
                name = name.strip().strip('"')
                email = email.strip('>')
                addresses.append(EmailAddress(email=email, name=name))
            else:
                addresses.append(EmailAddress(email=addr))
        
        return addresses
    
    def _parse_attachments(self, message: email.message.Message) -> List[EmailAttachment]:
        """Extract attachments from email message."""
        attachments = []
        
        for part in message.walk():
            if part.get_content_disposition() == 'attachment':
                filename = part.get_filename()
                if filename:
                    filename = self._decode_header(filename)
                    content_type = part.get_content_type()
                    content = part.get_payload(decode=True)
                    if content:
                        attachments.append(EmailAttachment(
                            filename=filename,
                            content_type=content_type,
                            size=len(content),
                            content=content,
                            content_id=part.get('Content-ID')
                        ))
        
        return attachments
    
    def _message_to_email(self, message_data: bytes, folder: str = None) -> EmailMessage:
        """Convert raw email message to EmailMessage object."""
        message = email.message_from_bytes(message_data)
        
        # Extract headers
        subject = self._decode_header(message.get('Subject', ''))
        sender_str = self._decode_header(message.get('From', ''))
        to_str = self._decode_header(message.get('To', ''))
        cc_str = self._decode_header(message.get('Cc', ''))
        bcc_str = self._decode_header(message.get('Bcc', ''))
        date_str = message.get('Date', '')
        message_id = message.get('Message-ID', '')
        
        # Parse addresses
        sender = self._parse_email_addresses(sender_str)[0] if sender_str else EmailAddress("")
        recipients = self._parse_email_addresses(to_str)
        cc = self._parse_email_addresses(cc_str)
        bcc = self._parse_email_addresses(bcc_str)
        
        # Parse date
        try:
            date = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')
        except (ValueError, TypeError):
            try:
                date = datetime.strptime(date_str, '%d %b %Y %H:%M:%S %z')
            except (ValueError, TypeError):
                date = datetime.now()
        
        # Extract body
        body_text = None
        body_html = None
        
        if message.is_multipart():
            for part in message.walk():
                content_type = part.get_content_type()
                if content_type == 'text/plain' and not body_text:
                    body_text = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                elif content_type == 'text/html' and not body_html:
                    body_html = part.get_payload(decode=True).decode('utf-8', errors='ignore')
        else:
            content_type = message.get_content_type()
            if content_type == 'text/plain':
                body_text = message.get_payload(decode=True).decode('utf-8', errors='ignore')
            elif content_type == 'text/html':
                body_html = message.get_payload(decode=True).decode('utf-8', errors='ignore')
        
        # Extract attachments
        attachments = self._parse_attachments(message)
        
        # Determine priority from headers
        priority_header = message.get('X-Priority', '').lower()
        if 'high' in priority_header or 'urgent' in priority_header:
            priority = EmailPriority.HIGH
        elif 'low' in priority_header:
            priority = EmailPriority.LOW
        else:
            priority = EmailPriority.NORMAL
        
        # Extract all headers
        headers = {}
        for key, value in message.items():
            headers[key] = self._decode_header(value)
        
        return EmailMessage(
            message_id=message_id,
            subject=subject,
            sender=sender,
            recipients=recipients,
            cc=cc,
            bcc=bcc,
            date=date,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
            priority=priority,
            status=EmailStatus.UNREAD,  # IMAP doesn't provide this directly
            headers=headers,
            folder=folder
        )
    
    def _build_search_criteria(self, filter_criteria: Optional[EmailFilter]) -> str:
        """Build IMAP search criteria from filter."""
        if not filter_criteria:
            return "ALL"
        
        criteria = []
        
        if filter_criteria.sender:
            criteria.append(f'FROM "{filter_criteria.sender}"')
        
        if filter_criteria.recipient:
            criteria.append(f'TO "{filter_criteria.recipient}"')
        
        if filter_criteria.subject_contains:
            criteria.append(f'SUBJECT "{filter_criteria.subject_contains}"')
        
        if filter_criteria.body_contains:
            criteria.append(f'BODY "{filter_criteria.body_contains}"')
        
        if filter_criteria.date_from:
            date_str = filter_criteria.date_from.strftime('%d-%b-%Y')
            criteria.append(f'SINCE {date_str}')
        
        if filter_criteria.date_to:
            date_str = filter_criteria.date_to.strftime('%d-%b-%Y')
            criteria.append(f'BEFORE {date_str}')
        
        if filter_criteria.has_attachments:
            criteria.append('HASATTACH')
        
        return ' '.join(criteria) if criteria else "ALL"
    
    def collect_emails(
        self, 
        filter_criteria: Optional[EmailFilter] = None,
        folder: str = "INBOX",
        **kwargs
    ) -> CollectionResult:
        """Collect emails synchronously."""
        start_time = datetime.now()
        messages = []
        errors = []
        
        try:
            connection = self._connect()
            connection.select(folder)
            
            search_criteria = self._build_search_criteria(filter_criteria)
            status, message_ids = connection.search(None, search_criteria)
            
            if status != 'OK':
                errors.append(f"Search failed: {message_ids}")
                return CollectionResult(
                    messages=messages,
                    total_count=0,
                    filtered_count=0,
                    collection_time=datetime.now(),
                    errors=errors
                )
            
            message_id_list = message_ids[0].split()
            total_count = len(message_id_list)
            
            # Apply max_results limit
            if filter_criteria and filter_criteria.max_results:
                message_id_list = message_id_list[:filter_criteria.max_results]
            
            filtered_count = len(message_id_list)
            
            for msg_id in message_id_list:
                try:
                    status, msg_data = connection.fetch(msg_id, '(RFC822)')
                    if status == 'OK' and msg_data:
                        email_msg = self._message_to_email(msg_data[0][1], folder)
                        messages.append(email_msg)
                except Exception as e:
                    errors.append(f"Failed to fetch message {msg_id}: {str(e)}")
            
            connection.close()
            connection.logout()
            
        except Exception as e:
            errors.append(f"Connection error: {str(e)}")
        
        return CollectionResult(
            messages=messages,
            total_count=total_count,
            filtered_count=filtered_count,
            collection_time=datetime.now(),
            errors=errors
        )
    
    async def acollect_emails(
        self, 
        filter_criteria: Optional[EmailFilter] = None,
        folder: str = "INBOX",
        **kwargs
    ) -> CollectionResult:
        """Collect emails asynchronously."""
        # For now, run sync version in thread pool
        # In production, use aioimaplib or similar async IMAP library
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.collect_emails, filter_criteria, folder)
    
    async def astream_emails(
        self, 
        filter_criteria: Optional[EmailFilter] = None,
        folder: str = "INBOX",
        **kwargs
    ) -> AsyncGenerator[EmailMessage, None]:
        """Stream emails asynchronously."""
        result = await self.acollect_emails(filter_criteria, folder, **kwargs)
        for message in result.messages:
            yield message
    
    def get_folders(self) -> List[str]:
        """Get list of available folders."""
        try:
            connection = self._connect()
            status, folders = connection.list()
            connection.logout()
            
            if status == 'OK':
                folder_names = []
                for folder in folders:
                    # Parse folder name from IMAP LIST response
                    folder_str = folder.decode('utf-8')
                    # Extract folder name between quotes
                    if '"' in folder_str:
                        start = folder_str.find('"') + 1
                        end = folder_str.find('"', start)
                        folder_name = folder_str[start:end]
                        folder_names.append(folder_name)
                return folder_names
            return []
        except Exception:
            return []
    
    async def aget_folders(self) -> List[str]:
        """Get list of available folders asynchronously."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_folders)
    
    def test_connection(self) -> bool:
        """Test connection to IMAP server."""
        try:
            connection = self._connect()
            connection.logout()
            return True
        except Exception as e:
            print(f"IMAP connection error: {e}")
            return False
    
    async def atest_connection(self) -> bool:
        """Test connection to IMAP server asynchronously."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.test_connection)
