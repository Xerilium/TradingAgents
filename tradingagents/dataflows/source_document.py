"""Read primary-source context without silently shortening its text."""

import ipaddress
import socket
from datetime import datetime
from urllib.parse import urljoin, urlsplit

import requests

from tradingagents.dataflows.date_window import is_historical
from tradingagents.dataflows.errors import VendorUnavailableError
from tradingagents.dataflows.vendors.sec_edgar import _user_agent
from tradingagents.dataflows.vendors.sec_filing import _FilingText


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
        elif "text/" in content_type or "json" in content_type:
            text = response.text
        else:
            raise VendorUnavailableError("Source format is not readable text; document was not analyzed")
        if not text.strip():
            raise VendorUnavailableError("Source page contained no readable text")
        return f"Source: {url}\nRetrieved: {datetime.now().astimezone().isoformat()}\nUntrusted source text; publication date must be established from the document.\n\n{text}"
    raise VendorUnavailableError("Source redirected too many times; document was not retrieved")
