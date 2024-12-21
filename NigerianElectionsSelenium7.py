import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import pdfplumber
from PIL import Image, ImageOps, ImageEnhance
import pytesseract
import re
import logging
from concurrent.futures import ThreadPoolExecutor
from retrying import retry

# Setup logging
logging.basicConfig(filename="election_results.log", level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

# Constants
driver_path = "Users/okwud/Downloads/chromedriver"  # Specify the correct path
base_directory = 'Election_Results'
os.makedirs(base_directory, exist_ok=True)
BASE_URL = "https://www.inecelectionresults.ng/pres/elections/63f8f25b594e164f8146a213?type=pres"

def clean_up_name(string):
    return ''.join(letter for letter in string if letter.isalnum())

@retry(stop_max_attempt_number=10, wait_fixed=2000)
def download_file(file_url, save_path):
    """Download a file with retry mechanism."""
    response = requests.get(file_url, stream=True, timeout=10)
    response.raise_for_status()  # Raise HTTPError for bad responses
    content_type = response.headers.get('Content-Type', '')

    if 'application/pdf' in content_type:
        with open(save_path, 'wb') as file:
            file.write(response.content)
        return "pdf"
    elif 'image' in content_type:
        with open(save_path, 'wb') as file:
            file.write(response.content)
        return "image"
    else:
        return content_type

def create_directories(base_dir, state, lga, ward):
    state_dir = os.path.join(base_dir, state)
    lga_dir = os.path.join(state_dir, lga)
    ward_dir = os.path.join(lga_dir, ward)
    os.makedirs(ward_dir, exist_ok=True)
    return ward_dir

def preprocess_image(image):
    """Enhance the image for better OCR accuracy."""
    image = ImageOps.grayscale(image)
    image = ImageEnhance.Contrast(image).enhance(2.0)
    return image

def rotate_until_text_extracted(image_path, max_retries=4):
    """Rotate image in 90-degree increments until text is extracted or max retries are reached."""
    try:
        with Image.open(image_path) as img:
            img = preprocess_image(img)
            for attempt in range(max_retries):
                text = pytesseract.image_to_string(img)
                if len(text.strip()) > 50:  # Check if text is sufficiently long
                    return text
                img = img.rotate(90, expand=True)
        return ""
    except Exception as e:
        logging.error(f"Error rotating image for text extraction: {e}")
        return ""

def extract_text_from_image(image_path):
    try:
        return rotate_until_text_extracted(image_path)
    except Exception as e:
        logging.error(f"Error extracting text from image: {e}")
        return ""

def rotate_pdf_pages_and_extract_text(pdf_path, max_retries=4):
    """Rotate PDF pages and use OCR for text extraction."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                for attempt in range(max_retries):
                    rotated_page = page.to_image().rotate(90 * attempt)
                    page_text = pytesseract.image_to_string(rotated_page.original)
                    if len(page_text.strip()) > 50:
                        text += page_text
                        break
            return text
    except Exception as e:
        logging.error(f"Error rotating PDF pages for text extraction: {e}")
        return ""

def extract_pdf_text(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "".join(page.extract_text() or "" for page in pdf.pages)
        if len(text.strip()) > 50:
            return text
        logging.info(f"Direct text extraction failed for {pdf_path}, attempting rotation.")
        return rotate_pdf_pages_and_extract_text(pdf_path)
    except Exception as e:
        logging.error(f"Error extracting text from PDF: {e}")
        return ""

def process_file(file_path, file_type):
    if file_type == "pdf":
        return extract_pdf_text(file_path)
    elif file_type == "image":
        return extract_text_from_image(file_path)
    return ""

def extract_polling_unit_data(text):
    """Extract structured data from the text of polling unit result sheets."""
    data = {
        'number_of_voters': None,
        'accredited_voters': None,
        'spoiled_ballots': None,
        'rejected_ballots': None,
        'valid_votes': None,
        'party_results': {},
        'presiding_officer': None
    }
    try:
        data['number_of_voters'] = int(re.search(r"Number of Voters on the Register\s*:\s*(\d+)", text, re.IGNORECASE).group(1))
        data['accredited_voters'] = int(re.search(r"Number of Accredited Voters\s*:\s*(\d+)", text, re.IGNORECASE).group(1))
        data['spoiled_ballots'] = int(re.search(r"Spoiled Ballot Papers\s*:\s*(\d+)", text, re.IGNORECASE).group(1))
        data['rejected_ballots'] = int(re.search(r"Rejected Ballot Papers\s*:\s*(\d+)", text, re.IGNORECASE).group(1))
        data['valid_votes'] = int(re.search(r"Total Valid Votes\s*:\s*(\d+)", text, re.IGNORECASE).group(1))
        party_results = re.findall(r"([A-Za-z]+)\s*:\s*(\d+)", text)
        for party, votes in party_results:
            data['party_results'][party] = int(votes)
        presiding_officer_match = re.search(r"Presiding Officer\s*:\s*([A-Za-z\s]+)", text, re.IGNORECASE)
        if presiding_officer_match:
            data['presiding_officer'] = presiding_officer_match.group(1).strip()
    except Exception as e:
        logging.error(f"Error extracting polling unit data: {e}")
    return data

def scrape_election_data_selenium(base_url, base_dir):
    data = []
    driver = webdriver.Chrome()
    try:
        driver.get(base_url)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CLASS_NAME, 'bold')))

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        state_links = soup.find_all('a', class_='')

        def process_state(state_link):
            state_name = clean_up_name(state_link.text.strip())
            state_url = state_link['href']
            full_state_url = f"https://www.inecelectionresults.ng{state_url}"
            driver.get(full_state_url)
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CLASS_NAME, 'bold')))

            state_soup = BeautifulSoup(driver.page_source, 'html.parser')
            lga_links = state_soup.find_all('a', class_='bold')

            for lga_link in lga_links:
                lga_name = clean_up_name(lga_link.text.strip())
                lga_url = lga_link['href']
                full_lga_url = f"https://www.inecelectionresults.ng{lga_url}"
                driver.get(full_lga_url)
                WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CLASS_NAME, 'bold')))

                lga_soup = BeautifulSoup(driver.page_source, 'html.parser')
                ward_links = lga_soup.find_all('a', class_='bold')

                for ward_link in ward_links:
                    ward_name = clean_up_name(ward_link.text.strip())
                    ward_url = ward_link['href']
                    full_ward_url = f"https://www.inecelectionresults.ng{ward_url}"
                    driver.get(full_ward_url)
                    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CLASS_NAME, 'btn btn-link')))

                    ward_soup = BeautifulSoup(driver.page_source, 'html.parser')
                    polling_unit_links = ward_soup.find_all('a', class_='btn btn-link ms-2')
                    pu_names = ward_soup.find_all('div', class_='pl-4 bold')

                    for pu_link, pu_name_div in zip(polling_unit_links, pu_names):
                        pu_name = clean_up_name(pu_name_div.text.strip())
                        pu_url = pu_link['href']

                        ward_dir = create_directories(base_dir, state_name, lga_name, ward_name)
                        file_path = os.path.join(ward_dir, f'{pu_name}')

                        try:
                            file_type = download_file(pu_url, file_path)
                            if file_type in ["pdf", "image"]:
                                text = process_file(file_path, file_type)
                                pu_data = extract_polling_unit_data(text)
                                data.append({
                                    'State': state_name,
                                    'LGA': lga_name,
                                    'Ward': ward_name,
                                    'Polling Unit': pu_name,
                                    'File Path': file_path,
                                    **pu_data
                                })
                        except Exception as e:
                            logging.error(f"Error processing polling unit: {pu_name}, {e}")

        with ThreadPoolExecutor() as executor:
            executor.map(process_state, state_links)

        df = pd.DataFrame(data)
        df.to_csv(os.path.join(base_dir, 'election_results.csv'), index=False)
        df.to_excel(os.path.join(base_dir, 'election_results.xlsx'), index=False)
    finally:
        driver.quit()
    return df

if __name__ == "__main__":
    logging.info("Scraping started.")
    try:
        results_df = scrape_election_data_selenium(BASE_URL, base_directory)
        logging.info("Scraping completed successfully.")
    except Exception as e:
        logging.error(f"Critical error occurred: {e}")
