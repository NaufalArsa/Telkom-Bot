import logging
from telethon import events
from supabase import create_client
import os
import requests
from urllib.parse import quote

logger = logging.getLogger(__name__)

class BrosurHandlers:
    def __init__(self):
        # Inisialisasi Supabase client
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        if self.supabase_url and self.supabase_key:
            self.client = create_client(self.supabase_url, self.supabase_key)
        else:
            self.client = None
            logger.warning("Supabase URL or key not set for BrosurHandlers.")

        # Mapping tipe brosur
        self.allowed_types = {
            "HSI": "Brosur HSI",
            "WMS": "Brosur WMS",
            "UMKM": "Brosur UMKM"
        }

    async def send_brosur(self, event, jenis: str):
        if not self.client:
            await event.reply("❌ Supabase belum terkonfigurasi.")
            return

        tipe_brosur = self.allowed_types.get(jenis.upper())
        if not tipe_brosur:
            await event.reply("❗Jenis brosur tidak valid. Gunakan: HSI, WMS, atau UMKM.")
            return

        # Coba cari file dengan ekstensi umum
        found = False
        for ext in [".jpg", ".jpeg", ".png", ".pdf"]:
            filename = f"{tipe_brosur}{ext}"
            try:
                public_url = self.client.storage.from_("brosur").get_public_url(quote(filename))
                # Cek apakah file benar-benar ada
                resp = requests.get(public_url)
                if resp.status_code == 200 and resp.content:
                    found = True
                    if ext in [".jpg", ".jpeg", ".png"]:
                        await event.reply(file=public_url, message=f"📄 {tipe_brosur}")
                    elif ext == ".pdf":
                        await event.reply(file=public_url, message=f"📄 {tipe_brosur} (PDF)")
                    break
            except Exception as e:
                logger.error(f"Error fetching brosur: {e}")
                continue

        if not found:
            await event.reply(f"❌ Brosur untuk *{tipe_brosur}* tidak ditemukan di storage.", parse_mode="md")

    async def brosur_command_handler(self, event):
        """Handle /brosur command dengan argumen jenis"""
        if event.is_private:
            parts = event.text.strip().split()
            if len(parts) < 2:
                await event.reply("❗ Format perintah salah.\n\nGunakan:\n`/brosur HSI`\n`/brosur WMS`\n`/brosur UMKM`", parse_mode="md")
                return
            jenis = parts[1]
            await self.send_brosur(event, jenis)