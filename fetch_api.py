import requests
import ast
import logging
import re
from datetime import datetime
from dateutil import parser
import pytz
from services.google_sheets import GoogleSheetsService
from dotenv import load_dotenv
from config import API_TOKEN, API_URL, SHEET_NAME

load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)



class FetchAPI:
    def __init__(self, token, api_url, spreadsheet_name, worksheet_name="Survey"):
        self.token = token
        self.api_url = api_url.rstrip('/')
        self.spreadsheet_name = spreadsheet_name
        self.worksheet_name = worksheet_name
        self.last_fetch_time = None

    def validate_token(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            response = requests.get(f"{self.api_url}/validate", headers=headers, timeout=5)
            return response.status_code != 401
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            return False

    def get_total_pages(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            response = requests.get(self.api_url, headers=headers, params={"witel_id": 2, "page": 1, "per_page": 50}, timeout=5)
            response.raise_for_status()
            json_data = response.json()
            last_url = json_data.get("links", {}).get("last", "")
            match = re.search(r"page=(\d+)", last_url)
            return int(match.group(1)) if match else 1
        except Exception as e:
            logger.error(f"Error determining total pages: {str(e)}")
            return 1

    def fetch_latest_survey_data(self, count=50, witel_id=2, last_id=None):
        if not self.validate_token():
            return []
        
        page = self.get_total_pages()

        params = {
            "witel_id": witel_id,
            "per_page": count,
            "page": page,
            "sort_column": "id",
            "sort_direction": "asc"
        }

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Cache-Control": "no-cache"
        }

        try:
            logger.info(f"Fetching data from API: page={page}, count={count}, witel_id={witel_id}, last_id={last_id}")
            response = requests.get(self.api_url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            records = data.get("data", [])

            if last_id:
                records = [r for r in records if int(r.get("id", 0)) > int(last_id)]

            return records
        except Exception as e:
            logger.error(f"Fetch error: {str(e)}")
            return []

    def parse_survey_data(self, records):
        rows = []
        question_mapping = {
            'Nama usaha?': 'Nama Usaha',
            'Jenis usaha (ekosistem)?': 'Jenis Usaha',
            'Alamat usaha?': 'Alamat Usaha',
            'Nama PIC yang ditemui?': 'PIC',
            'Status PIC yang ditemui? (Owner / Karyawan)': 'Status PIC',
            'Nomor HP PIC yang ditemui?': 'HP/WA',
            'Layanan yang digunakan saat ini? (Indibiz / Kompetitor / Belum Berlangganan)?': 'Internet Existing',
            'Jenis layanan? (contoh Indibiz 50 Mbps / Biznet 150 Mbps / Icon+ 20 Mbps)': 'Kecepatan',
            'Harga layanan Solusi yang digunakan saat ini?': 'Biaya Internet Existing',
            'Biaya Maksimal untuk Internet (anggaran yang disediakan)?': 'Alokasi',
            'Hasil visit?': 'Voice of Customer'
        }

        city_mapping = {
            'KOTA MALANG': 'KOTA MALANG',
            'MALANG': 'MALANG',
            'KOTA BATU': 'KOTA BATU',
        }

        for rec in records:
            try:
                questions = self._safe_parse(rec.get('questions', '[]'))
                sales_agent = self._safe_parse(rec.get('sales_agent', '{}'))

                city_raw = rec.get('city', '').strip().upper()
                if city_raw not in city_mapping:
                    continue

                created_at_raw = rec.get('created_at', '')
                try:
                    created_at_utc = parser.isoparse(created_at_raw)
                    created_at_wib = created_at_utc.astimezone(pytz.timezone('Asia/Jakarta'))
                    created_at_str = created_at_wib.strftime('%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    logger.warning(f"Gagal parse Created At untuk record {rec.get('id')}: {e}")
                    created_at_str = created_at_raw

                row = {
                    'ID': rec.get('id', ''),
                    'Created At': created_at_str,
                    'SA ID': sales_agent.get('id', ''),
                    'SA Name': sales_agent.get('name', ''),
                    'SA Witel': 'JATIM BARAT',
                    'Longitude': rec.get('longitude', ''),
                    'Latitude': rec.get('latitude', ''),
                    'ODP Name': rec.get('odp_name', ''),
                    'STO': rec.get('sto', ''),
                    'City': city_mapping[city_raw],
                    'Photo': ''
                }

                for header in question_mapping.values():
                    row[header] = ''

                for q in questions:
                    question_text = q.get('question', '')
                    if question_text in question_mapping:
                        col_name = question_mapping[question_text]
                        row[col_name] = q.get('answer', '')

                rows.append(row)

            except Exception as e:
                logger.error(f"Error parsing record {rec.get('id', '?')}: {str(e)}")
                continue

        return rows

    def _safe_parse(self, json_input):
        if isinstance(json_input, (dict, list)):
            return json_input
        if isinstance(json_input, str):
            try:
                return ast.literal_eval(json_input)
            except Exception as e:
                logger.warning(f"Failed to parse JSON string: {e}")
        return {} if 'agent' in str(json_input).lower() else []

    def get_existing_records(self):
        try:
            sheets_service = GoogleSheetsService()
            worksheet = sheets_service.sheet.spreadsheet.worksheet(self.worksheet_name)
            values = worksheet.get_all_values()
            if len(values) <= 1:
                return []
            header = values[0]
            return [dict(zip(header, row)) for row in values[1:]]
        except Exception as e:
            logger.error(f"Error reading sheet: {str(e)}")
            return []

    def get_latest_id_from_sheet(self):
        try:
            records = self.get_existing_records()
            if not records:
                return None
            return records[-1].get("ID")
        except Exception as e:
            logger.error(f"Error getting latest ID: {str(e)}")
            return None

    def save_to_sheet(self, rows):
        if not rows:
            return True
        try:
            existing_records = self.get_existing_records()
            existing_ids = {r["ID"] for r in existing_records}
            new_rows = [r for r in rows if str(r["ID"]) not in existing_ids]

            if not new_rows:
                logger.info("No new records to save")
                return True

            sheets_service = GoogleSheetsService()
            worksheet = sheets_service.sheet.spreadsheet.worksheet(self.worksheet_name)
            header = worksheet.row_values(1)
            data_to_save = [[row.get(col, '') for col in header] for row in new_rows]

            worksheet.append_rows(data_to_save)
            logger.info(f"Saved {len(new_rows)} new records")
            return True

        except Exception as e:
            logger.error(f"Save failed: {str(e)}")
            return False

    def run(self):
        logger.info("Running single fetch cycle...")

        try:
            if not self.validate_token():
                logger.error("Invalid API token.")
                return

            latest_id = self.get_latest_id_from_sheet()
            logger.info(f"Latest ID in sheet: {latest_id}")

            records = self.fetch_latest_survey_data(last_id=latest_id)
            if not records:
                logger.info("No new records received")
                return

            rows = self.parse_survey_data(records)
            if not rows:
                logger.info("No rows parsed")
                return

            self.save_to_sheet(rows)
            self.last_fetch_time = datetime.now()
            logger.info(f"Cycle completed at {self.last_fetch_time}")

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")

def main():
    config = {
        "token": API_TOKEN,
        "api_url": API_URL,
        "spreadsheet_name": SHEET_NAME,
        "worksheet_name": "Survey"
    }

    fetcher = FetchAPI(
        token=config['token'],
        api_url=config['api_url'],
        spreadsheet_name=config['spreadsheet_name'],
        worksheet_name=config['worksheet_name']
    )

    fetcher.run()


if __name__ == "__main__":
    main()
