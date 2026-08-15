#!/usr/bin/env python3
"""Fetch LinkedIn profile data via the Member Data Portability API and write JSON Resume."""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime

API_BASE = "https://api.linkedin.com"
SNAPSHOT_PATH = "/rest/memberSnapshotData"
LINKEDIN_VERSION = "202312"

DEFAULT_DOMAINS = [
    "PROFILE",
    "POSITIONS",
    "EDUCATION",
    "SKILLS",
    "CERTIFICATIONS",
    "HONORS",
    "LANGUAGES",
    "PROJECTS",
    "RECOMMENDATIONS",
    "VOLUNTEERING_EXPERIENCES",
]

# Full documented Member Snapshot domain list (case-sensitive).
ALL_DOMAINS = [
    "ADS_CLICKED", "MEMBER_FOLLOWING", "LOGIN", "RICH_MEDIA", "SEARCHES",
    "INFERENCE_TAKEOUT", "ALL_COMMENTS", "CONTACTS", "EVENTS", "RECEIPTS",
    "AD_TARGETING", "REGISTRATION", "REVIEWS", "ARTICLES", "PATENTS",
    "GROUPS", "COMPANY_FOLLOWS", "INVITATIONS", "PHONE_NUMBERS", "CONNECTIONS",
    "EMAIL_ADDRESSES", "JOB_POSTINGS", "JOB_APPLICATIONS", "JOB_SEEKER_PREFERENCES",
    "LEARNING", "INBOX", "SAVED_JOBS", "SAVED_JOB_ALERTS", "PROFILE", "SKILLS",
    "POSITIONS", "EDUCATION", "TEST_SCORES", "CAUSES_YOU_CARE_ABOUT", "PUBLICATIONS",
    "PROJECTS", "ORGANIZATIONS", "LANGUAGES", "HONORS", "COURSES", "CERTIFICATIONS",
    "RECOMMENDATIONS", "ENDORSEMENTS", "MEMBER_SHARE_INFO", "SECURITY_CHALLENGE_PIPE",
    "TRUSTED_GRAPH", "MARKETPLACE_ENGAGEMENTS", "MARKETPLACE_PROVIDERS",
    "MARKETPLACE_OPPORTUNITIES", "ACTOR_SAVE_ITEM", "JOB_APPLICANT_SAVED_ANSWERS",
    "TALENT_QUESTION_SAVED_RESPONSE", "PROFILE_SUMMARY", "ALL_LIKES", "ALL_VOTES",
    "RECEIPTS_LBP", "EASYAPPLY_BLOCKING", "LEARNING_COACH_AI_TAKEOUT",
    "LEARNING_COACH_INBOX", "LEARNING_ROLEPLAY_INBOX", "VOLUNTEERING_EXPERIENCES",
    "ACCOUNT_HISTORY", "INSTANT_REPOSTS", "IDENTITY_CREDENTIALS_AND_ASSETS", "ADS_LAN",
]

DATE_FORMATS = ["%Y-%m-%d", "%b %Y", "%B %Y", "%m/%Y", "%Y-%m", "%Y"]


class LinkedInAPIError(RuntimeError):
    def __init__(self, status, body):
        super().__init__(f"LinkedIn API error {status}: {body}")
        self.status = status
        self.body = body


def build_snapshot_url(domain=None, start=None):
    params = ["q=criteria"]
    if domain:
        params.append(f"domain={domain}")
    if start is not None:
        params.append(f"start={start}")
    return f"{API_BASE}{SNAPSHOT_PATH}?{'&'.join(params)}"


def api_request(url, token):
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Linkedin-Version": LINKEDIN_VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        if "no data found" in body.lower():
            return None
        raise LinkedInAPIError(error.code, body) from None


def fetch_domain(token, domain):
    records = []
    start = None
    seen_starts = set()
    while start not in seen_starts:
        seen_starts.add(start)
        payload = api_request(build_snapshot_url(domain=domain, start=start), token)
        if payload is None:
            break
        for element in payload.get("elements", []):
            records.extend(element.get("snapshotData", []))
        next_href = next(
            (link.get("href") for link in payload.get("paging", {}).get("links", [])
             if link.get("rel") == "next"),
            None,
        )
        if not next_href:
            break
        match = re.search(r"[?&]start=(\d+)", next_href)
        if not match:
            break
        start = int(match.group(1))
    return records


def get_field(record, *candidates):
    lowered = {str(key).strip().lower(): value for key, value in record.items()}
    for candidate in candidates:
        value = lowered.get(candidate.lower())
        if value not in (None, ""):
            return value
    return None


def normalize_date(value):
    if not value:
        return None
    value = str(value).strip()
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        if fmt == "%Y":
            return f"{parsed.year:04d}"
        if fmt in ("%b %Y", "%B %Y", "%m/%Y", "%Y-%m"):
            return f"{parsed.year:04d}-{parsed.month:02d}"
        return parsed.strftime("%Y-%m-%d")
    return value


