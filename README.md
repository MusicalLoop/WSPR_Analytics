# WSPR_Analytics

**WSPR Analytics** is a standalone Python web application designed to retrieve WSPR (Weak Signal Propagation Reporter) data. You enter a Call Sign and time period, and it retrieves data from WSPR.live and displays it in a table for you to analyze. There is also a simple analyze option that provides some basic metrics.

It provides a user-friendly interface to configure parameters, retrieve data from wspr.live, and display the results in a tabular format.

## Features

*   Bootstrap-based web interface with dark mode toggle.
*   Navigation menu with Configuration, Data, Analyze, and Logs pages.
*   **Configuration page with:**
    *   Transmitter Call Sign input (max 10 characters).
    *   Time period selection (default: 30 minutes).
    *   Top Stations input (default: 10) to control analysis depth.
*   Configuration persistence using `WSPR_Analytics.conf` and default fallback in `WSPR_Analytics.ini`.
*   Data retrieval from wspr.live using a backend process.
*   Executes `WSPR_Analytics.py` to fetch data from wspr.live.
*   **Data page displays the latest CSV data in a table.**
*   **Analysis page includes:**
    *   Summary metrics (total spots, unique spots, grid squares).
    *   Hourly distance analysis.
    *   Top call signs by frequency.
    *   Furthest stations by distance.
    *   Spot counts by country.
    *   Distance binning distribution.
*   Logs page shows application logs.

## Prerequisites

*   Python 3.8 or higher.
*   `pip` (Python package manager).

## Installation

1.  Clone or download the repository.
2.  (Optional) Create a Python virtual environment:
    ```bash
    python -m venv venv
    ```
    This creates a virtual environment named `venv` in your current directory.
3.  Activate your Python virtual environment:
    *   **Windows:**
        ```bash
        venv\Scripts\activate.bat
        ```
    *   **Linux/macOS:**
        ```bash
        source venv/bin/activate
        ```
4.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  Run the Flask application:
    ```bash
    python app.py
    ```
2.  Open your web browser and navigate to:
    ```
    http://127.0.0.1:5000
    ```
3.  Use the **Configuration** page to enter your call sign and select a time period.
4.  Click **Submit** to fetch data and view it on the **Data** page.
5.  Click **Analysis** to display basic metrics.

