""" 
This file will scrape the Ever supermarket website in Chrome browser using Selenium 
and saves the grocery data in csv file.
"""

import re
import os
import time
import random
import pandas as pd
import numpy as np
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import ElementNotInteractableException
from webdriver_manager.chrome import ChromeDriverManager


TODAY_STR = date.today().strftime('%Y%m%d')

# Initialize output dir
output_main_dir = "csv"
output_sub_dir = TODAY_STR
if not os.path.isdir(f"{output_main_dir}/{output_sub_dir}"):
    os.makedirs(f"{output_main_dir}/{output_sub_dir}")


# Access page
URL = "https://ever.ph/collections"
categories_page = requests.get(URL).text
soup = BeautifulSoup(categories_page, 'lxml')


# NOTE - tags subject to change
categories_path = soup.find_all('div', {"class":"grid-item small--one-half medium--one-third large--one-fifth"})
# Get URL of each grocery category
category_links = []
for i, categories in enumerate(categories_path):
    category_path_link = "https://ever.ph" + categories.a['href'] # NOTE - tags subject to change
    category_link = category_path_link
    category_links.append(category_link)


# In case of script rerun, iterate thru categories that were already saved in dir
available_categories = []
for file in os.listdir(f"{output_main_dir}/{output_sub_dir}"):
    letter_with_space_only = re.sub(r'[^a-zA-Z\s]', '', file) # Remove digits and special chars
    first_word = re.sub(r'(csv)$', '', letter_with_space_only).split()[0] # Remove "csv" at end
    available_categories.append(first_word)

categories_to_exclude = ""
for category in available_categories:
    categories_to_exclude += f"{category}|"
# NOTE - DEFAULT: Exclude Covid page (has error on submit button) and EVP (Ever Value Plus) campaign page
categories_to_exclude += "covid|evp19" 

# Exclude links of categories that were available in dir
regex = re.compile(f'.*({categories_to_exclude}).*', re.IGNORECASE) 
category_links_filtered = [category_link for category_link in category_links if not regex.match(category_link)]
category_links_filtered = sorted(category_links_filtered, key=lambda x: random.random()) # Shuffle pages to reduce bot behavior


