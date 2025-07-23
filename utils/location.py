import re
import requests
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

def get_gmaps_link_from_coords(lat: float, lon: float) -> str:
    """Generate Google Maps link from coordinates"""
    return f"https://www.google.com/maps?q={lat},{lon}"

def extract_coords_from_gmaps_link(link: str) -> Tuple[Optional[float], Optional[float]]:
    """Extract latitude and longitude from Google Maps short or long link."""
    if not link or not link.strip():
        return None, None
    try:
        # follow redirects to get the final URL page
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        response = requests.get(link, headers=headers, allow_redirects=True, timeout=50)
        html = response.text
        logger.info(f"HTML: {html}")
        # Try to extract lat,lng from embed or preview URLs
        match = re.search(
            r"https://www\.google\.com/maps/preview/place/.*?@(-?\d+\.\d+),(-?\d+\.\d+)",
            html
        )
        if match:
            lat, lng = match.groups()
            return float(lat), float(lng)
        # fallback: try plain lat,lng patterns in URL or page
        final_url = response.url
        match2 = re.search(r"[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)", final_url)
        if match2:
            lat, lng = match2.groups()
            return float(lat), float(lng)
    except Exception as e:
        logger.error(f"Error extracting coordinates from link {link}: {e}")
    # Fallback to Selenium if requests/regex failed
    return None, None

def process_coordinates(lat: float, lon: float) -> Tuple[str, str]:
    """Process coordinates and return location string and Google Maps link"""
    location_coords = f"{lat},{lon}"
    gmaps_link = get_gmaps_link_from_coords(lat, lon)
    return location_coords, gmaps_link 