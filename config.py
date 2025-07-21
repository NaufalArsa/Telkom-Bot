import os
import json
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_env_var(name, required=True):
    value = os.environ.get(name)
    if required and not value:
        raise ValueError(f"{name} environment variable not set!")
    return value

# Environment variables
API_ID = int(get_env_var('API_ID'))  # type: ignore
API_HASH = get_env_var('API_HASH')
BOT_TOKEN = get_env_var('BOT_TOKEN')
SHEET_NAME = get_env_var('GOOGLE_SHEET_NAME')
SUPABASE_URL = get_env_var('SUPABASE_URL', required=False)
SUPABASE_KEY = get_env_var('SUPABASE_KEY', required=False)

# Type assertions to satisfy the linter
assert API_ID is not None
assert API_HASH is not None
assert BOT_TOKEN is not None
assert SHEET_NAME is not None

# Column indices for spreadsheet
COLUMNS = {
    'no': 0,
    'timestamp': 1,
    'user_id': 2,
    'nama_sa': 3,
    'sto': 4,
    'cluster': 5,
    'usaha': 6,
    'pic': 7,
    'hpwa': 8,
    'internet': 9,
    'biaya': 10,
    'voc': 11,
    'location': 12,
    'file_link': 13,
    'link_gmaps': 14,
    'validitas': 15
}

# Required fields for validation
REQUIRED_FIELDS = {
    'nama_sa': 'Nama SA/AR',
    'sto': 'STO', 
    'cluster': 'Cluster',
    'usaha': 'Nama usaha',
    'pic': 'Nama PIC',
    'hpwa': 'Nomor HP/WA',
    'internet': 'Internet existing',
    'biaya': 'Biaya internet existing',
    'voc': 'Voice of Customer'
}

# Configure logging
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

# Load Google credentials
def load_google_credentials():
    try:
        creds_json = get_env_var('GOOGLE_CREDS_JSON')
        assert creds_json is not None
        creds_dict = json.loads(creds_json)
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        return creds_dict, scope
    except Exception as e:
        print(f"Error loading Google credentials: {e}")
        # Fallback to file-based credentials
        try:
            CREDENTIALS_FILE = 'gcredentials.json'
            with open(CREDENTIALS_FILE, 'r') as f:
                creds_dict = json.load(f)
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            print("✅ Using file-based credentials as fallback")
            return creds_dict, scope
        except Exception as e2:
            print(f"Error loading fallback credentials: {e2}")
            raise 