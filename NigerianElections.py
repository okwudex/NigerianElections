import os
import requests
from bs4 import BeautifulSoup
import pandas as pd
import pdfplumber

# Base URL of the election results site
BASE_URL = "https://www.inecelectionresults.ng/pres/elections/63f8f25b594e164f8146a213?type=pres"

# Create a function to download the PDF
def download_pdf(pdf_url, save_path):
    response = requests.get(pdf_url)
    with open(save_path, 'wb') as file:
        file.write(response.content)

# Create directories for State, LGAs, Wards, and Polling Units
def create_directories(base_dir, state, lga, ward, polling_unit):
    state_dir = os.path.join(base_dir, state)
    lga_dir = os.path.join(state_dir, lga)
    ward_dir = os.path.join(lga_dir, ward)
    polling_unit_dir = os.path.join(ward_dir, polling_unit)
    os.makedirs(polling_unit_dir, exist_ok=True)
    return polling_unit_dir

# Extract text from PDF and return as string
def extract_pdf_text(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text()
    return text

# Parse each state, LGA, ward, and polling unit to download PDFs
def scrape_election_data(base_url, base_dir):
    data = []
    
    # Start by requesting the base page and getting state links
    response = requests.get(base_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    print(response)
    print(soup)
    
    # Assume state links are found in specific containers, adjust as needed based on page structure
    state_links = soup.find_all('a')  # Adjust class names as per website structure
    print(state_links)

    for state_link in state_links:
        state_name = state_link.text.strip()
        state_url = state_link['href']
        
        # Scrape LGAs in the state
        state_response = requests.get(state_url)
        state_soup = BeautifulSoup(state_response.content, 'html.parser')
        lga_links = state_soup.find_all('a', class_='lga-link')  # Adjust based on page
        
        for lga_link in lga_links:
            lga_name = lga_link.text.strip()
            lga_url = lga_link['href']
            
            # Scrape wards in the LGA
            lga_response = requests.get(lga_url)
            lga_soup = BeautifulSoup(lga_response.content, 'html.parser')
            ward_links = lga_soup.find_all('a', class_='ward-link')  # Adjust based on page
            
            for ward_link in ward_links:
                ward_name = ward_link.text.strip()
                ward_url = ward_link['href']
                
                # Scrape polling units in the ward
                ward_response = requests.get(ward_url)
                ward_soup = BeautifulSoup(ward_response.content, 'html.parser')
                polling_unit_links = ward_soup.find_all('a', class_='polling-unit-link')  # Adjust based on page
                
                for pu_link in polling_unit_links:
                    pu_name = pu_link.text.strip()
                    pu_url = pu_link['href']
                    
                    # Scrape the polling unit to get the PDF link
                    pu_response = requests.get(pu_url)
                    pu_soup = BeautifulSoup(pu_response.content, 'html.parser')
                    pdf_link = pu_soup.find('a', class_='pdf-link')['href']  # Adjust based on page
                    
                    # Create directories and download PDF
                    polling_unit_dir = create_directories(base_dir, state_name, lga_name, ward_name, pu_name)
                    pdf_path = os.path.join(polling_unit_dir, f'{pu_name}.pdf')
                    download_pdf(pdf_link, pdf_path)
                    
                    # Extract text from the downloaded PDF
                    pdf_text = extract_pdf_text(pdf_path)
                    
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
    df_results = scrape_election_data(BASE_URL, base_directory)
    
    # Display the DataFrame (optional)
    print(df_results)
