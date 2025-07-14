import os
import re
import json
import gspread
import requests
import subprocess
import logging
from datetime import datetime
from typing import Dict, Tuple, Optional, List
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from telethon import TelegramClient, events
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
from supabase import create_client, Client
from timezone_utils import get_current_time, format_timestamp

# Load environment variables
load_dotenv()

def get_env_var(name, required=True):
    value = os.environ.get(name)
    if required and not value:
        raise ValueError(f"{name} environment variable not set!")
    return value

# Environment variables (use the same names as in bot.py)
API_ID = int(get_env_var('API_ID'))  # type: ignore
API_HASH = get_env_var('API_HASH')
BOT_TOKEN = get_env_var('BOT_TOKEN')
DRIVE_ID = get_env_var('GOOGLE_DRIVE_FOLDER_ID')
SHEET_NAME = get_env_var('GOOGLE_SHEET_NAME')
NODE_SCRIPT_PATH = get_env_var('NODE_SCRIPT_PATH')
SUPABASE_URL = get_env_var('SUPABASE_URL', required=False)  # Supabase URL
SUPABASE_KEY = get_env_var('SUPABASE_KEY', required=False)  # Supabase anon key

# Type assertions to satisfy the linter
assert API_ID is not None
assert API_HASH is not None
assert BOT_TOKEN is not None
assert DRIVE_ID is not None
assert SHEET_NAME is not None
assert NODE_SCRIPT_PATH is not None

# Load Google credentials from environment variable
try:
    creds_json = get_env_var('GOOGLE_CREDS_JSON')
    assert creds_json is not None
    creds_dict = json.loads(creds_json)
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)  # type: ignore
    gc = gspread.authorize(creds)  # type: ignore
    sheet = gc.open(SHEET_NAME).sheet1
except Exception as e:
    print(f"Error loading Google credentials or opening sheet: {e}")
    # Fallback to file-based credentials like bot_optimized.py
    try:
        CREDENTIALS_FILE = 'gcredentials.json'
        with open(CREDENTIALS_FILE, 'r') as f:
            creds_dict = json.load(f)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        gc = gspread.service_account(filename=CREDENTIALS_FILE)
        sheet = gc.open(SHEET_NAME).sheet1
        print("✅ Using file-based credentials as fallback")
    except Exception as e2:
        print(f"Error loading fallback credentials: {e2}")
        exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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

# Regex pattern for caption parsing
CAPTION_PATTERN = re.compile(r"""
    Nama\s+SA/\s*AR:\s*(?P<nama_sa>.+?)\n+
    STO:\s*(?P<sto>.+?)\n+
    Cluster:\s*(?P<cluster>.+?)\n+
    \n*
    Nama\s+usaha:\s*(?P<usaha>.+?)\n+
    Nama\s+PIC:\s*(?P<pic>.+?)\n+
    Nomor\s+HP/\s*WA:\s*(?P<hpwa>.+?)\n+
    Internet\s+existing:\s*(?P<internet>.+?)\n+
    Biaya\s+internet\s+existing:\s*(?P<biaya>.+?)\n+
    Voice\s+of\s+Customer:\s*(?P<voc>.+?)(?:\n|$)
""", re.DOTALL | re.MULTILINE | re.IGNORECASE | re.VERBOSE)

# Initialize client and services
client = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Data storage
pending_data: Dict[str, Dict] = {}
user_started: Dict[str, bool] = {}

# Cache for Google Drive service
_drive_service = None

def get_drive_service():
    """Get or create Google Drive service with caching"""
    global _drive_service
    if _drive_service is None:
        try:
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            _drive_service = build('drive', 'v3', credentials=creds)
            logger.info("Google Drive service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}")
            return None
    return _drive_service

def get_gmaps_link_from_coords(lat: float, lon: float) -> str:
    """Generate Google Maps link from coordinates"""
    return f"https://www.google.com/maps?q={lat},{lon}"

