from datetime import datetime, timedelta, time
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
import os
import sys
import pandas as pd
from typing import List, Tuple, Set

# Add the project directory to Python path
project_dir = os.getenv('PROJECT_DIR', os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
if project_dir not in sys.path:
    sys.path.append(project_dir)

# Import functions directly
from crawler.DerStandard_crawler_today import extract_article_content, save_to_csv, read_seen_urls
from dateutil import parser

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
    'article_workflow',
    default_args=default_args,
    description='Detailed workflow for article crawling and processing',
    schedule_interval='0 0 * * *',  # Run daily at midnight
    catchup=False,
)

# Task 1: Setup paths and configuration
def setup_configuration(**context):
    """Initialize paths and configuration for the workflow"""
    # Define file paths
    csv_path = os.path.join(project_dir, 'crawler', 'urls_today.csv')
    
    # Get today's date
    today = datetime.now()
    today_date = today.date()
    
    # Create the sitemap URL for the current month
    sitemap_url = f"https://www.derstandard.at/sitemaps/sitemap-{today.year}-{today.month:02}.xml"
    
    # Store configuration in XCom
    context['ti'].xcom_push(key='csv_path', value=csv_path)
    context['ti'].xcom_push(key='today_date', value=today_date.isoformat())
    context['ti'].xcom_push(key='sitemap_url', value=sitemap_url)
    
    print(f"Setup complete: Processing articles for {today_date}")
    print(f"Using sitemap: {sitemap_url}")
    print(f"CSV will be saved to: {csv_path}")
    
    return "Configuration setup complete"

# Task 2: Read existing URLs to avoid duplicates
def read_existing_urls(**context):
    """Read existing URLs from the CSV file to avoid duplicates"""
    csv_path = context['ti'].xcom_pull(task_ids='setup_configuration', key='csv_path')
    
    # Call the original function
    seen_urls = read_seen_urls(csv_path)
    
    # Store in XCom
    context['ti'].xcom_push(key='seen_urls', value=list(seen_urls))
    
    print(f"Found {len(seen_urls)} existing URLs in the database")
    return f"Read {len(seen_urls)} existing URLs"

# Task 3: Fetch sitemap data
def fetch_sitemap(**context):
    """Fetch and parse the sitemap XML"""
    import requests
    from bs4 import BeautifulSoup
    
    sitemap_url = context['ti'].xcom_pull(task_ids='setup_configuration', key='sitemap_url')
    today_date_str = context['ti'].xcom_pull(task_ids='setup_configuration', key='today_date')
    today_date = datetime.fromisoformat(today_date_str).date()
    
    # Define cookies for GDPR compliance
    COOKIES = {'DSGVO_ZUSAGE_V1': 'true'}
    
    try:
        # Fetch the sitemap
        print(f"Fetching sitemap: {sitemap_url}")
        response = requests.get(sitemap_url, cookies=COOKIES)
        response.raise_for_status()
        
        # Parse the XML
        sitemap_content = response.content
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
        context['ti'].xcom_push(key='today_urls', value=today_urls)
        return f"Fetched {len(today_urls)} URLs from today"
        
    except requests.RequestException as e:
        print(f"Error fetching sitemap {sitemap_url}: {e}")
        return f"Error: {str(e)}"

# Task 4: Process articles (extract content)
def process_articles(**context):
    """Extract content from each article URL"""
    today_urls = context['ti'].xcom_pull(task_ids='fetch_sitemap', key='today_urls')
    seen_urls_list = context['ti'].xcom_pull(task_ids='read_existing_urls', key='seen_urls')
    seen_urls = set(seen_urls_list) if seen_urls_list else set()
    
    collected_data = []
    processed_count = 0
    
    for loc, lastmod in today_urls:
        if loc in seen_urls:
            continue
            
        print(f"Processing article from today: {loc}")
        content, author = extract_article_content(loc)
        
        # Only add to collected_data if content is not empty
        if content:
            collected_data.append((loc, lastmod, author, content))
            seen_urls.add(loc)
            processed_count += 1
    
    context['ti'].xcom_push(key='collected_data', value=collected_data)
    
    print(f"Processed {processed_count} new articles")
    return f"Extracted content from {processed_count} articles"

# Task 5: Save articles to CSV
def save_articles_to_csv(**context):
    """Save the collected article data to CSV"""
    collected_data = context['ti'].xcom_pull(task_ids='process_articles', key='collected_data')
    csv_path = context['ti'].xcom_pull(task_ids='setup_configuration', key='csv_path')
    
    if not collected_data:
        print("No new articles to save")
        return "No new articles saved"
    
    # Call the original save function
    save_to_csv(csv_path, collected_data)
    
    return f"Saved {len(collected_data)} articles to CSV"

