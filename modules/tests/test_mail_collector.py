import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from mail_collector import MailCollector, EmailFilter, EmailMessage, EmailAddress, EmailPriority, EmailStatus
from mail_collector.collectors.imap import IMAPCollector
from mail_collector.collectors.pop3 import POP3Collector


class TestEmailFilter:
    """Test EmailFilter functionality."""
    
    def test_empty_filter(self):
        """Test empty filter creation."""
        filter_criteria = EmailFilter()
        assert filter_criteria.sender is None
        assert filter_criteria.recipient is None
        assert filter_criteria.subject_contains is None
        assert filter_criteria.body_contains is None
        assert filter_criteria.date_from is None
        assert filter_criteria.date_to is None
        assert filter_criteria.folder is None
        assert filter_criteria.status is None
        assert filter_criteria.priority is None
        assert filter_criteria.has_attachments is None
        assert filter_criteria.max_results is None
    
    def test_filter_with_values(self):
        """Test filter with specific values."""
        date_from = datetime.now() - timedelta(days=7)
        date_to = datetime.now()
        
        filter_criteria = EmailFilter(
            sender="test@example.com",
            recipient="user@example.com",
            subject_contains="urgent",
            body_contains="meeting",
            date_from=date_from,
            date_to=date_to,
            folder="INBOX",
            status=EmailStatus.UNREAD,
            priority=EmailPriority.HIGH,
            has_attachments=True,
            max_results=100
        )
        
        assert filter_criteria.sender == "test@example.com"
        assert filter_criteria.recipient == "user@example.com"
        assert filter_criteria.subject_contains == "urgent"
        assert filter_criteria.body_contains == "meeting"
        assert filter_criteria.date_from == date_from
        assert filter_criteria.date_to == date_to
        assert filter_criteria.folder == "INBOX"
        assert filter_criteria.status == EmailStatus.UNREAD
        assert filter_criteria.priority == EmailPriority.HIGH
        assert filter_criteria.has_attachments is True
        assert filter_criteria.max_results == 100
    
    def test_filter_to_dict(self):
        """Test filter conversion to dictionary."""
        date_from = datetime.now() - timedelta(days=7)
        filter_criteria = EmailFilter(
            sender="test@example.com",
            status=EmailStatus.UNREAD,
            priority=EmailPriority.HIGH,
            date_from=date_from,
            max_results=50
        )
        
        result = filter_criteria.to_dict()
        
        assert result["sender"] == "test@example.com"
        assert result["status"] == "unread"
        assert result["priority"] == "high"
        assert result["date_from"] == date_from.isoformat()
        assert result["max_results"] == 50
        assert "recipient" not in result
        assert "subject_contains" not in result


class TestEmailMessage:
    """Test EmailMessage functionality."""
    
    def test_email_message_creation(self):
        """Test basic email message creation."""
        sender = EmailAddress("sender@example.com", "Test Sender")
        recipient = EmailAddress("recipient@example.com", "Test Recipient")
        
        message = EmailMessage(
            message_id="<test@example.com>",
            subject="Test Subject",
            sender=sender,
            recipients=[recipient],
            cc=[],
            bcc=[],
            date=datetime.now(),
            body_text="Test body",
            body_html="<p>Test body</p>"
        )
        
        assert message.message_id == "<test@example.com>"
        assert message.subject == "Test Subject"
        assert message.sender.email == "sender@example.com"
        assert message.sender.name == "Test Sender"
        assert len(message.recipients) == 1
        assert message.recipients[0].email == "recipient@example.com"
        assert message.body_text == "Test body"
        assert message.body_html == "<p>Test body</p>"
        assert message.priority == EmailPriority.NORMAL
        assert message.status == EmailStatus.UNREAD
        assert message.attachments == []
        assert message.headers == {}
    
    def test_email_address_str(self):
        """Test EmailAddress string representation."""
        addr_with_name = EmailAddress("test@example.com", "Test User")
        addr_without_name = EmailAddress("test@example.com")
        
        assert str(addr_with_name) == "Test User <test@example.com>"
        assert str(addr_without_name) == "test@example.com"


