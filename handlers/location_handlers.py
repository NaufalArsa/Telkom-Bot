import os
import logging
from typing import Dict
from utils.validation import CAPTION_PATTERN, validate_caption_data, extract_markdown_link
from utils.location import extract_coords_from_gmaps_link, process_coordinates
from services.supabase_service import SupabaseService
from services.google_sheets import GoogleSheetsService

logger = logging.getLogger(__name__)

class LocationHandlers:
    def __init__(self):
        self.supabase_service = SupabaseService()
        self.sheets_service = GoogleSheetsService()
    
    async def handle_gmaps_link(self, event, user_id: str, pending_data: Dict):
        """Handle Google Maps link messages"""
        if user_id not in pending_data:
            await event.reply("❌ Tidak ada data sementara.\n\nSilakan kirim data terlebih dahulu.")
            return
        
        pending = pending_data[user_id]
        data_type = pending.get('type', 'unknown')
        link_gmaps = event.text.strip()
        lat, lon = extract_coords_from_gmaps_link(link_gmaps)
        
        if lat is None or lon is None:
            await event.reply("❌ Link Google Maps tidak valid.\n\nSilakan kirim Link Google Maps yang valid atau share lokasi.")
            return
        
        # Process based on data type
        if data_type == 'complete':
            await self.process_complete_data_with_coords(event, pending, user_id, lat, lon, link_gmaps, pending_data)
        elif data_type == 'caption_only':
            await self.process_caption_only_with_coords(event, pending, user_id, lat, lon, link_gmaps, pending_data)
        elif data_type == 'photo_only':
            await event.reply("❌ Data belum lengkap.\n\nSilakan kirim caption terlebih dahulu.")
        else:
            await self.process_other_data_with_coords(event, pending, user_id, lat, lon, link_gmaps, pending_data)
    
    async def handle_location_share(self, event, user_id: str, pending_data: Dict):
        """Handle location sharing"""
        try:
            latitude = event.message.geo.lat
            longitude = event.message.geo.long
            
            if user_id in pending_data:
                pending = pending_data[user_id]
                data_type = pending.get('type', 'unknown')
                
                if data_type == 'complete':
                    await self.process_complete_data_with_coords(event, pending, user_id, latitude, longitude, "", pending_data)
                elif data_type == 'caption_only':
                    await self.process_caption_only_with_coords(event, pending, user_id, latitude, longitude, "", pending_data)
                elif data_type == 'photo_only':
                    await event.reply("❌ Data belum lengkap.\n\nSilakan kirim caption terlebih dahulu.")
                else:
                    await self.process_other_data_with_coords(event, pending, user_id, latitude, longitude, "", pending_data)
            else:
                # Update existing data in spreadsheet
                if self.sheets_service.update_location_in_spreadsheet(user_id, latitude, longitude):
                    await event.reply(f"✅ **Koordinat berhasil ditambahkan!**\n\n📍 Lokasi: {latitude}, {longitude}\n📊 Data telah dilengkapi dengan koordinat")
                else:
                    await event.reply("❌ **Tidak dapat menambahkan koordinat!**\n\nTidak ditemukan data sebelumnya untuk user ini.\n\n📋 **Langkah yang benar:**\n1. Kirim data dengan Link Google Maps yang valid, ATAU\n2. Kirim data tanpa Link Gmaps, kemudian share lokasi")
        except Exception as e:
            logger.error(f"Error in handle_location_share: {e}")
            await event.reply("❌ Terjadi error saat memproses lokasi. Silakan coba lagi.")
    
    async def process_complete_data_with_coords(self, event, pending: Dict, user_id: str, lat: float, lon: float, link_gmaps: str, pending_data: Dict):
        """Process complete data with coordinates"""
        try:
            caption_text = pending['data']
            match = CAPTION_PATTERN.search(caption_text)
            if not match:
                await event.reply("❌ Format caption tidak sesuai.\n\nKetik /format untuk melihat format yang benar.")
                return
            
            row = match.groupdict()
            is_valid, missing_fields, error_message = validate_caption_data(row)
            if not is_valid:
                await event.reply(error_message)
                return
            
            file_path = pending['file_path']
            
            try:
                file_link = self.supabase_service.upload_file(file_path)
            except Exception as e:
                logger.warning(f"Supabase upload failed, continuing without upload: {e}")
                file_link = "Foto tersimpan"
                
            location_coords, gmaps_link = process_coordinates(lat, lon)
            
            if self.sheets_service.save_to_spreadsheet(row, user_id, location_coords, file_link, gmaps_link):
                self._cleanup_pending_data(user_id, pending_data)
                if os.path.exists(file_path):
                    os.remove(file_path)
                await event.reply(f"✅ **SELAMAT Data berhasil disimpan ke spreadsheet!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data lengkap telah ditambahkan\n\n🎉 **Status:** Data selesai diproses")
            else:
                await event.reply("❌ Gagal menyimpan ke Google Spreadsheet")
        except Exception as e:
            logger.error(f"Error in process_complete_data_with_coords: {e}")
            await event.reply("❌ Terjadi error saat memproses data. Silakan coba lagi.")
    
    async def process_caption_only_with_coords(self, event, pending: Dict, user_id: str, lat: float, lon: float, link_gmaps: str, pending_data: Dict):
        """Process caption-only data with coordinates"""
        try:
            caption_text = pending['data']
            match = CAPTION_PATTERN.search(caption_text)
            if not match:
                await event.reply("❌ Format caption tidak sesuai.\n\nKetik /format untuk melihat format yang benar.")
                return
            
            row = match.groupdict()
            is_valid, missing_fields, error_message = validate_caption_data(row)
            if not is_valid:
                await event.reply(error_message)
                return
            
            location_coords, gmaps_link = process_coordinates(lat, lon)
            
            if self.sheets_service.save_to_spreadsheet(row, user_id, location_coords, "Tidak ada foto", gmaps_link):
                self._cleanup_pending_data(user_id, pending_data)
                await event.reply(f"✅ **SELAMAT Data berhasil disimpan ke spreadsheet!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data telah ditambahkan (tanpa foto)\n\n🎉 **Status:** Data selesai diproses")
            else:
                await event.reply("❌ Gagal menyimpan ke Google Spreadsheet")
        except Exception as e:
            logger.error(f"Error in process_caption_only_with_coords: {e}")
            await event.reply("❌ Terjadi error saat memproses data. Silakan coba lagi.")
    
    async def process_other_data_with_coords(self, event, pending: Dict, user_id: str, lat: float, lon: float, link_gmaps: str, pending_data: Dict):
        """Process other data types with coordinates"""
        try:
            if 'data' not in pending or not pending['data']:
                await event.reply("❌ Data tidak lengkap.\n\nSilakan kirim foto dan caption terlebih dahulu.")
                return
            
            if isinstance(pending['data'], dict):
                row = pending['data']
                is_valid, missing_fields, error_message = validate_caption_data(row)
                if not is_valid:
                    await event.reply(error_message)
                    return
                
                file_path = pending.get('file_path')
                file_link = pending.get('file_link', 'Gagal upload')
                
                # Try to upload if we have a file path
                if file_path and os.path.exists(file_path):
                    try:
                        file_link = self.supabase_service.upload_file(file_path)
                    except Exception as e:
                        logger.warning(f"Supabase upload failed, continuing without upload: {e}")
                        file_link = "Foto tersimpan"
                
                location_coords, gmaps_link = process_coordinates(lat, lon)
                
                if self.sheets_service.save_to_spreadsheet(row, user_id, location_coords, file_link, gmaps_link):
                    self._cleanup_pending_data(user_id, pending_data)
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                    await event.reply(f"✅ **SELAMAT Data berhasil disimpan ke spreadsheet!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data lengkap telah ditambahkan\n\n🎉 **Status:** Data selesai diproses")
                else:
                    await event.reply("❌ Gagal menyimpan ke Google Spreadsheet")
            else:
                await event.reply("❌ Format data tidak sesuai.\n\nSilakan kirim ulang data dengan format yang benar.")
        except Exception as e:
            logger.error(f"Error in process_other_data_with_coords: {e}")
            await event.reply("❌ Terjadi error saat memproses data. Silakan coba lagi.")
    
    def _cleanup_pending_data(self, user_id: str, pending_data: Dict):
        """Clean up pending data and temporary files for a user"""
        if user_id in pending_data:
            old_file_path = pending_data[user_id].get('file_path')
            if old_file_path and os.path.exists(old_file_path):
                try:
                    os.remove(old_file_path)
                    logger.info(f"Cleaned up temporary file: {old_file_path}")
                except Exception as e:
                    logger.error(f"Failed to remove temporary file: {e}")
            del pending_data[user_id] 