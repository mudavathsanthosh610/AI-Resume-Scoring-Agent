"""
FastAPI Web Application — Resume Scoring Agent
Candidates can upload resumes, get scored, and receive selection emails.
Run: python app.py
"""

import os
import io
import re
import json
import uuid
import base64
import tempfile
import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# Resume parsing
from pdfminer.high_level import extract_text as extract_pdf_text
from docx import Document

# Email
import smtplib
from email.message import EmailMessage

# Optional fuzzy matching
try:
    from rapidfuzz import fuzz
except Exception:
    fuzz = None

load_dotenv()

# ─── Configuration ────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger('resume-app')

GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
MASTER_SHEET_ID = os.getenv('MASTER_SHEET_ID')
DETAIL_SHEET_ID = os.getenv('DETAIL_SHEET_ID')
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
FROM_EMAIL = os.getenv('FROM_EMAIL', SMTP_USER)

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# ─── Google Sheets Client ────────────────────────────────────────────

def get_gspread_client():
    sa_json = GOOGLE_SERVICE_ACCOUNT_JSON
    # Check for base64-encoded service account JSON (for Railway CLI compatibility)
    sa_b64 = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON_B64')
    if sa_b64:
        sa_json = base64.b64decode(sa_b64).decode('utf-8')
    # If the env var is a file path, load from file; otherwise treat as raw JSON string
    if sa_json and os.path.isfile(sa_json):
        creds = Credentials.from_service_account_file(sa_json, scopes=SCOPES)
    elif sa_json:
        sa_info = json.loads(sa_json)
        creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    else:
        raise RuntimeError('GOOGLE_SERVICE_ACCOUNT_JSON is not set')
    return gspread.authorize(creds)


# ─── Resume Parsing ──────────────────────────────────────────────────

def extract_text_from_pdf_bytes(content: bytes) -> str:
    try:
        return extract_pdf_text(io.BytesIO(content))
    except Exception as e:
        logger.exception('PDF parse failed: %s', e)
        return ''


def extract_text_from_docx_bytes(content: bytes) -> str:
    try:
        tmp_path = os.path.join(tempfile.gettempdir(), f'resume_{uuid.uuid4().hex}.docx')
        with open(tmp_path, 'wb') as f:
            f.write(content)
        doc = Document(tmp_path)
        text = '\n'.join(p.text for p in doc.paragraphs)
        os.remove(tmp_path)
        return text
    except Exception as e:
        logger.exception('DOCX parse failed: %s', e)
        return ''


# ─── Education / Location / Experience Detection ─────────────────────

EDUCATION_PATTERNS = {
    'btech': r"\bB\.?\s?Tech\b|Bachelor\s+of\s+Technology|BTech\b",
    'bsc': r"\bB\.?\s?Sc\b|Bachelor\s+of\s+Science",
    'mtech': r"\bM\.?\s?Tech\b|Master\s+of\s+Technology",
    'msc': r"\bM\.?\s?Sc\b|Master\s+of\s+Science",
    'mba': r"\bMBA\b|Master\s+of\s+Business\s+Administration",
    'bca': r"\bBCA\b|Bachelor\s+of\s+Computer\s+Applications",
    'mca': r"\bMCA\b|Master\s+of\s+Computer\s+Applications",
    'be': r"\bB\.?\s?E\b|Bachelor\s+of\s+Engineering",
    'phd': r"\bPh\.?\s?D\b|Doctor\s+of\s+Philosophy",
}

LOCATION_KEYWORDS = [
    'Hyderabad', 'Bengaluru', 'Bangalore', 'Pune', 'Chennai',
    'Mumbai', 'Delhi', 'Noida', 'Gurgaon', 'Kolkata', 'Ahmedabad',
]


def detect_education(text: str) -> List[str]:
    found = []
    for key, pat in EDUCATION_PATTERNS.items():
        if re.search(pat, text, flags=re.I):
            found.append(key)
    return found


def detect_location(text: str) -> Optional[str]:
    for loc in LOCATION_KEYWORDS:
        if re.search(r'\b' + re.escape(loc) + r'\b', text, flags=re.I):
            return loc
    return None


