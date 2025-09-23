"""
Session Token Manager for Brain-Heart Deep Research System  
Multi-account support with 1-hour session tokens and enhanced security
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import base64
import hashlib
import uuid
import requests
import time

# Simple encryption (for production, use cryptography)
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

logger = logging.getLogger(__name__)

class SessionTokenManager:
    """Manages 1-hour session tokens that wrap Google OAuth tokens"""
    
    def __init__(self, user_id: str, account_id: str = "default"):
        self.user_id = user_id
        self.account_id = account_id
        os.makedirs("sessions", exist_ok=True)
        os.makedirs(f"sessions/{user_id}", exist_ok=True)
        
        self.session_file = f"sessions/{user_id}/session_{account_id}.json"
        self.key_file = f"sessions/{user_id}/key_{account_id}.key"
        
        logger.info(f"📝 SessionTokenManager initialized for user: {user_id}, account: {account_id}")
    
    
    def _encrypt_data(self, data: str) -> bytes:
        """Encrypt session data with TTL"""
        if not CRYPTO_AVAILABLE:
            return base64.b64encode(data.encode())
        
        key = Fernet.generate_key()
        fernet = Fernet(key)
        encrypted_data = fernet.encrypt_at_time(data.encode(), current_time=int(time.time()))
        
        return key + encrypted_data

    
    def _decrypt_data(self, encrypted_data: bytes) -> Optional[str]:
        """Decrypt session data with TTL check"""
        try:
            if not CRYPTO_AVAILABLE:
                return base64.b64decode(encrypted_data).decode()
            
            key = encrypted_data[:44]
            data = encrypted_data[44:]
            
            fernet = Fernet(key)
            decrypted = fernet.decrypt_at_time(data, ttl=3600, current_time=int(time.time()))
            return decrypted.decode()
            
        except Exception as e:
            logger.error(f"❌ Session expired or decrypt failed for user {self.user_id}, account {self.account_id}: {e}")
            return None

    
    def create_session(self, google_creds, account_email: str = "", account_alias: str = "") -> str:
        """Create 1-hour session token from Google credentials"""
        try:
            session_data = {
                "user_id": self.user_id,
                "account_id": self.account_id,
                "account_email": account_email,
                "account_alias": account_alias,
                "google_tokens": google_creds.to_json(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                "session_id": hashlib.sha256(f"{self.user_id}_{self.account_id}_{datetime.now()}".encode()).hexdigest()[:16]
            }
            
            encrypted_data = self._encrypt_data(json.dumps(session_data))
            
            with open(self.session_file, 'wb') as f:
                f.write(encrypted_data)
            
            logger.info(f"✅ Created 1-hour session for user: {self.user_id}, account: {self.account_id}")
            return session_data["session_id"]
            
        except Exception as e:
            logger.error(f"❌ Failed to create session for user {self.user_id}, account {self.account_id}: {e}")
            return None
    
    def validate_session(self) -> Optional[Dict[str, Any]]:
        """Check if session is valid and not expired"""
        try:
            if not os.path.exists(self.session_file):
                logger.info(f"📭 No session file found for user: {self.user_id}, account: {self.account_id}")
                return None
            
            with open(self.session_file, 'rb') as f:
                encrypted_data = f.read()

            
            decrypted_data = self._decrypt_data(encrypted_data)
            if not decrypted_data:
                return None
            
            session_data = json.loads(decrypted_data)
            
            expires_at = datetime.fromisoformat(session_data['expires_at'])
            now = datetime.now(timezone.utc)
            
            if now > expires_at:
                logger.warning(f"⏰ Session expired for user {self.user_id}, account {self.account_id}")
                self.revoke_google_tokens()
                self.delete_session()
                return None
            
            logger.info(f"✅ Valid session found for user: {self.user_id}, account: {self.account_id}")
            return session_data
            
        except Exception as e:
            logger.error(f"❌ Session validation failed for user {self.user_id}, account {self.account_id}: {e}")
            self.revoke_google_tokens()
            return None
    
    def get_google_credentials(self):
        """Get Google credentials from valid session"""
        session_data = self.validate_session()
        if not session_data:
            return None
        
        try:
            from google.oauth2.credentials import Credentials
            google_creds_data = json.loads(session_data['google_tokens'])
            creds = Credentials.from_authorized_user_info(google_creds_data)
            
            logger.info(f"🔑 Retrieved Google credentials for user: {self.user_id}, account: {self.account_id}")
            return creds
            
        except Exception as e:
            logger.error(f"❌ Failed to get Google credentials for user {self.user_id}, account {self.account_id}: {e}")
            return None
    
    def delete_session(self):
        """Delete user session and cleanup"""
        try:
            if os.path.exists(self.session_file):
                os.remove(self.session_file)
                logger.info(f"🗑️ Deleted session file for user: {self.user_id}, account: {self.account_id}")
                
        except Exception as e:
            logger.error(f"❌ Failed to delete session for user {self.user_id}, account {self.account_id}: {e}")

            
    def revoke_google_tokens(self) -> bool:
        """Immediately revoke Google tokens - FIXED VERSION"""
        try:
            # DON'T call validate_session - causes infinite loop!
            
            # Read session file directly
            if not os.path.exists(self.session_file):
                logger.info(f"No session to revoke for user {self.user_id}, account {self.account_id}")
                return True
            
            with open(self.session_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self._decrypt_data(encrypted_data)
            if not decrypted_data:
                return False
            
            session_data = json.loads(decrypted_data)
            
            # Get the Google tokens
            google_creds_data = json.loads(session_data['google_tokens'])
            
            # Revoke refresh token (this also revokes access token)
            if 'refresh_token' in google_creds_data:
                refresh_token = google_creds_data['refresh_token']
                revoke_url = f"https://oauth2.googleapis.com/revoke?token={refresh_token}"
                
                response = requests.post(revoke_url, headers={'Content-Type': 'application/x-www-form-urlencoded'})
                
                if response.status_code == 200:
                    logger.info(f"✅ Successfully revoked Google tokens for user {self.user_id}, account {self.account_id}")
                else:
                    logger.warning(f"⚠️ Token revocation returned status {response.status_code}")
            
            # Also revoke access token as backup
            if 'token' in google_creds_data:
                access_token = google_creds_data['token']
                revoke_url = f"https://oauth2.googleapis.com/revoke?token={access_token}"
                
                requests.post(revoke_url, headers={'Content-Type': 'application/x-www-form-urlencoded'})
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to revoke tokens for user {self.user_id}, account {self.account_id}: {e}")
            return False



class MultiAccountManager:
    """Manages multiple Google Drive accounts per user"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.accounts_file = f"sessions/{user_id}/accounts_index.json"
        os.makedirs(f"sessions/{user_id}", exist_ok=True)
    
    def get_user_accounts(self) -> List[Dict[str, Any]]:
        """Get all accounts for this user"""
        if not os.path.exists(self.accounts_file):
            return []
        
        try:
            with open(self.accounts_file, 'r') as f:
                accounts_data = json.load(f)
            
            # Check which accounts have valid sessions
            active_accounts = []
            for account in accounts_data:
                session_mgr = SessionTokenManager(self.user_id, account['account_id'])
                session_data = session_mgr.validate_session()
                
                account['is_active'] = session_data is not None
                if session_data:
                    account['expires_at'] = session_data['expires_at']
                    account['account_email'] = session_data.get('account_email', '')
                
                active_accounts.append(account)
            
            return active_accounts
            
        except Exception as e:
            logger.error(f"❌ Error getting user accounts for {self.user_id}: {e}")
            return []
    
    def add_account(self, account_id: str, account_email: str, account_alias: str):
        """Add account to user's account index"""
        try:
            accounts = self.get_user_accounts()
            
            # Check if account already exists
            for account in accounts:
                if account['account_id'] == account_id:
                    return  # Already exists
            
            # Add new account
            accounts.append({
                'account_id': account_id,
                'account_email': account_email,
                'account_alias': account_alias,
                'added_at': datetime.now(timezone.utc).isoformat()
            })
            
            with open(self.accounts_file, 'w') as f:
                json.dump(accounts, f, indent=2)
            
            logger.info(f"📝 Added account {account_email} for user {self.user_id}")
            
        except Exception as e:
            logger.error(f"❌ Error adding account for user {self.user_id}: {e}")
    
    def remove_account(self, account_id: str):
        """Remove account and cleanup its sessions"""
        try:
            # Delete session
            session_mgr = SessionTokenManager(self.user_id, account_id)
            session_mgr.delete_session()
            
            # Remove from index
            accounts = self.get_user_accounts()
            accounts = [acc for acc in accounts if acc['account_id'] != account_id]
            
            with open(self.accounts_file, 'w') as f:
                json.dump(accounts, f, indent=2)
            
            logger.info(f"🗑️ Removed account {account_id} for user {self.user_id}")
            
        except Exception as e:
            logger.error(f"❌ Error removing account for user {self.user_id}: {e}")
            
    def revoke_all_accounts(self):
        """Revoke ALL Google tokens for this user"""
        try:
            accounts = self.get_user_accounts()
            revoked_count = 0
            
            for account in accounts:
                session_mgr = SessionTokenManager(self.user_id, account['account_id'])
                if session_mgr.revoke_google_tokens():
                    revoked_count += 1
            
            logger.info(f"✅ Revoked {revoked_count} accounts for user {self.user_id}")
            return revoked_count
            
        except Exception as e:
            logger.error(f"❌ Failed to revoke all accounts for user {self.user_id}: {e}")
            return 0