def extract_lat_lng_from_short_url(short_url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    try:
        response = requests.get(short_url, headers=headers, allow_redirects=True, timeout=10)
        html = response.text
        match = re.search(r"https://www\\.google\\.com/maps/preview/place/.*?@(-?\\d+\\.\\d+),(-?\\d+\\.\\d+)", html)
        if match:
            lat, lng = match.groups()
            return float(lat), float(lng)
    except Exception as e:
        logger.error(f"Error extracting lat/lng from short url: {e}")
    return None, None

def extract_coords_from_gmaps_link(link: str) -> Tuple[Optional[float], Optional[float]]:
    """Extract latitude and longitude from Google Maps link using Python only (no Node.js fallback)"""
    if not link or not link.strip():
        return None, None
    link = link.strip()

    # Try to extract directly from URL (long form)
    patterns = [
        r'@(-?\d+\.\d+),(-?\d+\.\d+)',
        r'q=(-?\d+\.\d+),(-?\d+\.\d+)',
        r'lat=(-?\d+\.\d+)&lng=(-?\d+\.\d+)',
        r'lat=(-?\d+\.\d+)&lon=(-?\d+\.\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            try:
                lat = float(match.group(1))
                lon = float(match.group(2))
                logger.info(f"Extracted coordinates from URL pattern: {lat}, {lon}")
                return lat, lon
            except (ValueError, IndexError):
                continue

    # If it's a short URL, try to extract from HTML preview
    if any(domain in link for domain in ['maps.app.goo.gl', 'goo.gl/maps']):
        lat, lon = extract_lat_lng_from_short_url(link)
        if lat is not None and lon is not None:
            logger.info(f"Extracted coordinates from short URL HTML: {lat}, {lon}")
            return lat, lon

    logger.warning(f"Failed to extract coordinates from link: {link}")
    return None, None

def upload_to_supabase(file_path: str) -> str:
    """Upload file to Supabase storage bucket with better error handling"""
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            logger.warning("Supabase URL or key not set")
            return "Foto tersimpan (tanpa upload)"
        
        # Initialize Supabase client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Generate unique filename
        import uuid
        file_extension = os.path.splitext(file_path)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        # Read the image file
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        # Upload to Supabase storage bucket
        bucket_name = "photo"
        try:
            logger.info(f"Uploading to bucket: {bucket_name}")
            
            # Upload to Supabase storage bucket
            response = supabase.storage.from_(bucket_name).upload(
                path=unique_filename,
                file=file_data,
                file_options={"content-type": "image/jpeg"}
            )
            
            if response:
                # Get public URL
                public_url = supabase.storage.from_(bucket_name).get_public_url(unique_filename)
                logger.info(f"Successfully uploaded to Supabase: {public_url}")
                return public_url
            else:
                logger.error("Supabase upload failed: No response")
                return "Foto tersimpan (gagal upload)"
                
        except Exception as upload_error:
            error_str = str(upload_error)
            if "row-level security policy" in error_str.lower():
                logger.error("Supabase RLS policy blocking upload. Please disable RLS for the 'photo' bucket or create appropriate policies.")
                return "Foto tersimpan (RLS policy blocking upload)"
            elif "bucket not found" in error_str.lower():
                logger.error("Supabase bucket 'photo' not found. Please create the bucket in your Supabase dashboard.")
                return "Foto tersimpan (bucket tidak ditemukan)"
            else:
                logger.error(f"Supabase upload error: {upload_error}")
                return "Foto tersimpan (error sistem)"
            
    except Exception as e:
        logger.error(f"Supabase upload error: {e}")
        return "Foto tersimpan (error sistem)"

def validate_caption_data(row: Dict[str, str]) -> Tuple[bool, List[str], str]:
    """Validate caption data fields"""
    missing_fields = []
    
    for field_key, field_name in REQUIRED_FIELDS.items():
        field_value = row.get(field_key, '').strip()
        if not field_value:
            missing_fields.append(field_name)
    
    if missing_fields:
        error_message = f"❌ **Data tidak lengkap!**\n\nField yang masih kosong:\n"
        for i, field in enumerate(missing_fields, 1):
            error_message += f"{i}. {field}\n"
        error_message += "\n📝 **Langkah selanjutnya:**\nLengkapi field yang kosong di atas, kemudian kirim ulang data."
        return False, missing_fields, error_message
    
    return True, [], "✅ Semua data lengkap!"

def cleanup_pending_data(user_id: str):
    """Clean up pending data and temporary files for a user"""
    if user_id in pending_data:
        old_file_path = pending_data[user_id].get('file_path')
        if old_file_path and os.path.exists(old_file_path):
            try:
                os.remove(old_file_path)
                logger.info(f"Cleaned up temporary file: {old_file_path}")
            except Exception as e:
                logger.error(f"Failed to remove temporary file: {e}")
        del pending_data[user_id]

def save_to_spreadsheet(data: Dict[str, str], user_id: str, coords: str, file_link: str, gmaps_link: str = "") -> bool:
    """Save data to spreadsheet with error handling"""
    if not sheet:
        logger.error("Google Sheets not available")
        return False
    
    try:
        timestamp = format_timestamp()
        no = len(sheet.get_all_values())
        
        row_data = [
            no, timestamp, user_id, data['nama_sa'], data['sto'], data['cluster'], data['usaha'],
            data['pic'], data['hpwa'], data['internet'], data['biaya'], data['voc'], 
            coords, file_link, gmaps_link, "Default"
        ]
        
        sheet.append_row(row_data)
        logger.info(f"Successfully saved data for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to save to spreadsheet: {e}")
        return False

def process_coordinates(lat: float, lon: float) -> Tuple[str, str]:
    """Process coordinates and return location string and Google Maps link"""
    location_coords = f"{lat},{lon}"
    gmaps_link = get_gmaps_link_from_coords(lat, lon)
    return location_coords, gmaps_link

def extract_markdown_link(text: str) -> str:
    """Extract URL from markdown link format [text](url)"""
    md_match = re.match(r'\[.*?\]\((https?://[^\)]+)\)', text)
    return md_match.group(1) if md_match else text

# Event handlers
async def handle_photo_only(event, user_id: str):
    """Handle photo-only messages"""
    try:
        file_path = await event.download_media()
        
        # Check if there's existing caption data
        if user_id in pending_data and pending_data[user_id].get('type') == 'caption_only':
            caption_text = pending_data[user_id]['data']
            match = CAPTION_PATTERN.search(caption_text)
            if match:
                row = match.groupdict()
                
                # Validate data
                is_valid, missing_fields, error_message = validate_caption_data(row)
                if not is_valid:
                    await event.reply(error_message)
                    return
                
                # Check for Google Maps link
                link_gmaps = row.get('link_gmaps', '').strip()
                has_valid_coordinates = False
                lat, lon = None, None
                
                if link_gmaps:
                    link_gmaps = extract_markdown_link(link_gmaps)
                    lat, lon = extract_coords_from_gmaps_link(link_gmaps)
                    if lat is not None and lon is not None:
                        has_valid_coordinates = True
                
                if has_valid_coordinates and lat is not None and lon is not None:
                    # Process complete data - with error handling for Supabase upload
                    try:
                        file_link = upload_to_supabase(file_path)
                    except Exception as e:
                        logger.warning(f"Supabase upload failed, continuing without upload: {e}")
                        file_link = "Foto tersimpan (gagal upload)"
                    
                    location_coords, gmaps_link = process_coordinates(lat, lon)
                    
                    if save_to_spreadsheet(row, user_id, location_coords, file_link, gmaps_link):
                        cleanup_pending_data(user_id)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        await event.reply(f"✅ **SELAMAT Data berhasil disimpan!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data telah ditambahkan ke spreadsheet\n\n🎉 **Status:** Data selesai diproses")
                    else:
                        await event.reply("❌ Gagal menyimpan ke Google Spreadsheet")
                else:
                    # Store pending data without failing if Supabase upload fails
                    cleanup_pending_data(user_id)
                    try:
                        file_link = upload_to_supabase(file_path)
                    except Exception as e:
                        logger.warning(f"Supabase upload failed, continuing without upload: {e}")
                        file_link = None
                    
                    pending_data[user_id] = {
                        'data': caption_text,
                        'file_link': file_link,
                        'timestamp': format_timestamp(),
                        'file_path': file_path,
                        'type': 'complete'
                    }
                    await event.reply("✅ **Foto dan caption telah digabung.**\n\n Data disimpan sementara.\n\n❌ **Yang masih kurang:**\n• Koordinat lokasi\n\n📍 **Langkah selanjutnya:**\n1. Share lokasi Anda sekarang, ATAU\n2. Kirim Link Google Maps")
            else:
                # Invalid caption format - store photo only without Drive upload attempt
                cleanup_pending_data(user_id)
                pending_data[user_id] = {
                    'data': None,
                    'file_link': None,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'file_path': file_path,
                    'type': 'photo_only'
                }
                await event.reply("⏳ **Foto disimpan sementara!**\n\nFormat caption sebelumnya tidak sesuai.\n\nSilakan kirim caption (teks) sesuai format.\n\nKetik /format untuk melihat format yang benar.")
        else:
            # Store photo only - don't try to upload to Google Drive yet
            cleanup_pending_data(user_id)
            pending_data[user_id] = {
                'data': None,
                'file_link': None,
                'timestamp': format_timestamp(),
                'file_path': file_path,
                'type': 'photo_only'
            }
            await event.reply("⏳ **Foto disimpan sementara!**\n\nSilakan kirim caption (teks) sesuai format.\n\nKetik /format untuk melihat format yang benar.")
            
    except Exception as e:
        logger.error(f"Error in handle_photo_only: {e}")
        try:
            await event.reply(f"❌ Terjadi error saat memproses foto: {e}")
        except:
            logger.error("Failed to send error message to user")

async def handle_photo_with_caption(event, user_id: str):
    """Handle photo with caption messages"""
    try:
        match = CAPTION_PATTERN.search(event.text.strip())
        if not match:
            await event.reply("❌ Data belum lengkap atau format caption tidak sesuai.\n\nLengkapi data atau ketik /format untuk melihat format yang benar.")
            return
        
        row = match.groupdict()
        
        # Validate data
        is_valid, missing_fields, error_message = validate_caption_data(row)
        if not is_valid:
            await event.reply(error_message)
            return
        
        # Check for Google Maps link
        link_gmaps = row.get('link_gmaps', '').strip()
        has_valid_coordinates = False
        lat, lon = None, None
        
        if link_gmaps:
            link_gmaps = extract_markdown_link(link_gmaps)
            lat, lon = extract_coords_from_gmaps_link(link_gmaps)
            if lat is not None and lon is not None:
                has_valid_coordinates = True
        
        if not has_valid_coordinates:
            # Store pending data
            cleanup_pending_data(user_id)
            file_path = await event.download_media()
            
            try:
                file_link = upload_to_supabase(file_path)
            except Exception as e:
                logger.warning(f"Supabase upload failed, continuing without upload: {e}")
                file_link = "Foto tersimpan"
            
            pending_data[user_id] = {
                'data': row,
                'file_link': file_link,
                'timestamp': format_timestamp(),
                'file_path': file_path
            }
            
            await event.reply("⏳ **Data disimpan sementara!**\n\n📋 Data Anda telah diterima tetapi belum lengkap.\n\n❌ **Yang masih kurang:**\n• Koordinat lokasi\n\n📍 **Langkah selanjutnya:**\n1. Share lokasi Anda sekarang, ATAU\n2. Kirim Link Google Maps")
            return
        
        # Process complete data
        cleanup_pending_data(user_id)
        file_path = await event.download_media()
        
        try:
            file_link = upload_to_supabase(file_path)
        except Exception as e:
            logger.warning(f"Supabase upload failed, continuing without upload: {e}")
            file_link = "Foto tersimpan"
            
        if lat is not None and lon is not None:
            location_coords, gmaps_link = process_coordinates(lat, lon)
        else:
            location_coords, gmaps_link = "", ""
        
        if save_to_spreadsheet(row, user_id, location_coords, file_link, gmaps_link):
            await event.reply(f"✅ **SELAMAT Data berhasil disimpan!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data telah ditambahkan ke spreadsheet\n\n🎉 **Status:** Data selesai diproses")
        else:
            await event.reply("❌ Gagal menyimpan ke Google Spreadsheet")
        
        # Clean up temporary file
        if os.path.exists(file_path):
            os.remove(file_path)
            
    except Exception as e:
        logger.error(f"Error in handle_photo_with_caption: {e}")
        try:
            await event.reply(f"❌ Terjadi error saat memproses foto dan caption: {e}")
        except:
            logger.error("Failed to send error message to user")

async def handle_caption_only(event, user_id: str):
    """Handle caption-only messages"""
    try:
        caption_text = event.text.strip()
        match = CAPTION_PATTERN.search(caption_text)
        if not match:
            await event.reply("❌ Format caption tidak sesuai.\n\nKetik /format untuk melihat format yang benar.")
            return
        
        row = match.groupdict()
        is_valid, missing_fields, error_message = validate_caption_data(row)
        if not is_valid:
            await event.reply(error_message)
            return
        
        # Check for Google Maps link
        link_gmaps = row.get('link_gmaps', '').strip()
        has_valid_coordinates = False
        lat, lon = None, None
        
        if link_gmaps:
            link_gmaps = extract_markdown_link(link_gmaps)
            lat, lon = extract_coords_from_gmaps_link(link_gmaps)
            if lat is not None and lon is not None:
                has_valid_coordinates = True
        
        # Check if there's existing photo data
        existing_photo_path = None
        if user_id in pending_data and pending_data[user_id].get('type') == 'photo_only':
            existing_photo_path = pending_data[user_id].get('file_path')
        
        if existing_photo_path and os.path.exists(existing_photo_path):
            # Combine with existing photo
            try:
                file_link = upload_to_supabase(existing_photo_path)
            except Exception as e:
                logger.warning(f"Supabase upload failed, continuing without upload: {e}")
                file_link = "Foto tersimpan"
            
            if has_valid_coordinates and lat is not None and lon is not None:
                # Process complete data
                location_coords, gmaps_link = process_coordinates(lat, lon)
                
                if save_to_spreadsheet(row, user_id, location_coords, file_link, gmaps_link):
                    cleanup_pending_data(user_id)
                    if os.path.exists(existing_photo_path):
                        os.remove(existing_photo_path)
                    await event.reply(f"✅ **SELAMAT Data berhasil disimpan!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data telah ditambahkan ke spreadsheet\n\n🎉 **Status:** Data selesai diproses")
                else:
                    await event.reply("❌ Gagal menyimpan ke Google Spreadsheet")
            else:
                # Store pending data with photo
                pending_data[user_id] = {
                    'data': caption_text,
                    'file_link': file_link,
                    'timestamp': format_timestamp(),
                    'file_path': existing_photo_path,
                    'type': 'complete'
                }
                await event.reply("✅ **Foto dan caption telah digabung.**\n\n Data disimpan sementara.\n\n❌ **Yang masih kurang:**\n• Koordinat lokasi\n\n📍 **Langkah selanjutnya:**\n1. Share lokasi Anda sekarang, ATAU\n2. Kirim Link Google Maps")
        else:
            # Store caption only
            cleanup_pending_data(user_id)
            pending_data[user_id] = {
                'data': caption_text,
                'file_link': None,
                'timestamp': format_timestamp(),
                'file_path': None,
                'type': 'caption_only'
            }
            
            if has_valid_coordinates:
                await event.reply(f"⏳ **Caption disimpan sementara!**\n\n✅ Link Google Maps: Valid\n📍 Koordinat: {lat}, {lon}\n\nSilakan kirim foto yang sesuai.\n\nKetik /format untuk melihat format yang benar.")
            else:
                await event.reply("⏳ **Caption disimpan sementara!**\n\nSilakan kirim foto yang sesuai.")
                
    except Exception as e:
        logger.error(f"Error in handle_caption_only: {e}")
        try:
            await event.reply(f"❌ Terjadi error saat memproses caption: {e}")
        except:
            logger.error("Failed to send error message to user")

async def handle_gmaps_link(event, user_id: str):
    """Handle Google Maps link messages"""
    if user_id not in pending_data:
        await event.reply("❌ Tidak ada data sementara.\n\nSilakan kirim data terlebih dahulu.")
        return
    
    pending = pending_data[user_id]
    data_type = pending.get('type', 'unknown')
    link_gmaps = event.text.strip()
    lat, lon = extract_coords_from_gmaps_link(link_gmaps)
    
    if lat is None or lon is None:
        await event.reply("❌ Link Google Maps tidak valid.\n\nSilakan kirim Link Google Maps yang valid atau share lokasi.")
        return
    
    # Process based on data type
    if data_type == 'complete':
        await process_complete_data_with_coords(event, pending, user_id, lat, lon, link_gmaps)
    elif data_type == 'caption_only':
        await process_caption_only_with_coords(event, pending, user_id, lat, lon, link_gmaps)
    elif data_type == 'photo_only':
        await event.reply("❌ Data belum lengkap.\n\nSilakan kirim caption terlebih dahulu.")
    else:
        await process_other_data_with_coords(event, pending, user_id, lat, lon, link_gmaps)

async def process_complete_data_with_coords(event, pending: Dict, user_id: str, lat: float, lon: float, link_gmaps: str):
    """Process complete data with coordinates"""
    try:
        caption_text = pending['data']
        match = CAPTION_PATTERN.search(caption_text)
        if not match:
            await event.reply("❌ Format caption tidak sesuai.\n\nKetik /format untuk melihat format yang benar.")
            return
        
        row = match.groupdict()
        is_valid, missing_fields, error_message = validate_caption_data(row)
        if not is_valid:
            await event.reply(error_message)
            return
        
        file_path = pending['file_path']
        
        try:
            file_link = upload_to_supabase(file_path)
        except Exception as e:
            logger.warning(f"Supabase upload failed, continuing without upload: {e}")
            file_link = "Foto tersimpan"
            
        location_coords, gmaps_link = process_coordinates(lat, lon)
        
        if save_to_spreadsheet(row, user_id, location_coords, file_link, gmaps_link):
            cleanup_pending_data(user_id)
            if os.path.exists(file_path):
                os.remove(file_path)
            await event.reply(f"✅ **SELAMAT Data berhasil disimpan ke spreadsheet!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data lengkap telah ditambahkan\n\n🎉 **Status:** Data selesai diproses")
        else:
            await event.reply("❌ Gagal menyimpan ke Google Spreadsheet")
    except Exception as e:
        logger.error(f"Error in process_complete_data_with_coords: {e}")
        await event.reply("❌ Terjadi error saat memproses data. Silakan coba lagi.")

async def process_caption_only_with_coords(event, pending: Dict, user_id: str, lat: float, lon: float, link_gmaps: str):
    """Process caption-only data with coordinates"""
    try:
        caption_text = pending['data']
        match = CAPTION_PATTERN.search(caption_text)
        if not match:
            await event.reply("❌ Format caption tidak sesuai.\n\nKetik /format untuk melihat format yang benar.")
            return
        
        row = match.groupdict()
        is_valid, missing_fields, error_message = validate_caption_data(row)
        if not is_valid:
            await event.reply(error_message)
            return
        
        location_coords, gmaps_link = process_coordinates(lat, lon)
        
        if save_to_spreadsheet(row, user_id, location_coords, "Tidak ada foto", gmaps_link):
            cleanup_pending_data(user_id)
            await event.reply(f"✅ **SELAMAT Data berhasil disimpan ke spreadsheet!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data telah ditambahkan (tanpa foto)\n\n🎉 **Status:** Data selesai diproses")
        else:
            await event.reply("❌ Gagal menyimpan ke Google Spreadsheet")
    except Exception as e:
        logger.error(f"Error in process_caption_only_with_coords: {e}")
        await event.reply("❌ Terjadi error saat memproses data. Silakan coba lagi.")

async def process_other_data_with_coords(event, pending: Dict, user_id: str, lat: float, lon: float, link_gmaps: str):
    """Process other data types with coordinates"""
    try:
        if 'data' not in pending or not pending['data']:
            await event.reply("❌ Data tidak lengkap.\n\nSilakan kirim foto dan caption terlebih dahulu.")
            return
        
        if isinstance(pending['data'], dict):
            row = pending['data']
            is_valid, missing_fields, error_message = validate_caption_data(row)
            if not is_valid:
                await event.reply(error_message)
                return
            
            file_path = pending.get('file_path')
            file_link = pending.get('file_link', 'Gagal upload')
            
            # Try to upload if we have a file path
            if file_path and os.path.exists(file_path):
                try:
                    file_link = upload_to_supabase(file_path)
                except Exception as e:
                    logger.warning(f"Supabase upload failed, continuing without upload: {e}")
                    file_link = "Foto tersimpan"
            
            location_coords, gmaps_link = process_coordinates(lat, lon)
            
            if save_to_spreadsheet(row, user_id, location_coords, file_link, gmaps_link):
                cleanup_pending_data(user_id)
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                await event.reply(f"✅ **SELAMAT Data berhasil disimpan ke spreadsheet!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data lengkap telah ditambahkan\n\n🎉 **Status:** Data selesai diproses")
            else:
                await event.reply("❌ Gagal menyimpan ke Google Spreadsheet")
        else:
            await event.reply("❌ Format data tidak sesuai.\n\nSilakan kirim ulang data dengan format yang benar.")
    except Exception as e:
        logger.error(f"Error in process_other_data_with_coords: {e}")
        await event.reply("❌ Terjadi error saat memproses data. Silakan coba lagi.")

async def handle_location_share(event, user_id: str):
    """Handle location sharing"""
    try:
        latitude = event.message.geo.lat
        longitude = event.message.geo.long
        
        if user_id in pending_data:
            pending = pending_data[user_id]
            data_type = pending.get('type', 'unknown')
            
            if data_type == 'complete':
                await process_complete_data_with_coords(event, pending, user_id, latitude, longitude, "")
            elif data_type == 'caption_only':
                await process_caption_only_with_coords(event, pending, user_id, latitude, longitude, "")
            elif data_type == 'photo_only':
                await event.reply("❌ Data belum lengkap.\n\nSilakan kirim caption terlebih dahulu.")
            else:
                await process_other_data_with_coords(event, pending, user_id, latitude, longitude, "")
        else:
            # Update existing data in spreadsheet
            try:
                expected_headers = [
                    'No', 'Timestamp', 'ID', 'Nama', 'STO', 'Cluster', 'Nama Usaha', 
                    'PIC', 'HP/WA', 'Internet Existing', 'Biaya Internet', 'VOC', 
                    'Lokasi', 'Foto', 'Link Gmaps', 'Validitas'
                ]
                records = sheet.get_all_records(expected_headers=expected_headers)
                row_idx = None
                for idx, row in enumerate(records, start=2):
                    if str(row.get('ID', '')) == user_id:
                        row_idx = idx
                        break
                
                if row_idx:
                    location_coords, gmaps_link = process_coordinates(latitude, longitude)
                    sheet.update_cell(row_idx, 13, location_coords)
                    sheet.update_cell(row_idx, 15, gmaps_link)
                    await event.reply(f"✅ **Koordinat berhasil ditambahkan!**\n\n📍 Lokasi: {latitude}, {longitude}\n📊 Data telah dilengkapi dengan koordinat")
                else:
                    await event.reply("❌ **Tidak dapat menambahkan koordinat!**\n\nTidak ditemukan data sebelumnya untuk user ini.\n\n📋 **Langkah yang benar:**\n1. Kirim data dengan Link Google Maps yang valid, ATAU\n2. Kirim data tanpa Link Gmaps, kemudian share lokasi")
            except Exception as e:
                logger.error(f"Failed to update location in spreadsheet: {e}")
                await event.reply(f"❌ Gagal menyimpan lokasi ke Google Spreadsheet: {e}")
    except Exception as e:
        logger.error(f"Error in handle_location_share: {e}")
        await event.reply("❌ Terjadi error saat memproses lokasi. Silakan coba lagi.")

# Main event handler
@client.on(events.NewMessage(incoming=True))
async def handler(event):
    try:
        if not event.is_private:
            return
        
        user_id = str(event.sender_id)
        
        # Handle commands
        if event.text and event.text.startswith('/'):
            return
        
        # Check if user has started
        if user_id not in user_started:
            await event.reply("⚠️ **Silakan ketik /start terlebih dahulu!**\n\nBot belum siap menerima data.\n\nKetik /start untuk memulai.")
            return
        
        # Handle different message types
        if event.photo and not event.text:
            await handle_photo_only(event, user_id)
        elif event.photo and event.text:
            await handle_photo_with_caption(event, user_id)
        elif event.text and not event.photo:
            if 'maps.google.com' in event.text or 'goo.gl/maps' in event.text or 'maps.app.goo.gl' in event.text:
                await handle_gmaps_link(event, user_id)
            else:
                await handle_caption_only(event, user_id)
        elif hasattr(event.message, "geo") and event.message.geo:
            await handle_location_share(event, user_id)
            
    except Exception as e:
        logger.error(f"Error in main handler: {e}")
        try:
            await event.reply(f"❌ Terjadi error pada bot: {e}")
        except:
            logger.error("Failed to send error message to user")

# Command handlers
@client.on(events.NewMessage(pattern=r'^/format$', incoming=True))
async def format_handler(event):
    if event.is_private:
        format_text = (
            "#VISIT\n\n"
            "Nama SA/ AR: \n"
            "STO: \n"
            "Cluster: \n\n"
            "Nama usaha: \n"
            "Nama PIC: \n"
            "Nomor HP/ WA: \n"
            "Internet existing: \n"
            "Biaya internet existing: \n"
            "Voice of Customer:  \n\n"
        )
        await event.reply(format_text)

@client.on(events.NewMessage(pattern=r'^/help$', incoming=True))
async def help_handler(event):
    if event.is_private:
        help_text = (
            "🆘 **BANTUAN BOT YOVI**\n\n"
            "📋 **CARA KERJA:**\n\n"
            "🚀 **Langkah 1:** Ketik /start untuk memulai\n\n"
            "📝 **Langkah 2:** Kirim data secara bertahap:\n"
            "• Kirim foto terlebih dahulu, ATAU\n"
            "• Kirim caption terlebih dahulu\n"
            "• Kemudian kirim bagian yang kurang\n\n"
            "📍 **Langkah 3:** Lengkapi koordinat:\n"
            "• Share lokasi, ATAU\n"
            "• Kirim Link Google Maps\n\n"
            "✅ **Data akan disimpan jika:**\n"
            "• Lengkap dan menyertakan koordinat (share lokasi atau Link Google Maps)\n\n"
            "⏳ **Data tanpa koordinat:**\n"
            "• Disimpan sementara sampai lengkap\n"
            "• Data lama akan diganti jika kirim data baru\n\n"
            "🗑️ **Reset data:**\n"
            "• Ketik /start untuk menghapus data sementara\n"
            "• Ketik /clear untuk menghapus data sementara\n\n"
            "📊 **Cek status:**\n"
            "• Ketik /status untuk melihat data sementara\n\n"
            "🔗 **CARA MENDAPATKAN LINK GOOGLE MAPS:**\n"
            "1. Buka Google Maps\n"
            "2. Cari lokasi yang diinginkan\n"
            "3. Klik Share → Copy link\n"
            "4. Paste di chat bot\n\n"
            "📍 **CARA SHARE LOKASI:**\n"
            "1. Kirim data terlebih dahulu\n"
            "2. Kemudian share lokasi Anda\n"
            "3. Data akan otomatis lengkap\n\n"
            "📝 **FORMAT DATA:**\n"
            "Ketik /format untuk melihat format yang benar"
        )
        await event.reply(help_text)

@client.on(events.NewMessage(pattern=r'^/start$', incoming=True))
async def start_handler(event):
    if event.is_private:
        user_id = str(event.sender_id)
        cleanup_pending_data(user_id)
        await event.reply("🤖 **Selamat datang di bot YOVI!**\n\nBot siap menerima data.\n\n📋 **Cara mengisi data:**\n\n1. Kirim foto terlebih dahulu, ATAU\n2. Kirim caption terlebih dahulu\n3. Kemudian kirim bagian yang kurang\n4. Share lokasi atau kirim Link Google Maps\n\n💡 **Command yang tersedia:**\n• /format - Format pengisian data\n• /help - Bantuan lengkap\n• /status - Cek status data sementara\n• /clear - Hapus data sementara")
        user_started[user_id] = True

@client.on(events.NewMessage(pattern=r'^/status$', incoming=True))
async def status_handler(event):
    if event.is_private:
        user_id = str(event.sender_id)
        
        if user_id not in user_started:
            await event.reply("⚠️ **Silakan ketik /start terlebih dahulu!**\n\nBot belum siap menerima data.\n\nKetik /start untuk memulai.")
            return
        
        if user_id in pending_data:
            pending = pending_data[user_id]
            data_type = pending.get('type', 'unknown')
            
            if data_type == 'photo_only':
                await event.reply("📸 **Status: Foto tersimpan**\n\n✅ Foto: Sudah ada\n❌ Caption: Belum ada\n\nSilakan kirim caption sesuai format.")
            elif data_type == 'caption_only':
                caption_text = pending.get('data', '')
                match = CAPTION_PATTERN.search(caption_text)
                if match:
                    row = match.groupdict()
                    link_gmaps = row.get('link_gmaps', '').strip()
                    if link_gmaps:
                        link_gmaps = extract_markdown_link(link_gmaps)
                        lat, lon = extract_coords_from_gmaps_link(link_gmaps)
                        if lat is not None and lon is not None:
                            await event.reply(f"📝 **Status: Caption tersimpan**\n\n❌ Foto: Belum ada\n✅ Caption: Sudah ada\n✅ Link Google Maps: Valid\n📍 Koordinat: {lat}, {lon}\n\nSilakan kirim foto yang sesuai.")
                        else:
                            await event.reply("📝 **Status: Caption tersimpan**\n\n❌ Foto: Belum ada\n✅ Caption: Sudah ada\n❌ Link Google Maps: Tidak valid\n\nSilakan kirim foto yang sesuai.")
                    else:
                        await event.reply("📝 **Status: Caption tersimpan**\n\n❌ Foto: Belum ada\n✅ Caption: Sudah ada\n❌ Link Google Maps: Belum ada\n\nSilakan kirim foto yang sesuai.")
                else:
                    await event.reply("📝 **Status: Caption tersimpan**\n\n❌ Foto: Belum ada\n✅ Caption: Sudah ada\n❌ Format: Tidak sesuai\n\nSilakan kirim foto yang sesuai.")
            elif data_type == 'complete':
                caption_text = pending.get('data', '')
                match = CAPTION_PATTERN.search(caption_text)
                if match:
                    row = match.groupdict()
                    link_gmaps = row.get('link_gmaps', '').strip()
                    if link_gmaps:
                        link_gmaps = extract_markdown_link(link_gmaps)
                        lat, lon = extract_coords_from_gmaps_link(link_gmaps)
                        if lat is not None and lon is not None:
                            await event.reply(f"📋 **Status: Data lengkap**\n\n✅ Foto: Sudah ada\n✅ Caption: Sudah ada\n✅ Link Google Maps: Valid\n📍 Koordinat: {lat}, {lon}\n\nData siap disimpan ke spreadsheet!")
                        else:
                            await event.reply("📋 **Status: Data lengkap**\n\n✅ Foto: Sudah ada\n✅ Caption: Sudah ada\n❌ Link Google Maps: Tidak valid\n\nSilakan share lokasi atau kirim Link Google Maps.")
                    else:
                        await event.reply("📋 **Status: Data lengkap**\n\n✅ Foto: Sudah ada\n✅ Caption: Sudah ada\n❌ Link Google Maps: Belum ada\n\nSilakan share lokasi atau kirim Link Google Maps.")
                else:
                    await event.reply("📋 **Status: Data lengkap**\n\n✅ Foto: Sudah ada\n✅ Caption: Sudah ada\n❌ Format: Tidak sesuai\n\nSilakan share lokasi atau kirim Link Google Maps.")
            else:
                await event.reply("📋 **Status: Data tersimpan**\n\nData sedang menunggu kelengkapan.\n\nSilakan lengkapi data yang kurang.")
        else:
            await event.reply("📭 **Status: Tidak ada data sementara**\n\nSilakan kirim foto atau caption untuk memulai.")

@client.on(events.NewMessage(pattern=r'^/clear$', incoming=True))
async def clear_handler(event):
    if event.is_private:
        user_id = str(event.sender_id)
        
        if user_id not in user_started:
            await event.reply("⚠️ **Silakan ketik /start terlebih dahulu!**\n\nBot belum siap menerima data.\n\nKetik /start untuk memulai.")
            return
        
        cleanup_pending_data(user_id)
        await event.reply("Silakan kirim data baru.")

# Main execution
if __name__ == "__main__":
    logger.info("Bot is starting...")
    logger.info(f"API ID: {API_ID}")
    logger.info(f"Bot Token: {BOT_TOKEN[:10] if BOT_TOKEN else 'None'}...")
    logger.info(f"Drive ID: {DRIVE_ID}")
    logger.info(f"Sheet Name: {SHEET_NAME}")
    
    try:
        logger.info("Bot is running...")
        client.run_until_disconnected()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise