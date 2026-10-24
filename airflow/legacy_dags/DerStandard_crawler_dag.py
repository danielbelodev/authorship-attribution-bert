from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.utils.dates import days_ago
from datetime import datetime
import subprocess

# Funktion zum Ausführen des allround_crawler.py
def run_crawler():
    subprocess.run(["python3", "/path/to/your/allround_crawler.py"], check=True)

# Funktion zum Ausführen des csv_to_db.py
def run_csv_to_db():
    subprocess.run(["python3", "/path/to/your/csv_to_db.py"], check=True)

# Definiere den DAG
dag = DAG(
    'derstandard_crawler_dag',
    default_args={'start_date': days_ago(1)},  # Startdatum ist einen Tag zurück
    schedule_interval='0 0 * * *',  # Jeden Tag um 0 Uhr
    catchup=False  # Verpasste DAG-Läufe nicht nachholen
)

# Task 1: Webcrawler ausführen
run_crawler_task = PythonOperator(
    task_id='run_allround_crawler',
    python_callable=run_crawler,
    dag=dag
)

# Task 2: CSV in die Datenbank übertragen
run_csv_to_db_task = PythonOperator(
    task_id='run_csv_to_db',
    python_callable=run_csv_to_db,
    dag=dag
)

# Setze die Abhängigkeit: Task 2 nach Task 1
run_crawler_task >> run_csv_to_db_task