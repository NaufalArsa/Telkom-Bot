import os, re, json, gspread, requests
from oauth2client.service_account import ServiceAccountCredentials
from telethon import TelegramClient, events
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

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
    api_id = int(api_id_env)
except Exception as e:
    print(f"Error loading Telegram credentials: {e}")
    exit(1)

try:
    creds_json = get_env_var("GOOGLE_CREDS_JSON")
    creds_dict = json.loads(creds_json)
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    gc = gspread.authorize(creds)
    sheet = gc.open('Recap Visit').sheet1
except Exception as e:
    print(f"Error loading Google credentials or opening sheet: {e}")
    exit(1)

client = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

pattern = re.compile(r"""
    (?P<bulan>^[A-Za-z]+\s\d{4})\n+
    Nama\s+SA/\s*AR:\s*(?P<nama_sa>.+?)\n+
    Cluster:\s*(?P<cluster>.+?)\n+
    \n*
    Nama\s+usaha:\s*(?P<usaha>.+?)\n+
    Nama\s+PIC:\s*(?P<pic>.+?)\n+
    Nomor\s+HP/\s*WA:\s*(?P<hpwa>.+?)\n+
    Internet\s+existing:\s*(?P<internet>.+?)\n+
    Biaya\s+internet\s+existing:\s*(?P<biaya>.+?)\n+
    Voice\s+of\s+Customer:\s*(?P<voc>.+)
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

def upload_to_gdrive(file_path, creds_dict):
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)
    file_metadata = {'name': os.path.basename(file_path), 'parents': []}
    media = MediaFileUpload(file_path, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    service.permissions().create(fileId=file.get('id'), body={'role': 'reader', 'type': 'anyone'}).execute()
    file_link = f"https://drive.google.com/uc?id={file.get('id')}"
    return file_link

@client.on(events.NewMessage(incoming=True))
async def handler(event):
    try:
        if event.is_private:
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
                        # Kolom: user_id, bulan, nama_sa, cluster, usaha, pic, hpwa, internet, biaya, voc, lokasi, file_link
                        sheet.append_row([
                            str(event.sender_id), row['bulan'], row['nama_sa'], row['cluster'], row['usaha'],
                            row['pic'], row['hpwa'], row['internet'], row['biaya'], row['voc'], "", file_link
                        ])
                        await event.reply("✅ Data dan gambar berhasil disimpan ke Google Spreadsheet. Silakan share lokasi untuk melengkapi data.")
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
                address = get_address_from_coords(latitude, longitude)
                try:
                    user_id = str(event.sender_id)
                    records = sheet.get_all_records()
                    row_idx = None
                    for idx, row in enumerate(records, start=2):  # start=2 karena header di baris 1
                        if str(row.get('ID', '')) == user_id:
                            row_idx = idx
                    if row_idx:
                        # Update kolom lokasi (kolom ke-11)
                        sheet.update_cell(row_idx, 11, f"{latitude},{longitude}")
                        await event.reply(f"📍 Lokasi berhasil ditambahkan ke data terakhir:\n{latitude}, {longitude}")
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
            "#VISIT_SGS\n"
            "Juni 2025\n\n"
            "Nama SA/ AR: \n"
            "Cluster:  \n\n"
            "Nama usaha: \n"
            "Nama PIC: \n"
            "Nomor HP/ WA:\n"
            "Internet existing:\n"
            "Biaya internet existing:\n"
            "Voice of Customer: "
        )
        await event.reply(format_text)

if __name__ == "__main__":
    print("Bot is running...")
    try:
        client.run_until_disconnected()
    except Exception as e:
        print(f"Fatal error: {e}")