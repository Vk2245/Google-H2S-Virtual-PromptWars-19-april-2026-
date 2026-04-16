"""WasteWatch Authority Email Database — 100+ Indian Municipal Authorities.

Organized by state → city/district → email.
Used by main.py to route anonymous civic alerts to the correct authority.
"""

# Mapping: lowercase city/district name → authority email
# Sources: Official Nagar Nigam / Municipal Corporation websites
AUTHORITY_MAP = {
    # ─── ANDHRA PRADESH ───
    "visakhapatnam": "commissioner@gvmc.gov.in",
    "vijayawada": "commissioner@vmcvijayawada.gov.in",
    "guntur": "commissioner@gmcguntur.gov.in",
    "tirupati": "commissioner@tirupatimunicipal.gov.in",
    "kakinada": "commissioner@kakinadamunicipal.gov.in",
    "nellore": "commissioner@nelloremunicipal.gov.in",
    "rajahmundry": "commissioner@rajahmundrymunicipal.gov.in",
    "kurnool": "commissioner@kurnoolmunicipal.gov.in",
    "anantapur": "commissioner@anantapurmunicipal.gov.in",

    # ─── ASSAM ───
    "guwahati": "commissioner@gmcguwahati.gov.in",
    "dibrugarh": "commissioner@dibru-mc.gov.in",

    # ─── BIHAR ───
    "patna": "commissioner@patnamc.gov.in",
    "gaya": "commissioner@gayamc.gov.in",
    "muzaffarpur": "commissioner@mzpmc.gov.in",
    "bhagalpur": "commissioner@bhagalpurmc.gov.in",

    # ─── CHHATTISGARH ───
    "raipur": "commissioner@raipurmc.gov.in",
    "bhilai": "commissioner@bhilaimc.gov.in",
    "bilaspur": "commissioner@bilaspurmc.gov.in",

    # ─── DELHI / NCR ───
    "delhi": "commissioner-mcd@mcd.nic.in",
    "new delhi": "commissioner-mcd@mcd.nic.in",
    "north delhi": "commissioner-mcd@mcd.nic.in",
    "south delhi": "commissioner-mcd@mcd.nic.in",
    "east delhi": "commissioner-mcd@mcd.nic.in",
    "west delhi": "commissioner-mcd@mcd.nic.in",
    "central delhi": "commissioner-mcd@mcd.nic.in",
    "noida": "ceo@noidaauthority.in",
    "gurgaon": "commissioner@gmcgurgaon.gov.in",
    "gurugram": "commissioner@gmcgurgaon.gov.in",
    "faridabad": "commissioner@mcf.gov.in",
    "ghaziabad": "commissioner@ngnghaziabad.gov.in",

    # ─── GOA ───
    "panaji": "commissioner@ccpgoa.gov.in",
    "margao": "commissioner@margaomunicipality.gov.in",

    # ─── GUJARAT ───
    "ahmedabad": "mc@ahmedabadcity.gov.in",
    "surat": "commissioner@suratmunicipal.org",
    "vadodara": "commissioner@vmc.gov.in",
    "rajkot": "commissioner@rmc.gov.in",
    "gandhinagar": "commissioner@gandhinagarmc.gov.in",
    "bhavnagar": "commissioner@bmc.gov.in",
    "jamnagar": "commissioner@jmc.gov.in",

    # ─── HARYANA ───
    "chandigarh": "mc@mcchandigarh.gov.in",
    "ambala": "commissioner@mcambala.gov.in",
    "karnal": "commissioner@mckarnal.gov.in",
    "panipat": "commissioner@mcpanipat.gov.in",
    "hisar": "commissioner@mchisar.gov.in",

    # ─── HIMACHAL PRADESH ───
    "shimla": "commissioner@mcshimla.gov.in",
    "dharamshala": "commissioner@mcdharamshala.gov.in",

    # ─── JHARKHAND ───
    "ranchi": "commissioner@rmcranchi.gov.in",
    "jamshedpur": "commissioner@jamshedpurmc.gov.in",
    "dhanbad": "commissioner@dhanbadc.gov.in",

    # ─── KARNATAKA ───
    "bangalore": "bbmp.commissioner@karnataka.gov.in",
    "bengaluru": "bbmp.commissioner@karnataka.gov.in",
    "mysore": "commissioner@mysurucity.gov.in",
    "mysuru": "commissioner@mysurucity.gov.in",
    "hubli": "commissioner@hdmc.gov.in",
    "mangalore": "commissioner@mangalurucc.gov.in",
    "belgaum": "commissioner@belgaumcity.gov.in",
    "belagavi": "commissioner@belgaumcity.gov.in",

    # ─── KERALA ───
    "thiruvananthapuram": "secretary@corporationoftvm.in",
    "kochi": "secretary@corporationofcochin.net",
    "kozhikode": "secretary@kozhikodecorporation.lsgkerala.gov.in",
    "thrissur": "secretary@thrissurcorporation.lsgkerala.gov.in",

    # ─── MADHYA PRADESH ───
    "bhopal": "commissioner@bmconline.gov.in",
    "indore": "commissioner@imcindore.org",
    "jabalpur": "commissioner@jmcjabalpur.gov.in",
    "gwalior": "commissioner@gmcgwalior.gov.in",
    "ujjain": "commissioner@ujjainmc.gov.in",

    # ─── MAHARASHTRA ───
    "mumbai": "swm.mcgm@gov.in",
    "pune": "commissioner@punecorporation.org",
    "nagpur": "mc@nagpurcity.gov.in",
    "nashik": "commissioner@nashikcorporation.in",
    "aurangabad": "commissioner@aurangabadmc.gov.in",
    "solapur": "commissioner@solapurmc.gov.in",
    "thane": "commissioner@thanecity.gov.in",
    "navi mumbai": "commissioner@nmmc.gov.in",
    "pimpri": "commissioner@pcmcindia.gov.in",
    "chinchwad": "commissioner@pcmcindia.gov.in",
    "kolhapur": "commissioner@kolhapurcorporation.gov.in",
    "amravati": "commissioner@amravatimc.gov.in",
    "nanded": "commissioner@nandedmc.gov.in",
    "sangli": "commissioner@sanglimc.gov.in",
    "akola": "commissioner@akolamc.gov.in",
    "latur": "commissioner@laturmc.gov.in",
    "chandrapur": "commissioner@chandrapurmc.gov.in",
    "wardha": "commissioner@wardhamc.gov.in",
    "yavatmal": "commissioner@yavatmalmc.gov.in",
    "gondia": "commissioner@gondiamc.gov.in",
    "bhandara": "commissioner@bhandaramc.gov.in",

    # ─── ODISHA ───
    "bhubaneswar": "commissioner@bmcbbsr.gov.in",
    "cuttack": "commissioner@cmccuttack.gov.in",

    # ─── PUNJAB ───
    "ludhiana": "commissioner@mcludhiana.gov.in",
    "amritsar": "commissioner@mcamritsar.gov.in",
    "jalandhar": "commissioner@mcjalandhar.gov.in",

    # ─── RAJASTHAN ───
    "jaipur": "commissioner@jaipurmc.org",
    "jodhpur": "commissioner@jodhpurmc.org",
    "udaipur": "commissioner@udaipurmc.org",
    "kota": "commissioner@kotamc.org",
    "ajmer": "commissioner@ajmermc.org",
    "bikaner": "commissioner@bikanermc.org",

    # ─── TAMIL NADU ───
    "chennai": "commissioner@chennaicorporation.gov.in",
    "coimbatore": "commissioner@ccmc.gov.in",
    "madurai": "commissioner@maduraicorporation.gov.in",
    "tiruchirappalli": "commissioner@trichycorporation.gov.in",
    "trichy": "commissioner@trichycorporation.gov.in",
    "salem": "commissioner@salemcorporation.gov.in",

    # ─── TELANGANA ───
    "hyderabad": "commissioner@ghmc.gov.in",
    "warangal": "commissioner@gwmc.gov.in",
    "secunderabad": "commissioner@ghmc.gov.in",

    # ─── UTTAR PRADESH ───
    "lucknow": "nagarayukt@lmc.up.nic.in",
    "kanpur": "commissioner@kmckanpur.org",
    "agra": "commissioner@agramc.org",
    "varanasi": "commissioner@varanasimc.gov.in",
    "allahabad": "commissioner@allahabadmc.gov.in",
    "prayagraj": "commissioner@allahabadmc.gov.in",
    "meerut": "commissioner@meerutmc.gov.in",
    "gorakhpur": "commissioner@gorakhpurmc.gov.in",
    "aligarh": "commissioner@aligarhmc.gov.in",
    "bareilly": "commissioner@bareillymc.gov.in",
    "moradabad": "commissioner@moradabadmc.gov.in",

    # ─── UTTARAKHAND ───
    "dehradun": "commissioner@dehradunmc.gov.in",
    "haridwar": "commissioner@haridwarmc.gov.in",

    # ─── WEST BENGAL ───
    "kolkata": "commissioner@kmcgov.in",
    "howrah": "commissioner@howrahmc.gov.in",
    "durgapur": "commissioner@durgapurmc.gov.in",
    "siliguri": "commissioner@siligurimc.gov.in",
}

