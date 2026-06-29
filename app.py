import os
import re
import io
import json
import time
import logging
import configparser
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, send_file, jsonify
from dotenv import load_dotenv
import datetime
import pandas as pd
import folium
from folium.plugins import GroupedLayerControl
from PIL import Image, ImageDraw, ImageFont
import WSPR_Analytics

logger = logging.getLogger()

DEFAULT_TX_LAT = 51.5
DEFAULT_TX_LON = -0.5
WSPR_LIVE_COOLDOWN_SECONDS = 5.5

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

RX_NORMALIZE_COLUMNS = {
    'tx_sign': 'rx_sign', 'rx_sign': 'tx_sign',
    'tx_lat': 'rx_lat', 'rx_lat': 'tx_lat',
    'tx_lon': 'rx_lon', 'rx_lon': 'tx_lon',
    'tx_loc': 'rx_loc', 'rx_loc': 'tx_loc',
    'azimuth': 'rx_azimuth', 'rx_azimuth': 'azimuth',
}

def normalize_rx_dataframe(df):
    """
    RX-mode CSVs have rx_sign fixed to the user's own callsign on every row
    (tx_sign is the remote station). Every analysis function (getSummary,
    getDistantCallSigns, getCallSignCount, getCountries, best SNR/DX lookups,
    map building) is written assuming 'rx_sign' is the station of interest,
    so RX data is column-swapped to match that shape before analysis:
    rx_sign/rx_lat/rx_lon/rx_loc/rx_azimuth become the remote station,
    tx_sign/tx_lat/tx_lon/tx_loc/azimuth become the user's own QTH.
    """
    return df.rename(columns=RX_NORMALIZE_COLUMNS)

def dataset_csv_path_for_mode(single_mode):
    name = WSPR_Analytics.RX_DATAFILE_NAME if single_mode == 'rx' else WSPR_Analytics.TX_DATAFILE_NAME
    return f"data/{name}.csv"

def fetch_and_analyse(call_sign, period, single_mode, num_bins):
    """
    Fetches and analyses a single TX or RX dataset: getData() + read CSV
    (normalized for RX) + analyseData() + best SNR/DX lookup. Used directly
    for TX-only/RX-only mode, and twice (once per side) for Both mode.
    Returns (result_dict, error). result_dict is None if error is set.
    """
    data_rows, error = WSPR_Analytics.getData(call_sign, period, mode=single_mode)
    if error:
        return None, error

    raw_data = None
    try:
        raw_data = pd.read_csv(dataset_csv_path_for_mode(single_mode))
        if single_mode == 'rx':
            raw_data = normalize_rx_dataframe(raw_data)
    except Exception as e:
        logger.warning(f"Failed to read raw data CSV for mode {single_mode}: {e}")
        return None, f"Failed to read raw data CSV for mode {single_mode}: {e}"

    # analyseData() falls back to reading DATAFILE_NAME from disk when raw_df
    # is None — that fallback exists for callers with no in-memory frame at
    # all, and would silently substitute a stale, unrelated dataset here.
    summaryData, frequencyList, logarithmicList, callSignList, distanceList, countryList, hourlyList, country_by_call, error = (
        WSPR_Analytics.analyseData(num_bins, raw_df=raw_data)
    )
    if error:
        return None, error

    best_snr_value = None
    best_snr_call = None
    best_snr_distance = None
    try:
        best_row = raw_data.loc[raw_data['snr'].idxmax()]
        best_snr_value = int(best_row['snr'])
        best_snr_call = best_row['rx_sign']
        best_snr_distance = int(best_row['distance'])
    except Exception:
        pass

    return dict(
        raw_data=raw_data,
        summaryData=summaryData,
        frequencyList=frequencyList,
        logarithmicList=logarithmicList,
        callSignList=callSignList,
        distanceList=distanceList,
        countryList=countryList,
        hourlyList=hourlyList,
        country_by_call=country_by_call,
        best_snr_value=best_snr_value,
        best_snr_call=best_snr_call,
        best_snr_distance=best_snr_distance,
    ), None

