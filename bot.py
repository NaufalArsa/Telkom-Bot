import os, re, json, gspread, requests, subprocess
from oauth2client.service_account import ServiceAccountCredentials
from telethon import TelegramClient, events
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def get_env_var(name, required=True):
    value = os.environ.get(name)
    if required and not value:
        raise ValueError(f"{name} environment variable not set!")
    return value

try:
    api_id_env = get_env_var("API_ID")
    api_hash = get_env_var("API_HASH")
    bot_token = get_env_var("BOT_TOKEN")
    api_id = int(api_id_env)  # type: ignore
except Exception as e:
    print(f"Error loading Telegram credentials: {e}")
    exit(1)

try:
    creds_json = get_env_var("GOOGLE_CREDS_JSON")
    creds_dict = json.loads(creds_json)  # type: ignore
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)  # type: ignore
    gc = gspread.authorize(creds)  # type: ignore
    sheet = gc.open('Recap Visit').sheet1
except Exception as e:
    print(f"Error loading Google credentials or opening sheet: {e}")
    exit(1)

client = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)  # type: ignore

pattern = re.compile(r"""
    Nama\s+SA/\s*AR:\s*(?P<nama_sa>.+?)\n+
    STO:\s*(?P<sto>.+?)\n+
    Cluster:\s*(?P<cluster>.+?)\n+
    \n*
    Nama\s+usaha:\s*(?P<usaha>.+?)\n+
    Nama\s+PIC:\s*(?P<pic>.+?)\n+
    Nomor\s+HP/\s*WA:\s*(?P<hpwa>.+?)\n+
    Internet\s+existing:\s*(?P<internet>.+?)\n+
    Biaya\s+internet\s+existing:\s*(?P<biaya>.+?)\n+
    Voice\s+of\s+Customer:\s*(?P<voc>.+?)\n+
    Link\s+Gmaps:\s*(?P<link_gmaps>.*)
""", re.DOTALL | re.MULTILINE | re.IGNORECASE | re.VERBOSE)

def get_address_from_coords(lat, lon):
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
    try:
        resp = requests.get(url, headers={"User-Agent": "TelegramBot"})
        if resp.status_code == 200:
            data = resp.json()
            return data.get("display_name", f"{lat},{lon}")
        return f"{lat},{lon}"
    except Exception:
        return f"{lat},{lon}"

def extract_coords_from_gmaps_link(link):
    """Extract latitude and longitude from Google Maps link using Node.js"""
    if not link or link.strip() == "":
        return None, None
    
    if '?' in link:
        link = link.split('?', 1)[0]

    try:
        # Call Node.js script and pass the link as an argument
        result = subprocess.run(
            ['node', 'expand.js', link],
            capture_output=True,
            text=True
        )
        
        # Parse the output (expecting a JSON-like result)
        for line in result.stdout.splitlines():
            if line.startswith("Result:"):
                coords_str = line.replace("Result:", "").strip()
                try:
                    coords = json.loads(coords_str.replace("'", '"'))
                    if coords and 'latitude' in coords and 'longitude' in coords:
                        return coords['latitude'], coords['longitude']
                except Exception as e:
                    print(f"Error parsing coordinates: {e}")
                    pass
    except Exception as e:
        print(f"Error calling Node.js script: {e}")
    
    return None, None

