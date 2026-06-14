import re
import spacy
import datetime
import logging
from typing import List, Dict, Any, Tuple, Optional
from geopy.distance import geodesic
import spacy.cli
from geocoder import HistoricalGeocoder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nlp_engine")

# Try loading spaCy, download if model not found, fallback to regex if download fails.
_NLP = None
def get_spacy_nlp():
    global _NLP
    if _NLP is not None:
        return _NLP
    
    model_name = "en_core_web_sm"
    try:
        logger.info(f"Loading spaCy model: {model_name}...")
        _NLP = spacy.load(model_name)
    except OSError:
        logger.warning(f"spaCy model {model_name} not found. Falling back to Rule-based NLP.")
        _NLP = None
    return _NLP


# Month map for date normalization
MONTHS_MAP = {
    "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, 
    "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, 
    "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11, 
    "dec": 12, "december": 12
}

def parse_date_string(date_str: str) -> Tuple[int, int, int]:
    """
    Parses a date string and returns a sortable tuple: (year, month, day).
    Defaults missing components to 1.
    """
    date_clean = date_str.lower().strip()
    
    # 1. Match DD Month YYYY (e.g. "14 October 1066" or "25 December 1066")
    pattern_dmy = r"\b(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{3,4})\b"
    match = re.search(pattern_dmy, date_clean)
    if match:
        day = int(match.group(1))
        month = MONTHS_MAP.get(match.group(2), 1)
        year = int(match.group(3))
        return year, month, day

    # 2. Match Month YYYY (e.g. "September 1066")
    pattern_my = r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{3,4})\b"
    match = re.search(pattern_my, date_clean)
    if match:
        month = MONTHS_MAP.get(match.group(1), 1)
        year = int(match.group(2))
        return year, month, 1

    # 3. Match YYYY (e.g. "1066" or "in 1066")
    pattern_y = r"\b(1\d{3}|20\d{2}|\d{3})\b"
    match = re.search(pattern_y, date_clean)
    if match:
        year = int(match.group(1))
        return year, 1, 1

    return 9999, 12, 31  # Sort to the end if unparseable


