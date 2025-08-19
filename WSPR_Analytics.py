#####################################################################
##   Name:     WSPR_Analytics.py                                   ##
##   Author:   Andy Holmes: 2E0IJC                                 ##
##   Date:     19th August 2025                                    ##
#####################################################################
##   Summary:                                                      ##
##                                                                 ##
##   **WSPR Analytics** is a standalone Python web application     ##
##   designed to analyze WSPR (Weak Signal Propagation Reporter)   ##
##   data. It provides a user-friendly interface to configure      ##
##   parameters, retrieve data from wspr.live, and display the     ##
##   results in a tabular format.                                  ##
##                                                                 ##
#####################################################################
##   Version: 0.1  Original draft                                  ##
##                                                                 ##
#####################################################################

# -*- coding: utf-8 -*-
 
## Imports ##
import sys
import os
import csv
from io import StringIO
import requests
from datetime import datetime, timedelta
import logging
import pandas as pd


## Main Code ##
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)  # Ensure the log directory exists

LOG_FILE = os.path.join(LOG_DIR, "WSPR_Analytics.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

def parse_time_periodOld(period_str):
    mapping = {
        "10 minutes": timedelta(minutes=10),
        "30 minutes": timedelta(minutes=30),
        "1 hour": timedelta(hours=1),
        "3 hours": timedelta(hours=3),
        "6 hours": timedelta(hours=6),
        "12 hours": timedelta(hours=12),
        "24 hours": timedelta(hours=24),
        "48 hours": timedelta(hours=48),
        "72 hours": timedelta(hours=72)
    }
    return mapping.get(period_str, timedelta(minutes=30))
    
def parse_time_period(time_period_str):
    """Parse a time period string like '10 minutes' into a timedelta."""
    parts = time_period_str.split()
    number = int(parts[0])
    unit = parts[1]
    if unit.startswith("minute"):
        return timedelta(minutes=number)
    elif unit.startswith("hour"):
        return timedelta(hours=number)
    elif unit.startswith("day"):
        return timedelta(days=number)
    else:
        raise ValueError(f"Unknown time period unit: {unit}")

def getData(call_sign, time_period_str):
    logging.debug(f"Starting data fetch for Call Sign: {call_sign}, Time Period: {time_period_str}")
    try:
        delta = parse_time_period(time_period_str)
    except Exception as e:
        logging.error(f"Error parsing time period: {e}")
        return None, f"Error parsing time period: {e}"

    end_time = datetime.utcnow()
    start_time = end_time - delta
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
    query_url = (
        f"http://wspr.live/wspr_downloader.php?"
        f"start={start_str}&end={end_str}&tx_sign={call_sign}&rx_sign=%&format=CSV"
    )
    logging.debug(f"Query URL: {query_url}")
    try:
        response = requests.get(query_url)
        response.raise_for_status()
        logging.debug("Data fetched successfully from API.")
    except Exception as e:
        logging.error(f"Failed to fetch data: {e}")
        return None, f"Failed to fetch data: {e}"

    os.makedirs("data", exist_ok=True)
    filename = "data/WSPR_Analytics.csv"
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(response.text)
        logging.debug(f"Data saved to {filename}")
    except Exception as e:
        logging.error(f"Failed to save data to file: {e}")
        return None, f"Failed to save data to file: {e}"

    # Parse CSV and return as table data
    try:
        csv_file = StringIO(response.text)
        reader = csv.DictReader(csv_file)
        data_rows = list(reader)
        if not data_rows:
            return None, "No data returned for this period and call sign."
        return data_rows, None
    except Exception as e:
        logging.error(f"Failed to parse CSV: {e}")
        return None, f"Failed to parse CSV: {e}"


def analyseData(top_stations_count=10):
    try:
        #import pandas as pd
        #import logging

        # Load the CSV file
        df = pd.read_csv("data/WSPR_Analytics.csv")

        # Debug
        #logging.info("Head: {df.head()}")
        #logging.info("Columns: {df.columns}")
        #logging.info("Shape: {df.shape}")

        # Total number of spots using 'rx_sign'
        total_spots = df['rx_sign'].count()

        # Total number of unique spots using 'rx_sign'
        unique_spots = df['rx_sign'].nunique()

        # Unique grid squares using 'rx_loc'
        grid_6_digit = df['rx_loc'].nunique()
        grid_4_digit = df['rx_loc'].apply(lambda x: str(x)[:4]).nunique()

        # Distance binning
        num_bins = 8
        df['DistanceBin'] = pd.qcut(df['distance'], q=num_bins)
        bin_labels = [f"{int(interval.left)}-{int(interval.right)} km" for interval in df['DistanceBin'].cat.categories]
        df['DistanceBin'] = pd.qcut(df['distance'], q=num_bins, labels=bin_labels)
        distance_counts = df['DistanceBin'].value_counts().sort_index()
        distance_table = pd.DataFrame({
            "Distance Range": distance_counts.index,
            "Number of Spots": distance_counts.values
        })

        # Top stations by frequency and most common grid
        top_station_freq = (
            df.groupby('rx_sign')
            .agg(
                Count=('rx_sign', 'size'),
                Most_Common_Grid=('rx_loc', lambda x: x.mode().iloc[0] if not x.mode().empty else '')
            )
            .reset_index()
            .sort_values(by='Count', ascending=False)
            .head(top_stations_count)
        )

        # Furthest stations by distance (with their grid at max distance, and count)
        furthest_idx = df.groupby('rx_sign')['distance'].idxmax()
        furthest_spots = df.loc[furthest_idx, ['rx_sign', 'rx_loc', 'distance']]
        counts = df['rx_sign'].value_counts().reset_index()
        counts.columns = ['rx_sign', 'Count']
        furthest_stations = (
            furthest_spots
            .merge(counts, on='rx_sign')
            .sort_values(by='distance', ascending=False)
            .head(top_stations_count)
        )

        # Prepare summary text
        summary_text = (
            f"Total number of spots (rx_sign): {total_spots}\n"
            f"Total number of unique spots (rx_sign): {unique_spots}\n"
            f"Number of unique grid squares (4 digits from rx_loc): {grid_4_digit}\n"
            f"Number of unique grid squares (6 digits from rx_loc): {grid_6_digit}\n"
        )

        # Debug
        logging.debug(top_station_freq)
        logging.debug(furthest_stations)
        
        # Convert tables to lists of dicts for rendering in Jinja
        distance_table_list = distance_table.to_dict(orient="records")
        top_stations_list = top_station_freq.to_dict(orient="records")
        furthest_stations_list = furthest_stations.to_dict(orient="records")

        # Debug
        logging.debug(distance_table_list)
        logging.debug(top_stations_list)
        logging.debug(furthest_stations_list)

        logging.info("analyseData completed successfully.")
        return summary_text, distance_table_list, top_stations_list, furthest_stations_list, None
    except Exception as e:
        logging.error(f"Error in analyseData: {e}")
        return None, None, None, None, f"Error in analyseData: {e}"

def visualiseData():
    try:
        png_path = "static/visualisation.png"
        logging.info(f"visualiseData called. Expected PNG: {png_path}")
        # Simulate: generate PNG and return path
        if not os.path.exists(png_path):
            logging.warning(f"Expected PNG file does not exist: {png_path}")
        logging.info(f"visualiseData result: {png_path}")
        return png_path
    except Exception as e:
        logging.error(f"Error in visualiseData: {e}")
        return f"Error in visualiseData: {e}"