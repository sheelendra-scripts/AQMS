"""Wards API — multi-ward AQI data for the map view.
Serves 12 MCD zones + ~250 individual ward readings.
"""
import math
import random
from datetime import datetime, timezone
from fastapi import APIRouter

from utils.aqi_calc import calculate_aqi, get_aqi_category

router = APIRouter(prefix="/api", tags=["wards"])

# ── Zone definitions ────────────────────────────────────────────────
ZONE_DEFS = {
    "Central":        {"lat": 28.6350, "lng": 77.2280, "radius": 0.020, "profile": "vehicle"},
    "South":          {"lat": 28.5300, "lng": 77.2200, "radius": 0.060, "profile": "vehicle"},
    "Shahdara North": {"lat": 28.6950, "lng": 77.2950, "radius": 0.035, "profile": "industrial"},
    "Shahdara South": {"lat": 28.6350, "lng": 77.3050, "radius": 0.035, "profile": "mixed"},
    "City SP":        {"lat": 28.6580, "lng": 77.2150, "radius": 0.016, "profile": "mixed"},
    "Civil Lines":    {"lat": 28.6870, "lng": 77.2200, "radius": 0.025, "profile": "clean"},
    "Karol Bagh":     {"lat": 28.6480, "lng": 77.1900, "radius": 0.022, "profile": "vehicle"},
    "Najafgarh":      {"lat": 28.5700, "lng": 77.0700, "radius": 0.060, "profile": "biomass"},
    "Narela":         {"lat": 28.7850, "lng": 77.1000, "radius": 0.050, "profile": "biomass"},
    "Rohini":         {"lat": 28.7200, "lng": 77.1250, "radius": 0.032, "profile": "construction"},
    "West":           {"lat": 28.6550, "lng": 77.1600, "radius": 0.025, "profile": "construction"},
    "Keshavpuram":    {"lat": 28.6850, "lng": 77.1500, "radius": 0.025, "profile": "vehicle"},
}

# ── Ward-to-zone mapping (all ~250 MCD wards) ─────────────────────
ZONE_WARDS = {
    "Central": [74,75,76,77,78,79,140,141,142,143,144,145,146,147,148],
    "South": list(range(149, 190)),
    "Shahdara North": list(range(224, 251)),
    "Shahdara South": list(range(190, 223)),
    "City SP": [71,72,73,80,81,82,83,84],
    "Civil Lines": [6,7,8,9,10,11,12,13,14,15,16,17,18,19,69,70],
    "Karol Bagh": [86,87,88,89,90,91,92,93,94,95,96,98,99,100,101,102,103,139],
    "Najafgarh": [104,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,129,130,131,132,133,134,135,136,138],
    "Narela": [1,2,3,4,5,20,26,27,28,29,30,31,32,33,34,35,36],
    "Rohini": [21,22,23,24,25,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54],
    "West": [55,56,57,58,59,60,61,62,63,64,65,66,67,68],
    "Keshavpuram": [85],  # remaining
}

