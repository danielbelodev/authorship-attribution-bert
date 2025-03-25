from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import os
import sys

# Add the project directory to Python path
project_dir = os.path.expanduser('~/schule/diplomarbeit')
if project_dir not in sys.path:
    sys.path.append(project_dir)

# Import the modules (not just the functions)
import crawler.DerStandard_crawler_today as crawler_module
import database.connection as db_module

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
    'simple_article_workflow',
    default_args=default_args,
    description='Simple workflow that directly calls crawler and database functions',
    schedule_interval='0 0 * * *',  # Run daily at midnight
    catchup=False,
)

# Task 1: Run Crawler
def run_crawler(**context):
    """Run the crawler to fetch today's articles"""
    # Define the CSV path
    csv_path = os.path.join(project_dir, 'crawler', 'urls_today.csv')
    
    # Call the crawler function directly
    print(f"Starting crawler for today's articles at {datetime.now()}")
    articles = crawler_module.crawl_today_articles(csv_path=csv_path)
    
    # Pass the CSV path to the next task
    context['ti'].xcom_push(key='csv_path', value=csv_path)
    
    print(f"Crawler completed, found {len(articles)} articles")
    return f"Crawler completed and saved {len(articles)} articles to {csv_path}"

# Task 2: Process Database
def run_database_import(**context):
    """Run the database import process"""
    # Get the CSV path from the previous task
    csv_path = context['ti'].xcom_pull(task_ids='run_crawler', key='csv_path')
    
    # Set up environment to pass the CSV path
    os.environ['CRAWLER_CSV_PATH'] = csv_path
    
    # Call the module's main functionality directly
    # We need to temporarily modify sys.argv to pass the CSV path
    original_argv = sys.argv
    
    try:
        # Pass CSV path as command line argument
        if len(sys.argv) > 1:
            sys.argv[1] = csv_path
        else:
            sys.argv.append(csv_path)
            
        # Import and run the module
        print(f"Running database import with CSV file: {csv_path}")
        
        # Execute the module directly
        import importlib.util
        
        # Get the full path to the connection.py file
        connection_path = os.path.join(project_dir, 'database', 'connection.py')
        
        # Load the module spec
        spec = importlib.util.spec_from_file_location("connection_module", connection_path)
        module = importlib.util.module_from_spec(spec)
        
        # Execute the module
        spec.loader.exec_module(module)
        
        return "Database import completed"
    finally:
        # Restore original argv
        sys.argv = original_argv

# Define the tasks
crawler_task = PythonOperator(
    task_id='run_crawler',
    python_callable=run_crawler,
    provide_context=True,
    dag=dag,
)

db_task = PythonOperator(
    task_id='run_database_import',
    python_callable=run_database_import,
    provide_context=True,
    dag=dag,
)

# Set task dependencies
crawler_task >> db_task 