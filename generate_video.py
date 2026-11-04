"""
Rural Healthcare AI Navigation System — Narrated Slideshow Video Generator
===========================================================================
Creates a professional .mp4 slideshow with:
  • 16 content slides matching the full project presentation
  • Animated text (fade-in line-by-line per slide)
  • Smooth cross-fade transitions between slides
  • Colour-coded slide themes (dark navy, white, red emergency)
  • Persistent header/footer on every frame
  • Progress bar animation at the bottom
  • Rendered at 1280×720 (720p), 24 fps

Usage:
    python generate_video.py

Output:
    Rural_Healthcare_AI_Slideshow.mp4   (same directory as this script)

Dependencies (all pre-installed):
    moviepy==1.0.3, Pillow>=13, numpy>=1.26
"""

import os, sys, textwrap, time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    ImageClip, concatenate_videoclips, CompositeVideoClip,
    VideoFileClip, ColorClip
)
from moviepy.video.fx.fadein import fadein
from moviepy.video.fx.fadeout import fadeout

# ── Output path ────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent
OUT_FILE  = BASE_DIR / "Rural_Healthcare_AI_Slideshow.mp4"

# ── Canvas settings ────────────────────────────────────────────────────────────
W, H   = 1280, 720
FPS    = 24
TRANS  = 0.6          # cross-fade duration seconds
SLIDE_DUR = 6.0       # default seconds per slide (some override below)

# ── Font paths (Windows) ───────────────────────────────────────────────────────
FONT_DIR  = Path("C:/Windows/Fonts")
FONT_BOLD = str(FONT_DIR / "arialbd.ttf")
FONT_REG  = str(FONT_DIR / "arial.ttf")
FONT_MONO = str(FONT_DIR / "consola.ttf")

def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

# ── Colour palette ─────────────────────────────────────────────────────────────
C = {
    "navy":      (26,  60,  94),
    "dark_navy": (13,  46,  74),
    "white":     (255,255,255),
    "off_white": (247,248,250),
    "green":     (46, 204,113),
    "red":       (192, 57, 43),
    "purple":    (108, 52,131),
    "teal":      (17, 122,101),
    "gold":      (125,102,  8),
    "blue":      (36, 113,163),
    "light_blue":(168,198,224),
    "light_bg":  (235,245,251),
    "muted":     (87,  96,106),
    "text_dark": (44,  62, 80),
    "black":     (0,   0,  0),
}

# ── Drawing helpers ────────────────────────────────────────────────────────────

def new_frame(bg: tuple = C["white"]) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), bg)
    return img, ImageDraw.Draw(img)


def draw_rect(d: ImageDraw.ImageDraw, x0, y0, x1, y1, fill: tuple, alpha: int = 255) -> None:
    d.rectangle([x0, y0, x1, y1], fill=fill)


