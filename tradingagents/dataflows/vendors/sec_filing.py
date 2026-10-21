"""Complete financial filings, including company-specific lines and notes."""

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import requests

from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.errors import NoMarketDataError, VendorUnavailableError
from tradingagents.dataflows.files import replace_file


class _FilingText(HTMLParser):
    def __init__(self, url=""):
        super().__init__()
        self.parts, self.skipped = [], []
        self.url = url

    def handle_starttag(self, tag, attrs):
        if self.skipped or tag in {"script", "style", "head", "ix:header", "ix:hidden"}:
            if tag not in {"br", "hr", "meta", "link", "img", "input"}:
                self.skipped.append(tag)
        elif tag in {"p", "div", "tr", "br"} or tag in {"h1", "h2", "h3", "h4"}:
            self.parts.append("\n")
        elif tag in {"td", "th"}:
            self.parts.append(" | ")
        elif tag == "a":
            href = dict(attrs).get("href") or ""
            if href and not href.startswith("#"):
                self.parts.append(f" [{urljoin(self.url, href)}] ")

    def handle_startendtag(self, tag, attrs):
        if not self.skipped:
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if self.skipped and tag == self.skipped[-1]:
            self.skipped.pop()
        elif not self.skipped and tag in {"p", "div", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skipped:
            self.parts.append(data)


def financial_filing(ticker, cik, freq, as_of_date, cached_json, user_agent):
    submissions = cached_json(f"https://data.sec.gov/submissions/CIK{cik}.json", f"submissions-{cik}.json")
    histories = [submissions["filings"]["recent"]]
    for page in submissions["filings"].get("files", []):
        if page["filingFrom"] <= as_of_date:
            histories.append(cached_json(f"https://data.sec.gov/submissions/{page['name']}", page["name"]))
    forms = {"10-K", "20-F", "40-F"} | ({"10-Q"} if freq.lower() == "quarterly" else set())
    eligible = []
    for history in histories:
        for row in zip(*(history[key] for key in ("filingDate", "form", "accessionNumber", "primaryDocument", "reportDate")), strict=True):
            filed, form, accession, document, period = row
            if filed <= as_of_date and period <= as_of_date and form.removesuffix("/A") in forms and document:
                eligible.append(row)
    if not eligible:
        raise NoMarketDataError(ticker, ticker, f"no {freq} financial filing by {as_of_date}")
    latest = max(eligible, key=lambda row: (row[4], row[0], row[2]))
    # Keep the original and amendments for this reporting period, in filing order.
    selected = sorted(row for row in eligible if row[4] == latest[4])
    reports = []
    for filed, form, accession, document, period in selected:
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{document}"
        path = Path(get_config()["data_cache_dir"]) / "sec_edgar" / f"{accession}-{Path(document).name}.links.txt"
        if path.exists():
            text = path.read_text(encoding="utf-8")
        else:
            try:
                response = requests.get(url, headers={"User-Agent": user_agent}, timeout=30)
                response.raise_for_status()
            except requests.RequestException as exc:
                raise VendorUnavailableError("SEC financial filing could not be retrieved") from exc
            parser = _FilingText(url)
            parser.feed(response.content.decode("utf-8"))
            text = "\n".join(" ".join(line.split()) for line in "".join(parser.parts).splitlines() if line.strip())
            if not text:
                raise VendorUnavailableError("SEC financial filing contained no readable text")
            path.parent.mkdir(parents=True, exist_ok=True)
            replace_file(path, lambda temp, content=text: Path(temp).write_text(content, encoding="utf-8"))
        reports.append(f"# {ticker.upper()} complete {form} filing: period {period}, filed {filed}\nSource: {url}\n"
                       f"All statements, notes and management discussion follow; units and periods are stated in the filing.\n\n{text}")
    return "\n\n".join(reports)
