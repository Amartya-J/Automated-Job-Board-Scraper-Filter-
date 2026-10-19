from __future__ import annotations

import argparse
import os
import smtplib
from dataclasses import dataclass, asdict
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests import RequestException

DEFAULT_TIMEOUT = 20


@dataclass
class JobPosting:
    title: str
    company: str
    link: str
    source: str


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def fetch_soup(url: str, timeout: int = DEFAULT_TIMEOUT) -> BeautifulSoup:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def _parse_hn_header(header_text: str) -> tuple[str, str]:
    parts = [part.strip() for part in header_text.replace("—", "|").split("|") if part.strip()]
    if len(parts) >= 2:
        return parts[1], parts[0]
    if len(parts) == 1:
        return "Role not specified", parts[0]
    return "Role not specified", "Unknown"


def extract_hn_jobs(soup: BeautifulSoup, source_url: str) -> list[JobPosting]:
    jobs: list[JobPosting] = []
    for comment in soup.select("tr.comtr"):
        text_block = comment.select_one("span.commtext")
        if text_block is None:
            continue

        lines = [line.strip() for line in text_block.get_text("\n", strip=True).splitlines() if line.strip()]
        if not lines:
            continue

        title, company = _parse_hn_header(lines[0])
        first_link = text_block.find("a", href=True)
        link = urljoin(source_url, first_link["href"]) if first_link else source_url
        jobs.append(JobPosting(title=title, company=company, link=link, source=source_url))
    return jobs


def extract_generic_jobs(
    soup: BeautifulSoup,
    source_url: str,
    item_selector: str,
    title_selector: str,
    company_selector: str,
    link_selector: str,
) -> list[JobPosting]:
    jobs: list[JobPosting] = []
    for item in soup.select(item_selector):
        title_node = item.select_one(title_selector)
        if title_node is None:
            continue

        title = title_node.get_text(" ", strip=True)
        if not title:
            continue

        company_node = item.select_one(company_selector)
        company = company_node.get_text(" ", strip=True) if company_node else "Unknown"

        link_node = item.select_one(link_selector)
        href = link_node.get("href", "") if link_node else ""
        link = urljoin(source_url, href) if href else source_url

        jobs.append(JobPosting(title=title, company=company, link=link, source=source_url))
    return jobs


def extract_jobs(
    soup: BeautifulSoup,
    source_url: str,
    item_selector: str,
    title_selector: str,
    company_selector: str,
    link_selector: str,
) -> list[JobPosting]:
    if "news.ycombinator.com/item" in source_url:
        return extract_hn_jobs(soup, source_url)
    return extract_generic_jobs(
        soup,
        source_url,
        item_selector=item_selector,
        title_selector=title_selector,
        company_selector=company_selector,
        link_selector=link_selector,
    )


def filter_jobs(
    jobs: Iterable[JobPosting],
    include_keywords: list[str] | None = None,
    exclude_keywords: list[str] | None = None,
) -> list[JobPosting]:
    include = [kw.lower() for kw in (include_keywords or [])]
    exclude = [kw.lower() for kw in (exclude_keywords or [])]

    filtered: list[JobPosting] = []
    for job in jobs:
        haystack = f"{job.title} {job.company}".lower()

        if include and not any(keyword in haystack for keyword in include):
            continue
        if exclude and any(keyword in haystack for keyword in exclude):
            continue
        filtered.append(job)

    return filtered


def write_excel(jobs: list[JobPosting], output_file: Path) -> Path:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(job) for job in jobs]
    df = pd.DataFrame(data, columns=["title", "company", "link", "source"])
    df.rename(columns={"title": "Title", "company": "Company", "link": "Link", "source": "Source"}, inplace=True)
    df.to_excel(output_file, index=False)
    return output_file


def send_email_with_attachment(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    email_to: str,
    attachment: Path,
    subject: str = "Automated job report",
) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = email_to
    msg.set_content("Please find attached the latest filtered job report.")

    with attachment.open("rb") as file_handle:
        msg.add_attachment(
            file_handle.read(),
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=attachment.name,
        )

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)


def run() -> None:
    parser = argparse.ArgumentParser(description="Scrape job boards, filter listings, export to Excel, and email report.")
    parser.add_argument(
        "--urls",
        default=os.getenv("JOB_BOARD_URLS", "https://news.ycombinator.com/item?id=42309075"),
        help="Comma-separated job board URLs",
    )
    parser.add_argument("--include-keywords", default=os.getenv("INCLUDE_KEYWORDS", ""))
    parser.add_argument("--exclude-keywords", default=os.getenv("EXCLUDE_KEYWORDS", ""))
    parser.add_argument("--output", default=os.getenv("OUTPUT_FILE", "job_report.xlsx"))
    parser.add_argument("--item-selector", default=os.getenv("JOB_ITEM_SELECTOR", "article,li,.job,.job-card,tr"))
    parser.add_argument("--title-selector", default=os.getenv("JOB_TITLE_SELECTOR", "h1,h2,h3,a"))
    parser.add_argument("--company-selector", default=os.getenv("JOB_COMPANY_SELECTOR", ".company,.company-name,.employer,.byline"))
    parser.add_argument("--link-selector", default=os.getenv("JOB_LINK_SELECTOR", "a[href]"))
    parser.add_argument("--smtp-host", default=os.getenv("SMTP_HOST", ""))
    parser.add_argument("--smtp-port", type=int, default=int(os.getenv("SMTP_PORT", "587")))
    parser.add_argument("--smtp-user", default=os.getenv("SMTP_USER", ""))
    parser.add_argument("--smtp-password", default=os.getenv("SMTP_PASS", ""))
    parser.add_argument("--email-to", default=os.getenv("EMAIL_TO", ""))
    parser.add_argument("--skip-email", action="store_true")

    args = parser.parse_args()

    urls = _split_csv(args.urls)
    include_keywords = _split_csv(args.include_keywords)
    exclude_keywords = _split_csv(args.exclude_keywords)

    all_jobs: list[JobPosting] = []
    for url in urls:
        try:
            soup = fetch_soup(url)
            all_jobs.extend(
                extract_jobs(
                    soup,
                    url,
                    item_selector=args.item_selector,
                    title_selector=args.title_selector,
                    company_selector=args.company_selector,
                    link_selector=args.link_selector,
                )
            )
        except RequestException as exc:
            print(f"Skipping {url}: {exc}")

    filtered_jobs = filter_jobs(all_jobs, include_keywords=include_keywords, exclude_keywords=exclude_keywords)
    output = write_excel(filtered_jobs, Path(args.output))

    should_send_email = not args.skip_email and all([args.smtp_host, args.smtp_user, args.smtp_password, args.email_to])
    if should_send_email:
        send_email_with_attachment(
            smtp_host=args.smtp_host,
            smtp_port=args.smtp_port,
            smtp_user=args.smtp_user,
            smtp_password=args.smtp_password,
            email_to=args.email_to,
            attachment=output,
        )
        print(f"Report emailed to {args.email_to} with {len(filtered_jobs)} filtered jobs.")
    else:
        print(f"Generated {output} with {len(filtered_jobs)} filtered jobs. Email skipped.")


if __name__ == "__main__":
    run()
