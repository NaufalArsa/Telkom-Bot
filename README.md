# 🤖 YOVI Bot Dashboard

A comprehensive Telegram bot with a Streamlit web dashboard for managing and monitoring bot activities.

## 📋 Features

### Bot Features
- **Telegram Bot Integration**: Handles photo and text messages
- **Google Sheets Integration**: Automatically saves data to Google Sheets
- **Potensi & ODP Lookup**: Finds nearest Potensi (Hotel, Perusahaan, Tempat Wisata, Industri, Cafe/Restaurant, Rumah Sakit) and ODP using data from Google Sheets tabs
- **PSB Lookup**: Find subscribed customers for the service provided
- **Record Historical Data**: Get historical data inputted by user
- **Supabase Storage (Image Only)**: Uploads photos to Supabase storage (tabular data now uses Google Sheets)
- **Location Processing**: Extracts coordinates from Google Maps links using Python
- **Data Validation**: Validates required fields before saving
- **Multi-step Data Collection**: Allows users to send data in parts
- **Brosur Management**: Send brosur based on type (HSI, WMS, UMKM) from Supabase storage
- **PSB Search**: Search for PSB data by customer name from Google Sheets
- **Record History**: View user's input history from Google Sheets

### Dashboard Features
- **Real-time Monitoring**: Monitor bot status and activities
- **Data Visualization**: View and analyze collected data
- **Bot Controls**: Start/stop bot from web interface
- **Storage Management**: Manage Supabase storage files (images only)
- **Environment Management**: Monitor configuration status

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Google Cloud Project with APIs enabled
- Supabase project (for image storage)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/NaufalArsa/Telkom-Bot.git
cd streamlit
```

2. **Install Python dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**
Create a `.env` file in the project root:
```env
# Telegram Bot Configuration
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
BOT_TOKEN=your_bot_token

# Google Services Configuration
GOOGLE_SHEET_NAME=your_google_sheet_name
GOOGLE_CREDS_JSON={"type": "service_account", ...}

# Supabase Configuration (for image/photo storage only)
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
```

4. **Set up Google Services**
   - Create a Google Cloud Project
   - Enable Google Sheets API
   - Create a service account and download credentials
   - Share your Google Sheet with the service account email
   - **Create additional tabs in your Google Sheet:**
     - `Hotel`, `Perusahaan`, `Tempat Wisata`, `Industri`, `Cafe/Restaurant`, `Rumah Sakit`, `ODP`
     - Each tab should have appropriate headers (see Data Format section)

5. **Set up Supabase**
   - Create a Supabase project
   - Create a storage bucket named "photo"
   - Get your project URL and anon key

## 🎯 Usage

### Running the Bot Only
```bash
python bot.py
```

### Running the Dashboard
```bash
streamlit run app.py
```

The dashboard will be available at `http://localhost:8501`

### Running Both (Recommended)
```bash
# Terminal 1: Start the dashboard
streamlit run app.py

# Terminal 2: Start the bot (optional, can be started from dashboard)
python bot.py
```

## 📊 Dashboard Features

### 1. Dashboard Overview
- **Bot Status**: Real-time bot running status
- **Total Records**: Number of records in Google Sheets
- **Today's Records**: Records added today
- **Live Bot Output**: Real-time bot logs
- **Google Maps Link Processor**: Test coordinate extraction

### 2. Storage Management
- **Supabase Storage**: View and manage uploaded image files
- **File Operations**: Download, delete, view image files
- **Storage Analytics**: File count and usage

### 3. Settings
- **Environment Status**: Check configuration
- **System Information**: Python version, working directory
- **File Status**: Check required files

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `API_ID` | Telegram API ID | ✅ |
| `API_HASH` | Telegram API Hash | ✅ |
| `BOT_TOKEN` | Telegram Bot Token | ✅ |
| `GOOGLE_SHEET_NAME` | Google Sheet name | ✅ |
| `GOOGLE_CREDS_JSON` | Google service account credentials | ✅ |
| `SUPABASE_URL` | Supabase project URL (for image/photo storage only) | ✅ |
| `SUPABASE_KEY` | Supabase anon key (for image/photo storage only) | ✅ |

### Google Services Setup

1. **Google Cloud Console**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing
   - Enable Google Sheets API

2. **Service Account**
   - Go to IAM & Admin > Service Accounts
   - Create a new service account
   - Download the JSON credentials
   - Add the JSON content to `GOOGLE_CREDS_JSON`

3. **Google Sheet**
   - Create a new Google Sheet
   - Share it with the service account email (with Editor access)
   - Note the sheet name for `GOOGLE_SHEET_NAME`
   - **Add tabs for Potensi and ODP:**
     - `Hotel`, `Perusahaan`, `Tempat Wisata`, `Industri`, `Cafe/Restaurant`, `Rumah Sakit`, `ODP`
     - Each tab should have headers such as: `Nama`, `Kab/Kota`, `Alamat`, `No. Telp`, `Gmaps`, `Lat`, `Long`, `Lokasi` (for Potensi) and `ODP`, `LATITUDE`, `LONGITUDE`, `AVAI` (for ODP)

