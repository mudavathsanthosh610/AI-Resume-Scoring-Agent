"""
View the output of the Resume Scoring Agent
Reads data from your Google Sheets and displays results
"""

import os
import json
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


def print_separator(char="=", width=75):
    print(char * width)


def main():
    # --- Connect to Google Sheets ---
    json_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
    master_id = os.getenv('MASTER_SHEET_ID')
    detail_id = os.getenv('DETAIL_SHEET_ID')

    print_separator()
    print("   AGENTIC AI - RESUME SCORING AGENT  |  PROJECT OUTPUT")
    print_separator()
    print()

    creds = Credentials.from_service_account_file(json_path, scopes=SCOPES)
    client = gspread.authorize(creds)

    # ─── MASTER SHEET (Job Postings) ──────────────────────────────────
    print("  [1] MASTER SHEET - Job Postings")
    print_separator("-")
    try:
        master_ss = client.open_by_key(master_id)
        master_ws = master_ss.worksheet('master')
        master_data = master_ws.get_all_records()

        if not master_data:
            print("  (No job postings found in master sheet)")
        else:
            # Print headers
            headers = list(master_data[0].keys())
            header_line = "  " + " | ".join(f"{h:<20}" for h in headers)
            print(header_line)
            print("  " + "-" * len(header_line))
            for row in master_data:
                row_line = "  " + " | ".join(f"{str(row.get(h, '')):<20}" for h in headers)
                print(row_line)
        print(f"\n  Total Job Postings: {len(master_data)}")
    except Exception as e:
        print(f"  Error reading master sheet: {e}")

    print()
    print_separator()
    print()

    # ─── DETAIL SHEET (Candidates) ────────────────────────────────────
    print("  [2] DETAIL SHEET - Candidate Results")
    print_separator("-")
    try:
        detail_ss = client.open_by_key(detail_id)
        detail_ws = detail_ss.worksheet('detail')
        detail_data = detail_ws.get_all_records()

        if not detail_data:
            print("  (No candidates found in detail sheet)")
        else:
            print(f"  Total Candidates: {len(detail_data)}")
            print()

            for i, row in enumerate(detail_data, 1):
                print(f"  CANDIDATE #{i}")
                print("  " + "-" * 50)

                # Display all fields
                for key, value in row.items():
                    if key == 'score_breakdown' and value:
                        # Parse and pretty-print score breakdown
                        print(f"    {key}:")
                        try:
                            breakdown = json.loads(str(value))
                            for bk, bv in breakdown.items():
                                print(f"      {bk:<20}: {bv}")
                        except (json.JSONDecodeError, TypeError):
                            print(f"      {value}")
                    elif key == 'resume_text' and value:
                        # Truncate long resume text
                        text = str(value)
                        preview = text[:150].replace('\n', ' ') + ('...' if len(text) > 150 else '')
                        print(f"    {key:<20}: {preview}")
                    else:
                        display_val = str(value) if value else "(empty)"
                        print(f"    {key:<20}: {display_val}")

                # Determine status
                try:
                    score = int(row.get('score_total', 0) or 0)
                    if score >= 70:
                        status = "STRONG CANDIDATE - Schedule Interview"
                    elif score >= 45:
                        status = "MODERATE CANDIDATE - Under Review"
                    else:
                        status = "BELOW THRESHOLD - Auto Follow-up"
                    print()
                    print(f"    >> STATUS: {status}")
                except (ValueError, TypeError):
                    pass

                print()
                print_separator("-")
                print()

            # ─── SUMMARY TABLE ────────────────────────────────────────
            print("  CANDIDATE SUMMARY")
            print_separator("-")
            print(f"  {'#':<4} {'Name':<25} {'Email':<30} {'Score':<10} {'Status'}")
            print("  " + "-" * 71)

            for i, row in enumerate(detail_data, 1):
                name = str(row.get('name', row.get('Name', 'N/A')))
                email = str(row.get('email', row.get('Email', 'N/A')))
                try:
                    score = int(row.get('score_total', 0) or 0)
                except (ValueError, TypeError):
                    score = 0

                if score >= 70:
                    status = "Interview"
                elif score >= 45:
                    status = "Review"
                else:
                    status = "Follow-up"

                print(f"  {i:<4} {name:<25} {email:<30} {score:<10} {status}")

            print_separator("-")

    except Exception as e:
        print(f"  Error reading detail sheet: {e}")

    print()
    print_separator()
    print()
    print("  Google Sheet Links:")
    print(f"  Master Sheet: https://docs.google.com/spreadsheets/d/{master_id}/edit")
    print(f"  Detail Sheet: https://docs.google.com/spreadsheets/d/{detail_id}/edit")
    print()
    print_separator()


if __name__ == "__main__":
    main()