class TestMailCollector:
    """Test MailCollector client functionality."""
    
    def test_mail_collector_initialization(self):
        """Test mail collector initialization."""
        mock_collector = Mock()
        client = MailCollector(mock_collector)
        
        assert client._collector == mock_collector
    
    def test_collect_emails_delegation(self):
        """Test that collect_emails delegates to collector."""
        mock_collector = Mock()
        mock_result = Mock()
        mock_collector.collect_emails.return_value = mock_result
        
        client = MailCollector(mock_collector)
        filter_criteria = EmailFilter(sender="test@example.com")
        
        result = client.collect_emails(filter_criteria)
        
        mock_collector.collect_emails.assert_called_once_with(filter_criteria=filter_criteria)
        assert result == mock_result
    
    @pytest.mark.asyncio
    async def test_acollect_emails_delegation(self):
        """Test that acollect_emails delegates to collector."""
        mock_collector = Mock()
        mock_result = Mock()
        
        # Create an async mock function
        async def mock_acollect_emails(**kwargs):
            return mock_result
        
        mock_collector.acollect_emails = mock_acollect_emails
        
        client = MailCollector(mock_collector)
        filter_criteria = EmailFilter(sender="test@example.com")
        
        result = await client.acollect_emails(filter_criteria)
        
        # Verify the method was called (we can't easily assert on async calls)
        assert result == mock_result
    
    @pytest.mark.asyncio
    async def test_astream_emails_delegation(self):
        """Test that astream_emails delegates to collector."""
        mock_collector = Mock()
        mock_message = Mock()
        
        # Create a proper async generator
        async def mock_astream():
            yield mock_message
        
        mock_collector.astream_emails.return_value = mock_astream()
        
        client = MailCollector(mock_collector)
        filter_criteria = EmailFilter(sender="test@example.com")
        
        messages = []
        async for message in client.astream_emails(filter_criteria):
            messages.append(message)
        
        mock_collector.astream_emails.assert_called_once_with(filter_criteria=filter_criteria)
        assert len(messages) == 1
        assert messages[0] == mock_message
    
    def test_get_folders_delegation(self):
        """Test that get_folders delegates to collector."""
        mock_collector = Mock()
        mock_folders = ["INBOX", "Sent", "Drafts"]
        mock_collector.get_folders.return_value = mock_folders
        
        client = MailCollector(mock_collector)
        folders = client.get_folders()
        
        mock_collector.get_folders.assert_called_once()
        assert folders == mock_folders
    
    def test_test_connection_delegation(self):
        """Test that test_connection delegates to collector."""
        mock_collector = Mock()
        mock_collector.test_connection.return_value = True
        
        client = MailCollector(mock_collector)
        result = client.test_connection()
        
        mock_collector.test_connection.assert_called_once()
        assert result is True


class TestIMAPCollector:
    """Test IMAPCollector functionality."""
    
    def test_imap_collector_initialization(self):
        """Test IMAP collector initialization."""
        collector = IMAPCollector(
            host="imap.example.com",
            port=993,
            username="test@example.com",
            password="password",
            use_ssl=True,
            timeout=30
        )
        
        assert collector.host == "imap.example.com"
        assert collector.port == 993
        assert collector.username == "test@example.com"
        assert collector.password == "password"
        assert collector.use_ssl is True
        assert collector.timeout == 30
        assert collector._connection is None
    
    def test_build_search_criteria_empty_filter(self):
        """Test building search criteria with empty filter."""
        collector = IMAPCollector("test.com")
        criteria = collector._build_search_criteria(None)
        assert criteria == "ALL"
    
    def test_build_search_criteria_with_filter(self):
        """Test building search criteria with filter."""
        collector = IMAPCollector("test.com")
        filter_criteria = EmailFilter(
            sender="test@example.com",
            subject_contains="urgent",
            has_attachments=True
        )
        
        criteria = collector._build_search_criteria(filter_criteria)
        expected = 'FROM "test@example.com" SUBJECT "urgent" HASATTACH'
        assert criteria == expected
    
    @patch('imaplib.IMAP4_SSL')
    def test_test_connection_success(self, mock_imaplib):
        """Test successful connection test."""
        mock_connection = Mock()
        mock_imaplib.return_value = mock_connection
        
        collector = IMAPCollector("test.com", username="user", password="pass")
        result = collector.test_connection()
        
        assert result is True
        mock_connection.login.assert_called_once_with("user", "pass")
        mock_connection.logout.assert_called_once()
    
    @patch('imaplib.IMAP4_SSL')
    def test_test_connection_failure(self, mock_imaplib):
        """Test failed connection test."""
        mock_imaplib.side_effect = Exception("Connection failed")
        
        collector = IMAPCollector("test.com", username="user", password="pass")
        result = collector.test_connection()
        
        assert result is False