class SpatiotemporalExtractor:
    """
    NLP parser designed to extract historical events, dates, locations,
    and narrative motion vectors from raw text.
    """
    def __init__(self, geocoder: HistoricalGeocoder):
        self.geocoder = geocoder
        self.use_spacy = True

    def extract_sentences(self, text: str) -> List[str]:
        """Splits narrative into logical sentences using spaCy or simple splitters."""
        nlp = get_spacy_nlp() if self.use_spacy else None
        if nlp:
            doc = nlp(text)
            return [sent.text.strip() for sent in doc.sents if sent.text.strip()]
        else:
            # Simple sentence splitting fallback
            # Splits on . ! ? followed by space and Capital Letter
            sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text.replace('\n', ' '))
            return [s.strip() for s in sentences if s.strip()]

    def extract_date_from_sentence(self, sentence: str) -> Optional[str]:
        """Extracts date strings using regular expressions."""
        # Check DD Month YYYY
        pattern_dmy = r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{3,4}\b"
        match = re.search(pattern_dmy, sentence, re.IGNORECASE)
        if match:
            return match.group(0)

        # Check Month YYYY
        pattern_my = r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{3,4}\b"
        match = re.search(pattern_my, sentence, re.IGNORECASE)
        if match:
            return match.group(0)

        # Check raw 3/4-digit years (e.g. 1066, 1812)
        pattern_y = r"\b(in|during|around|by)?\s+(\d{3,4})\b"
        match = re.search(pattern_y, sentence, re.IGNORECASE)
        if match:
            return match.group(0)

        return None

    def extract_locations_from_sentence(self, sentence: str) -> List[str]:
        """Extracts candidate location names using spaCy NER, known fallbacks, and filters them."""
        nlp = get_spacy_nlp() if self.use_spacy else None
        locations = []
        
        # Blacklist of generic location phrases to skip
        blacklist = {"south coast", "north coast", "east coast", "west coast", 
                     "northern england", "southern england", "neman river", 
                     "remnants", "remnant", "south", "north", "east", "west",
                     "silk road", "channel", "english channel", "sea", "ocean",
                     "england", "russia", "france", "china"}
        
        # 1. First extract using spaCy NER if available
        if nlp:
            doc = nlp(sentence)
            for ent in doc.ents:
                if ent.label_ in ["GPE", "LOC", "FAC"]:
                    loc_name = ent.text.strip().strip(",.!?\"'")
                    if loc_name.lower().startswith("the "):
                        loc_name = loc_name[4:]
                    if loc_name.lower() in blacklist:
                        continue
                    if loc_name and loc_name not in locations:
                        locations.append(loc_name)
        else:
            # Fallback Rule-based Extraction using capitalized words
            # Skip phrases containing titles, names, months, prepositions, or pronouns
            non_location_words = {
                "harold", "william", "edward", "godwinson", "king", "duke", "conqueror", 
                "harald", "hardrada", "napoleon", "confessor", "lord", "earl", "pope", 
                "queen", "prince", "emperor", "grand", "grande", "armée", "armėe",
                "january", "february", "march", "april", "may", "june", "july", "august", 
                "september", "october", "november", "december", "in", "on", "at", "by", 
                "during", "under", "through", "while", "meanwhile", "he", "she", "they",
                "immediately", "hearing", "french", "normans", "norman", "english", "russians", "norwegian",
                "following", "monarch", "his", "her", "their", "our", "we", "i", "you"
            }
            words = re.findall(r"\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b", sentence)
            for word in words:
                word_clean = word.strip().strip(",.!?\"'")
                # Split phrase into individual words to check
                sub_words = [w.lower() for w in re.split(r'\s+', word_clean)]
                if any(sw in non_location_words for sw in sub_words):
                    continue
                if word_clean.lower() in blacklist:
                    continue
                if word_clean not in locations:
                    locations.append(word_clean)

        # 2. Cross-reference with known historical fallbacks (case-insensitive substring word match)
        from geocoder import HISTORICAL_FALLBACKS
        for fallback_key in HISTORICAL_FALLBACKS.keys():
            pattern = rf"\b{re.escape(fallback_key)}\b"
            if re.search(pattern, sentence, re.IGNORECASE):
                match = re.search(pattern, sentence, re.IGNORECASE)
                original_cased = match.group(0)
                
                # Check if this location is already represented
                already_present = False
                for loc in locations:
                    if loc.lower() == fallback_key.lower():
                        already_present = True
                        break
                
                if not already_present and fallback_key.lower() not in blacklist:
                    locations.append(original_cased)

        # Deduplicate: remove locations that are substrings of other longer locations
        locations.sort(key=len, reverse=True)
        filtered_locs = []
        for loc in locations:
            is_sub = False
            for longer_loc in filtered_locs:
                if loc.lower() in longer_loc.lower():
                    is_sub = True
                    break
            if not is_sub:
                filtered_locs.append(loc)
                
        # Re-sort to preserve original order of appearance in the sentence
        appearance_order = {l: sentence.lower().find(l.lower()) for l in filtered_locs}
        filtered_locs.sort(key=lambda x: appearance_order.get(x, 0))

        # Filter country names if a more specific location exists in the same list
        countries = {"england", "norway", "denmark", "russia", "france", "china", "persia"}
        has_specific = any(loc.lower() not in countries for loc in filtered_locs)
        if has_specific:
            filtered_locs = [loc for loc in filtered_locs if loc.lower() not in countries]

        return filtered_locs

    def classify_faction(self, sentence: str, location: Optional[str], text_context: str = "") -> str:
        """
        Classifies the faction/army for a given event sentence.
        """
        sentence_lc = sentence.lower()
        location_lc = (location or "").lower()
        text_lc = text_context.lower()
        
        # 1. Check if the text matches the Norman Conquest
        is_norman_conquest = "hastings" in text_lc or "harold" in text_lc or "william" in text_lc or "1066" in text_lc
        is_napoleon = "napoleon" in text_lc or "grande armée" in text_lc or "1812" in text_lc or "berezina" in text_lc
        
        if is_norman_conquest:
            # Factions: "Anglo-Saxon (Harold Godwinson)", "Norman (William of Normandy)", "Norwegian (Harald Hardrada)"
            # Checks for Norwegians first (Harald Hardrada, Norway)
            if any(kw in sentence_lc or kw in location_lc for kw in ["hardrada", "norway", "norwegian", "fulford"]):
                return "Norwegian (Harald Hardrada)"
            
            # Checks for Normans (William, Normandy, Saint-Valery, Pevensey, Hastings, Kent, Westminster Abbey)
            if any(kw in sentence_lc or kw in location_lc for kw in ["william", "normandy", "norman", "saint-valery", "pevensey", "hastings", "kent", "abbey"]):
                return "Norman (William of Normandy)"
                
            # Checks for Anglo-Saxons (Edward, Confessor, Harold, Godwinson, Stamford Bridge, Westminster)
            if any(kw in sentence_lc or kw in location_lc for kw in ["harold", "godwinson", "edward", "confessor", "westminster", "stamford bridge"]):
                return "Anglo-Saxon (Harold Godwinson)"
                
            # Default fallback for Norman Conquest
            return "Anglo-Saxon (Harold Godwinson)"
            
        elif is_napoleon:
            # Factions: "Grande Armée (French)", "Russian Empire"
            # Checks for Russians (Russian, Borodino, Moscow, Maloyaroslavets, Berezina)
            if any(kw in sentence_lc or kw in location_lc for kw in ["russian", "russians", "burning", "deserted", "ablaze", "withdraw", "borodino", "moscow", "maloyaroslavets", "berezina"]):
                if "entered moscow" in sentence_lc or "retreat from moscow" in sentence_lc:
                    return "Grande Armée (French)"
                return "Russian Empire"
            # Default
            return "Grande Armée (French)"
            
        # Default for other narratives
        return "Main Narrative"

    def process_narrative(self, raw_text: str) -> List[Dict[str, Any]]:
        """
        Parses raw text, links dates and locations, geocodes coordinates,
        and returns a sorted timeline of spatiotemporal events with faction assignments.
        """
        sentences = self.extract_sentences(raw_text)
        events = []
        
        current_date = None
        current_date_str = "Unknown Date"
        
        for index, sentence in enumerate(sentences):
            # 1. Extract dates
            date_found = self.extract_date_from_sentence(sentence)
            if date_found:
                current_date_str = date_found
                current_date = parse_date_string(date_found)
            
            # 2. Extract locations
            locations = self.extract_locations_from_sentence(sentence)
            
            # 3. Create events for found locations
            if locations:
                for loc in locations:
                    coords = self.geocoder.geocode(loc)
                    if coords:
                        faction = self.classify_faction(sentence, loc, raw_text)
                        events.append({
                            "id": len(events) + 1,
                            "sentence_idx": index,
                            "date_str": current_date_str,
                            "sort_key": current_date if current_date else (9999, 12, 31),
                            "location": loc,
                            "coords": coords,
                            "sentence": sentence,
                            "summary": sentence[:150] + "..." if len(sentence) > 150 else sentence,
                            "faction": faction
                        })
            else:
                # If there is a date but no location, and we are not starting, see if we can anchor it
                # to the last known location, or save it as a date-anchor event without coords (will not plot on map).
                if date_found:
                    faction = self.classify_faction(sentence, None, raw_text)
                    events.append({
                        "id": len(events) + 1,
                        "sentence_idx": index,
                        "date_str": current_date_str,
                        "sort_key": current_date,
                        "location": None,
                        "coords": None,
                        "sentence": sentence,
                        "summary": sentence[:150] + "..." if len(sentence) > 150 else sentence,
                        "faction": faction
                    })

        # Sort events chronologically based on their parsed dates
        events.sort(key=lambda x: (x["sort_key"] if x["sort_key"] else (9999, 12, 31), x["sentence_idx"]))

        # Remove duplicate successive locations on the same date/sentence to avoid map crowding
        filtered_events = []
        seen = set()
        for ev in events:
            # We want unique combinations of Date + Location
            key = (ev["date_str"], ev["location"])
            if key not in seen:
                seen.add(key)
                filtered_events.append(ev)

        # Recalculate IDs after sorting
        for idx, ev in enumerate(filtered_events):
            ev["id"] = idx + 1

        return filtered_events

    def calculate_motion_statistics(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Computes motion vectors (distance, speed, and heading) between sequential geocoded points
        within the same faction/group, ensuring historical relevance.
        """
        # Group events by faction
        factions_data = {}
        for ev in events:
            if ev["coords"] is not None:
                faction = ev.get("faction", "Main Narrative")
                if faction not in factions_data:
                    factions_data[faction] = []
                factions_data[faction].append(ev)
                
        motion_vectors = []
        for faction, faction_events in factions_data.items():
            for i in range(len(faction_events) - 1):
                start_event = faction_events[i]
                end_event = faction_events[i+1]
                
                p1 = start_event["coords"]
                p2 = end_event["coords"]
                
                # Distance in km
                distance = round(geodesic(p1, p2).kilometers, 2)
                
                motion_vectors.append({
                    "from_id": start_event["id"],
                    "to_id": end_event["id"],
                    "from_loc": start_event["location"],
                    "to_loc": end_event["location"],
                    "from_date": start_event["date_str"],
                    "to_date": end_event["date_str"],
                    "coords_from": p1,
                    "coords_to": p2,
                    "distance_km": distance,
                    "faction": faction
                })
                
        # Sort motion vectors by to_id to keep them in order of the timeline
        motion_vectors.sort(key=lambda x: x["to_id"])
        return motion_vectors


# Preset Archives Data
PRESETS = {
    "The Norman Conquest (1066)": """In January 1066, King Edward the Confessor died in London. Immediately, Harold Godwinson was crowned King of England at Westminster.
Meanwhile, across the English Channel, William, Duke of Normandy, claimed the English throne. He began preparing a massive invasion fleet in Normandy.
In September 1066, Harald Hardrada of Norway invaded northern England. He sailed his fleet to York.
On 20 September 1066, Harald Hardrada defeated the local English forces at the Battle of Fulford near York.
Hearing this, King Harold Godwinson marched north from London to defend his crown. On 25 September 1066, Harold surprised and decisively defeated the Norwegian invaders at Stamford Bridge, killing Harald Hardrada.
While King Harold was in the north, Duke William's fleet set sail from Saint-Valery-sur-Somme.
On 28 September 1066, William's invasion force landed at Pevensey on the south coast of England.
William established a camp and built a wooden fort nearby at Hastings.
King Harold rushed back south with his exhausted army. On 14 October 1066, the English and Norman armies clashed at the Battle of Hastings (near modern Battle). Harold Godwinson was killed, and the Normans won a decisive victory.
Following his victory, William marched around Kent and up towards London, securing the submission of the English nobles.
On 25 December 1066, William the Conqueror was crowned King of England at Westminster Abbey.""",

    "Napoleon's Russian Campaign (1812)": """In June 1812, Napoleon's Grande Armée crossed the Neman River at Kaunas to begin the invasion of Russia.
By July 1812, the French forces occupied Vilnius, but the Russian armies retreated, burning resources.
In August 1812, a major clash occurred at Smolensk, resulting in a French victory but the city was burned.
On 7 September 1812, the bloody Battle of Borodino was fought near Moscow. Both sides suffered heavy casualties, and the Russians withdrew.
On 14 September 1812, Napoleon entered Moscow, finding it deserted and set ablaze by the Russians.
In October 1812, realizing he could not sustain his army through winter, Napoleon began his retreat from Moscow.
On 24 October 1812, the Battle of Maloyaroslavets forced the French onto the devastated northern route.
In November 1812, the French rear guard fought desperately at Vyazma.
Between 26 and 29 November 1812, the remnants of the Grande Armée crossed the freezing Berezina River, suffering catastrophic losses.
By December 1812, the French survivors recrossed the border, ending the disastrous campaign.""",

    "Marco Polo's Journey to China (1271-1295)": """In 1271, young Marco Polo set sail from Venice with his father and uncle.
They first stopped in Acre to receive letters from the Pope, and then visited Jerusalem.
From Jerusalem, the Polos travelled overland to Tabriz, a major Persian trade center.
They headed south to the port of Hormuz to take a ship, but changed their minds and decided to go overland.
They marched through Khorasan and reached Balkh, a famous ancient city.
They crossed the Pamir Mountains and arrived in Kashgar, a key Silk Road oasis.
They traversed the dangerous Taklamakan Desert and passed through Lop Nor.
In 1275, they reached Dunhuang and were welcomed.
Eventually, they arrived at Shangdu, the summer palace of Kublai Khan.
They then travelled to Cambaluc (modern Beijing), where Marco Polo entered the service of the Emperor.
After 17 years in China, the Polos returned by sea, stopping in Hangzhou and travelling back to Venice in 1295."""
}
