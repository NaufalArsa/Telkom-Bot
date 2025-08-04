import requests
import logging
import re
import pandas as pd
from geopy.distance import geodesic
from datetime import datetime
from services.google_sheets import GoogleSheetsService
from handlers.odp_handlers import ODPHandlers
from config import SHEET_NAME

# Setup logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class KDMPHandler:
    def __init__(self):
        self.google_sheets_service = GoogleSheetsService()
        self.odp_handler = ODPHandlers()  # Use existing ODP handler
        self.spreadsheet_name = SHEET_NAME

    def _find_coord_column(self, headers, keyword):
        """Find coordinate column by keyword"""
        for h in headers:
            norm = h.strip().lower().replace(" ", "")
            if keyword in norm:
                return h
        return None

    def _clean_coordinate(self, value):
        """Convert coordinate value to float, handling errors and special cases."""
        if pd.isna(value) or value == '' or str(value).strip().upper() in ['#N/A', 'N/A', 'NA']:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def get_odp_dataframe(self):
        """
        Get ODP data using the existing ODP handler for consistency
        """
        return self.odp_handler.get_odp_dataframe()

    def fetch_kdmp_data(self):
        """
        Ambil data KDMP dari Google Sheets dan konversi ke DataFrame.
        """
        try:
            data = self.google_sheets_service.get_sheet_data_by_name(self.spreadsheet_name, "KDMP")
            if data and len(data) > 1:
                headers = data[0]
                rows = data[1:]
                df = pd.DataFrame(rows, columns=headers)

                lat_col = self._find_coord_column(headers, "latitude")
                lon_col = self._find_coord_column(headers, "longitude")

                if lat_col and lon_col:
                    # Clean coordinate data
                    df['Latitude'] = df[lat_col].apply(self._clean_coordinate)
                    df['Longitude'] = df[lon_col].apply(self._clean_coordinate)
                else:
                    logger.warning("Kolom Latitude atau Longitude tidak ditemukan di KDMP.")
                logger.info(f"Loaded {len(df)} rows from sheet: KDMP")
                return df
            else:
                logger.warning("Tidak ada data di sheet: KDMP")
                return None
        except Exception as e:
            logger.error(f"Error getting data from sheet KDMP: {e}")
            return None

    def find_nearest_odp_for_location(self, lat, lon, df_odp):
        """
        Find nearest ODP for a given location using the same logic as ODP handler
        """
        try:
            user_location = (lat, lon)
            
            # Ensure required columns exist
            if not all(col in df_odp.columns for col in ["ODP", "LATITUDE", "LONGITUDE"]):
                logger.error("ODP data tidak valid (kolom tidak lengkap).")
                return "ODP Tidak Diketahui", float('inf')
            
            # Add AVAI column if not present
            if "AVAI" not in df_odp.columns:
                df_odp["AVAI"] = "N/A"
            
            # Filter valid locations
            locations = df_odp[["ODP", "LATITUDE", "LONGITUDE", "AVAI"]].dropna(subset=["ODP", "LATITUDE", "LONGITUDE"])
            
            if locations.empty:
                return "ODP Tidak Diketahui", float('inf')
            
            # Convert lat/lon to float for distance calculation
            locations["LATITUDE"] = pd.to_numeric(locations["LATITUDE"], errors='coerce')
            locations["LONGITUDE"] = pd.to_numeric(locations["LONGITUDE"], errors='coerce')
            
            # Remove rows with invalid coordinates
            locations = locations.dropna(subset=["LATITUDE", "LONGITUDE"])
            
            if locations.empty:
                return "ODP Tidak Diketahui", float('inf')
            
            # Calculate distances
            locations["DISTANCE_KM"] = locations.apply(
                lambda row: geodesic(user_location, (row["LATITUDE"], row["LONGITUDE"])).km,
                axis=1
            )
            
            # Find nearest ODP
            nearest = locations.sort_values(by="DISTANCE_KM").iloc[0]
            return nearest["ODP"], nearest["DISTANCE_KM"]
            
        except Exception as e:
            logger.error(f"Error finding nearest ODP: {e}")
            return "ODP Tidak Diketahui", float('inf')

    def assign_nearest_odp(self):
        """
        Hitung dan simpan ODP terdekat untuk setiap baris KDMP menggunakan logic dari ODP handler.
        """
        logger.info("🚀 Memulai proses pencarian ODP terdekat untuk KDMP...")
        
        # Fetch data
        df_kdmp = self.fetch_kdmp_data()
        df_odp = self.get_odp_dataframe()

        if df_kdmp is None:
            logger.error("Data KDMP tidak tersedia.")
            return "❌ Gagal mengambil data KDMP."
            
        if df_odp is None:
            logger.error("Data ODP tidak tersedia.")
            return "❌ Gagal mengambil data ODP."

        logger.info(f"📊 Memproses {len(df_kdmp)} baris KDMP dengan {len(df_odp)} data ODP")
        
        # Prepare results
        nearest_odps = []
        nearest_distances = []
        processed_count = 0

        for idx, kdmp_row in df_kdmp.iterrows():
            lat_kdmp = kdmp_row.get('Latitude')
            lon_kdmp = kdmp_row.get('Longitude')

            if pd.isna(lat_kdmp) or pd.isna(lon_kdmp) or lat_kdmp is None or lon_kdmp is None:
                nearest_odps.append("Koordinat Tidak Lengkap")
                nearest_distances.append("")
                logger.warning(f"⚠️ Baris {idx + 1}: Koordinat tidak lengkap")
                continue

            try:
                # Use the integrated method to find nearest ODP
                nearest_odp, distance = self.find_nearest_odp_for_location(lat_kdmp, lon_kdmp, df_odp.copy())
                
                nearest_odps.append(nearest_odp)
                if distance == float('inf'):
                    nearest_distances.append("")
                else:
                    nearest_distances.append(round(distance, 2))
                
                processed_count += 1
                if processed_count % 10 == 0:
                    logger.info(f"📍 Diproses: {processed_count}/{len(df_kdmp)} lokasi KDMP")
                    
            except Exception as e:
                logger.error(f"❌ Error processing row {idx + 1}: {e}")
                nearest_odps.append("Error")
                nearest_distances.append("")

        # Add results to dataframe
        df_kdmp['ODP'] = nearest_odps
        df_kdmp['Jarak ODP (km)'] = nearest_distances

        logger.info(f"✅ Selesai memproses {processed_count} lokasi KDMP")

        # Update Google Sheet
        try:
            logger.info("💾 Menyimpan hasil ke Google Sheet...")
            updated_rows = [df_kdmp.columns.tolist()] + df_kdmp.values.tolist()
            success = self.google_sheets_service.update_sheet_by_name(self.spreadsheet_name, "KDMP", updated_rows)
            
            if success:
                logger.info("✅ Berhasil menyimpan ODP terdekat ke sheet KDMP.")
                return f"✅ Berhasil menyimpan {processed_count} ODP terdekat ke KDMP."
            else:
                logger.error("❌ Gagal menyimpan data ke Google Sheet.")
                return "❌ Gagal menyimpan data ke Google Sheet."
                
        except Exception as e:
            logger.error(f"❌ Gagal menyimpan data ke Google Sheet: {e}")
            return f"❌ Gagal menyimpan data ke Google Sheet: {e}"

    def main(self):
        """
        Fungsi utama untuk menjalankan proses.
        """
        result = self.assign_nearest_odp()
        print(result)
        return result


if __name__ == "__main__":
    handler = KDMPHandler()
    handler.main()