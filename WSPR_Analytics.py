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

# -*- coding: utf-8 -*-
 
## Imports ##
import sys
import os
import csv
from io import StringIO
import requests
from datetime import datetime, timedelta
import logging
from logging.handlers import TimedRotatingFileHandler
import pandas as pd
from pyhamtools import Callinfo, LookupLib
import numpy as np

## Constants ##

DATA_DIR         = "data"
RESOURCES_DIR    = "resources" 
LOG_DIR          = "logs"

DATAFILE_NAME    = "WSPR_Analytics"
SUMMARY_NAME     = "WSPR_Summary"
BINNING_NAME     = "WSPR_Graph"
LOG_BINNING_NAME = "WSPR_LogGraph"
HOURLY_NAME      = "WSPR_Hourly"
DISTANCES_NAME   = "WSPR_Distances"
CALLSIGNS_NAME   = "WSPR_CallSigns"
COUNTRIES_NAME   = "WSPR_Countries"

FMT_TEXT    = "txt"
FMT_CSV     = "csv"
FMT_JSON    = "json"

CTY_FILE = os.path.join(RESOURCES_DIR, "cty.plist")

## Main Code ##

os.makedirs(LOG_DIR, exist_ok=True)        # Ensure the log directory exists
os.makedirs(RESOURCES_DIR, exist_ok=True)  # Ensure the resources directory exists
os.makedirs(DATA_DIR, exist_ok=True)       # Ensure the data directory exists

LOG_FILE = os.path.join(LOG_DIR, "WSPR_Analytics.log")


# Create a formatter
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

# Create a TimedRotatingFileHandler for daily rotation
# 'when'='midnight' rotates at midnight every day
# 'backupCount'=3 keeps 3 previous log files (plus the current one)
file_handler = TimedRotatingFileHandler(
    filename=LOG_FILE,
    when='midnight',
    interval=1,  # Rotate every day
    backupCount=3,
    encoding='utf-8' # Specify encoding for the log file
)
file_handler.setFormatter(formatter)

# Create a StreamHandler for console output
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

# Get the root logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)  # Set the logging level

# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(stream_handler)


    
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



def saveData(data, filename, directory="data", format="csv", **kwargs):
    """
    Saves data to a specified file in the given directory and format.

    Args:
        data: The data to save. Can be a Pandas DataFrame, a list of dictionaries,
              or other data types that can be serialized to the specified format.
        filename (str): The name of the file to save the data to (e.g., "summary").
        directory (str, optional): The directory where the file will be saved.
                                   Defaults to "data".
        format (str, optional): The format to save the data in ("csv", "json", "txt").
                                Defaults to "csv".
        **kwargs: Additional keyword arguments to pass to the underlying
                  saving function (e.g., index=False for DataFrames).
    """
    os.makedirs(directory, exist_ok=True)  # Create directory if it doesn't exist
    file_path = os.path.join(directory, f"{filename}.{format}")

    try:
        if format == "csv":
            if isinstance(data, pd.DataFrame):
                data.to_csv(file_path, **kwargs)
                logger.debug(f"DataFrame successfully saved to CSV: {file_path}")
            elif isinstance(data, list) and all(isinstance(d, dict) for d in data):
                # If it's a list of dictionaries, convert to DataFrame first for easier CSV saving
                pd.DataFrame(data).to_csv(file_path, **kwargs)
                logger.debug(f"List of dictionaries converted to DataFrame and saved to CSV: {file_path}")
            else:
                # Handle other iterable data as simple rows in CSV
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(data)
                logger.debug(f"Generic data saved to CSV: {file_path}")

        elif format == "json":
            if isinstance(data, pd.DataFrame):
                data.to_json(file_path, orient="records", indent=4, **kwargs) # orient="records" is common for list of dicts JSON
                logger.debug(f"DataFrame successfully saved to JSON: {file_path}")
            else:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, **kwargs)
                logger.debug(f"Data successfully saved to JSON: {file_path}")

        elif format == "txt":
            with open(file_path, "w", encoding="utf-8") as f:
                if isinstance(data, list):
                    for item in data:
                        f.write(str(item) + "\n")
                else:
                    f.write(str(data))
            logger.debug(f"Data successfully saved to TXT: {file_path}")

        else:
            logger.warning(f"Unsupported format: {format}. Data not saved.")
            return False, f"Unsupported format: {format}. Data not saved."
        
        return True, None

    except Exception as e:
        logger.error(f"Failed to save data to {file_path}: {e}")
        return False, f"Failed to save data to {file_path}: {e}"



