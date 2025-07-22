import logging
from typing import Dict
from telethon import TelegramClient, events
from config import API_ID, API_HASH, BOT_TOKEN, setup_logging
from handlers.data_handlers import DataHandlers
from handlers.location_handlers import LocationHandlers
from handlers.command_handlers import CommandHandlers
from handlers.odp_handlers import ODPHandlers
from handlers.potensi_handlers import PotensiHandlers
from handlers.psb_handlers import PSBHandlers
from utils.location import extract_coords_from_gmaps_link

# Setup logging
logger = setup_logging()

# Initialize client
client = TelegramClient('bot', API_ID, API_HASH) # type: ignore

# Initialize handlers
data_handlers = DataHandlers()
location_handlers = LocationHandlers()
command_handlers = CommandHandlers()
odp_handlers = ODPHandlers()
potensi_handlers = PotensiHandlers(client)
psb_handlers = PSBHandlers(client)

# Data storage
pending_data: Dict[str, Dict] = {}
user_started: Dict[str, bool] = {}

# Main event handler
@client.on(events.NewMessage(incoming=True))
async def handler(event):
    
    try:
        if not event.is_private:
            return
        
        user_id = str(event.sender_id)
        
        # Handle commands
        if event.text and event.text.startswith('/'):
            return
        
        # Check if user has started
        if user_id not in user_started:
            await event.reply("⚠️ **Silakan ketik /start terlebih dahulu!**\n\nBot belum siap menerima data.\n\nKetik /start untuk memulai.")
            return
        
        # Handle different message types
        if event.photo and not event.text:
            await data_handlers.handle_photo_only(event, user_id, pending_data)
        elif event.photo and event.text:
            await data_handlers.handle_photo_with_caption(event, user_id, pending_data)
        elif event.text and not event.photo:
            if 'maps.google.com' in event.text or 'goo.gl/maps' in event.text or 'maps.app.goo.gl' in event.text:
                # Check potensi state first
                if await potensi_handlers.handle_gmaps_link_with_potensi(event, user_id):
                    return
                # Check ODP state
                if not await odp_handlers.handle_gmaps_link_with_odp(event, user_id):
                    await location_handlers.handle_gmaps_link(event, user_id, pending_data)
            else:
                # Check if user is selecting potensi category
                if await potensi_handlers.handle_category_selection(event, user_id):
                    return
                await data_handlers.handle_caption_only(event, user_id, pending_data)
        elif hasattr(event.message, "geo") and event.message.geo:
            # Check potensi state first
            if await potensi_handlers.handle_location_share_with_potensi(event, user_id):
                return
            # Check ODP state
            if not await odp_handlers.handle_location_share_with_odp(event, user_id):
                await location_handlers.handle_location_share(event, user_id, pending_data)
            
    except Exception as e:
        logger.error(f"Error in main handler: {e}")
        try:
            await event.reply(f"❌ Terjadi error pada bot: {e}")
        except:
            logger.error("Failed to send error message to user")

# Command handlers
@client.on(events.NewMessage(pattern=r'^/format$', incoming=True))
async def format_handler(event):
    await command_handlers.format_handler(event)

@client.on(events.NewMessage(pattern=r'^/help$', incoming=True))
async def help_handler(event):
    await command_handlers.help_handler(event)

@client.on(events.NewMessage(pattern=r'^/start$', incoming=True))
async def start_handler(event):
    await command_handlers.start_handler(event, user_started, pending_data)

@client.on(events.NewMessage(pattern=r'^/status$', incoming=True))
async def status_handler(event):
    await command_handlers.status_handler(event, user_started, pending_data)

@client.on(events.NewMessage(pattern=r'^/clear$', incoming=True))
async def clear_handler(event):
    await command_handlers.clear_handler(event, user_started, pending_data)

@client.on(events.NewMessage(pattern=r'^/odp$', incoming=True))
async def odp_command_handler(event):
    await odp_handlers.odp_command_handler(event)

@client.on(events.NewMessage(pattern=r'^/potensi$', incoming=True))
async def potensi_command_handler(event):
    await potensi_handlers.potensi_command_handler(event)

# Main execution
if __name__ == "__main__":
    logger.info("Bot is starting...")
    logger.info(f"API ID: {API_ID}")
    logger.info(f"Bot Token: {BOT_TOKEN[:10] if BOT_TOKEN else 'None'}...")
    
    try:
        logger.info("Bot is running...")
        client.start(bot_token=BOT_TOKEN) # type: ignore
        client.run_until_disconnected()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise 