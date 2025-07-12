import os, re, json, gspread, requests, subprocess
from oauth2client.service_account import ServiceAccountCredentials
from telethon import TelegramClient, events
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials
from datetime import datetime

api_id = 29586893
api_hash = "d52a299d8400f35bdf8acd65900ea13f"
bot_token = "7234638021:AAHLBVH4CK9L0xMmWwEI27vduHS50_GEjJI"
drive_id = '118MghjEj1lQGx3xht7v_2yMwS84z96q0'

client = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
gc = gspread.service_account(filename='gcredentials.json')
sheet = gc.open('Recap Visit YOVI').sheet1 

with open('gcredentials.json', 'r') as f:
    creds_dict = json.load(f)

# Dictionary untuk menyimpan data pending (belum lengkap)
pending_data = {}

# Dictionary untuk melacak status user (apakah sudah /start)
user_started = {}

pattern = re.compile(r"""
    Nama\s+SA/\s*AR:\s*(?P<nama_sa>.+?)\n+
    STO:\s*(?P<sto>.+?)\n+
    Cluster:\s*(?P<cluster>.+?)\n+
    \n*
    Nama\s+usaha:\s*(?P<usaha>.+?)\n+
    Nama\s+PIC:\s*(?P<pic>.+?)\n+
    Nomor\s+HP/\s*WA:\s*(?P<hpwa>.+?)\n+
    Internet\s+existing:\s*(?P<internet>.+?)\n+
    Biaya\s+internet\s+existing:\s*(?P<biaya>.+?)\n+
    Voice\s+of\s+Customer:\s*(?P<voc>.+?)(?:\n|$)
""", re.DOTALL | re.MULTILINE | re.IGNORECASE | re.VERBOSE)

def get_address_from_coords(lat, lon):
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
    try:
        resp = requests.get(url, headers={"User-Agent": "TelegramBot"})
        if resp.status_code == 200:
            data = resp.json()
            return data.get("display_name", f"{lat},{lon}")
        return f"{lat},{lon}"
    except Exception:
        return f"{lat},{lon}"

def get_gmaps_link_from_coords(lat, lon):
    """
    Generate Google Maps link from coordinates
    Returns: Google Maps URL
    """
    return f"https://www.google.com/maps?q={lat},{lon}"

def extract_coords_from_gmaps_link(link):
    """Extract latitude and longitude from Google Maps link using Node.js"""
    if not link or link.strip() == "":
        return None, None
    
    if '?' in link:
        link = link.split('?', 1)[0]

    try:
        # Call Node.js script and pass the link as an argument
        result = subprocess.run(
            ['node', 'expand.js', link],
            capture_output=True,
            text=True
        )
        
        # Parse the output (expecting a JSON-like result)
        for line in result.stdout.splitlines():
            if line.startswith("Result:"):
                coords_str = line.replace("Result:", "").strip()
                try:
                    coords = json.loads(coords_str.replace("'", '"'))
                    if coords and 'latitude' in coords and 'longitude' in coords:
                        return coords['latitude'], coords['longitude']
                except Exception as e:
                    print(f"Error parsing coordinates: {e}")
                    pass
    except Exception as e:
        print(f"Error calling Node.js script: {e}")
    
    return None, None

