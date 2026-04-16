"""WasteWatch v7.0 – AI Civic Waste Reporting Backend (Gemini 2.5 Flash Multimodal)."""
import json
import logging
import math
import os
import re
import sqlite3
import httpx
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("wastewatch")
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import hashlib
import secrets
from fastapi import Header
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None  
load_dotenv()
DATABASE_MODE = os.getenv("DATABASE_MODE", "sqlite")
SUPABASE_DB_HOST = os.getenv("SUPABASE_DB_HOST", "")
SUPABASE_DB_USER = os.getenv("SUPABASE_DB_USER", "postgres")
SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "")
SUPABASE_DB_NAME = os.getenv("SUPABASE_DB_NAME", "postgres")
SUPABASE_DB_PORT = int(os.getenv("SUPABASE_DB_PORT", "5432"))
def get_supabase_client():
    from supabase import create_client, Client
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    return create_client(url, key) if url and key else None
DB_PATH = "wastewatch.db"
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
AVATAR_DIR = Path("uploads/avatars")
AVATAR_DIR.mkdir(parents=True, exist_ok=True)
GEMINI_MODEL = "gemini-2.5-flash"
MAX_IMG_BYTES = 18 * 1024 * 1024  
DEMO_MODE = not bool(os.getenv("FAST2SMS_KEY", "").strip())
DEMO_PHONE = "8989893838"
DEMO_PASSWORD = "demo@123"
DEMO_NAME = "Demo User"
GAMING_RADIUS_M = 200
HOTSPOT_RADIUS_M = 150
TIME_WINDOW_DAYS = 10
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        log.info(f"Database initialized successfully (mode: {DATABASE_MODE})")
        if DEMO_MODE:
            seed_demo_user()
            log.info(f"🎮 DEMO MODE active — use phone: {DEMO_PHONE}, password: {DEMO_PASSWORD}, OTP: 123456")
    except Exception as e:
        log.error(f"CRITICAL: Database initialization failed: {e}")
        log.error("App will start but database operations will fail. Check your DB config.")
    yield
app = FastAPI(title="WasteWatch API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
class LoginReq(BaseModel):
    phone: str
    password: str
def hash_pwd(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()
class GeminiResult(BaseModel):
    category: str
    severity: str
    action_plan: str
    authenticity_score: int = 100  
    authenticity_note: str = ""    
    is_civic_issue: bool = True    
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000  
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))
def reverse_geocode(lat: float, lng: float):
    """Uses Nominatim (free, no API key required) to get location details."""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lng}&format=json"
        headers = {"User-Agent": "WasteWatch-CivicApp/3.0 (info@wastewatch.local)"}
        resp = httpx.get(url, headers=headers, timeout=6.0)
        if resp.status_code == 200:
            data = resp.json()
            address = data.get("address", {})
            pincode = address.get("postcode") or "Unknown"
            city = address.get("city") or address.get("town") or address.get("village") or address.get("county") or "Unknown"
            state = address.get("state") or "Unknown"
            district = address.get("state_district") or address.get("county") or "Unknown"
            return pincode, city, state, district
    except Exception as e:
        log.warning(f"reverse_geocode failed: {e}")
    return "Unknown", "Unknown", "Unknown", "Unknown"
def lookup_pincode_details(pincode: str):
    """Use PostalPincode.in API for better Indian address resolution."""
    try:
        resp = httpx.get(f"https://api.postalpincode.in/pincode/{pincode}", timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            if data and data[0].get("Status") == "Success":
                po = data[0]["PostOffice"][0]
                return {
                    "district": po.get("District", "Unknown"),
                    "state": po.get("State", "Unknown"),
                    "division": po.get("Division", "Unknown"),
                    "region": po.get("Region", "Unknown"),
                    "block": po.get("Block", "Unknown"),
                }
    except Exception as e:
        log.warning(f"PostalPincode lookup failed: {e}")
    return None
class PostgresAdapter:
    def __init__(self):
        if psycopg2 is None:
            raise RuntimeError("psycopg2 not installed. Run: pip install psycopg2-binary")
        try:
            self._conn = psycopg2.connect(
                host=SUPABASE_DB_HOST,
                port=SUPABASE_DB_PORT,
                dbname=SUPABASE_DB_NAME,
                user=SUPABASE_DB_USER,
                password=SUPABASE_DB_PASSWORD,
                cursor_factory=psycopg2.extras.RealDictCursor,
                sslmode="require",
                connect_timeout=10
            )
            self._conn.autocommit = False
        except Exception as e:
            raise RuntimeError(f"Supabase connection failed: {e}") from e
    def execute(self, query: str, args=()):
        cur = self._conn.cursor()
        pg_query = query.replace("?", "%s")
        cur.execute(pg_query, args)
        return cur
    def commit(self):
        self._conn.commit()
    def rollback(self):
        self._conn.rollback()
    def close(self):
        self._conn.close()
def get_db():
    if DATABASE_MODE == "supabase":
        return PostgresAdapter()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
def init_db() -> None:
    conn = get_db()
    id_type = "SERIAL PRIMARY KEY" if DATABASE_MODE == "supabase" else "INTEGER PRIMARY KEY AUTOINCREMENT"
    text_type = "TEXT"
    real_type = "REAL"
    bool_type = "BOOLEAN"
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS citizens (
            phone TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            total_points INTEGER DEFAULT 0,
            password_hash TEXT,
            token TEXT,
            avatar_path TEXT
        )
    """)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS hotspots (
            id {id_type},
            lat {real_type} NOT NULL,
            lng {real_type} NOT NULL,
            pincode TEXT,
            city TEXT,
            state TEXT,
            report_count INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS reports (
            id          {id_type},
            description TEXT    NOT NULL,
            lat         {real_type}    NOT NULL,
            lng         {real_type}    NOT NULL,
            category    TEXT    NOT NULL,
            severity    TEXT    NOT NULL,
            action_plan TEXT    NOT NULL,
            image_path  TEXT,
            status      TEXT    NOT NULL DEFAULT 'Open',
            created_at  TEXT    NOT NULL,
            phone       TEXT,
            pincode     TEXT,
            city        TEXT,
            state       TEXT,
            district    TEXT,
            hotspot_id  INTEGER,
            points_earned INTEGER DEFAULT 0,
            authenticity_score INTEGER DEFAULT 100,
            authenticity_note TEXT DEFAULT '',
            notified INTEGER DEFAULT 0
        )
    """)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS badges (
            id {id_type},
            phone TEXT NOT NULL,
            badge_name TEXT NOT NULL,
            badge_icon TEXT NOT NULL,
            earned_at TEXT NOT NULL
        )
    """)
    dt_type = "DOUBLE PRECISION" if DATABASE_MODE == "supabase" else "REAL"
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS pending_otps (
            phone TEXT PRIMARY KEY,
            otp TEXT NOT NULL,
            expires_at {dt_type} NOT NULL
        )
    """)
    if DATABASE_MODE == "supabase":
        try:
            conn.execute("ALTER TABLE pending_otps ALTER COLUMN expires_at TYPE DOUBLE PRECISION")
        except Exception:
            conn.rollback() 
    if DATABASE_MODE != "supabase":
        for col, ctype in [('password_hash', 'TEXT'), ('token', 'TEXT'), ('avatar_path', 'TEXT')]:
            try: conn.execute(f"ALTER TABLE citizens ADD COLUMN {col} {ctype}")
            except sqlite3.OperationalError: pass
        for col, ctype in [('phone', 'TEXT'), ('pincode', 'TEXT'), ('city', 'TEXT'),
                           ('state', 'TEXT'), ('hotspot_id', 'INTEGER'), ('image_path', 'TEXT'),
                           ('points_earned', 'INTEGER DEFAULT 0'),
                           ('authenticity_score', 'INTEGER DEFAULT 100'), ('authenticity_note', 'TEXT'),
                           ('district', 'TEXT'), ('notified', 'INTEGER DEFAULT 0')]:
            try: conn.execute(f"ALTER TABLE reports ADD COLUMN {col} {ctype}")
            except sqlite3.OperationalError: pass
    conn.commit()
    conn.close()
