## WSPR Analytics
WSPR Analytics is a standalone Python web application designed to analyze WSPR (Weak Signal Propagation Reporter) data. It provides a user-friendly interface to configure parameters, retrieve data from wspr.live, and display results in a tabular format.

## Features
Web interface built with Flask
Configuration management with .ini and .conf files
Data retrieval from WSPR API
Analysis of signal propagation including:
Spot counts
Grid square statistics
Distance binning
Top and furthest stations
Dark mode toggle
Log viewer

---

## Project Structure
>
>|-- app.py                # Flask web app
>
>|-- WSPR_Analytics.py     # Data processing and analysis logic
>
>|-- requirements.txt        # Python dependencies
>
>|-- static/                 # Static files (e.g., visualisation.png)
>
>|-- templates/              # HTML templates
>
>|-- logs/                   # Log files
>
>|-- data/                   # Downloaded CSV data
>

---

## Requirements
The following Python packages are used:

>csv
>
>datetime
>
>flask
>
>logging
>
>os
>
>pandas
>
>requests
>
>sys
>

---

### Installation
1. Clone the repository
git clone https://github.com/yourusername/wspr-analytics.git
cd wspr-analytics
2. Create a virtual environment (optional but recommended)

   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

3. Install dependencies

   pip install -r requirements.txt

4. Run the application

   python "app 4.py"

5. Then open your browser and go to http://127.0.0.1:5000.

---

## Configuration
Default settings are stored in WSPR_Analytics.ini
User-modified settings are saved in WSPR_Analytics.conf
You can reset to defaults via the web interface

---

## Output
Data is saved in data/WSPR_Analytics.csv

Logs are written to logs/WSPR_Analytics.log