def upload_to_gdrive(file_path, creds_dict):
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)
    # Replace 'YOUR_FOLDER_ID' with your actual folder ID
    file_metadata = {'name': os.path.basename(file_path), 'parents': [drive_id]}
    media = MediaFileUpload(file_path, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    service.permissions().create(fileId=file.get('id'), body={'role': 'reader', 'type': 'anyone'}).execute()
    file_link = f"https://drive.google.com/uc?id={file.get('id')}"
    return file_link

def validate_caption_data(row):
    """
    Validasi semua field caption data untuk memastikan tidak ada yang kosong
    Returns: (is_valid, missing_fields, error_message)
    """
    required_fields = {
        'nama_sa': 'Nama SA/AR',
        'sto': 'STO', 
        'cluster': 'Cluster',
        'usaha': 'Nama usaha',
        'pic': 'Nama PIC',
        'hpwa': 'Nomor HP/WA',
        'internet': 'Internet existing',
        'biaya': 'Biaya internet existing',
        'voc': 'Voice of Customer'
    }
    
    missing_fields = []
    
    for field_key, field_name in required_fields.items():
        field_value = row.get(field_key, '').strip()
        
        # Cek apakah field ada dan tidak kosong
        if not field_value or field_value == '':
            missing_fields.append(field_name)
    
    if missing_fields:
        error_message = f"❌ **Data tidak lengkap!**\n\nField yang masih kosong:\n"
        for i, field in enumerate(missing_fields, 1):
            error_message += f"{i}. {field}\n"
        error_message += "\n📝 **Langkah selanjutnya:**\nLengkapi field yang kosong di atas, kemudian kirim ulang data."
        return False, missing_fields, error_message
    
    return True, [], "✅ Semua data lengkap!"

@client.on(events.NewMessage(incoming=True))
async def handler(event):
    try:
        if event.is_private:
            user_id = str(event.sender_id)
            
            # Cek apakah ini adalah command, jika ya, skip handler ini
            if event.text and event.text.startswith('/'):
                return  # Biarkan handler command yang spesifik menangani ini
            
            # Cek apakah user sudah /start
            if user_id not in user_started:
                await event.reply("⚠️ **Silakan ketik /start terlebih dahulu!**\n\nBot belum siap menerima data.\n\nKetik /start untuk memulai.")
                return

            # Jika hanya foto tanpa caption
            if event.photo and not event.text:
                # Hapus data pending lama jika ada
                if user_id in pending_data:
                    old_file_path = pending_data[user_id].get('file_path')
                    if old_file_path and os.path.exists(old_file_path):
                        os.remove(old_file_path)
                
                # Download gambar
                file_path = await event.download_media()
                
                # Cek apakah sudah ada caption sementara
                if user_id in pending_data and pending_data[user_id].get('type') == 'caption_only':
                    # Parse caption untuk mendapatkan data
                    caption_text = pending_data[user_id]['data']
                    match = pattern.search(caption_text)
                    if match:
                        row = match.groupdict()
                        
                        # Validasi data caption terlebih dahulu
                        is_valid, missing_fields, error_message = validate_caption_data(row)
                        if not is_valid:
                            await event.reply(error_message)
                        return

                        # Check if link_gmaps is provided and extract coordinates
                        link_gmaps = row.get('link_gmaps', '').strip()
                        location_coords = ""
                        has_valid_coordinates = False
                        lat, lon = None, None
                        
                        if link_gmaps and link_gmaps != "":
                            # If the link is in Markdown format [text](url), extract the url
                            md_match = re.match(r'\[.*?\]\((https?://[^\)]+)\)', link_gmaps)
                            if md_match:
                                link_gmaps = md_match.group(1)
                            lat, lon = extract_coords_from_gmaps_link(link_gmaps)
                            if lat is not None and lon is not None:
                                location_coords = f"{lat},{lon}"
                                has_valid_coordinates = True
                        
                        # Jika ada koordinat valid, langsung proses dan simpan ke spreadsheet
                        if has_valid_coordinates:
                            try:
                                file_link = upload_to_gdrive(file_path, creds_dict)
                            except Exception as e:
                                file_link = f"Gagal upload: {e}"
                            
                            try:
                                timestamp = pending_data[user_id]['timestamp']
                                no = len(sheet.get_all_values())
                                
                                sheet.append_row([
                                    no, timestamp, user_id, row['nama_sa'], row['sto'], row['cluster'], row['usaha'],
                                    row['pic'], row['hpwa'], row['internet'], row['biaya'], row['voc'], location_coords, file_link, link_gmaps, "Default"
                                ])
                                
                                # Hapus data pending
                                del pending_data[user_id]
                                
                                # Hapus file temporary
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                                
                                await event.reply(f"✅ **SELAMAT Data berhasil disimpan!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data telah ditambahkan ke spreadsheet\n\n🎉 **Status:** Data selesai diproses")
                                
                            except Exception as e:
                                await event.reply(f"❌ Gagal menyimpan ke Google Spreadsheet: {e}")
                        else:
                            # Gabungkan dengan caption yang sudah ada (tanpa koordinat)
                            pending_data[user_id] = {
                                'data': caption_text,
                                'file_link': None,
                                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'file_path': file_path,
                                'type': 'complete'
                            }
                            await event.reply("✅ **Foto dan caption telah digabung.**\n\n Data disimpan sementara.\n\n❌ **Yang masih kurang:**\n• Koordinat lokasi\n\n📍 **Langkah selanjutnya:**\n1. Share lokasi Anda sekarang, ATAU\n2. Kirim Link Google Maps")
                    else:
                        # Format caption tidak sesuai, simpan foto sementara
                        pending_data[user_id] = {
                            'data': None,
                            'file_link': None,
                            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'file_path': file_path,
                            'type': 'photo_only'
                        }
                        await event.reply("⏳ **Foto disimpan sementara!**\n\nFormat caption sebelumnya tidak sesuai.\n\nSilakan kirim caption (teks) sesuai format.\n\nKetik /format untuk melihat format yang benar.")
                else:
                    # Simpan foto sementara
                    pending_data[user_id] = {
                        'data': None,
                        'file_link': None,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'file_path': file_path,
                        'type': 'photo_only'
                    }
                    await event.reply("⏳ **Foto disimpan sementara!**\n\nSilakan kirim caption (teks) sesuai format.\n\nKetik /format untuk melihat format yang benar.")
                return

            # Semua pesan harus gambar + caption data
            if event.photo and event.text:
                match = pattern.search(event.text.strip())
                if match:
                    row = match.groupdict()
                    
                    # Validasi data caption terlebih dahulu
                    is_valid, missing_fields, error_message = validate_caption_data(row)
                    if not is_valid:
                        await event.reply(error_message)
                        return
                    
                    # Check if link_gmaps is provided and extract coordinates
                    link_gmaps = row.get('link_gmaps', '').strip()
                    location_coords = ""
                    has_valid_coordinates = False
                    
                    if link_gmaps and link_gmaps != "":
                        # If the link is in Markdown format [text](url), extract the url
                        md_match = re.match(r'\[.*?\]\((https?://[^\)]+)\)', link_gmaps)
                        if md_match:
                            link_gmaps = md_match.group(1)
                        lat, lon = extract_coords_from_gmaps_link(link_gmaps)
                        if lat is not None and lon is not None:
                            location_coords = f"{lat},{lon}"
                            has_valid_coordinates = True
                    
                    # VALIDASI: Jika tidak ada koordinat valid, simpan data sementara
                    if not has_valid_coordinates:
                        # Hapus data pending lama jika ada
                        if user_id in pending_data:
                            # Hapus file lama jika masih ada
                            old_file_path = pending_data[user_id]['file_path']
                            if os.path.exists(old_file_path):
                                os.remove(old_file_path)
                            del pending_data[user_id]
                        
                        # Download dan upload gambar baru
                        file_path = await event.download_media()
                        try:
                            file_link = upload_to_gdrive(file_path, creds_dict)
                        except Exception as e:
                            file_link = f"Gagal upload: {e}"
                        
                        # Simpan data pending baru
                        pending_data[user_id] = {
                            'data': row,
                            'file_link': file_link,
                            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'file_path': file_path
                        }
                        
                        await event.reply("⏳ **Data disimpan sementara!**\n\n📋 Data Anda telah diterima tetapi belum lengkap.\n\n❌ **Yang masih kurang:**\n• Koordinat lokasi\n\n📍 **Langkah selanjutnya:**\n1. Share lokasi Anda sekarang, ATAU\n2. Kirim Link Google Maps")
                        
                        return
                    
                    # Jika ada koordinat valid, lanjutkan proses upload dan simpan ke sheet
                    # Hapus data pending lama jika ada
                    if user_id in pending_data:
                        # Hapus file lama jika masih ada
                        old_file_path = pending_data[user_id]['file_path']
                        if os.path.exists(old_file_path):
                            os.remove(old_file_path)
                        del pending_data[user_id]
                    
                    file_path = await event.download_media()
                    try:
                        file_link = upload_to_gdrive(file_path, creds_dict)
                    except Exception as e:
                        file_link = f"Gagal upload: {e}"
                    
                    try:
                        # Get current timestamp
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        # Get the next row number (excluding header)
                        no = len(sheet.get_all_values())  # This counts all rows including header, so next row is len+1, but for display, len is enough
                        
                        # Kolom: timestamp, user_id, nama_sa, sto, cluster, usaha, pic, hpwa, internet, biaya, voc, lokasi, file_link, link_gmaps
                        sheet.append_row([
                            no, timestamp, str(event.sender_id), row['nama_sa'], row['sto'], row['cluster'], row['usaha'],
                            row['pic'], row['hpwa'], row['internet'], row['biaya'], row['voc'], location_coords, file_link, link_gmaps, "Default"
                        ])
                        
                        await event.reply(f"✅ **SELAMAT Data berhasil disimpan!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data telah ditambahkan ke spreadsheet\n\n🎉 **Status:** Data selesai diproses")
                        
                    except Exception as e:
                        await event.reply(f"❌ Gagal menyimpan ke Google Spreadsheet: {e}")
                    
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return
                else:
                    await event.reply("❌ Data belum lengkap atau format caption tidak sesuai.\n\nLengkapi data atau ketik /format untuk melihat format yang benar.")
                    return

            # Handler untuk Link Google Maps yang dikirim terpisah
            if event.text and not event.photo and ('maps.google.com' in event.text or 'goo.gl/maps' in event.text or 'maps.app.goo.gl' in event.text):
                # Cek apakah ada data pending
                if user_id in pending_data:
                    pending = pending_data[user_id]
                    data_type = pending.get('type', 'unknown')
                    
                    # Extract coordinates from the link
                    link_gmaps = event.text.strip()
                    lat, lon = extract_coords_from_gmaps_link(link_gmaps)
                    
                    if lat is not None and lon is not None:
                        # Jika data sudah lengkap (foto + caption)
                        if data_type == 'complete':
                            # Parse caption untuk mendapatkan data
                            caption_text = pending['data']
                            match = pattern.search(caption_text)
                            if match:
                                row = match.groupdict()
                                
                                # Validasi data caption terlebih dahulu
                                is_valid, missing_fields, error_message = validate_caption_data(row)
                                if not is_valid:
                                    await event.reply(error_message)
                                    return
                                
                                file_path = pending['file_path']
                                
                                # Upload foto ke Google Drive
                                try:
                                    file_link = upload_to_gdrive(file_path, creds_dict)
                                except Exception as e:
                                    file_link = f"Gagal upload: {e}"
                                
                                # Simpan ke spreadsheet
                                try:
                                    timestamp = pending['timestamp']
                                    no = len(sheet.get_all_values())
                                    
                                    sheet.append_row([
                                        no, timestamp, user_id, row['nama_sa'], row['sto'], row['cluster'], row['usaha'],
                                        row['pic'], row['hpwa'], row['internet'], row['biaya'], row['voc'], f"{lat},{lon}", file_link, link_gmaps, "Default"
                                    ])
                                    
                                    # Hapus data pending
                                    del pending_data[user_id]
                                    
                                    # Hapus file temporary
                                    if os.path.exists(file_path):
                                        os.remove(file_path)
                                    
                                    await event.reply(f"✅ **SELAMAT Data berhasil disimpan ke spreadsheet!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data lengkap telah ditambahkan\n\n🎉 **Status:** Data selesai diproses")
                                    
                                except Exception as e:
                                    await event.reply(f"❌ Gagal menyimpan ke Google Spreadsheet: {e}")
                            else:
                                await event.reply("❌ Format caption tidak sesuai.\n\nKetik /format untuk melihat format yang benar.")
                        
                        # Jika ada foto saja
                        elif data_type == 'photo_only':
                            await event.reply("❌ Data belum lengkap.\n\nSilakan kirim caption terlebih dahulu.")
                        
                        # Jika ada caption saja
                        elif data_type == 'caption_only':
                            # Parse caption untuk mendapatkan data
                            caption_text = pending['data']
                            match = pattern.search(caption_text)
                            if match:
                                row = match.groupdict()
                                
                                # Validasi data caption terlebih dahulu
                                is_valid, missing_fields, error_message = validate_caption_data(row)
                                if not is_valid:
                                    await event.reply(error_message)
                                    return
                                
                                # Simpan ke spreadsheet tanpa foto
                                try:
                                    timestamp = pending['timestamp']
                                    no = len(sheet.get_all_values())
                                    
                                    sheet.append_row([
                                        no, timestamp, user_id, row['nama_sa'], row['sto'], row['cluster'], row['usaha'],
                                        row['pic'], row['hpwa'], row['internet'], row['biaya'], row['voc'], f"{lat},{lon}", "Tidak ada foto", '', "Default"
                                    ])
                                    
                                    # Hapus data pending
                                    del pending_data[user_id]
                                    
                                    await event.reply(f"✅ **SELAMAT Data berhasil disimpan ke spreadsheet!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data telah ditambahkan (tanpa foto)\n\n🎉 **Status:** Data selesai diproses")
                                    
                                except Exception as e:
                                    await event.reply(f"❌ Gagal menyimpan ke Google Spreadsheet: {e}")
                            else:
                                await event.reply("❌ Format caption tidak sesuai.\n\nKetik /format untuk melihat format yang benar.")
                        
                        # Jika ada data dengan type lain
                        else:
                            # Coba parse data yang ada
                            if 'data' in pending and pending['data']:
                                # Jika data adalah dictionary
                                if isinstance(pending['data'], dict):
                                    row = pending['data']
                                    
                                    # Validasi data caption terlebih dahulu
                                    is_valid, missing_fields, error_message = validate_caption_data(row)
                                    if not is_valid:
                                        await event.reply(error_message)
                                        return
                                    
                                    file_path = pending.get('file_path')
                                    file_link = pending.get('file_link', 'Gagal upload')
                                    
                                    try:
                                        timestamp = pending['timestamp']
                                        no = len(sheet.get_all_values())
                                        
                                        sheet.append_row([
                                            no, timestamp, user_id, row['nama_sa'], row['sto'], row['cluster'], row['usaha'],
                                            row['pic'], row['hpwa'], row['internet'], row['biaya'], row['voc'], f"{lat},{lon}", file_link, '', "Default"
                                        ])
                                        
                                        # Hapus data pending
                                        del pending_data[user_id]
                                        
                                        # Hapus file temporary
                                        if file_path and os.path.exists(file_path):
                                            os.remove(file_path)
                                        
                                        await event.reply(f"✅ **SELAMAT Data berhasil disimpan ke spreadsheet!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data lengkap telah ditambahkan\n\n🎉 **Status:** Data selesai diproses")
                                        
                                    except Exception as e:
                                        await event.reply(f"❌ Gagal menyimpan ke Google Spreadsheet: {e}")
                                else:
                                    await event.reply("❌ Format data tidak sesuai.\n\nSilakan kirim ulang data dengan format yang benar.")
                            else:
                                await event.reply("❌ Data tidak lengkap.\n\nSilakan kirim foto dan caption terlebih dahulu.")
                    else:
                        await event.reply("❌ Link Google Maps tidak valid.\n\nSilakan kirim Link Google Maps yang valid atau share lokasi.")
                else:
                    await event.reply("❌ Tidak ada data sementara.\n\nSilakan kirim data terlebih dahulu.")
                return

            # Handler untuk caption saja (mungkin update data yang sudah ada)
            if event.text and not event.photo:
                # Cek apakah ada data pending yang sudah lengkap
                if user_id in pending_data and pending_data[user_id].get('type') == 'complete':
                    # Parse caption untuk mendapatkan data
                    caption_text = pending_data[user_id]['data']
                    match = pattern.search(caption_text)
                    if match:
                        row = match.groupdict()
                        
                        # Check if link_gmaps is provided and extract coordinates
                        link_gmaps = row.get('link_gmaps', '').strip()
                        location_coords = ""
                        has_valid_coordinates = False
                        
                        if link_gmaps and link_gmaps != "":
                            # If the link is in Markdown format [text](url), extract the url
                            md_match = re.match(r'\[.*?\]\((https?://[^\)]+)\)', link_gmaps)
                            if md_match:
                                link_gmaps = md_match.group(1)
                            lat, lon = extract_coords_from_gmaps_link(link_gmaps)
                            if lat is not None and lon is not None:
                                location_coords = f"{lat},{lon}"
                                has_valid_coordinates = True
                        
                        # Jika ada koordinat valid, proses data
                        if has_valid_coordinates:
                            file_path = pending_data[user_id]['file_path']
                            try:
                                file_link = upload_to_gdrive(file_path, creds_dict)
                            except Exception as e:
                                file_link = f"Gagal upload: {e}"
                            
                            try:
                                timestamp = pending_data[user_id]['timestamp']
                                no = len(sheet.get_all_values())
                                
                                sheet.append_row([
                                    no, timestamp, user_id, row['nama_sa'], row['sto'], row['cluster'], row['usaha'],
                                    row['pic'], row['hpwa'], row['internet'], row['biaya'], row['voc'], location_coords, file_link, '', "Default"
                                ])
                                
                                # Hapus data pending
                                del pending_data[user_id]
                                
                                # Hapus file temporary
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                                
                                await event.reply(f"✅ **SELAMAT Data berhasil disimpan!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data telah ditambahkan ke spreadsheet\n\n🎉 **Status:** Data selesai diproses")
                                
                            except Exception as e:
                                await event.reply(f"❌ Gagal menyimpan ke Google Spreadsheet: {e}")
                        else:
                            # Update caption data
                            pending_data[user_id]['data'] = event.text.strip()
                            await event.reply("⏳ **Caption diperbarui!**\n\nData disimpan sementara.\n\n❌ **Yang masih kurang:**\n• Koordinat lokasi\n\n📍 **Langkah selanjutnya:**\n1. Share lokasi Anda sekarang, ATAU\n2. Kirim Link Google Maps")
                    else:
                        await event.reply("❌ Format caption tidak sesuai.\n\nKetik /format untuk melihat format yang benar.")
                    return
                
                # Cek apakah sudah ada foto sementara
                elif user_id in pending_data and pending_data[user_id].get('type') == 'photo_only':
                    # Parse caption untuk mendapatkan data
                    caption_text = event.text.strip()
                    match = pattern.search(caption_text)
                    if match:
                        row = match.groupdict()
                        
                        # Validasi data caption terlebih dahulu
                        is_valid, missing_fields, error_message = validate_caption_data(row)
                        if not is_valid:
                            await event.reply(error_message)
                            return
                        
                        # Check if link_gmaps is provided and extract coordinates
                        link_gmaps = row.get('link_gmaps', '').strip()
                        location_coords = ""
                        has_valid_coordinates = False
                        lat, lon = None, None
                        
                        if link_gmaps and link_gmaps != "":
                            # If the link is in Markdown format [text](url), extract the url
                            md_match = re.match(r'\[.*?\]\((https?://[^\)]+)\)', link_gmaps)
                            if md_match:
                                link_gmaps = md_match.group(1)
                            lat, lon = extract_coords_from_gmaps_link(link_gmaps)
                            if lat is not None and lon is not None:
                                location_coords = f"{lat},{lon}"
                                has_valid_coordinates = True
                        
                        # Jika ada koordinat valid, langsung proses dan simpan ke spreadsheet
                        if has_valid_coordinates:
                            file_path = pending_data[user_id]['file_path']
                            try:
                                file_link = upload_to_gdrive(file_path, creds_dict)
                            except Exception as e:
                                file_link = f"Gagal upload: {e}"
                            
                            try:
                                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                no = len(sheet.get_all_values())
                                
                                sheet.append_row([
                                    no, timestamp, user_id, row['nama_sa'], row['sto'], row['cluster'], row['usaha'],
                                    row['pic'], row['hpwa'], row['internet'], row['biaya'], row['voc'], location_coords, file_link, '', "Default"
                                ])
                                
                                # Hapus data pending
                                del pending_data[user_id]
                                
                                # Hapus file temporary
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                                
                                await event.reply(f"✅ **SELAMAT Data berhasil disimpan!**\n\n🏢 **Nama Usaha:** {row['usaha']}\n📍 Koordinat: {lat}, {lon}\n📊 Data telah ditambahkan ke spreadsheet\n\n🎉 **Status:** Data selesai diproses")
                                
                            except Exception as e:
                                await event.reply(f"❌ Gagal menyimpan ke Google Spreadsheet: {e}")
                        else:
                            # Gabungkan dengan foto yang sudah ada (tanpa koordinat)
                            file_path = pending_data[user_id]['file_path']
                            pending_data[user_id] = {
                                'data': event.text.strip(),
                                'file_link': None,
                                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'file_path': file_path,
                                'type': 'complete'
                            }
                            await event.reply("✅ **Foto dan caption telah digabung.** Data disimpan sementara.\n\n❌ **Yang masih kurang:**\n• Koordinat lokasi\n\n📍 **Langkah selanjutnya:**\n1. Share lokasi Anda sekarang, ATAU\n2. Kirim ulang dengan Link Google Maps yang valid")
                    else:
                        await event.reply("❌ Format caption tidak sesuai.\n\nKetik /format untuk melihat format yang benar.")
                    return
                
                # Jika belum ada data pending atau caption_only
                else:
                    # Parse caption untuk mendapatkan data
                    caption_text = event.text.strip()
                    match = pattern.search(caption_text)
                    if match:
                        row = match.groupdict()
                        
                        # Validasi data caption terlebih dahulu
                        is_valid, missing_fields, error_message = validate_caption_data(row)
                        if not is_valid:
                            await event.reply(error_message)
                            return
                        
                        # Check if link_gmaps is provided and extract coordinates
                        link_gmaps = row.get('link_gmaps', '').strip()
                        location_coords = ""
                        has_valid_coordinates = False
                        lat, lon = None, None
                        
                        if link_gmaps and link_gmaps != "":
                            # If the link is in Markdown format [text](url), extract the url
                            md_match = re.match(r'\[.*?\]\((https?://[^\)]+)\)', link_gmaps)
                            if md_match:
                                link_gmaps = md_match.group(1)
                            lat, lon = extract_coords_from_gmaps_link(link_gmaps)
                            if lat is not None and lon is not None:
                                location_coords = f"{lat},{lon}"
                                has_valid_coordinates = True
                        
                        # Hapus data pending lama jika ada
                        if user_id in pending_data:
                            old_file_path = pending_data[user_id].get('file_path')
                            if old_file_path and os.path.exists(old_file_path):
                                os.remove(old_file_path)
                        
                        # Simpan caption sementara
                        pending_data[user_id] = {
                            'data': event.text.strip(),
                            'file_link': None,
                            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'file_path': None,
                            'type': 'caption_only'
                        }
                        
                        if has_valid_coordinates:
                            await event.reply("⏳ **Caption disimpan sementara!**\n\n✅ Link Google Maps: Valid\n📍 Koordinat: " + f"{lat}, {lon}" + "\n\nSilakan kirim foto yang sesuai.\n\nKetik /format untuk melihat format yang benar.")
                        else:
                            await event.reply("⏳ **Caption disimpan sementara!**\n\nSilakan kirim foto yang sesuai.")
                    else:
                        await event.reply("❌ Format caption tidak sesuai.\n\nKetik /format untuk melihat format yang benar.")
                    return

            # Handler share location (setelah data+gambar)
            if hasattr(event.message, "geo") and event.message.geo:
                latitude = event.message.geo.lat
                longitude = event.message.geo.long

                try:
                    # Cek apakah ada data pending untuk user ini
                    if user_id in pending_data:
                        pending = pending_data[user_id]
                        data_type = pending.get('type', 'unknown')

                        # Jika data sudah lengkap (foto + caption)
                        if data_type == 'complete':
                            # Parse caption untuk mendapatkan data
                            caption_text = pending['data']
                            match = pattern.search(caption_text)
                            if match:
                                row = match.groupdict()

                                # Validasi data caption terlebih dahulu
                                is_valid, missing_fields, error_message = validate_caption_data(row)
                                if not is_valid:
                                    await event.reply(error_message)
                                    return

                                file_path = pending['file_path']

                                # Generate Google Maps link from coordinates
                                gmaps_link = get_gmaps_link_from_coords(latitude, longitude)

                                # Upload foto ke Google Drive
                                try:
                                    file_link = upload_to_gdrive(file_path, creds_dict)
                                except Exception as e:
                                    file_link = f"Gagal upload: {e}"

                                # Simpan ke spreadsheet
                                try:
                                    timestamp = pending['timestamp']
                                    no = len(sheet.get_all_values())

                                    sheet.append_row([
                                        no, timestamp, user_id, row['nama_sa'], row['sto'], row['cluster'], row['usaha'],
                                        row['pic'], row['hpwa'], row['internet'], row['biaya'], row['voc'],
                                        f"{latitude},{longitude}", file_link, gmaps_link, "Default"
                                    ])

                                    # Hapus data pending
                                    del pending_data[user_id]

                                    # Hapus file temporary
                                    if os.path.exists(file_path):
                                        os.remove(file_path)

                                    await event.reply(
                                        f"✅ **SELAMAT Data berhasil disimpan ke spreadsheet!**\n\n"
                                        f"🏢 **Nama Usaha:** {row['usaha']}\n"
                                        f"📍 Koordinat: {latitude}, {longitude}\n"
                                        f"📊 Data lengkap telah ditambahkan\n\n"
                                        f"🎉 **Status:** Data selesai diproses"
                                    )

                                except Exception as e:
                                    await event.reply(f"❌ Gagal menyimpan ke Google Spreadsheet: {e}")
                            else:
                                await event.reply("❌ Format caption tidak sesuai.\n\nKetik /format untuk melihat format yang benar.")

                        # Jika ada foto saja
                        elif data_type == 'photo_only':
                            await event.reply("❌ Data belum lengkap.\n\nSilakan kirim caption terlebih dahulu.")

                        # Jika ada caption saja
                        elif data_type == 'caption_only':
                            # Parse caption untuk mendapatkan data
                            caption_text = pending['data']
                            match = pattern.search(caption_text)
                            if match:
                                row = match.groupdict()

                                # Validasi data caption terlebih dahulu
                                is_valid, missing_fields, error_message = validate_caption_data(row)
                                if not is_valid:
                                    await event.reply(error_message)
                                    return

                                # Generate Google Maps link from coordinates
                                gmaps_link = get_gmaps_link_from_coords(latitude, longitude)

                                # Simpan ke spreadsheet tanpa foto
                                try:
                                    timestamp = pending['timestamp']
                                    no = len(sheet.get_all_values())

                                    sheet.append_row([
                                        no, timestamp, user_id, row['nama_sa'], row['sto'], row['cluster'], row['usaha'],
                                        row['pic'], row['hpwa'], row['internet'], row['biaya'], row['voc'],
                                        f"{latitude},{longitude}", "Tidak ada foto", gmaps_link, "Default"
                                    ])

                                    # Hapus data pending
                                    del pending_data[user_id]

                                    await event.reply(
                                        f"✅ **SELAMAT Data berhasil disimpan ke spreadsheet!**\n\n"
                                        f"🏢 **Nama Usaha:** {row['usaha']}\n"
                                        f"📍 Koordinat: {latitude}, {longitude}\n"
                                        f"📊 Data telah ditambahkan (tanpa foto)\n\n"
                                        f"🎉 **Status:** Data selesai diproses"
                                    )

                                except Exception as e:
                                    await event.reply(f"❌ Gagal menyimpan ke Google Spreadsheet: {e}")
                            else:
                                await event.reply("❌ Format caption tidak sesuai.\n\nKetik /format untuk melihat format yang benar.")

                        # Jika ada data dengan type lain (dari caption + gambar tanpa Link Gmaps)
                        else:
                            # Coba parse data yang ada
                            if 'data' in pending and pending['data']:
                                # Jika data adalah dictionary (dari caption + gambar)
                                if isinstance(pending['data'], dict):
                                    row = pending['data']

                                    # Validasi data caption terlebih dahulu
                                    is_valid, missing_fields, error_message = validate_caption_data(row)
                                    if not is_valid:
                                        await event.reply(error_message)
                                        return

                                    # Generate Google Maps link from coordinates
                                    gmaps_link = get_gmaps_link_from_coords(latitude, longitude)

                                    file_path = pending.get('file_path')
                                    file_link = pending.get('file_link', 'Gagal upload')

                                    try:
                                        timestamp = pending['timestamp']
                                        no = len(sheet.get_all_values())

                                        sheet.append_row([
                                            no, timestamp, user_id, row['nama_sa'], row['sto'], row['cluster'], row['usaha'],
                                            row['pic'], row['hpwa'], row['internet'], row['biaya'], row['voc'],
                                            f"{latitude},{longitude}", file_link, gmaps_link, "Default"
                                        ])

                                        # Hapus data pending
                                        del pending_data[user_id]

                                        # Hapus file temporary
                                        if file_path and os.path.exists(file_path):
                                            os.remove(file_path)

                                        await event.reply(
                                            f"✅ **SELAMAT Data berhasil disimpan ke spreadsheet!**\n\n"
                                            f"🏢 **Nama Usaha:** {row['usaha']}\n"
                                            f"📍 Koordinat: {latitude}, {longitude}\n"
                                            f"📊 Data lengkap telah ditambahkan\n\n"
                                            f"🎉 **Status:** Data selesai diproses"
                                        )

                                    except Exception as e:
                                        await event.reply(f"❌ Gagal menyimpan ke Google Spreadsheet: {e}")
                                else:
                                    await event.reply("❌ Format data tidak sesuai.\n\nSilakan kirim ulang data dengan format yang benar.")
                            else:
                                await event.reply("❌ Data tidak lengkap.\n\nSilakan kirim foto dan caption terlebih dahulu.")

                        return

                    # Jika tidak ada data pending, cek data yang sudah ada di sheet
                    else:
                        # Define expected headers to avoid duplicate issues
                        expected_headers = [
                            'No', 'Timestamp', 'ID', 'Nama', 'STO', 'Cluster', 'Nama Usaha',
                            'PIC', 'HP/WA', 'Internet Existing', 'Biaya Internet', 'VOC',
                            'Lokasi', 'Foto', 'Link Gmaps', 'Validitas'
                        ]
                        records = sheet.get_all_records(expected_headers=expected_headers)
                        row_idx = None
                        for idx, row in enumerate(records, start=2):  # start=2 karena header di baris 1
                            if str(row.get('ID', '')) == user_id:
                                row_idx = idx
                        if row_idx:
                            # Generate Google Maps link from coordinates
                            gmaps_link = get_gmaps_link_from_coords(latitude, longitude)

                            # Update kolom lokasi (kolom ke-13) dengan "latitude,longitude"
                            sheet.update_cell(row_idx, 13, f"{latitude},{longitude}")
                            # Update kolom Link Gmaps (kolom ke-15) dengan link Google Maps
                            sheet.update_cell(row_idx, 15, gmaps_link)
                            await event.reply(
                                f"✅ **Koordinat berhasil ditambahkan!**\n\n"
                                f"📍 Lokasi: {latitude}, {longitude}\n"
                                f"📊 Data telah dilengkapi dengan koordinat"
                            )
                        else:
                            await event.reply(
                                "❌ **Tidak dapat menambahkan koordinat!**\n\n"
                                "Tidak ditemukan data sebelumnya untuk user ini.\n\n"
                                "📋 **Langkah yang benar:**\n"
                                "1. Kirim data dengan Link Google Maps yang valid, ATAU\n"
                                "2. Kirim data tanpa Link Gmaps, kemudian share lokasi"
                            )

                except Exception as e:
                    await event.reply(f"❌ Gagal menyimpan lokasi ke Google Spreadsheet: {e}")
                return

    except Exception as e:
        await event.reply(f"❌ Terjadi error pada bot: {e}")

@client.on(events.NewMessage(pattern=r'^/format$', incoming=True))
async def format_handler(event):
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

@client.on(events.NewMessage(pattern=r'^/help$', incoming=True))
async def help_handler(event):
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
            "• Ketik /start untuk menghapus data sementara\n"
            "• Ketik /clear untuk menghapus data sementara\n\n"
            "📊 **Cek status:**\n"
            "• Ketik /status untuk melihat data sementara\n\n"
            "🔗 **CARA MENDAPATKAN LINK GOOGLE MAPS:**\n"
            "1. Buka Google Maps\n"
            "2. Cari lokasi yang diinginkan\n"
            "3. Klik Share → Copy link\n"
            "4. Paste di chat bot\n\n"
            "📍 **CARA SHARE LOKASI:**\n"
            "1. Kirim data terlebih dahulu\n"
            "2. Kemudian share lokasi Anda\n"
            "3. Data akan otomatis lengkap\n\n"
            "📝 **FORMAT DATA:**\n"
            "Ketik /format untuk melihat format yang benar"
        )
        await event.reply(help_text)

