import os
import configparser
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
import datetime
import WSPR_Analytics

app = Flask(__name__)
app.secret_key = "super-secret-key"  # Change for production

CONFIG_FILE = 'WSPR_Analytics.conf'
DEFAULT_FILE = 'WSPR_Analytics.ini'

def load_config(path):
    config = configparser.ConfigParser()
    config.read(path)
    if not config.sections():
        config['default'] = {
            'CallSign'     : 'Call Sign',
            'Period'       : '10 minutes',
            'TopStations'  : '10',            
            'NumBins'      : '8'              # New field for number of bins
        }
    return config['default']

def save_config(values):
    config = configparser.ConfigParser()
    config['default'] = values
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)

def reset_config():
    if os.path.exists(DEFAULT_FILE):
        default = load_config(DEFAULT_FILE)
        save_config(default)
        return default
    else:
        return load_config(CONFIG_FILE)

@app.route('/', methods=['GET', 'POST'])
def index():
    show_menu = session.get('config_saved', False)
    dark_mode = session.get('dark_mode', False)
    if request.method == 'POST':
        if 'submit' in request.form:
            call_sign    = request.form['CallSign']
            period       = request.form['Period']
            top_stations = request.form['TopStations']
            num_bins     = request.form['NumBins']
            values = {
                'CallSign': call_sign,
                'Period': period,
                'TopStations': top_stations,
                'NumBins': num_bins # New field for number of bins
            }
            save_config(values)
            session['config_saved'] = True
            return redirect(url_for('data'))
        elif 'reset' in request.form:
            values = reset_config()
            session['config_saved'] = False
            return render_template('index.html', config=values, periods=period_list(), dark_mode=dark_mode, show_menu=False, year=datetime.datetime.now().year)
        elif 'dark_toggle' in request.form:
            session['dark_mode'] = not dark_mode
            return redirect(request.url)
    config = load_config(CONFIG_FILE if show_menu else DEFAULT_FILE)
    return render_template('index.html', config=config, periods=period_list(), dark_mode=dark_mode, show_menu=show_menu, year=datetime.datetime.now().year)

@app.route('/data', methods=['GET', 'POST'])
def data():
    if not session.get('config_saved', False):
        return redirect(url_for('index'))
    config = load_config(CONFIG_FILE)
    dark_mode = session.get('dark_mode', False)
    if request.method == 'POST':
        if 'dark_toggle' in request.form:
            session['dark_mode'] = not dark_mode
            return redirect(request.url)
            
    data_rows, error = WSPR_Analytics.getData(config['CallSign'], config['Period'])
    
    return render_template(
        'data.html',
        data_rows=data_rows,
        error=error,
        dark_mode=dark_mode,
        show_menu=True,
        year=datetime.datetime.now().year
    )

@app.route('/analysis', methods=['GET', 'POST'])
def analysis():
    if not session.get('config_saved', False):
        return redirect(url_for('index'))
    
    config = load_config(CONFIG_FILE)

    dark_mode = session.get('dark_mode', False)

    if request.method == 'POST':
        if 'dark_toggle' in request.form:
            session['dark_mode'] = not dark_mode
            return redirect(request.url)
 
    try:
        num_bins = int(config.get('NumBins', 8))
    except Exception:
        num_bins = 8

    summaryData, frequencyList, logarithmicList, callSignList, distanceList, countryList, hourlyList, error = WSPR_Analytics.analyseData(num_bins)

    try:
        top_stations_count = int(config.get('TopStations', 10))
    except Exception:
        top_stations_count = 10

    # Apply row limit if TopStations > 0
    if top_stations_count > 0:
        callSignList = callSignList[:top_stations_count]
        distanceList = distanceList[:top_stations_count]


    # --- Define your mapping dictionaries here in Python ---
    hourly_header_map = {
        'Time': 'Time', # Data key: 'time', Display header: 'Time'
        'Mean': 'Mean',
        'Min': 'Min',
        'Max': 'Max',
        'Spots': 'Spots'
    }

    call_sign_header_map = {
        'rx_sign': 'Call Sign',
        'Count': 'Count',
        'gridRef': 'Grid'
    }

    distance_header_map = {
        'rx_sign': 'Call Sign',
        'distance': 'Distance (km)',
        'rx_loc': 'Grid',
        'Count': 'Count'
    }    
    
    return render_template(
        'analysis.html',
        summaryData           = summaryData,
        freqBinList           = frequencyList,
        logBinList            = logarithmicList,
        callSignList          = callSignList,
        distanceList          = distanceList,
        countryList           = countryList,
        hourlyList            = hourlyList,
        # --- Pass the mapping dictionaries to the template ---
        hourly_header_map     = hourly_header_map,
        call_sign_header_map  = call_sign_header_map,
        distance_header_map   = distance_header_map,
        error=error,
        dark_mode             = dark_mode,
        show_menu             = True,
        year=datetime.datetime.now().year
    )

@app.route('/visualise', methods=['GET', 'POST'])
def visualise():
    if not session.get('config_saved', False):
        return redirect(url_for('index'))
    dark_mode = session.get('dark_mode', False)
    if request.method == 'POST':
        if 'dark_toggle' in request.form:
            session['dark_mode'] = not dark_mode
            return redirect(request.url)
    png_path = WSPR_Analytics.visualiseData()
    return render_template(
        'visualise.html', 
        png_file=png_path, 
        dark_mode=dark_mode, 
        show_menu=True, 
        year=datetime.datetime.now().year)

@app.route('/static/<path:filename>')
def staticfiles(filename):
    return send_from_directory('static', filename)

@app.route('/logs')
def logs():
    import os
    log_path = os.path.join('logs', 'WSPR_Analytics.log')
    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            log_contents = f.read()
    except Exception as e:
        log_contents = f"Could not open log file: {e}"
    dark_mode = session.get('dark_mode', False)
    return render_template(
        'logs.html',
        log_contents=log_contents,
        dark_mode=dark_mode,
        show_menu=True,
        year=datetime.datetime.now().year
    )

@app.route('/export-data')
def export_data():
    file_path = "data/WSPR_Analytics.csv"
    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    return send_from_directory(directory, filename, as_attachment=True)

def period_list():
    return [
        "10 minutes", "30 minutes", "1 hour", "3 hours", "6 hours", "12 hours", "1 day", "2 days", "3 days", "5 days", "7 days", "14 days"
    ]

if __name__ == '__main__':
    app.run(debug=True)