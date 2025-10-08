from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum


class EmailPriority(Enum):
    """Email priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class EmailStatus(Enum):
    """Email status indicators."""
    READ = "read"
    UNREAD = "unread"
    FLAGGED = "flagged"
    DRAFT = "draft"
    DELETED = "deleted"


@dataclass
class EmailAddress:
    """Represents an email address with optional display name."""
    email: str
    name: Optional[str] = None
    
    def __str__(self) -> str:
        if self.name:
            return f"{self.name} <{self.email}>"
        return self.email


@dataclass
class EmailAttachment:
    """Represents an email attachment."""
    filename: str
    content_type: str
    size: int
    content: bytes
    content_id: Optional[str] = None


@dataclass
class EmailMessage:
    """Represents a complete email message."""
    message_id: str
    subject: str
    sender: EmailAddress
    recipients: List[EmailAddress]
    cc: List[EmailAddress]
    bcc: List[EmailAddress]
    date: datetime
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    attachments: List[EmailAttachment] = None
    priority: EmailPriority = EmailPriority.NORMAL
    status: EmailStatus = EmailStatus.UNREAD
    headers: Dict[str, str] = None
    folder: Optional[str] = None
    
    def __post_init__(self):
        if self.attachments is None:
            self.attachments = []
        if self.headers is None:
            self.headers = {}
    
    def save_to_file(self, output_dir: str, format: str = "json") -> str:
        """
        Save email to file in specified format.
        
        Args:
            output_dir: Directory to save the email file
            format: File format ("json", "txt", "eml")
            
        Returns:
            Path to the saved file
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Create safe filename from subject and date
        safe_subject = "".join(c for c in self.subject if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_subject = safe_subject[:50]  # Limit length
        date_str = self.date.strftime("%Y%m%d_%H%M%S")
        message_id_short = self.message_id.replace("<", "").replace(">", "").split("@")[0][:10]
        
        if format == "json":
            filename = f"{date_str}_{message_id_short}_{safe_subject}.json"
            filepath = os.path.join(output_dir, filename)
            
            # Convert to serializable format
            email_data = {
                "message_id": self.message_id,
                "subject": self.subject,
                "sender": {"email": self.sender.email, "name": self.sender.name},
                "recipients": [{"email": r.email, "name": r.name} for r in self.recipients],
                "cc": [{"email": r.email, "name": r.name} for r in self.cc],
                "bcc": [{"email": r.email, "name": r.name} for r in self.bcc],
                "date": self.date.isoformat(),
                "body_text": self.body_text,
                "body_html": self.body_html,
                "attachments": [
                    {
                        "filename": att.filename,
                        "content_type": att.content_type,
                        "size": att.size,
                        "content_id": att.content_id
                    } for att in self.attachments
                ],
                "priority": self.priority.value,
                "status": self.status.value,
                "headers": self.headers,
                "folder": self.folder
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(email_data, f, indent=2, ensure_ascii=False)
                
        elif format == "txt":
            filename = f"{date_str}_{message_id_short}_{safe_subject}.txt"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"Subject: {self.subject}\n")
                f.write(f"From: {self.sender}\n")
                f.write(f"To: {', '.join(str(r) for r in self.recipients)}\n")
                if self.cc:
                    f.write(f"CC: {', '.join(str(r) for r in self.cc)}\n")
                f.write(f"Date: {self.date}\n")
                f.write(f"Priority: {self.priority.value}\n")
                f.write(f"Status: {self.status.value}\n")
                f.write(f"Folder: {self.folder}\n")
                f.write(f"Message ID: {self.message_id}\n")
                f.write("\n" + "="*50 + "\n\n")
                
                if self.body_text:
                    f.write("TEXT BODY:\n")
                    f.write(self.body_text)
                    f.write("\n\n")
                
                if self.body_html:
                    f.write("HTML BODY:\n")
                    f.write(self.body_html)
                    f.write("\n\n")
                
                if self.attachments:
                    f.write("ATTACHMENTS:\n")
                    for att in self.attachments:
                        f.write(f"- {att.filename} ({att.content_type}, {att.size} bytes)\n")
                
                f.write("\n" + "="*50 + "\n\n")
                f.write("HEADERS:\n")
                for key, value in self.headers.items():
                    f.write(f"{key}: {value}\n")
                    
        elif format == "eml":
            filename = f"{date_str}_{message_id_short}_{safe_subject}.eml"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"Message-ID: {self.message_id}\n")
                f.write(f"Subject: {self.subject}\n")
                f.write(f"From: {self.sender}\n")
                f.write(f"To: {', '.join(str(r) for r in self.recipients)}\n")
                if self.cc:
                    f.write(f"Cc: {', '.join(str(r) for r in self.cc)}\n")
                f.write(f"Date: {self.date.strftime('%a, %d %b %Y %H:%M:%S %z')}\n")
                f.write(f"X-Priority: {self.priority.value}\n")
                f.write("MIME-Version: 1.0\n")
                f.write("Content-Type: multipart/mixed; boundary=\"boundary123\"\n")
                f.write("\n")
                
                # Write text body
                if self.body_text:
                    f.write("--boundary123\n")
                    f.write("Content-Type: text/plain; charset=utf-8\n")
                    f.write("\n")
                    f.write(self.body_text)
                    f.write("\n")
                
                # Write HTML body
                if self.body_html:
                    f.write("--boundary123\n")
                    f.write("Content-Type: text/html; charset=utf-8\n")
                    f.write("\n")
                    f.write(self.body_html)
                    f.write("\n")
                
                # Write attachments info (without actual content for now)
                for att in self.attachments:
                    f.write("--boundary123\n")
                    f.write(f"Content-Type: {att.content_type}\n")
                    f.write(f"Content-Disposition: attachment; filename=\"{att.filename}\"\n")
                    f.write(f"Content-Length: {att.size}\n")
                    f.write("\n")
                    f.write("[Attachment content not included in EML format]\n")
                
                f.write("--boundary123--\n")
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        return filepath


@dataclass
class EmailFilter:
    """Filter criteria for email collection."""
    sender: Optional[str] = None
    recipient: Optional[str] = None
    subject_contains: Optional[str] = None
    body_contains: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    folder: Optional[str] = None
    status: Optional[EmailStatus] = None
    priority: Optional[EmailPriority] = None
    has_attachments: Optional[bool] = None
    max_results: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert filter to dictionary for provider use."""
        result = {}
        for key, value in self.__dict__.items():
            if value is not None:
                if isinstance(value, (EmailStatus, EmailPriority)):
                    result[key] = value.value
                elif isinstance(value, datetime):
                    result[key] = value.isoformat()
                else:
                    result[key] = value
        return result


@dataclass
class CollectionOptions:
    """Options for email collection and output."""
    output_dir: Optional[str] = None
    output_format: str = "json"  # json, txt, eml
    save_attachments: bool = False
    attachment_dir: Optional[str] = None
    create_subdirs: bool = True  # Create subdirectories by date/sender
    
    def __post_init__(self):
        if self.save_attachments and not self.attachment_dir:
            self.attachment_dir = os.path.join(self.output_dir or ".", "attachments")


@dataclass
class CollectionResult:
    """Result of email collection operation."""
    messages: List[EmailMessage]
    total_count: int
    filtered_count: int
    collection_time: datetime
    provider_metadata: Optional[Dict[str, Any]] = None
    errors: List[str] = None
    saved_files: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.saved_files is None:
            self.saved_files = []