# Ward names extracted from MCD PDF
WARD_NAMES = {
    1:"Narela",2:"Bankner",3:"Holambi Kalan",4:"Alipur",5:"Bakhtawarpur",
    6:"Burari",7:"Kadipur",8:"Mukundpur",9:"Sant Nagar",10:"Jharoda",
    11:"Timarpur",12:"Malka Ganj",13:"Mukherjee Nagar",14:"Dhirpur",
    15:"Adarsh Nagar",16:"Azadpur",17:"Bhalswa",18:"Jahangir Puri",
    19:"Sarup Nagar",20:"Samaypur Badli",21:"Rohini-A",22:"Rohini-B",
    23:"Rithala",24:"Vijay Vihar",25:"Budh Vihar",26:"Pooth Kalan",
    27:"Begumpur",28:"Shahbaad Dairy",29:"Pooth Khurd",30:"Bawana",
    31:"Nangal Thakran",32:"Kanjhawala",33:"Rani Khera",34:"Nangloi",
    35:"Mundka",36:"Nilothi",37:"Kirari",38:"Prem Nagar",39:"Mubarikpur",
    40:"Nithari",41:"Aman Vihar",42:"Mangol Puri",43:"Sultanpuri-A",
    44:"Sultanpuri-B",45:"Jawalapuri",46:"Nangloi Jat",47:"Nihal Vihar",
    48:"Guru Harkishan Nagar",49:"Mangolpuri-A",50:"Mangolpuri-B",
    51:"Rohini-C",52:"Rohini-F",53:"Rohini-E",54:"Rohini-D",
    55:"Shalimar Bagh-A",56:"Shalimar Bagh-B",57:"Pitam Pura",
    58:"Saraswati Vihar",59:"Paschim Vihar",60:"Rani Bagh",
    61:"Kohat Enclave",62:"Shakur Pur",63:"Tri Nagar",64:"Keshav Puram",
    65:"Ashok Vihar",66:"Wazir Pur",67:"Sangam Park",68:"Model Town",
    69:"Kamla Nagar",70:"Shastri Nagar",71:"Kishan Ganj",72:"Sadar Bazar",
    73:"Civil Lines",74:"Chandni Chowk",75:"Jama Masjid",76:"Chandani Mahal",
    77:"Delhi Gate",78:"Bazar Sita Ram",79:"Ballimaran",80:"Ram Nagar",
    81:"Quraish Nagar",82:"Pahar Ganj",83:"Karol Bagh",84:"Dev Nagar",
    85:"Patel Nagar",86:"East Patel Nagar",87:"Ranjeet Nagar",
    88:"Baljeet Nagar",89:"Karam Pura",90:"Moti Nagar",91:"Ramesh Nagar",
    92:"Punjabi Bagh",93:"Madipur",94:"Raghubir Nagar",95:"Vishnu Garden",
    96:"Rajouri Garden",98:"Subhash Nagar",99:"Hari Nagar",
    100:"Fateh Nagar",101:"Tilak Nagar",102:"Khyala",103:"Keshopur",
    104:"Janak Puri South",106:"Janak Puri West",107:"Vikas Puri",
    108:"Hastsal",109:"Vikas Nagar",110:"Kunwar Singh Nagar",
    111:"Baprola",112:"Sainik Enclave",113:"Mohan Garden",114:"Nawada",
    115:"Uttam Nagar",116:"Binda Pur",117:"Dabri",118:"Sagarpur",
    119:"Manglapuri",120:"Dwarka-B",121:"Dwarka-A",122:"Matiala",
    123:"Kakrola",124:"Nangli Sakrawati",125:"Chhawala",126:"Isapur",
    127:"Najafgarh",128:"Dichaon Kalan",129:"Roshan Pura",130:"Dwarka-C",
    131:"Bijwasan",132:"Kapashera",133:"Mahipalpur",134:"Raj Nagar",
    135:"Palam",136:"Madhu Vihar",138:"Sadh Nagar",139:"Naraina",
    140:"Inder Puri",141:"Rajinder Nagar",142:"Daryaganj",
    143:"Sidhartha Nagar",144:"Lajpat Nagar",145:"Andrews Ganj",
    146:"Amar Colony",147:"Kotla Mubarakpur",148:"Hauz Khas",
    149:"Malviya Nagar",150:"Green Park",151:"Munirka",152:"R.K. Puram",
    153:"Vasant Vihar",154:"Lado Sarai",155:"Mehrauli",156:"Vasant Kunj",
    157:"Aya Nagar",158:"Bhati",159:"Chhatarpur",160:"Said-ul-Ajaib",
    161:"Deoli",162:"Tigri",163:"Sangam Vihar-A",164:"Dakshin Puri",
    165:"Madangir",166:"Pushp Vihar",167:"Khanpur",168:"Sangam Vihar-C",
    169:"Sangam Vihar-B",170:"Tughlakabad Ext.",171:"Chitaranjan Park",
    172:"Chirag Delhi",173:"Greater Kailash",174:"Sri Niwas Puri",
    175:"Kalkaji",176:"Govind Puri",177:"Harkesh Nagar",
    178:"Tughlakabad",179:"Pul Pehladpur",180:"Badarpur",181:"Molarband",
    182:"Meethapur",183:"Hari Nagar Ext.",184:"Jaitpur",
    185:"Madanpur Khadar East",186:"Madanpur Khadar West",
    187:"Sarita Vihar",188:"Abul Fazal Enclave",189:"Zakir Nagar",
    190:"New Ashok Nagar",191:"Mayur Vihar Phase-I",192:"Trilokpuri",
    193:"Kondli",194:"Gharoli",195:"Kalyanpuri",
    196:"Mayur Vihar Phase-II",197:"Patpar Ganj",198:"Vinod Nagar",
    199:"Mandawali",200:"Pandav Nagar",201:"Lalita Park",202:"Shakarpur",
    203:"Laxmi Nagar",204:"Preet Vihar",205:"I.P. Extension",
    206:"Anand Vihar",207:"Vishwas Nagar",208:"Anarkali",
    209:"Jagat Puri",210:"Geeta Colony",211:"Krishna Nagar",
    212:"Gandhi Nagar",213:"Shastri Park",214:"Azad Nagar",
    215:"Shahdara",216:"Jhilmil",217:"Dilshad Colony",218:"Sundar Nagri",
    219:"Dilshad Garden",220:"Nand Nagri",221:"Ashok Nagar",
    222:"Ram Nagar East",224:"Welcome Colony",225:"Seelampur",
    226:"Gautam Puri",227:"Chauhan Banger",228:"Maujpur",
    229:"Braham Puri",230:"Bhajanpura",231:"Ghonda",232:"Yamuna Vihar",
    233:"Subhash Mohalla",234:"Kabir Nagar",235:"Gorakh Park",
    236:"Kardam Puri",237:"Harsh Vihar",238:"Saboli",239:"Gokal Puri",
    240:"Joharipur",241:"Karawal Nagar-East",242:"Dayalpur",
    243:"Mustafabad",244:"Nehru Vihar",245:"Brij Puri",
    246:"Sri Ram Colony",247:"Sadatpur",248:"Karawal Nagar-West",
    249:"Sonia Vihar",250:"Sabapur",
}

