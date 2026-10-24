from datetime import datetime, timedelta
import os
import sys
import requests
import csv
from bs4 import BeautifulSoup
import pandas as pd
import mysql.connector
from airflow import DAG
from airflow.operators.python import PythonOperator

# Add project directory to Python path
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_dir)

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
    description='Detailed workflow for DerStandard article processing',
    schedule_interval='0 0 * * *',  # Run daily at midnight
    catchup=False,
)

def setup_date_and_url(**context):
    """Set up the date and URL for the workflow."""
    today = datetime.now().strftime('%Y-%m-%d')
    base_url = "https://www.derstandard.at/sitemap/"
    sitemap_url = f"{base_url}{today}.xml"
    context['task_instance'].xcom_push(key='sitemap_url', value=sitemap_url)
    context['task_instance'].xcom_push(key='date', value=today)
    return f"Setup completed for date: {today}"

def fetch_sitemap(**context):
    """Fetch the sitemap content."""
    sitemap_url = context['task_instance'].xcom_pull(task_ids='setup_date_and_url', key='sitemap_url')
    try:
        response = requests.get(sitemap_url)
        response.raise_for_status()
        context['task_instance'].xcom_push(key='sitemap_content', value=response.text)
        return "Sitemap fetched successfully"
    except Exception as e:
        raise Exception(f"Failed to fetch sitemap: {str(e)}")

def parse_sitemap(**context):
    """Parse the sitemap to extract URLs and last modification dates."""
    sitemap_content = context['task_instance'].xcom_pull(task_ids='fetch_sitemap', key='sitemap_content')
    soup = BeautifulSoup(sitemap_content, 'xml')
    urls = []
    lastmods = []
    
    for url in soup.find_all('url'):
        urls.append(url.loc.text)
        lastmods.append(url.lastmod.text if url.lastmod else None)
    
    context['task_instance'].xcom_push(key='urls', value=urls)
    context['task_instance'].xcom_push(key='lastmods', value=lastmods)
    return f"Parsed {len(urls)} URLs from sitemap"

def check_existing_urls(**context):
    """Check which URLs already exist in the database."""
    urls = context['task_instance'].xcom_pull(task_ids='parse_sitemap', key='urls')
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=os.getenv("DB_PASSWORD", ""),
            database="diplomarbeit",
            port=33061
        )
        cursor = conn.cursor()
        
        # Get existing URLs
        cursor.execute("SELECT url FROM articles")
        existing_urls = {row[0] for row in cursor.fetchall()}
        
        # Find new URLs
        new_urls = [url for url in urls if url not in existing_urls]
        
        context['task_instance'].xcom_push(key='new_urls', value=new_urls)
        return f"Found {len(new_urls)} new URLs to process"
    except Exception as e:
        raise Exception(f"Database check failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

def extract_content(**context):
    """Extract content from new URLs."""
    new_urls = context['task_instance'].xcom_pull(task_ids='check_existing_urls', key='new_urls')
    articles = []
    
    for url in new_urls:
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract article details
            title = soup.find('h1').text.strip() if soup.find('h1') else ''
            content = ' '.join([p.text.strip() for p in soup.find_all('p')])
            date = soup.find('time')['datetime'] if soup.find('time') else ''
            
            articles.append({
                'url': url,
                'title': title,
                'content': content,
                'date': date
            })
        except Exception as e:
            print(f"Error processing {url}: {str(e)}")
            continue
    
    context['task_instance'].xcom_push(key='articles', value=articles)
    return f"Extracted content from {len(articles)} articles"

def save_articles(**context):
    """Save extracted articles to CSV file."""
    articles = context['task_instance'].xcom_pull(task_ids='extract_content', key='articles')
    date = context['task_instance'].xcom_pull(task_ids='setup_date_and_url', key='date')
    
    if not articles:
        # Create an empty CSV file to maintain the workflow
        csv_file = f"articles_{date}.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['url', 'title', 'content', 'date'])
            writer.writeheader()
        context['task_instance'].xcom_push(key='csv_file', value=csv_file)
        return "No articles to save, created empty CSV file"
    
    csv_file = f"articles_{date}.csv"
    try:
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['url', 'title', 'content', 'date'])
            writer.writeheader()
            writer.writerows(articles)
        
        context['task_instance'].xcom_push(key='csv_file', value=csv_file)
        return f"Saved {len(articles)} articles to {csv_file}"
    except Exception as e:
        raise Exception(f"Failed to save articles to CSV: {str(e)}")

def run_database_import(**context):
    """Import articles from CSV file into MySQL database."""
    csv_file = context['task_instance'].xcom_pull(task_ids='save_articles', key='csv_file')
    
    if not csv_file:
        raise Exception("No CSV file path found in XCom")
    
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=os.getenv("DB_PASSWORD", ""),
            database="diplomarbeit",
            port=33061
        )
        cursor = conn.cursor()
        
        # Read CSV file
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row_count = 0
            for row in reader:
                # Insert article into database
                cursor.execute("""
                    INSERT INTO articles (url, title, content, date)
                    VALUES (%s, %s, %s, %s)
                """, (row['url'], row['title'], row['content'], row['date']))
                row_count += 1
        
        conn.commit()
        return f"Successfully imported {row_count} articles"
    except Exception as e:
        raise Exception(f"Database import failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

# Define the tasks
setup_task = PythonOperator(
    task_id='setup_date_and_url',
    python_callable=setup_date_and_url,
    provide_context=True,
    dag=dag,
)

fetch_task = PythonOperator(
    task_id='fetch_sitemap',
    python_callable=fetch_sitemap,
    provide_context=True,
    dag=dag,
)

parse_task = PythonOperator(
    task_id='parse_sitemap',
    python_callable=parse_sitemap,
    provide_context=True,
    dag=dag,
)

# Add new tasks
check_task = PythonOperator(
    task_id='check_existing_urls',
    python_callable=check_existing_urls,
    provide_context=True,
    dag=dag,
)

extract_task = PythonOperator(
    task_id='extract_content',
    python_callable=extract_content,
    provide_context=True,
    dag=dag,
)

# Add final tasks
save_task = PythonOperator(
    task_id='save_articles',
    python_callable=save_articles,
    provide_context=True,
    dag=dag,
)

import_task = PythonOperator(
    task_id='run_database_import',
    python_callable=run_database_import,
    provide_context=True,
    dag=dag,
)

# Update task dependencies
setup_task >> fetch_task >> parse_task >> check_task >> extract_task >> save_task >> import_task 