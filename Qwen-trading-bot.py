import os
import requests
import yaml
import sqlite3
import time
from datetime import datetime

class DexScreenerBot:
    def __init__(self):
        self.load_config()
        self.db = sqlite3.connect('token_analysis.db')
        self.init_db()
        self.tg_api_url = f"https://api.telegram.org/bot{self.config['tg_bot_token']}/sendMessage"

    def load_config(self):
        with open('config.yaml') as f:
            self.config = yaml.safe_load(f)
            
        self.coin_blacklist = set(open(self.config['files']['coin_blacklist']).read().splitlines())
        self.dev_blacklist = set(open(self.config['files']['dev_blacklist']).read().splitlines())

    def init_db(self):
        self.db.execute('''CREATE TABLE IF NOT EXISTS tokens (
            address TEXT PRIMARY KEY,
            symbol TEXT,
            created_at INTEGER,
            volume REAL,
            is_rug INTEGER,
            is_pump INTEGER,
            dev_address TEXT,
            last_checked INTEGER
        )''')

    def fetch_dexscreener_data(self):
        url = "https://api.dexscreener.com/latest/dex/pairs/new"
        params = {'limit': 100}
        return requests.get(url, params=params).json()

    def check_rugcheck(self, address):
        try:
            response = requests.get(f"http://rugcheck.xyz/api/check/{address}")
            data = response.json()
            return data.get('score', 0) > 80 and not data.get('is_bundle', False)
        except:
            return False

    def check_pocker_universe(self, address):
        try:
            response = requests.post(self.config['pocker_api_url'],
                                   json={'address': address})
            return response.json().get('fake_volume', False)
        except:
            return True

    def analyze_tokens(self):
        data = self.fetch_dexscreener_data()
        for pair in data['pairs']:
            if self.should_process(pair):
                self.process_pair(pair)

    def should_process(self, pair):
        filters = self.config['filters']
        return (
            pair['baseToken']['address'] not in self.coin_blacklist and
            pair['creator'] not in self.dev_blacklist and
            pair['liquidity']['usd'] > filters['min_liquidity'] and
            pair['volume']['h24'] > filters['min_volume'] and
            time.time() - pair['pairCreatedAt']/1000 < filters['max_age']
        )

    def process_pair(self, pair):
        address = pair['baseToken']['address']
        if self.check_pocker_universe(address):
            self.coin_blacklist.add(address)
            return

        if not self.check_rugcheck(address):
            return

        self.save_token(pair)
        self.execute_trade(pair)

    def save_token(self, pair):
        self.db.execute('''INSERT OR REPLACE INTO tokens VALUES 
            (?, ?, ?, ?, ?, ?, ?, ?)''', (
            pair['baseToken']['address'],
            pair['baseToken']['symbol'],
            pair['pairCreatedAt'],
            pair['volume']['h24'],
            0,  # is_rug
            0,  # is_pump
            pair['creator'],
            int(time.time())
        ))
        self.db.commit()

    def execute_trade(self, pair):
        message = f"🚀 Buy {pair['baseToken']['symbol']} at {pair['priceUsd']}"
        params = {
            'chat_id': self.config['tg_chat_id'],
            'text': message,
            'parse_mode': 'HTML'
        }
        requests.post(self.tg_api_url, params=params)
        # Add ToxiSol TG integration here using their API

    def monitor_rugs(self):
        # Implement rug detection logic using price/liquidity changes
        pass

    def send_alert(self, message):
        params = {
            'chat_id': self.config['tg_alert_chat_id'],
            'text': message,
            'parse_mode': 'HTML'
        }
        requests.post(self.tg_api_url, params=params)

if __name__ == "__main__":
    bot = DexScreenerBot()
    while True:
        bot.analyze_tokens()
        time.sleep(300)
        
        
        