def map_profile(records):
    basics = {}
    if not records:
        return basics
    record = records[0]
    name = " ".join(
        part for part in (get_field(record, "First Name"), get_field(record, "Last Name")) if part
    )
    if name:
        basics["name"] = name
    headline = get_field(record, "Headline")
    if headline:
        basics["label"] = headline
    summary = get_field(record, "Summary")
    if summary:
        basics["summary"] = summary
    region = get_field(record, "Geo Location", "Location")
    if region:
        basics["location"] = {"region": region}
    websites = get_field(record, "Websites")
    if websites:
        profiles = []
        for entry in re.split(r"[;,]", str(websites)):
            entry = entry.strip()
            if not entry:
                continue
            url_match = re.search(r"https?://\S+", entry)
            profiles.append({"network": "Website", "url": url_match.group(0) if url_match else entry})
        if profiles:
            basics["profiles"] = profiles
    return basics


def map_email(records):
    for record in records or []:
        email = get_field(record, "Email Address", "Email")
        if email:
            return email
    return None


def map_phone(records):
    for record in records or []:
        phone = get_field(record, "Number", "Phone Number")
        if phone:
            return phone
    return None


def map_positions(records):
    work = []
    for record in records:
        entry = {}
        if name := get_field(record, "Company Name", "Company"):
            entry["name"] = name
        if position := get_field(record, "Title", "Position"):
            entry["position"] = position
        if summary := get_field(record, "Description"):
            entry["summary"] = summary
        if start := normalize_date(get_field(record, "Started On", "Start Date")):
            entry["startDate"] = start
        if end := normalize_date(get_field(record, "Finished On", "End Date")):
            entry["endDate"] = end
        if entry:
            work.append(entry)
    return work


def map_education(records):
    education = []
    for record in records:
        entry = {}
        if institution := get_field(record, "School Name", "School"):
            entry["institution"] = institution
        if area := get_field(record, "Field Of Study", "Notes"):
            entry["area"] = area
        if study_type := get_field(record, "Degree Name", "Degree"):
            entry["studyType"] = study_type
        if start := normalize_date(get_field(record, "Start Date", "Started On")):
            entry["startDate"] = start
        if end := normalize_date(get_field(record, "End Date", "Finished On")):
            entry["endDate"] = end
        if entry:
            education.append(entry)
    return education


def map_skills(records):
    skills = []
    for record in records:
        if name := get_field(record, "Name", "Skill Name"):
            skills.append({"name": name})
    return skills


def map_certifications(records):
    certificates = []
    for record in records:
        entry = {}
        if name := get_field(record, "Name"):
            entry["name"] = name
        if date_value := normalize_date(get_field(record, "Started On", "Issued On")):
            entry["date"] = date_value
        if issuer := get_field(record, "Authority", "Issuer"):
            entry["issuer"] = issuer
        if url := get_field(record, "Url"):
            entry["url"] = url
        if entry:
            certificates.append(entry)
    return certificates


def map_honors(records):
    awards = []
    for record in records:
        entry = {}
        if title := get_field(record, "Title"):
            entry["title"] = title
        if date_value := normalize_date(get_field(record, "Issued On")):
            entry["date"] = date_value
        if awarder := get_field(record, "Issuer"):
            entry["awarder"] = awarder
        if summary := get_field(record, "Description"):
            entry["summary"] = summary
        if entry:
            awards.append(entry)
    return awards


def map_languages(records):
    languages = []
    for record in records:
        entry = {}
        if language := get_field(record, "Name"):
            entry["language"] = language
        if fluency := get_field(record, "Proficiency"):
            entry["fluency"] = fluency
        if entry:
            languages.append(entry)
    return languages


def map_projects(records):
    projects = []
    for record in records:
        entry = {}
        if name := get_field(record, "Title"):
            entry["name"] = name
        if description := get_field(record, "Description"):
            entry["description"] = description
        if url := get_field(record, "Url"):
            entry["url"] = url
        if start := normalize_date(get_field(record, "Started On")):
            entry["startDate"] = start
        if end := normalize_date(get_field(record, "Finished On")):
            entry["endDate"] = end
        if entry:
            projects.append(entry)
    return projects


def map_recommendations(records):
    references = []
    for record in records:
        if not get_field(record, "Status"):
            continue
        text = get_field(record, "Text", "Recommendation")
        if not text:
            continue
        entry = {"reference": text}
        name = " ".join(
            part for part in (get_field(record, "First Name"), get_field(record, "Last Name")) if part
        )
        job_title = get_field(record, "Job Title")
        if name and job_title:
            entry["name"] = f"{name} - {job_title}"
        elif name:
            entry["name"] = name
        references.append(entry)
    return references


