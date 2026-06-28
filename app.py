import os
import re
import json
import logging
import configparser
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, jsonify
from dotenv import load_dotenv
import datetime
import pandas as pd
import folium
from folium.plugins import GroupedLayerControl
from pyhamtools import Callinfo, LookupLib
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

AZIMUTH_SECTOR_ORDER = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
AZIMUTH_SECTOR_BOUNDS = [
    ('N', 337.5, 360.0), ('N', 0.0, 22.5),
    ('NE', 22.5, 67.5),
    ('E', 67.5, 112.5),
    ('SE', 112.5, 157.5),
    ('S', 157.5, 202.5),
    ('SW', 202.5, 247.5),
    ('W', 247.5, 292.5),
    ('NW', 292.5, 337.5),
]

def azimuth_sector(az):
    az = az % 360
    for name, lo, hi in AZIMUTH_SECTOR_BOUNDS:
        if lo <= az < hi:
            return name
    return 'N'

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('WSPR_SECRET_KEY', 'wspr-analytics-dev-key')
if app.secret_key == 'wspr-analytics-dev-key':
    logger.warning(
        "WSPR_SECRET_KEY not set — using insecure default key. Set WSPR_SECRET_KEY in .env"
    )

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
        callSignList=None,
        distanceList=None,
        countryList=None,
        hourlyList=None,
        best_ears_list=[],
        reliable_paths_list=[],
        best_snr_value=None,
        best_snr_call=None,
        best_snr_distance=None,
        snr_scatter_data=json.dumps([]),
        freq_chart_data=json.dumps({'labels': [], 'values': []}),
        hourly_chart_data=json.dumps({'labels': [], 'values': []}),
        country_chart_data=json.dumps({'labels': [], 'values': []}),
        azimuth_chart_data='{}',
        propagation_chart_data='{}',
        map_header_html='',
        map_body_html='',
        map_script_html='',
        tx_lat=tx_lat,
        tx_lon=tx_lon,
        dataset_start='',
        dataset_end='',
        duration_hours=0,
        granularity_minutes=0,
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
        row['unknown_country'] = False
    for row in distanceList:
        row['best_snr'] = 'N/A'
        row['mean_snr'] = 'N/A'
        row['unknown_country'] = False

    best_snr_value = None
    best_snr_call = None
    best_snr_distance = None
    snr_scatter_data = json.dumps([])
    map_header_html = ''
    map_body_html = ''
    map_script_html = ''
    dataset_start = ''
    dataset_end = ''
    duration_hours = 0
    granularity_minutes = 0
    raw_data = None
    try:
        raw_data = pd.read_csv('data/WSPR_Analytics.csv')
        best_row = raw_data.loc[raw_data['snr'].idxmax()]
        best_snr_value = int(best_row['snr'])
        best_snr_call = best_row['rx_sign']
        best_snr_distance = int(best_row['distance'])

        raw_time_full = pd.to_datetime(raw_data['time'])
        dataset_start_dt = raw_time_full.min()
        dataset_end_dt = raw_time_full.max()
        dataset_start = dataset_start_dt.isoformat()
        dataset_end = dataset_end_dt.isoformat()
        duration_hours = (dataset_end_dt - dataset_start_dt).total_seconds() / 3600
        granularity_minutes = granularity_minutes_for_duration(duration_hours)

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

    # Per-callsign country lookup, mirroring WSPR_Analytics.getCountries().
    # data/WSPR_Countries.csv only holds aggregate Country/Spots totals,
    # not a per-callsign mapping, so it can't be read back for this.
    # Computed once here and reused by the table enrichment, best
    # ears / reliable paths, and map generation code below.
    country_by_call = {}
    if raw_data is not None:
        try:
            if os.path.exists(WSPR_Analytics.CTY_FILE):
                lookup_lib = LookupLib(lookuptype="countryfile", filename=WSPR_Analytics.CTY_FILE)
            else:
                lookup_lib = LookupLib(lookuptype="countryfile")
            call_info = Callinfo(lookup_lib)
            country_by_call = {
                call: WSPR_Analytics.get_country_safely(call, call_info)
                for call in raw_data['rx_sign'].unique()
            }
        except Exception as e:
            logger.warning(f"Failed to resolve countries: {e}")

    if raw_data is not None:
        try:
            distance_mode_lookup = (
                raw_data.groupby('rx_sign')['distance']
                .apply(lambda s: s.mode().iloc[0])
                .to_dict()
            )
            snr_stats = raw_data.groupby('rx_sign')['snr'].agg(['max', 'mean'])

            for row in callSignList:
                rx_sign = row['rx_sign']
                row['distance'] = distance_mode_lookup.get(rx_sign, 0)
                row['unknown_country'] = country_by_call.get(rx_sign, 'Unknown') == 'Unknown'
                if row['unknown_country']:
                    row['rx_sign'] = f"{rx_sign}*"

            for row in distanceList:
                rx_sign = row['rx_sign']
                if rx_sign in snr_stats.index:
                    row['best_snr'] = format_snr(snr_stats.loc[rx_sign, 'max'], decimals=0) or 'N/A'
                    row['mean_snr'] = format_snr(snr_stats.loc[rx_sign, 'mean'], decimals=1) or 'N/A'
                row['unknown_country'] = country_by_call.get(rx_sign, 'Unknown') == 'Unknown'
                if row['unknown_country']:
                    row['rx_sign'] = f"{rx_sign}*"
        except Exception as e:
            logger.warning(f"Failed to enrich call sign / distance tables: {e}")

    best_ears_list = []
    reliable_paths_list = []
    if raw_data is not None:
        try:
            station_groups = raw_data.groupby('rx_sign')
            station_stats = station_groups['snr'].agg(spots='count', mean_snr='mean', best_snr='max', worst_snr='min')
            station_stats = station_stats[station_stats['spots'] >= 3]
            station_stats['distance'] = station_groups['distance'].apply(lambda s: s.mode().iloc[0])
            station_stats['snr_range_value'] = (station_stats['best_snr'] - station_stats['worst_snr']).round().astype(int)

            best_ears_df = station_stats.sort_values(by='mean_snr', ascending=True).head(15)
            best_ears_list = [
                {
                    'call_sign': f"{rx_sign}*" if country_by_call.get(rx_sign, 'Unknown') == 'Unknown' else rx_sign,
                    'distance': int(row['distance']),
                    'spots': int(row['spots']),
                    'mean_snr': format_snr(row['mean_snr'], decimals=1),
                    'best_snr': format_snr(row['best_snr'], decimals=0),
                    'worst_snr': format_snr(row['worst_snr'], decimals=0),
                    'unknown_country': country_by_call.get(rx_sign, 'Unknown') == 'Unknown',
                }
                for rx_sign, row in best_ears_df.iterrows()
            ]

            reliable_df = station_stats.sort_values(by='snr_range_value', ascending=True).head(15)
            reliable_paths_list = [
                {
                    'call_sign': f"{rx_sign}*" if country_by_call.get(rx_sign, 'Unknown') == 'Unknown' else rx_sign,
                    'distance': int(row['distance']),
                    'spots': int(row['spots']),
                    'mean_snr': format_snr(row['mean_snr'], decimals=1),
                    'best_snr': format_snr(row['best_snr'], decimals=0),
                    'worst_snr': format_snr(row['worst_snr'], decimals=0),
                    'range': f"{int(row['snr_range_value'])} dB",
                    'unknown_country': country_by_call.get(rx_sign, 'Unknown') == 'Unknown',
                }
                for rx_sign, row in reliable_df.iterrows()
            ]
        except Exception as e:
            logger.warning(f"Failed to compute best ears / reliable paths tables: {e}")

    if raw_data is not None:
        try:
            folium_map = folium.Map(location=[tx_lat, tx_lon], zoom_start=5, tiles='OpenStreetMap')

            receivers = raw_data.loc[raw_data.groupby('rx_sign')['snr'].idxmax()]

            raw_data_countries = raw_data['rx_sign'].map(country_by_call).fillna('Unknown')
            country_counts = raw_data_countries.value_counts()
            country_counts = country_counts[country_counts.index != 'Unknown']
            top_countries = list(country_counts.head(10).index)

            # Distance FeatureGroups (markers live here)
            fg_under_500 = folium.FeatureGroup(name='Under 500 km', show=True)
            fg_500_1000 = folium.FeatureGroup(name='500 – 1,000 km', show=True)
            fg_over_1000 = folium.FeatureGroup(name='Over 1,000 km', show=True)
            for fg in (fg_under_500, fg_500_1000, fg_over_1000):
                fg.add_to(folium_map)

            # Country FeatureGroups (propagation lines live here)
            country_feature_groups = {}
            for country_name in top_countries:
                country_feature_groups[country_name] = folium.FeatureGroup(name=country_name, show=True)
            country_feature_groups['Other'] = folium.FeatureGroup(name='Other', show=True)
            for fg in country_feature_groups.values():
                fg.add_to(folium_map)

            for _, rx_row in receivers.iterrows():
                rx_distance = rx_row['distance']
                if rx_distance < 500:
                    line_colour = 'green'
                    distance_group = fg_under_500
                elif rx_distance <= 1000:
                    line_colour = 'orange'
                    distance_group = fg_500_1000
                else:
                    line_colour = 'red'
                    distance_group = fg_over_1000

                country_name = country_by_call.get(rx_row['rx_sign'], 'Unknown')
                country_group = country_feature_groups.get(country_name, country_feature_groups['Other'])

                popup_html = (
                    f"<b>{rx_row['rx_sign']}</b><br>"
                    f"Distance: {rx_distance:.0f} km<br>"
                    f"Best SNR: {rx_row['snr']} dB<br>"
                    f"Grid: {rx_row['rx_loc']}<br>"
                    f"Country: {country_name}"
                )

                # A folium element can only belong to one FeatureGroup, so the
                # marker (distance dimension) and line (country dimension) are
                # split across the two groups they need to be filterable by.
                folium.CircleMarker(
                    location=[rx_row['rx_lat'], rx_row['rx_lon']],
                    radius=6,
                    popup=folium.Popup(popup_html, max_width=220),
                    color=line_colour,
                    fill=True,
                    fillColor=line_colour,
                    fillOpacity=0.8
                ).add_to(distance_group)

                folium.PolyLine(
                    locations=[[tx_lat, tx_lon], [rx_row['rx_lat'], rx_row['rx_lon']]],
                    color=line_colour,
                    weight=2,
                    opacity=0.7
                ).add_to(country_group)

            # Distance rings stay outside any FeatureGroup so they're always visible.
            for ring_radius_km in (500, 1000, 1500):
                folium.Circle(
                    location=[tx_lat, tx_lon],
                    radius=ring_radius_km * 1000,
                    color='grey',
                    fill=False,
                    dashArray='5, 5'
                ).add_to(folium_map)

            GroupedLayerControl(
                groups={
                    'Distance': [fg_under_500, fg_500_1000, fg_over_1000],
                    'Countries': list(country_feature_groups.values())
                },
                exclusive_groups=False,
                collapsed=True,
                position='topright'
            ).add_to(folium_map)

            map_root = folium_map.get_root()
            map_root.render()
            map_header_html = map_root.header.render()
            map_body_html = map_root.html.render()
            map_script_html = map_root.script.render()

            # Folium injects its own Bootstrap 5.2.2 CSS/JS, which conflicts
            # with the page's own Bootstrap 5.3.3 (loaded via base.html).
            map_header_html = re.sub(r'<link[^>]*bootstrap[^>]*>', '', map_header_html)
            map_header_html = re.sub(r'<script[^>]*bootstrap[^>]*></script>', '', map_header_html)
        except Exception as e:
            logger.warning(f"Failed to build Folium map: {e}")
            map_header_html = ''
            map_body_html = ''
            map_script_html = ''

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

    azimuth_chart_data = json.dumps({
        'labels': AZIMUTH_SECTOR_ORDER,
        'values': [0] * len(AZIMUTH_SECTOR_ORDER)
    })
    if raw_data is not None and 'azimuth' in raw_data.columns:
        try:
            sector_counts = raw_data['azimuth'].apply(azimuth_sector).value_counts()
            azimuth_chart_data = json.dumps({
                'labels': AZIMUTH_SECTOR_ORDER,
                'values': [int(sector_counts.get(s, 0)) for s in AZIMUTH_SECTOR_ORDER]
            })
        except Exception as e:
            logger.warning(f"Failed to compute azimuth chart data: {e}")

    propagation_labels = [row['Time'].strftime('%H:%M') for row in hourlyList]
    propagation_spots = [row['Spots'] for row in hourlyList]
    propagation_snr = [None] * len(hourlyList)
    if raw_data is not None:
        try:
            raw_time = pd.to_datetime(raw_data['time'])
            hourly_snr = raw_data.groupby(raw_time.dt.floor('h'))['snr'].mean()
            propagation_snr = [
                round(float(hourly_snr[row['Time']]), 1) if row['Time'] in hourly_snr.index else None
                for row in hourlyList
            ]
        except Exception as e:
            logger.warning(f"Failed to compute hourly mean SNR: {e}")

    propagation_chart_data = json.dumps({
        'labels': propagation_labels,
        'spots': propagation_spots,
        'snr': propagation_snr
    })

    return render_template(
        'dashboard.html',
        summaryData=summaryData,
        callSignList=callSignList,
        distanceList=distanceList,
        countryList=countryList,
        hourlyList=hourlyList,
        best_ears_list=best_ears_list,
        reliable_paths_list=reliable_paths_list,
        best_snr_value=best_snr_value,
        best_snr_call=best_snr_call,
        best_snr_distance=best_snr_distance,
        snr_scatter_data=snr_scatter_data,
        freq_chart_data=freq_chart_data,
        hourly_chart_data=hourly_chart_data,
        country_chart_data=country_chart_data,
        azimuth_chart_data=azimuth_chart_data,
        propagation_chart_data=propagation_chart_data,
        map_header_html=map_header_html,
        map_body_html=map_body_html,
        map_script_html=map_script_html,
        tx_lat=tx_lat,
        tx_lon=tx_lon,
        dataset_start=dataset_start,
        dataset_end=dataset_end,
        duration_hours=duration_hours,
        granularity_minutes=granularity_minutes,
        error=error,
        dark_mode=dark_mode,
        show_menu=True,
        year=datetime.datetime.now().year,
        config=config
    )

