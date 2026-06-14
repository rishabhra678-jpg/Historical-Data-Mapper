import os
import sqlite3
import logging
from typing import Optional, Tuple, Dict
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("geocoder")

# Predefined coordinates dictionary for common historical locations.
# Essential for offline capabilities, rate-limit avoidance, and resolving ambiguous names.
HISTORICAL_FALLBACKS: Dict[str, Tuple[float, float]] = {
    # Norman Conquest 1066 Sites
    "normandy": (49.1804, -0.3703),           # Caen, Capital of Normandy
    "saint-valery-sur-somme": (50.1843, 1.6294), # Port where William's fleet gathered
    "pevensey": (50.8197, 0.3347),            # William's landing site in England
    "hastings": (50.8542, 0.5735),            # Battle of Hastings region
    "battle": (50.9161, 0.4851),              # Actual site of the Battle of Hastings (Battle Abbey)
    "york": (53.9599, -1.0873),               # City of York
    "fulford": (53.9317, -1.0667),            # Battle of Fulford
    "stamford bridge": (53.9877, -0.9022),     # Battle of Stamford Bridge
    "london": (51.5074, -0.1278),             # Capital city
    "westminster": (51.4996, -0.1348),        # Coronation site (Westminster Abbey)
    "waltham abbey": (51.6888, -0.0102),       # Burial site of King Harold II
    "norway": (60.4720, 8.4689),              # Harald Hardrada's kingdom
    "denmark": (56.2639, 9.5018),             # King Sweyn's origin
    "rouen": (49.4431, 1.0993),               # Death location of William the Conqueror
    "caen": (49.1804, -0.3703),               # Ducal castle of William
    "fecamp": (49.7565, 0.3644),              # Fécamp Abbey

    # General/Napoleon Russian Campaign 1812 Sites
    "moscow": (55.7558, 37.6173),
    "borodino": (55.5283, 35.8208),
    "smolensk": (54.7826, 32.0453),
    "vilnius": (54.6872, 25.2797),
    "kaunas": (54.8985, 23.9036),
    "krasny": (54.5619, 31.4253),
    "vyazma": (55.2104, 34.2984),
    "maloyaroslavets": (55.0136, 36.4678),
    "berezina": (54.2694, 28.6011),
    "st. petersburg": (59.9343, 30.3351),
    "saint petersburg": (59.9343, 30.3351),
    "paris": (48.8566, 2.3522),

    # Marco Polo / Silk Road Sites
    "venice": (45.4408, 12.3155),
    "acre": (32.9331, 35.0827),
    "jerusalem": (31.7683, 35.2137),
    "tabriz": (38.0962, 46.2738),
    "hormuz": (27.0983, 56.4622),
    "balkh": (36.7581, 66.8989),
    "kashgar": (39.4677, 75.9896),
    "lop nor": (40.1667, 90.5000),
    "dunhuang": (40.1421, 94.6618),
    "shangdu": (42.2667, 116.1833),
    "beijing": (39.9042, 116.4074),
    "cambaluc": (39.9042, 116.4074),           # Historical name for Beijing
    "hangzhou": (30.2741, 120.1551),
}


class HistoricalGeocoder:
    """
    Geocodes location names to lat/lon coordinates with a SQLite caching database
    and pre-configured fallback dictionary for historical accuracy.
    """
    def __init__(self, db_path: str = "geocoding_cache.db"):
        self.db_path = db_path
        self._init_db()
        self.geolocator = Nominatim(user_agent="historical_spatiotemporal_dashboard")

    def _init_db(self):
        """Initializes the SQLite cache table."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS geocoding_cache (
                    query_name TEXT PRIMARY KEY,
                    latitude REAL,
                    longitude REAL
                )
                """
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize caching database: {e}")

    def _get_from_cache(self, query: str) -> Optional[Tuple[float, float]]:
        """Retrieves coordinates from the SQLite cache database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT latitude, longitude FROM geocoding_cache WHERE query_name = ?",
                (query.lower().strip(),)
            )
            result = cursor.fetchone()
            conn.close()
            if result:
                return result[0], result[1]
        except sqlite3.Error as e:
            logger.error(f"Error reading from cache database: {e}")
        return None

    def _save_to_cache(self, query: str, lat: float, lon: float):
        """Saves coordinates to the SQLite cache database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO geocoding_cache (query_name, latitude, longitude) VALUES (?, ?, ?)",
                (query.lower().strip(), lat, lon)
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.error(f"Error saving to cache database: {e}")

    def geocode(self, location_name: str) -> Optional[Tuple[float, float]]:
        """
        Geocodes a location name to (latitude, longitude) coordinates.
        Checks cache database -> fallback dictionary -> external API.
        """
        clean_name = location_name.strip()
        if not clean_name:
            return None

        # 1. Check local DB cache
        cached = self._get_from_cache(clean_name)
        if cached:
            logger.info(f"Geocoding [Cache Hit]: '{clean_name}' -> {cached}")
            return cached

        # 2. Check historical fallbacks (helps with ancient/historical names)
        lookup_key = clean_name.lower()
        if lookup_key in HISTORICAL_FALLBACKS:
            coords = HISTORICAL_FALLBACKS[lookup_key]
            logger.info(f"Geocoding [Fallback Match]: '{clean_name}' -> {coords}")
            self._save_to_cache(clean_name, coords[0], coords[1])
            return coords

        # 3. Use External Nominatim Geocoder API
        try:
            logger.info(f"Geocoding [API Request]: '{clean_name}'...")
            location = self.geolocator.geocode(clean_name, timeout=5)
            if location:
                coords = (location.latitude, location.longitude)
                self._save_to_cache(clean_name, coords[0], coords[1])
                logger.info(f"Geocoding [API Success]: '{clean_name}' -> {coords}")
                return coords
            else:
                logger.warning(f"Geocoding [Not Found]: '{clean_name}' on Nominatim")
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.error(f"Geocoding [API Exception] for '{clean_name}': {e}")
            # Try a partial string search for historical places (e.g. "Battle of Hastings" -> "Hastings")
            for fallback_key, coords in HISTORICAL_FALLBACKS.items():
                if fallback_key in lookup_key or lookup_key in fallback_key:
                    logger.info(f"Geocoding [API Fail - Partial Fallback]: '{clean_name}' matched '{fallback_key}' -> {coords}")
                    self._save_to_cache(clean_name, coords[0], coords[1])
                    return coords

        return None
