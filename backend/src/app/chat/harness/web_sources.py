"""Read public reference pages when search engines do not index a requested source."""
import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urlsplit
import requests


class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.hidden += 1
    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self.hidden = max(0, self.hidden - 1)
    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def read_reference_pages(urls, domains):
    sources = []
    for url in urls:
        parsed = urlsplit(url)
        # Restrict to explicit public documentation hosts. Extend deliberately
        # after reviewing a new source, rather than accepting arbitrary URLs.
        allowed = ('docs.python.org', 'www.cs.cornell.edu', 'cs.cornell.edu', 'ocw.mit.edu')
        if parsed.scheme != 'https' or parsed.hostname not in allowed or parsed.port not in (None, 443) or parsed.username or parsed.password:
            raise ValueError('reference_host_not_supported')
        if domains and not any(parsed.hostname == d or parsed.hostname.endswith('.' + d) for d in domains):
            raise ValueError('reference_domain_mismatch')
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError('reference_address_not_public')
        with requests.get(url, timeout=(5, 15), allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                raise ValueError('reference_fetch_failed')
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('reference_content_type_unsupported')
            data = bytearray()
            for chunk in response.iter_content(16384):
                data.extend(chunk)
                if len(data) > 1000000:
                    raise ValueError('reference_page_too_large')
        parser = PageText()
        parser.feed(bytes(data).decode('utf-8', errors='replace'))
        body = '\n'.join(parser.parts)[:18000]
        if len(body) < 100:
            raise ValueError('reference_page_empty')
        sources.append({'url': url, 'title': parsed.hostname + parsed.path,
                        'excerpt': body, 'retrieval_mode': 'direct_reference_page'})
    return sources