RAW_DATA_CSV_PATH = 'data/WSPR_Analytics.csv'
SNAPSHOT_GRANULARITY_MINUTES = 2

def granularity_minutes_for_duration(duration_hours):
    if duration_hours < 6:
        return 15
    elif duration_hours < 24:
        return 30
    elif duration_hours < 72:
        return 60
    else:
        return 240

@app.route('/api/dataset-info')
def api_dataset_info():
    if not session.get('config_saved', False):
        return jsonify({'error': 'No active session. Submit a query first.'}), 401

    if not os.path.exists(RAW_DATA_CSV_PATH):
        return jsonify({"error": "No data available. Submit a query first."}), 404

    try:
        raw_data = pd.read_csv(RAW_DATA_CSV_PATH)
        raw_time = pd.to_datetime(raw_data['time'])
        start = raw_time.min()
        end = raw_time.max()
        duration_hours = (end - start).total_seconds() / 3600

        return jsonify({
            "start": start.isoformat(),
            "end": end.isoformat(),
            "duration_hours": round(duration_hours, 2),
            "total_spots": int(len(raw_data)),
            "granularity_minutes": granularity_minutes_for_duration(duration_hours)
        })
    except Exception as e:
        logger.warning(f"Failed to read dataset info: {e}")
        return jsonify({"error": f"Failed to read dataset: {e}"}), 500

