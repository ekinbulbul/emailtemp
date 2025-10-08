from __future__ import annotations

import email
import poplib
import ssl
from datetime import datetime
from email.header import decode_header
from typing import Any, AsyncGenerator, Dict, List, Optional

from ..types import EmailAddress, EmailAttachment, EmailFilter, EmailMessage, EmailPriority, EmailStatus, CollectionResult


class POP3Collector:
    """
    POP3-based email collector.
    
    Supports POP3 servers with SSL/TLS encryption. Note that POP3 has limitations
    compared to IMAP (no folder support, limited search capabilities).
    """
    
    def __init__(
        self,
        host: str,
        port: int = 995,
        username: str = "",
        password: str = "",
        use_ssl: bool = True,
        timeout: int = 30,
    ):
        """
        Initialize POP3 collector.
        
        Args:
            host: POP3 server hostname
            port: POP3 server port (default: 995 for SSL)
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
    
    def _connect(self) -> poplib.POP3_SSL:
        """Establish connection to POP3 server."""
        if self.use_ssl:
            connection = poplib.POP3_SSL(self.host, self.port, timeout=self.timeout)
        else:
            connection = poplib.POP3(self.host, self.port, timeout=self.timeout)
        
        connection.user(self.username)
        connection.pass_(self.password)
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
    
    def _message_to_email(self, message_data: bytes) -> EmailMessage:
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
            status=EmailStatus.UNREAD,
            headers=headers,
            folder="INBOX"  # POP3 doesn't support folders
        )
    
    def collect_emails(
        self, 
        filter_criteria: Optional[EmailFilter] = None,
        **kwargs
    ) -> CollectionResult:
        """Collect emails synchronously."""
        start_time = datetime.now()
        messages = []
        errors = []
        
        try:
            connection = self._connect()
            
            # Get message count
            message_count, _ = connection.stat()
            total_count = message_count
            
            # POP3 doesn't support server-side filtering, so we collect all and filter client-side
            message_ids = list(range(1, message_count + 1))
            
            # Apply max_results limit
            if filter_criteria and filter_criteria.max_results:
                message_ids = message_ids[:filter_criteria.max_results]
            
            filtered_count = len(message_ids)
            
            for msg_id in message_ids:
                try:
                    # Retrieve message
                    _, msg_lines, _ = connection.retr(msg_id)
                    msg_data = b'\n'.join(msg_lines)
                    email_msg = self._message_to_email(msg_data)
                    
                    # Apply client-side filtering
                    if self._matches_filter(email_msg, filter_criteria):
                        messages.append(email_msg)
                        
                except Exception as e:
                    errors.append(f"Failed to fetch message {msg_id}: {str(e)}")
            
            connection.quit()
            
        except Exception as e:
            errors.append(f"Connection error: {str(e)}")
        
        return CollectionResult(
            messages=messages,
            total_count=total_count,
            filtered_count=filtered_count,
            collection_time=datetime.now(),
            errors=errors
        )
    
    def _matches_filter(self, message: EmailMessage, filter_criteria: Optional[EmailFilter]) -> bool:
        """Check if message matches filter criteria."""
        if not filter_criteria:
            return True
        
        if filter_criteria.sender and filter_criteria.sender.lower() not in message.sender.email.lower():
            return False
        
        if filter_criteria.recipient:
            recipient_emails = [r.email.lower() for r in message.recipients]
            if filter_criteria.recipient.lower() not in recipient_emails:
                return False
        
        if filter_criteria.subject_contains and filter_criteria.subject_contains.lower() not in message.subject.lower():
            return False
        
        if filter_criteria.body_contains:
            body_text = (message.body_text or "").lower()
            body_html = (message.body_html or "").lower()
            if filter_criteria.body_contains.lower() not in body_text and filter_criteria.body_contains.lower() not in body_html:
                return False
        
        if filter_criteria.date_from and message.date < filter_criteria.date_from:
            return False
        
        if filter_criteria.date_to and message.date > filter_criteria.date_to:
            return False
        
        if filter_criteria.has_attachments is not None:
            if filter_criteria.has_attachments and not message.attachments:
                return False
            if not filter_criteria.has_attachments and message.attachments:
                return False
        
        return True
    
    async def acollect_emails(
        self, 
        filter_criteria: Optional[EmailFilter] = None,
        **kwargs
    ) -> CollectionResult:
        """Collect emails asynchronously."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.collect_emails, filter_criteria)
    
    async def astream_emails(
        self, 
        filter_criteria: Optional[EmailFilter] = None,
        **kwargs
    ) -> AsyncGenerator[EmailMessage, None]:
        """Stream emails asynchronously."""
        result = await self.acollect_emails(filter_criteria, **kwargs)
        for message in result.messages:
            yield message
    
    def get_folders(self) -> List[str]:
        """POP3 doesn't support folders."""
        return ["INBOX"]
    
    async def aget_folders(self) -> List[str]:
        """POP3 doesn't support folders."""
        return ["INBOX"]
    
    def test_connection(self) -> bool:
        """Test connection to POP3 server."""
        try:
            connection = self._connect()
            connection.quit()
            return True
        except Exception:
            return False
    
    async def atest_connection(self) -> bool:
        """Test connection to POP3 server asynchronously."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.test_connection)