@client.on(events.NewMessage(pattern=r'^/start$', incoming=True))
async def start_handler(event):
    if event.is_private:
        user_id = str(event.sender_id)
        
        # Hapus data pending jika ada
        if user_id in pending_data:
            old_file_path = pending_data[user_id].get('file_path')
            if old_file_path and os.path.exists(old_file_path):
                os.remove(old_file_path)
            del pending_data[user_id]
            await event.reply("🗑️ **Data sementara Anda telah dihapus!**\n\nBot siap menerima data baru.\n\n📋 **Cara mengisi data:**\n\n1. Kirim foto terlebih dahulu, ATAU\n2. Kirim caption terlebih dahulu\n3. Kemudian kirim bagian yang kurang\n4. Share lokasi atau kirim Link Google Maps\n\n💡 **Command yang tersedia:**\n• /format - Format pengisian data\n• /help - Bantuan lengkap\n• /status - Cek status data sementara\n• /clear - Hapus data sementara")
        else:
            await event.reply("🤖 **Selamat datang di bot YOVI!**\n\nBot siap menerima data.\n\n📋 **Cara mengisi data:**\n\n1. Kirim foto terlebih dahulu, ATAU\n2. Kirim caption terlebih dahulu\n3. Kemudian kirim bagian yang kurang\n4. Share lokasi atau kirim Link Google Maps\n\n💡 **Command yang tersedia:**\n• /format - Format pengisian data\n• /help - Bantuan lengkap\n• /status - Cek status data sementara\n• /clear - Hapus data sementara")
        
        # Tandai user sudah /start
        user_started[user_id] = True