def map_volunteering(records):
    volunteer = []
    for record in records:
        entry = {}
        if organization := get_field(record, "Company Name", "Organization Name"):
            entry["organization"] = organization
        if position := get_field(record, "Role", "Title"):
            entry["position"] = position
        if summary := get_field(record, "Description"):
            entry["summary"] = summary
        if start := normalize_date(get_field(record, "Start Date", "Started On")):
            entry["startDate"] = start
        if end := normalize_date(get_field(record, "End Date", "Finished On")):
            entry["endDate"] = end
        if entry:
            volunteer.append(entry)
    return volunteer


# Maps a snapshot domain to its JSON Resume section key and mapper function.
# PROFILE/EMAIL_ADDRESSES/PHONE_NUMBERS feed into "basics" and are handled separately.
SECTION_MAPPERS = {
    "POSITIONS": ("work", map_positions),
    "EDUCATION": ("education", map_education),
    "SKILLS": ("skills", map_skills),
    "CERTIFICATIONS": ("certificates", map_certifications),
    "HONORS": ("awards", map_honors),
    "LANGUAGES": ("languages", map_languages),
    "PROJECTS": ("projects", map_projects),
    "RECOMMENDATIONS": ("references", map_recommendations),
    "VOLUNTEERING_EXPERIENCES": ("volunteer", map_volunteering),
}


def build_json_resume(records_by_domain):
    resume = {"$schema": "https://jsonresume.org/schema"}

    basics = map_profile(records_by_domain.get("PROFILE", []))
    if email := map_email(records_by_domain.get("EMAIL_ADDRESSES")):
        basics["email"] = email
    if phone := map_phone(records_by_domain.get("PHONE_NUMBERS")):
        basics["phone"] = phone
    if basics:
        resume["basics"] = basics

    for domain, (section, mapper) in SECTION_MAPPERS.items():
        records = records_by_domain.get(domain)
        if not records:
            continue
        section_data = mapper(records)
        if section_data:
            resume[section] = section_data

    resume["meta"] = {
        "generator": "linkedin-jsonresume-export",
        "generatedAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return resume


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export a LinkedIn member's profile data to a JSON Resume file via "
        "LinkedIn's Member Data Portability API."
    )
    parser.add_argument(
        "--domain", action="append", dest="domains", metavar="DOMAIN",
        help="Snapshot domain to fetch (repeatable). Defaults to a CV-relevant set.",
    )
    parser.add_argument(
        "--all-domains", action="store_true",
        help="Fetch every documented snapshot domain instead of the default set.",
    )
    parser.add_argument(
        "--output", default="linkedin_resume.json",
        help="Where to write the JSON Resume document (default: %(default)s).",
    )
    parser.add_argument(
        "--save-raw", metavar="PATH",
        help="Also write the untrimmed raw snapshot records to this path.",
    )
    parser.add_argument(
        "--from-raw", metavar="PATH",
        help="Skip the API call and build the JSON Resume file from a previously saved --save-raw dump.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.from_raw:
        with open(args.from_raw, "r", encoding="utf-8") as handle:
            records_by_domain = json.load(handle)
    else:
        token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
        if not token:
            print("Error: LINKEDIN_ACCESS_TOKEN is not set.", file=sys.stderr)
            print(
                "Export a LinkedIn OAuth access token with the r_dma_portability_3rd_party "
                "or r_dma_portability_member scope before running this script.",
                file=sys.stderr,
            )
            return 1

        domains = ALL_DOMAINS if args.all_domains else (args.domains or DEFAULT_DOMAINS)

        records_by_domain = {}
        for domain in domains:
            print(f"Fetching {domain}...", file=sys.stderr)
            try:
                records_by_domain[domain] = fetch_domain(token, domain)
            except LinkedInAPIError as error:
                print(f"Error fetching {domain}: {error}", file=sys.stderr)
                if error.status in (401, 403):
                    print(
                        "Check that the token is valid, has the right scope, and the "
                        "member has consented to data sharing.",
                        file=sys.stderr,
                    )
                return 1

        if args.save_raw:
            with open(args.save_raw, "w", encoding="utf-8") as handle:
                json.dump(records_by_domain, handle, indent=2, ensure_ascii=False)
            print(f"Saved raw snapshot data to {args.save_raw}", file=sys.stderr)

    resume = build_json_resume(records_by_domain)

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(resume, handle, indent=2, ensure_ascii=False)

    print(f"Wrote JSON Resume to {args.output}")
    for section in (
        "basics", "work", "education", "skills", "certificates",
        "awards", "languages", "projects", "volunteer", "references",
    ):
        value = resume.get(section)
        if value is None:
            continue
        print(f"  {section}: {1 if section == 'basics' else len(value)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
