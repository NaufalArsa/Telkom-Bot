import logging
from typing import Dict
from utils.validation import CAPTION_PATTERN, extract_markdown_link
from utils.location import extract_coords_from_gmaps_link
from handlers.data_handlers import DataHandlers

logger = logging.getLogger(__name__)

# Command Handlers for various commands
class CommandHandlers:
    def __init__(self):
        self.data_handlers = DataHandlers()
    
    # Format handler for /format command
    async def format_handler(self, event):
        """Handle /format command"""
        if event.is_private:
            format_text = (
                "#VISIT\n\n"
                "Nama SA/ AR: \n"
                "STO: \n"
                "Cluster: \n\n"
                "Nama usaha: \n"
                "Nama PIC: \n"
                "Nomor HP/ WA: \n"
                "Internet existing: \n"
                "Biaya internet existing: \n"
                "Voice of Customer:  \n\n"
            )
            await event.reply(format_text)
    
    # Help handler for /help command
    async def help_handler(self, event):
        """Handle /help command"""
        if event.is_private:
            help_text = (
                "🆘 **BANTUAN BOT YOVI**\n\n"
                "📋 **CARA KERJA:**\n\n"
                "🚀 **Langkah 1:** Ketik /start untuk memulai\n\n"
                "📝 **Langkah 2:** Kirim data secara bertahap:\n"
                "• Kirim foto terlebih dahulu, ATAU\n"
                "• Kirim caption terlebih dahulu\n"
                "• Kemudian kirim bagian yang kurang\n\n"
                "📍 **Langkah 3:** Lengkapi koordinat:\n"
                "• Share lokasi, ATAU\n"
                "• Kirim Link Google Maps\n\n"
                "✅ **Data akan disimpan jika:**\n"
                "• Lengkap dan menyertakan koordinat (share lokasi atau Link Google Maps)\n\n"
                "⏳ **Data tanpa koordinat:**\n"
                "• Disimpan sementara sampai lengkap\n"
                "• Data lama akan diganti jika kirim data baru\n\n"
                "🗑️ **Reset data:**\n"
                "• Ketik /start atau /clear untuk menghapus data sementara\n\n"
                "📊 **Cek status:**\n"
                "• Ketik /status untuk melihat data sementara\n\n"
                "🚩 **Langkah khusus /odp:**\n"
                "1. Ketik /odp\n"
                "2. Kirim link Google Maps atau share lokasi Anda\n" 
                "3. Bot akan membalas 5 ODP terdekat dari lokasi yang Anda kirimkan.\n\n"
                "💡 **Langkah khusus /potensi:**\n"
                "1. Ketik /potensi\n"
                "2. Pilih kategori\n"
                "3. Kirim link Google Maps atau share lokasi Anda\n" 
                "4. Bot akan membalas 5 Potensi terdekat dari lokasi yang Anda kirimkan.\n\n"
                "🔍 **Langkah khusus /psb:**\n"
                "1. Ketik /psb dikkuti dengan nama customer. Contoh /psb Batubara\n"
                "2. Bot akan mmeberikan 5 data PSB terkait.\n\n"
                "📜 **Langkah khusus /brosur:**"
                "1. Ketik /brosur diikuti dengan jenis brosur (HSI, WMS, UMKM)\n"
                "2. Bot akan mengirimkan brosur yang sesuai dengan jenis yang diminta.\n\n"
                "📖 **Brosur yang tersedia:**\n"
                "• HSI - Brosur HSI\n"
                "• WMS - Brosur WMS\n"    
                "• UMKM - Brosur UMKM\n\n"
                "📝 **FORMAT DATA:**\n"
                "Ketik /format untuk melihat format yang benar"
            )
            await event.reply(help_text)
    
    # Start handler for /start command
    async def start_handler(self, event, user_started: Dict, pending_data: Dict):
        """Handle /start command"""
        if event.is_private:
            user_id = str(event.sender_id)
            self.data_handlers.cleanup_pending_data(user_id, pending_data)
            await event.reply("🤖 **Selamat datang di bot YOVI!**\n\n"
                            "Bot siap menerima data.\n\n"
                            "📋 **Cara mengisi data:**\n\n"
                            "1. Kirim foto terlebih dahulu, ATAU\n"
                            "2. Kirim caption terlebih dahulu\n"
                            "3. Kemudian kirim bagian yang kurang\n"
                            "4. Share lokasi atau kirim Link Google Maps\n\n"
                            "💡 **Command yang tersedia:**\n"
                            "• /format - Format pengisian data\n"
                            "• /help - Bantuan lengkap\n"
                            "• /status - Cek status data sementara\n"
                            "• /clear - Hapus data sementara\n"
                            "• /odp - Cari 5 ODP terdekat dari lokasi Anda.\n"
                            "• /potensi - Cari 5 Potensi terdekat dari lokasi Anda.\n"
                            "• /psb - Cari 5 PSB terkait dengan nama customer.\n"
                            "• /brosur - Dapatkan brosur sesuai jenis yang diminta.\n"
                            "• /record - Cek riwayat input Anda.\n\n")
            user_started[user_id] = True
    
    # Status handler for /status command
    async def status_handler(self, event, user_started: Dict, pending_data: Dict):
        """Handle /status command"""
        if event.is_private:
            user_id = str(event.sender_id)
            
            if user_id not in user_started:
                await event.reply("⚠️ **Silakan ketik /start terlebih dahulu!**\n\nBot belum siap menerima data.\n\nKetik /start untuk memulai.")
                return
            
            if user_id in pending_data:
                pending = pending_data[user_id]
                data_type = pending.get('type', 'unknown')
                
                if data_type == 'photo_only':
                    await event.reply("📸 **Status: Foto tersimpan**\n\n✅ Foto: Sudah ada\n❌ Caption: Belum ada\n\nSilakan kirim caption sesuai format.")
                elif data_type == 'caption_only':
                    caption_text = pending.get('data', '')
                    match = CAPTION_PATTERN.search(caption_text)
                    if match:
                        row = match.groupdict()
                        link_gmaps = row.get('link_gmaps', '').strip()
                        if link_gmaps:
                            link_gmaps = extract_markdown_link(link_gmaps)
                            lat, lon = extract_coords_from_gmaps_link(link_gmaps)
                            if lat is not None and lon is not None:
                                await event.reply(f"📝 **Status: Caption tersimpan**\n\n❌ Foto: Belum ada\n✅ Caption: Sudah ada\n✅ Link Google Maps: Valid\n📍 Koordinat: {lat}, {lon}\n\nSilakan kirim foto yang sesuai.")
                            else:
                                await event.reply("📝 **Status: Caption tersimpan**\n\n❌ Foto: Belum ada\n✅ Caption: Sudah ada\n❌ Link Google Maps: Tidak valid\n\nSilakan kirim foto yang sesuai.")
                        else:
                            await event.reply("📝 **Status: Caption tersimpan**\n\n❌ Foto: Belum ada\n✅ Caption: Sudah ada\n❌ Link Google Maps: Belum ada\n\nSilakan kirim foto yang sesuai.")
                    else:
                        await event.reply("📝 **Status: Caption tersimpan**\n\n❌ Foto: Belum ada\n✅ Caption: Sudah ada\n❌ Format: Tidak sesuai\n\nSilakan kirim foto yang sesuai.")
                elif data_type == 'complete':
                    caption_text = pending.get('data', '')
                    match = CAPTION_PATTERN.search(caption_text)
                    if match:
                        row = match.groupdict()
                        link_gmaps = row.get('link_gmaps', '').strip()
                        if link_gmaps:
                            link_gmaps = extract_markdown_link(link_gmaps)
                            lat, lon = extract_coords_from_gmaps_link(link_gmaps)
                            if lat is not None and lon is not None:
                                await event.reply(f"📋 **Status: Data lengkap**\n\n✅ Foto: Sudah ada\n✅ Caption: Sudah ada\n✅ Link Google Maps: Valid\n📍 Koordinat: {lat}, {lon}\n\nData siap disimpan ke spreadsheet!")
                            else:
                                await event.reply("📋 **Status: Data lengkap**\n\n✅ Foto: Sudah ada\n✅ Caption: Sudah ada\n❌ Link Google Maps: Tidak valid\n\nSilakan share lokasi atau kirim Link Google Maps.")
                        else:
                            await event.reply("📋 **Status: Data lengkap**\n\n✅ Foto: Sudah ada\n✅ Caption: Sudah ada\n❌ Link Google Maps: Belum ada\n\nSilakan share lokasi atau kirim Link Google Maps.")
                    else:
                        await event.reply("📋 **Status: Data lengkap**\n\n✅ Foto: Sudah ada\n✅ Caption: Sudah ada\n❌ Format: Tidak sesuai\n\nSilakan share lokasi atau kirim Link Google Maps.")
                else:
                    await event.reply("📋 **Status: Data tersimpan**\n\nData sedang menunggu kelengkapan.\n\nSilakan lengkapi data yang kurang.")
            else:
                await event.reply("📭 **Status: Tidak ada data sementara**\n\nSilakan kirim foto atau caption untuk memulai.")
    
    # Clear handler for /clear command
    async def clear_handler(self, event, user_started: Dict, pending_data: Dict):
        """Handle /clear command"""
        if event.is_private:
            user_id = str(event.sender_id)
            
            if user_id not in user_started:
                await event.reply("⚠️ **Silakan ketik /start terlebih dahulu!**\n\nBot belum siap menerima data.\n\nKetik /start untuk memulai.")
                return
            
            self.data_handlers.cleanup_pending_data(user_id, pending_data)
            await event.reply("Silakan kirim data baru.") 