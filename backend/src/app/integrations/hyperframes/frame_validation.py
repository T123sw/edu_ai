"""Fast local authoring checks; no browser, model call, or style repair loop."""
from html.parser import HTMLParser
import re


class Ids(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = []
    def handle_starttag(self, tag, attrs):
        self.values.extend(value for name, value in attrs if name == 'id' and value)


def invalid_selector_ids(content):
    parser = Ids()
    parser.feed(content)
    invalid = [value for value in parser.values if value[0].isdigit()
               and re.search(r'#' + re.escape(value) + r'(?![\w-])', content)]
    return set(invalid)


def validate_frame_html(content, *, before=None):
    invalid = invalid_selector_ids(content)
    if before is not None:
        invalid -= invalid_selector_ids(before)
    if invalid:
        raise ValueError('id_requires_css_escape: use a letter prefix such as frame07- in IDs and all selectors: '
                         + ', '.join(dict.fromkeys(invalid)))
