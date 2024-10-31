import os
import time
import requests
from selenium import webdriver
from bs4 import BeautifulSoup
import pandas as pd
from pdf2image import convert_from_path
import pytesseract
import re

# Configuration
def initialize_driver(driver_path):
    """Initialize the Selenium WebDriver."""
    return webdriver.Chrome(executable_path=driver_path)

# Constants
BASE_URL = "https://www.inecelectionresults.ng/pres/elections/63f8f25b594e164f8146a213?type=pres"

# Utility Functions
def clean_up_name(string):
    """Clean up a string by removing non-alphanumeric characters."""
    return ''.join(letter for letter in string if letter.isalnum())

def download_pdf(pdf_url, save_path):
    """Download a PDF file from a given URL."""
    response = requests.get(pdf_url)
    with open(save_path, 'wb') as file:
        file.write(response.content)

def extract_text_from_image(image):
    """Extract text from an image using pytesseract."""
    return pytesseract.image_to_string(image)

def extract_pdf_text_ocr(pdf_path, pu_name, ward_name, lga_name, state_name):
    """Convert PDF to images and use OCR to extract text."""
    try:
        # Convert PDF to images
        images = convert_from_path(pdf_path)
        text = ""
        
        # Perform OCR on each image
        for image in images:
            text += extract_text_from_image(image)
        
        # Process the extracted text to find relevant information
        relevant_info = extract_relevant_information(text, pu_name, ward_name, lga_name, state_name)
        return relevant_info

    except Exception as e:
        print(f"The error is: {e}, Polling unit is {pu_name}, Ward is {ward_name}, State is {state_name}")
        return None

def extract_relevant_information(text, pu_name, ward_name, lga_name, state_name):
    """Extract relevant information from the OCR text."""
    relevant_info = {
        "State": state_name,
        "LGA": lga_name,
        "Ward": ward_name,
        "Polling Unit": pu_name,
        "Total Registered Voters": None,
        "Total Accredited Voters": None,
        "Political Parties": [],
        "Contested Results": []
    }
    
    # Split text into lines and search for specific information
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if "registered voters" in line.lower():
            relevant_info["Total Registered Voters"] = extract_number_from_text(line)
        elif "accredited voters" in line.lower():
            relevant_info["Total Accredited Voters"] = extract_number_from_text(line)
        elif any(keyword in line.lower() for keyword in ["party", "result"]):
            party, result = parse_party_result(line)
            if party and result:
                relevant_info["Political Parties"].append(party)
                relevant_info["Contested Results"].append(result)

    return relevant_info

def extract_number_from_text(text):
    """Extract the first number found in the text."""
    match = re.search(r'\d+', text)
    return int(match.group()) if match else None

def parse_party_result(line):
    """Parse a line to extract party name and result."""
    parts = line.split()
    party = parts[0] if parts else None
    result = parts[-1] if parts and parts[-1].isdigit() else None
    return party, int(result) if result else None

# Directory Management
def create_directories(base_dir, state, lga, ward):
    """Create directories for saving PDF files."""
    state_dir = os.path.join(base_dir, state)
    lga_dir = os.path.join(state_dir, lga)
    polling_unit_dir = os.path.join(lga_dir, ward)
    os.makedirs(polling_unit_dir, exist_ok=True)
    return polling_unit_dir

# Web Scraping Functions
def scrape_election_data_selenium(driver, base_url, base_dir):
    """Scrape election data from the provided URL using Selenium."""
    data = []
    driver.get(base_url)
    time.sleep(20)  # Allow time for the page to load

    # Parse the page to get state links
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    state_links = soup.find_all('a', class_='')  # Adjust class name as necessary

    for state_link in state_links:
        state_name = clean_up_name(state_link.text.strip())
        state_url = state_link['href']
        full_state_url = f"https://www.inecelectionresults.ng{state_url}"
        driver.get(full_state_url)
        time.sleep(20)

        # Parse LGAs within the state
        state_soup = BeautifulSoup(driver.page_source, 'html.parser')
        lga_links = state_soup.find_all('a', class_='bold')  # Adjust class name as necessary

        for lga_link in lga_links:
            lga_name = clean_up_name(lga_link.text.strip())
            lga_url = lga_link['href']
            full_lga_url = f"https://www.inecelectionresults.ng{lga_url}"
            driver.get(full_lga_url)
            time.sleep(20)

            # Parse Wards within the LGA
            lga_soup = BeautifulSoup(driver.page_source, 'html.parser')
            ward_links = lga_soup.find_all('a', class_='bold')  # Adjust class name as necessary

            for ward_link in ward_links:
                ward_name = clean_up_name(ward_link.text.strip())
                ward_url = ward_link['href']
                full_ward_url = f"https://www.inecelectionresults.ng{ward_url}"
                driver.get(full_ward_url)
                time.sleep(20)

                # Parse Polling Units within the Ward
                ward_soup = BeautifulSoup(driver.page_source, 'html.parser')
                polling_unit_links = ward_soup.find_all('a', class_='btn btn-link ms-2')  # Adjust class name as necessary

                for pu_link in polling_unit_links:
                    pu_name = clean_up_name(pu_link['href'])
                    pu_url = pu_link['href']
                    driver.get(pu_url)
                    time.sleep(20)

                    # Create directories and download PDF
                    polling_unit_dir = create_directories(base_dir, state_name, lga_name, ward_name)
                    pdf_path = os.path.join(polling_unit_dir, f'{pu_name}.pdf')
                    download_pdf(pu_url, pdf_path)

                    # Extract text from the downloaded PDF using OCR
                    relevant_info = extract_pdf_text_ocr(pdf_path, pu_name, ward_name, lga_name, state_name)

                    # Append data to the list
                    if relevant_info:
                        data.append(relevant_info)

    # Convert data into a DataFrame and save it
    df = pd.DataFrame(data)
    df.to_csv(os.path.join(base_dir, 'election_results.csv'), index=False)
    return df

# Main Execution
if __name__ == "__main__":
    driver_path = "Users/okwud/Downloads/chromedriver"  # Update the driver path
    driver = initialize_driver(driver_path)

    base_directory = 'Election_Results'
    os.makedirs(base_directory, exist_ok=True)

    # Scrape data and download PDFs
    df_results = scrape_election_data_selenium(driver, BASE_URL, base_directory)

    # Display the DataFrame
    print(df_results)

    # Close the Selenium driver
    driver.quit()
