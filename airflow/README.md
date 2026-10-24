# Article Crawler Airflow DAG

This repository contains an Apache Airflow DAG that automates the process of crawling articles from derstandard.at and loading them into a MySQL database.

## Overview

The DAG consists of two main tasks:
1. **Crawl Articles**: Scrapes article content from derstandard.at sitemaps and saves to a CSV file
2. **Load to Database**: Processes the CSV data and loads it into a MySQL database

## Setup Instructions

### Prerequisites
- Apache Airflow installed and configured
- Python 3.6+ with the following packages:
  - pandas
  - sqlalchemy
  - mysql-connector-python
  - requests
  - beautifulsoup4
  - lxml (for XML parsing)

### Database Setup
1. Ensure you have a MySQL database named `diplomarbeit` running
2. The database should have the following tables:
   - `authors` with columns: `id` (primary key), `name`
   - `articles` with columns: `id` (primary key), `url`, `lastmod`, `content`, `author_id` (foreign key to authors.id)

### Installation Steps
1. Place the `article_crawler_dag.py` file in your Airflow DAGs folder
2. Ensure your Airflow environment has all the required dependencies installed
3. Start/restart your Airflow webserver and scheduler
4. The DAG should appear in the Airflow UI

## Usage

1. Access the Airflow webserver UI (typically at http://localhost:8080)
2. Locate the `article_crawler` DAG in the DAGs list
3. Enable the DAG by toggling the switch
4. The DAG will run automatically according to the schedule (daily)
5. For a manual run, use the "Trigger DAG" button

## Configuration

You can modify the following parameters in the DAG file:
- `schedule_interval`: How often the DAG runs (default: daily)
- `days_back`: How many days back to look for articles (default: 30)
- Database connection string: Update as per your MySQL configuration
- CSV file path: Default is `urls.csv` in the parent directory of the DAGs folder

## Monitoring

- View task execution status in the Airflow UI
- Check task logs for detailed information about each run
- Task return values will show summary statistics about articles crawled and inserted 