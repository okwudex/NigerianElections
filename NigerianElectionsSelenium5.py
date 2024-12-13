import os
import time
import requests
from selenium import webdriver
from bs4 import BeautifulSoup
import pandas as pd
import pdfplumber
import re

driver_path = "Users/okwud/Downloads/chromedriver"  
# Specify the correct path for your webdriver.
# Please refer to the following links for direction on how to install the webdriver
# https://sites.google.com/chromium.org/driver/getting-started
# https://sites.google.com/chromium.org/driver/downloads

driver = webdriver.Chrome()

BASE_URL = "https://www.inecelectionresults.ng/pres/elections/63f8f25b594e164f8146a213?type=pres"

# This is INEC link for the 2023 Presidential Elections

def clean_up_name(string):
    return ''.join(letter for letter in string if letter.isalnum())
# This function cleans up any string and removes special characters and symbols

def download_file(file_url, save_path):
    # This function is for downloading pdf files.
    response = requests.get(file_url, stream=True)
    content_type = response.headers.get('Content-Type', '')
    
    if 'application/pdf' in content_type:
        with open(save_path, 'wb') as file:
            file.write(response.content)
        return "pdf"
    else:
        return content_type

def create_directories(base_dir, state, lga, ward):
    # This function creates folders for storing downloaded pdf files
    state_dir = os.path.join(base_dir, state)
    lga_dir = os.path.join(state_dir, lga)
    ward_dir = os.path.join(lga_dir, ward)
    os.makedirs(ward_dir, exist_ok=True)
    return ward_dir

def is_pdf_readable(text):
    # A simple heuristic: unreadable PDFs often have very short or mostly non-alphanumeric text
    if len(text) < 50 or not any(char.isalnum() for char in text):
        return False
    return True

def extract_pdf_text(pdf_path, pu_exception, ward_exception, lga_exception, state_exception, unreadable_count_by_location, state_name, lga_name, ward_name):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "".join(page.extract_text() or "" for page in pdf.pages)
        if not is_pdf_readable(text):
            unreadable_count_by_location[state_name][lga_name][ward_name]['unreadable'] += 1
            print(f"Unreadable PDF detected: {pdf_path} (Polling Unit: {pu_exception}, Ward: {ward_exception}, LGA: {lga_exception}, State: {state_name})")
        return text
    except Exception as e:
        print("Error extracting text from PDF:", e, "Polling Unit:", pu_exception, "Ward:", ward_exception, "LGA:", lga_exception, "State:", state_name)
        return None

def scrape_election_data_selenium(base_url, base_dir):
    data = []
    non_pdf_files_by_location = {}
    unreadable_count_by_location = {}
    driver.get(base_url)
    time.sleep(20)  # Allow time for the page to load

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    state_links = soup.find_all('a', class_='')

    for state_link in state_links:
        state_name = clean_up_name(state_link.text.strip())
        state_url = state_link['href']
        full_state_url = f"https://www.inecelectionresults.ng{state_url}"
        driver.get(full_state_url)
        time.sleep(20)

        non_pdf_files_by_location.setdefault(state_name, {})
        unreadable_count_by_location.setdefault(state_name, {})

        state_soup = BeautifulSoup(driver.page_source, 'html.parser')
        lga_links = state_soup.find_all('a', class_='bold')

        for lga_link in lga_links:
            lga_name = clean_up_name(lga_link.text.strip())
            lga_url = lga_link['href']
            full_lga_url = f"https://www.inecelectionresults.ng{lga_url}"
            driver.get(full_lga_url)
            time.sleep(20)

            non_pdf_files_by_location[state_name].setdefault(lga_name, {})
            unreadable_count_by_location[state_name].setdefault(lga_name, {})

            lga_soup = BeautifulSoup(driver.page_source, 'html.parser')
            ward_links = lga_soup.find_all('a', class_='bold')

            for ward_link in ward_links:
                ward_name = clean_up_name(ward_link.text.strip())
                ward_url = ward_link['href']
                full_ward_url = f"https://www.inecelectionresults.ng{ward_url}"
                driver.get(full_ward_url)
                time.sleep(20)

                non_pdf_files_by_location[state_name][lga_name].setdefault(ward_name, {'non_pdf': 0, 'unreadable': 0})
                unreadable_count_by_location[state_name][lga_name].setdefault(ward_name, {'non_pdf': 0, 'unreadable': 0})

                ward_soup = BeautifulSoup(driver.page_source, 'html.parser')
                polling_unit_links = ward_soup.find_all('a', class_='btn btn-link ms-2')
                pu_names = ward_soup.find_all('div', class_='pl-4 bold')

                for pu_link, pu_name_div in zip(polling_unit_links, pu_names):
                    pu_name = clean_up_name(pu_name_div.text.strip())
                    pu_url = pu_link['href']

                    ward_dir = create_directories(base_dir, state_name, lga_name, ward_name)
                    pdf_path = os.path.join(ward_dir, f'{pu_name}.pdf')

                    file_type = download_file(pu_url, pdf_path)

                    if file_type != "pdf":
                        non_pdf_files_by_location[state_name][lga_name][ward_name]['non_pdf'] += 1
                        print(f"Non-PDF file encountered: {file_type} (Polling Unit: {pu_name}, Ward: {ward_name}, LGA: {lga_name}, State: {state_name})")
                        continue

                    pdf_text = extract_pdf_text(pdf_path, pu_name, ward_name, lga_name, state_name, unreadable_count_by_location, state_name, lga_name, ward_name)

                    data.append({
                        'State': state_name,
                        'LGA': lga_name,
                        'Ward': ward_name,
                        'Polling Unit': pu_name,
                        'PDF Path': pdf_path,
                        'PDF Text': pdf_text
                    })

    df = pd.DataFrame(data)
    df.to_csv(os.path.join(base_dir, 'election_results.csv'), index=False)

    print("Summary of non-PDF files by location:")
    for state, lgas in non_pdf_files_by_location.items():
        for lga, wards in lgas.items():
            for ward, counts in wards.items():
                print(f"{state} -> {lga} -> {ward}: {counts['non_pdf']} non-PDF files")

    print("Summary of unreadable PDFs by location:")
    for state, lgas in unreadable_count_by_location.items():
        for lga, wards in lgas.items():
            for ward, counts in wards.items():
                print(f"{state} -> {lga} -> {ward}: {counts['unreadable']} unreadable PDFs")

    return df

if __name__ == "__main__":
    base_directory = 'Election_Results'
    os.makedirs(base_directory, exist_ok=True)

    df_results = scrape_election_data_selenium(BASE_URL, base_directory)
    print(df_results)

driver.quit()