def seed_demo_user():
    """Seed a demo user account so the app works out-of-the-box without OTP."""
    conn = get_db()
    existing = conn.execute("SELECT phone FROM citizens WHERE phone=?", (DEMO_PHONE,)).fetchone()
    if not existing:
        token = secrets.token_hex(16)
        conn.execute(
            "INSERT INTO citizens (phone, name, created_at, password_hash, token) VALUES (?, ?, ?, ?, ?)",
            (DEMO_PHONE, DEMO_NAME, datetime.now(timezone.utc).isoformat(), hash_pwd(DEMO_PASSWORD), token)
        )
        conn.commit()
        log.info(f"✅ Demo user seeded: phone={DEMO_PHONE}, password={DEMO_PASSWORD}")
    else:
        log.info(f"Demo user already exists: {DEMO_PHONE}")
    conn.close()
GEMINI_PROMPT = (
    "You are an expert civic waste classification assistant for Indian municipalities.\n"
    "Analyze the following citizen waste report{image_hint} and return ONLY a valid JSON object with exactly:\n"
    '  "is_civic_issue": boolean (true if it actually shows civic waste/garbage/infrastructure issues, false if it is a selfie, meme, animal, person, or unrelated object)\n'
    '  "category": one of "Garbage", "E-waste", "Debris", "Other"\n'
    '  "severity": one of "Low", "Medium", "High"\n'
    '  "action_plan": a single clear, actionable sentence for municipal cleanup workers\n'
    '{authenticity_fields}'
    "\nCitizen description: \"{description}\"\n\n"
    "Indian civic severity rules:\n"
    "- High: near schools/hospitals, blocking roads, fire hazard, open drains, large volume\n"
    "- Medium: moderate pile, public space, residential area\n"
    "- Low: small amount, isolated spot\n\n"
    "**CRITICAL REJECTION RULE**: If the image or description does NOT clearly show civic waste or garbage (e.g., if it's a selfie, an animal, a room interior, a meme), you MUST set is_civic_issue to false, category to \"Other\", and if an image is attached, set authenticity_score to 0 with note 'Irrelevant photo'.\n\n"
    "Respond with ONLY the JSON object."
)
AUTHENTICITY_FIELDS = (
    '  "authenticity_score": integer 0-100 estimating how likely the photo is a GENUINE on-site capture OF ACTUAL WASTE. '
    '(100=genuine field photo of waste, 50=uncertain, 0=completely irrelevant photo, selfie, screenshot, or fake). '
    'If the image does not show garbage, you MUST return 0!\n'
    '  "authenticity_note": short 1-sentence explanation of your assessment\n'
)
def call_gemini(description: str, image_bytes: bytes | None = None, mime_type: str = "image/jpeg") -> GeminiResult | None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return None
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        has_image = image_bytes is not None
        auth_fields = AUTHENTICITY_FIELDS if has_image else ""
        prompt_text = GEMINI_PROMPT.format(
            description=description,
            image_hint=" (with attached photo)" if has_image else "",
            authenticity_fields=auth_fields,
        )
        parts: list = []
        if has_image:
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
        parts.append(prompt_text)
        resp = client.models.generate_content(model=GEMINI_MODEL, contents=parts)
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", resp.text.strip())
        data = json.loads(text)
        return GeminiResult(
            category=data.get("category", "Other"),
            severity=data.get("severity", "Low"),
            action_plan=data.get("action_plan", "Pending review"),
            authenticity_score=data.get("authenticity_score", 100),
            authenticity_note=data.get("authenticity_note", ""),
            is_civic_issue=bool(data.get("is_civic_issue", True))
        )
    except Exception as e:
        log.error(f"call_gemini error: {e}")
        return None
def call_groq_vision(description: str, image_bytes: bytes | None = None, mime_type: str = "image/jpeg") -> GeminiResult | None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key: return None
    try:
        from groq import Groq
        import base64
        client = Groq(api_key=api_key)
        has_image = image_bytes is not None
        auth_fields = AUTHENTICITY_FIELDS if has_image else ""
        prompt_text = GEMINI_PROMPT.format(
            description=description,
            image_hint=" (with attached photo)" if has_image else "",
            authenticity_fields=auth_fields,
        )
        messages = [
            {"role": "system", "content": "You are a JSON-only API. Only return valid JSON."}
        ]
        user_content = []
        if has_image:
            b64_img = base64.b64encode(image_bytes).decode('utf-8')
            user_content.append({"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_img}"}})
        user_content.append({"type": "text", "text": prompt_text})
        messages.append({"role": "user", "content": user_content})
        res = client.chat.completions.create(
            messages=messages,
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            response_format={"type": "json_object"}
        )
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", res.choices[0].message.content.strip())
        data = json.loads(text)
        return GeminiResult(
            category=data.get("category", "Other"),
            severity=data.get("severity", "Low"),
            action_plan=data.get("action_plan", "Pending review"),
            authenticity_score=data.get("authenticity_score", 100),
            authenticity_note=data.get("authenticity_note", ""),
            is_civic_issue=bool(data.get("is_civic_issue", True))
        )
    except Exception as e:
        log.error(f"call_groq_vision error: {e}")
        return None
