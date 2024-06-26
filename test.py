import logging

from app.crawler import Crawler
from app import crawler


cache = "website_cache.cache"


class CustomFormatter(logging.Formatter):
    print_format = "%(asctime)s - %(name)s - %(message)s (%(filename)s:%(lineno)d)"

    COLORS = {
        logging.DEBUG: "\033[0;34;49m",
        logging.INFO: "\033[0;32;49m",
        logging.WARNING: "\033[0;33;49m",
        logging.ERROR: "\033[0;31;49m",
        logging.CRITICAL: "\033[4;31;49m",
        "reset": "\033[0m",
    }

    def format(self, record):
        color = self.COLORS.get(record.levelno)
        log_fmt = color + self.print_format + self.COLORS.get("reset")
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


if __name__ == '__main__':
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(CustomFormatter())
    logging.basicConfig(handlers=[stream_handler])
    logging.getLogger("webcrawler").setLevel(logging.DEBUG)
    crawler = Crawler("https://www.uni-due.de")
    for _ in zip(crawler, range(1, 100)):
        continue
    crawler.save("website_cache.cache")
    loaded_crawler = Crawler.load("website_cache.cache")
    print("finished script")

doi_regex: str = r"10.[0-9]{4}-[0-9]{2}-[0-9]{2}"
ubo_url = "bibliographie.ub.uni-due.de/"
