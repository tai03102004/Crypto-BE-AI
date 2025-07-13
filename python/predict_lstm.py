import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import numpy as np
import pandas as pd
from tensorflow.keras.models import load_model
from datetime import timedelta
import joblib
import json

# Load model
model = load_model("python/models/lstm_model.keras")

# Load scalers (dictionary)
scalers = joblib.load("python/models/scalers.joblib")
close_scaler = scalers['close']

# List of feature names
FEATURES = [
    'close', 'rsi_14', 'ema_30', 'sma_10', 'sma_50',
    'bb_upper', 'bb_lower', 'bb_width', 'bb_position',
    'price_sma10_ratio', 'price_sma50_ratio'
]

# =========================
# Feature calculation utils
# =========================
def calculate_rsi(prices, window=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_ema(prices, window=30):
    return prices.ewm(span=window, adjust=False).mean()

def calculate_sma(prices, window):
    return prices.rolling(window=window).mean()

def calculate_bollinger_bands(prices, window=20, num_std=2):
    sma = prices.rolling(window=window).mean()
    std = prices.rolling(window=window).std()
    upper = sma + (std * num_std)
    lower = sma - (std * num_std)
    return upper, lower

def engineer_features(df):
    """
    Tính đầy đủ 11 features
    """
    df = df.copy()
    df['rsi_14'] = calculate_rsi(df['close'])
    df['ema_30'] = calculate_ema(df['close'])
    df['sma_10'] = calculate_sma(df['close'], window=10)
    df['sma_50'] = calculate_sma(df['close'], window=50)
    bb_upper, bb_lower = calculate_bollinger_bands(df['close'])
    df['bb_upper'] = bb_upper
    df['bb_lower'] = bb_lower
    df['bb_width'] = df['bb_upper'] - df['bb_lower']
    df['bb_position'] = (df['close'] - df['bb_lower']) / df['bb_width']
    df['price_sma10_ratio'] = df['close'] / df['sma_10']
    df['price_sma50_ratio'] = df['close'] / df['sma_50']
    df = df.dropna().reset_index(drop=True)
    return df

# =========================
# Load and preprocess data
# =========================
def load_data():
    df = pd.read_csv("python/data/BTC.csv", usecols=["date","close"])
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    end_date = df['date'].max()
    start_date = end_date - timedelta(days=5*365)
    df = df[df['date'] >= start_date].reset_index(drop=True)
    return df

# =========================
# Predict function
# =========================
def predict():
    df = load_data()
    df_feat = engineer_features(df)
    
    seq_len = 30
    last_seq_df = df_feat.iloc[-seq_len:].reset_index(drop=True)
    
    # Scale all features
    scaled = np.zeros_like(last_seq_df[FEATURES].values)
    for i, col in enumerate(FEATURES):
        scaled[:, i] = scalers[col].transform(last_seq_df[col].values.reshape(-1,1)).flatten()
    
    # Predict next day
    inp = scaled.reshape(1, seq_len, scaled.shape[1])
    pred = model.predict(inp, verbose=0)[0,0]
    next_price = close_scaler.inverse_transform([[pred]])[0,0]
    
    # Multi-step forecast
    preds = []
    df_future = df.copy()
    for _ in range(7):
        # Append predicted close to df_future
        pred_close = close_scaler.inverse_transform([[pred]])[0,0]
        next_date = df_future['date'].iloc[-1] + timedelta(days=1)
        df_future = pd.concat([
            df_future,
            pd.DataFrame({'date':[next_date],'close':[pred_close]})
        ], ignore_index=True)
        
        # Recompute features
        df_feat_future = engineer_features(df_future)
        last_seq_df = df_feat_future.iloc[-seq_len:].reset_index(drop=True)
        
        # Scale
        scaled = np.zeros_like(last_seq_df[FEATURES].values)
        for i, col in enumerate(FEATURES):
            scaled[:, i] = scalers[col].transform(last_seq_df[col].values.reshape(-1,1)).flatten()
        
        # Predict next
        inp = scaled.reshape(1, seq_len, scaled.shape[1])
        pred = model.predict(inp, verbose=0)[0,0]
        preds.append(pred)
    
    # Inverse transform all predictions
    dummy_multi = np.zeros((len(preds),1))
    dummy_multi[:,0] = preds
    multi_prices = close_scaler.inverse_transform(dummy_multi).flatten().tolist()
    
    return next_price, multi_prices

# =========================
# Main
# =========================
if __name__ == "__main__":
    next_day, multi = predict()
    print(json.dumps({
        "next_day": next_day,
        "multi_step": multi
    }))
