import logging
from services.google_sheets import GoogleSheetsService
from config import SHEET_NAME
import pandas as pd

logger = logging.getLogger(__name__)

class SummaryHandlers:
    def __init__(self):
        self.google_sheets_service = GoogleSheetsService()
        self.spreadsheet_name = SHEET_NAME

    def get_summary_dataframe(self):
        """
        Get summary data from Google Sheets
        """
        try:
            data = self.google_sheets_service.get_sheet_data_by_name(self.spreadsheet_name, "Survey")
            if data and len(data) > 1:
                headers = data[0]
                rows = data[1:]
                df = pd.DataFrame(rows, columns=headers)
                logger.info(f"Loaded {len(df)} rows from sheet: Survey")
                return df
            else:
                logger.warning("No data found in sheet: Survey")
                return None
        except Exception as e:
            logger.error(f"Error getting data from sheet Survey: {e}")
            return None

    def get_all_summary(self, target_visit=50):
        """
        Mengembalikan ringkasan visit HI dan MTD per SA dan STO dalam format tabel teks.
        """

        sa_list = {"Paramita", "Faruq", "Hafiz", "Wiwik", "Zainul", "Joko", "Randy", "Ifdan", "Aziz"}
        sto_list = {"BTU", "NTG", "KPO", "BLB", "SGS", "LWG", "PKS", "TMP"}

        df = self.get_summary_dataframe()
        if df is None:
            logger.error("Gagal mengambil data dari Google Sheets.")
            return "Gagal mengambil data summary."

        try:
            df['Created At'] = pd.to_datetime(df['Created At'], errors='coerce')
            today = pd.to_datetime("today").normalize()
            this_month = today.month
            this_year = today.year

            # Header Summary SA
            sa_summary = ["Nama SA | Jumlah Visit HI | Jumlah Visit MTD | Achieve MTD"]
            for sa in sorted(sa_list):
                df_sa = df[df['SA Name'] == sa]
                if df_sa.empty:
                    sa_summary.append(f"{sa} | 0 | 0 | 0%")
                    continue

                df_today = df_sa[df_sa['Created At'].dt.normalize() == today]
                df_mtd = df_sa[
                    (df_sa['Created At'].dt.month == this_month) &
                    (df_sa['Created At'].dt.year == this_year)
                ]
                jumlah_visit_hi = len(df_today)
                jumlah_visit_mtd = len(df_mtd)
                achievement = (jumlah_visit_mtd / target_visit) * 100 if target_visit > 0 else 0

                sa_summary.append(f"{sa} | {jumlah_visit_hi} | {jumlah_visit_mtd} | {achievement:.0f}%")

            # Header Summary STO
            sto_summary = ["\nSTO | Jumlah Visit HI | Jumlah Visit MTD"]
            for sto in sorted(sto_list):
                df_sto = df[df['STO'] == sto]
                if df_sto.empty:
                    sto_summary.append(f"{sto} | 0 | 0")
                    continue

                df_today = df_sto[df_sto['Created At'].dt.normalize() == today]
                df_mtd = df_sto[
                    (df_sto['Created At'].dt.month == this_month) &
                    (df_sto['Created At'].dt.year == this_year)
                ]
                jumlah_visit_hi = len(df_today)
                jumlah_visit_mtd = len(df_mtd)

                sto_summary.append(f"{sto} | {jumlah_visit_hi} | {jumlah_visit_mtd}")

            return "\n".join(sa_summary + sto_summary)

        except Exception as e:
            logger.error(f"Error processing all summary: {e}")
            return "Terjadi kesalahan saat memproses data summary keseluruhan."

    def get_today_summary_by_id(self, sa_id, target_visit=50):
        """
        Ambil ringkasan visit harian + MTD + achievement berdasarkan SA ID.
        Jumlah Visit HI dihitung berdasarkan jumlah entri (baris) di tanggal hari ini.
        """
        df = self.get_summary_dataframe()
        if df is None:
            logger.error("Gagal mengambil data dari Google Sheets.")
            return "Gagal mengambil data summary."

        try:
            df['Created At'] = pd.to_datetime(df['Created At'], errors='coerce')
            logger.info(f"Available columns: {df.columns.tolist()}")
            
            # Gunakan hari sebelumnya jika belum ada data hari ini
            today = pd.to_datetime("today").normalize()
            logger.info(f"Fetching summary for SA ID: {sa_id} on {today.strftime('%Y-%m-%d')}") 
            this_month = today.month
            this_year = today.year

            # Filter berdasarkan SA ID
            df_sa = df[df['SA ID'] == sa_id]

            if df_sa.empty:
                return f"ℹ️ Tidak ditemukan data dengan SA ID: {sa_id}"

            # Ambil nama SA dari baris terakhir
            sa_name = df_sa.iloc[-1].get("SA Name", "-")

            # Hitung jumlah visit HI = jumlah baris yang dibuat di tanggal `today`
            df_today = df_sa[df_sa['Created At'].dt.normalize() == today]
            jumlah_visit_hi = len(df_today)

            # Hitung jumlah visit MTD = jumlah baris di bulan dan tahun sekarang
            df_mtd = df_sa[
                (df_sa['Created At'].dt.month == this_month) &
                (df_sa['Created At'].dt.year == this_year)
            ]

            jumlah_visit_mtd = len(df_mtd)

            # Hitung achievement berdasarkan jumlah visit MTD
            achievement = (jumlah_visit_mtd / target_visit) * 100 if target_visit > 0 else 0
            today_date = today.strftime('%Y-%m-%d')

            result = (
                f"📅 Ringkasan Tanggal: {today_date}\n\n"
                f"👤 SA Name: {sa_name}\n"
                f"📅 Jumlah Visit HI: {jumlah_visit_hi}\n"
                f"📊 Jumlah Visit MTD: {jumlah_visit_mtd}\n"
                f"🏆 Achievement: {achievement:.2f}%"
            )
            return result

        except Exception as e:
            logger.error(f"Error processing summary for SA ID {sa_id}: {e}")
            return "Terjadi kesalahan saat memproses data summary."

    async def summary_sa_command_handler(self, event):
        """
        Handler untuk command /summary [SA_ID]
        """
        if not event.is_private:
            return
        text = event.text.strip()
        if len(text.split(" ", 1)) < 2:
            await event.reply("Silakan gunakan format: /summary [SA_ID]")
            return
        sa_id = text.split(" ", 1)[1].strip()
        summary = self.get_today_summary_by_id(sa_id)
        await event.reply(summary)    

    async def summary_all_command_handler(self, event):
        if not event.is_private:
            return
        summary = self.get_all_summary()
        await event.reply(summary)

    