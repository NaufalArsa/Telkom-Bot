import requests
import ast
import time
import logging
import re
from datetime import datetime
from dateutil import parser
import pytz
from services.google_sheets import GoogleSheetsService
# Import dotenv to load environment variables if needed
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file if it exists

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AutoFetchSurvey:
    def __init__(self, token, api_url, spreadsheet_name="Recap Visit YOVI", worksheet_name="Survey"):
        self.token = token
        self.api_url = api_url.rstrip('/')
        self.spreadsheet_name = spreadsheet_name
        self.worksheet_name = worksheet_name
        self.last_fetch_time = None

    def validate_token(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            response = requests.get(f"{self.api_url}/validate", headers=headers, timeout=5)
            if response.status_code == 401:
                logger.error("Token is invalid or expired")
                return False
            return True
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            return False

    def get_total_pages(self):
        """Get total pages by extracting page number from API response"""
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

    def fetch_latest_survey_data(self, count=50, witel_id=2):
        if not self.validate_token():
            return []

        page = self.get_total_pages()

        params = {
            "witel_id": witel_id,
            "per_page": count,
            "page": page,
            "order_by": "id"
        }

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Cache-Control": "no-cache"
        }

        try:
            logger.info(f"Fetching data from last page: {page}")
            response = requests.get(self.api_url, params=params, headers=headers, timeout=15)
            response.raise_for_status()

            data = response.json()
            return data.get("data", [])
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

                city_raw = rec.get('city', '').strip().upper()  # Adjust field name if needed
                if city_raw not in city_mapping:
                    continue  # Skip if city is not in mapping

                 # Convert created_at to Asia/Jakarta timezone
                created_at_raw = rec.get('created_at', '')
                try:
                    created_at_utc = parser.isoparse(created_at_raw)
                    created_at_wib = created_at_utc.astimezone(pytz.timezone('Asia/Jakarta'))
                    created_at_str = created_at_wib.strftime('%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    logger.warning(f"Gagal parse Created At untuk record {rec.get('id')}: {e}")
                    created_at_str = created_at_raw  # fallback

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


    def is_duplicate(self, new_row, existing_rows):
        comparison_fields = 'ID'
        for existing in existing_rows:
            if all(
                str(new_row.get(f, '')).strip().lower() ==
                str(existing.get(f, '')).strip().lower()
                for f in comparison_fields
            ):
                return True
        return False

    def save_to_sheet(self, rows):
        if not rows:
            return True

        try:
            existing_records = self.get_existing_records()
            new_rows = [row for row in rows if not self.is_duplicate(row, existing_records)]

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

    def fetch_all_survey_data(self, witel_id=2, per_page=50):
        """Fetch data from all pages sequentially"""
        if not self.validate_token():
            return []

        all_records = []
        current_page = 1
        total_pages = None

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }

        while True:
            params = {
                "witel_id": witel_id,
                "per_page": per_page,
                "page": current_page,
                "order_by": "id"
            }

            try:
                logger.info(f"Fetching page {current_page}")
                response = requests.get(
                    self.api_url,
                    params=params,
                    headers=headers,
                    timeout=15
                )
                response.raise_for_status()
                data = response.json()

                # Get records from current page
                page_records = data.get("data", [])
                all_records.extend(page_records)

                # Determine if we should continue
                if total_pages is None:
                    # Extract total pages from API response if available
                    last_url = data.get("links", {}).get("last", "")
                    match = re.search(r"page=(\d+)", last_url)
                    total_pages = int(match.group(1)) if match else 1

                current_page += 1
                if current_page > total_pages:
                    break

                # Small delay between requests to avoid rate limiting
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Error fetching page {current_page}: {str(e)}")
                break

        logger.info(f"Fetched {len(all_records)} records from {total_pages} pages")
        return all_records

    def run(self, interval=60):
        logger.info(f"Starting survey fetcher. Checking every {interval} seconds")
        while True:
            try:
                if not self.validate_token():
                    logger.error("Invalid API token.")
                    time.sleep(interval)
                    continue

                logger.info("Fetching new data...")
                records = self.fetch_all_survey_data()
                if not records:
                    logger.info("No records received")
                    time.sleep(interval)
                    continue

                rows = self.parse_survey_data(records)
                if not rows:
                    logger.info("No rows parsed")
                    time.sleep(interval)
                    continue

                self.save_to_sheet(rows)
                self.last_fetch_time = datetime.now()
                logger.info(f"Cycle completed at {self.last_fetch_time}")

            except KeyboardInterrupt:
                logger.info("Stopping...")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")

            time.sleep(interval)

def main():
    config = {
        "token": "42|C4CtzajB8kjNkpo76Z14wBTWSDIBV2SgW0Np9J0sbea387b4",
        "api_url": "https://smestr3.id/api/sales-agent-surveys",
        "spreadsheet_name": "Recap Visit YOVI",
        "worksheet_name": "Survey",
        "interval": 60,
    }

    fetcher = AutoFetchSurvey(
        token=config['token'],
        api_url=config['api_url'],
        spreadsheet_name=config['spreadsheet_name'],
        worksheet_name=config['worksheet_name']
    )

    fetcher.run(
        interval=config['interval']
    )

if __name__ == "__main__":
    main()