def estimate_experience_months(text: str) -> int:
    years = re.findall(r"(\d+)\s+years?", text, flags=re.I)
    months = re.findall(r"(\d+)\s+months?", text, flags=re.I)
    total = 0
    if years:
        total += sum(int(y) * 12 for y in years)
    if months:
        total += sum(int(m) for m in months)
    return total


# ─── Scoring Engine ──────────────────────────────────────────────────

DEFAULT_SCORING = {
    'education': {
        'btech': 10, 'be': 10, 'bsc': 5, 'bca': 5,
        'mtech': 12, 'msc': 8, 'mca': 8, 'mba': 8, 'phd': 15
    },
    'top_tier_college': 15,
    'experience_in_months_threshold': {'months': 5, 'points': 15},
    'location': {'Hyderabad': 15, 'Bengaluru': 10, 'Bangalore': 10, 'Pune': 8, 'Chennai': 8, 'Mumbai': 8, 'Delhi': 5},
    'profile_tagline': 10,
    'resume_quality': 15,
}


def compute_skill_match_score(resume_text: str, required_skills_str: str) -> int:
    """Score based on how many required skills appear in the resume."""
    if not required_skills_str or not resume_text:
        return 0
    required = [s.strip().lower() for s in required_skills_str.split(',') if s.strip()]
    if not required:
        return 0

    resume_lower = resume_text.lower()
    matched = 0
    for skill in required:
        if fuzz and fuzz.partial_ratio(skill, resume_lower) > 75:
            matched += 1
        elif skill in resume_lower:
            matched += 1

    ratio = matched / len(required)
    return min(15, int(ratio * 15))


def score_candidate(candidate: Dict, job: Dict = None, scoring_config: Dict = None) -> Dict:
    if scoring_config is None:
        scoring_config = DEFAULT_SCORING
    score_breakdown = {}
    total = 0

    resume_text = candidate.get('resume_text', '') or ''

    # Education
    educ_found = detect_education(resume_text)
    educ_points = 0
    for e in educ_found:
        educ_points = max(educ_points, scoring_config.get('education', {}).get(e, 0))
    score_breakdown['education'] = educ_points
    total += educ_points

    # Top tier college
    top_tier = 0
    college_name = candidate.get('college', '') or ''
    top_tier_list = scoring_config.get('top_tier_list', ['IIT', 'NIT', 'BITS', 'IIIT'])
    for t in top_tier_list:
        if t.lower() in college_name.lower():
            top_tier = scoring_config.get('top_tier_college', 0)
            break
    score_breakdown['top_tier_college'] = top_tier
    total += top_tier

    # Experience
    exp_months = int(candidate.get('experience_months') or 0)
    exp_cfg = scoring_config.get('experience_in_months_threshold', {})
    job_min_exp = int(job.get('min_experience_months', 0)) if job else exp_cfg.get('months', 5)
    exp_points = exp_cfg.get('points', 0) if exp_months >= job_min_exp else 0
    score_breakdown['experience'] = exp_points
    total += exp_points

    # Location
    candidate_location = candidate.get('location') or detect_location(resume_text) or ''
    location_points = scoring_config.get('location', {}).get(candidate_location, 0)
    if job and candidate_location.lower() == (job.get('preferred_location', '') or '').lower():
        location_points = max(location_points, 15)
    score_breakdown['location'] = location_points
    total += location_points

    # Profile tagline (college name serves as tagline proxy)
    tagline_pts = scoring_config.get('profile_tagline', 0) if college_name else 0
    score_breakdown['tagline'] = tagline_pts
    total += tagline_pts

    # Resume quality: heuristic based on word count
    word_count = len(re.findall(r"\w+", resume_text))
    resume_pts = min(scoring_config.get('resume_quality', 0), int(word_count / 50))
    score_breakdown['resume_quality'] = resume_pts
    total += resume_pts

    # Skill match (bonus on top)
    if job:
        skill_pts = compute_skill_match_score(resume_text, job.get('required_skills', ''))
        score_breakdown['skill_match'] = skill_pts
        total += skill_pts

    total = min(total, 100)
    score_breakdown['total'] = total
    return score_breakdown


