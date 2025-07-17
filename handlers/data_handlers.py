import os
import logging
from typing import Dict
from utils.validation import CAPTION_PATTERN, validate_caption_data, extract_markdown_link
from utils.location import extract_coords_from_gmaps_link, process_coordinates
from services.supabase_service import SupabaseService
from services.google_sheets import GoogleSheetsService
from timezone_utils import format_timestamp

logger = logging.getLogger(__name__)

class DataHandlers:
    def __init__(self):
        self.supabase_service = SupabaseService()
        self.sheets_service = GoogleSheetsService()
    
    def cleanup_pending_data(self, user_id: str, pending_data: Dict):
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
    
    async def handle_photo_only(self, event, user_id: str, pending_data: Dict):
        """Handle photo-only messages"""
        try:
            file_path = await event.download_media()
            
            # Check if there's existing caption data
            if user_id in pending_data and pending_data[user_id].get('type') == 'caption_only':
                caption_text = pending_data[user_id]['data']
                match = CAPTION_PATTERN.search(caption_text)
                if match:
                    row = match.groupdict()
                    
                    # Validate data
                    is_valid, missing_fields, error_message = validate_caption_data(row)
                    if not is_valid:
                        await event.reply(error_message)
                        return
                    
                    # Check for Google Maps link
                    link_gmaps = row.get('link_gmaps', '').strip()
                    has_valid_coordinates = False
                    lat, lon = None, None
                    
                    if link_gmaps:
                        link_gmaps = extract_markdown_link(link_gmaps)
                        lat, lon = extract_coords_from_gmaps_link(link_gmaps)
                        if lat is not None and lon is not None:
                            has_valid_coordinates = True
                    
                    if has_valid_coordinates and lat is not None and lon is not None:
                        # Process complete data - with error handling for Supabase upload
                        try:
                            file_link = self.supabase_service.upload_file(file_path)
                        except Exception as e:
                            logger.warning(f"Supabase upload failed, continuing without upload: {e}")
                            file_link = "Foto tersimpan (gagal upload)"
                        
                        location_coords, gmaps_link = process_coordinates(lat, lon)
                        
                        if self.sheets_service.save_to_spreadsheet(row, user_id, location_coords, file_link, gmaps_link):
                            self.cleanup_pending_data(user_id, pending_data)
                            if os.path.exists(file_path):
                                os.remove(file_path)
                            await event.reply(f"✅ **SELAMAT Data berhasil disimpan!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data telah ditambahkan ke spreadsheet\n\n🎉 **Status:** Data selesai diproses")
                        else:
                            await event.reply("❌ Gagal menyimpan ke Google Spreadsheet")
                    else:
                        # Store pending data without failing if Supabase upload fails
                        self.cleanup_pending_data(user_id, pending_data)
                        try:
                            file_link = self.supabase_service.upload_file(file_path)
                        except Exception as e:
                            logger.warning(f"Supabase upload failed, continuing without upload: {e}")
                            file_link = None
                        
                        pending_data[user_id] = {
                            'data': caption_text,
                            'file_link': file_link,
                            'timestamp': format_timestamp(),
                            'file_path': file_path,
                            'type': 'complete'
                        }
                        await event.reply("✅ **Foto dan caption telah digabung.**\n\n Data disimpan sementara.\n\n❌ **Yang masih kurang:**\n• Koordinat lokasi\n\n📍 **Langkah selanjutnya:**\n1. Share lokasi Anda sekarang, ATAU\n2. Kirim Link Google Maps")
                else:
                    # Invalid caption format - store photo only without Drive upload attempt
                    self.cleanup_pending_data(user_id, pending_data)
                    pending_data[user_id] = {
                        'data': None,
                        'file_link': None,
                        'timestamp': format_timestamp(),
                        'file_path': file_path,
                        'type': 'photo_only'
                    }
                    await event.reply("⏳ **Foto disimpan sementara!**\n\nFormat caption sebelumnya tidak sesuai.\n\nSilakan kirim caption (teks) sesuai format.\n\nKetik /format untuk melihat format yang benar.")
            else:
                # Store photo only - don't try to upload to Google Drive yet
                self.cleanup_pending_data(user_id, pending_data)
                pending_data[user_id] = {
                    'data': None,
                    'file_link': None,
                    'timestamp': format_timestamp(),
                    'file_path': file_path,
                    'type': 'photo_only'
                }
                await event.reply("⏳ **Foto disimpan sementara!**\n\nSilakan kirim caption (teks) sesuai format.\n\nKetik /format untuk melihat format yang benar.")
                
        except Exception as e:
            logger.error(f"Error in handle_photo_only: {e}")
            try:
                await event.reply(f"❌ Terjadi error saat memproses foto: {e}")
            except:
                logger.error("Failed to send error message to user")
    
    async def handle_photo_with_caption(self, event, user_id: str, pending_data: Dict):
        """Handle photo with caption messages"""
        try:
            match = CAPTION_PATTERN.search(event.text.strip())
            if not match:
                await event.reply("❌ Data belum lengkap atau format caption tidak sesuai.\n\nLengkapi data atau ketik /format untuk melihat format yang benar.")
                return
            
            row = match.groupdict()
            
            # Validate data
            is_valid, missing_fields, error_message = validate_caption_data(row)
            if not is_valid:
                await event.reply(error_message)
                return
            
            # Check for Google Maps link
            link_gmaps = row.get('link_gmaps', '').strip()
            has_valid_coordinates = False
            lat, lon = None, None
            
            if link_gmaps:
                link_gmaps = extract_markdown_link(link_gmaps)
                lat, lon = extract_coords_from_gmaps_link(link_gmaps)
                if lat is not None and lon is not None:
                    has_valid_coordinates = True
            
            if not has_valid_coordinates:
                # Store pending data
                self.cleanup_pending_data(user_id, pending_data)
                file_path = await event.download_media()
                
                try:
                    file_link = self.supabase_service.upload_file(file_path)
                except Exception as e:
                    logger.warning(f"Supabase upload failed, continuing without upload: {e}")
                    file_link = "Foto tersimpan"
                
                pending_data[user_id] = {
                    'data': row,
                    'file_link': file_link,
                    'timestamp': format_timestamp(),
                    'file_path': file_path
                }
                
                await event.reply("⏳ **Data disimpan sementara!**\n\n📋 Data Anda telah diterima tetapi belum lengkap.\n\n❌ **Yang masih kurang:**\n• Koordinat lokasi\n\n📍 **Langkah selanjutnya:**\n1. Share lokasi Anda sekarang, ATAU\n2. Kirim Link Google Maps")
                return
            
            # Process complete data
            self.cleanup_pending_data(user_id, pending_data)
            file_path = await event.download_media()
            
            try:
                file_link = self.supabase_service.upload_file(file_path)
            except Exception as e:
                logger.warning(f"Supabase upload failed, continuing without upload: {e}")
                file_link = "Foto tersimpan"
                
            if lat is not None and lon is not None:
                location_coords, gmaps_link = process_coordinates(lat, lon)
            else:
                location_coords, gmaps_link = "", ""
            
            if self.sheets_service.save_to_spreadsheet(row, user_id, location_coords, file_link, gmaps_link):
                await event.reply(f"✅ **SELAMAT Data berhasil disimpan!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data telah ditambahkan ke spreadsheet\n\n🎉 **Status:** Data selesai diproses")
            else:
                await event.reply("❌ Gagal menyimpan ke Google Spreadsheet")
            
            # Clean up temporary file
            if os.path.exists(file_path):
                os.remove(file_path)
                
        except Exception as e:
            logger.error(f"Error in handle_photo_with_caption: {e}")
            try:
                await event.reply(f"❌ Terjadi error saat memproses foto dan caption: {e}")
            except:
                logger.error("Failed to send error message to user")
    
    async def handle_caption_only(self, event, user_id: str, pending_data: Dict):
        """Handle caption-only messages"""
        try:
            caption_text = event.text.strip()
            match = CAPTION_PATTERN.search(caption_text)
            if not match:
                await event.reply("❌ Format caption tidak sesuai.\n\nKetik /format untuk melihat format yang benar.")
                return
            
            row = match.groupdict()
            is_valid, missing_fields, error_message = validate_caption_data(row)
            if not is_valid:
                await event.reply(error_message)
                return
            
            # Check for Google Maps link
            link_gmaps = row.get('link_gmaps', '').strip()
            has_valid_coordinates = False
            lat, lon = None, None
            
            if link_gmaps:
                link_gmaps = extract_markdown_link(link_gmaps)
                lat, lon = extract_coords_from_gmaps_link(link_gmaps)
                if lat is not None and lon is not None:
                    has_valid_coordinates = True
            
            # Check if there's existing photo data
            existing_photo_path = None
            if user_id in pending_data and pending_data[user_id].get('type') == 'photo_only':
                existing_photo_path = pending_data[user_id].get('file_path')
            
            if existing_photo_path and os.path.exists(existing_photo_path):
                # Combine with existing photo
                try:
                    file_link = self.supabase_service.upload_file(existing_photo_path)
                except Exception as e:
                    logger.warning(f"Supabase upload failed, continuing without upload: {e}")
                    file_link = "Foto tersimpan"
                
                if has_valid_coordinates and lat is not None and lon is not None:
                    # Process complete data
                    location_coords, gmaps_link = process_coordinates(lat, lon)
                    
                    if self.sheets_service.save_to_spreadsheet(row, user_id, location_coords, file_link, gmaps_link):
                        self.cleanup_pending_data(user_id, pending_data)
                        if os.path.exists(existing_photo_path):
                            os.remove(existing_photo_path)
                        await event.reply(f"✅ **SELAMAT Data berhasil disimpan!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data telah ditambahkan ke spreadsheet\n\n🎉 **Status:** Data selesai diproses")
                    else:
                        await event.reply("❌ Gagal menyimpan ke Google Spreadsheet")
                else:
                    # Store pending data with photo
                    pending_data[user_id] = {
                        'data': caption_text,
                        'file_link': file_link,
                        'timestamp': format_timestamp(),
                        'file_path': existing_photo_path,
                        'type': 'complete'
                    }
                    await event.reply("✅ **Foto dan caption telah digabung.**\n\n Data disimpan sementara.\n\n❌ **Yang masih kurang:**\n• Koordinat lokasi\n\n📍 **Langkah selanjutnya:**\n1. Share lokasi Anda sekarang, ATAU\n2. Kirim Link Google Maps")
            else:
                # Store caption only
                self.cleanup_pending_data(user_id, pending_data)
                pending_data[user_id] = {
                    'data': caption_text,
                    'file_link': None,
                    'timestamp': format_timestamp(),
                    'file_path': None,
                    'type': 'caption_only'
                }
                
                if has_valid_coordinates:
                    await event.reply(f"⏳ **Caption disimpan sementara!**\n\n✅ Link Google Maps: Valid\n📍 Koordinat: {lat}, {lon}\n\nSilakan kirim foto yang sesuai.\n\nKetik /format untuk melihat format yang benar.")
                else:
                    await event.reply("⏳ **Caption disimpan sementara!**\n\nSilakan kirim foto yang sesuai.")
                    
        except Exception as e:
            logger.error(f"Error in handle_caption_only: {e}")
            try:
                await event.reply(f"❌ Terjadi error saat memproses caption: {e}")
            except:
                logger.error("Failed to send error message to user") 