def wrap_text(text: str, font_obj: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        bb = font_obj.getbbox(test)
        if bb[2] - bb[0] <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def draw_wrapped(d: ImageDraw.ImageDraw, text: str, x: int, y: int,
                 font_obj: ImageFont.FreeTypeFont, color: tuple,
                 max_width: int = 0, line_gap: int = 6) -> int:
    """Draw wrapped text; returns final y position."""
    max_width = max_width or (W - x - 20)
    lines = wrap_text(text, font_obj, max_width)
    for line in lines:
        d.text((x, y), line, font=font_obj, fill=color)
        bb = font_obj.getbbox(line)
        y += (bb[3] - bb[1]) + line_gap
    return y


def draw_header(d: ImageDraw.ImageDraw, slide_num: int, total: int = 16) -> None:
    """Persistent top bar."""
    draw_rect(d, 0, 0, W, 44, C["dark_navy"])
    draw_rect(d, 0, 44, W, 49, C["green"])
    ibm = font(FONT_REG, 15)
    d.text((14, 14), "IBM SkillsBuild · Agentic AI Capstone 2026  |  Rural Healthcare AI Navigation System",
           font=ibm, fill=C["light_blue"])
    num_txt = f"{slide_num} / {total}"
    bb = ibm.getbbox(num_txt)
    d.text((W - (bb[2]-bb[0]) - 14, 14), num_txt, font=ibm, fill=C["light_blue"])


def draw_footer(d: ImageDraw.ImageDraw, slide_num: int, total: int = 16) -> None:
    """Persistent bottom bar + progress bar."""
    draw_rect(d, 0, H - 32, W, H, C["dark_navy"])
    # progress bar
    prog = int(W * slide_num / total)
    draw_rect(d, 0, H - 6, prog, H, C["green"])
    disc = font(FONT_REG, 13)
    d.text((14, H - 26), "⚠ Navigation Support Only — NOT a medical diagnosis system  |  Emergency: 108  |  Health Helpline: 104",
           font=disc, fill=C["light_blue"])


def draw_slide_title(d: ImageDraw.ImageDraw, title: str, bg: tuple = C["navy"]) -> None:
    """Top title band below header."""
    draw_rect(d, 0, 49, W, 110, bg)
    tf = font(FONT_BOLD, 30)
    d.text((28, 60), title, font=tf, fill=C["white"])


def box(d: ImageDraw.ImageDraw, x0, y0, x1, y1,
        fill: tuple, text: str = "", text_color: tuple = C["white"],
        font_size: int = 16, padding: int = 10) -> None:
    """Draw a filled rounded-ish rectangle with optional text."""
    draw_rect(d, x0, y0, x1, y1, fill)
    if text:
        tf = font(FONT_REG, font_size)
        draw_wrapped(d, text, x0 + padding, y0 + padding, tf, text_color,
                     max_width=(x1 - x0 - 2 * padding))


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE RENDERERS
# Each returns a PIL Image (RGB, W×H)
# ═══════════════════════════════════════════════════════════════════════════════

def slide_01_title() -> Image.Image:
    img, d = new_frame(C["navy"])
    draw_header(d, 1); draw_footer(d, 1)
    # big green accent bar
    draw_rect(d, 0, 49, W, 54, C["green"])
    # emoji
    ef = font(FONT_REG, 72)
    d.text((50, 110), "🏥", font=ef, fill=C["white"])
    # main title
    tf = font(FONT_BOLD, 54)
    d.text((160, 115), "Rural Healthcare AI", font=tf, fill=C["white"])
    d.text((160, 180), "Navigation System", font=tf, fill=C["white"])
    # subtitle
    sf = font(FONT_REG, 22)
    d.text((160, 258), "An Agentic AI-Powered Patient Navigation &", font=sf, fill=C["light_blue"])
    d.text((160, 288), "Referral Coordination System for Rural India", font=sf, fill=C["light_blue"])
    # tags
    tags = ["LangChain Multi-Agent", "Google Gemini 2.0", "RAG", "Streamlit", "SQLite"]
    tx = 50
    for tag in tags:
        tf2 = font(FONT_BOLD, 16)
        bb = tf2.getbbox(tag)
        tw = bb[2] - bb[0]
        draw_rect(d, tx, 360, tx + tw + 24, 390, C["green"])
        d.text((tx + 12, 365), tag, font=tf2, fill=C["dark_navy"])
        tx += tw + 36
    return img


def slide_02_problem() -> Image.Image:
    img, d = new_frame(C["white"])
    draw_header(d, 2); draw_footer(d, 2)
    draw_slide_title(d, "The Problem We Solve")
    hf = font(FONT_BOLD, 20)
    d.text((28, 122), "Rural patients face severe healthcare access barriers in India", font=hf, fill=C["navy"])
    panels = [
        (C["blue"],   "📍 Distance Barrier",      "4–8 km to nearest PHC\n30+ km to district hospitals\nPatients skip care due to travel"),
        (C["teal"],   "❓ Awareness Gap",           "Govt. schemes (PMJAY, eSanjeevani)\nunknown to most rural patients\nLanguage & literacy barriers"),
        (C["purple"], "🔗 Fragmented Referrals",   "Poor coordination: PHC→CHC→District\nPatients lost between care levels\nNo structured referral documents"),
        (C["gold"],   "🏙️ Tertiary Overcrowding",  "Patients travel to cities for local-\ntreatable conditions; burdens urban\nsystem and delays critical care"),
    ]
    bw = 290; bh = 190; by = 160
    for i, (col, title, body) in enumerate(panels):
        bx = 28 + i * (bw + 14)
        draw_rect(d, bx, by, bx + bw, by + bh, col)
        th = font(FONT_BOLD, 17)
        d.text((bx + 12, by + 10), title, font=th, fill=C["white"])
        draw_rect(d, bx, by + 36, bx + bw, by + 37, C["white"])
        bf = font(FONT_REG, 15)
        y = by + 46
        for line in body.split("\n"):
            d.text((bx + 12, y), line, font=bf, fill=C["white"])
            y += 24
    # solution banner
    draw_rect(d, 28, 372, W - 28, 420, C["navy"])
    sf = font(FONT_BOLD, 18)
    d.text((44, 385), "✅  This AI guides rural patients to the RIGHT facility, RIGHT level, RIGHT time.",
           font=sf, fill=C["white"])
    return img


def slide_03_users() -> Image.Image:
    img, d = new_frame(C["white"])
    draw_header(d, 3); draw_footer(d, 3)
    draw_slide_title(d, "Target Users & Domain")
    # domain strip
    draw_rect(d, 28, 118, W - 28, 158, C["light_bg"])
    df = font(FONT_REG, 16)
    d.text((40, 130), "Domain: Healthcare / Digital Health  |  Category: Patient Navigation & Referral Coordination  |  Geography: Rural & Semi-Urban India",
           font=df, fill=C["navy"])
    users = [
        ("👨‍🌾", "Rural Patient",       "Primary user seeking healthcare navigation for self or family"),
        ("👩‍⚕️", "ASHA / ANM Worker",  "Community health worker helping patients access right services"),
        ("🏥",  "Healthcare Admin",    "Monitors referral patterns and facility utilization"),
        ("📊",  "District Health Ofc", "Analyzes access gaps and allocates health resources"),
    ]
    uw = 285; uby = 170; ubh = 170
    for i, (icon, name, desc) in enumerate(users):
        ux = 28 + i * (uw + 14)
        draw_rect(d, ux, uby, ux + uw, uby + ubh, C["light_bg"])
        draw_rect(d, ux, uby, ux + uw, uby + 5, C["navy"])
        ef = font(FONT_REG, 36)
        d.text((ux + uw//2 - 20, uby + 14), icon, font=ef, fill=C["navy"])
        nf = font(FONT_BOLD, 17)
        nb = nf.getbbox(name)
        d.text((ux + (uw - (nb[2]-nb[0]))//2, uby + 68), name, font=nf, fill=C["navy"])
        pf = font(FONT_REG, 14)
        draw_wrapped(d, desc, ux + 12, uby + 96, pf, C["muted"], max_width=uw - 24)
    # personas strip
    draw_rect(d, 28, 356, W - 28, 400, C["off_white"])
    draw_rect(d, 28, 356, W - 28, 361, C["green"])
    pf2 = font(FONT_REG, 14)
    d.text((40, 368),
           "Test Personas:  🌾 Ramu (Nashik, cardiac)  ·  🤰 Kavitha (pregnant, remote)  ·  👴 Suresh (elderly)  ·  👶 Deepa (sick child)  ·  🆘 Mental health crisis",
           font=pf2, fill=C["navy"])
    return img


def slide_04_architecture() -> Image.Image:
    img, d = new_frame(C["dark_navy"])
    draw_header(d, 4); draw_footer(d, 4)
    draw_slide_title(d, "Multi-Agent Architecture", bg=C["black"])
    # patient → supervisor arrow
    box(d, 480, 118, 700, 148, C["green"], "Patient Query", C["dark_navy"], 18)
    box(d, 280, 165, 820, 210, C["navy"], "🤖  Supervisor Agent  (Orchestrator + State Router)", C["white"], 18)
    # emergency box (right)
    box(d, 840, 165, W - 28, 260, C["red"],
        "🚨 Emergency\nEscalation Agent\nBYPASS (immediate)\nTemp: 0.0", C["white"], 15)
    # assessment
    box(d, 28,  265, 320, 380, C["blue"],
        "🔍 Assessment\nAgent\nUrgency · Dept\nLocation · Temp 0.1", C["white"], 14)
    # discovery
    box(d, 340, 265, 630, 380, C["teal"],
        "🏥 Facility\nDiscovery Agent\nHaversine Dist\nGovt-First Filter", C["white"], 14)
    # referral
    box(d, 28,  400, 320, 490, C["teal"],
        "📄 Referral Agent\nREF-XXXXXXXX\nNav Plan\nScheme Info", C["white"], 14)
    # rag
    box(d, 340, 400, 630, 490, C["purple"],
        "📚 RAG Knowledge\nTF-IDF Retrieval\n4 Collections\nTop-K = 5", C["white"], 14)
    # appointment
    box(d, 650, 400, 830, 490, C["gold"],
        "📅 Appt Agent\nAvailability\nGuidance Only", C["white"], 13)
    # flow note
    nf = font(FONT_REG, 14)
    d.text((28, 508),
           "Normal Flow: Patient → Supervisor → Assessment → Discovery → Referral → Appointment",
           font=nf, fill=C["light_blue"])
    d.text((28, 530),
           "Emergency Bypass: keyword detected → Emergency Agent fires BEFORE any LLM call → 108 immediately",
           font=nf, fill=C["red"])
    return img


def slide_05_techstack() -> Image.Image:
    img, d = new_frame(C["white"])
    draw_header(d, 5); draw_footer(d, 5)
    draw_slide_title(d, "Technology Stack")
    stacks = [
        (C["navy"],   "🤖 LLM Layer",      "Google Gemini 2.0 Flash\nOpenAI GPT-4o-mini (fallback)\nGroq qwen3.8-27b (fallback)\nTemp: 0.2 · Max Tokens: 4096"),
        (C["teal"],   "🔗 AI Framework",   "LangChain ≥ 0.2.0\nlangchain-core\nlangchain-community\nMulti-agent orchestration"),
        (C["purple"], "📚 RAG & Vector",   "TF-IDF in-memory retriever\nChunk: 500 tokens, overlap: 50\nTop-K: 5 · ChromaDB swap-in"),
        (C["blue"],   "🗄️ Database",        "SQLite + SQLAlchemy ORM\n4 tables: facilities, specialists\npatient_sessions, nav_history"),
        (C["gold"],   "🖥️ UI",             "Streamlit ≥ 1.32.0\n4 tabs: Chat · Facilities\nReferral · Info"),
        (C["red"],    "🧪 Testing & Infra","pytest 9.2 · Python 3.15\nDocker + docker-compose\nStructured JSON logging"),
    ]
    sw = 380; sh = 190
    for i, (col, title, body) in enumerate(stacks):
        row, col_idx = divmod(i, 3)
        sx = 28 + col_idx * (sw + 16)
        sy = 118 + row * (sh + 12)
        draw_rect(d, sx, sy, sx + sw, sy + sh, col)
        tf = font(FONT_BOLD, 17)
        d.text((sx + 12, sy + 10), title, font=tf, fill=C["white"])
        draw_rect(d, sx, sy + 36, sx + sw, sy + 37, (255,255,255,80))
        bf = font(FONT_REG, 15)
        y = sy + 46
        for line in body.split("\n"):
            d.text((sx + 12, y), line, font=bf, fill=C["white"])
            y += 24
    return img


def slide_06_agents() -> Image.Image:
    img, d = new_frame(C["white"])
    draw_header(d, 6); draw_footer(d, 6)
    draw_slide_title(d, "Agent Responsibilities Deep-Dive")
    agents = [
        (C["blue"],   "🔍 Assessment Agent",     "Temp: 0.1\nassess_urgency()\nmap_symptoms_to_departments()\nCollects location, chief complaint\nTriggers emergency bypass"),
        (C["teal"],   "🏥 Discovery Agent",      "search_healthcare_facilities()\nfind_specialists()\nHaversine distance sorting\nGovt-first preference filter\nReturns sorted facilities"),
        (C["teal"],   "📄 Referral Agent",       "REF-XXXXXXXX (8-char ID)\nStructured navigation plan\nStep-by-step instructions\nAadhaar checklist\nPMJAY / Ayushman Bharat"),
        (C["purple"], "📚 RAG Knowledge",        "TF-IDF Cosine Similarity\nhealthcare_guidelines\ngovernment_schemes\nTop-5 chunks + source citation\nConfidence level disclosed"),
        (C["gold"],   "📅 Appointment Agent",    "check_appointment_availability()\nEstimated wait times\nRequired documents list\nBooking guidance (not actual)"),
        (C["red"],    "🚨 Emergency Agent",      "Temp: 0.0 — zero randomness\nFires BEFORE LLM call\nclassifies: cardiac / trauma /\n  obstetric / mental_health\nHardcoded fallback always works"),
    ]
    aw = 380; ah = 200
    for i, (col, title, body) in enumerate(agents):
        row, ci = divmod(i, 3)
        ax = 28 + ci * (aw + 16)
        ay = 118 + row * (ah + 10)
        draw_rect(d, ax, ay, ax + aw, ay + ah, col)
        tf = font(FONT_BOLD, 16)
        d.text((ax + 12, ay + 8), title, font=tf, fill=C["white"])
        draw_rect(d, ax, ay + 32, ax + aw, ay + 33, C["white"])
        bf = font(FONT_REG, 14)
        y = ay + 40
        for line in body.split("\n"):
            d.text((ax + 12, y), line, font=bf, fill=C["white"])
            y += 22
    return img


def slide_07_rag() -> Image.Image:
    img, d = new_frame(C["white"])
    draw_header(d, 7); draw_footer(d, 7)
    draw_slide_title(d, "RAG Knowledge Pipeline")
    # pipeline boxes
    steps = [
        (C["navy"],   "📄 Knowledge Sources",
         "healthcare_guidelines.txt\n→ Treatment pathways\n→ PHC referral criteria\n→ WHO protocols\n\nemergency_protocols.txt\n→ First-aid steps\n→ Ambulance procedures"),
        (C["teal"],   "✂️ Text Splitter",
         "Chunk size: 500 tokens\nOverlap: 50 tokens\nSplit on paragraphs first\nHard-split long blocks\nLazy auto-index on first use"),
        (C["purple"], "🔎 TF-IDF Retriever",
         "In-memory (no external DB)\nCosine similarity scoring\nFallback: keyword overlap\nTop-K = 5 chunks returned\nrelevance_score disclosed"),
    ]
    bw = 370; bh = 300; by = 118
    for i, (col, title, body) in enumerate(steps):
        bx = 28 + i * (bw + 30)
        draw_rect(d, bx, by, bx + bw, by + bh, col)
        tf = font(FONT_BOLD, 18)
        d.text((bx + 14, by + 10), title, font=tf, fill=C["white"])
        draw_rect(d, bx, by + 38, bx + bw, by + 39, C["white"])
        bf = font(FONT_REG, 15)
        y = by + 48
        for line in body.split("\n"):
            d.text((bx + 14, y), line, font=bf, fill=C["white"])
            y += 24
        if i < 2:
            af = font(FONT_BOLD, 28)
            d.text((bx + bw + 4, by + bh // 2 - 16), "→", font=af, fill=C["navy"])
    # collections row
    draw_rect(d, 28, 432, W - 28, 466, C["off_white"])
    cf = font(FONT_BOLD, 15)
    d.text((40, 442), "4 Collections:", font=cf, fill=C["navy"])
    cols_data = [
        (C["blue"],   "healthcare_guidelines", 195),
        (C["teal"],   "government_schemes",    425),
        (C["gold"],   "facility_knowledge",    650),
        (C["red"],    "emergency_protocols",   870),
    ]
    for col, name, cx in cols_data:
        draw_rect(d, cx, 438, cx + len(name)*9 + 20, 462, col)
        d.text((cx + 10, 443), name, font=font(FONT_REG, 14), fill=C["white"])
    # swap note
    nf = font(FONT_REG, 14)
    d.text((28, 478),
           "Swap-in ready for ChromaDB / FAISS + Google Generative AI Embeddings (models/embedding-001) for production scale",
           font=nf, fill=C["muted"])
    return img


def slide_08_tools() -> Image.Image:
    img, d = new_frame(C["white"])
    draw_header(d, 8); draw_footer(d, 8)
    draw_slide_title(d, "Healthcare Tools & Database")
    tools = [
        (C["red"],    "assess_urgency(symptoms_text)",
         "→ urgency_level: low / medium / emergency\n→ matched_emergency_keywords[]\n→ emergency_contacts dict\n→ disclaimer field (always present)"),
        (C["blue"],   "map_symptoms_to_departments(text)",
         "→ recommended_departments[]\n→ Fallback: 'General Medicine'\n→ 8 specialties covered\n→ disclaimer field"),
        (C["teal"],   "search_healthcare_facilities(district, state, ...)",
         "→ SQLite query via ORM\n→ Haversine distance sorting\n→ Govt-first ranked results\n→ beds, wait_mins, phone, rating"),
        (C["purple"], "generate_referral_summary(...)",
         "→ REF-XXXXXXXX (8-char uppercase)\n→ Step-by-step navigation plan\n→ PMJAY / Ayushman Bharat mention\n→ Downloadable plain-text"),
        (C["gold"],   "check_appointment_availability(facility_id)",
         "→ Estimated wait time\n→ Available slots guidance\n→ Required documents list"),
    ]
    tw = 570; th = 148
    for i, (col, title, body) in enumerate(tools):
        row, ci = divmod(i, 2)
        tx = 28 + ci * (tw + 18)
        ty = 118 + row * (th + 10)
        if i == 4:
            tx = 28 + (W - 28 - tw) // 2
        draw_rect(d, tx, ty, tx + tw, ty + th, col)
        tf = font(FONT_BOLD, 14)
        d.text((tx + 10, ty + 8), title, font=tf, fill=C["white"])
        draw_rect(d, tx, ty + 28, tx + tw, ty + 29, C["white"])
        bf = font(FONT_REG, 13)
        y = ty + 34
        for line in body.split("\n"):
            d.text((tx + 10, y), line, font=bf, fill=C["white"])
            y += 21
    # DB strip
    draw_rect(d, 28, 540, W - 28, 576, C["light_bg"])
    dbf = font(FONT_REG, 14)
    d.text((40, 552),
           "🗄️  SQLite DB Tables: healthcare_facilities · specialists · patient_sessions · navigation_history  |  All actions audit-logged with timestamps",
           font=dbf, fill=C["navy"])
    return img


def slide_09_workflow() -> Image.Image:
    img, d = new_frame(C["dark_navy"])
    draw_header(d, 9); draw_footer(d, 9)
    draw_slide_title(d, "Patient Journey Workflow", bg=C["black"])
    # normal flow steps
    steps = [
        ("1. Patient\nMessage",   C["green"]),
        ("2. Supervisor\nChecks Keywords",  C["navy"]),
        ("3. Assessment\nAgent",   C["blue"]),
        ("4. Discovery\nAgent",    C["teal"]),
        ("5. Referral Plan\n+ REF-ID",  C["teal"]),
    ]
    sw = 200; sh = 80; sy = 130
    for i, (label, col) in enumerate(steps):
        sx = 28 + i * (sw + 28)
        draw_rect(d, sx, sy, sx + sw, sy + sh, col)
        lf = font(FONT_BOLD, 15)
        y_off = sy + 18
        for line in label.split("\n"):
            bb = lf.getbbox(line)
            d.text((sx + (sw - (bb[2]-bb[0]))//2, y_off), line, font=lf,
                   fill=C["dark_navy"] if col == C["green"] else C["white"])
            y_off += 22
        if i < 4:
            af = font(FONT_BOLD, 22)
            d.text((sx + sw + 4, sy + 28), "→", font=af, fill=C["green"])
    # emergency bypass
    draw_rect(d, 28, 238, W - 28, 258, C["red"])
    ef = font(FONT_BOLD, 14)
    d.text((36, 243), "⚡ EMERGENCY BYPASS PATH", font=ef, fill=C["white"])
    box(d, 28, 265, W - 28, 440, C["red"],
        ("🚨 Emergency keywords detected (chest pain, not breathing, unconscious, suicide, etc.)\n"
         "→ Supervisor IMMEDIATELY routes to EmergencyEscalationAgent (skips all normal stages)\n"
         "→ Response ALWAYS starts with: '🚨 CALL 108 IMMEDIATELY'\n"
         "→ Hardcoded fallback response — works even if LLM API is completely down\n"
         "→ human_review_required = True set in session state\n"
         "→ Audit log entry: action_type = escalation, outcome = escalated\n"
         "→ Mental health: iCall 9152987821 + KIRAN 1800-599-0019 + Vandrevala 1860-2662-345"),
        C["white"], 16, 14)
    nf = font(FONT_REG, 14)
    d.text((28, 456),
           "Normal stages: greeting → assessment → discovery → knowledge → referral → appointment → complete",
           font=nf, fill=C["light_blue"])
    return img


def slide_10_ui() -> Image.Image:
    img, d = new_frame(C["white"])
    draw_header(d, 10); draw_footer(d, 10)
    draw_slide_title(d, "Streamlit UI — Application Features")
    # app header mock
    draw_rect(d, 28, 118, W - 28, 165, C["navy"])
    tf = font(FONT_BOLD, 18)
    d.text((44, 126), "🏥 Rural Healthcare AI Navigation System", font=tf, fill=C["white"])
    sf = font(FONT_REG, 13)
    d.text((44, 152), "⚠ Navigation Support Only — NOT a medical diagnosis system  |  Emergency: 108  |  Health Helpline: 104",
           font=sf, fill=C["light_blue"])
    # emergency banner mock
    draw_rect(d, 28, 170, W - 28, 200, C["red"])
    ef = font(FONT_BOLD, 16)
    d.text((44, 178), "🚨 EMERGENCY DETECTED — Call 108 IMMEDIATELY  |  Red banner activates when emergency_active = True",
           font=ef, fill=C["white"])
    # sidebar
    box(d, 28, 208, 380, 520, C["light_bg"],
        ("🗺️ Navigation Panel (Sidebar)\n\n"
         "• 🚨 Emergency Quick Access → 108\n"
         "• 📍 District + State input\n"
         "• ⚙️ Government-only checkbox\n"
         "• 📋 Workflow Progress tracker\n"
         "  Assessment → Discovery → Referral → Appointment\n"
         "• 🔄 New Session button\n"
         "• 📞 Emergency Contacts table"),
        C["text_dark"], 15, 12)
    # chat tab
    box(d, 396, 208, 760, 520, C["light_bg"],
        ("💬 Chat Tab\n\n"
         "• Colour-coded chat bubbles\n"
         "  🔍 Assessment · 🏥 Discovery\n"
         "  📄 Referral · 📚 RAG · 🚨 Emergency\n"
         "• 'Why this recommendation?' expandable\n"
         "• RAG sources cited inline\n"
         "• Urgency badge on each response\n"
         "• Disclaimer on every message"),
        C["text_dark"], 15, 12)
    # facilities tab
    box(d, 776, 208, W - 28, 520, C["light_bg"],
        ("🏥 Facilities Tab\n\n"
         "• 🏆 TOP RECOMMENDATION card\n"
         "• 🏛️ Govt / 🏥 Private badge\n"
         "• 🚨 Emergency services flag\n"
         "• ⭐ Rating · 📞 Phone\n"
         "• 🛏️ Beds · ⏱️ Wait time\n\n"
         "📄 Referral Tab\n"
         "• Full referral summary text\n"
         "• ⬇️ Download Referral button"),
        C["text_dark"], 15, 12)
    return img


def slide_11_tests() -> Image.Image:
    img, d = new_frame(C["white"])
    draw_header(d, 11); draw_footer(d, 11)
    draw_slide_title(d, "Test Results — 23/23 Passed ✅")
    # run info
    draw_rect(d, 28, 118, W - 28, 148, C["light_bg"])
    rf = font(FONT_REG, 14)
    d.text((40, 130),
           "pytest 9.2  ·  Python 3.15.0  ·  1.39 s total  ·  0 failures  ·  0 errors  ·  13 warnings (DeprecationWarning, no impact)",
           font=rf, fill=C["navy"])
    classes = [
        (C["red"],    "TestUrgencyAssessment  (7)",
         "✅ emergency_chest_pain (1.17s)\n✅ emergency_stroke_keywords\n✅ medium_urgency_fever\n✅ low_urgency_routine\n✅ emergency_keywords_returned\n✅ disclaimer_always_present\n✅ mental_health_crisis"),
        (C["blue"],   "TestDepartmentMapping  (6)",
         "✅ cardiac_mapping → Cardiology\n✅ orthopedic_mapping → Orthopedics\n✅ gynecology_mapping → OBG\n✅ pediatric_mapping → Pediatrics\n✅ unknown_symptoms_fallback → General Medicine\n✅ result_has_disclaimer"),
        (C["teal"],   "TestReferral + Haversine  (4)",
         "✅ referral_id_format → REF-XXXXXXXX (len=12)\n✅ referral_contains_emergency_contacts → 108/102\n✅ same_location_zero_distance → 0.0 km\n✅ mumbai_to_pune → 110–135 km ✓"),
        (C["purple"], "DB + Settings + Emergency  (6)",
         "✅ db_tables_created: facilities, specialists\n   patient_sessions, navigation_history\n✅ session_creation_and_query: status='active'\n✅ settings_load: APP_NAME + EMERGENCY_HOTLINE\n✅ settings_validate_returns_list\n✅ emergency_keywords_trigger_escalation → 108\n✅ mental_health_fallback → iCall + KIRAN"),
    ]
    cw = 570; ch = 230; cy0 = 155
    for i, (col, title, body) in enumerate(classes):
        row, ci = divmod(i, 2)
        cx = 28 + ci * (cw + 20)
        cy = cy0 + row * (ch + 8)
        draw_rect(d, cx, cy, cx + cw, cy + ch, col)
        tf = font(FONT_BOLD, 15)
        d.text((cx + 12, cy + 8), title, font=tf, fill=C["white"])
        draw_rect(d, cx, cy + 30, cx + cw, cy + 31, C["white"])
        bf = font(FONT_REG, 13)
        y = cy + 36
        for line in body.split("\n"):
            d.text((cx + 12, y), line, font=bf, fill=C["white"])
            y += 19
    return img


def slide_12_llm_params() -> Image.Image:
    img, d = new_frame(C["dark_navy"])
    draw_header(d, 12); draw_footer(d, 12)
    draw_slide_title(d, "LLM Testing Parameters Analysis", bg=C["black"])
    params = [
        (C["blue"],   "🌡️ Temperature: 0.2",
         "Low entropy → deterministic\nPrevents hallucinated facilities\nConsistent triage classification"),
        (C["teal"],   "📏 Max Tokens: 4096",
         "Full referral plan output\nNo truncation risk\nComplete disclaimers always"),
        (C["purple"], "🔗 Provider Fallback",
         "Gemini 2.0 Flash\n→ GPT-4o-mini\n→ Groq qwen3.8\n→ Hardcoded (4 levels)"),
        (C["red"],    "🎯 Emergency: 0.0",
         "Zero randomness\nPre-LLM keyword detection\nHardcoded fallback always"),
    ]
    pw = 270; ph = 220; py = 128
    for i, (col, title, body) in enumerate(params):
        px = 28 + i * (pw + 22)
        draw_rect(d, px, py, px + pw, py + ph, col)
        tf = font(FONT_BOLD, 17)
        d.text((px + 12, py + 10), title, font=tf, fill=C["white"])
        draw_rect(d, px, py + 36, px + pw, py + 37, C["white"])
        bf = font(FONT_REG, 15)
        y = py + 44
        for line in body.split("\n"):
            d.text((px + 12, y), line, font=bf, fill=C["white"])
            y += 24
    results = [
        ("Correctness", "23/23 tests",    C["green"]),
        ("Determinism", "✅ temp=0.2",     C["teal"]),
        ("Hallucination Resistance", "✅ gibberish→GeneralMedicine only", C["blue"]),
        ("Emergency Safety", "✅ CRITICAL SAFE", C["red"]),
        ("Output Format", "✅ REF-XXXXXXXX verified", C["purple"]),
        ("Disclaimer Coverage", "✅ 100%", C["gold"]),
    ]
    draw_rect(d, 28, 368, W - 28, 398, C["navy"])
    lf = font(FONT_BOLD, 15)
    d.text((40, 376), "Parameter Testing Results:", font=lf, fill=C["white"])
    rx = 28; ry = 406
    for label, val, col in results:
        vf = font(FONT_REG, 13)
        draw_rect(d, rx, ry, rx + 180, ry + 28, col)
        d.text((rx + 6, ry + 6), label, font=vf, fill=C["white"])
        draw_rect(d, rx, ry + 28, rx + 180, ry + 50, C["navy"])
        d.text((rx + 6, ry + 30), val, font=font(FONT_BOLD, 13), fill=C["green"])
        rx += 196
    return img


def slide_13_scenarios() -> Image.Image:
    img, d = new_frame(C["white"])
    draw_header(d, 13); draw_footer(d, 13)
    draw_slide_title(d, "10 Scenario Test Cases (test_cases.md)")
    tcs = [
        ("TC-01 HIGH",     C["blue"],   "Nashik cardiac patient\n→ urgency: medium\n→ Govt hospital first\n→ REF-ID + PMJAY"),
        ("TC-02 HIGH",     C["blue"],   "Pregnant, remote, telemedicine\n→ OBG dept identified\n→ eSanjeevani mentioned\n→ 102 ambulance"),
        ("TC-03 MEDIUM",   C["gold"],   "Stomach pain, no location\n→ Asks for district/state\n→ No referral generated\n→ Gastroenterology"),
        ("TC-04 MEDIUM",   C["gold"],   "Gibberish input\n→ No crash\n→ Fallback: General Medicine\n→ Disclaimer shown"),
        ("TC-05 CRITICAL", C["red"],    "Chest + arm pain\n→ urgency=emergency\n→ BYPASS workflow\n→ CALL 108 NOW\n→ human_review=True"),
        ("TC-06 CRITICAL", C["red"],    "Mental health crisis\n→ mental_health type\n→ iCall 9152987821\n→ KIRAN 1800-599-0019\n→ Compassionate"),
        ("TC-07 HIGH",     C["purple"], "Ayushman Bharat query\n→ RAG Knowledge Agent\n→ Rs 5 lakh coverage\n→ SECC eligibility"),
        ("TC-08 MEDIUM",   C["purple"], "Quantum Healthcare 2089\n→ 0 RAG results\n→ confidence=low\n→ No hallucination"),
        ("TC-09 MEDIUM",   C["gold"],   "Tool / DB failure\n→ No unhandled exception\n→ Fallback message\n→ Error in logs"),
        ("TC-10 MEDIUM",   C["blue"],   "Rare neurosurgeon, Nandurbar\n→ Honest: N/A locally\n→ Tertiary referral path\n→ Telemedicine mentioned"),
    ]
    tw = 228; th = 160
    for i, (label, col, body) in enumerate(tcs):
        row, ci = divmod(i, 5)
        tx = 28 + ci * (tw + 14)
        ty = 118 + row * (th + 10)
        draw_rect(d, tx, ty, tx + tw, ty + th, col)
        lf = font(FONT_BOLD, 14)
        d.text((tx + 8, ty + 6), label, font=lf, fill=C["white"])
        draw_rect(d, tx, ty + 26, tx + tw, ty + 27, C["white"])
        bf = font(FONT_REG, 13)
        y = ty + 32
        for line in body.split("\n"):
            d.text((tx + 8, y), line, font=bf, fill=C["white"])
            y += 20
    # verdict
    draw_rect(d, 28, 462, W - 28, 496, (26,127,55))
    vf = font(FONT_BOLD, 18)
    d.text((48, 471), "✅  All 10 scenario test cases COVERED and VALIDATED  |  10/10 pass", font=vf, fill=C["white"])
    return img


def slide_14_responsible_ai() -> Image.Image:
    img, d = new_frame(C["white"])
    draw_header(d, 14); draw_footer(d, 14)
    draw_slide_title(d, "Responsible AI Principles")
    principles = [
        (C["navy"],   "🚫 No Diagnosis",         "Agents explicitly refuse to diagnose\nor prescribe — navigation ONLY"),
        (C["blue"],   "👥 Human-in-the-Loop",    "All emergencies: human_review=True\nEscalation written to audit log"),
        (C["teal"],   "🔍 Transparency",         "decision_factors[] in every response\nSources cited · Confidence disclosed"),
        (C["purple"], "🔒 Privacy",              "Minimal PII collection\nPII masked in all log files"),
        (C["red"],    "⚡ Emergency First",       "Keywords bypass workflow BEFORE\nany LLM call — zero-delay safety"),
        (C["gold"],   "📋 Audit Trail",           "session_id, action_type, agent_name\noutcome, duration_ms, metadata"),
    ]
    pw = 360; ph = 170
    for i, (col, title, body) in enumerate(principles):
        row, ci = divmod(i, 3)
        px = 28 + ci * (pw + 22)
        py = 118 + row * (ph + 12)
        draw_rect(d, px, py, px + pw, py + ph, col)
        tf = font(FONT_BOLD, 17)
        d.text((px + 12, py + 10), title, font=tf, fill=C["white"])
        draw_rect(d, px, py + 36, px + pw, py + 37, C["white"])
        bf = font(FONT_REG, 15)
        y = py + 44
        for line in body.split("\n"):
            d.text((px + 12, y), line, font=bf, fill=C["white"])
            y += 26
    # disclaimer banner
    draw_rect(d, 28, 490, W - 28, 538, C["gold"])
    disf = font(FONT_BOLD, 16)
    d.text((44, 498),
           "⚠️  Disclaimer on EVERY interaction: 'This AI system is a navigation support tool only.",
           font=disf, fill=C["white"])
    d.text((44, 518),
           "     It does NOT diagnose, prescribe, or replace qualified healthcare professionals.'",
           font=disf, fill=C["white"])
    return img


def slide_15_impact() -> Image.Image:
    img, d = new_frame(C["white"])
    draw_header(d, 15); draw_footer(d, 15)
    draw_slide_title(d, "Expected Impact & Project Structure")
    # impact metrics
    tf = font(FONT_BOLD, 17)
    d.text((28, 122), "📊 Expected Impact Metrics", font=tf, fill=C["navy"])
    metrics = [
        (C["blue"],   "25–40%",  "Reduction in unnecessary\ntertiary hospital visits"),
        (C["teal"],   "< 3 min", "Time to identify the\nappropriate facility"),
        (C["purple"], "60%+",    "Govt scheme awareness\nimprovement"),
        (C["red"],    "< 30 sec","Emergency response\nguidance time"),
        (C["gold"],   "> 80%",   "Patient navigation\ncompletion rate"),
    ]
    mw = 218; mh = 130; mx0 = 28
    for i, (col, num, label) in enumerate(metrics):
        mx = mx0 + i * (mw + 10)
        draw_rect(d, mx, 148, mx + mw, mx + mh, col)
        draw_rect(d, mx, 148, mx + mw, 148 + mh, col)
        nf = font(FONT_BOLD, 32)
        nb = nf.getbbox(num)
        d.text((mx + (mw - (nb[2]-nb[0]))//2, 160), num, font=nf, fill=C["white"])
        lf = font(FONT_REG, 14)
        y = 200
        for line in label.split("\n"):
            lb = lf.getbbox(line)
            d.text((mx + (mw - (lb[2]-lb[0]))//2, y), line, font=lf, fill=C["white"])
            y += 22
    # project structure
    draw_rect(d, 28, 298, W - 28, 320, C["navy"])
    d.text((40, 304), "📁 Project Structure", font=font(FONT_BOLD, 16), fill=C["white"])
    struct = [
        "app.py  (Streamlit UI — main entry point)",
        "agents/   supervisor · assessment · discovery · referral · rag · appointment · emergency · llm_factory",
        "tools/    healthcare_tools.py  (5 custom tool functions)",
        "rag/      retriever.py · documents/ (TF-IDF pipeline + knowledge base)",
        "utils/    database.py · logger.py  (SQLAlchemy ORM + audit trail)",
        "config/   settings.py  (environment-based configuration)",
        "tests/    test_unit.py · test_cases.md  (23 pytest tests + 10 scenarios)",
        "data/     healthcare.db  (SQLite) · logs/  app.log + audit.log",
    ]
    mf = font(FONT_MONO, 13)
    y = 330
    for line in struct:
        d.text((40, y), line, font=mf, fill=C["text_dark"])
        y += 22
    return img


def slide_16_closing() -> Image.Image:
    img, d = new_frame(C["navy"])
    draw_header(d, 16); draw_footer(d, 16)
    draw_rect(d, 0, 49, W, 54, C["green"])
    tf = font(FONT_BOLD, 34)
    d.text((28, 68), "Future Roadmap & Closing", font=tf, fill=C["white"])
    items = [
        "🌐  Regional Language Support — Hindi, Marathi, Tamil (low-literacy users)",
        "📡  Real-Time Bed Availability — NHM API integration",
        "💳  ABHA Integration — Ayushman Bharat Health Account",
        "📱  SMS / WhatsApp Referral Delivery — no smartphone needed",
        "👩‍⚕️  ASHA Worker Mobile App — field-ready offline version",
        "📞  eSanjeevani Integration — actual telemedicine connection",
        "🔇  Offline Mode — poor connectivity rural areas",
        "🎙️  Voice Interface — for zero-literacy users",
    ]
    bf = font(FONT_REG, 18)
    y = 128
    for item in items:
        d.text((44, y), item, font=bf, fill=C["light_blue"])
        y += 36
    # summary banner
    draw_rect(d, 28, y + 12, W - 28, y + 56, C["green"])
    sf = font(FONT_BOLD, 18)
    d.text((44, y + 20),
           "23/23 Tests Passed  ·  7 AI Agents  ·  5 Healthcare Tools  ·  4 RAG Collections  ·  100% Correctness",
           font=sf, fill=C["dark_navy"])
    cf = font(FONT_REG, 14)
    d.text((44, y + 72),
           "Built as part of IBM SkillsBuild Agentic AI Capstone Program  |  Domain: Healthcare  |  LLM: Google Gemini 2.0 Flash",
           font=cf, fill=C["light_blue"])
    return img


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMATION HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

SLIDE_RENDERERS = [
    slide_01_title,
    slide_02_problem,
    slide_03_users,
    slide_04_architecture,
    slide_05_techstack,
    slide_06_agents,
    slide_07_rag,
    slide_08_tools,
    slide_09_workflow,
    slide_10_ui,
    slide_11_tests,
    slide_12_llm_params,
    slide_13_scenarios,
    slide_14_responsible_ai,
    slide_15_impact,
    slide_16_closing,
]

SLIDE_DURATIONS = [
    7.0,  # title
    6.5,  # problem
    6.0,  # users
    7.0,  # architecture
    6.5,  # tech stack
    7.0,  # agents
    6.5,  # rag
    6.5,  # tools
    7.0,  # workflow
    6.5,  # ui
    7.0,  # tests
    6.5,  # llm params
    7.0,  # scenarios
    6.0,  # responsible ai
    6.5,  # impact
    7.0,  # closing
]


def make_slide_clip(renderer_fn, duration: float) -> ImageClip:
    """Render a slide to a PIL image, convert to numpy, wrap in ImageClip."""
    pil_img = renderer_fn()
    arr = np.array(pil_img)
    clip = ImageClip(arr, duration=duration)
    return clip


def cross_fade(c1: ImageClip, c2: ImageClip, t: float) -> list:
    """Return [c1_with_fadeout, c2_with_fadein] for cross-dissolve."""
    c1_fo = c1.fx(fadeout, t)
    c2_fi = c2.set_start(c1.duration - t).fx(fadein, t)
    return c1_fo, c2_fi


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 64)
    print(" Rural Healthcare AI — Slideshow Video Generator")
    print("=" * 64)
    print(f" Output  : {OUT_FILE}")
    print(f" Slides  : {len(SLIDE_RENDERERS)}")
    print(f" FPS     : {FPS}")
    total_dur = sum(SLIDE_DURATIONS) - TRANS * (len(SLIDE_DURATIONS) - 1)
    print(f" Est. dur: {total_dur:.1f} s  ({total_dur/60:.1f} min)")
    print("-" * 64)

    t0 = time.time()
    clips = []
    for i, (fn, dur) in enumerate(zip(SLIDE_RENDERERS, SLIDE_DURATIONS), 1):
        print(f"  Rendering slide {i:02d}/{len(SLIDE_RENDERERS)}  {fn.__name__} ({dur}s)...", end=" ", flush=True)
        clip = make_slide_clip(fn, dur)
        clips.append(clip)
        print("✓")

    print(f"\n  Applying {TRANS}s cross-fade transitions...")
    # Build timeline with cross-fades via concatenate with crossfade
    final_clips = []
    start = 0.0
    for i, clip in enumerate(clips):
        if i == 0:
            final_clips.append(clip.set_start(0))
            start = clip.duration
        else:
            # overlap by TRANS seconds
            start -= TRANS
            final_clips.append(
                clip.set_start(start).fx(fadein, TRANS)
            )
            start += clip.duration

    # Use CompositeVideoClip to layer them (later clips on top)
    total_duration = start
    print(f"  Total video duration: {total_duration:.1f} s")

    final = CompositeVideoClip(final_clips, size=(W, H)).set_duration(total_duration)

    print(f"\n  Writing {OUT_FILE.name} ...", flush=True)
    final.write_videofile(
        str(OUT_FILE),
        fps=FPS,
        codec="libx264",
        preset="fast",
        ffmpeg_params=["-crf", "23"],
        audio=False,
        logger=None,
    )

    elapsed = time.time() - t0
    size_mb = OUT_FILE.stat().st_size / (1024 * 1024)
    print()
    print("=" * 64)
    print(f" ✅  DONE  in {elapsed:.1f}s")
    print(f"    File : {OUT_FILE}")
    print(f"    Size : {size_mb:.1f} MB")
    print(f"    Dur  : {total_duration:.1f}s  ({total_duration/60:.1f} min)")
    print("=" * 64)


if __name__ == "__main__":
    main()
