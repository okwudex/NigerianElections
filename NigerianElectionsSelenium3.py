import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import pandas as pd
import pdfplumber
import re

# Initialize WebDriver (adjust the path to your chromedriver)
driver_path = "Users/okwud/Downloads/chromedriver"  # Specify the correct path
driver = webdriver.Chrome()

# Base URL of the election results site
BASE_URL = "https://www.inecelectionresults.ng/pres/elections/63f8f25b594e164f8146a213?type=pres"

# Helper function to clean names
def clean_up_name(string):
    return ''.join(letter for letter in string if letter.isalnum())

# Function to download PDF file
def download_pdf(pdf_url, save_path):
    response = requests.get(pdf_url)
    with open(save_path, 'wb') as file:
        file.write(response.content)

# Create directories for State, LGAs, and Wards
def create_directories(base_dir, state, lga, ward):
    state_dir = os.path.join(base_dir, state)
    lga_dir = os.path.join(state_dir, lga)
    ward_dir = os.path.join(lga_dir, ward)
    os.makedirs(ward_dir, exist_ok=True)
    return ward_dir

# Extract text from PDF and return as string
def extract_pdf_text(pdf_path, pu_exception, ward_exception, state_exception):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text()
        return text
    except Exception as e:
        print("Error:", e, "Polling Unit:", pu_exception, "Ward:", ward_exception, "State:", state_exception)

# Selenium function to navigate and scrape the links dynamically
def scrape_election_data_selenium(base_url, base_dir):
    data = []
    driver.get(base_url)
    time.sleep(20)  # Allow time for the page to load
    
    # Parse the page to get state links
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    state_links = soup.find_all('a', class_='')  # Adjust based on actual class name
    
    for state_link in state_links:
        state_name = clean_up_name(state_link.text.strip())
        state_url = state_link['href']
        full_state_url = f"https://www.inecelectionresults.ng{state_url}"
        driver.get(full_state_url)
        time.sleep(20)
        
        # Parse LGAs within the state
        state_soup = BeautifulSoup(driver.page_source, 'html.parser')
        lga_links = state_soup.find_all('a', class_='bold')  # Adjust based on actual class name
        
        for lga_link in lga_links:
            lga_name = clean_up_name(lga_link.text.strip())
            lga_url = lga_link['href']
            full_lga_url = f"https://www.inecelectionresults.ng{lga_url}"
            driver.get(full_lga_url)
            time.sleep(20)
            
            # Parse Wards within the LGA
            lga_soup = BeautifulSoup(driver.page_source, 'html.parser')
            ward_links = lga_soup.find_all('a', class_='bold')  # Adjust based on actual class name
            
            for ward_link in ward_links:
                ward_name = clean_up_name(ward_link.text.strip())
                ward_url = ward_link['href']
                full_ward_url = f"https://www.inecelectionresults.ng{ward_url}"
                driver.get(full_ward_url)
                time.sleep(20)
                
                # Parse Polling Units within the Ward
                ward_soup = BeautifulSoup(driver.page_source, 'html.parser')
                polling_unit_links = ward_soup.find_all('a', class_='btn btn-link ms-2')  # Adjust based on actual class name
                pu_names = ward_soup.find_all('div', class_='pl-4 bold')
                
                for pu_link, pu_name_div in zip(polling_unit_links, pu_names):
                    pu_name = clean_up_name(pu_name_div.text.strip())
                    pu_url = pu_link['href']
                    
                    # Create directories and download PDF
                    ward_dir = create_directories(base_dir, state_name, lga_name, ward_name)
                    pdf_path = os.path.join(ward_dir, f'{pu_name}.pdf')
                    download_pdf(pu_url, pdf_path)
                    
                    # Extract text from the downloaded PDF
                    pdf_text = extract_pdf_text(pdf_path, pu_name, ward_name, state_name)
                    
                    # Append data to the list
                    data.append({
                        'State': state_name,
                        'LGA': lga_name,
                        'Ward': ward_name,
                        'Polling Unit': pu_name,
                        'PDF Path': pdf_path,
                        'PDF Text': pdf_text
                    })
    
    # Convert data into a Pandas DataFrame and save it
    df = pd.DataFrame(data)
    df.to_csv(os.path.join(base_dir, 'election_results.csv'), index=False)
    return df

# Main execution
if __name__ == "__main__":
    base_directory = 'Election_Results'  # Root directory where data will be saved
    os.makedirs(base_directory, exist_ok=True)
    
    # Scrape data and download PDFs
    df_results = scrape_election_data_selenium(BASE_URL, base_directory)
    
    # Display the DataFrame (optional)
    print(df_results)

# Close the Selenium driver after finishing
driver.quit()