### Supabase Setup

1. **Create Supabase Project**
   - Go to [Supabase](https://supabase.com/)
   - Create a new project
   - Note your project URL and anon key

2. **Create Storage Bucket**
   - Go to Storage in your Supabase dashboard
   - Create a bucket named "photo"
   - Set appropriate permissions

## 📱 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Initialize the bot |
| `/format` | Show data format |
| `/help` | Show help information |
| `/status` | Check current data status |
| `/clear` | Clear pending data |
| `/potensi` | Cari potensi terdekat dari Google Sheets (Hotel, Perusahaan, dll) |
| `/odp` | Cari ODP terdekat dari Google Sheets tab ODP |
| `/psb [CUSTOMER_NAME]` | Mendapatkan data pelanggan sesuai dengan nama |
| `/record` | Mendapatkan informasi riwayat data yang pernah diinput |

## 📋 Data Format

The bot expects data in this format:
```
#VISIT

Nama SA/ AR: [Name]
STO: [STO Code]
Cluster: [Cluster]

Nama usaha: [Business Name]
Nama PIC: [PIC Name]
Nomor HP/ WA: [Phone Number]
Internet existing: [Internet Status]
Biaya internet existing: [Cost]
Voice of Customer: [VOC]
```

**Potensi Sheet Example:**
```
| Nama | Kab/Kota | Alamat | No. Telp | Gmaps | Lat | Long | Lokasi |
|------|----------|--------|----------|-------|-----|------|--------|
| Hotel ABC | Jakarta | Jl. Sudirman | 021-123456 | link | -6.123 | 106.456 | detail |
```

**ODP Sheet Example:**
```
| ODP | LATITUDE | LONGITUDE | AVAI |
|-----|----------|-----------|------|
| ODP-001 | -6.123 | 106.456 | 2 |
```

## 🛠️ Development

### Project Structure
```
streamlit/
├── bot.py                 # Main entry point for the Telegram bot
├── app.py                 # Streamlit dashboard web app
├── requirements.txt       # List of Python dependencies required for the project.
├── .env                   # Environment variables (API keys, tokens, config) 
├── bot.log                # Log file for bot activity, errors, and debugging information.
├── README.md              # Project documentation
├── config.py              # Centralized configuration constants 
├── handlers/              # Directory for modular bot command/data handlers.
│   ├── __init__.py            # Marks the directory as a Python package.
│   ├── command_handlers.py    # Handles generic bot commands (e.g., /start, /help).
│   ├── data_handlers.py       # Handles data-related commands or logic.
│   ├── location_handlers.py   # Handles location extraction and processing.
│   ├── odp_handlers.py        # Handles ODP-specific commands and logic.
│   ├── potensi_handlers.py    # Handles Potensi (potential customer) search and formatting.
│   ├── psb_handlers.py        # Handles PSB (customer) search and formatting.
│   ├── brosur_handlers.py     # Handles brosur (brochure) retrieval and sending.
│   ├── record_handlers.py     # Handles user record/history retrieval and formatting.
├── services/              # Directory for integrations with external services.
│   ├── __init__.py            # Marks the directory as a Python package.
│   ├── google_sheets.py       # Functions/classes for interacting with Google Sheets API.
│   ├── potensi_service.py     # Service logic for Potensi data (fetching, filtering, etc.).
│   ├── supabase_service.py    # Functions/classes for interacting with Supabase storage.
├── utils/                 # Utility/helper functions.
│   ├── __init__.py            # Marks the directory as a Python package.
│   ├── location.py            # Functions for extracting and validating coordinates.
|   |-- validation.py          # Configure regex pattern and validate data input.
```

### Adding New Features

1. **Bot Features**: Modify `bot.py`
2. **Dashboard Features**: Modify `app.py`
3. **Dependencies**: Update `requirements.txt`

### Logging
- Bot logs are saved to `bot.log`
- Dashboard shows recent logs in real-time
- Log level can be configured in `bot.py`

## 🔍 Troubleshooting

### Common Issues

1. **Bot not starting**
   - Check environment variables
   - Verify Google credentials
   - Check bot token validity

2. **Dashboard not loading data**
   - Verify Google Sheet permissions
   - Check service account access
   - Ensure sheet name and tab names are correct

3. **Upload failures (images only)**
   - Check Supabase storage permissions
   - Verify bucket exists and is named "photo"
   - Check internet connection

4. **Google Maps link processing fails**
   - Check if link is valid
   - Verify network connectivity
   - Test with `test.py` script

### Debug Mode
Enable debug logging by modifying the logging level in `bot.py`:
```python
logging.basicConfig(level=logging.DEBUG)
```

## 📈 Monitoring

### Bot Health Checks
- Dashboard shows real-time bot status
- Environment variable validation
- File existence checks
- Process monitoring

### Data Quality
- Required field validation
- Format checking
- Coordinate validation
- Duplicate detection

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Check the troubleshooting section
- Review the logs in `bot.log`
- Check the dashboard for error messages
- Ensure all environment variables are set correctly

---

**Happy Botting! 🤖✨**