def total_spots_of(summary_list):
    if not summary_list:
        return 0
    item = next((r for r in summary_list if r['label'] == 'Total spots'), None)
    return item['value'] if item else 0

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
            'TxLon'        : str(DEFAULT_TX_LON),
            'Mode'         : 'tx'
        }
    else:
        config['default'].setdefault('TxLat', str(DEFAULT_TX_LAT))
        config['default'].setdefault('TxLon', str(DEFAULT_TX_LON))
        config['default'].setdefault('Mode', 'tx')
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
            mode         = request.form.get('Mode', 'tx')
            if mode not in ('tx', 'rx', 'both'):
                mode = 'tx'
            values = {
                'CallSign': call_sign,
                'Period': period,
                'TopStations': top_stations,
                'NumBins': num_bins, # New field for number of bins
                'TxLat': str(tx_lat),
                'TxLon': str(tx_lon),
                'Mode': mode
            }
            save_config(values)
            session['config_saved'] = True
            return redirect(url_for('dashboard'))
        elif 'reset' in request.form:
            values = reset_config()
            return render_template('index.html', config=values, periods=period_list(), dark_mode=dark_mode, show_menu=show_menu, year=datetime.datetime.now().year)
        elif 'dark_toggle' in request.form:
            session['dark_mode'] = not dark_mode
            active_tab = request.form.get('active_tab', '')
            redirect_url = request.path + active_tab if active_tab else request.url
            return redirect(redirect_url)
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
            active_tab = request.form.get('active_tab', '')
            redirect_url = request.path + active_tab if active_tab else request.url
            return redirect(redirect_url)

    tx_lat = parse_tx_coordinate(config.get('TxLat'), DEFAULT_TX_LAT, 'TxLat')
    tx_lon = parse_tx_coordinate(config.get('TxLon'), DEFAULT_TX_LON, 'TxLon')
    mode = config.get('Mode', 'tx')
    if mode not in ('tx', 'rx', 'both'):
        mode = 'tx'
    primary_mode = 'tx' if mode == 'both' else mode

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
        config=config,
        mode=mode
    )

    try:
        num_bins = int(config.get('NumBins', 8))
    except Exception:
        num_bins = 8

    primary, error = fetch_and_analyse(config['CallSign'], config['Period'], primary_mode, num_bins)
    if error:
        return render_template('dashboard.html', error=error, **empty_result)

    raw_data = primary['raw_data']
    summaryData = primary['summaryData']
    frequencyList = primary['frequencyList']
    logarithmicList = primary['logarithmicList']
    callSignList = primary['callSignList']
    distanceList = primary['distanceList']
    countryList = primary['countryList']
    hourlyList = primary['hourlyList']
    country_by_call = primary['country_by_call']

    # Both mode: fetch + analyse the RX side too (TX side is the primary
    # dataset above), then derive symmetric-path and combined metrics for
    # the Summary tab's three-column layout. The other tabs (Map, Charts,
    # Analysis) still render from the TX dataset only — RX/combined views
    # for those tabs are phases 5-7, not yet implemented.
    tx_result = rx_result = None
    symmetric_calls = []
    symmetric_count = 0
    combined_spots = 0
    combined_unique = 0
    combined_countries = 0
    if mode == 'both':
        tx_result = primary
        # wspr.live enforces a 5s cooldown between requests from the same
        # client; firing the RX query immediately after the TX query above
        # gets rejected with an HTML "let the server cool down" error page.
        time.sleep(WSPR_LIVE_COOLDOWN_SECONDS)
        rx_result, rx_error = fetch_and_analyse(config['CallSign'], config['Period'], 'rx', num_bins)
        if rx_error:
            logger.warning(f"Both mode: RX dataset fetch/analysis failed: {rx_error}")
            rx_result = None

        tx_remote_calls = set(tx_result['raw_data']['rx_sign'].unique()) if tx_result['raw_data'] is not None else set()
        rx_remote_calls = set(rx_result['raw_data']['rx_sign'].unique()) if rx_result and rx_result['raw_data'] is not None else set()
        symmetric_calls = sorted(tx_remote_calls & rx_remote_calls)
        symmetric_count = len(symmetric_calls)
        combined_unique = len(tx_remote_calls | rx_remote_calls)
        combined_spots = total_spots_of(tx_result['summaryData']) + total_spots_of(rx_result['summaryData'] if rx_result else None)
        tx_countries_set = {row['Country'] for row in tx_result['countryList']}
        rx_countries_set = {row['Country'] for row in (rx_result['countryList'] if rx_result else [])}
        combined_countries = len(tx_countries_set | rx_countries_set)

    try:
        top_stations_count = int(config.get('TopStations', 10))
    except Exception:
        top_stations_count = 10

    # Apply row limit if TopStations > 0
    if top_stations_count > 0:
        callSignList = callSignList[:top_stations_count]
        distanceList = distanceList[:top_stations_count]
        if rx_result:
            rx_result['distanceList'] = rx_result['distanceList'][:top_stations_count]

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
    try:
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

    # country_by_call is returned by WSPR_Analytics.analyseData() (sourced from
    # getCountries(), the single place this pyhamtools lookup now runs) and
    # reused here by the table enrichment, best ears / reliable paths, and
    # map generation code below.

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

            if mode == 'both':
                # Distance FeatureGroups (lines live here, same convention as
                # the TX/RX-only map below but inverted: there, distance
                # groups hold markers and country groups hold lines; here
                # direction groups hold markers and distance groups hold lines)
                fg_under_500 = folium.FeatureGroup(name='Under 500 km', show=True)
                fg_500_1000 = folium.FeatureGroup(name='500 – 1,000 km', show=True)
                fg_over_1000 = folium.FeatureGroup(name='Over 1,000 km', show=True)
                for fg in (fg_under_500, fg_500_1000, fg_over_1000):
                    fg.add_to(folium_map)

                # Direction FeatureGroups (markers live here)
                fg_tx = folium.FeatureGroup(name='TX Spots (heard you)', show=True)
                fg_rx = folium.FeatureGroup(name='RX Spots (you heard)', show=True)
                fg_symmetric = folium.FeatureGroup(name='Symmetric Paths', show=True)
                for fg in (fg_tx, fg_rx, fg_symmetric):
                    fg.add_to(folium_map)

                def distance_group_for(distance_km):
                    if distance_km < 500:
                        return 'green', fg_under_500
                    elif distance_km <= 1000:
                        return 'orange', fg_500_1000
                    return 'red', fg_over_1000

                tx_raw_data = tx_result['raw_data'] if tx_result and tx_result['raw_data'] is not None else None
                rx_raw_data = rx_result['raw_data'] if rx_result and rx_result['raw_data'] is not None else None

                tx_receivers = (
                    tx_raw_data.loc[tx_raw_data.groupby('rx_sign')['snr'].idxmax()]
                    if tx_raw_data is not None else None
                )
                rx_receivers = (
                    rx_raw_data.loc[rx_raw_data.groupby('rx_sign')['snr'].idxmax()]
                    if rx_raw_data is not None else None
                )

                if tx_receivers is not None:
                    for _, row in tx_receivers.iterrows():
                        colour, distance_group = distance_group_for(row['distance'])
                        popup_html = (
                            f"<b>{row['rx_sign']}</b><br>"
                            f"Distance: {row['distance']:.0f} km<br>"
                            f"Best SNR: {row['snr']} dB<br>"
                            f"Grid: {row['rx_loc']}"
                        )
                        folium.CircleMarker(
                            location=[row['rx_lat'], row['rx_lon']],
                            radius=6,
                            popup=folium.Popup(popup_html, max_width=220),
                            color=colour,
                            fill=True,
                            fillColor=colour,
                            fillOpacity=0.8
                        ).add_to(fg_tx)
                        folium.PolyLine(
                            locations=[[tx_lat, tx_lon], [row['rx_lat'], row['rx_lon']]],
                            color=colour,
                            weight=2,
                            opacity=0.7
                        ).add_to(distance_group)

                if rx_receivers is not None:
                    for _, row in rx_receivers.iterrows():
                        colour, distance_group = distance_group_for(row['distance'])
                        popup_html = (
                            f"<b>{row['rx_sign']}</b><br>"
                            f"Distance: {row['distance']:.0f} km<br>"
                            f"Best SNR: {row['snr']} dB<br>"
                            f"Grid: {row['rx_loc']}"
                        )
                        folium.CircleMarker(
                            location=[row['rx_lat'], row['rx_lon']],
                            radius=8,
                            popup=folium.Popup(popup_html, max_width=220),
                            color=colour,
                            fill=False
                        ).add_to(fg_rx)
                        folium.PolyLine(
                            locations=[[row['rx_lat'], row['rx_lon']], [tx_lat, tx_lon]],
                            color=colour,
                            weight=2,
                            opacity=0.7
                        ).add_to(distance_group)

                if tx_receivers is not None and symmetric_calls:
                    symmetric_rows = tx_receivers[tx_receivers['rx_sign'].isin(symmetric_calls)]
                    for _, row in symmetric_rows.iterrows():
                        _, distance_group = distance_group_for(row['distance'])
                        popup_html = f"<b>{row['rx_sign']}</b><br>Two-way path confirmed"
                        folium.CircleMarker(
                            location=[row['rx_lat'], row['rx_lon']],
                            radius=10,
                            popup=folium.Popup(popup_html, max_width=220),
                            color='#FFD700',
                            fill=True,
                            fillColor='#FFD700',
                            fillOpacity=0.9
                        ).add_to(fg_symmetric)
                        folium.PolyLine(
                            locations=[[tx_lat, tx_lon], [row['rx_lat'], row['rx_lon']]],
                            color='#FFD700',
                            weight=3,
                            opacity=0.9
                        ).add_to(distance_group)

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
                        'Direction': [fg_tx, fg_rx, fg_symmetric],
                        'Distance': [fg_under_500, fg_500_1000, fg_over_1000]
                    },
                    exclusive_groups=False,
                    collapsed=True,
                    position='topright'
                ).add_to(folium_map)
            else:
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
        config=config,
        mode=mode,
        tx_summaryData=tx_result['summaryData'] if tx_result else None,
        rx_summaryData=rx_result['summaryData'] if rx_result else None,
        tx_distanceList=tx_result['distanceList'] if tx_result else [],
        rx_distanceList=rx_result['distanceList'] if rx_result else [],
        tx_countryList=tx_result['countryList'] if tx_result else [],
        rx_countryList=rx_result['countryList'] if rx_result else [],
        tx_best_snr_value=best_snr_value if mode == 'both' else None,
        rx_best_snr_value=rx_result['best_snr_value'] if rx_result else None,
        tx_best_snr_call=best_snr_call if mode == 'both' else None,
        rx_best_snr_call=rx_result['best_snr_call'] if rx_result else None,
        tx_best_snr_distance=best_snr_distance if mode == 'both' else None,
        rx_best_snr_distance=rx_result['best_snr_distance'] if rx_result else None,
        symmetric_count=symmetric_count,
        symmetric_calls=symmetric_calls,
        combined_spots=combined_spots,
        combined_unique=combined_unique,
        combined_countries=combined_countries
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
            active_tab = request.form.get('active_tab', '')
            redirect_url = request.path + active_tab if active_tab else request.url
            return redirect(redirect_url)

    mode = config.get('Mode', 'tx')
    if mode not in ('tx', 'rx'):
        mode = 'tx'
    data_rows, error = WSPR_Analytics.getData(config['CallSign'], config['Period'], mode=mode)

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