def getData(call_sign, time_period_str):
    logger.debug(f"Starting data fetch for Call Sign: {call_sign}, Time Period: {time_period_str}")
    try:
        delta = parse_time_period(time_period_str)
    except Exception as e:
        logger.error(f"Error parsing time period: {e}")
        return None, f"Error parsing time period: {e}"

    end_time = datetime.utcnow()
    start_time = end_time - delta
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
    query_url = (
        f"http://wspr.live/wspr_downloader.php?"
        f"start={start_str}&end={end_str}&tx_sign={call_sign}&rx_sign=%&format=CSV"
    )
    logger.debug(f"Query URL: {query_url}")
    try:
        response = requests.get(query_url)
        response.raise_for_status()
        logger.debug("Data fetched successfully from API.")
    except Exception as e:
        logger.error(f"Failed to fetch data: {e}")
        return None, f"Failed to fetch data: {e}"

    saveData(response.text, DATAFILE_NAME, DATA_DIR, FMT_CSV)
    
    # Parse CSV and return as table data
    try:
        csv_file = StringIO(response.text)
        reader = csv.DictReader(csv_file)
        data_rows = list(reader)
        if not data_rows:
            return None, "No data returned for this period and call sign."
        return data_rows, None
    except Exception as e:
        logger.error(f"Failed to parse CSV: {e}")
        return None, f"Failed to parse CSV: {e}"
   
def getSummary(Data):

    # Total number of spots using 'rx_sign'
    
    logger.debug("getSummary")
    
    total_spots = Data['rx_sign'].count()

    logger.debug(f"Total Spots: {total_spots}")
    
    # Total number of unique spots using 'rx_sign'
    unique_spots = Data['rx_sign'].nunique()
    
    logger.debug(f"Total Unique Spots: {unique_spots}")
    
    # Unique grid squares using 'rx_loc'
    grid_6_digit = Data['rx_loc'].nunique()
    grid_4_digit = Data['rx_loc'].apply(lambda x: str(x)[:4]).nunique()


    summary_list = [
        {"label": "Total spots", "value": total_spots},
        {"label": "Total unique spots", "value": unique_spots},
        {"label": "Total unique grid squares (4 digits)", "value": grid_4_digit},
        {"label": "Total unique grid squares (6 digits)", "value": grid_6_digit}
    ]


    saveData(summary_list, SUMMARY_NAME, DATA_DIR, FMT_CSV)
	
    return summary_list
	

def getDistantCallSigns(Data):

    # Analyse and find the Call Signs furthest away.
    
    logger.debug("getDistantCallSigns")
    
    furthest_idx = Data.groupby('rx_sign')['distance'].idxmax()

    furthest_spots = Data.loc[furthest_idx, ['rx_sign', 'rx_loc', 'distance']]

    counts = Data['rx_sign'].value_counts().reset_index()

    counts.columns = ['rx_sign', 'Count']

    furthest_stations = (
        furthest_spots
        .merge(counts, on='rx_sign')
        .sort_values(by='distance', ascending=False)
    )

    logger.debug("getDistances: {furthest_stations}")
    
    saveData(furthest_stations, DISTANCES_NAME, DATA_DIR, FMT_CSV)
    
    return furthest_stations

def getCallSignCount(Data):

    # Top Call Signs by frequency  - including Grid Reference

    logger.debug("getCallSignCount")
    
    callSign_count= (
        Data.groupby('rx_sign')
        .agg(
            Count=('rx_sign', 'size'),
            gridRef=('rx_loc', lambda x: x.mode().iloc[0] if not x.mode().empty else '')
        )
        .reset_index()
        .sort_values(by='Count', ascending=False)
    )
    
    logger.debug(f"getCallSigns: {callSign_count}")
    
    saveData(callSign_count, CALLSIGNS_NAME, DATA_DIR, FMT_CSV)

    return callSign_count
        

def get_country_safely(callsign, callinfo_obj):
    if not callsign:
        return 'Unknown'
    try:
        call_data = callinfo_obj.get_all(callsign)
        return call_data.get('country', 'Unknown')
    except KeyError: # Catch KeyError, as this is what get_all raises for undecodable callsigns
        return 'Unknown'
        
