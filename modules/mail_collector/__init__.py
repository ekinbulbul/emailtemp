from .client import MailCollector
from .types import EmailMessage, EmailFilter, CollectionResult, CollectionOptions, EmailAddress, EmailPriority, EmailStatus
from .collectors.imap import IMAPCollector
from .collectors.pop3 import POP3Collector
from .collectors.oauth2_imap import OAuth2IMAPCollector

__all__ = [
    "MailCollector",
    "IMAPCollector",
    "POP3Collector", 
    "OAuth2IMAPCollector",
    "EmailMessage", 
    "EmailFilter",
    "CollectionResult",
    "CollectionOptions",
    "EmailAddress",
    "EmailPriority", 
    "EmailStatus",
]
