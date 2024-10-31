import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import pandas as pd
import pdfplumber
from pdf2image import convert_from_path
from pytesseract import image_to_string

# Initialize WebDriver (adjust the path to your chromedriver)
driver_path = "Users/okwud/Downloads/chromedriver"  # Specify the correct path
driver = webdriver.Chrome()

# Base URL of the election results site
BASE_URL = "https://www.inecelectionresults.ng/pres/elections/63f8f25b594e164f8146a213?type=pres"

def clean_up_name(string):
    
    test_str = ''.join(letter for letter in string if letter.isalnum())
    return test_str
# Function to download PDF file
def download_pdf(pdf_url, save_path):
    response = requests.get(pdf_url)
    with open(save_path, 'wb') as file:
        file.write(response.content)

# Create directories for State, LGAs, Wards, and Polling Units
def create_directories(base_dir, state, lga, ward):
    state_dir = os.path.join(base_dir, state)
    lga_dir = os.path.join(state_dir, lga)
    polling_unit_dir = os.path.join(lga_dir, ward)
    #polling_unit_dir = os.path.join(ward_dir, polling_unit)
    os.makedirs(polling_unit_dir, exist_ok=True)
    return polling_unit_dir

# Extract text from PDF and return as string
def extract_pdf_text(pdf_path, pu_exception, ward_exception, state_exception):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text()
        return text
    except Exception as e:
        print("The error is: ", e, " Polling unit is ", pu_exception, " Ward is ", ward_exception, " State is ", state_exception)


# Selenium function to navigate and scrape the links dynamically
def scrape_election_data_selenium(base_url, base_dir):
    data = []
    driver.get(base_url)
    time.sleep(20)  # Allow time for the page to load
    
    # Parse the page to get state links
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    state_links = soup.find_all('a', class_='')  # Adjust based on actual class name
    
    for state_link in state_links:
        print(state_link)
        state_name = state_link.text.strip()
        print(state_name)
        state_name = clean_up_name(state_name)
        state_url = state_link['href']
        print(state_url)
        full_state_url = "https://www.inecelectionresults.ng"+state_url
        print(full_state_url)
        driver.get(full_state_url)
        time.sleep(20)
        
        # Parse LGAs within the state
        state_soup = BeautifulSoup(driver.page_source, 'html.parser')
        print(state_soup)
        lga_links = state_soup.find_all('a', class_='bold')  # Adjust based on actual class name
        print(lga_links)
        for lga_link in lga_links:
            print(lga_link)
            lga_name = lga_link.text.strip()
            print(lga_name)
            lga_name = clean_up_name(lga_name)
            lga_url = lga_link['href']
            print(lga_url)
            full_lga_url = "https://www.inecelectionresults.ng"+lga_url
            print(full_lga_url)
            driver.get(full_lga_url)
            time.sleep(20)
            
            # Parse Wards within the LGA
            lga_soup = BeautifulSoup(driver.page_source, 'html.parser')
            ward_links = lga_soup.find_all('a', class_='bold')  # Adjust based on actual class name
            print(ward_links)
            
            for ward_link in ward_links:
                print(ward_link)
                ward_name = ward_link.text.strip()
                print(ward_name)
                ward_name = clean_up_name(ward_name)
                ward_url = ward_link['href']
                print(ward_url)
                full_ward_url = "https://www.inecelectionresults.ng"+ward_url
                print(full_ward_url)
                driver.get(full_ward_url)
                time.sleep(20)
                
                # Parse Polling Units within the Ward
                ward_soup = BeautifulSoup(driver.page_source, 'html.parser')
                polling_unit_links = ward_soup.find_all('a', class_='btn btn-link ms-2')  # Adjust based on actual class name
                print(polling_unit_links)
                
                for pu_link in polling_unit_links:
                    print(pu_link)
                    pu_name = clean_up_name(pu_link['href'])
                    print(pu_name)
                    pu_url = pu_link['href']
                    print(pu_url)
                    driver.get(pu_url)
                    time.sleep(20)
                    
                    # Find and download the PDF file
                    #pdf_link = BeautifulSoup(driver.page_source, 'html.parser')
                    #print(pdf_link)
                    #pdf_link = pu_soup.find('a', class_='')['href']  # Adjust based on actual class name
                    
                    # Create directories and download PDF
                    polling_unit_dir = create_directories(base_dir, state_name, lga_name, ward_name)
                    print(polling_unit_dir)
                    pdf_path = os.path.join(polling_unit_dir, f'{pu_name}.pdf')
                    print(pdf_path)
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