def getCountries(Data):
    # Use Call Sign to get the Country, and then list the Countries and number of spots
    
    logger.debug(f"getCountries: City File: {CTY_FILE}")

    # Check if the local file exists before trying to use it
    if os.path.exists(CTY_FILE):
        lookup = LookupLib(lookuptype="countryfile", filename=CTY_FILE)
        logger.debug(f"Using local country file: {CTY_FILE}")
    else:
        logger.debug(f"Local country file not found at {CTY_FILE}. Attempting to download.")
        lookup = LookupLib(lookuptype="countryfile") # This will download from the internet
        logger.debug("Downloaded country file from the internet.")

    callInfo = Callinfo(lookup)


    # Add country column
    Data['country'] = Data['rx_sign'].apply(lambda call: get_country_safely(call, callInfo))

    # Create country spot count table
    country_counts = Data['country'].value_counts().reset_index()
    country_counts.columns = ['Country', 'Spots']
    country_counts = country_counts.sort_values(by='Spots', ascending=False)

    saveData(country_counts, COUNTRIES_NAME, DATA_DIR, FMT_CSV)
    return country_counts

def frequencyBinning(Data, num_bins=8):

    logger.debug("frequencyBinning")
    
    # Distance binning using pd.qcut for equal frequency bins
    logger.debug(f"frequencyBinning: Number of Bins: {num_bins}")

    Data['FrequencyBin'] = pd.qcut(Data['distance'], q=num_bins)

    bin_labels = [f"{int(interval.left)}-{int(interval.right)} km" for interval in Data['FrequencyBin'].cat.categories]

    Data['FrequencyBin'] = pd.qcut(Data['distance'], q=num_bins, labels=bin_labels)

    distance_counts = Data['FrequencyBin'].value_counts().sort_index()

    distance_table = pd.DataFrame({
        "Distance Range": distance_counts.index,
        "Number of Spots": distance_counts.values
    })
    
    logger.debug(f"FrequencyBin: {distance_table}")
    
    saveData(distance_table, BINNING_NAME, DATA_DIR, FMT_CSV)
    return distance_table

def logarithmicBinning(Data, num_bins=8): # Can use qcut or cut on log-transformed data

    logger.debug("logarithmicBinning")
    logger.debug(f"logarithmicBinning: Number of Bins: {num_bins}")

    # Apply logarithmic transformation (using log1p to handle distance = 0 if any)
    Data['distance_log'] = np.log1p(Data['distance']) # log(1+x)

    # Now apply equal-width binning to the log-transformed data
    # Use pd.cut to create bins of equal width in the log-space
    # You can also use pd.qcut on the log-transformed data if you want equal frequency in log-space
    log_min = Data['distance_log'].min()
    log_max = Data['distance_log'].max()
    log_bins = np.linspace(log_min, log_max, num_bins + 1)
    
    Data['DistanceBin_Log'] = pd.cut(Data['distance_log'], bins=log_bins, right=False)

    # Re-convert bin edges back to original km scale for labels
    bin_labels = []
    for interval in Data['DistanceBin_Log'].cat.categories:
        lower = np.expm1(interval.left) # exp(x)-1 to reverse log1p
        upper = np.expm1(interval.right)
        bin_labels.append(f"{int(lower)}-{int(upper)} km")
    
    Data['DistanceBin_Log'] = pd.cut(Data['distance_log'], bins=log_bins, right=False, labels=bin_labels)

    distance_counts = Data['DistanceBin_Log'].value_counts().sort_index()
    distance_table = pd.DataFrame({
        "Distance Range": distance_counts.index,
        "Number of Spots": distance_counts.values
    })
    
    logger.debug(f"logarithmicBinning: {distance_table}")
    
    saveData(distance_table, LOG_BINNING_NAME, DATA_DIR, FMT_CSV)
    
    return distance_table


