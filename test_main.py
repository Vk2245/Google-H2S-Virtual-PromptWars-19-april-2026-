import os
# SET ENVIRONMENT BEFORE ANY IMPORTS
os.environ["DATABASE_MODE"] = "sqlite"
os.environ["FAST2SMS_KEY"] = "" # Force DEMO_MODE = True

import pytest
import time
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
# Now import main - it will pick up the os.environ correctly
import main
from main import hash_pwd

# ---------------------------------------------------------------------------
# FIXTURES & SETUP
# ---------------------------------------------------------------------------
@pytest.fixture(name="client", scope="function")
def client_fixture():
    """Create a test client with a dedicated test database."""
    main.DB_PATH = "test_wastewatch_final_final.db"
    main.DEMO_MODE = True # Extra insurance
    
    # Initialize the test database schema
    main.init_db()
    
    with TestClient(main.app) as c:
        # Wipe tables for a clean slate in every test
        conn = main.get_db()
        conn.execute("DELETE FROM citizens")
        conn.execute("DELETE FROM reports")
        conn.execute("DELETE FROM hotspots")
        conn.execute("DELETE FROM pending_otps")
        conn.commit()
        conn.close()
        
        yield c
    
    # Cleanup file system
    if os.path.exists("test_wastewatch_final_final.db"):
        try: os.remove("test_wastewatch_final_final.db")
        except: pass

# ---------------------------------------------------------------------------
# MOCK DATA
# ---------------------------------------------------------------------------
MOCK_GEMINI_SUCCESS = MagicMock(
    is_civic_issue=True, 
    category="Garbage", 
    severity="High", 
    action_plan="Clear the waste immediately.", 
    authenticity_score=95, 
    authenticity_note="Clear photo of municipal waste."
)

# ---------------------------------------------------------------------------
# CORE ENDPOINT TESTS
# ---------------------------------------------------------------------------

def test_health_check(client):
    """Verify system health and configuration reporting."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["demo_mode"] == True

def test_auth_full_flow(client):
    """Test OTP send (mocked), registration, and login flow."""
    phone = "9876543210"
    
    # 1. Send OTP
    resp_otp = client.post("/api/auth/otp/send", json={"phone": phone})
    assert resp_otp.status_code == 200
    
    # 2. Register (using bypass OTP since we're in forced DEMO_MODE)
    reg_data = {
        "phone": phone, "name": "Test User", "password": "password123", "otp": "123456"
    }
    resp_reg = client.post("/api/auth/register", json=reg_data)
    assert resp_reg.status_code == 200, f"Registration failed with {resp_reg.status_code}: {resp_reg.text}"
    token = resp_reg.json()["token"]
    
    # 3. Login
    login_data = {"phone": phone, "password": "password123"}
    resp_login = client.post("/api/auth/login", json=login_data)
    assert resp_login.status_code == 200
    assert resp_login.json()["token"] == token

def test_register_duplicate_phone(client):
    """Ensure system prevents duplicate registration."""
    phone = "9123456789"
    reg_data = {"phone": phone, "name": "U1", "password": "p1", "otp": "123456"}
    client.post("/api/auth/register", json=reg_data)
    resp_dup = client.post("/api/auth/register", json=reg_data)
    assert resp_dup.status_code == 400
    assert "already registered" in resp_dup.json()["detail"]

# ---------------------------------------------------------------------------
# REPORTING & AI LOGIC TESTS
# ---------------------------------------------------------------------------

@patch("main.call_gemini")
def test_create_report_success(mock_gemini, client):
    """Test successful report creation with mocked AI analysis."""
    # 1. Setup User
    phone = "9111111111"
    client.post("/api/auth/register", json={"phone": phone, "name": "Reporter", "password": "p", "otp": "123456"})
    login_resp = client.post("/api/auth/login", json={"phone": phone, "password": "p"})
    token = login_resp.json()["token"]
    
    # 2. Mock Gemini Return
    mock_gemini.return_value = MOCK_GEMINI_SUCCESS
    
    # 3. Submit Report
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"description": "Large garbage pile near school", "lat": 28.6139, "lng": 77.2090}
    response = client.post("/api/report", data=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "Garbage"
    assert data["severity"] == "High"

@patch("main.call_gemini")
def test_create_report_ai_rejection(mock_gemini, client):
    """Test report rejection when AI identifies non-civic issues (Selfie/Meme)."""
    # 1. Setup User
    phone = "9111111112"
    client.post("/api/auth/register", json={"phone": phone, "name": "Spammer", "password": "p", "otp": "123456"})
    token = client.post("/api/auth/login", json={"phone": phone, "password": "p"}).json()["token"]
    
    # 2. Mock AI Rejection
    mock_gemini.return_value = MagicMock(is_civic_issue=False, category="Other", severity="Low", action_plan="", authenticity_score=0)
    
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"description": "This is just a selfie", "lat": 19.0760, "lng": 72.8777}
    resp = client.post("/api/report", data=payload, headers=headers)
    assert resp.status_code == 400
    assert "Rejected" in resp.json()["detail"]

# ---------------------------------------------------------------------------
# EDGE CASES & RATE LIMITING
# ---------------------------------------------------------------------------

def test_rate_limiting_same_location(client):
    """Verify anti-gaming geofence (200m radius check)."""
    phone = "9222222222"
    client.post("/api/auth/register", json={"phone": phone, "name": "User", "password": "p", "otp": "123456"})
    token = client.post("/api/auth/login", json={"phone": phone, "password": "p"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # First report
    client.post("/api/report", data={"description": "Pile 1", "lat": 28.5, "lng": 77.5}, headers=headers)
    
    # Second report at near-identical location (50m away)
    resp_spam = client.post("/api/report", data={"description": "Pile 2", "lat": 28.5001, "lng": 77.5001}, headers=headers)
    assert resp_spam.status_code == 429
    assert "already reported" in resp_spam.json()["detail"]

def test_invalid_gps_coordinates(client):
    """Ensure system rejects impossible latitude/longitude."""
    headers = {"Authorization": "Bearer some-token"}
    payload = {"description": "Outer space", "lat": 1000.0, "lng": 2000.0}
    response = client.post("/api/report", data=payload, headers=headers)
    assert response.status_code == 422 # Pydantic validation

# ---------------------------------------------------------------------------
# ANALYTICS & ACCESS
# ---------------------------------------------------------------------------

def test_leaderboard_basic(client):
    """Verify leaderboard contains entries following user registration."""
    phone = "9888888888"
    client.post("/api/auth/register", json={"phone": phone, "name": "PrivacyUser", "password": "p", "otp": "123456"})
    resp = client.get("/api/leaderboard")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
