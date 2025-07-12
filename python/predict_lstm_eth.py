import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import numpy as np
import pandas as pd
from tensorflow.keras.models import load_model
import joblib
from datetime import timedelta
import json

model = load_model("python/models/lstm_eth_model.keras")
scaler = joblib.load("python/models/scaler_eth.save")

def calculate_rsi(prices, window=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_ema(prices, window=30):
    return prices.ewm(span=window, adjust=False).mean()

def load_latest_data():
    df = pd.read_csv("python/data/ETH.csv")
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    end_date = df['date'].max()
    start_date = end_date - timedelta(days=5*365)
    df = df[df['date'] >= start_date].reset_index(drop=True)

    df['rsi_14'] = calculate_rsi(df['close'])
    df['ema_30'] = calculate_ema(df['close'])
    df = df.dropna().reset_index(drop=True)

    features = ['close', 'rsi_14', 'ema_30']
    return df[features].values

def predict():
    data = load_latest_data()
    scaled = scaler.transform(data)
    seq_len = 30
    last_seq = scaled[-seq_len:].reshape(1, seq_len, scaled.shape[1])

    pred = model.predict(last_seq, verbose=0)
    dummy = np.zeros((1, scaled.shape[1]))
    dummy[0,0] = pred[0,0]
    next_price = scaler.inverse_transform(dummy)[0,0]

    # Multi-step forecast
    preds = []
    curr = scaled[-seq_len:].copy()
    for _ in range(7):
        inp = curr.reshape(1, seq_len, scaled.shape[1])
        p = model.predict(inp, verbose=0)[0,0]
        preds.append(p)
        new_row = curr[-1].copy()
        new_row[0] = p
        curr = np.vstack([curr[1:], new_row])

    dummy_multi = np.zeros((len(preds), scaled.shape[1]))
    dummy_multi[:,0] = preds
    multi_prices = scaler.inverse_transform(dummy_multi)[:,0].tolist()

    return next_price, multi_prices

if __name__ == "__main__":
    next_day, multi = predict()
    print(json.dumps({
        "next_day": next_day,
        "multi_step": multi
    }))
