"""
Microsoft Exchange API Client

This module provides a client for interacting with Microsoft Graph API
to perform mail operations on Exchange/Outlook.
"""

import requests
import json
from typing import List, Dict, Any, Optional, Generator
from datetime import datetime, timedelta
from urllib.parse import urlencode

from .oauth_handler import OAuthHandler


class ExchangeClient:
    """Client for Microsoft Exchange API operations."""
    
    BASE_URL = "https://graph.microsoft.com/v1.0"
    
    def __init__(self, oauth_handler: OAuthHandler):
        """
        Initialize Exchange client.
        
        Args:
            oauth_handler: OAuth handler instance for authentication
        """
        self.oauth_handler = oauth_handler
        self.session = requests.Session()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers with authorization token."""
        token = self.oauth_handler.get_access_token()
        if not token:
            raise ValueError("No valid access token available")
        
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make authenticated request to Microsoft Graph API.
        
        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request parameters
            
        Returns:
            Response object
        """
        headers = self._get_headers()
        kwargs.setdefault('headers', {}).update(headers)
        
        response = self.session.request(method, url, **kwargs)
        
        # Handle rate limiting
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            print(f"Rate limited. Waiting {retry_after} seconds...")
            import time
            time.sleep(retry_after)
            return self._make_request(method, url, **kwargs)
        
        return response
    
    def get_mail_folders(self) -> List[Dict[str, Any]]:
        """
        Get list of mail folders.
        
        Returns:
            List of mail folder dictionaries
        """
        url = f"{self.BASE_URL}/me/mailFolders"
        response = self._make_request("GET", url)
        
        if response.status_code == 200:
            return response.json().get("value", [])
        else:
            raise Exception(f"Failed to get mail folders: {response.status_code} - {response.text}")
    
    def get_messages(self, folder_id: str = "inbox", limit: int = 50, 
                    skip_token: Optional[str] = None, 
                    filter_query: Optional[str] = None,
                    select_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get messages from a specific folder.
        
        Args:
            folder_id: ID of the mail folder (default: "inbox")
            limit: Maximum number of messages to retrieve
            skip_token: Token for pagination
            filter_query: OData filter query
            select_fields: Fields to select in response
            
        Returns:
            Dictionary containing messages and pagination info
        """
        url = f"{self.BASE_URL}/me/mailFolders/{folder_id}/messages"
        
        params = {
            "$top": min(limit, 999),  # Microsoft Graph API limit
            "$orderby": "receivedDateTime desc"
        }
        
        if skip_token:
            params["$skiptoken"] = skip_token
        
        if filter_query:
            params["$filter"] = filter_query
        
        if select_fields:
            params["$select"] = ",".join(select_fields)
        
        # Add expand for attachments if not explicitly excluded
        if not select_fields or "attachments" not in select_fields:
            params["$expand"] = "attachments"
        
        query_string = urlencode(params)
        full_url = f"{url}?{query_string}"
        
        response = self._make_request("GET", full_url)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get messages: {response.status_code} - {response.text}")
    
    def get_message_details(self, message_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific message.
        
        Args:
            message_id: ID of the message
            
        Returns:
            Message details dictionary
        """
        url = f"{self.BASE_URL}/me/messages/{message_id}"
        params = {"$expand": "attachments"}
        
        query_string = urlencode(params)
        full_url = f"{url}?{query_string}"
        
        response = self._make_request("GET", full_url)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get message details: {response.status_code} - {response.text}")
    
    def download_attachment(self, message_id: str, attachment_id: str, 
                           save_path: Optional[str] = None) -> bytes:
        """
        Download an attachment from a message.
        
        Args:
            message_id: ID of the message
            attachment_id: ID of the attachment
            save_path: Optional path to save the attachment
            
        Returns:
            Attachment content as bytes
        """
        url = f"{self.BASE_URL}/me/messages/{message_id}/attachments/{attachment_id}/$value"
        
        response = self._make_request("GET", url)
        
        if response.status_code == 200:
            content = response.content
            
            if save_path:
                with open(save_path, 'wb') as f:
                    f.write(content)
            
            return content
        else:
            raise Exception(f"Failed to download attachment: {response.status_code} - {response.text}")
    
    def search_messages(self, query: str, folder_id: str = "inbox", 
                       limit: int = 50) -> Dict[str, Any]:
        """
        Search messages using Microsoft Graph search.
        
        Args:
            query: Search query string
            folder_id: ID of the folder to search in
            limit: Maximum number of results
            
        Returns:
            Search results dictionary
        """
        url = f"{self.BASE_URL}/me/mailFolders/{folder_id}/messages"
        
        params = {
            "$search": f'"{query}"',
            "$top": min(limit, 999),
            "$orderby": "receivedDateTime desc"
        }
        
        query_string = urlencode(params)
        full_url = f"{url}?{query_string}"
        
        response = self._make_request("GET", full_url)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to search messages: {response.status_code} - {response.text}")
    
    def get_messages_by_date_range(self, start_date: datetime, end_date: datetime,
                                 folder_id: str = "inbox", limit: int = 50) -> Dict[str, Any]:
        """
        Get messages within a specific date range.
        
        Args:
            start_date: Start date for filtering
            end_date: End date for filtering
            folder_id: ID of the folder to search in
            limit: Maximum number of results
            
        Returns:
            Messages dictionary
        """
        # Format dates for OData filter
        start_str = start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        end_str = end_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        
        filter_query = f"receivedDateTime ge {start_str} and receivedDateTime le {end_str}"
        
        return self.get_messages(
            folder_id=folder_id,
            limit=limit,
            filter_query=filter_query
        )
    
    def get_all_messages(self, folder_id: str = "inbox", 
                        limit: Optional[int] = None,
                        filter_query: Optional[str] = None) -> Generator[Dict[str, Any], None, None]:
        """
        Generator to get all messages from a folder with pagination.
        
        Args:
            folder_id: ID of the mail folder
            limit: Maximum total number of messages (None for all)
            filter_query: OData filter query
            
        Yields:
            Individual message dictionaries
        """
        skip_token = None
        total_retrieved = 0
        
        while True:
            batch_size = min(999, limit - total_retrieved if limit else 999)
            
            if limit and total_retrieved >= limit:
                break
            
            result = self.get_messages(
                folder_id=folder_id,
                limit=batch_size,
                skip_token=skip_token,
                filter_query=filter_query
            )
            
            messages = result.get("value", [])
            if not messages:
                break
            
            for message in messages:
                yield message
                total_retrieved += 1
                
                if limit and total_retrieved >= limit:
                    break
            
            # Check for next page
            next_link = result.get("@odata.nextLink")
            if not next_link:
                break
            
            # Extract skip token from next link
            skip_token = None
            if "skiptoken=" in next_link:
                skip_token = next_link.split("skiptoken=")[1].split("&")[0]
    
    def get_user_profile(self) -> Dict[str, Any]:
        """
        Get user profile information.
        
        Returns:
            User profile dictionary
        """
        url = f"{self.BASE_URL}/me"
        response = self._make_request("GET", url)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get user profile: {response.status_code} - {response.text}")
