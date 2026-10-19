# Automated-Job-Board-Scraper-Filter-

A Python automation script that:
- Scrapes one or more public job board/forum pages
- Extracts job title, company, and application link
- Filters out unwanted keywords
- Exports a clean Excel report
- Emails the report via SMTP

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` values into your environment (or export variables directly).

## Run

```bash
python main.py --skip-email
```

Run with email enabled by setting `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, and `EMAIL_TO`.

Useful options:

```bash
python main.py \
  --urls "https://news.ycombinator.com/item?id=42309075,https://news.ycombinator.com/item?id=42168719" \
  --exclude-keywords "internship,unpaid" \
  --include-keywords "python,backend,remote" \
  --output job_report.xlsx
```

## Test

```bash
python -m unittest discover -s tests -p 'test_*.py'
```
