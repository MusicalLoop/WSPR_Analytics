# WSPR_Analytics
**WSPR Analytics** is a standalone Python web application designed to retrieve WSPR (Weak Signal Propagation Reporter) data. You enter a Call Sign and time period, and it retrieves data from WSPR.live and displays it in a table for you to analyse. There is also an simple analyse option that provides some basic metrics.

Provides a user-friendly interface to configure parameters, retrieve data from wspr.live, and display the results in a tabular format.

## Features

- Bootstrap-based web interface with dark mode toggle
- Navigation menu with Configuration, Data, Analyse and Logs pages
- Configuration page with:
  - Transmitter Call Sign input (max 10 characters)
  - Time period selection (default: 30 minutes)
  - Top Stations - default 10: the number of top stations to display in the analysis page
- Provides a defauly configuration in WSPR_Analytics.ini
- Saves configuration to `WSPR_Analytics.conf` and reloads the last used entries
- Executes `WSPR_Analytics.py` to fetch data from wspr.live
- Saves data as `data/WSPR_Analytics.csv` - this provides a starting point for deeper analysis of your data
- Displays the latest CSV data in a table on the Data page
- Displays basic metrics on the Analysis page

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## Installation

1. Clone or download the repository
2. Create a virtual environment (optional)
3. Install dependencies:
   pip install flask requests

## Usage

1. Run the Flask app:
   python app.py

2. Open your browser and go to:
   http://127.0.0.1:5000

3. Use the Configuration page to enter your call sign and select a time period.
4. Click Submit to fetch data and view it on the Data page.
5. Click Analyse to display basic metrics.
