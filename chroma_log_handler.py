import logging
import chromadb
import json
import time
import os
import streamlit as st
from datetime import datetime

# Get user ID for logging isolation
def _get_current_user_id():
    """Get current user ID from Streamlit session"""
    try:
        if 'user_id' in st.session_state:
            return st.session_state.user_id[:8]  # First 8 chars for brevity
        return 'anonymous'
    except:
        return 'system'

@st.cache_resource
def _get_cached_chroma_client():
    """Cache ChromaDB client as singleton across all sessions"""
    try:
        if (os.getenv('CHROMA_LOGS_API_KEY') and 
            os.getenv('CHROMA_LOGS_TENANT') and 
            os.getenv('CHROMA_LOGS_DATABASE')):
            
            client = chromadb.CloudClient(
                api_key=os.getenv('CHROMA_LOGS_API_KEY'),
                tenant=os.getenv('CHROMA_LOGS_TENANT'), 
                database=os.getenv('CHROMA_LOGS_DATABASE')
            )
            
            return client
        else:
            return None
    except Exception as e:
        print(f"ChromaDB client initialization failed: {e}")
        return None

def _get_user_collection(client, user_id: str):
    """Get or create user-specific collection"""
    try:
        collection_name = f"logs_user_{user_id}"
        return client.get_or_create_collection(
            name=collection_name,
            metadata={
                "description": f"Application logs for user {user_id}", 
                "user_id": user_id,
                "created": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        print(f"Failed to create collection for user {user_id}: {e}")
        return None

class ChromaLogHandler(logging.Handler):
    """Multi-user isolated ChromaDB logging handler with READABLE format"""
    
    def __init__(self, api_key: str, tenant: str, database: str):
        super().__init__()
        
        # Use cached singleton client
        self.client = _get_cached_chroma_client()
        
        if not self.client:
            print("⚠️ ChromaDB logging handler disabled - client initialization failed")
    
    def emit(self, record):
        """Multi-user isolated log emission with READABLE format"""
        if not self.client:
            return
            
        try:
            # Skip asyncio and aiohttp errors specifically
            if (record.name in ['asyncio', 'aiohttp'] and 
                'unclosed' in record.getMessage().lower()):
                return
                
            # Only send INFO+ level logs
            if record.levelno < logging.INFO:
                return
            
            # Get current user for isolation
            user_id = _get_current_user_id()
            
            # Get user-specific collection
            collection = _get_user_collection(self.client, user_id)
            if not collection:
                return
            
            # READABLE log structure (like terminal format)
            terminal_format = f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] {record.name:<20} {record.levelname:<8} | {record.funcName}:{record.lineno} | {record.getMessage()}"
            
            # Enhanced log structure with MORE DETAILS
            log_entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "user_id": user_id,
                "level": record.levelname,
                "logger": record.name,
                "function": getattr(record, 'funcName', 'unknown'),
                "line": getattr(record, 'lineno', 0),
                "module": getattr(record, 'module', 'unknown'),
                "message": record.getMessage()[:1000],  # Longer messages
                "terminal_format": terminal_format,  # Exact terminal format
                "thread": record.thread,
                "process": record.process
            }
            
            # Add exception info if present
            if record.exc_info:
                log_entry["error"] = {
                    "type": record.exc_info[0].__name__ if record.exc_info[0] else "Unknown",
                    "message": str(record.exc_info[1]) if record.exc_info[1] else "No message",
                    "traceback": record.getMessage()[:500]
                }
            
            # Extract more context from specific loggers
            if record.name == 'core.brain_agent':
                # Extract Brain Agent specific info
                msg = record.getMessage()
                if 'user_id:' in msg:
                    try:
                        user_part = msg.split('user_id:')[1].split('[')[0].strip()
                        log_entry["extracted_user_id"] = user_part
                    except:
                        pass
                
                if 'EXECUTING PLAN' in msg:
                    log_entry["action"] = "executing_plan"
                elif 'Tools to execute:' in msg:
                    log_entry["action"] = "tools_selection"
                elif 'EXECUTION RESULTS:' in msg:
                    log_entry["action"] = "execution_results"
                elif 'Synthesizing final response' in msg:
                    log_entry["action"] = "synthesizing"
                elif 'COMPLETED successfully' in msg:
                    log_entry["action"] = "completed"
            
            # User-specific unique ID
            doc_id = f"log_{user_id}_{int(time.time() * 1000)}_{record.thread % 1000}"
            
            # Store with enhanced metadata
            collection.add(
                documents=[log_entry["terminal_format"]],  # Use terminal format as document
                metadatas=[{
                    "level": record.levelname,
                    "user_id": user_id,
                    "logger": record.name,
                    "function": log_entry["function"],
                    "action": log_entry.get("action", "general"),
                    "timestamp": log_entry["timestamp"][:19],
                    "full_log": json.dumps(log_entry, ensure_ascii=False, separators=(',', ':'))
                }],
                ids=[doc_id]
            )
            
        except Exception:
            # Never let logging errors crash the app
            pass
