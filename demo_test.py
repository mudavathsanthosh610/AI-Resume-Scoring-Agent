"""
Demo script to showcase the Resume Scoring Agent features
Runs locally without needing Google Sheets / SMTP credentials
"""

from resume_parser_agent import (
    detect_education,
    detect_location,
    estimate_experience_months,
    score_candidate,
    DEFAULT_SCORING,
)

# ─── Sample Resume Texts ───────────────────────────────────────────────
SAMPLE_RESUMES = [
    {
        "name": "Rahul Sharma",
        "email": "rahul.sharma@gmail.com",
        "college": "IIT Hyderabad",
        "tagline": "Full Stack Developer | Python & React",
        "resume_text": (
            "Rahul Sharma\n"
            "B.Tech in Computer Science, IIT Hyderabad (2023)\n"
            "Location: Hyderabad, Telangana\n\n"
            "Experience:\n"
            "- Software Engineer Intern at TCS for 8 months\n"
            "- Built REST APIs using Django and Flask\n"
            "- Developed React dashboards for analytics\n\n"
            "Skills: Python, JavaScript, React, Django, SQL, Docker, Git\n"
            "Certifications: AWS Cloud Practitioner\n"
        ),
    },
    {
        "name": "Priya Patel",
        "email": "priya.patel@outlook.com",
        "college": "BITS Pilani",
        "tagline": "Data Scientist | ML Engineer",
        "resume_text": (
            "Priya Patel\n"
            "M.Tech in Data Science, BITS Pilani (2024)\n"
            "Location: Bengaluru, Karnataka\n\n"
            "Experience:\n"
            "- Data Science Intern at Infosys for 6 months\n"
            "- Research Assistant for 1 year at university lab\n"
            "- Published 2 papers on NLP and Computer Vision\n\n"
            "Skills: Python, TensorFlow, PyTorch, SQL, Pandas, Scikit-learn, NLP\n"
            "Certifications: Google Professional ML Engineer\n"
        ),
    },
    {
        "name": "Amit Kumar",
        "email": "amit.kumar@yahoo.com",
        "college": "Osmania University",
        "tagline": "",
        "resume_text": (
            "Amit Kumar\n"
            "B.Sc Computer Science, Osmania University (2025)\n"
            "Location: Hyderabad\n\n"
            "Experience:\n"
            "- Intern at local startup for 3 months\n\n"
            "Skills: Java, HTML, CSS\n"
        ),
    },
    {
        "name": "Sneha Reddy",
        "email": "sneha.reddy@gmail.com",
        "college": "NIT Warangal",
        "tagline": "Backend Developer | Java & Spring Boot",
        "resume_text": (
            "Sneha Reddy\n"
            "B.Tech in Information Technology, NIT Warangal (2023)\n"
            "MBA from IIM Lucknow (2025)\n"
            "Location: Pune, Maharashtra\n\n"
            "Experience:\n"
            "- Software Developer at Wipro for 2 years\n"
            "- Team Lead for backend services migration\n"
            "- Led a team of 5 developers in microservices architecture\n\n"
            "Skills: Java, Spring Boot, Kubernetes, AWS, MongoDB, PostgreSQL, CI/CD\n"
            "Achievements: Promoted to Senior Developer within 1 year\n"
        ),
    },
]


def print_separator(char="=", width=70):
    print(char * width)


def main():
    print_separator()
    print("   AGENTIC AI - RESUME SCORING AGENT  |  DEMO OUTPUT")
    print_separator()
    print()

    for i, candidate_data in enumerate(SAMPLE_RESUMES, 1):
        resume_text = candidate_data["resume_text"]

        # --- Step 1: Extract information ---
        education = detect_education(resume_text)
        location = detect_location(resume_text)
        experience = estimate_experience_months(resume_text)

        # --- Step 2: Build candidate dict for scoring ---
        candidate = {
            "education_text": resume_text,
            "location": location,
            "experience_months": experience,
            "tagline": candidate_data.get("tagline", ""),
            "resume_text": resume_text,
            "college": candidate_data.get("college", ""),
        }

        # --- Step 3: Score ---
        score_result = score_candidate(candidate, scoring_config=DEFAULT_SCORING)

        # --- Step 4: Display ---
        print(f"  CANDIDATE #{i}: {candidate_data['name']}")
        print_separator("-")
        print(f"  Email       : {candidate_data['email']}")
        print(f"  College     : {candidate_data['college']}")
        print(f"  Tagline     : {candidate_data.get('tagline') or '(none)'}")
        print(f"  Education   : {', '.join(education) if education else '(none detected)'}")
        print(f"  Location    : {location or '(not detected)'}")
        print(f"  Experience  : {experience} months")
        print()

        print("  SCORE BREAKDOWN:")
        print(f"    Education        : {score_result['education']:>3} pts")
        print(f"    Top-Tier College : {score_result['top_tier_college']:>3} pts")
        print(f"    Experience       : {score_result['experience']:>3} pts")
        print(f"    Location         : {score_result['location']:>3} pts")
        print(f"    Tagline          : {score_result['tagline']:>3} pts")
        print(f"    Resume Quality   : {score_result['resume_quality']:>3} pts")
        print("                       " + "-" * 7)
        print(f"    TOTAL SCORE      : {score_result['total']:>3} / 100")
        print()

        # Classification
        total = score_result["total"]
        if total >= 70:
            status = "STRONG CANDIDATE - Schedule Interview"
        elif total >= 45:
            status = "MODERATE CANDIDATE - Under Review"
        else:
            status = "BELOW THRESHOLD - Auto Follow-up"
        print(f"  >> STATUS: {status}")
        print()
        print_separator()
        print()

    # --- Summary Table ---
    print("  SUMMARY TABLE")
    print_separator("-")
    print(f"  {'Name':<20} {'Score':>6}  {'Education':<15} {'Location':<12} {'Status'}")
    print_separator("-")
    for candidate_data in SAMPLE_RESUMES:
        resume_text = candidate_data["resume_text"]
        education = detect_education(resume_text)
        location = detect_location(resume_text)
        experience = estimate_experience_months(resume_text)
        candidate = {
            "education_text": resume_text,
            "location": location,
            "experience_months": experience,
            "tagline": candidate_data.get("tagline", ""),
            "resume_text": resume_text,
            "college": candidate_data.get("college", ""),
        }
        score_result = score_candidate(candidate, scoring_config=DEFAULT_SCORING)
        total = score_result["total"]
        if total >= 70:
            status = "Interview"
        elif total >= 45:
            status = "Review"
        else:
            status = "Follow-up"

        print(
            f"  {candidate_data['name']:<20} {total:>4}/100"
            f"  {', '.join(education):<15} {(location or 'N/A'):<12} {status}"
        )
    print_separator("-")
    print()
    print("  Demo completed successfully! All features working.")
    print_separator()


if __name__ == "__main__":
    main()