def upload_to_gdrive(file_path, creds_dict):
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)
    # Replace 'YOUR_FOLDER_ID' with your actual folder ID
    file_metadata = {'name': os.path.basename(file_path), 'parents': ['118MghjEj1lQGx3xht7v_2yMwS84z96q0']}
    media = MediaFileUpload(file_path, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    service.permissions().create(fileId=file.get('id'), body={'role': 'reader', 'type': 'anyone'}).execute()
    file_link = f"https://drive.google.com/uc?id={file.get('id')}"
    return file_link

@client.on(events.NewMessage(incoming=True))
async def handler(event):
    try:
        if event.is_private:
            # Handle case when user sends only image without caption
            if event.photo and not event.text:
                await event.reply("⚠️ **PERINGATAN!**\n\nAnda hanya mengirim gambar tanpa caption.\n\nUntuk memproses data, silakan kirim gambar dengan caption yang berisi data lengkap sesuai format.\n\nKetik /format untuk melihat format yang benar.")
                return
            
            # Handle case when user sends only text without image
            if event.text and not event.photo:
                await event.reply("⚠️ **PERINGATAN!**\n\nAnda hanya mengirim teks tanpa gambar.\n\nUntuk memproses data, silakan kirim gambar dengan caption yang berisi data lengkap sesuai format.\n\nKetik /format untuk melihat format yang benar.")
                return
            
            # Semua pesan harus gambar + caption data
            if event.photo and event.text:
                match = pattern.search(event.text.strip())
                if match:
                    row = match.groupdict()
                    file_path = await event.download_media()
                    try:
                        file_link = upload_to_gdrive(file_path, creds_dict)
                    except Exception as e:
                        file_link = f"Gagal upload: {e}"
                    try:
                        # Check if link_gmaps is provided and extract coordinates
                        link_gmaps = row['link_gmaps'].strip()
                        location_coords = ""
                        
                        if link_gmaps and link_gmaps != "":
                            lat, lon = extract_coords_from_gmaps_link(link_gmaps)
                            if lat is not None and lon is not None:
                                location_coords = f"{lat},{lon}"
                                await event.reply(f"✅ Data dan gambar berhasil disimpan ke Google Spreadsheet.\n📍 Koordinat dari Link Gmaps: {lat}, {lon}")
                            else:
                                await event.reply("✅ Data dan gambar berhasil disimpan ke Google Spreadsheet.\n⚠️ Link Gmaps tidak dapat diproses. Silakan share lokasi untuk melengkapi data koordinat.")
                        else:
                            await event.reply("✅ Data dan gambar berhasil disimpan ke Google Spreadsheet.\n📍 Silakan share lokasi untuk melengkapi data koordinat.")
                        
                        # Get current timestamp
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        # Get the next row number (excluding header)
                        no = len(sheet.get_all_values())  # This counts all rows including header, so next row is len+1, but for display, len is enough
                        
                        # Kolom: timestamp, user_id, nama_sa, sto, cluster, usaha, pic, hpwa, internet, biaya, voc, lokasi, file_link, link_gmaps
                        sheet.append_row([
                            no, timestamp, str(event.sender_id), row['nama_sa'], row['sto'], row['cluster'], row['usaha'],
                            row['pic'], row['hpwa'], row['internet'], row['biaya'], row['voc'], location_coords, file_link, row['link_gmaps'], "Default"
                        ])
                    except Exception as e:
                        await event.reply(f"❌ Gagal menyimpan ke Google Spreadsheet: {e}")
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return
                else:
                    await event.reply("❌ Format caption tidak sesuai.\n\nKetik /format untuk melihat format yang benar.")
                    return

            # Handler share location (setelah data+gambar)
            if hasattr(event.message, "geo") and event.message.geo:
                latitude = event.message.geo.lat
                longitude = event.message.geo.long
                try:
                    user_id = str(event.sender_id)
                    # Define expected headers to avoid duplicate issues
                    expected_headers = [
                        'No', 'Timestamp', 'ID', 'Nama', 'STO', 'Cluster', 'Nama Usaha', 
                        'PIC', 'HP/WA', 'Internet Existing', 'Biaya Internet', 'VOC', 
                        'Lokasi', 'Foto', 'Link Gmaps', 'Validitas'
                    ]
                    records = sheet.get_all_records(expected_headers=expected_headers)
                    row_idx = None
                    for idx, row in enumerate(records, start=2):  # start=2 karena header di baris 1
                        if str(row.get('ID', '')) == user_id:
                            row_idx = idx
                    if row_idx:
                        # Update kolom lokasi (kolom ke-12) dengan "latitude,longitude"
                        sheet.update_cell(row_idx, 13, f"{latitude},{longitude}")
                        await event.reply(f"📍 Koordinat berhasil ditambahkan ke data terakhir:\n{latitude}, {longitude}")
                    else:
                        await event.reply("❌ Tidak ditemukan data sebelumnya untuk user ini. Kirim data dan gambar dulu.")
                except Exception as e:
                    await event.reply(f"❌ Gagal menyimpan lokasi ke Google Spreadsheet: {e}")
                return

    except Exception as e:
        await event.reply(f"❌ Terjadi error pada bot: {e}")

@client.on(events.NewMessage(pattern=r'^/format$', incoming=True))
async def format_handler(event):
    if event.is_private:
        format_text = (
            "#VISIT\n\n"
            "Nama SA/ AR: \n"
            "STO: \n"
            "Cluster:  \n\n"
            "Nama usaha: \n"
            "Nama PIC: \n"
            "Nomor HP/ WA:\n"
            "Internet existing:\n"
            "Biaya internet existing:\n"
            "Voice of Customer: \n"
            "Link Gmaps: "
        )
        await event.reply(format_text)

@client.on(events.NewMessage(pattern=r'^/start$', incoming=True))
async def start_handler(event):
    if event.is_private:
        await event.reply("Selamat datang di bot SGS! Berikut adalah langkah untuk mengisi data:\n\n"
                          "1. Kirim data dan gambar sesuai format\n"
                          "2. Share lokasi apabila tidak menyertakan Link Gmaps\n"
                          "3. Kirim pesan /format untuk melihat format yang benar\n")

if __name__ == "__main__":
    print("Bot is running...")
    try:
        client.run_until_disconnected()
    except Exception as e:
        print(f"Fatal error: {e}")