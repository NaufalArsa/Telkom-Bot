import logging
from services.google_sheets import GoogleSheetsService
from config import SHEET_NAME
import pandas as pd

logger = logging.getLogger(__name__)

class PSBHandlers:
    def __init__(self, client):
        self.client = client
        self.google_sheets_service = GoogleSheetsService()
        self.spreadsheet_name = SHEET_NAME

    def get_psb_dataframe(self):
        try:
            data = self.google_sheets_service.get_sheet_data_by_name(self.spreadsheet_name, "PSB")
            if data and len(data) > 1:
                headers = data[0]
                rows = data[1:]
                df = pd.DataFrame(rows, columns=headers)  # type: ignore
                logger.info(f"Successfully loaded {len(df)} rows from sheet: PSB")
                return df
            else:
                logger.warning("No data found in sheet: PSB")
                return None
        except Exception as e:
            logger.error(f"Error getting data from sheet PSB: {e}")
            return None

    def search_by_customer_name(self, df, customer_name):
        # Case-insensitive search, exact or partial match
        if "CUSTOMER NAME" not in df.columns:
            return None
        matches = df[df["CUSTOMER NAME"].str.contains(customer_name, case=False, na=False)]
        return matches

    def format_psb_result(self, row):
        main_fields = [
            "CUSTOMER NAME", "STO", "NOMOR INTERNET", "PROVIDER", 
            "ALAMAT", "PAKET", "CHANNEL", "TGL PS"
        ]
        field_emojis = {
            "CUSTOMER NAME": "👤",
            "STO": "🏢",
            "NOMOR INTERNET": "💡",
            "PROVIDER": "🌐",
            "ALAMAT": "📍",
            "PAKET": "📦",
            "CHANNEL": "📡",
            "TGL PS": "📅"
        }
        msg = (
            "<b>📄 Hasil Pencarian PSB</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        for field in main_fields:
            val = row.get(field, "-")
            emoji = field_emojis.get(field, "•")
            display_name = field.title().replace("_", " ")
            if field == "CUSTOMER NAME":
                msg += f"{emoji} <b>{val}</b>\n"
            else:
                msg += f"{emoji} <b>{display_name}</b>: {val}\n"
        other_fields = [col for col in row.index if col not in main_fields]
        if other_fields:
            msg += "\n<b>📌 Detail Tambahan:</b>\n"
            for col in other_fields:
                val = row.get(col, "-")
                display_name = col.title().replace("_", " ")
                msg += f"• <b>{display_name}</b>: {val}\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━"
        return msg

    async def psb_command_handler(self, event):
        if not event.is_private:
            return
        text = event.text.strip()
        if len(text.split(" ", 1)) < 2:
            await event.reply("Silakan gunakan format: /psb [CUSTOMER NAME]")
            return
        customer_name = text.split(" ", 1)[1].strip()
        df = self.get_psb_dataframe()
        if df is None or df.empty:
            await event.reply("❌ Data PSB tidak ditemukan.")
            return
        matches = self.search_by_customer_name(df, customer_name)
        if matches is None or matches.empty:
            await event.reply(f"❌ Tidak ada data PSB untuk nama: {customer_name}")
            return
        for _, row in matches.head(5).iterrows():
            msg = self.format_psb_result(row)
            await event.reply(msg, parse_mode="html") 