from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import os
import sys
import subprocess

# Define the absolute paths to the scripts
PROJECT_DIR = os.getenv('PROJECT_DIR', os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
CRAWLER_SCRIPT = os.path.join(PROJECT_DIR, 'crawler', 'DerStandard_crawler_today.py')
CONNECTION_SCRIPT = os.path.join(PROJECT_DIR, 'database', 'connection.py')

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
    description='Crawl articles and load to database',
    schedule_interval='0 0 * * *',  # Run daily at midnight (cron syntax)
    start_date=datetime(2023, 1, 1),
    catchup=False,
)

def run_crawler(**context):
    """Execute the crawler script"""
    result = subprocess.run([sys.executable, CRAWLER_SCRIPT], 
                          capture_output=True, 
                          text=True,
                          cwd=os.path.dirname(CRAWLER_SCRIPT))  # Set working directory to crawler directory
    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)
    return "Crawler completed"

def run_db_connection(**context):
    """Execute the database connection script"""
    result = subprocess.run([sys.executable, CONNECTION_SCRIPT], 
                          capture_output=True, 
                          text=True,
                          cwd=os.path.dirname(CONNECTION_SCRIPT))  # Set working directory to database directory
    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)
    return "Database connection completed"

# Define the tasks
crawl_task = PythonOperator(
    task_id='crawl_articles',
    python_callable=run_crawler,
    dag=dag,
)

db_task = PythonOperator(
    task_id='load_to_database',
    python_callable=run_db_connection,
    dag=dag,
)

# Set task dependencies
crawl_task >> db_task