# ─── Skill Match Analysis ────────────────────────────────────────────

def analyze_skill_match(resume_text: str, required_skills_str: str) -> dict:
    """Analyze which skills matched and which are missing."""
    if not required_skills_str or not resume_text:
        return {'matched': [], 'missing': [], 'match_pct': 0}
    required = [s.strip() for s in required_skills_str.split(',') if s.strip()]
    if not required:
        return {'matched': [], 'missing': [], 'match_pct': 0}

    resume_lower = resume_text.lower()
    matched = []
    missing = []
    for skill in required:
        skill_lower = skill.lower()
        found = False
        if fuzz and fuzz.partial_ratio(skill_lower, resume_lower) > 75:
            found = True
        elif skill_lower in resume_lower:
            found = True
        if found:
            matched.append(skill)
        else:
            missing.append(skill)

    match_pct = int((len(matched) / len(required)) * 100) if required else 0
    return {'matched': matched, 'missing': missing, 'match_pct': match_pct}


# ─── Email Sending ───────────────────────────────────────────────────

def send_selection_email(
    to_email: str, candidate_name: str, job_title: str,
    score: int, status: str,
    score_breakdown: dict = None, job: dict = None,
    resume_text: str = '', education: list = None,
    location: str = '', experience_months: int = 0
) -> bool:
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning('SMTP credentials not set; skipping email')
        return False

    # Analyze skills
    required_skills_str = job.get('required_skills', '') if job else ''
    skill_analysis = analyze_skill_match(resume_text, required_skills_str)
    sb = score_breakdown or {}

    # Build score bar helper
    def score_bar(pts, max_pts):
        filled = int((pts / max_pts) * 10) if max_pts > 0 else 0
        return '█' * filled + '░' * (10 - filled)

    # Determine strength level
    if score >= 80:
        strength = '🟢 EXCELLENT MATCH'
    elif score >= 60:
        strength = '🟡 GOOD MATCH'
    elif score >= 40:
        strength = '🟠 AVERAGE MATCH'
    else:
        strength = '🔴 NEEDS IMPROVEMENT'

    # Build category-wise improvement tips
    improvements = []
    pref_loc = job.get('preferred_location', '') if job else ''
    min_exp = job.get('min_experience_months', 0) if job else 0

    edu_pts = sb.get('education', 0)
    if edu_pts >= 12:
        edu_tip = '✅ Strong — Your education qualifications are well recognized.'
    elif edu_pts >= 5:
        edu_tip = '🔶 Moderate — Consider adding higher education (M.Tech, MBA, Ph.D) to boost this score.'
    else:
        edu_tip = '🔴 Weak — Clearly mention your degree (B.Tech, B.Sc, MCA, etc.) with full form. Add certifications if no formal degree.'
    improvements.append(('🎓 Education', edu_pts, 15, edu_tip))

    college_pts = sb.get('top_tier_college', 0)
    if college_pts > 0:
        college_tip = '✅ Strong — Your institution is recognized as top-tier (IIT/NIT/BITS/IIIT).'
    else:
        college_tip = '🔶 Tip — If your college has notable rankings or affiliations, mention them. Add NAAC/NIRF ratings.'
    improvements.append(('🏛️ College Tier', college_pts, 15, college_tip))

    exp_pts = sb.get('experience', 0)
    if exp_pts > 0:
        exp_tip = f'✅ Strong — You meet the minimum experience requirement of {min_exp} months.'
    else:
        exp_tip = f'🔴 Weak — This role requires {min_exp}+ months experience. Add internships, freelance work, or project durations with clear timelines (e.g., "6 months", "1 year").'
    improvements.append(('💼 Experience', exp_pts, 15, exp_tip))

    loc_pts = sb.get('location', 0)
    if loc_pts >= 10:
        loc_tip = f'✅ Strong — Your location matches the job preference ({pref_loc}).'
    elif loc_pts > 0:
        loc_tip = f'🔶 Moderate — Your location is recognized. For a higher score, mention willingness to relocate to {pref_loc}.'
    else:
        loc_tip = f'🔴 Weak — This job prefers candidates from {pref_loc}. Add "Willing to relocate to {pref_loc}" in your resume.'
    improvements.append(('📍 Location', loc_pts, 15, loc_tip))

    skill_pts = sb.get('skill_match', 0)
    if skill_analysis['match_pct'] >= 80:
        skill_tip = '✅ Strong — Your skills closely match the job requirements.'
    elif skill_analysis['match_pct'] >= 50:
        skill_tip = f"🔶 Moderate — Add these missing skills: {', '.join(skill_analysis['missing'])}"
    else:
        skill_tip = f"🔴 Weak — Missing key skills: {', '.join(skill_analysis['missing'])}. Add relevant projects, courses, or certifications."
    improvements.append(('🎯 Skill Match', skill_pts, 15, skill_tip))

    qual_pts = sb.get('resume_quality', 0)
    if qual_pts >= 10:
        qual_tip = '✅ Strong — Your resume is detailed and well-structured.'
    elif qual_pts >= 5:
        qual_tip = '🔶 Moderate — Add more content: projects, achievements, certifications, technical skills section.'
    else:
        qual_tip = '🔴 Weak — Your resume is too short. Add: detailed project descriptions, work achievements, technical skills, certifications, and awards.'
    improvements.append(('📄 Resume Quality', qual_pts, 15, qual_tip))

    tag_pts = sb.get('tagline', 0)
    if tag_pts > 0:
        tag_tip = '✅ Strong — Your profile headline is present.'
    else:
        tag_tip = '🔴 Weak — Add a professional headline at the top (e.g., "Full Stack Developer | Python & React | 2+ Years Experience").'
    improvements.append(('🏷️ Profile Headline', tag_pts, 10, tag_tip))

    improvements_text = ''
    for cat_name, cat_pts, cat_max, cat_tip in improvements:
        improvements_text += f'''
    {cat_name}  ({cat_pts}/{cat_max})  {score_bar(cat_pts, cat_max)}
    → {cat_tip}
'''

    # Build quick action items (weakest areas first)
    weak_areas = [(name, pts, mx) for name, pts, mx, _ in improvements if pts < mx * 0.5]
    weak_areas.sort(key=lambda x: x[1] / x[2] if x[2] > 0 else 0)
    if not weak_areas:
        actions_text = '    ✅ Your resume is strong! Keep applying to matching roles.'
    else:
        action_lines = []
        for i, (area_name, area_pts, area_max) in enumerate(weak_areas[:5], 1):
            action_lines.append(f'    {i}. Improve {area_name} (currently {area_pts}/{area_max})')
        actions_text = '\n'.join(action_lines)

    subject = f"📊 ATS Resume Score: {score}/100 for {job_title} — {candidate_name}"
    body = f"""Dear {candidate_name},

Thank you for applying for the {job_title} position. Here is your detailed ATS Resume Analysis Report.


╔══════════════════════════════════════════════════════════════╗
║              ATS RESUME ANALYSIS REPORT                     ║
╠══════════════════════════════════════════════════════════════╣
║  Candidate  : {candidate_name:<45}║
║  Job Role   : {job_title:<45}║
║  Job Location : {(pref_loc or 'N/A'):<43}║
║  Applied On : {datetime.now().strftime('%B %d, %Y at %I:%M %p'):<45}║
╚══════════════════════════════════════════════════════════════╝


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📊  YOUR ATS SCORE:  {score} / 100     {strength}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📋  SCORE BREAKDOWN:

    Category              Score     Bar
    ─────────────────────────────────────────
    🎓 Education          {sb.get('education', 0):>3}/15    {score_bar(sb.get('education', 0), 15)}
    🏛️ College Tier       {sb.get('top_tier_college', 0):>3}/15    {score_bar(sb.get('top_tier_college', 0), 15)}
    💼 Experience         {sb.get('experience', 0):>3}/15    {score_bar(sb.get('experience', 0), 15)}
    📍 Location           {sb.get('location', 0):>3}/15    {score_bar(sb.get('location', 0), 15)}
    🎯 Skill Match        {sb.get('skill_match', 0):>3}/15    {score_bar(sb.get('skill_match', 0), 15)}
    📄 Resume Quality     {sb.get('resume_quality', 0):>3}/15    {score_bar(sb.get('resume_quality', 0), 15)}
    🏷️ Profile Headline   {sb.get('tagline', 0):>3}/10    {score_bar(sb.get('tagline', 0), 10)}
    ─────────────────────────────────────────
    ⭐ TOTAL              {score:>3}/100   {score_bar(score, 100)}


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  🎯  SKILL MATCH:  {skill_analysis['match_pct']}% Match

    ✅ Skills Found in Resume ({len(skill_analysis['matched'])}):
       {', '.join(skill_analysis['matched']) if skill_analysis['matched'] else '(none detected)'}

    ❌ Skills Missing from Resume ({len(skill_analysis['missing'])}):
       {', '.join(skill_analysis['missing']) if skill_analysis['missing'] else '(none — perfect match! 🎉)'}


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📌  WHAT WE DETECTED FROM YOUR RESUME:

    • Education     : {', '.join(education).upper() if education else 'Not detected — add your degree!'}
    • Location      : {location or 'Not detected — add your city!'}
    • Experience    : {experience_months} months{' ✅' if exp_pts > 0 else f' (need {min_exp}+ months)'}
    • College       : {'Top-tier ✅' if college_pts > 0 else 'Not in top-tier list'}


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  🔧  WHERE TO IMPROVE YOUR RESUME:
  (Category-wise feedback to increase your ATS score)
{improvements_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📝  QUICK ACTION ITEMS (fix these first):

{actions_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This is an automated ATS analysis. Improve the areas marked
above and re-apply to boost your score!

Best regards,
HR Recruitment Team
AI Resume Scoring Agent — Powered by Agentic AI
"""

    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email
        msg.set_content(body)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
        logger.info('Sent ATS report email to %s (score: %d)', to_email, score)
        return True
    except Exception as e:
        logger.exception('Failed to send email: %s', e)
        return False


