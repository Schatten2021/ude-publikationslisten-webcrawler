from app.crawler import Site, Website, _captured_sites


def contains_publication_list(site: Site) -> bool:
    if not isinstance(site, Website):
        return False
    site: Website
    ""
