# -*- coding: utf-8 -*-
"""
WEB CONTENT MANAGER - Plain Access Control, Fixed SyntaxError, XLS Downloads, Clickable URLs
"""
import streamlit as st
import pandas as pd
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from streamlit_option_menu import option_menu
import logging
import os
import time
from io import BytesIO

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Verify Streamlit version
if st.__version__ != "1.31.0":
    st.error(f"Streamlit version {st.__version__} detected. This app requires 1.31.0. Check Cloud logs or contact support.")

# Set page configuration
st.set_page_config(
    page_title="Web Content Manager",
    page_icon="🔖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Hardcoded passwords
ADMIN_PASSWORD = "admin123"
GUEST_PASSWORD = "guest456"

# File paths
DATA_DIR = "data"
OWNER_FILE = os.path.join(DATA_DIR, "owner_links.xlsx")
GUEST_FILE = os.path.join(DATA_DIR, "guest_links.xlsx")

# Initialize session state
if 'mode' not in st.session_state:
    st.session_state['mode'] = None
if 'password_input_counter' not in st.session_state:
    st.session_state['password_input_counter'] = 0
if 'url_input_counter' not in st.session_state:
    st.session_state['url_input_counter'] = 0
if 'clear_url' not in st.session_state:
    st.session_state['clear_url'] = False

# CSS for buttons
st.markdown("""
<style>
    .login-btn, .exit-btn {
        background-color: #4CAF50;
        color: white;
        padding: 10px 20px;
        border: none;
        border-radius: 5px;
        cursor: pointer;
        font-size: 16px;
    }
    .login-btn:hover, .exit-btn:hover {
        background-color: #45a049;
    }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

def save_data(df, excel_file, mode):
    """Save DataFrame to Excel file with permission checks."""
    directory = os.path.dirname(excel_file)
    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
        except Exception as e:
            st.error(f"Failed to create directory {directory}: {e}")
            return False
    if not os.access(directory, os.W_OK):
        st.error(f"No write permission for directory {directory}")
        return False
    try:
        logging.debug(f"Attempting to save DataFrame to {excel_file}: {df.to_dict()}")
        df.to_excel(excel_file, index=False, engine='openpyxl')
        logging.info(f"Successfully saved DataFrame to {excel_file}")
        return True
    except Exception as e:
        st.error(f"Failed to save data: {e}")
        logging.error(f"Save error: {e}")
        return False

def load_data(excel_file):
    """Load DataFrame from Excel file."""
    try:
        if os.path.exists(excel_file):
            df = pd.read_excel(excel_file, engine='openpyxl')
            logging.debug(f"Loaded DataFrame from {excel_file}: {df.to_dict()}")
            return df
        else:
            logging.info(f"File {excel_file} does not exist, returning empty DataFrame")
            return pd.DataFrame(columns=['url', 'title', 'description', 'date_added'])
    except Exception as e:
        st.error(f"Failed to load data: {e}")
        logging.error(f"Load error: {e}")
        return pd.DataFrame(columns=['url', 'title', 'description', 'date_added'])

def fetch_metadata(url):
    """Fetch title and description from URL."""
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.title.string if soup.title else "No title"
        description = soup.find('meta', attrs={'name': 'description'})
        description = description['content'] if description else "No description"
        return title.strip(), description.strip()
    except Exception as e:
        logging.error(f"Metadata fetch error for {url}: {e}")
        return "Error fetching title", "Error fetching description"

def login_page():
    """Render plain access control page."""
    st.title("🔖 Web Content Manager")
    st.markdown("Enter password to access owner or guest mode, or continue as public.")
    st.info("Public mode allows temporary link storage. Log in for persistent storage.")

    with st.form(key="login_form"):
        password = st.text_input(
            "Password",
            type="password",
            key=f"password_input_{st.session_state['password_input_counter']}",
            value="",
            autocomplete="off"
        )
        submitted = st.form_submit_button("🔑 Login")
        if submitted:
            if password == ADMIN_PASSWORD:
                st.session_state['mode'] = "owner"
                st.session_state['password_input_counter'] += 1
                st.rerun()
            elif password == GUEST_PASSWORD:
                st.session_state['mode'] = "guest"
                st.session_state['password_input_counter'] += 1
                st.rerun()
            else:
                st.error("Invalid password")
                st.session_state['mode'] = "public"
                st.session_state['password_input_counter'] += 1
                st.rerun()

    if st.button("🌐 Continue as Public", key="public_access_button"):
        st.session_state['mode'] = "public"
        st.session_state['password_input_counter'] += 1
        st.rerun()

    # Fallback login
    st.markdown("---")
    st.markdown("**Fallback Login** (use if form fails)")
    fallback_password = st.text_input(
        "Fallback Password",
        type="password",
        key=f"fallback_password_{st.session_state['password_input_counter']}",
        value="",
        autocomplete="off"
    )
    if st.button("🔑 Login (Fallback)", key=f"fallback_login_{st.session_state['password_input_counter']}"):
        if fallback_password == ADMIN_PASSWORD:
            st.session_state['mode'] = "owner"
        elif fallback_password == GUEST_PASSWORD:
            st.session_state['mode'] = "guest"
        else:
            st.session_state['mode'] = "public"
        st.session_state['password_input_counter'] += 1
        st.rerun()
    if st.button("🌐 Continue as Public (Fallback)", key=f"fallback_public_{st.session_state['password_input_counter']}"):
        st.session_state['mode'] = "public"
        st.session_state['password_input_counter'] += 1
        st.rerun()

def add_link_section(df, excel_file, mode):
    """Add or update a URL with metadata."""
    st.header("Add New Link")
    url_key = f"url_input_{st.session_state['url_input_counter']}"
    url = st.text_input("Enter URL", key=url_key, value="" if st.session_state['clear_url'] else st.session_state.get(url_key, ""))
    
    if st.button("➕ Add/Update Link", key=f"add_button_{st.session_state['url_input_counter']}"):
        if url:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            title, description = fetch_metadata(url)
            date_added = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_row = pd.DataFrame({
                'url': [url],
                'title': [title],
                'description': [description],
                'date_added': [date_added]
            })
            if url in df['url'].values:
                df = df[df['url'] != url]
                st.success("✅ URL exists and updated!")
            else:
                st.success("✅ Link saved successfully!")
            df = pd.concat([df, new_row], ignore_index=True)
            if mode != "public":
                if save_data(df, excel_file, mode):
                    st.balloons()
            else:
                st.session_state['user_df'] = df
                st.balloons()
            st.session_state['clear_url'] = True
            st.session_state['url_input_counter'] += 1
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("Please enter a URL")
    
    if st.session_state['clear_url']:
        st.session_state['clear_url'] = False

def browse_section(df, excel_file, mode):
    """Browse and manage links."""
    st.header("Browse Links")
    if df.empty:
        st.info("No links available.")
        return
    
    # Configure columns for clickable URLs
    st.dataframe(
        df,
        column_config={
            "url": st.column_config.LinkColumn(
                "URL",
                width="medium",
                help="Click to visit the webpage",
                display_text=lambda x: x[:50] + "..." if len(x) > 50 else x
            ),
            "title": st.column_config.TextColumn("Title", width="medium"),
            "description": st.column_config.TextColumn("Description", width="large"),
            "date_added": st.column_config.DatetimeColumn("Date Added", format="YYYY-MM-DD HH:mm:ss")
        },
        use_container_width=True,
        hide_index=True
    )

    # Search functionality
    st.subheader("Search Links")
    search_term = st.text_input("Search by URL, title, or description", key="search_input")
    if search_term:
        filtered_df = df[
            df['url'].str.contains(search_term, case=False, na=False) |
            df['title'].str.contains(search_term, case=False, na=False) |
            df['description'].str.contains(search_term, case=False, na=False)
        ]
        if filtered_df.empty:
            st.info("No results found.")
        else:
            st.dataframe(
                filtered_df,
                column_config={
                    "url": st.column_config.LinkColumn(
                        "URL",
                        width="medium",
                        help="Click to visit the webpage",
                        display_text=lambda x: x[:50] + "..." if len(x) > 50 else x
                    ),
                    "title": st.column_config.TextColumn("Title", width="medium"),
                    "description": st.column_config.TextColumn("Description", width="large"),
                    "date_added": st.column_config.DatetimeColumn("Date Added", format="YYYY-MM-DD HH:mm:ss")
                },
                use_container_width=True,
                hide_index=True
            )

    # Delete functionality (owner mode only)
    if mode == "owner":
        st.subheader("Delete Link")
        url_to_delete = st.selectbox("Select URL to delete", options=df['url'].tolist(), key="delete_select")
        if st.button("🗑️ Delete Link", key="delete_button"):
            df = df[df['url'] != url_to_delete]
            if save_data(df, excel_file, mode):
                st.success("✅ Link deleted successfully!")
                st.balloons()
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Failed to delete link.")

def download_section(df, excel_file, mode):
    """Download links as Excel."""
    st.header("Download Links")
    working_df = df.copy()
    
    if mode != "public":
        if os.path.exists(excel_file):
            with open(excel_file, 'rb') as f:
                st.download_button(
                    label=f"Download {mode.capitalize()} Links (Excel)",
                    data=f,
                    file_name=f"{mode}_links.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_excel_{mode}"
                )
        else:
            st.info(f"No {mode} links file available for download.")
    else:
        if not working_df.empty:
            output = BytesIO()
            working_df.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            st.download_button(
                label="Download Public Links (Excel)",
                data=output,
                file_name="public_links.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_excel_public"
            )
        else:
            st.info("No public links available for download.")

def main():
    """Main application logic."""
    if st.session_state['mode'] is None:
        login_page()
        return

    mode = st.session_state['mode']
    excel_file = OWNER_FILE if mode == "owner" else GUEST_FILE if mode == "guest" else None
    df = load_data(excel_file) if mode != "public" else st.session_state.get('user_df', pd.DataFrame(columns=['url', 'title', 'description', 'date_added']))

    # Sidebar navigation
    with st.sidebar:
        st.header(f"Welcome, {mode.capitalize()}!")
        if st.button("🚪 Exit and Clear Cache", key="exit_button"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.session_state['mode'] = None
            st.session_state['password_input_counter'] = 0
            st.session_state['url_input_counter'] = 0
            st.session_state['clear_url'] = False
            st.balloons()
            time.sleep(0.5)
            st.rerun()
        
        selected = option_menu(
            "Menu",
            ["Add Link", "Browse Links", "Download Links"],
            icons=["plus-circle", "list", "download"],
            menu_icon="cast",
            default_index=0
        )

    # Main content
    if selected == "Add Link":
        add_link_section(df, excel_file, mode)
    elif selected == "Browse Links":
        browse_section(df, excel_file, mode)
    elif selected == "Download Links":
        download_section(df, excel_file, mode)

if __name__ == "__main__":
    main()
