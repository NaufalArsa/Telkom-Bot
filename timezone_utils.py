import pytz
from datetime import datetime

# Set the timezone for Indonesia (UTC+7)
INDONESIA_TIMEZONE = pytz.timezone('Asia/Jakarta')

# Function to get current time in Indonesia timezone
def get_current_time():
    """Get current time in Indonesia timezone"""
    return datetime.now(INDONESIA_TIMEZONE)

# Function to format timestamp in Indonesia timezone
def format_timestamp():
    """Format current timestamp in Indonesia timezone"""
    return get_current_time().strftime("%Y-%m-%d %H:%M:%S")

# Function to convert a datetime to Indonesia timezone
def convert_to_local_timezone(dt):
    """Convert a datetime to Indonesia timezone"""
    if dt.tzinfo is None:
        # If no timezone info, assume it's UTC
        dt = dt.replace(tzinfo=pytz.UTC)
    return dt.astimezone(INDONESIA_TIMEZONE) 