# Task 6: Load CSV to pandas
def load_csv_to_pandas(**context):
    """Load the CSV file into a pandas DataFrame"""
    csv_path = context['ti'].xcom_pull(task_ids='setup_configuration', key='csv_path')
    
    try:
        df = pd.read_csv(csv_path)
        print(f"Successfully loaded {len(df)} rows from CSV")
        
        # Ensure correct column names
        if len(df.columns) == 4:
            df.columns = ["url", "lastmod", "author", "content"]
            
        # Store DataFrame as pickled object in XCom
        context['ti'].xcom_push(key='df_dict', value=df.to_dict())
        
        return f"Loaded {len(df)} rows from CSV"
    except Exception as e:
        print(f"Error loading CSV file {csv_path}: {e}")
        return f"Error: {str(e)}"

# Task 7: Parse and clean dates
def parse_and_clean_dates(**context):
    """Parse and clean the dates in the DataFrame"""
    df_dict = context['ti'].xcom_pull(task_ids='load_csv_to_pandas', key='df_dict')
    df = pd.DataFrame.from_dict(df_dict)
    
    if df.empty:
        return "No data to process"
    
    # Define date parsing function
    def parse_dates(date_str):
        try:
            return parser.parse(date_str)
        except Exception:
            return pd.NaT
    
    # Parse dates
    df['lastmod'] = df['lastmod'].apply(parse_dates)
    
    # Check for invalid dates
    nat_count = df['lastmod'].isna().sum()
    if nat_count > 0:
        print(f"Warning: Found {nat_count} invalid date values")
    
    # Fix datetime issues
    def fix_lastmod_datetime(dt):
        if pd.isnull(dt):
            return None
        try:
            if dt.hour is None or dt.minute is None or dt.second is None:
                return datetime.combine(dt.date(), time(0, 0, 0))
            return dt
        except:
            return None
    
    def round_up_to_next_second(dt):
        if pd.isnull(dt):
            return None
        return (dt + timedelta(seconds=1)).replace(microsecond=0) if dt.microsecond > 0 else dt
    
    # Apply date fixes
    df['lastmod'] = df['lastmod'].apply(fix_lastmod_datetime)
    df['lastmod'] = df['lastmod'].apply(round_up_to_next_second)
    df['lastmod'] = df['lastmod'].apply(lambda x: x.replace(microsecond=0) if pd.notnull(x) else x)
    
    # Remove timezone info
    df['lastmod'] = df['lastmod'].dt.tz_localize(None)
    
    # Limit author name length
    max_length = 255
    df['author'] = df['author'].apply(lambda x: x[:max_length] if isinstance(x, str) else x)
    
    # Convert timestamps to ISO format strings to make them JSON serializable
    df_serializable = df.copy()
    df_serializable['lastmod'] = df_serializable['lastmod'].apply(
        lambda x: x.isoformat() if pd.notnull(x) else None
    )
    
    # Store cleaned DataFrame with serializable dates
    context['ti'].xcom_push(key='cleaned_df_dict', value=df_serializable.to_dict())
    
    return f"Cleaned dates for {len(df)} rows"

# Task 8: Filter new articles
def filter_new_articles(**context):
    """Filter to only include articles not already in the database"""
    from sqlalchemy import create_engine, text
    
    df_dict = context['ti'].xcom_pull(task_ids='parse_and_clean_dates', key='cleaned_df_dict')
    df = pd.DataFrame.from_dict(df_dict)
    
    if df.empty:
        return "No data to filter"
    
    # Convert lastmod ISO strings back to datetime objects
    df['lastmod'] = pd.to_datetime(df['lastmod'])
    
    # Connect to database
    engine = create_engine(os.getenv("DB_URL", "mysql+mysqlconnector://root@localhost:33061/diplomarbeit"))
    
    with engine.connect() as connection:
        # Get the last inserted URL
        last_url = connection.execute(text("""
            SELECT url FROM articles ORDER BY id DESC LIMIT 1
        """)).fetchone()
        
        if last_url:
            last_url = last_url['url']
            df = df[df['url'] > last_url]
            
        # Filter out rows with NaT in lastmod
        df = df[df['lastmod'].notna()]
    
    # Convert timestamps back to ISO format strings for JSON serialization 
    df_serializable = df.copy()
    df_serializable['lastmod'] = df_serializable['lastmod'].apply(
        lambda x: x.isoformat() if pd.notnull(x) else None
    )
        
    context['ti'].xcom_push(key='filtered_df_dict', value=df_serializable.to_dict())
    
    if df.empty:
        print("No new articles to insert")
    else:
        print(f"Found {len(df)} new articles to insert")
        
    return f"Filtered to {len(df)} new articles"