# ── Build WARD_META at import time ──────────────────────────────────
WARD_META = []
_zone_idx = 0
for zone_name, zdef in ZONE_DEFS.items():
    _zone_idx += 1
    # Zone-level entry
    WARD_META.append({
        "ward_id": f"zone_{_zone_idx:02d}",
        "name": f"{zone_name} Zone",
        "zone": zone_name,
        "lat": zdef["lat"],
        "lng": zdef["lng"],
        "profile": zdef["profile"],
        "feature_type": "zone",
    })
    # Ward-level entries distributed inside zone
    ward_ids = ZONE_WARDS.get(zone_name, [])
    n = len(ward_ids)
    cols = max(1, int(math.ceil(math.sqrt(n * 1.3))))
    cell = zdef["radius"] * 2 / max(cols, 1)
    for i, wid in enumerate(ward_ids):
        col, row = i % cols, i // cols
        WARD_META.append({
            "ward_id": f"ward_{wid}",
            "name": WARD_NAMES.get(wid, f"Ward {wid}"),
            "zone": zone_name,
            "lat": zdef["lat"] - zdef["radius"] * 0.65 + row * cell + cell / 2,
            "lng": zdef["lng"] - zdef["radius"] * 0.85 + col * cell + cell / 2,
            "profile": zdef["profile"],
            "feature_type": "ward",
        })

