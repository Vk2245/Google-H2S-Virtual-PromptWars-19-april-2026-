<div align="center">

<img src="logo.webp" alt="WasteWatch Logo" width="160" />

# 🌿 WasteWatch
### India's First AI-Native Civic Intelligence Platform

**Built for Bharat · Powered by Google Gemini · Engineered with Google Antigravity**

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Gemini 2.5](https://img.shields.io/badge/Gemini_2.5_Flash-AI-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://aistudio.google.com)
[![PWA](https://img.shields.io/badge/PWA-Ready-5A0FC8?style=for-the-badge&logo=pwa&logoColor=white)](https://web.dev/progressive-web-apps/)
[![Deployed](https://img.shields.io/badge/Deployed_on-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://wastewatch224.onrender.com/)

---

### 🚀 [Live Demo](https://wastewatch224.onrender.com/) | 📁 [Source Code](https://github.com/Vk2245/Google-H2S-Virtual-PromptWars-19-april-2026-) | 🛡️ [Security Audit](#-security--integrity)

</div>

## 🎯 The Crisis: Municipal Waste in India

Every day, India generates over **150,000 tonnes of municipal solid waste**. Despite the Swachh Bharat Mission (Clean India Mission), a critical gap remains: the **"Last-Mile Civic Reporting Gap."**

- **The Problem**: Citizens lack a structured, accountable method to report waste dumps. WhatsApp reports are ignored, phone calls are untracked, and resolution timelines are non-existent.
- **The Exclusion**: Digital civic tools often exclude illiterate or non-technical users, particularly those who prefer regional languages like Hindi.
- **The Blindness**: Municipal authorities lack a "Real-Time Hotspot Map" to prioritize cleanup efforts based on severity and health risk.

**WasteWatch** is the bridge. We provide a mobile-first, AI-native platform that transforms every citizen into an Eco-Warrior.

---

## 💡 The WasteWatch Solution

We don't just report waste; we **analyze, categorize, and route it** with surgical precision using the Google ecosystem.

### 🤖 Intelligent Core (Google Gemini 2.5 Flash)
Our AI doesn't just "see" an image; it understands the civic context:
- **Visual Classification**: Differentiates between dry, wet, hazardous, and construction waste.
- **Severity Scoring (1–10)**: Calculates health risks and environmental impact instantly.
- **Disposal Intelligence**: Provides users with Gemini-generated guides on how that specific waste should be handled.
- **Personalized Narratives**: Generates AI insights for users to help them understand their local city's waste trends.

### 🗣️ Inclusive Interaction (Bilingual Voice Agent)
To ensure **Civic Inclusion**, we built a Web-Speech-API-powered guide:
- **Vernacular Support**: Full reporting flow in **Hindi & English**.
- **Voice-First Navigation**: Illiterate users can simply speak their report, and the AI processes the intent.
- **Fallback Resilience**: Uses **Groq (Llama-4-Scout)** for high-speed fallback when Gemini hits rate limits.

### 🏆 Civic Gamification
Transformation requires engagement. We've built a robust incentive engine:
- **XP & Achievement Badges**: Unlock 'Hotspot Hunter' or 'Eco Warrior' statuses.
- **National & City Leaderboards**: Competitive cleanup culture backed by real-time ranking.
- **Anti-Gaming Shield**: AI-powered fraud detection ensures only genuine reports earn points.

---

## 🏗️ System Architecture

```mermaid
graph TD
    User((Citizen)) -->|Voice/Photo| PWA[WasteWatch App]
    subgraph Frontend (PWA)
        PWA -->|GPS/Media| SW[Service Worker]
        SW -->|Local Cache| Offline[Offline Mode]
    end
    
    PWA -->|REST API| BE[FastAPI Backend]
    
    subgraph AI Intelligence Layer
        BE -->|Async Call| Gemini[Gemini 2.5 Flash]
        BE -->|Fallback| Groq[Groq Llama-4]
        Gemini -->|Analysis| BE
    end
    
    subgraph Data & Integration
        BE -->|SQL Ops| DB[(SQLite/Supabase)]
        BE -->|SMTP| Resend[Resend API]
        Resend -->|Notification| Auth[Municipal Authority]
    end
    
    BE -->|GeoJSON| Maps[Live Heatmap]
```

---

## 🔌 API & Technology Stack

| Component | Technology | Purpose |
|:--- |:--- |:--- |
| **Brain** | Google Gemini 2.5 Flash | Classification, Voice, Analytics |
| **Speed** | Groq (Llama-4-Scout) | High-speed AI Fallback |
| **Backend** | FastAPI (Python 3.13) | Asynchronous Logic, Auth, Routing |
| **Frontend** | Vanilla JS + Tailwind | Premium UI, Glassmorphism, PWA |
| **Messaging** | Resend API | Smart Authority Notifications |
| **Geospatial** | Leaflet + Nominatim | Live Mapping & Geocoding |
| **Persistence** | Supabase / SQLite | Multi-mode Database Support |

---

## 🛡️ Security & Integrity

- **JWT Authentication**: Secure user sessions with standard encryption.
- **Privacy First**: Phone numbers are masked (`******3210`) in all public leaderboards.
- **Geofencing**: Blocks duplicate submissions within a 200m radius to prevent point-farming.
- **AI Fraud Analysis**: Gemini validates if the photo is *actually* a civic issue (rejects memes, selfies, or stock photos).

---

## 🧪 Comprehensive Testing

WasteWatch is built with **Resilience Engineering**. Our `pytest` suite covers:
- ✅ **API Health**: Heartbeat and dependency checks.
- ✅ **Auth Flow**: OTP verification and JWT longevity.
- ✅ **Anti-Spam**: Rate limits and geofencing integrity.
- ✅ **AI Responses**: Mocking Gemini payloads to ensure UI stability.

Execute tests: `python -m pytest test_main.py -v`

---

## 🚢 Deployment & Scale

Deployed on **Render.com** with automated CI/CD:
- **URL**: [wastewatch224.onrender.com](https://wastewatch224.onrender.com/)
- **Infrastructure**: Ready for Google Cloud Run (Docker-compatible).

---

## 🙏 Credits & Acknowledgments

- **Google H2S Team**: For organizing the Virtual PromptWars.
- **Google Antigravity**: The AI agent that orchestrated this development cycle.
- **Swachh Bharat Mission**: Ongoing inspiration for building #AIforBharat.

---
<div align="center">
  <b>Designed for Change. Built for Bharat.</b> <br>
  © 2026 WasteWatch Project. MIT Licensed.
</div>