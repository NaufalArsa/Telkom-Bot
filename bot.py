import os
import re
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telethon import TelegramClient, events
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

client = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

@client.on(events.NewMessage(incoming=True))
async def handler(event):
    try:
        if event.is_private and event.text:
            # Abaikan jika pesan adalah /format
            if event.text.strip().lower() == "/format":
                return
            match = pattern.search(event.text.strip())
            if match:
                row = match.groupdict()
                try:
                    sheet.append_row([
                        row['bulan'], row['nama_sa'], row['cluster'], row['usaha'],
                        row['pic'], row['hpwa'], row['internet'], row['biaya'], row['voc']
                    ])
                    await event.reply("✅ Data berhasil disimpan ke Google Spreadsheet.")
                except Exception as e:
                    await event.reply(f"❌ Gagal menyimpan ke Google Spreadsheet: {e}")
            else:
                await event.reply("❌ Format pesan tidak sesuai.\n\nKetik /format untuk melihat format yang benar.")
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