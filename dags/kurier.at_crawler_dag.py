from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator

# Importiere die Funktion aus dem Webcrawling-Skript
from webcrawler import save_urls_to_csv

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2023, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'webcrawler_dag',
    default_args=default_args,
    description='Ein einfacher DAG für Webcrawling',
    schedule_interval='@monthly',  # Ausführung monatlich geplant
)

def save_task():
    save_urls_to_csv("/path/to/your/airflow/dags/urls.csv")

webcrawler_task = PythonOperator(
    task_id='run_webcrawler',
    python_callable=save_task,
    dag=dag,
)

webcrawler_task
