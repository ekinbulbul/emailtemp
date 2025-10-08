"""
OAuth2 Authentication Handler for Microsoft Graph API

This module handles OAuth2 authentication flow for accessing Microsoft Graph API
to collect emails from Exchange/Outlook.
"""

import os
import json
import webbrowser
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs
import http.server
import socketserver
import threading
from datetime import datetime, timedelta

import msal
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class OAuthHandler:
    """Handles OAuth2 authentication with Microsoft Graph API."""
    
    # Microsoft Graph API endpoints
    AUTHORITY = "https://login.microsoftonline.com/{tenant_id}"
    SCOPES = ["https://graph.microsoft.com/Mail.Read", "https://graph.microsoft.com/Mail.ReadWrite"]
    REDIRECT_URI = "http://localhost:8080/callback"
    
    def __init__(self, tenant_id: Optional[str] = None, client_id: Optional[str] = None, 
                 client_secret: Optional[str] = None, token_cache_file: Optional[str] = None):
        """
        Initialize OAuth handler.
        
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
        
        self.authority = self.AUTHORITY.format(tenant_id=self.tenant_id)
        
        # Initialize MSAL app with token cache persistence
        self.app = msal.PublicClientApplication(
            self.client_id,
            authority=self.authority,
            token_cache=msal.SerializableTokenCache()
        )
        
        # Load existing token cache
        self._load_token_cache()
    
    def _load_token_cache(self):
        """Load token cache from file if it exists."""
        if os.path.exists(self.token_cache_file):
            try:
                with open(self.token_cache_file, 'r') as f:
                    cache_data = f.read()
                    self.app.token_cache.deserialize(cache_data)
            except Exception as e:
                print(f"Warning: Could not load token cache: {e}")
    
    def _save_token_cache(self):
        """Save token cache to file."""
        try:
            cache_data = self.app.token_cache.serialize()
            with open(self.token_cache_file, 'w') as f:
                f.write(cache_data)
        except Exception as e:
            print(f"Warning: Could not save token cache: {e}")
    
    def get_access_token(self) -> Optional[str]:
        """
        Get access token for Microsoft Graph API.
        
        Returns:
            Access token string if successful, None otherwise
        """
        # Try to get token from cache first
        accounts = self.app.get_accounts()
        if accounts:
            result = self.app.acquire_token_silent(self.SCOPES, account=accounts[0])
            if result and "access_token" in result:
                return result["access_token"]
        
        # If no cached token, start device code flow
        return self._device_code_flow()
    
    def _device_code_flow(self) -> Optional[str]:
        """
        Perform device code flow for authentication.
        
        Returns:
            Access token string if successful, None otherwise
        """
        try:
            flow = self.app.initiate_device_flow(scopes=self.SCOPES)
            if "user_code" not in flow:
                raise ValueError("Failed to create device flow")
            
            print(f"\nTo sign in, use a web browser to open the page {flow['verification_uri']}")
            print(f"and enter the code {flow['user_code']} to authenticate.")
            
            # Wait for user to complete authentication
            result = self.app.acquire_token_by_device_flow(flow)
            
            if "access_token" in result:
                self._save_token_cache()
                return result["access_token"]
            else:
                print(f"Authentication failed: {result.get('error_description', 'Unknown error')}")
                return None
                
        except Exception as e:
            print(f"Device code flow failed: {e}")
            return None
    
    def refresh_token(self) -> Optional[str]:
        """
        Refresh the access token.
        
        Returns:
            New access token string if successful, None otherwise
        """
        accounts = self.app.get_accounts()
        if accounts:
            result = self.app.acquire_token_silent(self.SCOPES, account=accounts[0])
            if result and "access_token" in result:
                self._save_token_cache()
                return result["access_token"]
        
        return None
    
    def is_token_valid(self) -> bool:
        """
        Check if the current token is valid.
        
        Returns:
            True if token is valid, False otherwise
        """
        token = self.get_access_token()
        return token is not None
    
    def revoke_token(self):
        """Revoke the current token and clear cache."""
        try:
            # Clear local cache
            if os.path.exists(self.token_cache_file):
                os.remove(self.token_cache_file)
            
            # Clear MSAL cache
            self.app.token_cache.clear()
            
            print("Token revoked and cache cleared.")
        except Exception as e:
            print(f"Error revoking token: {e}")
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the authenticated user.
        
        Returns:
            User information dictionary if successful, None otherwise
        """
        token = self.get_access_token()
        if not token:
            return None
        
        try:
            import requests
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to get user info: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Error getting user info: {e}")
            return None
