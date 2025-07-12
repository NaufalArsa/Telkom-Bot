# TelkomBot Local / Production

A Telegram bot for collecting and storing customer visit data, including photos, captions, and location, into a Google Spreadsheet and Google Drive.

## Features

- Accepts photo, caption, and location data from users
- Validates and parses structured captions
- Uploads photos to Google Drive
- Stores all data in a Google Spreadsheet
- Supports Google Maps links and direct location sharing
- Handles incomplete submissions and guides users to complete their data

## Requirements

- Python 3.8+
- [Node.js](https://nodejs.org/) (for coordinate extraction)
- Telegram Bot Token
- Google Cloud Service Account credentials (JSON)
- Google Spreadsheet and Drive access

## Setup

1. **Clone this repository** and navigate to the project folder.

2. **Install dependencies:**
    ```sh
    pip install -r requirements.txt
    ```

3. **Create a `.env` file** in the project root:
    ```
    TELEGRAM_API_ID=your_telegram_api_id
    TELEGRAM_API_HASH=your_telegram_api_hash
    TELEGRAM_BOT_TOKEN=your_telegram_bot_token
    GOOGLE_DRIVE_FOLDER_ID=your_drive_folder_id
    GOOGLE_SHEET_NAME=your_google_sheet_name
    GOOGLE_CREDENTIALS_FILE=gcredentials.json
    NODE_SCRIPT_PATH=expand.js
    ```

4. **Place your Google credentials JSON** (service account) as `gcredentials.json` in the project root.

5. **Ensure your Google Sheet and Drive folder** are shared with the service account email.

6. **Place your Node.js script** (for coordinate extraction) as `expand.js` in the project root.

## Running the Bot

```sh
python bot_production.py
```

## Usage

- Send `/start` to begin.
- Send a photo, caption, or both.
- Share your location or send a Google Maps link to complete your submission.
- Use `/format` to see the required caption format.
- Use `/help` for detailed instructions.

## Environment Variables

All sensitive configuration is managed via the `.env` file. **Never share your `.env` or credentials publicly.**

## License

MIT License

---

**For more info or troubleshooting, see the code comments or