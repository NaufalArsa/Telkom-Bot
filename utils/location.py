import re
import requests
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

def get_gmaps_link_from_coords(lat: float, lon: float) -> str:
    """Generate Google Maps link from coordinates"""
    return f"https://www.google.com/maps?q={lat},{lon}"

def extract_lat_lng_with_selenium(short_url: str) -> Tuple[Optional[float], Optional[float]]:
    """Extract lat/lng from Google Maps short link using Selenium (headless) with webdriver-manager."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        import time
        options = Options()
        options.add_argument("--headless")
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(short_url)
        time.sleep(3)  # Wait for redirect and JS
        current_url = driver.current_url
        driver.quit()
        match = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", current_url)
        if match:
            lat, lng = match.groups()
            return float(lat), float(lng)
    except Exception as e:
        logger.error(f"Selenium error extracting coordinates from link {short_url}: {e}")
    return None, None

def extract_coords_from_gmaps_link(link: str) -> Tuple[Optional[float], Optional[float]]:
    """Extract latitude and longitude from Google Maps short or long link. Fallback to Selenium if needed."""
    if not link or not link.strip():
        return None, None
    try:
        # follow redirects to get the final URL page
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        response = requests.get(link, headers=headers, allow_redirects=True, timeout=10)
        html = response.text
        # Try to extract lat,lng from embed or preview URLs
        match = re.search(
            r"https://www\.google\.com/maps/preview/place/.*?@(-?\d+\.\d+),(-?\d+\.\d+)",
            html
        )
        if match:
            lat, lng = match.groups()
            return float(lat), float(lng)
        # fallback: try plain lat,lng patterns in URL or page
        match2 = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", html)
        if match2:
            lat, lng = match2.groups()
            return float(lat), float(lng)
    except Exception as e:
        logger.error(f"Error extracting coordinates from link {link}: {e}")
    # Fallback to Selenium if requests/regex failed
    return extract_lat_lng_with_selenium(link)

def process_coordinates(lat: float, lon: float) -> Tuple[str, str]:
    """Process coordinates and return location string and Google Maps link"""
    location_coords = f"{lat},{lon}"
    gmaps_link = get_gmaps_link_from_coords(lat, lon)
    return location_coords, gmaps_link 