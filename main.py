import socket
import urllib.request
from bs4 import BeautifulSoup
import logging
import logging.handlers
import json
import os
from supabase import create_client
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger_file_handler =  logging.handlers.RotatingFileHandler(
    "status.log",
    maxBytes=1024*1024,
    backupCount=1,
    encoding="utf8",
)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger_file_handler.setFormatter(formatter)
logger.addHandler(logger_file_handler)


url =  os.environ.get("SUPA_URL")
key = os.environ.get("SUPA_KEY")
base_url_page = os.environ.get("BASE_URL_PAGE")
base_url = os.environ.get("BASE_URL")
supabase = create_client(url, key)

spec_list = {
    'Brand', 
    'Model',
    'Price in India', 
    'Release date',
    'Dimensions (mm)', 
    'Screen size (inches)',
    'Form factor',
    'Weight (g)',
    'IP rating',
    'Fast charging',
    'Wireless charging',
    'Refresh Rate',
    'Resolution Standard',
    'Resolution',
    'Processor make',
    'Processor',
    'RAM',
    'Internal storage',
    'Colours',
    'Battery capacity (mAh)',
    'Dedicated microSD slot',
    'Rear camera',
    'No. of Rear Cameras',
    'Front camera',
    'Operating system',
    'In-Display Fingerprint Sensor',
    'Number of SIMs'
    }

brand_list = [
        "honor",
        "oppo",
        "xiaomi",
        "infinix",
        "apple",
        "sony",
        "realme",
        "oneplus",
    ] 

PROGRESS_FILE = "progress.json"
PAGE_PER_RUN = 3

def loadProgress():
    if not os.path.exists(PROGRESS_FILE):
        return {"brand_index" : 0, "page": 1}
    try:
        with open(PROGRESS_FILE, 'r') as prog:
            return json.load(prog)
    except (json.JSONDecodeError, IOError) as e:
        logger.info(f"Error reading progress file: {e}. Starting from scratch.")
        return {"brand_index": 0, "page": 1}



def saveProgess(progress, name):
    logger.info(f"Paused at: {progress}, brand:{name}")
    try:
        with open(PROGRESS_FILE, 'w') as prog:
            json.dump(progress, prog)
    except IOError as e:
        logger.info(f"Failed to save progess: {e}")


def save():
    
    progress = loadProgress()
    brand_index = progress['brand_index']
    page = progress['page']
    page_scrapped = 0
    logger.info(f"Started at: brand_index: {brand_list[brand_index]}, page: {page}")

    while page_scrapped < PAGE_PER_RUN:
        name = brand_list[brand_index]
        url = base_url_page.format(page=page, name=name)
        logger.info(f"Scraping {name} - Page {page}")

        try:
            with urllib.request.urlopen(url, timeout=60) as fid:
                webpage = fid.read().decode('latin-1').encode('utf-8')
                if not webpage: 
                    logger.info(f"No more products found for {name} on page {page}. Moving to next brand.")
                    if brand_index + 1 < len(brand_list):
                        brand_index += 1
                        page = 1
                        continue
                    else:
                        logger.info("End of list")
                        break;

                extract(webpage)
                page += 1
                page_scrapped += 1 
        except urllib.error.URLError as e:
            logger.info(f"Network error while fetching {url}: {e}")
        except socket.timeout:
            logger.info(f"Request timed out for {url}")
        except Exception as e:
            logger.info(f"Error fetching data: {e}")
            break

    saveProgess({"brand_index": brand_index, "page": page}, name)
               
          

def extract(webpage):
    soup = BeautifulSoup(webpage, 'html.parser')
    list_items = soup.find_all('li')

    for li in list_items:

        link = li.find('a')
        if link:
            href = link.get('href')
            saveProductDetails(href)


def saveProductDetails(href):
    try:
        with urllib.request.urlopen(href) as fid:
            productLink = fid.read().decode('latin-1').encode('utf-8')
            productDetails(productLink)
    except Exception as e:
        logger.info(f"Error fetching data: {e}")





def productDetails(product_html):
    soup = BeautifulSoup(product_html, 'html.parser')
    spec_sheet = soup.find('div', id="specs")
    if spec_sheet:
        product_name = spec_sheet.find('h2', class_= "_hd").get_text()
        product_name = product_name.replace('Full Specifications', '')
        specs = {'product_name' : product_name}

        for section in soup.find_all('div', class_='_gry-bg _spctbl _ovfhide'):
            for row in section.find_all('tr'):
                cols = row.find_all('td')
                if len(cols) < 2:
                    continue 
                if len(cols) == 2:
                    spec_name = cols[0].get_text()
                    value = cols[1].get_text()
                    
                    if spec_name in spec_list:
                        spec_name = spec_name.lower().replace('(', '').replace(')', '').replace(' ', '_').replace('-', '_').replace('.', '')
                        specs[spec_name] = value

        try:
            data = supabase.table('scrappeddata').upsert(specs, on_conflict=["product_name"]).execute()
        except Exception as e:
            logger.info(f"Supabase error for {product_name}: {e}\n data: {data}")
        # print(f"done: {product_name}")


        

        


if __name__ == "__main__" :
    save()
    