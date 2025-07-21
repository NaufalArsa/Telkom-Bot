import logging
from telethon import events, Button
from services.potensi_service import PotensiService
from utils.location import extract_coords_from_gmaps_link

logger = logging.getLogger(__name__)

class PotensiHandlers:
    def __init__(self, client):
        self.client = client
        self.potensi_service = PotensiService()
        self.user_potensi_state = {}  # user_id: kategori

    async def process_potensi_search(self, event, kategori, user_lat, user_lon):
        try:
            await event.reply(f"🔎 Mencari 5 potensi terdekat untuk kategori: {kategori}...")
            
            df = self.potensi_service.get_potensi_dataframe(kategori)
            if df is None or df.empty:
                await event.reply(f"❌ Data potensi untuk kategori '{kategori}' tidak ditemukan.")
                return
            
            nearest = self.potensi_service.find_nearest(df, user_lat, user_lon, n=5)
            
            if nearest.empty:
                await event.reply(f"❌ Tidak ada data potensi '{kategori}' di sekitar lokasi Anda.")
                return
            
            # Cek kolom koordinat yang tersedia
            lat_col = None
            lon_col = None
            
            possible_lat_cols = ["lat", "latitude", "Lat", "Latitude"]
            possible_lon_cols = ["long", "longitude", "lon", "Long", "Longitude", "Lon"]
            
            for col in possible_lat_cols:
                if col in nearest.columns:
                    lat_col = col
                    break
                    
            for col in possible_lon_cols:
                if col in nearest.columns:
                    lon_col = col
                    break
            
            possible_nama_cols = ['Nama', 'nama', 'nama_instansi', 'NAMA', 'name']
            nama_col = next((col for col in possible_nama_cols if col in nearest.columns), None)

            msg = f"📍 **5 Potensi Terdekat - {kategori}**\n\n"
            for i, row in enumerate(nearest.itertuples(index=False), 1):
                # Use getattr for namedtuple, fallback to '-'
                nama = getattr(row, nama_col, '-') if nama_col else '-'
                lat = getattr(row, lat_col) # type: ignore
                lon = getattr(row, lon_col) # type: ignore
                dist = getattr(row, 'distance_m')
                
                # Convert lat/lon to float for formatting and maps link
                try:
                    lat_float = float(str(lat)) if lat else 0.0
                    lon_float = float(str(lon)) if lon else 0.0
                    maps_link = f"https://www.google.com/maps?q={lat_float},{lon_float}"
                except (ValueError, TypeError):
                    lat_float = 0.0
                    lon_float = 0.0
                    maps_link = "#"

                if dist < 1000:
                    distance_str = f"{dist:.0f} m"
                else:
                    distance_str = f"{dist/1000:.1f} km"

                msg += (
                    f"{i}. **{nama}**\n"
                    f"   📍 {lat_float:.6f}, {lon_float:.6f}\n"
                    f"   📏 Jarak: {distance_str}\n"
                    f"   🗺️ [Lihat di Maps]({maps_link})\n\n"
                )
            
            await event.reply(msg, parse_mode='markdown')
            
        except Exception as e:
            logger.error(f"Error in process_potensi_search: {e}")
            await event.reply(f"❌ Terjadi error saat mencari potensi: {e}")

    async def potensi_command_handler(self, event):
        """Handle /potensi command"""
        if event.is_private:
            categories = [
                "Hotel", "Perusahaan", "Tempat Wisata", "Industri", "Cafe/Restaurant", "Rumah Sakit", "Semua"
            ]
            # Satu tombol per baris (reply keyboard)
            buttons = [[Button.text(cat)] for cat in categories]
            await event.reply(
                "🏷️ **Pilih Kategori Potensi:**\n\nSetelah memilih kategori, silakan share lokasi Anda atau kirim link Google Maps untuk mencari 5 potensi terdekat.",
                buttons=buttons
            )

    async def handle_gmaps_link_with_potensi(self, event, user_id: str):
        """Handle Google Maps link with potensi state check"""
        if user_id in self.user_potensi_state:
            kategori = self.user_potensi_state[user_id]
            lat, lon = extract_coords_from_gmaps_link(event.text.strip())
            if lat is not None and lon is not None:
                await self.process_potensi_search(event, kategori, lat, lon)
                self.user_potensi_state.pop(user_id, None)
                return True
            else:
                await event.reply("❌ Link Google Maps tidak valid atau tidak mengandung koordinat.")
                return True
        return False

    async def handle_location_share_with_potensi(self, event, user_id: str):
        """Handle location share with potensi state check"""
        if user_id in self.user_potensi_state:
            kategori = self.user_potensi_state[user_id]
            user_lat = event.message.geo.lat
            user_lon = event.message.geo.long
            await self.process_potensi_search(event, kategori, user_lat, user_lon)
            self.user_potensi_state.pop(user_id, None)
            return True
        return False

    async def handle_category_selection(self, event, user_id: str):
        """Handle category selection for potensi"""
        text = event.text.strip()
        categories = [
            "Hotel", "Perusahaan", "Tempat Wisata", "Industri", "Cafe/Restaurant", "Rumah Sakit", "Semua"
        ]
        
        if text in categories:
            self.user_potensi_state[user_id] = text
            await event.reply("📍 Silakan share lokasi Anda atau kirim link Google Maps untuk mencari 5 potensi terdekat.")
            return True
        return False 