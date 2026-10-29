from pathlib import Path
import re

from bs4 import BeautifulSoup
from dotenv import dotenv_values
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


# Get the .env file path relative to this script's location
env_path = Path(__file__).parent / ".env"
config = dotenv_values(env_path)
golf_url = "https://mijn.golf.nl/login"
score_url = "https://mijn.golf.nl/mijn-spel/scores"

driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
driver.get(golf_url)
driver.find_element(By.NAME, "email").send_keys(config.get("email"))
driver.find_element(By.NAME, "password").send_keys(config.get("password"))
driver.find_element(By.CLASS_NAME, "button").click()
driver.get(golf_url)
driver.get(score_url)

try:
    element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "c-scores"))
    )

    score_elements = driver.find_elements(By.CLASS_NAME, "c-module")
    score_element_html = [score.get_attribute("innerHTML") for score in score_elements]
    score_differentials = []

    for score in score_element_html:
        score_parser = BeautifulSoup(score, "html.parser")
        score_divs = score_parser.find_all("div")
        score_divs = list(filter(lambda x: x.get("class") is not None, score_divs))
        score_status_divs = [
            score_status_div
            for score_status_div in score_divs
            if "c-score__status" in score_status_div.get("class")
        ]
        sd_pattern = "<div>SD(.*?)\xa0"
        matches = [
            re.search(sd_pattern, str(div_string)) for div_string in score_status_divs
        ]
        extracted_matches = [
            float(match.group(1).replace(",", ".")) for match in matches
        ]
        score_differentials.append(extracted_matches)

    score_differentials_flattened = [
        item for sub_list in score_differentials for item in sub_list
    ]
    print(score_differentials_flattened)

finally:
    driver.quit()