def fallback_classify(description: str, has_image: bool = False) -> GeminiResult:
    desc = description.lower()
    cat, sev, act = "Garbage", "Medium", "Dispatch cleanup crew for standard waste removal."
    if any(w in desc for w in ("construction", "debris", "rubble", "cement")):
        cat, act = "Debris", "Send heavy-duty vehicle for debris clearance."
    elif any(w in desc for w in ("electronic", "battery", "e-waste", "mobile")):
        cat, act = "E-waste", "Deploy e-waste certified collection team."
    if any(w in desc for w in ("school", "hospital", "blocking", "fire", "drain")):
        sev, act = "High", "URGENT: Prioritize immediate cleanup – sensitive area or hazard detected."
    elif any(w in desc for w in ("large", "overflow", "smell")): sev = "High"
    auth_score = 50 if has_image else 100
    note = "AI temporarily busy (Rate Limit). Verification uncertain." if has_image else ""
    return GeminiResult(category=cat, severity=sev, action_plan=act, authenticity_score=auth_score, authenticity_note=note)
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "WasteWatch",
        "ai_model": GEMINI_MODEL,
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "demo_mode": DEMO_MODE,
        "demo_credentials": {"phone": DEMO_PHONE, "password": DEMO_PASSWORD, "otp": "123456"} if DEMO_MODE else None
    }
class OTPSendReq(BaseModel):
    phone: str
@app.post("/api/auth/otp/send")
def send_otp(req: OTPSendReq):
    p = re.sub(r'^(?:\+91|91)', '', req.phone)
    if not re.match(r"^[6789]\d{9}$", p):
        raise HTTPException(status_code=422, detail="Invalid phone")
    otp = str(secrets.randbelow(899999) + 100000)
    expiry = time.time() + 600 
    conn = get_db()
    if DATABASE_MODE == "supabase":
        conn.execute("INSERT INTO pending_otps (phone, otp, expires_at) VALUES (%s, %s, %s) ON CONFLICT (phone) DO UPDATE SET otp = EXCLUDED.otp, expires_at = EXCLUDED.expires_at", (p, otp, expiry))
    else:
        conn.execute("INSERT OR REPLACE INTO pending_otps (phone, otp, expires_at) VALUES (?, ?, ?)", (p, otp, expiry))
    conn.commit()
    conn.close()
    f2s_key = os.getenv("FAST2SMS_KEY")
    if f2s_key:
        try:
            httpx.post("https://www.fast2sms.com/dev/bulkV2", 
                headers={"authorization": f2s_key},
                data={"variables_values": otp, "route": "otp", "numbers": p})
        except Exception as e:
            log.error(f"Fast2SMS failed: {e}")
    log.info(f"OTP for {p}: {otp} (MOCK SEND)")
    resp = {"message": "OTP sent successfully. Please check your messages.", "phone": p}
    if DEMO_MODE:
        resp["dev_otp"] = otp  
        resp["demo_hint"] = "Demo mode: use OTP 123456 (always works)"
    return resp
class RegisterReq(BaseModel):
    phone: str
    name: str
    password: str
    otp: str 
