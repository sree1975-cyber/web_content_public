# -*- coding: utf-8 -*-
"""
WEB CONTENT MANAGER - Restored Public Access, Fixed Save Messages/Balloons, XLS-Only Downloads, Clickable URLs
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

# Custom CSS
st.markdown("""
<style>
    .header {
        background: linear-gradient(135deg, #6e8efb, #a777e3);
        color: white;
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .card {
        background: white;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    }
    .dataframe {
        width: 100%;
    }
    .tag {
        display: inline-block;
        background: #e0e7ff;
        color: #4f46e5;
        padding: 0.2rem 0.5rem;
        border-radius: 1rem;
        font-size: 0.8rem;
        margin-right: 0.5rem;
        margin-bottom: 0.3rem;
    }
    .delete-btn {
        background-color: #ff4b4b !important;
        color: white !important;
        margin-top: 0.5rem;
    }
    .mode-indicator {
        background: #e0e7ff;
        color: #4f46e5;
        padding: 0.5rem;
        border-radius: 5px;
        margin-bottom: 1rem;
        font-weight: bold;
        text-align: center;
    }
    .exit-btn {
        background-color: #ff4b4b !important;
        color: white !important;
        width: 100%;
        margin-top: 1rem;
    }
    .login-btn {
        background-color: #6e8efb !important;
        color: white !important;
        width: 100%;
        margin-top: 1rem;
    }
    .login-container {
        background: white;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        max-width: 500px;
        margin: 2rem auto;
    }
    .login-title {
        text-align: center;
        color: #4f46e5;
        margin-bottom: 1rem;
    }
    .login-info {
        text-align: center;
        color: #666;
        margin-bottom: 1.5rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
    }
    .login-btn:hover {
        background-color: #5a7de3 !important;
    }
    .public-btn {
        background-color: #10b981 !important;
        color: white !important;
    }
    .public-btn:hover {
        background-color: #0e9f6e !important;
    }
</style>
""", unsafe_allow_html=True)

def init_data(mode, username=None):
    """Initialize or load Excel file based on mode"""
    if mode == "owner":
        excel_file = 'web_links.xlsx'
    elif mode == "guest":
        if not username:
            raise ValueError("Username required for guest mode")
        excel_file = f'guest_{username}.xlsx'
    else:
        return pd.DataFrame(), None  # Public mode uses session state
    
    try:
        if os.path.exists(excel_file):
            df = pd.read_excel(excel_file, engine='openpyxl')
            if 'tags' in df.columns:
                df['tags'] = df['tags'].apply(lambda x: x.split(',') if isinstance(x, str) else [] if pd.isna(x) else x)
            for col in ['title', 'url', 'description']:
                if col in df.columns:
                    df[col] = df[col].astype(str).replace('nan', '')
            logging.info(f"Loaded {excel_file}")
        else:
            df = pd.DataFrame(columns=[
                'id', 'url', 'title', 'description', 'tags', 
                'created_at', 'updated_at'
            ])
            logging.info(f"Created new {excel_file}")
        return df, excel_file
    except Exception as e:
        st.error(f"Failed to initialize {excel_file}: {str(e)}")
        logging.error(f"Data initialization failed: {str(e)}")
        return pd.DataFrame(), excel_file

def save_data(df, excel_file):
    """Save DataFrame to Excel file"""
    try:
        logging.debug(f"Saving DataFrame to {excel_file}: {df.to_dict()}")
        df_to_save = df.copy()
        if 'tags' in df_to_save.columns:
            df_to_save['tags'] = df_to_save['tags'].apply(lambda x: ','.join(map(str, x)) if isinstance(x, list) else '')
        
        if os.path.exists(excel_file):
            if not os.access(excel_file, os.W_OK):
                raise PermissionError(f"No write permission for {excel_file}")
        else:
            directory = os.path.dirname(excel_file) or '.'
            if not os.access(directory, os.W_OK):
                raise PermissionError(f"No write permission for directory {directory}")
        
        df_to_save.to_excel(excel_file, index=False, engine='openpyxl')
        logging.info("Data saved successfully")
        return True
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")
        logging.error(f"Data save failed: {str(e)}")
        return False

def save_link(df, url, title, description, tags):
    """Save or update a link in the DataFrame"""
    try:
        logging.debug(f"Saving link: URL={url}, Title={title}, Description={description}, Tags={tags}")
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        existing_index = df[df['url'] == url].index
        
        if not existing_index.empty:
            idx = existing_index[0]
            df.at[idx, 'title'] = title
            df.at[idx, 'description'] = description if description else ""
            df.at[idx, 'tags'] = [str(tag).strip() for tag in tags if str(tag).strip()]
            df.at[idx, 'updated_at'] = now
            action = "updated"
        else:
            new_id = df['id'].max() + 1 if not df.empty else 1
            new_entry = {
                'id': new_id,
                'url': url,
                'title': title,
                'description': description if description else "",
                'tags': [str(tag).strip() for tag in tags if str(tag).strip()],
                'created_at': now,
                'updated_at': now
            }
            df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
            action = "saved"
        
        logging.info(f"Link {action} successfully")
        return df, action
    except Exception as e:
        st.error(f"Error saving link: {str(e)}")
        logging.error(f"Link save failed: {str(e)}")
        return df, None

def delete_selected_links(df, excel_file, selected_urls, mode):
    """Delete selected links from the DataFrame"""
    try:
        logging.debug(f"Deleting URLs: {selected_urls}")
        if not selected_urls:
            st.warning("No links selected for deletion")
            return df
        df = df[~df['url'].isin(selected_urls)]
        if mode in ["owner", "guest"]:
            if save_data(df, excel_file):
                st.session_state['df'] = df
                st.success(f"✅ {len(selected_urls)} link(s) deleted successfully!")
                st.balloons()
                time.sleep(0.5)
            else:
                st.error("Failed to save changes after deletion")
        else:
            st.session_state['user_df'] = df
            st.success(f"✅ {len(selected_urls)} link(s) deleted successfully!")
            st.balloons()
            time.sleep(0.5)
        return df
    except Exception as e:
        st.error(f"Error deleting links: {str(e)}")
        logging.error(f"Delete links failed: {str(e)}")
        return df

def display_header(mode, username=None):
    """Display beautiful header with mode indicator"""
    mode_text = "Public Mode"
    if mode == "owner":
        mode_text = "Logged in as Owner"
    elif mode == "guest":
        mode_text = f"Logged in as Guest: {username}"
    
    st.markdown(f"""
    <div class="mode-indicator">
        {mode_text}
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="header">
        <h1 style="color: white; margin-bottom: 0;">🔖 Web Content Manager</h1>
        <p style="color: white; opacity: 0.9; font-size: 1.1rem;">
        Save, organize, and rediscover your web treasures
        </p>
    </div>
    """, unsafe_allow_html=True)

def fetch_metadata(url):
    """Get page metadata with error handling"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        title = soup.title.string if soup.title else url
        description = soup.find('meta', attrs={'name': 'description'})
        description = description['content'] if description else ""
        
        keywords = soup.find('meta', attrs={'name': 'keywords'})
        keywords = keywords['content'].split(',')[:5] if keywords else []
        
        return title, description, [k.strip() for k in keywords if k.strip()]
    except Exception as e:
        st.warning(f"Couldn't fetch metadata: {str(e)}")
        return url, "", []

def add_link_section(df, excel_file, mode):
    """Section for adding new links with working Fetch button"""
    st.markdown("### 🌐 Add New Web Content")
    
    # Initialize user DataFrame for public mode
    if mode == "public" and 'user_df' not in st.session_state:
        st.session_state['user_df'] = pd.DataFrame(columns=[
            'id', 'url', 'title', 'description', 'tags', 
            'created_at', 'updated_at'
        ])
    
    # Determine the DataFrame to use
    working_df = st.session_state['user_df'] if mode == "public" else df
    
    # Dynamic key for url_input to force reset
    if 'url_input_counter' not in st.session_state:
        st.session_state['url_input_counter'] = 0
    url_input_key = f"url_input_{st.session_state['url_input_counter']}"
    
    # Clear URL field if signaled
    url_value = '' if st.session_state.get('clear_url', False) else st.session_state.get(url_input_key, '')
    
    # Fetch Metadata button
    url_temp = st.text_input(
        "URL*", 
        value=url_value,
        placeholder="https://example.com",
        key=url_input_key,
        help="Enter the full URL including https://"
    )
    
    is_url_valid = url_temp.startswith(("http://", "https://")) if url_temp else False
    
    if st.button("Fetch Metadata", disabled=not is_url_valid, key="fetch_metadata"):
        with st.spinner("Fetching..."):
            title, description, keywords = fetch_metadata(url_temp)
            st.session_state['auto_title'] = title
            st.session_state['auto_description'] = description
            st.session_state['suggested_tags'] = keywords
            st.session_state['clear_url'] = False
    
    # Form for saving link
    with st.form("add_link_form", clear_on_submit=True):
        url = st.text_input(
            "URL (Confirm)*", 
            value=st.session_state.get(url_input_key, ''),
            key="url_form_input",
            help="Confirm the URL to save"
        )
        
        title = st.text_input(
            "Title*", 
            value=st.session_state.get('auto_title', ''),
            help="Give your link a descriptive title",
            key="title_input"
        )
        
        description = st.text_area(
            "Description", 
            value=st.session_state.get('auto_description', ''),
            height=100,
            help="Add notes about why this link is important",
            key="description_input"
        )
        
        # Get all unique tags from DataFrame
        all_tags = sorted({str(tag).strip() for sublist in working_df['tags'] 
                         for tag in (sublist if isinstance(sublist, list) else []) 
                         if str(tag).strip()})
        suggested_tags = st.session_state.get('suggested_tags', []) + \
                       ['research', 'tutorial', 'news', 'tool', 'inspiration']
        all_tags = sorted(list(set(all_tags + [str(tag).strip() for tag in suggested_tags if str(tag).strip()])))
        
        selected_tags = st.multiselect(
            "Tags",
            options=all_tags,
            default=[],
            help="Select existing tags or add new ones below.",
            key="existing_tags_input"
        )
        
        new_tag = st.text_input(
            "Add New Tag (optional)",
            placeholder="Type a new tag and press Enter",
            help="Enter a new tag to add to the selected tags",
            key="new_tag_input"
        )
        
        tags = selected_tags + ([new_tag.strip()] if new_tag.strip() else [])
        
        submitted = st.form_submit_button("💾 Save Link")
        
        if submitted:
            logging.debug(f"Form submitted: URL={url}, Title={title}, Description={description}, Tags={tags}, Mode={mode}")
            if not url:
                st.error("Please enter a URL")
            elif not title:
                st.error("Please enter a title")
            else:
                working_df, action = save_link(working_df, url, title, description, tags)
                if action:
                    logging.debug(f"Displaying success message and balloons for action: {action}")
                    if mode in ["owner", "guest"]:
                        if save_data(working_df, excel_file):
                            st.session_state['df'] = working_df
                            st.success(f"✅ Link {action} successfully!")
                            st.balloons()
                            time.sleep(0.5)
                            st.session_state['clear_url'] = True
                            st.session_state['url_input_counter'] += 1
                            for key in ['auto_title', 'auto_description', 'suggested_tags']:
                                st.session_state.pop(key, None)
                            st.rerun()
                        else:
                            st.error("Failed to save link to Excel file")
                    else:
                        st.session_state['user_df'] = working_df
                        st.success(f"✅ Link {action} successfully! Download your links as they are temporary.")
                        st.balloons()
                        time.sleep(0.5)
                        st.session_state['clear_url'] = True
                        st.session_state['url_input_counter'] += 1
                        for key in ['auto_title', 'auto_description', 'suggested_tags']:
                            st.session_state.pop(key, None)
                        st.rerun()
                else:
                    st.error("Failed to process link")
    
    return working_df

def browse_section(df, excel_file, mode):
    """Section for browsing saved links"""
    st.markdown("### 📚 Browse Saved Links")
    
    # Use user_df for public mode
    working_df = st.session_state['user_df'] if mode == "public" else df
    
    if working_df.empty:
        st.info("✨ No links saved yet. Add your first link to get started!")
        return
    
    with st.form("search_form"):
        search_col, tag_col = st.columns([3, 1])
        with search_col:
            search_query = st.text_input(
                "Search content",
                placeholder="Search by title, URL, description, or tags",
                key="search_query",
                help="Enter words to filter links"
            )
        with tag_col:
            all_tags = sorted({str(tag).strip() for sublist in working_df['tags'] 
                             for tag in (sublist if isinstance(sublist, list) else []) 
                             if str(tag).strip()})
            selected_tags = st.multiselect(
                "Filter by tags",
                options=all_tags,
                key="tag_filter",
                help="Select tags to filter links"
            )
        
        submitted = st.form_submit_button("🔍 Search")
    
    filtered_df = working_df.copy()
    
    if search_query or submitted:
        logging.debug(f"Applying search query: {search_query}")
        search_lower = search_query.lower()
        try:
            mask = (
                filtered_df['title'].str.lower().str.contains(search_lower, na=False) |
                filtered_df['url'].str.lower().str.contains(search_lower, na=False) |
                filtered_df['description'].str.lower().str.contains(search_lower, na=False) |
                filtered_df['tags'].apply(
                    lambda x: any(search_lower in str(tag).lower() for tag in (x if isinstance(x, list) else []))
                )
            )
            filtered_df = filtered_df[mask]
            logging.debug(f"Search results: {len(filtered_df)} links found")
        except Exception as e:
            st.error(f"Search error: {str(e)}")
            logging.error(f"Search failed: {str(e)}")
    
    if selected_tags:
        logging.debug(f"Applying tag filter: {selected_tags}")
        try:
            mask = filtered_df['tags'].apply(
                lambda x: any(str(tag) in map(str, (x if isinstance(x, list) else [])) 
                              for tag in selected_tags)
            )
            filtered_df = filtered_df[mask]
            logging.debug(f"Tag filter results: {len(filtered_df)} links found")
        except Exception as e:
            st.error(f"Tag filter error: {str(e)}")
            logging.error(f"Tag filter failed: {str(e)}")
    
    if filtered_df.empty:
        st.warning("No links match your search criteria")
    else:
        st.markdown(f"<small>Found <strong>{len(filtered_df)}</strong> link(s)</small>", unsafe_allow_html=True)
    
    if 'selected_urls' not in st.session_state:
        st.session_state.selected_urls = []

    with st.expander("📊 View All Links as Data Table", expanded=True):
        display_df = filtered_df.copy()
        display_df['tags'] = display_df['tags'].apply(
            lambda x: ', '.join(str(tag) for tag in (x if isinstance(x, list) else [])))
        
        display_df['Select'] = [False] * len(display_df)
        for i, row in display_df.iterrows():
            display_df.at[i, 'Select'] = row['url'] in st.session_state.selected_urls
        
        edited_df = st.data_editor(
            display_df[['Select', 'title', 'url', 'description', 'tags', 'created_at']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Select": st.column_config.CheckboxColumn("Select", help="Select links to delete"),
                "title": st.column_config.TextColumn("Title", width="medium"),
                "url": st.column_config.LinkColumn(
                    "URL",
                    width="medium",
                    help="Click to visit the webpage",
                    display_text=lambda x: x[:50] + "..." if len(x) > 50 else x
                ),
                "description": st.column_config.TextColumn("Description", width="large"),
                "tags": st.column_config.TextColumn("Tags"),
                "created_at": st.column_config.DatetimeColumn("Date Added", format="YYYY-MM-DD HH:mm:ss")
            },
            disabled=['title', 'url', 'description', 'tags', 'created_at'],
            key="data_editor"
        )
        
        st.session_state.selected_urls = edited_df[edited_df['Select']]['url'].tolist()
        
        if st.session_state.selected_urls:
            if st.button("🗑️ Delete Selected Links", key="delete_selected"):
                working_df = delete_selected_links(working_df, excel_file, st.session_state.selected_urls, mode)
                if mode == "public":
                    st.session_state['user_df'] = working_df
                else:
                    st.session_state['df'] = working_df
                st.session_state.selected_urls = []
                st.rerun()

def format_tags(tags):
    """Format tags as pretty pills"""
    from html import escape
    if not tags or (isinstance(tags, float) and pd.isna(tags)):
        return ""
    
    if isinstance(tags, str):
        tags = tags.split(',')
    
    html_tags = []
    for tag in tags:
        if tag and str(tag).strip():
            html_tags.append(f"""
            <span class="tag">
                {escape(str(tag).strip())}
            </span>
            """)
    return "".join(html_tags)

def download_section(df, excel_file, mode):
    """Section for downloading data (XLS only)"""
    st.markdown("### 📥 Export Your Links")
    
    # Use user_df for public mode
    working_df = st.session_state['user_df'] if mode == "public" else df
    
    if working_df.empty:
        st.warning("No links available to export")
        return
    
    with st.container():
        st.markdown("""
        <div class="card">
            <h3>Export Options</h3>
            <p>Download your saved links in Excel format</p>
        </div>
        """, unsafe_allow_html=True)
        
        if mode in ["owner", "guest"] and excel_file:
            with open(excel_file, 'rb') as f:
                st.download_button(
                    label=f"Download {mode.capitalize()} Links (Excel)",
                    data=f,
                    file_name=f"{mode}_links.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help=f"Download all {mode} links in Excel format"
                )
        elif mode == "public" and not working_df.empty:
            output = BytesIO()
            working_df.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            st.download_button(
                label="Download Public Links (Excel)",
                data=output,
                file_name="public_links.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Download all public links in Excel format"
            )
        
        st.markdown(f"""
        <div style="margin-top: 1rem;">
            <p><strong>Stats:</strong> {len(working_df)} links saved | {len(set(tag for sublist in working_df['tags'] for tag in (sublist if isinstance(sublist, list) else [])))} unique tags</p>
        </div>
        """, unsafe_allow_html=True)

def login_form():
    """Display login form with public access option"""
    # Dynamic keys for password and username inputs
    if 'password_input_counter' not in st.session_state:
        st.session_state['password_input_counter'] = 0
    if 'username_input_counter' not in st.session_state:
        st.session_state['username_input_counter'] = 0
    
    password_input_key = f"password_input_{st.session_state['password_input_counter']}"
    username_input_key = f"username_input_{st.session_state['username_input_counter']}"
    
    st.markdown("""
    <div class="login-container">
        <h2 class="login-title">🔖 Web Content Manager</h2>
        <p class="login-info">Log in as Owner or Guest, or continue as Public to save links temporarily.</p>
    </div>
    """, unsafe_allow_html=True)
    
    try:
        with st.form(key="login_form", clear_on_submit=True):
            password = st.text_input(
                "Enter Password",
                type="password",
                help="Enter the password for owner or guest mode",
                key=password_input_key,
                value='',
                autocomplete="off"
            )
            
            username = st.text_input(
                "Enter Username (Guest Mode)",
                placeholder="Your username",
                help="Required for guest mode to access your personal file",
                key=username_input_key,
                value='',
                autocomplete="off"
            )
            
            submitted = st.form_submit_button("🔑 Login")
            
            if submitted:
                logging.debug(f"Login attempt: Password={password}, Username={username}")
                if password == ADMIN_PASSWORD:
                    st.session_state['mode'] = "owner"
                    st.session_state['username'] = None
                    st.session_state['password_input_counter'] += 1
                    st.session_state['username_input_counter'] = 1
                    st.success("✅ Logged in as Owner!")
                    st.rerun()
                elif password == GUEST_PASSWORD:
                    if username:
                        st.session_state['mode'] = "guest"
                        st.session_state['username'] = username
                        st.session_state['password_input_counter'] += 1
                        st.session_state['username_input_counter'] += 1
                        st.success(f"✅ Logged in as Guest: {username}!")
                        st.rerun()
                    else:
                        st.error("Please enter a username for guest mode")
                else:
                    st.error("Invalid password")
                    st.session_state['mode'] = "public"
                    st.session_state['password_input_counter'] += 1
                    st.session_state['username_input_counter'] += 1
                    st.rerun()
    except Exception as e:
        st.error(f"Form error: {str(e)}. Using fallback login.")
        logging.error(f"Form error: {str(e)}")
        # Fallback non-form login
        password = st.text_input(
            "Enter Password (Fallback)",
            type="password",
            key=f"fallback_password_{st.session_state['password_input_counter']}",
            value='',
            autocomplete="off"
        )
        username = st.text_input(
            "Enter Username (Guest Mode, Fallback)",
            placeholder="Your username",
            key=f"fallback_username_{st.session_state['username_input_counter']}",
            value='',
            autocomplete="off"
        )
        if st.button("🔑 Login (Fallback)", key=f"fallback_login_{st.session_state['password_input_counter']}"):
            logging.debug(f"Fallback login attempt: Password={password}, Username={username}")
            if password == ADMIN_PASSWORD:
                st.session_state['mode'] = "owner"
                st.session_state['username'] = None
                st.session_state['password_input_counter'] += 1
                st.session_state['username_input_counter'] += 1
                st.success("✅ Logged in as Owner!")
                st.rerun()
            elif password == GUEST_PASSWORD and username:
                st.session_state['mode'] = "guest"
                st.session_state['username'] = username
                st.session_state['password_input_counter'] += 1
                st.session_state['username_input_counter'] += 1
                st.success(f"✅ Logged in as Guest: {username}!")
                st.rerun()
            elif password == GUEST_PASSWORD:
                st.error("Please enter a username for guest mode")
            else:
                st.session_state['mode'] = "public"
                st.session_state['password_input_counter'] += 1
                st.session_state['username_input_counter'] += 1
                st.rerun()
    
    if st.button("🌐 Continue as Public", key="public_access_button", help="Access without logging in (temporary storage)"):
        st.session_state['mode'] = "public"
        st.session_state['password_input_counter'] += 1
        st.session_state['username_input_counter'] += 1
        st.rerun()

def main():
    # Check if logged in
    if 'mode' not in st.session_state:
        login_form()
        return
    
    mode = st.session_state['mode']
    username = st.session_state.get('username')
    
    # Sidebar with Exit button and navigation
    with st.sidebar:
        st.markdown(f"""
        <p style='color: {"green" if mode == "owner" else "blue" if mode == "guest" else "gray"}; font-weight: bold;'>
            {mode.capitalize()} Mode{f" ({username})" if username else ""}
        </p>
        """, unsafe_allow_html=True)
        
        if st.button("🚪 Exit and Clear Cache", key="exit_button", help="Clear all session data and reset the app"):
            logging.debug(f"Exit button clicked. Session state before clear: {st.session_state}")
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.session_state['password_input_counter'] = 0
            st.session_state['username_input_counter'] = 0
            st.success("✅ Session cleared! App will reset.")
            st.balloons()
            time.sleep(0.5)
            st.rerun()
        
        st.markdown("""
        <div style="padding: 1rem;">
            <h2 style="margin-bottom: 1.5rem;">Navigation</h2>
        </div>
        """, unsafe_allow_html=True)
        
        selected = option_menu(
            menu_title=None,
            options=["Add Link", "Browse Links", "Export Data"],
            icons=['plus-circle', 'book', 'download'],
            default_index=0,
            styles={
                "container": {"padding": "0!important"},
                "icon": {"color": "#6e8efb", "font-size": "1rem"}, 
                "nav-link": {"font-size": "1rem", "text-align": "left", "margin": "0.5rem 0", "padding": "0.5rem 1rem"},
                "nav-link-selected": {"background-color": "#6e8efb", "font-weight": "normal"},
            }
        )
    
    # Initialize data based on mode
    if mode in ["owner", "guest"]:
        if 'df' not in st.session_state or st.session_state.get('username') != username:
            df, excel_file = init_data(mode, username)
            st.session_state['df'] = df
            st.session_state['excel_file'] = excel_file
            st.session_state['username'] = username
        else:
            df = st.session_state['df']
            excel_file = st.session_state['excel_file']
    else:
        df, excel_file = pd.DataFrame(), None
        if 'user_df' not in st.session_state:
            st.session_state['user_df'] = pd.DataFrame(columns=[
                'id', 'url', 'title', 'description', 'tags', 
                'created_at', 'updated_at'
            ])
    
    # Display header with mode indicator
    display_header(mode, username)
    
    # About section
    with st.expander("ℹ️ About Web Content Manager", expanded=False):
        st.markdown("""
        <div style="padding: 1rem;">
            <h3>Your Personal Web Library</h3>
            <p>Web Content Manager helps you save and organize web links with:</p>
            <ul>
                <li>📌 One-click saving of important web resources</li>
                <li>🏷️ <strong>Smart tagging</strong> - Automatically suggests tags</li>
                <li>🔍 <strong>Powerful search</strong> - Full-text search with tag filtering</li>
                <li>🗑️ <strong>Delete functionality</strong> - Remove unwanted links</li>
                <li>📊 <strong>Data Table View</strong> - View links in a table</li>
                <li>📥 <strong>Export capability</strong> - Download as Excel</li>
                <li>💾 <strong>Storage</strong> - Owner/guest data persists; public data is temporary</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    # Render selected section
    if selected == "Add Link":
        updated_df = add_link_section(df, excel_file, mode)
        if mode == "public":
            st.session_state['user_df'] = updated_df
        else:
            st.session_state['df'] = updated_df
    elif selected == "Browse Links":
        browse_section(df, excel_file, mode)
    elif selected == "Export Data":
        download_section(df, excel_file, mode)

if __name__ == "__main__":
    main()
