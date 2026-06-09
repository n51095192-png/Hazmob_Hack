"""
Simple Flask API server — connects frontend to the MySQL database.
Run alongside bot.py on Railway (or any server).
"""

import json
from flask import Flask, jsonify
import mysql.connector

app = Flask(__name__)

DB_CONFIG = {
    'host': 'db4free.net',
    'database': 'noaprojectdb',
    'user': 'noaishere',
    'password': 'Mohammad86$',
    'port': 3306,
    'connection_timeout': 20,
}

STARRED = ['AmyraxVPN', 'prrofile_purple', 'vpn11ir', 'hex_proxy']


def get_conn():
    return mysql.connector.connect(**DB_CONFIG)


def fetch_rows(query, params=()):
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(query, params)
        return cur.fetchall()
    finally:
        conn.close()


@app.route('/api/data', methods=['GET'])
def get_all_data():
    try:
        npvt_rows = fetch_rows(
            "SELECT channel_name, file_name, file_content, is_starred FROM npvt_configs ORDER BY is_starred DESC, id DESC"
        )
        proxy_rows = fetch_rows(
            "SELECT channel_name, proxy_link, is_starred FROM proxy_configs ORDER BY is_starred DESC, id DESC"
        )
        config_rows = fetch_rows(
            "SELECT channel_name, config_type, config_data, is_starred FROM vpn_configs ORDER BY is_starred DESC, id DESC"
        )

        npvt = [
            {
                'id': f"n{i}",
                'channel': r['channel_name'],
                'config': r['file_content'],
                'fileName': r['file_name'],
                'starred': bool(r['is_starred']),
                'type': 'npvt',
            }
            for i, r in enumerate(npvt_rows)
        ]

        proxy = [
            {
                'id': f"p{i}",
                'channel': r['channel_name'],
                'config': r['proxy_link'],
                'starred': bool(r['is_starred']),
                'type': 'proxy',
            }
            for i, r in enumerate(proxy_rows)
        ]

        config = [
            {
                'id': f"c{i}",
                'channel': r['channel_name'],
                'config': r['config_data'],
                'starred': bool(r['is_starred']),
                'type': r['config_type'],
            }
            for i, r in enumerate(config_rows)
        ]

        return jsonify({'npvt': npvt, 'proxy': proxy, 'config': config})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(__import__('os').environ.get('PORT', 5000)))