@app.post("/api/auth/register")
def register(req: RegisterReq):
    p = re.sub(r'^(?:\+91|91)', '', req.phone)
    if not re.match(r"^[6789]\d{9}$", p):
        raise HTTPException(status_code=422, detail="Invalid phone")
    clean_name = re.sub(r'<[^>]*>', '', req.name).strip()
    conn = get_db()
    existing = conn.execute("SELECT phone FROM citizens WHERE phone=?", (p,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="Phone already registered")
    if DEMO_MODE and req.otp == "123456":
        log.info(f"Demo mode: OTP bypass accepted for {p}")
    else:
        row = conn.execute("SELECT otp, expires_at FROM pending_otps WHERE phone=?", (p,)).fetchone()
        if not row or row["otp"] != req.otp or time.time() > row["expires_at"]:
            conn.close()
            raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    token = secrets.token_hex(16)
    conn.execute("INSERT INTO citizens (phone, name, created_at, password_hash, token) VALUES (?, ?, ?, ?, ?)",
                 (p, clean_name, datetime.now(timezone.utc).isoformat(), hash_pwd(req.password), token))
    conn.execute("DELETE FROM pending_otps WHERE phone=?", (p,)) 
    conn.commit()
    conn.close()
    return {"token": token, "name": clean_name, "phone": p}
@app.post("/api/auth/login")
def login(req: LoginReq):
    p = re.sub(r'^(?:\+91|91)', '', req.phone)
    conn = get_db()
    user = conn.execute("SELECT * FROM citizens WHERE phone=? AND password_hash=?", (p, hash_pwd(req.password))).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = secrets.token_hex(16)
    conn.execute("UPDATE citizens SET token=? WHERE phone=?", (token, p))
    conn.commit()
    name = user["name"]
    conn.close()
    return {"token": token, "name": name, "phone": p}
@app.post("/api/report")
async def create_report(
    description: str = Form(..., min_length=5, max_length=1000),
    lat: float = Form(..., ge=-90, le=90),
    lng: float = Form(..., ge=-180, le=180),
    image: UploadFile | None = File(default=None),
    authorization: str = Header(...)
):
    conn = None
    try:
        now_ts = datetime.now(timezone.utc)
        now = now_ts.isoformat()
        conn = get_db()
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401)
        token = authorization.split(" ")[1]
        user = conn.execute("SELECT * FROM citizens WHERE token=?", (token,)).fetchone()
        if not user:
            raise HTTPException(status_code=401)
        phone = user["phone"]
        name = user["name"]
        if not check_rate_limit(phone):
            raise HTTPException(status_code=429, detail="You've submitted too many reports this hour. Please wait before submitting more.")
        cutoff = (now_ts - timedelta(hours=24)).isoformat()
        recent = conn.execute("SELECT lat, lng FROM reports WHERE phone = ? AND created_at >= ?", (phone, cutoff)).fetchall()
        for row in recent:
            if haversine(lat, lng, row["lat"], row["lng"]) <= GAMING_RADIUS_M:
                raise HTTPException(status_code=429, detail="You already reported a waste issue in this exact area recently! Keep exploring to earn more points.")
        pincode, city, state, district = reverse_geocode(lat, lng)
        if pincode and pincode != "Unknown":
            pin_details = lookup_pincode_details(pincode)
            if pin_details:
                if city == "Unknown": city = pin_details.get("district", city)
                if state == "Unknown": state = pin_details.get("state", state)
                if district == "Unknown": district = pin_details.get("district", district)
        image_bytes, saved_image_path = None, None
        mime_type = "image/jpeg"
        if image and image.filename:
            raw = await image.read()
            if len(raw) > MAX_IMG_BYTES:
                raise HTTPException(status_code=413, detail="Image too large (max 18 MB).")
            image_bytes = raw
            mime_type = image.content_type or "image/jpeg"
            suffix = Path(image.filename).suffix or ".jpg"
            filename = f"report_{now_ts.strftime('%Y%m%d%H%M%S%f')}{suffix}"
            if DATABASE_MODE == "supabase":
                sb = get_supabase_client()
                if sb:
                    sb.storage.from_("wastewatch-uploads").upload(filename, image_bytes, file_options={"content-type": mime_type})
                    saved_image_path = sb.storage.from_("wastewatch-uploads").get_public_url(filename)
                else:
                    (UPLOAD_DIR / filename).write_bytes(raw)
                    saved_image_path = f"uploads/{filename}"
            else:
                (UPLOAD_DIR / filename).write_bytes(raw)
                saved_image_path = f"uploads/{filename}"
        result = call_gemini(description, image_bytes, mime_type) or call_groq_vision(description, image_bytes, mime_type) or fallback_classify(description, bool(image_bytes))
        if not result.is_civic_issue or result.category == "Other" or (image_bytes and result.authenticity_score <= 10):
            raise HTTPException(status_code=400, detail="Submission Rejected: The AI determined this photo/description is not related to civic waste.")
        hotspots = conn.execute("SELECT id, lat, lng FROM hotspots").fetchall()
        matched_hotspot_id = None
        new_location_bonus = 3
        for hs in hotspots:
            if haversine(lat, lng, hs["lat"], hs["lng"]) <= HOTSPOT_RADIUS_M:
                matched_hotspot_id = hs["id"]
                conn.execute("UPDATE hotspots SET report_count = report_count + 1 WHERE id = ?", (matched_hotspot_id,))
                new_location_bonus = 0
                break
        if not matched_hotspot_id:
            c = conn.execute(
                "INSERT INTO hotspots (lat, lng, pincode, city, state, created_at) VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
                (lat, lng, pincode, city, state, now)
            )
            matched_hotspot_id = c.fetchone()["id"]
        if result.category == "Other" or (image_bytes and result.authenticity_score <= 10):
            points = 0
        else:
            points = 10  
            if image_bytes: 
                points += 5
            points += new_location_bonus
            if result.severity == "High": points += 5
            elif result.severity == "Medium": points += 3
            if image_bytes and result.authenticity_score < 60:
                points = max(1, points - 8)
        conn.execute("UPDATE citizens SET total_points = total_points + ? WHERE phone = ?", (points, phone))
        insert_sql = """INSERT INTO reports 
               (description, lat, lng, category, severity, action_plan, image_path,
                status, created_at, phone, pincode, city, state, hotspot_id,
                points_earned, authenticity_score, authenticity_note, district)
               VALUES (?,?,?,?,?,?,?,'Open',?,?,?,?,?,?,?,?,?,?)"""
        clean_desc = re.sub(r'<[^>]*>', '', description)
        params = (clean_desc, lat, lng, result.category, result.severity, result.action_plan,
                  saved_image_path, now, phone, pincode, city, state, matched_hotspot_id,
                  points, result.authenticity_score, result.authenticity_note, district)
        if DATABASE_MODE == "supabase":
            cursor = conn.execute(insert_sql + " RETURNING id", params)
            report_id = cursor.fetchone()["id"]
        else:
            cursor = conn.execute(insert_sql, params)
            report_id = cursor.lastrowid
        conn.commit()
        new_badges = []
        try:
            new_badges = check_and_award_badges(phone, conn)
        except Exception:
            pass
        authority_email = "swachh.bharat@gov.in"
        try:
            report_row = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
            if report_row:
                authority_email, _ = resolve_authority(report_row)
        except Exception:
            pass
        return {
            "id": report_id,
            "description": description,
            "lat": lat, "lng": lng,
            "category": result.category,
            "severity": result.severity,
            "action_plan": result.action_plan,
            "image_path": saved_image_path,
            "status": "Open",
            "created_at": now,
            "maps_link": f"https://maps.google.com/?q={lat},{lng}",
            "points_earned": points,
            "city": city,
            "pincode": pincode,
            "authenticity_score": result.authenticity_score,
            "authenticity_note": result.authenticity_note,
            "new_badges": new_badges,
            "authority_email": authority_email,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_report unhandled error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Report processing failed: {str(e)}")
    finally:
        if conn:
            conn.close()
@app.get("/api/reports")
def list_reports(authorization: str | None = Header(default=None)):
    conn = get_db()
    current_phone = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        user = conn.execute("SELECT phone FROM citizens WHERE token=?", (token,)).fetchone()
        if user:
            current_phone = user["phone"]
    rows = conn.execute("SELECT * FROM reports ORDER BY id DESC").fetchall()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        is_me = (d.get("phone") == current_phone)
        d.pop("phone", None) 
        d["is_me"] = is_me
        if not is_me:
            d["description"] = "🔒 Hidden for privacy"
            d["image_path"] = None
            d["action_plan"] = "🔒 Auth restricted"
        d["maps_link"] = f"https://maps.google.com/?q={r['lat']},{r['lng']}"
        res.append(d)
    return res
@app.get("/api/leaderboard")
def get_leaderboard(scope: str = "national", value: str = ""):
    conn = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=TIME_WINDOW_DAYS)).isoformat()
    query = """
    SELECT c.name, r.phone, SUM(r.points_earned) as score, COUNT(r.id) as reports
    FROM reports r JOIN citizens c ON r.phone = c.phone
    WHERE r.created_at >= ?
    """
    params = [cutoff]
    if scope == "pincode" and value:
        query += " AND r.pincode = ?"
        params.append(value)
    elif scope == "state" and value:
        query += " AND LOWER(r.state) = LOWER(?)"
        params.append(value)
    query += " GROUP BY r.phone, c.name ORDER BY score DESC LIMIT 20"
    rows = conn.execute(query, tuple(params)).fetchall()
    conn.close()
    res = []
    for r in rows:
        phone = r["phone"]
        masked = f"******{phone[-4:]}" if phone else "******"
        res.append({"name": r["name"], "phone_masked": masked, "score": r["score"], "reports": r["reports"]})
    return res
