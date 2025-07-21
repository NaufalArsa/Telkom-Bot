import pandas as pd
from geopy.distance import geodesic
from services.google_sheets import GoogleSheetsService
import logging
from config import SHEET_NAME

logger = logging.getLogger(__name__)

class PotensiService:
    def __init__(self):
        self.google_sheets_service = GoogleSheetsService()
        # Use the same spreadsheet as the main service, but different sheets
        self.spreadsheet_name = SHEET_NAME

    def get_potensi_dataframe(self, kategori):
        # Get data from Google Sheets - same spreadsheet, different sheets
        # Sheet names: Hotel, Manufaktur, Tempat Wisata, Pergudangan, Cafe/Restaurant, Distributor
        if kategori.lower() == "semua":
            dfs = []
            for cat in ["Hotel", "Manufaktur", "Tempat Wisata", "Pergudangan", "Cafe/Restaurant", "Distributor"]:
                df = self.get_sheet_data(cat)
                if df is not None and not df.empty:
                    dfs.append(df)
            if dfs:
                return pd.concat(dfs, ignore_index=True)
            return None
        else:
            # Convert category name to sheet name format
            sheet_name = self.convert_category_to_sheet_name(kategori)
            return self.get_sheet_data(sheet_name)

    def convert_category_to_sheet_name(self, kategori):
        """Convert category name to Google Sheets tab name"""
        # Map category names to sheet names
        category_mapping = {
            "hotel": "Hotel",
            "manufaktur": "Manufaktur", 
            "tempat wisata": "Tempat Wisata",
            "Pergudangan": "Pergudangan",
            "cafe/restaurant": "Cafe/Restaurant",
            "cafe restaurant": "Cafe/Restaurant",
            "Distributor": "Distributor"
        }
        
        # Try exact match first
        if kategori.lower() in category_mapping:
            return category_mapping[kategori.lower()]
        
        # Try partial match
        for key, value in category_mapping.items():
            if key in kategori.lower():
                return value
        
        # Default: return as is (for exact sheet names)
        return kategori

    def get_sheet_data(self, sheet_name):
        """Get data from Google Sheets by sheet name"""
        try:
            # Get data from the specific sheet in the same spreadsheet
            data = self.google_sheets_service.get_sheet_data_by_name(self.spreadsheet_name, sheet_name)  # type: ignore
            
            if data and len(data) > 1:  # Has header + data
                # Convert to DataFrame
                headers = data[0]
                rows = data[1:]
                df = pd.DataFrame(rows, columns=headers)  # type: ignore
                logger.info(f"Successfully loaded {len(df)} rows from sheet: {sheet_name}")
                return df
            else:
                logger.warning(f"No data found in sheet: {sheet_name}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting data from sheet {sheet_name}: {e}")
            return None

    def find_nearest(self, df, user_lat, user_lon, n=5):
        user_location = (user_lat, user_lon)
        
        # Cek kolom koordinat yang tersedia
        lat_col = None
        lon_col = None
        
        # Coba berbagai kemungkinan nama kolom
        possible_lat_cols = ["lat", "latitude", "Lat", "Latitude"]
        possible_lon_cols = ["long", "longitude", "lon", "Long", "Longitude", "Lon"]
        
        for col in possible_lat_cols:
            if col in df.columns:
                lat_col = col
                break
                
        for col in possible_lon_cols:
            if col in df.columns:
                lon_col = col
                break
        
        if lat_col is None or lon_col is None:
            logger.error(f"Kolom koordinat tidak ditemukan. Kolom yang tersedia: {list(df.columns)}")
            return pd.DataFrame()  # Return empty DataFrame
        
        # Drop rows dengan koordinat yang kosong
        df = df.dropna(subset=[lat_col, lon_col])
        
        if df.empty:
            return df
        
        # Hitung jarak
        df["distance_m"] = df.apply(
            lambda row: geodesic(user_location, (row[lat_col], row[lon_col])).meters,
            axis=1
        )
        
        return df.sort_values(by="distance_m").head(n) 