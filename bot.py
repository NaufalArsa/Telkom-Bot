import os, re, json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telethon import TelegramClient, events
from dotenv import load_dotenv
load_dotenv()

api_id = int(os.environ.get("API_ID"))
api_hash = os.environ.get("API_HASH")
bot_token = os.environ.get("BOT_TOKEN")

client = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

creds_json = os.environ.get("GOOGLE_CREDS_JSON")
if not creds_json:
    raise ValueError("GOOGLE_CREDS_JSON environment variable not set!")

creds_dict = json.loads(creds_json)
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(creds)
sheet = gc.open('Recap Visit').sheet1 

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

@client.on(events.NewMessage(incoming=True))
async def handler(event):
    if event.is_private and event.text:
        # Abaikan jika pesan adalah /format
        if event.text.strip().lower() == "/format":
            return
        match = pattern.search(event.text.strip())
        if match:
            row = match.groupdict()
            # Tambahkan data ke Google Sheet
            sheet.append_row([
                row['bulan'], row['nama_sa'], row['cluster'], row['usaha'],
                row['pic'], row['hpwa'], row['internet'], row['biaya'], row['voc']
            ])
            await event.reply("Data berhasil disimpan ke Google Spreadsheet.")
        else:
            await event.reply("Format pesan tidak sesuai.")

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
    client.run_until_disconnected()