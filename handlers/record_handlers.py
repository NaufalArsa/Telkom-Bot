import logging
from services.google_sheets import GoogleSheetsService
from config import SHEET_NAME
import pandas as pd

logger = logging.getLogger(__name__)

# RecordHandlers class to handle record-related operations
class RecordHandlers:
    def __init__(self):
        self.google_sheets_service = GoogleSheetsService()
        self.spreadsheet_name = SHEET_NAME

    # Method to get record data from Google Sheets
    def get_record_dataframe(self):
        try:
            data = self.google_sheets_service.get_sheet_data_by_name(self.spreadsheet_name, "Rekap")
            if data and len(data) > 1:
                headers = data[0]
                rows = data[1:]
                df = pd.DataFrame(rows, columns=headers)
                logger.info(f"Loaded {len(df)} rows from sheet: Rekap")
                return df
            else:
                logger.warning("No data found in sheet: Rekap")
                return None
        except Exception as e:
            logger.error(f"Error getting data from sheet Rekap: {e}")
            return None

    # Method to search records by Telegram ID
    def search_by_telegram_id(self, df, telegram_id):
        # Cari kolom Telegram ID
        id_cols = [col for col in df.columns if col.strip().lower() in ["id"]]
        if not id_cols:
            return None
        id_col = id_cols[0]
        matches = df[df[id_col] == str(telegram_id)]
        return matches

    # Method to format record result for display
    def format_record_result(self, row, idx):
        # Kolom yang ingin ditampilkan
        main_fields = ["No", "Nama Usaha", "PIC", "Timestamp"]
        msg = f"<b>{idx}. Riwayat Input</b>\n"
        for field in main_fields:
            val = row.get(field, "-")
            msg += f"<b>{field}</b>: {val}\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
        return msg

    # Command handler for /record
    async def record_command_handler(self, event):
        if not event.is_private:
            return
        user_id = str(event.sender_id)
        df = self.get_record_dataframe()
        if df is None or df.empty:
            await event.reply("❌ Data riwayat tidak ditemukan.")
            return
        matches = self.search_by_telegram_id(df, user_id)
        if matches is None or matches.empty:
            await event.reply("📭 Anda belum memiliki riwayat input.")
            return
        msg = "<b>📋 Riwayat Input Anda:</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
        for idx, (_, row) in enumerate(matches.iterrows(), 1):
            msg += self.format_record_result(row, idx)
        await event.reply(msg, parse_mode="html")