import gspread
import logging
from typing import Dict
from oauth2client.service_account import ServiceAccountCredentials
from config import SHEET_NAME, load_google_credentials
from timezone_utils import format_timestamp

logger = logging.getLogger(__name__)

class GoogleSheetsService:
    def __init__(self):
        self.sheet = None
        self._initialize_sheet()
    
    def _initialize_sheet(self):
        """Initialize Google Sheets connection"""
        try:
            creds_dict, scope = load_google_credentials()
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)  # type: ignore
            gc = gspread.authorize(creds)  # type: ignore
            self.sheet = gc.open(SHEET_NAME).sheet1  # type: ignore
            logger.info("Google Sheets service initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Google Sheets: {e}")
            # Fallback to file-based credentials
            try:
                CREDENTIALS_FILE = 'gcredentials.json'
                gc = gspread.service_account(filename=CREDENTIALS_FILE)
                self.sheet = gc.open(SHEET_NAME).sheet1  # type: ignore
                logger.info("✅ Using file-based credentials as fallback")
            except Exception as e2:
                logger.error(f"Error loading fallback credentials: {e2}")
                raise
    
    def save_to_spreadsheet(self, data: Dict[str, str], user_id: str, coords: str, file_link: str, gmaps_link: str = "") -> bool:
        """Save data to spreadsheet with error handling"""
        if not self.sheet:
            logger.error("Google Sheets not available")
            return False
        
        try:
            timestamp = format_timestamp()
            no = len(self.sheet.get_all_values())
            
            row_data = [
                no, timestamp, user_id, data['nama_sa'], data['sto'], data['cluster'], data['usaha'],
                data['pic'], data['hpwa'], data['internet'], data['biaya'], data['voc'], 
                coords, file_link, gmaps_link, "Default"
            ]
            
            self.sheet.append_row(row_data)
            logger.info(f"Successfully saved data for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save to spreadsheet: {e}")
            return False
    
    def update_location_in_spreadsheet(self, user_id: str, latitude: float, longitude: float) -> bool:
        """Update location coordinates for existing user data"""
        try:
            expected_headers = [
                'No', 'Timestamp', 'ID', 'Nama', 'STO', 'Cluster', 'Nama Usaha', 
                'PIC', 'HP/WA', 'Internet Existing', 'Biaya Internet', 'VOC', 
                'Lokasi', 'Foto', 'Link Gmaps', 'Validitas'
            ]
            records = self.sheet.get_all_records(expected_headers=expected_headers)  # type: ignore
            row_idx = None
            for idx, row in enumerate(records, start=2):
                if str(row.get('ID', '')) == user_id:
                    row_idx = idx
                    break
            
            if row_idx:
                from utils.location import process_coordinates
                location_coords, gmaps_link = process_coordinates(latitude, longitude)
                self.sheet.update_cell(row_idx, 13, location_coords)  # type: ignore
                self.sheet.update_cell(row_idx, 15, gmaps_link)  # type: ignore
                logger.info(f"Successfully updated location for user {user_id}")
                return True
            else:
                logger.warning(f"No existing data found for user {user_id}")
                return False
        except Exception as e:
            logger.error(f"Failed to update location in spreadsheet: {e}")
            return False 

    def get_sheet_data(self, spreadsheet_id: str, sheet_name: str):
        """Get data from a specific sheet in a Google Spreadsheet"""
        try:
            # Get credentials
            creds_dict, scope = load_google_credentials()
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)  # type: ignore
            gc = gspread.authorize(creds)  # type: ignore
            
            # Open the spreadsheet and get the specific sheet
            spreadsheet = gc.open_by_key(spreadsheet_id)  # type: ignore
            worksheet = spreadsheet.worksheet(sheet_name)  # type: ignore
            
            # Get all data from the sheet
            data = worksheet.get_all_values()
            return data
            
        except Exception as e:
            logger.error(f"Error getting data from sheet {sheet_name}: {e}")
            return None

    def get_sheet_data_by_name(self, spreadsheet_name: str, sheet_name: str):
        """Get data from a specific sheet by name within the same spreadsheet"""
        try:
            # Get credentials
            creds_dict, scope = load_google_credentials()
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)  # type: ignore
            gc = gspread.authorize(creds)  # type: ignore
            
            # Open the spreadsheet by name and get the specific sheet
            spreadsheet = gc.open(spreadsheet_name)  # type: ignore
            worksheet = spreadsheet.worksheet(sheet_name)  # type: ignore
            
            # Get all data from the sheet
            data = worksheet.get_all_values()
            return data
            
        except Exception as e:
            logger.error(f"Error getting data from sheet {sheet_name} in {spreadsheet_name}: {e}")
            return None 