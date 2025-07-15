import streamlit as st
import pandas as pd
import json
import os
import subprocess
import threading
import time
import sys
from datetime import datetime
from timezone_utils import get_current_time, format_timestamp
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Initialize Supabase client
def get_supabase_client():
    """Get Supabase client if credentials are available"""
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if supabase_url and supabase_key:
        try:
            return create_client(supabase_url, supabase_key)
        except Exception as e:
            st.error(f"Failed to initialize Supabase client: {e}")
            return None
    return None

def list_supabase_files():
    """List all files in Supabase storage bucket"""
    supabase = get_supabase_client()
    if not supabase:
        return [], "Supabase credentials not configured"
    
    try:
        bucket_name = "photo"
        files = supabase.storage.from_(bucket_name).list()
        return files, None
    except Exception as e:
        return [], f"Error listing files: {str(e)}"

def delete_supabase_file(filename):
    """Delete a file from Supabase storage"""
    supabase = get_supabase_client()
    if not supabase:
        return False, "Supabase credentials not configured"
    
    try:
        bucket_name = "photo"
        result = supabase.storage.from_(bucket_name).remove([filename])
        return True, None
    except Exception as e:
        return False, f"Error deleting file: {str(e)}"

def get_supabase_file_url(filename):
    """Get public URL for a file in Supabase storage"""
    supabase = get_supabase_client()
    if not supabase:
        return None
    
    try:
        bucket_name = "photo"
        return supabase.storage.from_(bucket_name).get_public_url(filename)
    except Exception as e:
        st.error(f"Error getting file URL: {e}")
        return None

# Page configuration
st.set_page_config(
    page_title="YOVI Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #ffffff;
        color: #000000;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #e0e0e0;
        margin: 0.5rem 0;
    }
    .success {
        color: #28a745;
    }
    .warning {
        color: #ffc107;
    }
    .danger {
        color: #dc3545;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'bot_running' not in st.session_state:
    st.session_state.bot_running = False
if 'bot_process' not in st.session_state:
    st.session_state.bot_process = None
if 'bot_output' not in st.session_state:
    st.session_state.bot_output = []

def get_google_sheets_data():
    """Get data from Google Sheets"""
    try:
        # Try environment variable first
        creds_json = os.getenv('GOOGLE_CREDS_JSON')
        if creds_json:
            creds_dict = json.loads(creds_json)
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)  # type: ignore
            gc = gspread.authorize(creds)  # type: ignore
        else:
            # Fallback to file-based credentials
            gc = gspread.service_account(filename='gcredentials.json')
        
        # Open sheet
        sheet_name = os.getenv('GOOGLE_SHEET_NAME', 'Recap Visit YOVI')
        sheet = gc.open(sheet_name).sheet1
        data = sheet.get_all_records()
        
        if not data:
            return pd.DataFrame(), "No data found"
        
        df = pd.DataFrame(data)
        return df, None
        
    except Exception as e:
        return None, f"Error loading data: {str(e)}"