@app.route('/api/spots')
def api_spots():
    if not session.get('config_saved', False):
        return jsonify({'error': 'No active session. Submit a query first.'}), 401

    start_param = request.args.get('start')
    window_param = request.args.get('window')
    mode_param = request.args.get('mode')

    if not start_param:
        return jsonify({"error": "Missing required parameter: start"}), 400
    try:
        start_dt = pd.to_datetime(start_param)
        if pd.isna(start_dt):
            raise ValueError("unparseable datetime")
        if start_dt.tzinfo is not None:
            start_dt = start_dt.tz_localize(None)
    except Exception:
        return jsonify({"error": f"Invalid start datetime: {start_param!r}"}), 400

    if not window_param:
        return jsonify({"error": "Missing required parameter: window"}), 400
    try:
        window_minutes = int(window_param)
        if window_minutes <= 0:
            raise ValueError("window must be positive")
    except (TypeError, ValueError):
        return jsonify({"error": f"Invalid window: {window_param!r} (must be a positive integer)"}), 400

    if mode_param not in ('rolling', 'snapshot'):
        return jsonify({"error": f"Invalid mode: {mode_param!r} (must be 'rolling' or 'snapshot')"}), 400

    if not os.path.exists(RAW_DATA_CSV_PATH):
        return jsonify({"error": "No data available. Submit a query first."}), 404

    try:
        raw_data = pd.read_csv(RAW_DATA_CSV_PATH)
        raw_data['time'] = pd.to_datetime(raw_data['time'])

        if mode_param == 'snapshot':
            window_end = start_dt + pd.Timedelta(minutes=SNAPSHOT_GRANULARITY_MINUTES)
        else:
            window_end = start_dt + pd.Timedelta(minutes=window_minutes)

        mask = (raw_data['time'] >= start_dt) & (raw_data['time'] < window_end)
        filtered = raw_data.loc[mask]

        spots = []
        if not filtered.empty:
            best_idx = filtered.groupby('rx_sign')['snr'].idxmax()
            best_rows = filtered.loc[best_idx]
            spots = [
                {
                    "rx_sign": row['rx_sign'],
                    "rx_lat": float(row['rx_lat']),
                    "rx_lon": float(row['rx_lon']),
                    "distance": int(row['distance']),
                    "snr": int(row['snr']),
                    "time": row['time'].strftime('%H:%M')
                }
                for _, row in best_rows.iterrows()
            ]

        return jsonify({
            "spots": spots,
            "window_start": start_dt.isoformat(),
            "window_end": window_end.isoformat(),
            "total_spots": len(spots)
        })
    except Exception as e:
        logger.warning(f"Failed to compute spots for window: {e}")
        return jsonify({"error": f"Failed to read data: {e}"}), 500

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
    if not session.get('config_saved', False):
        return redirect(url_for('index'))

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
    if not session.get('config_saved', False):
        return redirect(url_for('index'))

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
