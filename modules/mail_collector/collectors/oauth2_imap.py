from __future__ import annotations

import email
import imaplib
import ssl
import json
import os
from datetime import datetime, timedelta
from email.header import decode_header
from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import unquote

from ..types import EmailAddress, EmailAttachment, EmailFilter, EmailMessage, EmailPriority, EmailStatus, CollectionResult


class OAuth2IMAPCollector:
    """
    OAuth2-enabled IMAP-based email collector for Outlook Office 365.
    
    Supports OAuth2 authentication using Microsoft's msal library.
    Handles token caching and automatic token refresh.
    """
    
    def __init__(
        self,
        host: str,
        port: int = 993,
        username: str = "",
        client_id: str = "",
        tenant_id: str = "",
        scopes: List[str] = None,
        config_file: Optional[str] = None,
        cache_file: str = "token_cache.json",
        token_file: str = "access_token.json",
        use_ssl: bool = True,
        timeout: int = 30,
    ):
        """
        Initialize OAuth2 IMAP collector.
        
        Args:
            host: IMAP server hostname
            port: IMAP server port (default: 993 for SSL)
            username: Email username
            client_id: Azure AD application client ID
            tenant_id: Azure AD tenant ID
            scopes: OAuth2 scopes for authentication
            config_file: Path to config.json file (optional)
            cache_file: Path to MSAL token cache file
            token_file: Path to simple token cache file
            use_ssl: Whether to use SSL/TLS encryption
            timeout: Connection timeout in seconds
        """
        self.host = host
        self.port = port
        self.username = username
        self.use_ssl = use_ssl
        self.timeout = timeout
        self._connection: Optional[imaplib.IMAP4_SSL] = None
        
        # Load configuration from file if provided
        if config_file:
            self._load_config_from_file(config_file)
        else:
            self.client_id = client_id
            self.tenant_id = tenant_id
            self.scopes = scopes or ["https://outlook.office365.com/IMAP.AccessAsUser.All"]
            self.cache_file = cache_file
            self.token_file = token_file
        
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
    
    def _load_config_from_file(self, config_file: str):
        """Load OAuth2 configuration from JSON config file."""
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
            
            oauth_config = config.get("oauth2", {})
            self.client_id = oauth_config.get("client_id", "")
            self.tenant_id = oauth_config.get("tenant_id", "")
            self.scopes = oauth_config.get("scopes", ["https://outlook.office365.com/IMAP.AccessAsUser.All"])
            self.cache_file = oauth_config.get("cache_file", "token_cache.json")
            self.token_file = oauth_config.get("token_file", "access_token.json")
            
        except Exception as e:
            raise ValueError(f"Failed to load config from {config_file}: {e}")
    
    def _load_cache(self):
        """Load MSAL token cache."""
        try:
            import msal
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r") as f:
                    return msal.SerializableTokenCache().deserialize(f.read())
            return msal.SerializableTokenCache()
        except ImportError:
            raise ImportError("msal library is required for OAuth2 authentication. Install with: pip install msal")
    
    def _save_cache(self, cache):
        """Save MSAL token cache."""
        if cache.has_state_changed:
            with open(self.cache_file, "w") as f:
                f.write(cache.serialize())
    
    def _save_access_token(self, access_token: str, expires_in: int = 3600):
        """Save access token to a simple JSON file."""
        token_data = {
            "access_token": access_token,
            "expires_at": (datetime.now() + timedelta(seconds=expires_in)).isoformat(),
            "saved_at": datetime.now().isoformat()
        }
        with open(self.token_file, "w") as f:
            json.dump(token_data, f, indent=2)
    
    def _load_access_token(self) -> Optional[str]:
        """Load access token from JSON file if it's still valid."""
        if not os.path.exists(self.token_file):
            return None
        
        try:
            with open(self.token_file, "r") as f:
                token_data = json.load(f)
            
            # Check if token is still valid
            expires_at = datetime.fromisoformat(token_data["expires_at"])
            if datetime.now() < expires_at:
                return token_data["access_token"]
            else:
                return None
        except Exception:
            return None
    
    def _acquire_token(self) -> str:
        """Acquire OAuth2 access token."""
        # First try to load cached token
        cached_token = self._load_access_token()
        if cached_token:
            return cached_token
        
        try:
            import msal
        except ImportError:
            raise ImportError("msal library is required for OAuth2 authentication. Install with: pip install msal")
        
        cache = self._load_cache()
        app = msal.PublicClientApplication(self.client_id, authority=self.authority, token_cache=cache)

        # First try to get token silently from cache
        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(self.scopes, account=accounts[0])
            if result:
                self._save_cache(cache)
                self._save_access_token(result["access_token"], result.get("expires_in", 3600))
                return result["access_token"]

        # Otherwise fall back to device flow
        flow = app.initiate_device_flow(scopes=self.scopes)
        print(f"Please visit: {flow['verification_uri']}")
        print(f"Enter this code: {flow['user_code']}")
        print("Waiting for authentication...")
        
        result = app.acquire_token_by_device_flow(flow)
        self._save_cache(cache)
        self._save_access_token(result["access_token"], result.get("expires_in", 3600))
        return result["access_token"]
    
    def _generate_oauth2_string(self, username: str, access_token: str) -> str:
        """Generate OAuth2 authentication string for IMAP."""
        return f"user={username}\x01auth=Bearer {access_token}\x01\x01"
    
    def _connect(self) -> imaplib.IMAP4_SSL:
        """Establish OAuth2 connection to IMAP server."""
        if self.use_ssl:
            # Create SSL context for secure connection
            context = ssl.create_default_context()
            connection = imaplib.IMAP4_SSL(self.host, self.port, ssl_context=context)
        else:
            connection = imaplib.IMAP4(self.host, self.port)
        
        connection.socket().settimeout(self.timeout)
        
        # Get OAuth2 access token
        access_token = self._acquire_token()
        
        # Authenticate using OAuth2
        auth_string = self._generate_oauth2_string(self.username, access_token)
        connection.authenticate('XOAUTH2', lambda x: auth_string.encode())
        
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
            print(f"OAuth2 IMAP connection error: {e}")
            return False
    
    async def atest_connection(self) -> bool:
        """Test connection to IMAP server asynchronously."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.test_connection)
