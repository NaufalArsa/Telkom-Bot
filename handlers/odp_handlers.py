import logging
from typing import Dict
from geopy.distance import geodesic
from utils.location import extract_coords_from_gmaps_link
from services.supabase_service import SupabaseService

logger = logging.getLogger(__name__)

class ODPHandlers:
    def __init__(self):
        self.supabase_service = SupabaseService()
        self.odp_user_state = {}  # user_id: True jika sedang menunggu lokasi untuk /odp
    
    def format_odp_result(self, nearest_5):
        """Format ODP results for display"""
        msg = "\n=== 5 ODP Terdekat ===\n"
        for i, row in enumerate(nearest_5.itertuples(index=False), 1):
            odp = getattr(row, 'ODP')
            lat = getattr(row, 'LATITUDE')
            lon = getattr(row, 'LONGITUDE')
            dist = getattr(row, 'DISTANCE_KM')
            avai = getattr(row, 'AVAI') 
            dist_meter = dist * 1000
            odp_maps = f"https://www.google.com/maps?q={lat},{lon}"
            msg += (
                f"{i}. {odp} | {lat:.6f},{lon:.6f} | {dist_meter:.2f} m | "
                f"Port Tersedia: {avai} | [Lihat di Maps]({odp_maps})\n"
            )
        return msg
    
    async def process_odp_nearest(self, event, user_id, lat, lon):
        """Process ODP nearest search"""
        user_maps = f"https://www.google.com/maps?q={lat},{lon}"
        await event.reply(f"📍 Lokasi Anda: {lat:.6f}, {lon:.6f}\n🔗 [Lihat di Google Maps]({user_maps})\n\nSedang mencari 5 ODP terdekat ...", parse_mode='markdown')
        
        df = self.supabase_service.get_odp_dataframe()
        if df is None:
            await event.reply("❌ Gagal mengambil data ODP dari Supabase.")
            return
        
        if not all(col in df.columns for col in ["ODP", "LATITUDE", "LONGITUDE"]):
            await event.reply("❌ Data ODP tidak valid (kolom tidak lengkap).")
            return
        
        try:
            user_location = (lat, lon)
            # Pastikan kolom AVAI juga diambil jika ada, jika tidak, isi dengan 'N/A'
            columns_needed = ["ODP", "LATITUDE", "LONGITUDE"]
            if "AVAI" in df.columns:
                columns_needed.append("AVAI")
            else:
                df["AVAI"] = "N/A"
                columns_needed.append("AVAI")
            locations = df[columns_needed].dropna(subset=["ODP", "LATITUDE", "LONGITUDE"]) # type: ignore
            locations["DISTANCE_KM"] = locations.apply(
                lambda row: geodesic(user_location, (row["LATITUDE"], row["LONGITUDE"])) .km,
                axis=1
            )
            nearest_5 = locations.sort_values(by="DISTANCE_KM").head(5)  # type: ignore
            msg = self.format_odp_result(nearest_5)
            await event.reply(msg, parse_mode='markdown')
        except Exception as e:
            await event.reply(f"❌ Gagal menghitung jarak ODP: {e}")
    
    async def odp_command_handler(self, event):
        """Handle /odp command"""
        if event.is_private:
            user_id = str(event.sender_id)
            self.odp_user_state[user_id] = True
            await event.reply("Silakan kirim link Google Maps atau share lokasi Anda untuk mencari ODP terdekat.")
    
    async def handle_gmaps_link_with_odp(self, event, user_id: str):
        """Handle Google Maps link with ODP state check"""
        lat, lon = extract_coords_from_gmaps_link(event.text.strip())
        if self.odp_user_state.get(user_id):
            await self.process_odp_nearest(event, user_id, lat, lon)
            self.odp_user_state[user_id] = False
            return True
        return False
    
    async def handle_location_share_with_odp(self, event, user_id: str):
        """Handle location share with ODP state check"""
        latitude = event.message.geo.lat
        longitude = event.message.geo.long
        if self.odp_user_state.get(user_id):
            await self.process_odp_nearest(event, user_id, latitude, longitude)
            self.odp_user_state[user_id] = False
            return True
        return False 