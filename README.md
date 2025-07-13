# 🤖 TelkomBot Dashboard

A comprehensive Telegram bot with a Streamlit web dashboard for managing and monitoring bot activities.

## 📋 Features

### Bot Features
- **Telegram Bot Integration**: Handles photo and text messages
- **Google Sheets Integration**: Automatically saves data to Google Sheets
- **Google Drive Upload**: Uploads photos to Google Drive
- **Location Processing**: Extracts coordinates from Google Maps links
- **Data Validation**: Validates required fields before saving
- **Multi-step Data Collection**: Allows users to send data in parts

### Dashboard Features
- **Real-time Monitoring**: Monitor bot status and activities
- **Data Visualization**: View and analyze collected data
- **Bot Controls**: Start/stop bot from web interface
- **Analytics**: Charts and statistics for data analysis
- **Data Export**: Download data as CSV
- **Environment Management**: Monitor configuration status

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Node.js (for coordinate extraction)
- Google Cloud Project with APIs enabled

### Installation

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd telkombot-local
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
GOOGLE_DRIVE_FOLDER_ID=your_google_drive_folder_id
GOOGLE_SHEET_NAME=your_google_sheet_name
GOOGLE_CREDS_JSON={"type": "service_account", ...}

# Node.js Script Path
NODE_SCRIPT_PATH=path/to/your/node/script.js
```

4. **Set up Google Services**
   - Create a Google Cloud Project
   - Enable Google Sheets API and Google Drive API
   - Create a service account and download credentials
   - Share your Google Sheet with the service account email

## 🎯 Usage

### Running the Bot Only
```bash
python bot.py
```

### Running the Dashboard
```bash
streamlit run streamlit_app.py
```

The dashboard will be available at `http://localhost:8501`

### Running Both (Recommended)
```bash
# Terminal 1: Start the dashboard
streamlit run streamlit_app.py

# Terminal 2: Start the bot (optional, can be started from dashboard)
python bot.py
```

## 📊 Dashboard Features

### 1. Dashboard Overview
- **Bot Status**: Real-time bot running status
- **Total Records**: Number of records in Google Sheets
- **Recent Activity**: Latest bot activities
- **Log Viewer**: Recent bot logs

### 2. Data Viewer
- **Data Table**: View all collected data
- **Filters**: Filter by business name, STO, etc.
- **Export**: Download data as CSV
- **Refresh**: Real-time data updates

### 3. Analytics
- **Basic Statistics**: Total businesses, STOs, records
- **Charts**: Visual representation of data
- **Time Series**: Records over time
- **STO Distribution**: Records by STO

### 4. Settings
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
| `GOOGLE_DRIVE_FOLDER_ID` | Google Drive folder ID | ✅ |
| `GOOGLE_SHEET_NAME` | Google Sheet name | ✅ |
| `GOOGLE_CREDS_JSON` | Google service account credentials | ✅ |
| `NODE_SCRIPT_PATH` | Path to Node.js coordinate extraction script | ✅ |

### Google Services Setup

1. **Google Cloud Console**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing
   - Enable Google Sheets API and Google Drive API

2. **Service Account**
   - Go to IAM & Admin > Service Accounts
   - Create a new service account
   - Download the JSON credentials
   - Add the JSON content to `GOOGLE_CREDS_JSON`

3. **Google Sheet**
   - Create a new Google Sheet
   - Share it with the service account email (with Editor access)
   - Note the sheet name for `GOOGLE_SHEET_NAME`

4. **Google Drive**
   - Create a folder in Google Drive
   - Share it with the service account email (with Editor access)
   - Copy the folder ID for `GOOGLE_DRIVE_FOLDER_ID`

## 📱 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Initialize the bot |
| `/format` | Show data format |
| `/help` | Show help information |
| `/status` | Check current data status |
| `/clear` | Clear pending data |

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

## 🛠️ Development

### Project Structure
```
telkombot-local/
├── bot.py                 # Main bot file
├── streamlit_app.py       # Streamlit dashboard
├── requirements.txt       # Python dependencies
├── .env                  # Environment variables
├── bot.log              # Bot logs
└── README.md            # This file
```

### Adding New Features

1. **Bot Features**: Modify `bot.py`
2. **Dashboard Features**: Modify `streamlit_app.py`
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
   - Ensure sheet name is correct

3. **Upload failures**
   - Check Google Drive permissions
   - Verify folder ID
   - Check internet connection

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