from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Optional

from ..types import EmailFilter, EmailMessage, CollectionResult


class BaseCollector(ABC):
    """
    Abstract base class for email collectors.
    
    Defines the interface that all email collector implementations must follow.
    This allows for easy extension with new mail protocols and providers.
    """
    
    @abstractmethod
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
        raise NotImplementedError
    
    @abstractmethod
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
        raise NotImplementedError
    
    @abstractmethod
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
        raise NotImplementedError
    
    @abstractmethod
    def get_folders(self) -> List[str]:
        """
        Get list of available email folders.
        
        Returns:
            List of folder names
        """
        raise NotImplementedError
    
    @abstractmethod
    async def aget_folders(self) -> List[str]:
        """
        Get list of available email folders asynchronously.
        
        Returns:
            List of folder names
        """
        raise NotImplementedError
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test the connection to the mail server.
        
        Returns:
            True if connection is successful, False otherwise
        """
        raise NotImplementedError
    
    @abstractmethod
    async def atest_connection(self) -> bool:
        """
        Test the connection to the mail server asynchronously.
        
        Returns:
            True if connection is successful, False otherwise
        """
        raise NotImplementedError