# Task 9: Process authors
def process_authors(**context):
    """Process authors and get or create author IDs"""
    from sqlalchemy import create_engine, text
    
    df_dict = context['ti'].xcom_pull(task_ids='filter_new_articles', key='filtered_df_dict')
    df = pd.DataFrame.from_dict(df_dict)
    
    if df.empty:
        return "No authors to process"
    
    # Connect to database
    engine = create_engine(os.getenv("DB_URL", "mysql+mysqlconnector://root@localhost:33061/diplomarbeit"))
    
    author_ids = {}
    
    with engine.connect() as connection:
        # Process each unique author
        unique_authors = df['author'].unique()
        for author in unique_authors:
            # Check if author exists
            result = connection.execute(
                text("SELECT id FROM authors WHERE name = :name"),
                {'name': author}
            ).fetchone()
            
            if result:
                author_ids[author] = result['id']
            else:
                # Insert new author
                connection.execute(
                    text("INSERT INTO authors (name) VALUES (:name)"),
                    {'name': author}
                )
                # Get new author ID
                author_id = connection.execute(
                    text("SELECT id FROM authors WHERE name = :name"),
                    {'name': author}
                ).fetchone()['id']
                author_ids[author] = author_id
    
    context['ti'].xcom_push(key='author_ids', value=author_ids)
    
    return f"Processed {len(author_ids)} authors"

# Task 10: Insert articles
def insert_articles(**context):
    """Insert articles into the database"""
    from sqlalchemy import create_engine, text
    
    df_dict = context['ti'].xcom_pull(task_ids='filter_new_articles', key='filtered_df_dict')
    df = pd.DataFrame.from_dict(df_dict)
    author_ids = context['ti'].xcom_pull(task_ids='process_authors', key='author_ids')
    
    if df.empty:
        return "No articles to insert"
    
    # Convert lastmod ISO strings back to datetime objects
    df['lastmod'] = pd.to_datetime(df['lastmod'])
    
    # Connect to database
    engine = create_engine(os.getenv("DB_URL", "mysql+mysqlconnector://root@localhost:33061/diplomarbeit"))
    
    inserted_count = 0
    
    with engine.connect() as connection:
        for index, row in df.iterrows():
            # Get author ID
            author_id = author_ids.get(row['author'])
            
            # Insert article
            connection.execute(
                text("""
                    INSERT INTO articles (url, lastmod, content, author_id)
                    VALUES (:url, :lastmod, :content, :author_id)
                """),
                {
                    'url': row['url'],
                    'lastmod': row['lastmod'].strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(row['lastmod']) else None,
                    'content': row['content'],
                    'author_id': author_id
                }
            )
            inserted_count += 1
    
    print(f"Successfully inserted {inserted_count} articles")
    return f"Inserted {inserted_count} articles"

# Define all tasks
task_setup = PythonOperator(
    task_id='setup_configuration',
    python_callable=setup_configuration,
    provide_context=True,
    dag=dag,
)

task_read_urls = PythonOperator(
    task_id='read_existing_urls',
    python_callable=read_existing_urls,
    provide_context=True,
    dag=dag,
)

task_fetch_sitemap = PythonOperator(
    task_id='fetch_sitemap',
    python_callable=fetch_sitemap,
    provide_context=True,
    dag=dag,
)

task_process_articles = PythonOperator(
    task_id='process_articles',
    python_callable=process_articles,
    provide_context=True,
    dag=dag,
)

task_save_csv = PythonOperator(
    task_id='save_articles_to_csv',
    python_callable=save_articles_to_csv,
    provide_context=True,
    dag=dag,
)

task_load_csv = PythonOperator(
    task_id='load_csv_to_pandas',
    python_callable=load_csv_to_pandas,
    provide_context=True,
    dag=dag,
)

task_clean_dates = PythonOperator(
    task_id='parse_and_clean_dates',
    python_callable=parse_and_clean_dates,
    provide_context=True,
    dag=dag,
)

task_filter_articles = PythonOperator(
    task_id='filter_new_articles',
    python_callable=filter_new_articles,
    provide_context=True,
    dag=dag,
)

task_process_authors = PythonOperator(
    task_id='process_authors',
    python_callable=process_authors,
    provide_context=True,
    dag=dag,
)

task_insert_articles = PythonOperator(
    task_id='insert_articles',
    python_callable=insert_articles,
    provide_context=True,
    dag=dag,
)

# Set task dependencies
task_setup >> task_read_urls >> task_fetch_sitemap >> task_process_articles >> task_save_csv
task_save_csv >> task_load_csv >> task_clean_dates >> task_filter_articles >> task_process_authors >> task_insert_articles 