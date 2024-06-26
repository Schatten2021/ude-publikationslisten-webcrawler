import logging
import pickle
import re
from abc import abstractmethod
from typing import Union
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup, ResultSet

_website_capture_regex: re.Pattern = re.compile(r"(https?://)?[A-Za-z0-9.\-_@+\[\]{}]*\.[a-zA-Z]{2,4}.*")
_ude_url_capture_regex: re.Pattern = re.compile(r"(https?://)?([A-Za-z0-9.\-_@+\[\]{}]*\.)?uni-due.de(/.*)?")
_filtered_urls_regex: re.Pattern = re.compile(r"(mailto:.*)|(javascript:.*)|(ftp:.*)|(tel:.*)")
_ude_host_regex: re.Pattern = re.compile(r"(.*\.)uni-due.de")

logger = logging.getLogger("webcrawler")

_captured_sites: dict[str, "Site"] = {}


def build_url(base: str, url: str) -> str | None:
    split_url = urlsplit(urljoin(base, url))
    if not _ude_host_regex.fullmatch(split_url.netloc) or split_url.scheme not in ["http", "https"]:
        return None
    final_url = "https://" + split_url.netloc + split_url.path
    # logger.debug(f"parsed url for {final_url}")
    return final_url


class Crawler:
    _remaining_sites: list["Site"]

    def __init__(self, start: str):
        self.start = start
        self.entry = Site(start)
        _captured_sites[self.entry.url] = self.entry
        self._remaining_sites = [self.entry]

    def __next__(self):
        if len(self._remaining_sites) == 0:
            raise StopIteration
        current: Site = self._remaining_sites.pop()
        current.capture()
        if not isinstance(current, Website):
            return current
        self._remaining_sites.extend(filter(lambda x: x.captured, current.linked_sites.values()))
        return current

    def __iter__(self):
        return self

    def save(self, file: str):
        with open(file, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(file: str):
        with open(file, "rb") as f:
            return pickle.load(f)


class Site:
    def __init__(self, url: str):
        self.request = None
        self.url = url
        self.captured = False

    def capture(self):
        self.request = requests.get(self.url)
        logger.debug("Capturing url %s", self.url)
        if 'text/html' in self.request.headers['Content-Type']:
            self.__class__ = Website
        self.post_capture()
        self.captured = True

    @abstractmethod
    def post_capture(self):
        ...

    def __getstate__(self):
        return {
            "url": self.url,
            "captured": self.captured,
            "request": self.request,
        }

    def __setstate__(self, state):
        self.url = state["url"]
        self.captured = state["captured"]
        self.request = state["request"]
        self.post_capture()


class Website(Site):
    raw: str
    soup: BeautifulSoup
    link_elements: ResultSet
    links: list[str]
    linked_sites: dict[str, Site]

    def __init__(self, url: str):
        super().__init__(url)

    def post_capture(self):
        self.raw = self.request.text
        self.load_links()

    def load_links(self):
        self.soup = BeautifulSoup(self.raw, 'html.parser')
        self.link_elements = self.soup.find_all('a', href=True)
        self.links = [elem["href"] for elem in self.link_elements]
        self.linked_sites = {}
        for link in self.links:
            url = build_url(self.url, link)
            if url is None:
                continue
            _captured_sites.setdefault(url, Site(url))
            self.linked_sites[url] = _captured_sites[url]