SHARE_CARD_FONT_DIR = '/usr/share/fonts/truetype/dejavu'
SHARE_CARD_FONT_CANDIDATES = {
    'bold': 'DejaVuSans-Bold.ttf',
    'regular': 'DejaVuSans.ttf',
}

def load_share_card_font(weight, size):
    font_name = SHARE_CARD_FONT_CANDIDATES.get(weight, SHARE_CARD_FONT_CANDIDATES['regular'])
    try:
        return ImageFont.truetype(os.path.join(SHARE_CARD_FONT_DIR, font_name), size)
    except Exception as e:
        logger.warning(f"Failed to load font {font_name}: {e}; falling back to PIL default")
        return ImageFont.load_default()

def draw_centred_text(draw, y, text, font, fill, width=600):
    text_width = draw.textlength(text, font=font)
    x = (width - text_width) / 2
    draw.text((x, y), text, font=font, fill=fill)

def draw_mixed_line(draw, x, y, segments):
    for text, font, fill in segments:
        draw.text((x, y), text, font=font, fill=fill)
        x += draw.textlength(text, font=font)
    return x

@app.route('/export-card')
def export_card():
    if not session.get('config_saved', False):
        return redirect(url_for('index'))

    config = load_config(CONFIG_FILE)
    callsign = config.get('CallSign', 'Unknown')
    period = config.get('Period', '')

    if not os.path.exists(RAW_DATA_CSV_PATH):
        return jsonify({"error": "No data available. Submit a query first."}), 404

    try:
        raw_data = pd.read_csv(RAW_DATA_CSV_PATH)
        if raw_data.empty:
            return jsonify({"error": "No data available."}), 404

        raw_time = pd.to_datetime(raw_data['time'])
        dataset_start_dt = raw_time.min()
        date_display = dataset_start_dt.strftime('%-d %B %Y')
        date_for_filename = dataset_start_dt.strftime('%Y-%m-%d')

        total_spots = int(len(raw_data))
        unique_stations = int(raw_data['rx_sign'].nunique())

        best_row = raw_data.loc[raw_data['snr'].idxmax()]
        best_snr_value = int(best_row['snr'])
        best_snr_call = best_row['rx_sign']
        best_snr_distance = int(best_row['distance'])

        countries_path = os.path.join(WSPR_Analytics.DATA_DIR, f"{WSPR_Analytics.COUNTRIES_NAME}.{WSPR_Analytics.FMT_CSV}")
        top_countries = []
        if os.path.exists(countries_path):
            countries_df = pd.read_csv(countries_path)
            countries_df = countries_df[countries_df['Country'] != 'Unknown']
            top_countries = countries_df['Country'].head(5).tolist()

        distances_path = os.path.join(WSPR_Analytics.DATA_DIR, f"{WSPR_Analytics.DISTANCES_NAME}.{WSPR_Analytics.FMT_CSV}")
        best_dx_call = 'N/A'
        best_dx_km = 0
        if os.path.exists(distances_path):
            distances_df = pd.read_csv(distances_path)
            if not distances_df.empty:
                best_dx_call = distances_df.iloc[0]['rx_sign']
                best_dx_km = int(distances_df.iloc[0]['distance'])
    except Exception as e:
        logger.warning(f"Failed to build share card data: {e}")
        return jsonify({"error": f"Failed to read data: {e}"}), 404

    width, height = 600, 420
    colour_dark = '#343a40'
    colour_muted_light = '#adb5bd'
    colour_text_dark = '#212529'
    colour_label = '#6c757d'
    colour_body = '#495057'
    colour_light_bg = '#f8f9fa'
    colour_border = '#343a40'

    img = Image.new('RGB', (width, height), '#FFFFFF')
    draw = ImageDraw.Draw(img)

    font_header_bold = load_share_card_font('bold', 22)
    font_header_sub = load_share_card_font('regular', 14)
    font_metric_value = load_share_card_font('bold', 36)
    font_metric_label = load_share_card_font('regular', 12)
    font_body_bold = load_share_card_font('bold', 15)
    font_body_regular = load_share_card_font('regular', 15)
    font_countries_label = load_share_card_font('bold', 12)
    font_countries_line = load_share_card_font('regular', 16)
    font_footer_1 = load_share_card_font('regular', 13)
    font_footer_2 = load_share_card_font('regular', 12)

    # Section 1 — Header (y 0-80)
    draw.rectangle([0, 0, width, 80], fill=colour_dark)
    draw_centred_text(draw, 18, f"{callsign} — WSPR Beacon Report", font_header_bold, '#FFFFFF')
    draw_centred_text(draw, 50, f"{date_display} · {period}", font_header_sub, colour_muted_light)

    # Section 2 — Key metrics (y 80-180)
    draw.line([(0, 80), (width, 80)], fill='#dee2e6', width=1)
    col_width = width / 2
    metric_value_y = 105
    metric_label_y = 150
    total_spots_text = str(total_spots)
    unique_stations_text = str(unique_stations)
    tw = draw.textlength(total_spots_text, font=font_metric_value)
    draw.text(((col_width - tw) / 2, metric_value_y), total_spots_text, font=font_metric_value, fill=colour_text_dark)
    lw = draw.textlength('STATIONS HEARD', font=font_metric_label)
    draw.text(((col_width - lw) / 2, metric_label_y), 'STATIONS HEARD', font=font_metric_label, fill=colour_label)

    uw = draw.textlength(unique_stations_text, font=font_metric_value)
    draw.text((col_width + (col_width - uw) / 2, metric_value_y), unique_stations_text, font=font_metric_value, fill=colour_text_dark)
    ulw = draw.textlength('UNIQUE STATIONS', font=font_metric_label)
    draw.text((col_width + (col_width - ulw) / 2, metric_label_y), 'UNIQUE STATIONS', font=font_metric_label, fill=colour_label)

    draw.line([(col_width, 90), (col_width, 170)], fill='#dee2e6', width=1)

    # Section 3 — DX and SNR (y 180-260)
    draw.line([(0, 180), (width, 180)], fill='#dee2e6', width=1)
    pad_x = 24
    draw_mixed_line(draw, pad_x, 200, [
        ('Best DX:  ', font_body_bold, colour_text_dark),
        (f"{best_dx_call}  {best_dx_km} km", font_body_regular, colour_body),
    ])
    draw_mixed_line(draw, pad_x, 228, [
        ('Best SNR: ', font_body_bold, colour_text_dark),
        (f"{best_snr_call}  {best_snr_value} dB  {best_snr_distance} km", font_body_regular, colour_body),
    ])

    # Section 4 — Top Countries (y 260-340)
    draw.rectangle([0, 260, width, 340], fill=colour_light_bg)
    label_text = 'TOP COUNTRIES'
    lblw = draw.textlength(label_text, font=font_countries_label)
    draw.text(((width - lblw) / 2, 275), label_text, font=font_countries_label, fill=colour_label)
    countries_line = ' · '.join(top_countries) if top_countries else 'N/A'
    draw_centred_text(draw, 300, countries_line, font_countries_line, colour_text_dark)

    # Section 5 — Footer (y 340-420)
    draw.rectangle([0, 340, width, height], fill=colour_dark)
    draw_centred_text(draw, 362, 'Generated by WSPR Analytics', font_footer_1, colour_muted_light)
    draw_centred_text(draw, 385, 'github.com/MusicalLoop/WSPR_Analytics', font_footer_2, colour_label)

    # Border
    draw.rectangle([0, 0, width - 1, height - 1], outline=colour_border, width=2)

    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)

    return send_file(
        img_bytes,
        mimetype='image/png',
        as_attachment=True,
        download_name=f'wspr_{callsign}_{date_for_filename}.png'
    )

def period_list():
    return [
        "10 minutes", "30 minutes", "1 hour", "3 hours", "6 hours", "12 hours", "1 day", "2 days", "3 days", "5 days", "7 days", "14 days"
    ]

if __name__ == '__main__':
    app.run(debug=True)
