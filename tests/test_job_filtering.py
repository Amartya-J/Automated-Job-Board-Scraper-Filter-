import unittest

from bs4 import BeautifulSoup

from main import JobPosting, extract_hn_jobs, filter_jobs


class TestJobFiltering(unittest.TestCase):
    def test_filter_jobs_exclude_keywords(self):
        jobs = [
            JobPosting(title="Backend Engineer", company="Acme", link="https://example.com/1", source="https://jobs.example.com"),
            JobPosting(title="Software Internship", company="Beta", link="https://example.com/2", source="https://jobs.example.com"),
        ]

        filtered = filter_jobs(jobs, exclude_keywords=["internship"])

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].title, "Backend Engineer")

    def test_extract_hn_jobs_parses_company_title_and_link(self):
        html = """
        <table>
            <tr class=\"comtr\">
                <td>
                    <span class=\"commtext\">
                        Acme Corp | Senior Python Engineer | Remote
                        <a href=\"https://acme.example/jobs/1\">Apply</a>
                    </span>
                </td>
            </tr>
        </table>
        """
        soup = BeautifulSoup(html, "html.parser")

        jobs = extract_hn_jobs(soup, "https://news.ycombinator.com/item?id=1")

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].company, "Acme Corp")
        self.assertEqual(jobs[0].title, "Senior Python Engineer")
        self.assertEqual(jobs[0].link, "https://acme.example/jobs/1")


if __name__ == "__main__":
    unittest.main()
