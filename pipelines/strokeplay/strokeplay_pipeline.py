from config_manager import load_config
from scrapers.golf_nl_scraper import GolfNLScraper


import logging


logging.basicConfig(level=logging.DEBUG, filename="strokeplay_scraper.log")
scraper_config = load_config()
golf_nl_scraper = GolfNLScraper(scraper_config)
score_details = golf_nl_scraper.run()
print(score_details)