def start_bot():
    """Start the bot in a separate thread with better error handling"""
    try:
        # Only use bot.py
        bot_file = 'bot.py'
        if not os.path.exists(bot_file):
            st.error("bot.py file not found!")
            return False
        
        # Use the same Python executable as Streamlit
        python_executable = sys.executable
        
        # Set environment variables for proper encoding
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUNBUFFERED'] = '1'
        
        # Start the bot process with improved error handling
        process = subprocess.Popen(
            [python_executable, bot_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Redirect stderr to stdout
            text=True,
            bufsize=1,
            universal_newlines=True,
            env=env,
            encoding='utf-8',
            errors='replace'  # Replace unicode errors instead of failing
        )
        
        st.session_state.bot_process = process
        st.session_state.bot_running = True
        st.session_state.bot_output = []  # Reset output
        
        # Start a thread to monitor the process and capture output
        def monitor_process():
            try:
                while True:
                    if process.poll() is not None:  # Process ended
                        st.session_state.bot_running = False
                        st.error("Bot process terminated unexpectedly!")
                        break
                    
                    # Read output line by line
                    if process.stdout:
                        line = process.stdout.readline()
                        if line:
                            # Clean the line and add to output
                            clean_line = line.strip()
                            if clean_line:
                                st.session_state.bot_output.append(clean_line)
                                # Keep only last 50 lines
                                if len(st.session_state.bot_output) > 50:
                                    st.session_state.bot_output = st.session_state.bot_output[-50:]
                        else:
                            time.sleep(0.1)
                    else:
                        time.sleep(0.1)
                        
            except Exception as e:
                st.error(f"Error monitoring bot process: {str(e)}")
                st.session_state.bot_running = False
        
        threading.Thread(target=monitor_process, daemon=True).start()
        
        return True
        
    except Exception as e:
        st.error(f"Error starting bot: {str(e)}")
        return False

def stop_bot():
    """Stop the bot"""
    try:
        if st.session_state.bot_process:
            st.session_state.bot_process.terminate()
            # Wait a bit for graceful shutdown
            try:
                st.session_state.bot_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                st.session_state.bot_process.kill()  # Force kill if needed
            st.session_state.bot_process = None
        st.session_state.bot_running = False
        return True
    except Exception as e:
        st.error(f"Error stopping bot: {str(e)}")
        return False

def check_bot_status():
    """Check if bot is running"""
    if st.session_state.bot_process:
        return st.session_state.bot_process.poll() is None
    return False

# Main dashboard
def main():
    st.markdown('<h1 class="main-header">🤖 YOVI Dashboard</h1>', unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.title("🎛️ Bot Controls")
    
    # Environment variables status
    st.sidebar.subheader("🔧 Environment Status")
    env_vars = {
        'API_ID': os.getenv('API_ID'),
        'API_HASH': os.getenv('API_HASH'),
        'BOT_TOKEN': os.getenv('BOT_TOKEN'),
        'GOOGLE_SHEET_NAME': os.getenv('GOOGLE_SHEET_NAME'),
        'GOOGLE_CREDS_JSON': os.getenv('GOOGLE_CREDS_JSON'),
        'SUPABASE_URL': os.getenv('SUPABASE_URL'),
        'SUPABASE_KEY': os.getenv('SUPABASE_KEY')
    }
    
    for var_name, var_value in env_vars.items():
        if var_value:
            st.sidebar.success(f"✅ {var_name}")
        else:
            st.sidebar.error(f"❌ {var_name}")
    
    # Bot control buttons
    st.sidebar.subheader("🚀 Bot Controls")
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if st.button("▶️ Start Bot", type="primary"):
            if start_bot():
                st.success("Bot started successfully!")
                st.rerun()
    
    with col2:
        if st.button("⏹️ Stop Bot"):
            if stop_bot():
                st.success("Bot stopped successfully!")
                st.rerun()
    
    # Check bot status once and use it consistently
    bot_is_running = check_bot_status()
    
    # Bot status
    st.sidebar.subheader("📊 Bot Status")
    if bot_is_running:
        st.sidebar.success("🟢 Bot is running")
    else:
        st.sidebar.error("🔴 Bot is stopped")
    
    # Main content area
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "☁️ Storage", "⚙️ Settings"])
    
    with tab1:
        # Dashboard header with inline refresh button
        col1, col2 = st.columns([4, 1])
        with col1:
            st.header("📊 Dashboard Overview")
        with col2:
            if st.button("🔄 Refresh", type="secondary"):
                st.rerun()
        
        # Status cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            status_text = "🟢 Running" if bot_is_running else "🔴 Stopped"
            status_class = "success" if bot_is_running else "danger"
            st.markdown(f"""
            <div class="metric-card">
                <h3>Bot Status</h3>
                <p class="{status_class}">{status_text}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            # Get data count
            df, error = get_google_sheets_data()
            if df is not None and not df.empty:
                data_count = len(df)
            else:
                data_count = 0
            
            st.markdown(f"""
            <div class="metric-card">
                <h3>Total Records</h3>
                <p>{data_count}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class="metric-card">
                <h3>Last Update</h3>
                <p>{}</p>
            </div>
            """.format(format_timestamp()), unsafe_allow_html=True)
        
        with col4:
            # Count today's records
            today_count = 0
            if df is not None and not df.empty and 'Timestamp' in df.columns:
                try:
                    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
                    today = get_current_time().date()
                    today_count = len(df[df['Timestamp'].dt.date == today])
                except:
                    today_count = 0
            
            st.markdown(f"""
            <div class="metric-card">
                <h3>Today's Records</h3>
                <p>{today_count}</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Recent activity
        st.subheader("🕒 Recent Activity")
        if bot_is_running:
            st.info("Bot is actively monitoring for new messages...")
        else:
            st.warning("Bot is not running. Start the bot to begin monitoring.")
        
        # Live bot output
        st.subheader("📝 Live Bot Output")
        if st.session_state.bot_output:
            # Create a container for the output
            output_container = st.container()
            with output_container:
                for line in st.session_state.bot_output[-20:]:  # Show last 20 lines
                    st.text(line)
        else:
            st.info("No bot output yet. Start the bot to see live logs.")
        
        # Log viewer (from file)
        st.subheader("📄 Log File")
        if os.path.exists('bot.log'):
            with open('bot.log', 'r', encoding='utf-8', errors='replace') as f:
                logs = f.readlines()[-10:]  # Last 10 lines
                for log in logs:
                    st.text(log.strip())
        else:
            st.warning("No log file found")
    
    with tab2:
        st.header("☁️ Supabase Storage Management")
        
        # Check if Supabase is configured
        supabase_client = get_supabase_client()
        if not supabase_client:
            st.error("❌ Supabase not configured")
            st.info("Please set SUPABASE_URL and SUPABASE_KEY in your .env file")
        else:
            st.success("✅ Supabase connected")
            
            # Storage controls
            col1, col2 = st.columns([1, 1])
            
            with col1:
                if st.button("🔄 Refresh File List", type="primary"):
                    st.rerun()
            
            with col2:
                if st.button("🗑️ Clear All Files", type="secondary"):
                    # Add confirmation dialog
                    if st.session_state.get('confirm_delete_all', False):
                        files, error = list_supabase_files()
                        if not error and files:
                            deleted_count = 0
                            for file in files:
                                # Handle both string and dict responses
                                filename = file['name'] if isinstance(file, dict) else str(file)
                                success, error_msg = delete_supabase_file(filename)
                                if success:
                                    deleted_count += 1
                            
                            if deleted_count > 0:
                                st.success(f"✅ Deleted {deleted_count} files")
                                st.rerun()
                            else:
                                st.error("❌ Failed to delete files")
                        st.session_state.confirm_delete_all = False
                    else:
                        st.session_state.confirm_delete_all = True
                        st.warning("⚠️ Click again to confirm deletion of all files")
            
            # File list
            st.subheader("📁 Stored Files")
            
            files, error = list_supabase_files()
            
            if error:
                st.error(f"❌ {error}")
            elif not files:
                st.info("📭 No files found in storage")
            else:
                st.success(f"📊 Found {len(files)} files")
                
                # Create a DataFrame for better display
                file_data = []
                for file in files:
                    # Handle both string and dict responses from Supabase
                    if isinstance(file, dict):
                        file_data.append({
                            'Filename': file.get('name', 'Unknown'),  # type: ignore
                            'Size (bytes)': file.get('metadata', {}).get('size', 'Unknown'),  # type: ignore
                            'Created': file.get('created_at', 'Unknown'),  # type: ignore
                            'Updated': file.get('updated_at', 'Unknown')  # type: ignore
                        })
                    else:
                        # If file is just a string (filename)
                        file_data.append({
                            'Filename': str(file),
                            'Size (bytes)': 'Unknown',
                            'Created': 'Unknown',
                            'Updated': 'Unknown'
                        })
                
                df_files = pd.DataFrame(file_data)
                st.dataframe(df_files, use_container_width=True)
                
                # File management
                st.subheader("🗂️ File Management")
                
                # File selection for individual operations
                if files:
                    # Extract filenames safely
                    filenames = []
                    for file in files:
                        if isinstance(file, dict):
                            filenames.append(file.get('name', 'Unknown'))
                        else:
                            filenames.append(str(file))
                    
                    selected_file = st.selectbox(
                        "Select a file to manage:",
                        filenames
                    )
                    
                    if selected_file:
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            if st.button("👁️ View File"):
                                file_url = get_supabase_file_url(selected_file)
                                if file_url:
                                    st.image(file_url, caption=selected_file, use_container_width=True)
                                else:
                                    st.error("❌ Could not get file URL")
                        
                        with col2:
                            if st.button("🔗 Copy URL"):
                                file_url = get_supabase_file_url(selected_file)
                                if file_url:
                                    st.code(file_url)
                                    st.success("✅ URL copied to clipboard")
                                else:
                                    st.error("❌ Could not get file URL")
                        
                        with col3:
                            if st.button("🗑️ Delete File", type="secondary"):
                                success, error_msg = delete_supabase_file(selected_file)
                                if success:
                                    st.success(f"✅ Deleted {selected_file}")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {error_msg}")
    
    with tab3:
        st.header("⚙️ Settings")
        
        st.subheader("🔧 Configuration")
        
        # Environment variables editor
        st.subheader("Environment Variables")
        st.info("Edit your .env file to modify these settings")
        
        # Display current settings (masked)
        settings = {
            "API_ID": os.getenv('API_ID', 'Not set'),
            "API_HASH": os.getenv('API_HASH', 'Not set')[:10] + "..." if os.getenv('API_HASH') else 'Not set',
            "BOT_TOKEN": os.getenv('BOT_TOKEN', 'Not set')[:10] + "..." if os.getenv('BOT_TOKEN') else 'Not set',
            "GOOGLE_SHEET_NAME": os.getenv('GOOGLE_SHEET_NAME', 'Not set'),
            "GOOGLE_CREDS_JSON": os.getenv('GOOGLE_CREDS_JSON', 'Not set'),
            "SUPABASE_URL": os.getenv('SUPABASE_URL', 'Not set'),
            "SUPABASE_KEY": os.getenv('SUPABASE_KEY', 'Not set')[:10] + "..." if os.getenv('SUPABASE_KEY') else 'Not set'
        }
        
        for key, value in settings.items():
            st.text_input(key, value, disabled=True)
        
        # System information
        st.subheader("💻 System Information")
        try:
            python_version = subprocess.check_output(['python', '--version']).decode().strip()
            st.text(f"Python Version: {python_version}")
        except:
            st.text("Python Version: Unable to determine")
        st.text(f"Streamlit Version: {st.__version__}")
        st.text(f"Working Directory: {os.getcwd()}")

    # Check if bot process has terminated
    if st.session_state.bot_process:
        if st.session_state.bot_process.poll() is not None:
            st.session_state.bot_running = False
            st.error("Bot process has terminated!")

if __name__ == "__main__":
    main() 