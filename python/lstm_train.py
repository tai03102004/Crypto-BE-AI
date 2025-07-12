import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
import matplotlib.pyplot as plt
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.losses import Huber
from datetime import datetime, timedelta
import joblib
import warnings
warnings.filterwarnings('ignore')

def calculate_rsi(prices, window=14):
    """
    Calculate Relative Strength Index (RSI) using pandas rolling functions
    """
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_ema(prices, window=30):
    """
    Calculate Exponential Moving Average (EMA) using pandas
    """
    return prices.ewm(span=window, adjust=False).mean()

def load_and_prepare_data(csv_file):
    """
    Load and prepare Bitcoin data with technical indicators
    """
    # Read CSV file
    df = pd.read_csv(csv_file)
    
    # Convert date column to datetime
    df['date'] = pd.to_datetime(df['date'])
    
    # Sort by date ascending
    df = df.sort_values('date').reset_index(drop=True)
    
    # Filter to last 5 years of data
    end_date = df['date'].max()
    start_date = end_date - timedelta(days=5*365)
    df = df[df['date'] >= start_date].reset_index(drop=True)
    
    print(f"Data loaded: {len(df)} records from {df['date'].min()} to {df['date'].max()}")
    
    return df

def engineer_features(df):
    """
    Create technical features: Close, RSI, EMA
    """
    # Calculate technical indicators
    df['rsi_14'] = calculate_rsi(df['close'], window=14)
    df['ema_30'] = calculate_ema(df['close'], window=30)
    
    # Select features for training
    features = ['close', 'rsi_14', 'ema_30']
    
    # Drop rows with NaN values (due to rolling calculations)
    df_features = df[features].dropna().reset_index(drop=True)
    
    print(f"Features engineered: {df_features.shape}")
    print(f"Features: {features}")
    
    return df_features.values, features

def normalize_features(data):
    """
    Normalize all features to [0,1] range using MinMaxScaler
    """
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(data)
    return scaled_data, scaler

def create_sequences(data, sequence_length, target_column=0):
    """
    Create input sequences for LSTM training
    Each sequence contains 'sequence_length' days of all features to predict next day's close price
    """
    X, y = [], []
    for i in range(sequence_length, len(data)):
        # Input: sequence_length previous days of all features
        X.append(data[i-sequence_length:i, :])
        # Output: next day's close price (first column)
        y.append(data[i, target_column])
    
    return np.array(X), np.array(y)

def build_lstm_model(input_shape):
    """
    Build LSTM model architecture with multiple layers
    - First LSTM layer with 64 units and return_sequences=True
    - Second LSTM layer with 32 units
    - Dense output layer
    """
    model = Sequential()
    
    # First LSTM layer with 64 units, return sequences for next layer
    model.add(LSTM(64, return_sequences=True, input_shape=input_shape))
    
    # Second LSTM layer with 32 units
    model.add(LSTM(32))
    
    # Dense output layer
    model.add(Dense(1))
    
    # Compile with Huber loss and Adam optimizer
    model.compile(optimizer='adam', loss=Huber())
    
    return model

