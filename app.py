from flask import Flask, render_template, request, redirect, jsonify
import os
import re
import csv
import pdfplumber
import requests
from urllib.parse import urljoin, urlencode
from bs4 import BeautifulSoup
import io
import base64

app = Flask(__name__, static_url_path='/static')

INSIGHTLY_API_KEY = "Basic YzUxZTNlMTMtZjljZS00MDExLTgzZGItZmM3MWY2ZTg2OTgx"
INSIGHTLY_API_ENDPOINT = "https://api.na1.insightly.com/v3.1/Contacts"

def scrape_website(url):
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        books_data = []

        for book_article in soup.find_all('article', class_='product_pod'):
            title = book_article.find('h3').find('a')['title']

            price = re.sub(r'Â', '', book_article.find('p', class_='price_color').get_text(strip=True))
            availability = book_article.find('p', class_='instock availability').get_text(strip=True)
            rating = book_article.find('p', class_='star-rating')['class'][1]

            link = book_article.find('h3').find('a')['href']
            
            book_url = urljoin(url, link)

            img_tag = book_article.find('img')
            if img_tag and 'src' in img_tag.attrs:
                image_url = urljoin(url, img_tag['src'])
            else:
                image_url = None

            books_data.append({
                'title': title,
                'price': price,
                'availability': availability,
                'rating': rating,
                'book_url': book_url,
                'image_url': image_url
            })

        return books_data
    else:
        return [f"Failed to retrieve the page. Status code: {response.status_code}"]


ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def input_into_crm_insightly(data):
    success_messages = []

    headers = {
        "Authorization": f"{INSIGHTLY_API_KEY}",
    }

    for item in data:
        insightly_payload = {
            "FIRST_NAME": item["Company"], 
            "PHONE": item["Phone"],
            "EMAIL_ADDRESS": item["Email"],
            "TITLE": item["Website"],
        }

        response = requests.post(INSIGHTLY_API_ENDPOINT, json=insightly_payload, headers=headers)

        if response.status_code == 200:
            success_messages.append(
                f"Data input into Insightly CRM successfully for '{item['Company']}'"
            )
        else:
            success_messages.append(
                f"Failed to input data into Insightly CRM for '{item['Company']}'. Status code: {response.status_code}. Response: {response.text}"
            )

    return success_messages

def process_csv(file):
    csv_data = []
    text_file = io.TextIOWrapper(file, encoding='utf-8')
    
    reader = csv.DictReader(text_file, delimiter=',')
    for row in reader:
        entry = {
            'Company': row.get('Company', ''),
            'Phone': row.get('Phone', ''),
            'Email': row.get('Email', ''),
            'Website': row.get('Website', ''),
        }
        csv_data.append(entry)

    return csv_data
    
def parse_pdf(file_path):
    with pdfplumber.open(file_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text()
        return text

def process_single_pdf(file):
    text = ""
    pattern = re.compile(r'([A-Za-z]+),\s*')
    number_pattern = re.compile(r'(\d+),\s*')
    tables = []

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            text += page_text
            matches = pattern.findall(text)
            matches_number = number_pattern.findall(text)
            current_page_table = page.extract_table()
            if current_page_table:
                tables.extend(current_page_table)
    # print(matches)
    return text, matches, matches_number, tables

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scraping', methods=['GET', 'POST'])
def scraping():
    if request.method == 'POST':
        website_url = request.form['website_url']
        scraped_data = scrape_website(website_url)
        return render_template('scraping.html', website_url=website_url, scraped_data=scraped_data)
    return render_template('scraping.html')

@app.route('/pdf_processing', methods=['GET', 'POST'])
def pdf_processing():
    if request.method == 'POST':
        pdf_file = request.files['pdf_file']
        if pdf_file and pdf_file.filename.endswith(".pdf"):
            pdf_filename = pdf_file.filename
            pdf_text, matches, matches_number, tables = process_single_pdf(pdf_file)
            return render_template('pdf_processing.html', pdf_filename=pdf_filename, pdf_text=pdf_text, animals=matches, numbers=matches_number, pdf_tables=tables)
    return render_template('pdf_processing.html')

@app.route('/upload_csv', methods=['GET', 'POST'])
def upload_csv():
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            return render_template('upload_csv.html', error='No file part')

        file = request.files['csv_file']

        if file.filename == '':
            return render_template('upload_csv.html', error='No selected file')

        if file and allowed_file(file.filename):
            csv_data = process_csv(file)

            success_messages = input_into_crm_insightly(csv_data)

            return render_template('upload_csv.html', success_messages=success_messages)

    return render_template('upload_csv.html')

@app.route('/input_into_crm', methods=['GET', 'POST'])
def input_into_crm():
    if request.method == 'POST':
        csv_file = request.files['csv_file']
        if csv_file and csv_file.filename.endswith(".csv"):
            csv_data = process_csv(csv_file)

            success_messages = input_into_crm_insightly(csv_data)

            return render_template('input_into_crm.html', success_messages=success_messages)

    return render_template('input_into_crm.html')

@app.route('/display_crm_data', methods=['GET'])
def display_crm_data():
    try:
        # Make an HTTP GET request to the fetch_crm_data route
        headers = {
            'Authorization': f'{INSIGHTLY_API_KEY}',
            'Content-Type': 'application/json',
        }
        response = requests.get(INSIGHTLY_API_ENDPOINT, headers=headers)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            crm_data = response.json()
            return render_template('display_crm_data.html', crm_data=crm_data)
        else:
            return render_template('display_crm_data.html', crm_data=None, error=f'Failed to fetch CRM data. Status code: {response.status_code}')
    except Exception as e:
        return render_template('display_crm_data.html', crm_data=None, error=f'An error occurred: {str(e)}')

if __name__ == '__main__':
    app.run(debug=True)