# Pollution profiles — Delhi-realistic high AQI (typical winter readings 150-350+)
PROFILES = {
    "clean":        {"pm25_base": 90,  "co_base": 2.0, "no2_base": 0.06, "tvoc_base": 0.30, "source": None},
    "vehicle":      {"pm25_base": 160, "co_base": 4.5, "no2_base": 0.14, "tvoc_base": 0.50, "source": "vehicle"},
    "industrial":   {"pm25_base": 220, "co_base": 6.0, "no2_base": 0.22, "tvoc_base": 1.00, "source": "industrial"},
    "construction": {"pm25_base": 250, "co_base": 3.5, "no2_base": 0.10, "tvoc_base": 1.40, "source": "construction"},
    "biomass":      {"pm25_base": 200, "co_base": 7.5, "no2_base": 0.12, "tvoc_base": 1.20, "source": "biomass"},
    "mixed":        {"pm25_base": 140, "co_base": 3.8, "no2_base": 0.10, "tvoc_base": 0.60, "source": "vehicle"},
}


def _generate_ward_reading(ward: dict) -> dict:
    """Generate a realistic reading for a ward based on its pollution profile."""
    now = datetime.now(timezone.utc)
    hour = now.hour + now.minute / 60.0

    morning_peak = math.exp(-((hour - 8) ** 2) / 8)
    evening_peak = math.exp(-((hour - 18) ** 2) / 8)
    traffic_factor = 0.4 + 0.6 * (morning_peak + evening_peak)

    prof = PROFILES.get(ward["profile"], PROFILES["mixed"])
    noise = lambda s=1.0: random.gauss(0, s)

    # Add per-ward variation so adjacent wards differ slightly
    wid_hash = hash(ward["ward_id"]) % 100 / 100.0
    ward_var = 0.85 + 0.3 * wid_hash

    pm25 = max(5, prof["pm25_base"] * traffic_factor * ward_var + noise(8))
    co = max(0.1, prof["co_base"] * traffic_factor * ward_var + noise(0.2))
    no2 = max(0.005, prof["no2_base"] * traffic_factor * ward_var + noise(0.008))
    tvoc = max(0.01, prof["tvoc_base"] * traffic_factor * ward_var + noise(0.05))
    temperature = 28.0 + 5 * math.sin((hour - 14) * math.pi / 12) + noise(1.2)
    humidity = 55.0 - 15 * math.sin((hour - 14) * math.pi / 12) + noise(2.5)

    aqi = calculate_aqi(pm25, co, no2)
    cat = get_aqi_category(aqi)

    return {
        "ward_id": ward["ward_id"],
        "name": ward["name"],
        "zone": ward["zone"],
        "lat": ward["lat"],
        "lng": ward["lng"],
        "feature_type": ward.get("feature_type", "ward"),
        "timestamp": now.isoformat().replace("+00:00", "Z"),
        "temperature": round(max(15, min(45, temperature)), 1),
        "humidity": round(max(20, min(95, humidity)), 1),
        "pm25": round(pm25, 1),
        "co": round(co, 2),
        "no2": round(no2, 3),
        "tvoc": round(tvoc, 2),
        "aqi": aqi,
        "aqi_category": cat["category"],
        "aqi_color": cat["color"],
        "source_detected": prof["source"],
        "source_confidence": round(0.65 + random.random() * 0.3, 2) if prof["source"] else None,
    }


@router.get("/wards")
async def get_all_wards():
    """Return current AQI data for all zones and wards."""
    readings = [_generate_ward_reading(w) for w in WARD_META]
    return {
        "count": len(readings),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "wards": readings,
    }


@router.get("/wards/{ward_id}")
async def get_ward(ward_id: str):
    """Return data for a specific ward or zone."""
    ward = next((w for w in WARD_META if w["ward_id"] == ward_id), None)
    if not ward:
        return {"error": "Ward not found"}
    return _generate_ward_reading(ward)
