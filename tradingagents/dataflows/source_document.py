"""Read primary-source context without silently shortening its text."""

import ipaddress
import socket
from io import BytesIO
from datetime import datetime
from urllib.parse import urljoin, urlsplit

import requests

from tradingagents.dataflows.date_window import is_historical
from tradingagents.dataflows.errors import VendorUnavailableError
from tradingagents.dataflows.vendors.sec_edgar import _user_agent
from tradingagents.dataflows.vendors.sec_filing import _FilingText


def source_excerpt(document: str, start_line: int = 1, line_count: int | None = None, query: str = "") -> str:
    """Select explicit, numbered source lines; the caller retains the full document."""
    if type(start_line) is not int or start_line < 1 or (line_count is not None and (type(line_count) is not int or line_count < 1)):
        raise ValueError("Source line numbers and counts must be positive integers.")
    if not query and start_line == 1 and line_count is None:
        return document
    if line_count is None:
        raise ValueError("Specify line_count for a bounded source read.")
    lines = document.splitlines()
    start = start_line - 1
    if query:
        found = next((index for index in range(start, len(lines)) if query.casefold() in lines[index].casefold()), None)
        if found is None:
            return f"SOURCE_NO_MATCH: {query!r} was not found from line {start_line}. Total lines: {len(lines)}. No passage was returned."
        start = found
    if start >= len(lines):
        raise ValueError(f"Source has {len(lines)} lines; choose a line within that range.")
    end = min(len(lines), start + line_count)
    source = next((line for line in lines if line.startswith("Source: ")), "Source URL not recorded")
    return (f"{source}\nVerbatim source excerpt: lines {start + 1}-{end} of {len(lines)}; "
            f"next start_line: {end + 1 if end < len(lines) else 'end'}. This is an excerpt, not the complete document.\n\n"
            + "\n".join(f"{index + 1}: {lines[index]}" for index in range(start, end)))


def read_source_document(url: str, as_of_date: str) -> str:
    if is_historical(as_of_date):
        raise VendorUnavailableError("Live source pages have no verified historical vintage; use the dated SEC filing tools")
    for _ in range(6):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
            raise ValueError("Source URL must be public HTTPS without credentials")
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
            raise ValueError("Source URL must resolve only to public addresses")
        with requests.Session() as session:
            session.trust_env = False  # public source reads must not use the user's netrc credentials
            response = session.get(url, timeout=30, allow_redirects=False, headers={"User-Agent": _user_agent()})
        if response.is_redirect:
            url = urljoin(url, response.headers["Location"])
            continue
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        if "html" in content_type:
            parser = _FilingText(url)
            parser.feed(response.text)
            text = "\n".join(" ".join(line.split()) for line in "".join(parser.parts).splitlines() if line.strip())
        elif "application/pdf" in content_type:
            from pypdf import PdfReader

            try:
                reader = PdfReader(BytesIO(response.content))
                pages = [page.extract_text(extraction_mode='layout') or '' for page in reader.pages]
                if not any(page.strip() for page in pages):
                    raise VendorUnavailableError("PDF contains no extractable text; OCR was not performed")
                text = "\n\n".join(
                    f"Page {number}\n{page}"
                    for number, page in enumerate(pages, 1)
                )
            except VendorUnavailableError:
                raise
            except Exception as exc:
                raise VendorUnavailableError(f"PDF text extraction failed ({type(exc).__name__})") from exc
            text = "PDF text extraction; table alignment may be imperfect. Verify units and headings.\n" + text
        elif "text/" in content_type or "json" in content_type:
            text = response.text
        else:
            raise VendorUnavailableError("Source format is not readable text; document was not analyzed")
        if not text.strip():
            raise VendorUnavailableError("Source page contained no readable text")
        return f"Source: {url}\nRetrieved: {datetime.now().astimezone().isoformat()}\nUntrusted source text; publication date must be established from the document.\n\n{text}"
    raise VendorUnavailableError("Source redirected too many times; document was not retrieved")
