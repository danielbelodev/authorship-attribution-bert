from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import os
import sys
import requests
from bs4 import BeautifulSoup
import csv

# Add the project directory to Python path
project_dir = os.path.expanduser('~/schule/diplomarbeit')
if project_dir not in sys.path:
    sys.path.append(project_dir)

# Import the functions from the original files
from crawler.DerStandard_crawler_today import extract_article_content, save_to_csv, read_seen_urls

# Constants
COOKIES = {'DSGVO_ZUSAGE_V1': 'true'}
CSV_PATH = os.path.join(project_dir, 'crawler', 'urls_today.csv')

# Default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2024, 1, 1),
}

# Define the DAG
dag = DAG(
    'detailed_workflow',
    default_args=default_args,
    description='Detailed workflow with many tasks using original functions',
    schedule_interval='0 0 * * *',  # Run daily at midnight
    catchup=False,
)

# Task 1: Get today's date and create sitemap URL
def setup_date_and_url():
    """Get today's date and create the sitemap URL"""
    today = datetime.now()
    today_date = today.date()
    sitemap_url = f"https://www.derstandard.at/sitemaps/sitemap-{today.year}-{today.month:02}.xml"
    
    print(f"Processing articles for {today_date}")
    print(f"Using sitemap: {sitemap_url}")
    
    # Return values for the next task
    return {
        'today_date': today_date,
        'sitemap_url': sitemap_url
    }

# Task 2: Fetch the sitemap
def fetch_sitemap(**context):
    """Fetch the sitemap XML"""
    ti = context['ti']
    result = context['ti'].xcom_pull(task_ids='setup_date_and_url')
    sitemap_url = result['sitemap_url']
    
    print(f"Fetching sitemap: {sitemap_url}")
    response = requests.get(sitemap_url, cookies=COOKIES)
    response.raise_for_status()
    
    # Store basic info about the sitemap
    return {
        'sitemap_url': sitemap_url,
        'status_code': response.status_code,
        'content_length': len(response.content),
        'content': response.content.decode('utf-8')  # Decode bytes to string
    }

# Task 3: Parse the sitemap
def parse_sitemap(**context):
    """Parse the sitemap XML and find today's articles"""
    result_fetch = context['ti'].xcom_pull(task_ids='fetch_sitemap')
    result_setup = context['ti'].xcom_pull(task_ids='setup_date_and_url')
    
    sitemap_content = result_fetch['content'].encode('utf-8')  # Convert string back to bytes for BeautifulSoup
    today_date = result_setup['today_date']
    
    soup = BeautifulSoup(sitemap_content, 'xml')
    url_tags = soup.find_all('url')
    
    # Filter for today's articles
    today_urls = []
    for url_tag in url_tags:
        loc = url_tag.find('loc').text
        lastmod_tag = url_tag.find('lastmod')
        
        if not lastmod_tag:
            continue
            
        lastmod = lastmod_tag.text
        
        # Parse the lastmod date to check if it's from today
        try:
            lastmod_date = datetime.fromisoformat(lastmod.replace('Z', '+00:00')).date()
            # Add if from today
            if lastmod_date == today_date:
                today_urls.append((loc, lastmod))
        except (ValueError, TypeError):
            continue
    
    print(f"Found {len(url_tags)} URLs in sitemap, {len(today_urls)} are from today")
    
    return {
        'total_urls': len(url_tags),
        'today_urls': today_urls
    }

# Task 4: Check existing URLs
def check_existing_urls():
    """Check which URLs have already been processed"""
    # Call the original function
    seen_urls = read_seen_urls(CSV_PATH)
    print(f"Found {len(seen_urls)} existing URLs in the database")
    
    return {
        'seen_urls': list(seen_urls)
    }

# Task 5: Extract content from articles
def extract_content(**context):
    """Extract content from today's articles"""
    result_parse = context['ti'].xcom_pull(task_ids='parse_sitemap')
    result_check = context['ti'].xcom_pull(task_ids='check_existing_urls')
    
    today_urls = result_parse['today_urls']
    seen_urls = set(result_check['seen_urls'])
    
    collected_data = []
    for loc, lastmod in today_urls:
        if loc in seen_urls:
            continue
            
        print(f"Processing article from today: {loc}")
        # Call the original extract function
        content, author = extract_article_content(loc)
        
        # Only add if content is not empty
        if content:
            collected_data.append((loc, lastmod, author, content))
    
    print(f"Processed {len(collected_data)} new articles")
    
    return {
        'collected_data': collected_data
    }

# Task 6: Save articles to CSV
def save_articles(**context):
    """Save the collected articles to CSV"""
    result = context['ti'].xcom_pull(task_ids='extract_content')
    collected_data = result['collected_data']
    
    if not collected_data:
        print("No new articles to save")
        return "No new articles saved"
    
    # Call the original save function
    save_to_csv(CSV_PATH, collected_data)
    
    print(f"Saved {len(collected_data)} articles to CSV: {CSV_PATH}")
    return f"Saved {len(collected_data)} articles"

# Task 7: Run database import
def run_database_import():
    """Run the database connection script with the CSV file"""
    # Get the full path to the connection.py file
    connection_path = os.path.join(project_dir, 'database', 'connection.py')
    
    # Set the environment variable
    os.environ['CRAWLER_CSV_PATH'] = CSV_PATH
    
    # Call the script using os.system or subprocess
    # This is simpler than the importlib approach
    import subprocess
    
    print(f"Running database import with: {connection_path}")
    result = subprocess.run(
        [sys.executable, connection_path, CSV_PATH],
        capture_output=True,
        text=True
    )
    
    print("Database stdout:", result.stdout)
    if result.stderr:
        print("Database stderr:", result.stderr)
    
    return "Database import completed"

# Define the tasks
task_setup = PythonOperator(
    task_id='setup_date_and_url',
    python_callable=setup_date_and_url,
    dag=dag,
)

task_fetch = PythonOperator(
    task_id='fetch_sitemap',
    python_callable=fetch_sitemap,
    provide_context=True,
    dag=dag,
)

task_parse = PythonOperator(
    task_id='parse_sitemap',
    python_callable=parse_sitemap,
    provide_context=True,
    dag=dag,
)

task_check = PythonOperator(
    task_id='check_existing_urls',
    python_callable=check_existing_urls,
    dag=dag,
)

task_extract = PythonOperator(
    task_id='extract_content',
    python_callable=extract_content,
    provide_context=True,
    dag=dag,
)

task_save = PythonOperator(
    task_id='save_articles',
    python_callable=save_articles,
    provide_context=True,
    dag=dag,
)

task_db = PythonOperator(
    task_id='run_database_import',
    python_callable=run_database_import,
    dag=dag,
)

# Set task dependencies
task_setup >> task_fetch >> task_parse
task_parse >> task_extract
task_check >> task_extract
task_extract >> task_save >> task_db 