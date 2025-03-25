from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import os
import sys

# Add project directory to Python path
project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.append(project_dir)

# Try to import custom modules
try:
    from crawler.DerStandard_crawler_today import crawl_today_articles
    from database.connection import import_articles_from_csv
    import_successful = True
except ImportError as e:
    print(f"Warning: Could not import custom modules: {e}")
    import_successful = False

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
    description='Simple workflow for DerStandard article processing',
    schedule_interval='0 0 * * *',  # Run daily at midnight
    catchup=False,
)

def run_crawler(**context):
    """Run the crawler to fetch today's articles"""
    if not import_successful:
        print("Skipping crawler due to import failure")
        return None
        
    try:
        crawl_today_articles()
        return "Crawler completed successfully"
    except Exception as e:
        print(f"Error running crawler: {e}")
        return None

def run_database_import(**context):
    """Import articles from CSV to database"""
    if not import_successful:
        print("Skipping database import due to import failure")
        return None
        
    csv_path = os.path.join(project_dir, 'crawler', 'urls_today.csv')
    try:
        import_articles_from_csv(csv_path)
        return "Database import completed successfully"
    except Exception as e:
        print(f"Error importing to database: {e}")
        return None

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