def web_scrape_data(category_links):
    """ 
    Web scrapes a page in steps:
    1. At first page, selects random category page where Selenium can successfully click the pop-up page 
    (the site sometimes shows abnormal behavior wherein the pop-up page dont disappear)
    2. Per category page, navigate the entire page by scrolling down continuously until the bottom end
    3. Extract the grocery item and price available on entire page
    4. Save the extracted data in CSV

    IMPORTANT NOTE: Majority of parts here are subject to change since the script of source website can change
    """

    # Initialize chrome driver
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
    print("Web scraping started \n")

    # Check if all csv were already exported
    if len(category_links) == 0:
        print("Already gathered all data as of today. Closing the website")

    for i, category_URL in enumerate(category_links):
        # Access category page link
        driver.get(category_URL)
        category_name = driver.find_element(By.CLASS_NAME, "section-header--title.section-header--left.h1").text
        print(f"{i} - Accessing {category_name} page...")

        #####################################################################################################################################
        # POP-UP PAGE HANDLING PART
               
        # For 1st time access, a pop-up page always appears asking which store branch to select
        failed_scraping = False
        if i == 0:
            num_clicks = 0
            pop_up_not_closed = True

            # Keep clicking the button until pop-up page was closed
            while pop_up_not_closed:
                try:
                    driver.find_element(By.XPATH, '//*[@id="confirmSelect"]').click() # Just click button and select default branch
                    time.sleep(10)
                except ElementNotInteractableException: # Button of pop-up was already gone, which means success and break out of loop
                    pop_up_not_closed = False
                
                num_clicks += 1
                if num_clicks == 3: # Force out of loop if pop-up didnt close even after 3 clicks
                    pop_up_not_closed = False
                    failed_scraping = True # Flag failure in scraping
            
            # Break out of main for-loop when pop-up page was not closed
            if failed_scraping:
                print("    Pop-up page didnt close after 3 clicks. Stopping the scraper...\n")
                break
            
            # Print success if pop-up was closed
            print(f"    Branch selection pop-up bypassed! Proceeding to actual page...")

        #####################################################################################################################################
        # PAGE NAVIGATION PART

        # Initialize body tag element for keys method inside the loop below
        body_tag_element = driver.find_element(By.TAG_NAME, 'body')  

        print(f"    Scrolling down...")

        # Continuously load page until very bottom
        last_item_not_reached = True
        while last_item_not_reached:
            # Scroll to current bottom
            driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
            time.sleep(3)

            # Scroll up a bit
            body_tag_element.send_keys(Keys.PAGE_UP) # Adds buffer in loading. Page doesnt load properly when staying too long at bottom page
            time.sleep(5)

            # Stop loop if page doesn't load anymore in bottom
            text_below = driver.find_element(By.XPATH, '//*[@id="CollectionSection"]/div/div/div[3]/button/span[2]').text
            if text_below == "No more results.": # Check for this message in given xpath
                last_item_not_reached = False

        print("    Successfully reached the bottom page! \n")
        print("    Extracting all data...")

        #####################################################################################################################################
        # DATA EXTRACTION PART

        # Get all product info
        products_data = []
        NOW = datetime.now() # Add timestamp for data logs and historization

        # Products with sale price (with different class name)
        products_with_sale = driver.find_elements(By.CLASS_NAME, 
                                        "productContainer.grid-item.large--one-quarter.medium--one-third.small--one-half.on-sale.slide-up-animation.animated")
        for product in products_with_sale:
            regular_price = product.find_element(By.CLASS_NAME, "product-item--price").text.split()[6].replace('₱', '')
            product_name = product.find_element(By.CLASS_NAME, "productNameContainer").text
            products_data.append({'product_category':category_name, 'product_name':product_name, 'price':regular_price, 'created_time':NOW})

        # Products not in sale
        products = driver.find_elements(By.CLASS_NAME, 
                                        "productContainer.grid-item.large--one-quarter.medium--one-third.small--one-half.slide-up-animation.animated")
        for product in products:
            regular_price = product.find_element(By.CLASS_NAME, "product-item--price").text.split()[2].replace('₱', '')
            product_name = product.find_element(By.CLASS_NAME, "productNameContainer").text
            products_data.append({'product_category':category_name, 'product_name':product_name, 'price':regular_price, 'created_time':NOW})


        # Export as CSV
        products_df = pd.DataFrame(products_data)
        products_df.to_csv(f"{output_main_dir}/{output_sub_dir}/{category_name}_{TODAY_STR}.csv", index=False)

        assert products_df.shape[0] != 0, """No data captured! Inspect the website again for possible changes in structure especially the XPATHs. 
                Compare the latest elements with those implemented here."""
        print("    All data exported! \n\n")


    # Close the browser
    driver.quit()

    # Ask for rerun if pop-up page was not closed
    if failed_scraping:
        need_rerun = True 
    else:
        need_rerun = False
        print("All done! Closing the website")

    return need_rerun


# Set initial param
need_rerun = True
driver_failed_count = 0

# Extract all data
while need_rerun:
    # Run the main script. Also return value if while-loop needs to rerun
    try:
        need_rerun = web_scrape_data(category_links_filtered)
    except ConnectionError: # Rerun when driver failed
        print("Chrome Driver failed to reach. Restarting...")
        driver_failed_count += 1
        if driver_failed_count <= 5:
            pass
        else:
            print("""CONNECTION ERROR: Chrome Driver still unreachable after 5 tries. Please diagnose the installed driver 
                  if it is still at the same location, outdated, etc.""")
            break

    # Shuffle page links to start at different page. Do this only when pop-up page was not closed at previously accessed page
    if need_rerun:
        category_links_filtered = sorted(category_links_filtered, key=lambda x: random.random()) # Shuffle pages
        print("Rerunning the scraper. Start accessing different page...")
        time.sleep(10) # Add delay to avoid ConnectionError