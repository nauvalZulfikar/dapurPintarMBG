# frontend/components/auth.py
import streamlit as st
import time
import hashlib
import os

SESSION_SECRET = os.getenv("SESSION_SECRET", "mbg_kitchen_secret_2024")
USERNAME = "admin"
PASSWORD = "admin"

def generate_session_token(username: str) -> str:
    """Generate a simple session token"""
    timestamp = str(int(time.time()))
    data = f"{username}:{timestamp}:{SESSION_SECRET}"
    token = hashlib.sha256(data.encode()).hexdigest()
    return f"{username}:{timestamp}:{token}"

def validate_session_token(token: str) -> bool:
    """Validate session token (valid for 7 days)"""
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return False
        
        username, timestamp, token_hash = parts
        
        # Check if token is expired (7 days)
        if int(time.time()) - int(timestamp) > 7 * 24 * 60 * 60:
            return False
        
        # Validate hash
        expected = hashlib.sha256(f"{username}:{timestamp}:{SESSION_SECRET}".encode()).hexdigest()
        return token_hash == expected
    except:
        return False

def check_session_from_url():
    """Check URL parameters for session token (persistent login)"""
    # Initialize session state
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "session_token" not in st.session_state:
        st.session_state.session_token = None
    
    query_params = st.query_params
    if "session" in query_params:
        token = query_params["session"]
        if validate_session_token(token):
            st.session_state.logged_in = True
            st.session_state.session_token = token

def login():
    """This function handles the login form and authentication."""
    st.title("🔐 MBG Kitchen Login")

    # Get username and password from the user
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login", type="primary"):
        if username == USERNAME and password == PASSWORD:
            # Generate session token
            token = generate_session_token(username)
            st.session_state.logged_in = True
            st.session_state.session_token = token
            
            # Add token to URL for persistence across browser refreshes
            st.query_params["session"] = token
            
            st.success("✅ Logged in successfully!")
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("❌ Invalid username or password")

def render_logout_button():
    """Render logout button in sidebar"""
    if st.sidebar.button("🚪 Logout", type="secondary"):
        st.session_state.logged_in = False
        st.session_state.session_token = None
        st.query_params.clear()
        st.rerun()