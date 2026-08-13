"""
One-time setup script to configure Google Sheets with proper headers and sample job data.
Run this once: python setup_sheets.py
"""

import os
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

load_dotenv()

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


def main():
    json_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
    master_id = os.getenv('MASTER_SHEET_ID')
    detail_id = os.getenv('DETAIL_SHEET_ID')

    creds = Credentials.from_service_account_file(json_path, scopes=SCOPES)
    client = gspread.authorize(creds)

    # ─── MASTER SHEET SETUP ───────────────────────────────────────────
    print("Setting up Master Sheet (Job Postings)...")
    master_ss = client.open_by_key(master_id)

    # Try to get or create 'master' worksheet
    try:
        master_ws = master_ss.worksheet('master')
    except gspread.exceptions.WorksheetNotFound:
        master_ws = master_ss.add_worksheet(title='master', rows=100, cols=20)

    master_ws.clear()

    master_headers = [
        'job_id', 'job_title', 'description', 'required_skills',
        'preferred_location', 'min_experience_months', 'min_score_to_select'
    ]

    sample_jobs = [
        [
            'JOB001',
            'AI / ML Engineer',
            'Looking for AI/ML engineers to build intelligent systems using Python, TensorFlow, and cloud platforms.',
            'Python, Machine Learning, TensorFlow, Deep Learning, NLP',
            'Hyderabad',
            '6',
            '50'
        ],
        [
            'JOB002',
            'Full Stack Developer',
            'Seeking full stack developers proficient in React, Node.js, and database management.',
            'Python, React, Django, JavaScript, SQL, REST APIs',
            'Bengaluru',
            '3',
            '45'
        ],
        [
            'JOB003',
            'Data Analyst',
            'Data analyst role requiring strong Excel, SQL, and visualization skills.',
            'Python, SQL, Excel, Power BI, Pandas, Data Visualization',
            'Pune',
            '0',
            '40'
        ],
        [
            'JOB004',
            'DevOps Engineer',
            'Join our infrastructure team to automate CI/CD pipelines, manage cloud deployments, and ensure 99.9% uptime.',
            'Docker, Kubernetes, Jenkins, AWS, Terraform, Linux, Git',
            'Bengaluru',
            '12',
            '55'
        ],
        [
            'JOB005',
            'Cybersecurity Analyst',
            'Protect our digital assets by monitoring threats, conducting vulnerability assessments, and building security frameworks.',
            'Network Security, SIEM, Penetration Testing, Firewalls, Python, ISO 27001',
            'Delhi',
            '6',
            '50'
        ],
        [
            'JOB006',
            'Mobile App Developer',
            'Build cross-platform mobile applications with modern frameworks for millions of users.',
            'React Native, Flutter, Dart, JavaScript, Firebase, REST APIs, Git',
            'Mumbai',
            '3',
            '45'
        ],
        [
            'JOB007',
            'Cloud Solutions Architect',
            'Design and implement scalable cloud architectures on AWS/Azure for enterprise clients.',
            'AWS, Azure, Cloud Architecture, Microservices, Serverless, Docker, Terraform',
            'Hyderabad',
            '24',
            '60'
        ],
        [
            'JOB008',
            'UI/UX Designer',
            'Craft beautiful and intuitive user experiences for web and mobile products using modern design tools.',
            'Figma, Adobe XD, User Research, Wireframing, Prototyping, HTML, CSS',
            'Pune',
            '3',
            '40'
        ],
        [
            'JOB009',
            'Backend Engineer (Java)',
            'Build high-performance backend services and APIs using Java and Spring Boot for fintech applications.',
            'Java, Spring Boot, Microservices, PostgreSQL, Redis, Kafka, REST APIs',
            'Chennai',
            '12',
            '50'
        ],
        [
            'JOB010',
            'QA Automation Engineer',
            'Develop and maintain automated test suites to ensure product quality across web and mobile platforms.',
            'Selenium, Cypress, Python, Java, Jenkins, API Testing, Jira',
            'Hyderabad',
            '6',
            '45'
        ],
    ]

    master_ws.update('A1', [master_headers] + sample_jobs)

    # Format header row bold
    master_ws.format('A1:G1', {'textFormat': {'bold': True}, 'backgroundColor': {'red': 0.2, 'green': 0.2, 'blue': 0.3}})

    print(f"  Added {len(sample_jobs)} job postings to Master Sheet")

    # ─── DETAIL SHEET SETUP ───────────────────────────────────────────
    print("Setting up Detail Sheet (Candidates)...")
    detail_ss = client.open_by_key(detail_id)

    try:
        detail_ws = detail_ss.worksheet('detail')
    except gspread.exceptions.WorksheetNotFound:
        detail_ws = detail_ss.add_worksheet(title='detail', rows=500, cols=20)

    detail_ws.clear()

    detail_headers = [
        'candidate_id', 'job_id', 'name', 'email', 'phone',
        'college', 'location', 'education', 'experience_months',
        'resume_text', 'score_total', 'score_breakdown',
        'status', 'applied_at'
    ]

    detail_ws.update('A1', [detail_headers])

    # Format header row
    detail_ws.format('A1:N1', {'textFormat': {'bold': True}, 'backgroundColor': {'red': 0.2, 'green': 0.2, 'blue': 0.3}})

    print("  Detail Sheet headers set up")

    print()
    print("=" * 60)
    print("  Setup complete!")
    print(f"  Master Sheet: https://docs.google.com/spreadsheets/d/{master_id}/edit")
    print(f"  Detail Sheet: https://docs.google.com/spreadsheets/d/{detail_id}/edit")
    print("=" * 60)


if __name__ == "__main__":
    main()