# ─── FastAPI App ─────────────────────────────────────────────────────

app = FastAPI(title="AI Resume Scoring Agent", version="1.0")


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    return {"status": "ok"}


@app.get("/api/debug")
async def debug_env():
    """Debug endpoint to check environment variable status."""
    return JSONResponse(content={
        "GOOGLE_SERVICE_ACCOUNT_JSON": "SET" if GOOGLE_SERVICE_ACCOUNT_JSON else "NOT SET",
        "GOOGLE_SA_LENGTH": len(GOOGLE_SERVICE_ACCOUNT_JSON) if GOOGLE_SERVICE_ACCOUNT_JSON else 0,
        "GOOGLE_SA_IS_FILE": os.path.isfile(GOOGLE_SERVICE_ACCOUNT_JSON) if GOOGLE_SERVICE_ACCOUNT_JSON else False,
        "GOOGLE_SA_STARTS_WITH": (GOOGLE_SERVICE_ACCOUNT_JSON[:20] + '...') if GOOGLE_SERVICE_ACCOUNT_JSON and len(GOOGLE_SERVICE_ACCOUNT_JSON) > 20 else GOOGLE_SERVICE_ACCOUNT_JSON,
        "MASTER_SHEET_ID": "SET" if MASTER_SHEET_ID else "NOT SET",
        "DETAIL_SHEET_ID": "SET" if DETAIL_SHEET_ID else "NOT SET",
        "SMTP_USER": "SET" if SMTP_USER else "NOT SET",
        "SMTP_PASSWORD": "SET" if SMTP_PASSWORD else "NOT SET",
    })