def plot_predictions(actual, predicted, title="Actual vs Predicted Bitcoin Prices"):
    """
    Plot actual vs predicted closing prices
    """
    plt.figure(figsize=(15, 8))
    plt.plot(actual, label='Actual Prices', color='blue', linewidth=2)
    plt.plot(predicted, label='Predicted Prices', color='red', linewidth=2)
    plt.title(title, fontsize=16)
    plt.xlabel('Time', fontsize=12)
    plt.ylabel('Bitcoin Price (USD)', fontsize=12)
    plt.legend(fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

def plot_training_history(history):
    """
    Plot training and validation loss
    """
    plt.figure(figsize=(12, 5))
    
    plt.subplot(1, 2, 1)
    plt.plot(history.history['loss'], label='Training Loss')
    plt.plot(history.history['val_loss'], label='Validation Loss')
    plt.title('Model Loss')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()

def train_lstm_model(csv_file):
    """
    Complete pipeline to train LSTM model with technical features
    """
    # Load and prepare data
    print("Step 1: Loading and preparing data...")
    df = load_and_prepare_data(csv_file)
    
    # Engineer technical features
    print("Step 2: Engineering technical features...")
    feature_data, feature_names = engineer_features(df)
    
    # Normalize all features to [0,1] range
    print("Step 3: Normalizing features...")
    scaled_data, scaler = normalize_features(feature_data)
    
    # Create input sequences with length 30
    print("Step 4: Creating input sequences...")
    sequence_length = 30
    X, y = create_sequences(scaled_data, sequence_length, target_column=0)
    
    print(f"Created {X.shape[0]} sequences with shape {X.shape}")
    print(f"Target shape: {y.shape}")
    
    # Split data into training (80%) and test (20%) sets
    print("Step 5: Splitting data...")
    train_size = int(len(X) * 0.8)
    X_train, X_test = X[:train_size], X[train_size:]
    y_train, y_test = y[:train_size], y[train_size:]
    
    print(f"Training set: {X_train.shape[0]} samples")
    print(f"Test set: {X_test.shape[0]} samples")
    
    # Build LSTM model
    print("Step 6: Building LSTM model...")
    model = build_lstm_model((X_train.shape[1], X_train.shape[2]))
    
    print("Model architecture:")
    model.summary()
    
    # Setup EarlyStopping callback
    early_stopping = EarlyStopping(
        monitor='val_loss',
        patience=3,
        restore_best_weights=True,
        verbose=1
    )
    
    # Train the model for up to 50 epochs with batch size 32
    print("Step 7: Training model...")
    history = model.fit(
        X_train, y_train,
        epochs=50,
        batch_size=32,
        validation_split=0.1,
        callbacks=[early_stopping],
        verbose=1
    )
    
    # Plot training history
    plot_training_history(history)
    
    # Make predictions on test set
    print("Step 8: Making predictions...")
    test_predictions = model.predict(X_test)
    
    # Inverse transform predictions back to original scale
    # Create dummy array with same shape as original features for inverse transform
    dummy_features = np.zeros((len(test_predictions), scaled_data.shape[1]))
    dummy_features[:, 0] = test_predictions.flatten()
    test_predictions_scaled = scaler.inverse_transform(dummy_features)[:, 0]
    
    # Inverse transform actual values
    dummy_actual = np.zeros((len(y_test), scaled_data.shape[1]))
    dummy_actual[:, 0] = y_test
    y_test_actual = scaler.inverse_transform(dummy_actual)[:, 0]
    
    # Plot actual vs predicted prices
    print("Step 9: Plotting results...")
    plot_predictions(y_test_actual, test_predictions_scaled)
    
    # Calculate and print performance metrics
    mse = np.mean((y_test_actual - test_predictions_scaled) ** 2)
    mae = np.mean(np.abs(y_test_actual - test_predictions_scaled))
    mape = np.mean(np.abs((y_test_actual - test_predictions_scaled) / y_test_actual)) * 100
    
    print(f"Test MSE: ${mse:.2f}")
    print(f"Test MAE: ${mae:.2f}")
    print(f"Test MAPE: {mape:.2f}%")
    
    # Save the trained model and scaler
    print("Step 10: Saving model and scaler...")
    model.save("python/models/lstm_model.keras")
    joblib.dump(scaler, "python/models/scaler.save")
    print("Model saved as 'lstm_model.keras'")
    print("Scaler saved as 'scaler.save'")

    np.save("python/models/scaled_data.npy", scaled_data)
    print("Scaled data saved as 'scaled_data.npy'")

    
    return model, scaler, scaled_data, feature_names

def predict_next_day(model, scaler, scaled_data, sequence_length=30):
    """
    Predict the next day's Bitcoin closing price
    """
    # Get the last 30 days of data (all features)
    last_sequence = scaled_data[-sequence_length:].reshape(1, sequence_length, scaled_data.shape[1])
    
    # Make prediction
    next_day_prediction = model.predict(last_sequence, verbose=0)
    
    # Inverse transform to get actual price
    dummy_features = np.zeros((1, scaled_data.shape[1]))
    dummy_features[0, 0] = next_day_prediction[0, 0]
    next_day_price = scaler.inverse_transform(dummy_features)[0, 0]
    
    return next_day_price

def predict_multi_step(model, scaler, scaled_data, num_days=7, sequence_length=30):
    """
    Predict multiple days ahead (multi-step forecasting)
    """
    predictions = []
    current_sequence = scaled_data[-sequence_length:].copy()
    
    for i in range(num_days):
        # Reshape for prediction
        sequence_input = current_sequence.reshape(1, sequence_length, scaled_data.shape[1])
        
        # Make prediction
        next_prediction = model.predict(sequence_input, verbose=0)[0, 0]
        
        # Store prediction
        predictions.append(next_prediction)
        
        # Update sequence for next prediction
        # Create new row with predicted close price and last known values for other features
        new_row = current_sequence[-1].copy()
        new_row[0] = next_prediction  # Update close price
        
        # Shift sequence and add new prediction
        current_sequence = np.vstack([current_sequence[1:], new_row])
    
    # Inverse transform predictions
    dummy_features = np.zeros((len(predictions), scaled_data.shape[1]))
    dummy_features[:, 0] = predictions
    predicted_prices = scaler.inverse_transform(dummy_features)[:, 0]
    
    return predicted_prices

if __name__ == "__main__":
    # Set random seeds for reproducibility
    np.random.seed(42)
    tf.random.set_seed(42)
    
    print("Bitcoin Price Prediction using LSTM with Technical Features")
    print("=" * 60)
    
    try:
        # Train the model
        model, scaler, scaled_data, feature_names = train_lstm_model("python/data/BTC.csv")
        
        # Predict next day's price based on last 30 days
        print("\nStep 11: Predicting next day's price...")
        next_day_price = predict_next_day(model, scaler, scaled_data)
        
        print(f"\nPredicted next day's Bitcoin closing price: ${next_day_price:.2f}")
        
        # Multi-step forecast for next 7 days
        print("\nStep 12: Multi-step forecasting for next 7 days...")
        multi_predictions = predict_multi_step(model, scaler, scaled_data, num_days=7)
        
        print("\n7-Day Price Forecast:")
        print("-" * 30)
        for i, price in enumerate(multi_predictions, 1):
            print(f"Day +{i}: ${price:.2f}")
        
        print("\nTraining completed successfully!")
        print("\nFiles created:")
        print("- lstm_model.keras (trained model)")
        print("- scaler.save (feature scaler)")
        
        print(f"\nFeatures used: {feature_names}")
        
    except FileNotFoundError:
        print("Error: 'BTC.csv' file not found!")
        print("Please ensure the CSV file exists and contains 'date', 'close' columns.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()