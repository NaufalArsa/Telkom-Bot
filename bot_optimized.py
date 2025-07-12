import os, re, json, gspread, requests, subprocess
from oauth2client.service_account import ServiceAccountCredentials
from telethon import TelegramClient, events
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
from datetime import datetime
from typing import Dict, Tuple, Optional, List
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
API_ID = 29586893
API_HASH = "d52a299d8400f35bdf8acd65900ea13f"
BOT_TOKEN = "7234638021:AAHLBVH4CK9L0xMmWwEI27vduHS50_GEjJI"
DRIVE_ID = '118MghjEj1lQGx3xht7v_2yMwS84z96q0'
SHEET_NAME = 'Recap Visit YOVI'
CREDENTIALS_FILE = 'gcredentials.json'

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

# Load credentials once
with open(CREDENTIALS_FILE, 'r') as f:
    creds_dict = json.load(f)

# Initialize Google services
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
gc = gspread.service_account(filename=CREDENTIALS_FILE)
sheet = gc.open(SHEET_NAME).sheet1

# Data storage
pending_data: Dict[str, Dict] = {}
user_started: Dict[str, bool] = {}

# Cache for Google Drive service
_drive_service = None

def get_drive_service():
    """Get or create Google Drive service with caching"""
    global _drive_service
    if _drive_service is None:
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        _drive_service = build('drive', 'v3', credentials=creds)
    return _drive_service