@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve the main web page."""
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        return HTMLResponse(content=f.read())


@app.get("/api/jobs")
async def get_jobs():
    """Fetch job postings from Master Google Sheet."""
    if not GOOGLE_SERVICE_ACCOUNT_JSON and not os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON_B64'):
        raise HTTPException(status_code=500, detail="GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_JSON_B64 environment variable is not set.")
    if not MASTER_SHEET_ID:
        raise HTTPException(status_code=500, detail="MASTER_SHEET_ID environment variable is not set. Add it in Railway Variables tab.")
    try:
        client = get_gspread_client()
        master_ss = client.open_by_key(MASTER_SHEET_ID)
        master_ws = master_ss.worksheet('master')
        jobs = master_ws.get_all_records()
        return JSONResponse(content={"jobs": jobs})
    except json.JSONDecodeError as e:
        logger.exception('Invalid JSON in GOOGLE_SERVICE_ACCOUNT_JSON: %s', e)
        raise HTTPException(status_code=500, detail=f"GOOGLE_SERVICE_ACCOUNT_JSON contains invalid JSON: {str(e)}")
    except Exception as e:
        logger.exception('Failed to fetch jobs: %s', e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload")
async def upload_resume(
    job_id: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    college: str = Form(""),
    resume: UploadFile = File(...)
):
    """Process uploaded resume: parse, score, save to sheet, send email."""
    try:
        # 1. Read the uploaded file
        content = await resume.read()
        filename = resume.filename.lower()

        if filename.endswith('.pdf'):
            resume_text = extract_text_from_pdf_bytes(content)
        elif filename.endswith('.docx'):
            resume_text = extract_text_from_docx_bytes(content)
        else:
            raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

        if not resume_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from resume. Please try another file.")

        # 2. Get job details from master sheet
        client = get_gspread_client()
        master_ss = client.open_by_key(MASTER_SHEET_ID)
        master_ws = master_ss.worksheet('master')
        jobs = master_ws.get_all_records()

        job = None
        for j in jobs:
            if str(j.get('job_id', '')) == job_id:
                job = j
                break

        if not job:
            raise HTTPException(status_code=404, detail=f"Job ID {job_id} not found")

        # 3. Detect candidate info from resume
        location = detect_location(resume_text)
        experience_months = estimate_experience_months(resume_text)
        education = detect_education(resume_text)

        # 4. Score the candidate
        candidate = {
            'resume_text': resume_text,
            'college': college,
            'location': location,
            'experience_months': experience_months,
            'education_text': resume_text,
        }
        score_result = score_candidate(candidate, job=job)
        score_total = score_result['total']

        # 5. Determine selection status
        min_score = int(job.get('min_score_to_select', 50))
        status = 'SELECTED' if score_total >= min_score else 'NOT SELECTED'

        # 6. Save to detail sheet
        candidate_id = f"C{uuid.uuid4().hex[:6].upper()}"
        detail_ss = client.open_by_key(DETAIL_SHEET_ID)
        detail_ws = detail_ss.worksheet('detail')

        row_data = [
            candidate_id,
            job_id,
            name,
            email,
            phone,
            college,
            location or '',
            ', '.join(education),
            str(experience_months),
            resume_text[:500],  # Truncate for sheet
            str(score_total),
            json.dumps(score_result),
            status,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ]
        detail_ws.append_row(row_data)
        logger.info('Saved candidate %s (%s) - Score: %d - Status: %s', name, email, score_total, status)

        # 7. Send email
        email_sent = send_selection_email(
            email, name, job.get('job_title', ''), score_total, status,
            score_breakdown=score_result, job=job,
            resume_text=resume_text, education=education,
            location=location or '', experience_months=experience_months
        )

        # 8. Return result
        return JSONResponse(content={
            "name": name,
            "email": email,
            "job_title": job.get('job_title', ''),
            "score_total": score_total,
            "score_breakdown": score_result,
            "status": status,
            "email_sent": email_sent,
            "message": f"Email {'sent' if email_sent else 'failed'} to {email}",
            "education_detected": education,
            "location_detected": location,
            "experience_months": experience_months,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception('Error processing resume: %s', e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Run ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print("=" * 60)
    print("  AI Resume Scoring Agent - Web Application")
    print(f"  Open in browser: http://localhost:{port}")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=port)
