import logging
import os.path
import pickle
import re
from abc import abstractmethod
from time import sleep
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup, ResultSet
from requests import Response, Session

_website_capture_regex: re.Pattern = re.compile(r"(https?://)?[A-Za-z0-9.\-_@+\[\]{}]*\.[a-zA-Z]{2,4}.*")
_ude_url_capture_regex: re.Pattern = re.compile(r"(https?://)?([A-Za-z0-9.\-_@+\[\]{}]*\.)?uni-due.de(/.*)?")
_filtered_urls_regex: re.Pattern = re.compile(r"(mailto:.*)|(javascript:.*)|(ftp:.*)|(tel:.*)")
_ude_host_regex: re.Pattern = re.compile(r"(.*\.)uni-due.de")

logger = logging.getLogger("webcrawler")
session = Session()

request_save_base_path = "./sites"
captured_sites: dict[str, "Site"] = {}


def build_url(base: str, url: str) -> str | None:
    split_url = urlsplit(urljoin(base, url))
    if not _ude_host_regex.fullmatch(split_url.netloc) or split_url.scheme not in ["http", "https"]:
        return None
    final_url = "https://" + split_url.netloc + split_url.path
    return final_url


class Crawler:
    _remaining_sites: set["Site"]

    def __init__(self, start: str):
        self.start = start
        self.entry = Site(start)
        captured_sites[self.entry.url] = self.entry
        self._remaining_sites = {self.entry}

    def __next__(self):
        if len(self._remaining_sites) == 0:
            raise StopIteration
        current: Site = self._remaining_sites.pop()
        current.capture()
        if not isinstance(current, Website):
            return current
        to_be_added = set(
            filter(lambda x: not (x.captured or x in self._remaining_sites), current.linked_sites.values()))
        self._remaining_sites |= to_be_added
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

    def current_remaining(self) -> int:
        return len(self._remaining_sites)

    def __getstate__(self):
        return {
            "remaining_sites": self._remaining_sites,
            "start": self.start,
            "entry": self.entry,
            "all": {url: site.__getstate__() for url, site in captured_sites.items()},
        }

    def __setstate__(self, state):
        global captured_sites
        self._remaining_sites = state["remaining_sites"]
        self.start = state["start"]
        self.entry = state["entry"]

        for url, site in state["all"].items():
            captured_sites[url] = Site(url)
            captured_sites[url].__setstate__(site)


class Site:
    def __init__(self, url: str):
        self.url = url
        self.file_path = os.path.join(request_save_base_path, self.url, "site.request")
        self.captured = False

    def capture(self):
        self.captured = True
        try:
            self.request = session.get(self.url)
        except requests.exceptions.Timeout as e:
            logger.error(f"Connection to {self.url} timed out ({e})")
            sleep(60)  # wait a minute so that if the servers crashed, they have time to get back up.
        except requests.exceptions.SSLError as e:
            logger.error(f"Couldn't verify ssl-certificate of {self.url} ({e})")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Couldn't connect to {self.url} due to a connection error ({e})")
        except requests.exceptions.HTTPError as e:
            logger.error(f"Couldn't get {self.url} due to {e} because the server returned an invalid response ({e})")
        except requests.exceptions.RequestException as e:
            logger.error(f"Couldn't get {self.url} due to {e}")
        except Exception as e:
            if isinstance(e, KeyboardInterrupt):
                raise e
            logger.error(f"Error trying to get {self.url}: {e}")
        else:
            logger.debug("Capturing url %s", self.url)
            if 'text/html' in self.request.headers.get("Content-Type", ""):
                self.__class__ = Website
            self.post_capture()

    @abstractmethod
    def post_capture(self):
        ...

    def __getstate__(self):
        state = {
            "url": self.url,
            "captured": self.captured,
        }
        return state

    def __setstate__(self, state):
        self.url = state["url"]
        self.file_path = os.path.join(request_save_base_path, self.url, "site.request")
        self.captured = state["captured"] or self.request is not None
        if self.request is None:
            return
        if 'text/html' in self.request.headers.get("Content-Type", ""):
            self.__class__ = Website
        self.post_capture()

    def __str__(self):
        return f"<{self.__class__.__name__}: {self.url}>"

    def __repr__(self):
        return str(self)

    @property
    def request(self) -> Response | None:
        if not os.path.isfile(self.file_path):
            return None
        with open(self.file_path, "rb") as f:
            return pickle.load(f)

    @request.setter
    def request(self, value: Response):
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, "wb") as f:
            pickle.dump(value, f)


class Website(Site):
    raw: str
    soup: BeautifulSoup
    link_elements: ResultSet
    links: list[str]
    linked_sites: dict[str, Site]

    def __init__(self, url: str):
        super().__init__(url)

    def post_capture(self):
        link_elements = self.soup.find_all('a', href=True)
        links = [elem["href"] for elem in link_elements]
        self.linked_sites = {}
        for link in links:
            url = build_url(self.url, link)
            if url is None:
                continue
            captured_sites.setdefault(url, Site(url))
            self.linked_sites[url] = captured_sites[url]

    @property
    def soup(self) -> BeautifulSoup:
        return BeautifulSoup(self.request.text, 'html.parser')