def get_address_from_coords(lat: float, lon: float) -> str:
    """Get address from coordinates using OpenStreetMap"""
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
    try:
        resp = requests.get(url, headers={"User-Agent": "TelegramBot"}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("display_name", f"{lat},{lon}")
        return f"{lat},{lon}"
    except Exception as e:
        logger.warning(f"Failed to get address from coordinates: {e}")
        return f"{lat},{lon}"

def get_gmaps_link_from_coords(lat: float, lon: float) -> str:
    """Generate Google Maps link from coordinates"""
    return f"https://www.google.com/maps?q={lat},{lon}"

def extract_coords_from_gmaps_link(link: str) -> Tuple[Optional[float], Optional[float]]:
    """Extract latitude and longitude from Google Maps link using Node.js"""
    if not link or not link.strip():
        return None, None
    
    # Clean the link
    if '?' in link:
        link = link.split('?', 1)[0]

    try:
        result = subprocess.run(
            ['node', 'expand.js', link],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        for line in result.stdout.splitlines():
            if line.startswith("Result:"):
                coords_str = line.replace("Result:", "").strip()
                try:
                    coords = json.loads(coords_str.replace("'", '"'))
                    if coords and 'latitude' in coords and 'longitude' in coords:
                        return coords['latitude'], coords['longitude']
                except Exception as e:
                    logger.error(f"Error parsing coordinates: {e}")
                    continue
    except Exception as e:
        logger.error(f"Error calling Node.js script: {e}")
    
    return None, None

def upload_to_gdrive(file_path: str) -> str:
    """Upload file to Google Drive and return public link"""
    try:
        service = get_drive_service()
        file_metadata = {
            'name': os.path.basename(file_path), 
            'parents': [DRIVE_ID]
        }
        media = MediaFileUpload(file_path, resumable=True)
        file = service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id'
        ).execute()
        
        # Make file publicly readable
        service.permissions().create(
            fileId=file.get('id'), 
            body={'role': 'reader', 'type': 'anyone'}
        ).execute()
        
        return f"https://drive.google.com/uc?id={file.get('id')}"
    except Exception as e:
        logger.error(f"Failed to upload to Google Drive: {e}")
        return f"Gagal upload: {e}"

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
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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

async def handle_photo_only(event, user_id: str):
    """Handle photo-only messages"""
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
                # Process complete data
                file_link = upload_to_gdrive(file_path)
                location_coords, gmaps_link = process_coordinates(lat, lon)
                
                if save_to_spreadsheet(row, user_id, location_coords, file_link, gmaps_link):
                    cleanup_pending_data(user_id)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    await event.reply(f"✅ **SELAMAT Data berhasil disimpan!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data telah ditambahkan ke spreadsheet\n\n🎉 **Status:** Data selesai diproses")
                else:
                    await event.reply("❌ Gagal menyimpan ke Google Spreadsheet")
            else:
                # Store pending data
                cleanup_pending_data(user_id)
                pending_data[user_id] = {
                    'data': caption_text,
                    'file_link': None,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'file_path': file_path,
                    'type': 'complete'
                }
                await event.reply("✅ **Foto dan caption telah digabung.**\n\n Data disimpan sementara.\n\n❌ **Yang masih kurang:**\n• Koordinat lokasi\n\n📍 **Langkah selanjutnya:**\n1. Share lokasi Anda sekarang, ATAU\n2. Kirim Link Google Maps")
        else:
            # Invalid caption format
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
        # Store photo only
        cleanup_pending_data(user_id)
        pending_data[user_id] = {
            'data': None,
            'file_link': None,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'file_path': file_path,
            'type': 'photo_only'
        }
        await event.reply("⏳ **Foto disimpan sementara!**\n\nSilakan kirim caption (teks) sesuai format.\n\nKetik /format untuk melihat format yang benar.")

async def handle_photo_with_caption(event, user_id: str):
    """Handle photo with caption messages"""
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
        file_link = upload_to_gdrive(file_path)
        
        pending_data[user_id] = {
            'data': row,
            'file_link': file_link,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'file_path': file_path
        }
        
        await event.reply("⏳ **Data disimpan sementara!**\n\n📋 Data Anda telah diterima tetapi belum lengkap.\n\n❌ **Yang masih kurang:**\n• Koordinat lokasi\n\n📍 **Langkah selanjutnya:**\n1. Share lokasi Anda sekarang, ATAU\n2. Kirim Link Google Maps")
        return
    
    # Process complete data
    cleanup_pending_data(user_id)
    file_path = await event.download_media()
    file_link = upload_to_gdrive(file_path)
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
    file_link = upload_to_gdrive(file_path)
    location_coords, gmaps_link = process_coordinates(lat, lon)
    
    if save_to_spreadsheet(row, user_id, location_coords, file_link, gmaps_link):
        cleanup_pending_data(user_id)
        if os.path.exists(file_path):
            os.remove(file_path)
        await event.reply(f"✅ **SELAMAT Data berhasil disimpan ke spreadsheet!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data lengkap telah ditambahkan\n\n🎉 **Status:** Data selesai diproses")
    else:
        await event.reply("❌ Gagal menyimpan ke Google Spreadsheet")

async def process_caption_only_with_coords(event, pending: Dict, user_id: str, lat: float, lon: float, link_gmaps: str):
    """Process caption-only data with coordinates"""
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

async def process_other_data_with_coords(event, pending: Dict, user_id: str, lat: float, lon: float, link_gmaps: str):
    """Process other data types with coordinates"""
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

async def handle_location_share(event, user_id: str):
    """Handle location sharing"""
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

async def handle_caption_only(event, user_id: str):
    """Handle caption-only messages"""
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
        file_link = upload_to_gdrive(existing_photo_path)
        
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
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'file_path': None,
            'type': 'caption_only'
        }
        
        if has_valid_coordinates:
            await event.reply(f"⏳ **Caption disimpan sementara!**\n\n✅ Link Google Maps: Valid\n📍 Koordinat: {lat}, {lon}\n\nSilakan kirim foto yang sesuai.\n\nKetik /format untuk melihat format yang benar.")
        else:
            await event.reply("⏳ **Caption disimpan sementara!**\n\nSilakan kirim foto yang sesuai.")

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
        await event.reply(f"❌ Terjadi error pada bot: {e}")

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

if __name__ == "__main__":
    logger.info("Bot is running...")
    try:
        client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Fatal error: {e}") 