@client.on(events.NewMessage(pattern=r'^/status$', incoming=True))
async def status_handler(event):
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
                # Cek apakah ada Link Google Maps yang valid
                caption_text = pending.get('data', '')
                match = pattern.search(caption_text)
                if match:
                    row = match.groupdict()
                    link_gmaps = row.get('link_gmaps', '').strip()
                    if link_gmaps and link_gmaps != "":
                        # If the link is in Markdown format [text](url), extract the url
                        md_match = re.match(r'\[.*?\]\((https?://[^\)]+)\)', link_gmaps)
                        if md_match:
                            link_gmaps = md_match.group(1)
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
                # Cek apakah ada Link Google Maps yang valid
                caption_text = pending.get('data', '')
                match = pattern.search(caption_text)
                if match:
                    row = match.groupdict()
                    link_gmaps = row.get('link_gmaps', '').strip()
                    if link_gmaps and link_gmaps != "":
                        # If the link is in Markdown format [text](url), extract the url
                        md_match = re.match(r'\[.*?\]\((https?://[^\)]+)\)', link_gmaps)
                        if md_match:
                            link_gmaps = md_match.group(1)
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

@client.on(events.NewMessage(pattern=r'^/clear$', incoming=True))
async def clear_handler(event):
    if event.is_private:
        user_id = str(event.sender_id)
        
        if user_id not in user_started:
            await event.reply("⚠️ **Silakan ketik /start terlebih dahulu!**\n\nBot belum siap menerima data.\n\nKetik /start untuk memulai.")
            return
        
        if user_id in pending_data:
            old_file_path = pending_data[user_id].get('file_path')
            if old_file_path and os.path.exists(old_file_path):
                os.remove(old_file_path)
            del pending_data[user_id]
            await event.reply("Silakan kirim data baru.")
        else:
            await event.reply("📭 **Tidak ada data sementara untuk dihapus.**\n\nSilakan kirim foto atau caption untuk memulai.")

if __name__ == "__main__":
    print("Bot is running...")
    try:
        client.run_until_disconnected()
    except Exception as e:
        print(f"Fatal error: {e}")