class TestPOP3Collector:
    """Test POP3Collector functionality."""
    
    def test_pop3_collector_initialization(self):
        """Test POP3 collector initialization."""
        collector = POP3Collector(
            host="pop.example.com",
            port=995,
            username="test@example.com",
            password="password",
            use_ssl=True,
            timeout=30
        )
        
        assert collector.host == "pop.example.com"
        assert collector.port == 995
        assert collector.username == "test@example.com"
        assert collector.password == "password"
        assert collector.use_ssl is True
        assert collector.timeout == 30
    
    def test_matches_filter_empty_filter(self):
        """Test filter matching with empty filter."""
        collector = POP3Collector("test.com")
        message = EmailMessage(
            message_id="test",
            subject="Test",
            sender=EmailAddress("test@example.com"),
            recipients=[],
            cc=[],
            bcc=[],
            date=datetime.now()
        )
        
        assert collector._matches_filter(message, None) is True
    
    def test_matches_filter_sender_match(self):
        """Test filter matching with sender filter."""
        collector = POP3Collector("test.com")
        message = EmailMessage(
            message_id="test",
            subject="Test",
            sender=EmailAddress("test@example.com"),
            recipients=[],
            cc=[],
            bcc=[],
            date=datetime.now()
        )
        
        filter_criteria = EmailFilter(sender="test@example.com")
        assert collector._matches_filter(message, filter_criteria) is True
        
        filter_criteria = EmailFilter(sender="other@example.com")
        assert collector._matches_filter(message, filter_criteria) is False
    
    def test_matches_filter_subject_match(self):
        """Test filter matching with subject filter."""
        collector = POP3Collector("test.com")
        message = EmailMessage(
            message_id="test",
            subject="Urgent Meeting",
            sender=EmailAddress("test@example.com"),
            recipients=[],
            cc=[],
            bcc=[],
            date=datetime.now()
        )
        
        filter_criteria = EmailFilter(subject_contains="urgent")
        assert collector._matches_filter(message, filter_criteria) is True
        
        filter_criteria = EmailFilter(subject_contains="unrelated")
        assert collector._matches_filter(message, filter_criteria) is False
    
    def test_get_folders(self):
        """Test that POP3 returns only INBOX folder."""
        collector = POP3Collector("test.com")
        folders = collector.get_folders()
        
        assert folders == ["INBOX"]
    
    @patch('poplib.POP3_SSL')
    def test_test_connection_success(self, mock_poplib):
        """Test successful connection test."""
        mock_connection = Mock()
        mock_poplib.return_value = mock_connection
        
        collector = POP3Collector("test.com", username="user", password="pass")
        result = collector.test_connection()
        
        assert result is True
        mock_connection.user.assert_called_once_with("user")
        mock_connection.pass_.assert_called_once_with("pass")
        mock_connection.quit.assert_called_once()
    
    @patch('poplib.POP3_SSL')
    def test_test_connection_failure(self, mock_poplib):
        """Test failed connection test."""
        mock_poplib.side_effect = Exception("Connection failed")
        
        collector = POP3Collector("test.com", username="user", password="pass")
        result = collector.test_connection()
        
        assert result is False