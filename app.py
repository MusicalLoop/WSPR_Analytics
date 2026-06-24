import os
import json
import logging
import configparser
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from dotenv import load_dotenv
import datetime
import pandas as pd
import folium
import WSPR_Analytics

logger = logging.getLogger()

DEFAULT_TX_LAT = 51.5
DEFAULT_TX_LON = -0.5

def parse_tx_coordinate(value, default, field_name):
    try:
        return float(value)
    except (TypeError, ValueError):
        logger.warning(f"Invalid or missing {field_name} ({value!r}); defaulting to {default}")
        return default

def format_snr(value, decimals=0):
    if value is None or pd.isna(value):
        return None
    rounded = round(float(value), decimals)
    if decimals == 0:
        rounded = int(rounded)
    sign = '+' if rounded >= 0 else ''
    return f"{sign}{rounded} dB"

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('WSPR_SECRET_KEY', 'wspr-analytics-dev-key')

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
            'NumBins'      : '8',             # New field for number of bins
            'TxLat'        : str(DEFAULT_TX_LAT),
            'TxLon'        : str(DEFAULT_TX_LON)
        }
    else:
        config['default'].setdefault('TxLat', str(DEFAULT_TX_LAT))
        config['default'].setdefault('TxLon', str(DEFAULT_TX_LON))
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
    if request.method == "POST":
        if 'submit' in request.form:
            call_sign    = request.form['CallSign']
            period       = request.form['Period']
            top_stations = request.form['TopStations']
            num_bins     = request.form['NumBins']
            tx_lat       = parse_tx_coordinate(request.form.get('TxLat'), DEFAULT_TX_LAT, 'TxLat')
            tx_lon       = parse_tx_coordinate(request.form.get('TxLon'), DEFAULT_TX_LON, 'TxLon')
            values = {
                'CallSign': call_sign,
                'Period': period,
                'TopStations': top_stations,
                'NumBins': num_bins, # New field for number of bins
                'TxLat': str(tx_lat),
                'TxLon': str(tx_lon)
            }
            save_config(values)
            session['config_saved'] = True
            return redirect(url_for('dashboard'))
        elif 'reset' in request.form:
            values = reset_config()
            session['config_saved'] = False
            return render_template('index.html', config=values, periods=period_list(), dark_mode=dark_mode, show_menu=False, year=datetime.datetime.now().year)
        elif 'dark_toggle' in request.form:
            session['dark_mode'] = not dark_mode
            return redirect(request.url)
    config = load_config(CONFIG_FILE if show_menu else DEFAULT_FILE)
    return render_template('index.html', config=config, periods=period_list(), dark_mode=dark_mode, show_menu=show_menu, year=datetime.datetime.now().year)

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if not session.get('config_saved', False):
        return redirect(url_for('index'))

    config = load_config(CONFIG_FILE)
    dark_mode = session.get('dark_mode', False)

    if request.method == "POST":
        if 'dark_toggle' in request.form:
            session['dark_mode'] = not dark_mode
            return redirect(request.url)

    tx_lat = parse_tx_coordinate(config.get('TxLat'), DEFAULT_TX_LAT, 'TxLat')
    tx_lon = parse_tx_coordinate(config.get('TxLon'), DEFAULT_TX_LON, 'TxLon')

    empty_result = dict(
        summaryData=None,
        frequencyList=None,
        logarithmicList=None,
        callSignList=None,
        distanceList=None,
        countryList=None,
        hourlyList=None,
        best_snr_value=None,
        best_snr_call=None,
        best_snr_distance=None,
        snr_scatter_data=json.dumps([]),
        freq_chart_data=json.dumps({'labels': [], 'values': []}),
        hourly_chart_data=json.dumps({'labels': [], 'values': []}),
        country_chart_data=json.dumps({'labels': [], 'values': []}),
        map_html='',
        tx_lat=tx_lat,
        tx_lon=tx_lon,
        dark_mode=dark_mode,
        show_menu=True,
        year=datetime.datetime.now().year,
        config=config
    )

    data_rows, error = WSPR_Analytics.getData(config['CallSign'], config['Period'])
    if error:
        return render_template('dashboard.html', error=error, **empty_result)

    try:
        num_bins = int(config.get('NumBins', 8))
    except Exception:
        num_bins = 8

    summaryData, frequencyList, logarithmicList, callSignList, distanceList, countryList, hourlyList, error = WSPR_Analytics.analyseData(num_bins)
    if error:
        return render_template('dashboard.html', error=error, **empty_result)

    try:
        top_stations_count = int(config.get('TopStations', 10))
    except Exception:
        top_stations_count = 10

    # Apply row limit if TopStations > 0
    if top_stations_count > 0:
        callSignList = callSignList[:top_stations_count]
        distanceList = distanceList[:top_stations_count]

    for row in callSignList:
        row['distance'] = 0
    for row in distanceList:
        row['best_snr'] = 'N/A'
        row['mean_snr'] = 'N/A'

    best_snr_value = None
    best_snr_call = None
    best_snr_distance = None
    snr_scatter_data = json.dumps([])
    map_html = ''
    raw_data = None
    try:
        raw_data = pd.read_csv('data/WSPR_Analytics.csv')
        best_row = raw_data.loc[raw_data['snr'].idxmax()]
        best_snr_value = int(best_row['snr'])
        best_snr_call = best_row['rx_sign']
        best_snr_distance = int(best_row['distance'])

        time_fmt = pd.to_datetime(raw_data['time']).dt.strftime('%H:%M')
        snr_scatter_data = json.dumps([
            {'x': float(d), 'y': float(s), 'call': c, 'grid': g, 'time': t}
            for d, s, c, g, t in zip(
                raw_data['distance'], raw_data['snr'],
                raw_data['rx_sign'], raw_data['rx_loc'], time_fmt
            )
        ])
    except Exception:
        pass

    if raw_data is not None:
        try:
            distance_mode_lookup = (
                raw_data.groupby('rx_sign')['distance']
                .apply(lambda s: s.mode().iloc[0])
                .to_dict()
            )
            snr_stats = raw_data.groupby('rx_sign')['snr'].agg(['max', 'mean'])

            for row in callSignList:
                row['distance'] = distance_mode_lookup.get(row['rx_sign'], 0)

            for row in distanceList:
                rx_sign = row['rx_sign']
                if rx_sign in snr_stats.index:
                    row['best_snr'] = format_snr(snr_stats.loc[rx_sign, 'max'], decimals=0) or 'N/A'
                    row['mean_snr'] = format_snr(snr_stats.loc[rx_sign, 'mean'], decimals=1) or 'N/A'
        except Exception as e:
            logger.warning(f"Failed to enrich call sign / distance tables: {e}")

    if raw_data is not None:
        try:
            folium_map = folium.Map(location=[tx_lat, tx_lon], zoom_start=5, tiles='OpenStreetMap')

            receivers = raw_data.loc[raw_data.groupby('rx_sign')['snr'].idxmax()]

            for _, rx_row in receivers.iterrows():
                rx_distance = rx_row['distance']
                if rx_distance < 500:
                    line_colour = 'green'
                elif rx_distance <= 1000:
                    line_colour = 'orange'
                else:
                    line_colour = 'red'

                popup_html = (
                    f"<b>{rx_row['rx_sign']}</b><br>"
                    f"Distance: {rx_distance:.0f} km<br>"
                    f"Best SNR: {rx_row['snr']} dB<br>"
                    f"Grid: {rx_row['rx_loc']}"
                )

                folium.CircleMarker(
                    location=[rx_row['rx_lat'], rx_row['rx_lon']],
                    radius=6,
                    popup=folium.Popup(popup_html, max_width=220),
                    color=line_colour,
                    fill=True,
                    fillColor=line_colour,
                    fillOpacity=0.8
                ).add_to(folium_map)

                folium.PolyLine(
                    locations=[[tx_lat, tx_lon], [rx_row['rx_lat'], rx_row['rx_lon']]],
                    color=line_colour,
                    weight=2,
                    opacity=0.7
                ).add_to(folium_map)

            for ring_radius_km in (500, 1000, 1500):
                folium.Circle(
                    location=[tx_lat, tx_lon],
                    radius=ring_radius_km * 1000,
                    color='grey',
                    fill=False,
                    dashArray='5, 5'
                ).add_to(folium_map)

            map_html = folium_map._repr_html_()
        except Exception as e:
            logger.warning(f"Failed to build Folium map: {e}")
            map_html = ''

    freq_chart_data = json.dumps({
        'labels': [row['Distance Range'] for row in frequencyList],
        'values': [row['Number of Spots'] for row in frequencyList]
    })

    hourly_chart_data = json.dumps({
        'labels': [row['Time'].strftime('%H:%M') for row in hourlyList],
        'values': [row['Spots'] for row in hourlyList]
    })

    top_countries = countryList[:10]
    country_chart_data = json.dumps({
        'labels': [row['Country'] for row in top_countries],
        'values': [row['Spots'] for row in top_countries]
    })

    return render_template(
        'dashboard.html',
        summaryData=summaryData,
        frequencyList=frequencyList,
        logarithmicList=logarithmicList,
        callSignList=callSignList,
        distanceList=distanceList,
        countryList=countryList,
        hourlyList=hourlyList,
        best_snr_value=best_snr_value,
        best_snr_call=best_snr_call,
        best_snr_distance=best_snr_distance,
        snr_scatter_data=snr_scatter_data,
        freq_chart_data=freq_chart_data,
        hourly_chart_data=hourly_chart_data,
        country_chart_data=country_chart_data,
        map_html=map_html,
        tx_lat=tx_lat,
        tx_lon=tx_lon,
        error=error,
        dark_mode=dark_mode,
        show_menu=True,
        year=datetime.datetime.now().year,
        config=config
    )

@app.route('/data', methods=['GET', 'POST'])
def data():
    if not session.get('config_saved', False):
        return redirect(url_for('index'))
    config = load_config(CONFIG_FILE)
    dark_mode = session.get('dark_mode', False)
    if request.method == "POST":
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