@app.get("/api/hotspots")
def list_hotspots():
    conn = get_db()
    rows = conn.execute("SELECT lat, lng, report_count, pincode, city FROM hotspots ORDER BY report_count DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]
VALID_STATUSES = ["Open", "In Progress", "Resolved"]
class StatusUpdate(BaseModel):
    status: str
@app.patch("/api/report/{report_id}/status")
def update_report_status(report_id: int, body: StatusUpdate, authorization: str = Header(...)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status. Must be one of: {VALID_STATUSES}")
    conn = get_db()
    report = conn.execute("SELECT id FROM reports WHERE id = ?", (report_id,)).fetchone()
    if not report:
        conn.close()
        raise HTTPException(status_code=404, detail="Report not found")
    conn.execute("UPDATE reports SET status = ? WHERE id = ?", (body.status, report_id))
    conn.commit()
    conn.close()
    return {"id": report_id, "status": body.status}
@app.get("/api/user/stats")
def get_user_stats(authorization: str = Header(...)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    token = authorization.split(" ")[1]
    conn = get_db()
    user = conn.execute("SELECT * FROM citizens WHERE token=?", (token,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=401)
    phone = user["phone"]
    total_reports = conn.execute("SELECT COUNT(*) as cnt FROM reports WHERE phone=?", (phone,)).fetchone()["cnt"]
    total_points = user["total_points"] or 0
    rank_row = conn.execute(
        "SELECT COUNT(*) + 1 as rank FROM citizens WHERE total_points > ?", (total_points,)
    ).fetchone()
    rank = rank_row["rank"] if rank_row else 1
    top3 = conn.execute("SELECT total_points FROM citizens ORDER BY total_points DESC LIMIT 3").fetchall()
    top3_min = top3[-1]["total_points"] if len(top3) >= 3 else (top3[0]["total_points"] if top3 else 0)
    gap = max(0, top3_min - total_points) if rank > 3 else 0
    conn.close()
    return {
        "name": user["name"],
        "phone_masked": f"******{phone[-4:]}",
        "total_reports": total_reports,
        "total_points": total_points,
        "rank": rank,
        "gap_to_top3": gap,
        "joined": user["created_at"]
    }
@app.get("/api/user/insight")
def get_user_insight(authorization: str = Header(...)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    token = authorization.split(" ")[1]
    conn = get_db()
    user = conn.execute("SELECT * FROM citizens WHERE token=?", (token,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=401)
    phone = user["phone"]
    reports = conn.execute("SELECT category, severity, city FROM reports WHERE phone=? ORDER BY id DESC LIMIT 5", (phone,)).fetchall()
    conn.close()
    if not reports:
        return {"insight": f"Welcome {user['name']}! Submit your first report to unlock AI insights."}
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"insight": "Keep reporting! Clean cities rely on active citizens like you. 🌟"}
    recent_str = ", ".join([f"{r['severity']} severity {r['category']} in {r['city']}" for r in reports])
    prompt = f"""
    You are the WasteWatch AI assistant communicating directly with '{user['name']}'.
    Their 5 most recent waste reports were: {recent_str}.
    Provide a very short (1-2 sentences, max 120 characters total), highly encouraging and gamified motivational message based on these specific reports. Always end with a positive emoji.
    Example: "Great job spotting that High severity plastic wait in Delhi! You're making a real impact. 🏆"
    """
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        insight_text = resp.text.strip().replace("\n", " ").replace("\"", "")
        return {"insight": insight_text}
    except Exception as e:
        log.warning(f"Insight generation failed: {e}")
        return {"insight": "You are doing an excellent job reporting waste. Your city thanks you! ⭐"}
from authority_db import lookup_authority_email
def resolve_authority(report) -> tuple[str, str]:
    """Resolve the correct municipal authority email for a report."""
    city = report["city"] or ""
    state = report["state"] or ""
    pincode = report["pincode"] or ""
    district = ""
    try:
        district = report["district"] or ""
    except (IndexError, KeyError):
        pass
    if pincode and pincode != "Unknown":
        pin_details = lookup_pincode_details(pincode)
        if pin_details:
            if not city or city == "Unknown":
                city = pin_details.get("district", city)
            if not district or district == "Unknown":
                district = pin_details.get("district", district)
            if not state or state == "Unknown":
                state = pin_details.get("state", state)
    email, method = lookup_authority_email(city, district, state)
    log.info(f"[AUTHORITY] Resolved: {email} via {method} (city={city}, district={district}, state={state})")
    return email, method
def send_authority_email(report_id: int, report, to_email: str) -> bool:
    """Send anonymous civic alert email via Resend API."""
    resend_key = os.getenv("RESEND_API_KEY", "").strip().replace('"', '').replace("'", "")
    if not resend_key:
        return False
    try:
        city = report["city"] or "Unknown"
        maps_link = f"https://maps.google.com/?q={report['lat']},{report['lng']}"
        photo_html = ""
        if report["image_path"]:
            photo_html = f'<p><strong>Photo Evidence:</strong> <a href="https://wastewatch224.onrender.com/{report["image_path"]}">View Photo</a></p>'
        else:
            photo_html = '<p><em>No photo provided</em></p>'
        html_body = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
          <div style="background:linear-gradient(90deg,
          <h2 style="color:
          <table style="width:100%;border-collapse:collapse;margin:16px 0">
            <tr><td style="padding:8px;border:1px solid 
            <tr><td style="padding:8px;border:1px solid 
            <tr><td style="padding:8px;border:1px solid 
            <tr><td style="padding:8px;border:1px solid 
            <tr><td style="padding:8px;border:1px solid 
            <tr><td style="padding:8px;border:1px solid 
            <tr><td style="padding:8px;border:1px solid 
          </table>
          {photo_html}
          <hr style="border:none;border-top:1px solid 
          <p style="color:
          <p style="color:
        </div>
        """
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={
                "from": os.getenv("RESEND_FROM", "WasteWatch Alert <onboarding@resend.dev>"),
                "to": [to_email],
                "subject": f"Civic Waste Alert — {report['severity']} Severity in {city} [
                "html": html_body
            },
            timeout=10.0
        )
        if resp.status_code in (200, 201):
            log.info(f"[RESEND] Email sent for Report 
            return True
        else:
            log.error(f"[RESEND ERROR] Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log.error(f"[RESEND EXCEPTION] Error: {e}")
    return False
@app.post("/api/report/{report_id}/notify")
def notify_authority(report_id: int, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    conn = get_db()
    report = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if not report:
        conn.close()
        raise HTTPException(status_code=404, detail="Report not found")
    to_email, method = resolve_authority(report)
    email_sent = send_authority_email(report_id, report, to_email)
    if not email_sent:
        log.info(f"[MOCK EMAIL] Would send to {to_email} for Report 
    try:
        conn.execute("UPDATE reports SET notified = 1 WHERE id = ?", (report_id,))
        conn.commit()
    except Exception:
        pass
    conn.close()
    return {
        "status": "success",
        "authority_email": to_email,
        "resolution_method": method,
        "email_sent": email_sent,
        "message": f"Alert {'sent' if email_sent else 'queued'} to {to_email}",
        "mailto_fallback": f"mailto:{to_email}?subject=Civic%20Waste%20Alert%20%23{report_id}&body=Report%20ID%3A%20{report_id}%0ALocation%3A%20{report['city'] or ''}%0AGPS%3A%20{report['lat']}%2C{report['lng']}"
    }
class VARequest(BaseModel):
    prompt: str
@app.post("/api/va-assist")
def va_assist(req: VARequest, authorization: str = Header(...)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    token = authorization.split(" ")[1]
    conn = get_db()
    user = conn.execute("SELECT phone FROM citizens WHERE token=?", (token,)).fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=401)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"reply": "Error: GEMINI_API_KEY is missing in the .env file! Please add it to use the AI."}
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(model=GEMINI_MODEL, contents=req.prompt)
        return {"reply": resp.text.strip()}
    except Exception as e:
        error_msg = str(e)
        log.error(f"va_assist error: {error_msg}")
        should_fallback = any(c in error_msg for c in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE"])
        if should_fallback:
            groq_key = os.getenv("GROQ_API_KEY")
            if groq_key:
                try:
                    log.info("Gemini unavailable. Initiating Groq Llama-3.3 failover...")
                    gr = httpx.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                        json={
                            "model": "llama-3.3-70b-versatile",
                            "messages": [
                                {"role": "system", "content": "You are WasteWatch AI guide. Reply only with helpful plain text. No markdown, no asterisks."},
                                {"role": "user", "content": req.prompt}
                            ],
                            "max_tokens": 150
                        },
                        timeout=8.0
                    )
                    if gr.status_code == 200:
                        reply_txt = gr.json()["choices"][0]["message"]["content"].strip()
                        return {"reply": f"\U0001f916 (Via Groq) {reply_txt}"}
                except Exception as groq_err:
                    log.error(f"Groq fallback failed: {groq_err}")
            return {"reply": "AI is temporarily busy. Please try again in a moment! \u23f3"}
        return {"reply": "AI temporarily unavailable. Please try again shortly."}
BADGE_DEFINITIONS = [
    {"name": "First Report", "icon": "🏅", "condition": lambda stats: stats["total_reports"] >= 1},
    {"name": "Explorer", "icon": "🧭", "condition": lambda stats: stats["unique_locations"] >= 5},
    {"name": "Vigilante", "icon": "🦸", "condition": lambda stats: stats["total_reports"] >= 10},
    {"name": "Photographer", "icon": "📸", "condition": lambda stats: stats["photo_reports"] >= 5},
    {"name": "50 Point Club", "icon": "⭐", "condition": lambda stats: stats["total_points"] >= 50},
    {"name": "Century", "icon": "💯", "condition": lambda stats: stats["total_points"] >= 100},
    {"name": "High Alert Hero", "icon": "🚨", "condition": lambda stats: stats["high_severity"] >= 3},
    {"name": "City Champion", "icon": "🏆", "condition": lambda stats: stats["rank"] == 1},
    {"name": "Eco Warrior", "icon": "🌿", "condition": lambda stats: stats["total_reports"] >= 25},
    {"name": "Map Master", "icon": "🗺️", "condition": lambda stats: stats["unique_locations"] >= 15},
]
def check_and_award_badges(phone: str, conn) -> list[dict]:
    """Check all badge conditions and award any newly earned badges."""
    total_reports = conn.execute("SELECT COUNT(*) as c FROM reports WHERE phone=?", (phone,)).fetchone()["c"]
    photo_reports = conn.execute("SELECT COUNT(*) as c FROM reports WHERE phone=? AND image_path IS NOT NULL", (phone,)).fetchone()["c"]
    high_severity = conn.execute("SELECT COUNT(*) as c FROM reports WHERE phone=? AND severity='High'", (phone,)).fetchone()["c"]
    unique_locations = conn.execute("SELECT COUNT(DISTINCT hotspot_id) as c FROM reports WHERE phone=?", (phone,)).fetchone()["c"]
    user = conn.execute("SELECT total_points FROM citizens WHERE phone=?", (phone,)).fetchone()
    total_points = user["total_points"] if user else 0
    rank_row = conn.execute("SELECT COUNT(*) + 1 as rank FROM citizens WHERE total_points > ?", (total_points,)).fetchone()
    rank = rank_row["rank"] if rank_row else 1
    stats = {
        "total_reports": total_reports,
        "photo_reports": photo_reports,
        "high_severity": high_severity,
        "unique_locations": unique_locations,
        "total_points": total_points,
        "rank": rank,
    }
    existing = {r["badge_name"] for r in conn.execute("SELECT badge_name FROM badges WHERE phone=?", (phone,)).fetchall()}
    newly_awarded = []
    now = datetime.now(timezone.utc).isoformat()
    for badge in BADGE_DEFINITIONS:
        if badge["name"] not in existing and badge["condition"](stats):
            conn.execute("INSERT INTO badges (phone, badge_name, badge_icon, earned_at) VALUES (?, ?, ?, ?)",
                         (phone, badge["name"], badge["icon"], now))
            newly_awarded.append({"name": badge["name"], "icon": badge["icon"]})
    if newly_awarded:
        conn.commit()
    return newly_awarded
@app.get("/api/user/profile")
def get_user_profile(authorization: str = Header(...)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    token = authorization.split(" ")[1]
    conn = get_db()
    user = conn.execute("SELECT * FROM citizens WHERE token=?", (token,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=401)
    phone = user["phone"]
    total_reports = conn.execute("SELECT COUNT(*) as c FROM reports WHERE phone=?", (phone,)).fetchone()["c"]
    total_points = user["total_points"] or 0
    rank_row = conn.execute("SELECT COUNT(*) + 1 as rank FROM citizens WHERE total_points > ?", (total_points,)).fetchone()
    rank = rank_row["rank"] if rank_row else 1
    reports = conn.execute(
        "SELECT id, description, category, severity, status, city, pincode, points_earned, created_at FROM reports WHERE phone=? ORDER BY id DESC LIMIT 15",
        (phone,)
    ).fetchall()
    badges = conn.execute("SELECT badge_name, badge_icon, earned_at FROM badges WHERE phone=? ORDER BY id DESC", (phone,)).fetchall()
    conn.close()
    avatar_path = None
    try:
        avatar_path = user["avatar_path"]
    except (IndexError, KeyError):
        pass
    return {
        "name": user["name"],
        "phone_masked": f"******{phone[-4:]}",
        "avatar_path": avatar_path,
        "joined": user["created_at"],
        "total_reports": total_reports,
        "total_points": total_points,
        "rank": rank,
        "reports": [dict(r) for r in reports],
        "badges": [dict(b) for b in badges],
    }
class ProfileUpdate(BaseModel):
    name: Optional[str] = None
@app.patch("/api/user/profile")
def update_user_profile(body: ProfileUpdate, authorization: str = Header(...)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    token = authorization.split(" ")[1]
    conn = get_db()
    user = conn.execute("SELECT phone FROM citizens WHERE token=?", (token,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=401)
    if body.name and body.name.strip():
        conn.execute("UPDATE citizens SET name=? WHERE phone=?", (body.name.strip(), user["phone"]))
        conn.commit()
    conn.close()
    return {"status": "updated", "name": body.name}
@app.post("/api/user/avatar")
async def upload_avatar(
    image: UploadFile = File(...),
    authorization: str = Header(...)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    token = authorization.split(" ")[1]
    conn = get_db()
    user = conn.execute("SELECT phone FROM citizens WHERE token=?", (token,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=401)
    raw = await image.read()
    if len(raw) > 5 * 1024 * 1024:
        conn.close()
        raise HTTPException(status_code=413, detail="Avatar too large (max 5 MB)")
    suffix = Path(image.filename).suffix or ".jpg"
    filename = f"avatar_{user['phone']}{suffix}"
    if DATABASE_MODE == "supabase":
        sb = get_supabase_client()
        if sb:
            try:
                sb.storage.from_("wastewatch-uploads").upload(f"avatars/{filename}", raw, file_options={"content-type": getattr(image, "content_type", "image/jpeg"), "upsert": "true"})
            except Exception as e:
                log.warning(f"Avatar upload exception (might be upsert unsupported): {e}")
            avatar_path = sb.storage.from_("wastewatch-uploads").get_public_url(f"avatars/{filename}")
        else:
            (AVATAR_DIR / filename).write_bytes(raw)
            avatar_path = f"uploads/avatars/{filename}"
    else:
        (AVATAR_DIR / filename).write_bytes(raw)
        avatar_path = f"uploads/avatars/{filename}"
    conn.execute("UPDATE citizens SET avatar_path=? WHERE phone=?", (avatar_path, user["phone"]))
    conn.commit()
    conn.close()
    return {"status": "uploaded", "avatar_path": avatar_path}
@app.get("/api/user/badges")
def get_user_badges(authorization: str = Header(...)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    token = authorization.split(" ")[1]
    conn = get_db()
    user = conn.execute("SELECT phone FROM citizens WHERE token=?", (token,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=401)
    new_badges = check_and_award_badges(user["phone"], conn)
    badges = conn.execute("SELECT badge_name, badge_icon, earned_at FROM badges WHERE phone=? ORDER BY id", (user["phone"],)).fetchall()
    conn.close()
    return {"badges": [dict(b) for b in badges], "new_badges": new_badges}
@app.get("/api/analytics/predict")
def analytics_predict(authorization: str = Header(...)):
    """Waste Trend Prediction — last 30 days → next 7 days forecast."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    conn = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    rows = conn.execute(
        "SELECT category, severity, city, created_at FROM reports WHERE created_at >= ? ORDER BY created_at",
        (cutoff,)
    ).fetchall()
    conn.close()
    if not rows:
        return {"prediction": "Not enough data yet. Submit more reports to unlock AI predictions!", "data": []}
    summary = {}
    for r in rows:
        day = r["created_at"][:10]
        summary.setdefault(day, {"count": 0, "categories": {}})
        summary[day]["count"] += 1
        cat = r["category"]
        summary[day]["categories"][cat] = summary[day]["categories"].get(cat, 0) + 1
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"prediction": "AI key not configured.", "data": list(summary.items())}
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = f"""Analyze this waste report data (daily counts with categories) and predict trends for the next 7 days.
Data: {json.dumps(summary)}
Return ONLY a JSON object with:
"prediction_text": 2-3 sentence summary of trends and predictions
"daily_forecast": [{{"date":"YYYY-MM-DD","predicted_count":N,"risk_level":"Low/Medium/High"}}] for next 7 days
"hotspot_categories": top 3 waste categories likely to increase
"recommendation": 1 sentence cleanup recommendation"""
        resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", resp.text.strip())
        data = json.loads(text)
        return {"prediction": data.get("prediction_text", ""), "forecast": data.get("daily_forecast", []),
                "hotspot_categories": data.get("hotspot_categories", []), "recommendation": data.get("recommendation", "")}
    except Exception as e:
        log.warning(f"Analytics predict error: {e}")
        total = sum(d["count"] for d in summary.values())
        avg = total / max(len(summary), 1)
        return {"prediction": f"Based on {total} reports over {len(summary)} days (avg {avg:.1f}/day), waste levels appear {'elevated' if avg > 5 else 'moderate'}.", "data": []}
@app.get("/api/analytics/area-risk")
def analytics_area_risk(lat: float, lng: float, authorization: str = Header(...)):
    """Area Risk Score — 0-100 based on nearby historical reports."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    conn = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    rows = conn.execute("SELECT lat, lng, severity, category FROM reports WHERE created_at >= ?", (cutoff,)).fetchall()
    conn.close()
    nearby = []
    for r in rows:
        dist = haversine(lat, lng, r["lat"], r["lng"])
        if dist <= 1000:  
            nearby.append({"distance": dist, "severity": r["severity"], "category": r["category"]})
    if not nearby:
        return {"risk_score": 0, "risk_level": "Low", "nearby_count": 0, "factors": ["No reports in this area recently"]}
    score = 0
    for r in nearby:
        weight = {"High": 30, "Medium": 15, "Low": 5}.get(r["severity"], 10)
        dist_factor = max(0.2, 1 - (r["distance"] / 1000))
        score += weight * dist_factor
    score = min(100, int(score))
    level = "High" if score >= 60 else "Medium" if score >= 30 else "Low"
    factors = []
    high_count = sum(1 for r in nearby if r["severity"] == "High")
    if high_count: factors.append(f"{high_count} high-severity reports within 1km")
    factors.append(f"{len(nearby)} total reports in the area in last 2 weeks")
    cats = {}
    for r in nearby:
        cats[r["category"]] = cats.get(r["category"], 0) + 1
    top_cat = max(cats, key=cats.get)
    factors.append(f"Most common: {top_cat} ({cats[top_cat]} reports)")
    return {"risk_score": score, "risk_level": level, "nearby_count": len(nearby), "factors": factors}
@app.get("/api/analytics/insights")
def analytics_insights(authorization: str = Header(...)):
    """City-Level Intelligence — aggregated insights with Gemini narrative."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    conn = get_db()
    rows = conn.execute(
        "SELECT city, category, severity, created_at FROM reports WHERE city IS NOT NULL AND city != 'Unknown' ORDER BY created_at DESC LIMIT 100"
    ).fetchall()
    conn.close()
    if not rows:
        return {"narrative": "No city-level data available yet.", "cities": []}
    city_data = {}
    for r in rows:
        c = r["city"]
        city_data.setdefault(c, {"total": 0, "categories": {}, "severities": {}})
        city_data[c]["total"] += 1
        cat = r["category"]
        city_data[c]["categories"][cat] = city_data[c]["categories"].get(cat, 0) + 1
        sev = r["severity"]
        city_data[c]["severities"][sev] = city_data[c]["severities"].get(sev, 0) + 1
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = f"""Analyze this city-level waste report data and write a 2-3 sentence intelligence narrative.
Data: {json.dumps(city_data)}
Focus on: which cities have worst problems, dominant waste types, severity patterns.
Be specific and data-driven. Keep it under 200 chars. End with an actionable insight."""
            resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            return {"narrative": resp.text.strip(), "cities": city_data}
        except Exception:
            pass
    top_city = max(city_data, key=lambda c: city_data[c]["total"])
    return {"narrative": f"{top_city} leads with {city_data[top_city]['total']} reports. Focus cleanup efforts there.", "cities": city_data}
@app.get("/api/environment")
def get_environment_data(lat: float, lng: float):
    """Get AQI + weather for a location using Open-Meteo (free)."""
    result = {"aqi": None, "weather": None}
    try:
        aqi_resp = httpx.get(
            f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lng}&current=european_aqi,pm2_5,pm10,nitrogen_dioxide",
            timeout=5.0
        )
        if aqi_resp.status_code == 200:
            aq = aqi_resp.json().get("current", {})
            aqi_val = aq.get("european_aqi", 0)
            level = "Good" if aqi_val <= 20 else "Fair" if aqi_val <= 40 else "Moderate" if aqi_val <= 60 else "Poor" if aqi_val <= 80 else "Very Poor"
            color = "
            result["aqi"] = {"value": aqi_val, "level": level, "color": color, "pm2_5": aq.get("pm2_5"), "pm10": aq.get("pm10")}
    except Exception as e:
        log.warning(f"AQI fetch failed: {e}")
    try:
        wx_resp = httpx.get(
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
            timeout=5.0
        )
        if wx_resp.status_code == 200:
            wx = wx_resp.json().get("current", {})
            wmo = wx.get("weather_code", 0)
            wx_map = {0: ("☀️", "Clear"), 1: ("🌤️", "Partly Cloudy"), 2: ("⛅", "Cloudy"), 3: ("☁️", "Overcast"),
                      45: ("🌫️", "Fog"), 48: ("🌫️", "Rime Fog"), 51: ("🌦️", "Light Drizzle"), 53: ("🌦️", "Drizzle"),
                      55: ("🌧️", "Heavy Drizzle"), 61: ("🌧️", "Light Rain"), 63: ("🌧️", "Rain"), 65: ("🌧️", "Heavy Rain"),
                      71: ("🌨️", "Light Snow"), 73: ("🌨️", "Snow"), 75: ("❄️", "Heavy Snow"), 80: ("🌦️", "Showers"),
                      95: ("⛈️", "Thunderstorm"), 96: ("⛈️", "Hail Storm")}
            icon, desc = wx_map.get(wmo, ("🌡️", "Unknown"))
            result["weather"] = {
                "temp": wx.get("temperature_2m"), "humidity": wx.get("relative_humidity_2m"),
                "wind": wx.get("wind_speed_10m"), "icon": icon, "description": desc,
                "risk_note": "⚠️ Rain increases flooding risk from waste blockages" if wmo in (61,63,65,80,95,96) else
                             "🔥 Heat accelerates decomposition — faster cleanup needed" if wx.get("temperature_2m", 0) > 38 else None
            }
    except Exception as e:
        log.warning(f"Weather fetch failed: {e}")
    return result
@app.get("/api/disposal-guide")
def get_disposal_guide(category: str, authorization: str = Header(None)):
    """AI-powered disposal guide for a waste category."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        guides = {
            "Garbage": "Segregate into wet and dry waste. Wet waste goes for composting, dry waste for recycling.",
            "E-waste": "Never burn! Drop at authorized e-waste collection centres. Many brands offer free pickup.",
            "Debris": "Contact your local Nagar Nigam for debris removal. Heavy items need special vehicles.",
            "Other": "Check with your municipal office for proper disposal guidelines."
        }
        return {"guide": guides.get(category, guides["Other"]), "source": "built-in"}
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = f"""Give a brief, practical disposal guide for {category} waste in India. Include:
1. How to safely handle it
2. Where to dispose (specific Indian options like kabadiwala, authorized centres)
3. Environmental impact if not disposed properly
Keep it under 100 words. Plain text, no markdown."""
        resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return {"guide": resp.text.strip(), "source": "gemini"}
    except Exception:
        return {"guide": f"Dispose {category} waste at your nearest municipal collection point.", "source": "fallback"}
_rate_store: dict[str, list[float]] = {}
def check_rate_limit(phone: str, max_per_hour: int = 10) -> bool:
    """Returns True if within limit, False if exceeded."""
    import time
    now = time.time()
    window = 3600  
    if phone not in _rate_store:
        _rate_store[phone] = []
    _rate_store[phone] = [t for t in _rate_store[phone] if now - t < window]
    if len(_rate_store[phone]) >= max_per_hour:
        return False
    _rate_store[phone].append(now)
    return True
@app.get("/")
@app.get("/index.html")
def serve_frontend():
    from fastapi.responses import FileResponse
    import os
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    raise HTTPException(status_code=404, detail="index.html not found")
@app.get("/manifest.json")
def serve_manifest():
    from fastapi.responses import FileResponse
    import os
    if os.path.exists("manifest.json"):
        return FileResponse("manifest.json")
    raise HTTPException(status_code=404, detail="manifest.json not found")
@app.get("/sw.js")
def serve_sw():
    from fastapi.responses import FileResponse
    import os
    if os.path.exists("sw.js"):
        return FileResponse("sw.js")
    raise HTTPException(status_code=404, detail="sw.js not found")
@app.get("/logo.webp")
def serve_logo():
    from fastapi.responses import FileResponse
    import os
    if os.path.exists("logo.webp"):
        return FileResponse("logo.webp")
    raise HTTPException(status_code=404, detail="logo.webp not found")
@app.get("/logo_circular.webp")
def serve_logo_circular():
    from fastapi.responses import FileResponse
    import os
    if os.path.exists("logo_circular.webp"):
        return FileResponse("logo_circular.webp")
    raise HTTPException(status_code=404, detail="logo_circular.webp not found")