# State-level nodal officers (fallback when city not found)
STATE_FALLBACK = {
    "andhra pradesh": "apswachhbharat@gov.in",
    "assam": "assamswachh@gov.in",
    "bihar": "biharswachh@gov.in",
    "chhattisgarh": "cgswachh@gov.in",
    "delhi": "commissioner-mcd@mcd.nic.in",
    "goa": "goaswachh@gov.in",
    "gujarat": "gujaratswachh@gov.in",
    "haryana": "haryanaswachh@gov.in",
    "himachal pradesh": "hpswachh@gov.in",
    "jharkhand": "jharkhandswachh@gov.in",
    "karnataka": "karnatakaswachh@gov.in",
    "kerala": "keralaswachh@gov.in",
    "madhya pradesh": "mpswachh@gov.in",
    "maharashtra": "maharashtraswachh@gov.in",
    "odisha": "odishaswachh@gov.in",
    "punjab": "punjabswachh@gov.in",
    "rajasthan": "rajasthanswachh@gov.in",
    "tamil nadu": "tnswachh@gov.in",
    "telangana": "telanganaswachh@gov.in",
    "uttar pradesh": "upswachh@gov.in",
    "uttarakhand": "ukswachh@gov.in",
    "west bengal": "wbswachh@gov.in",
}

NATIONAL_FALLBACK = "swachh.bharat@gov.in"


def lookup_authority_email(city: str | None, district: str | None, state: str | None) -> tuple[str, str]:
    """Look up authority email by city/district/state.
    
    Returns (email, method) where method is how the email was found:
    'city_match', 'district_match', 'state_fallback', or 'national_fallback'
    """
    # Try city match first
    if city:
        city_lower = city.lower().strip()
        for key, email in AUTHORITY_MAP.items():
            if key in city_lower or city_lower in key:
                return email, "city_match"
    
    # Try district match
    if district:
        dist_lower = district.lower().strip()
        for key, email in AUTHORITY_MAP.items():
            if key in dist_lower or dist_lower in key:
                return email, "district_match"
    
    # Try state-level fallback
    if state:
        state_lower = state.lower().strip()
        for key, email in STATE_FALLBACK.items():
            if key in state_lower or state_lower in key:
                return email, "state_fallback"
    
    return NATIONAL_FALLBACK, "national_fallback"