def getDistanceByHour(Data):

    logger.debug("getDistanceByHour")

    Data['Time'] = pd.to_datetime(Data['time'], format="%Y-%m-%d %H:%M:%S")

    # Set 'Time' as the DataFrame's index for resampling
    Data = Data.set_index('Time')

    # Define the date range for the data
    start_date = Data.index.min().floor('D')
    end_date = Data.index.max().ceil('D') - pd.Timedelta(seconds=1)

    # Create a complete hourly time range for the period
    full_time_range = pd.date_range(start=start_date, end=end_date, freq='h')

    # Resample the data by hour, calculate mean, min, max, and count of 'distance'
    daily_hourly_stats = Data['distance'].resample('h').agg(['mean', 'min', 'max', 'count'])

    # Reindex the DataFrame to ensure all hours within the date range are present
    daily_hourly_stats = daily_hourly_stats.reindex(full_time_range)

    # Rename the 'count' column for clarity (e.g., 'Spots')
    daily_hourly_stats = daily_hourly_stats.rename(columns={'count': 'Spots'})

    # Drop rows that contain any NaN values (i.e., hours with no data)
    daily_hourly_stats = daily_hourly_stats.dropna()
    
    # Reset the index, which will move the current index (the datetime objects) into a new column.
    # By default, this column is named 'index'.
    daily_hourly_stats = daily_hourly_stats.reset_index()

    # Rename the columns to start with uppercase as requested
    daily_hourly_stats = daily_hourly_stats.rename(columns={
        'index': 'Time',  # Renames the column previously 'index' to 'Time'
        'mean': 'Mean',
        'min': 'Min',
        'max': 'Max'
    })

    # Round Mean
    daily_hourly_stats['Mean'] = daily_hourly_stats['Mean'].round(2)
    
    # Convert 'Min', 'Max', and 'Spots' to integers
    daily_hourly_stats['Min'] = daily_hourly_stats['Min'].astype(int)
    daily_hourly_stats['Max'] = daily_hourly_stats['Max'].astype(int)
    daily_hourly_stats['Spots'] = daily_hourly_stats['Spots'].astype(int) 
    
    logger.debug(f"getDistanceByHour: {daily_hourly_stats}")
    
    # Log the type of daily_hourly_stats here
    logger.debug(f"Type of daily_hourly_stats before saving: {type(daily_hourly_stats)}")
    
    saveData(daily_hourly_stats, HOURLY_NAME, DATA_DIR, FMT_CSV)

    # Convert DataFrame to a list of dictionaries for Jinja2 template rendering
    hourly_list_for_template = daily_hourly_stats.to_dict('records')

    # Log the type of hourly_list_for_template here
    logger.debug(f"Type of hourly_list_for_template (after conversion): {type(hourly_list_for_template)}")

    logger.debug(f"Returning data for template: {hourly_list_for_template}")

    return hourly_list_for_template


def analyseData(number_of_bins=8):

    logger.debug("analyseData")
    
    try:

        # Load the CSV file
        logger.debug("analyseData: Loading CSV file")
        
        file_path = os.path.join(DATA_DIR, f"{DATAFILE_NAME}.{FMT_CSV}") 

        logger.debug(f"analyseData: File Path: {file_path}")

        df = pd.read_csv(file_path) 

        logger.debug("analyseData: File Read")
        logger.debug(f"DataFrame Columns: {df.columns.tolist()}")

        summaryData   = getSummary(df)
        freqBins      = frequencyBinning(df, number_of_bins)
        logBins       = logarithmicBinning(df, number_of_bins)
        distanceData  = getDistantCallSigns(df)
        callSignData  = getCallSignCount(df)
        countryData   = getCountries(df)
        hourlyList    = getDistanceByHour(df)
        
        # Convert tables to lists of dicts for rendering in Jinja
        freqBinList     = freqBins.to_dict(orient="records")
        logBinList      = logBins.to_dict(orient="records")
        callSignList    = callSignData.to_dict(orient="records")
        distanceList    = distanceData.to_dict(orient="records")
        countryList     = countryData.to_dict(orient="records")
        
        logger.debug("analyseData: hourlyList")
        #hourlyList      = hourlyData.to_dict(orient="records")

        # Debug
        #logger.debug(f"Summary metrics: {summaryData}")
        #logger.debug(f"Distance (Frequency Binning): {freqBinList}")
        #logger.debug(f"Distance (Logarithmic Binning): {logBinList}")
        #logger.debug(f"Call Sign List: {callSignList}")
        #logger.debug(f"Distance List: {distanceList}")
        #logger.debug(f"Country List: {countryList}")
        #logger.debug(f"Hourly Stats: {hourlyData}")

        logger.info("analyseData completed successfully.")

        return summaryData, freqBinList, logBinList, callSignList, distanceList, countryList, hourlyList, None
    except Exception as e:
        logger.error(f"Error in analyseData: {e}")
        return None, None, None, None, None, None, None, f"Error in analyseData: {e}"



def visualiseData():
    try:
        png_path = "static/visualisation.png"
        logger.info(f"visualiseData called. Expected PNG: {png_path}")
        # Simulate: generate PNG and return path
        if not os.path.exists(png_path):
            logger.warning(f"Expected PNG file does not exist: {png_path}")
        logger.info(f"visualiseData result: {png_path}")
        return png_path
    except Exception as e:
        logger.error(f"Error in visualiseData: {e}")
        return f"Error in visualiseData: {e}"