from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import os
import sys

# Add the project directory to Python path
project_dir = os.path.expanduser('~/schule/diplomarbeit')
if project_dir not in sys.path:
    sys.path.append(project_dir)

# Import functions directly from modules
from crawler.DerStandard_crawler import crawl_sitemap

# Default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Define the DAG
dag = DAG(
    'article_crawler',
    default_args=default_args,
    description='Crawl all articles and load to database',
    schedule_interval='0 0 * * 0',  # Run weekly on Sunday at midnight
    start_date=datetime(2023, 1, 1),
    catchup=False,
)

def run_crawler(**context):
    """Execute the crawler function directly from the crawler module"""
    # Define CSV path
    csv_path = os.path.join(project_dir, 'crawler', 'urls.csv')
    
    # Call the crawler function directly
    print(f"Starting full article crawler at {datetime.now()}")
    
    # Set up the sitemap URLs - from January of start_year to current date
    current_year = datetime.now().year
    current_month = datetime.now().month
    start_year = 2023
    
    collected_data = []
    for year in range(start_year, current_year + 1):
        for month in range(1, 13):
            if year == current_year and month > current_month:
                break
            sitemap_url = f"https://www.derstandard.at/sitemaps/sitemap-{year}-{month:02}.xml"
            print(f"Crawling sitemap: {sitemap_url}")
            data = crawl_sitemap(sitemap_url)
            collected_data.extend(data)
    
    # Store the csv path for the next task
    context['ti'].xcom_push(key='csv_file_path', value=csv_path)
    
    print(f"Crawler collected {len(collected_data)} articles total")
    return f"Crawler completed, saved to {csv_path}"

def run_db_connection(**context):
    """Execute the database connection script with the CSV path"""
    # Get CSV file path from previous task
    csv_file = context['ti'].xcom_pull(task_ids='crawl_articles', key='csv_file_path')
    
    # We'll use sys.argv hack to pass the CSV path to the connection script
    # Save original argv
    original_argv = sys.argv.copy()
    
    try:
        # Set sys.argv[1] to the CSV path
        if len(sys.argv) > 1:
            sys.argv[1] = csv_file
        else:
            sys.argv.append(csv_file)
        
        # Set environment variable as alternative way to pass the CSV path
        os.environ['CRAWLER_CSV_PATH'] = csv_file
        
        print(f"Running database connection with CSV file: {csv_file}")
        
        # Run the module directly - this will execute its main code
        # We use the importlib approach to "run" the module
        import importlib
        import importlib.util
        
        # Get the full path to the connection.py file
        connection_path = os.path.join(project_dir, 'database', 'connection.py')
        
        # Load the module spec
        spec = importlib.util.spec_from_file_location("connection_module", connection_path)
        module = importlib.util.module_from_spec(spec)
        
        # Execute the module
        spec.loader.exec_module(module)
        
        return "Database connection completed"
    
    finally:
        # Restore original argv
        sys.argv = original_argv

# Define the tasks
crawl_task = PythonOperator(
    task_id='crawl_articles',
    python_callable=run_crawler,
    provide_context=True,
    dag=dag,
)

db_task = PythonOperator(
    task_id='load_to_database',
    python_callable=run_db_connection,
    provide_context=True,
    dag=dag,
)

# Set task dependencies
crawl_task >> db_task