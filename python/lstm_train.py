import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
import matplotlib.pyplot as plt
import seaborn as sns
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.losses import Huber
from datetime import datetime, timedelta
import joblib
import warnings
import json
import os
from typing import Tuple, List, Dict, Any

warnings.filterwarnings('ignore')

# =============================================================================
# MODEL HYPERPARAMETERS
# =============================================================================
HYPERPARAMS = {
    'sequence_length': 30,
    'batch_size': 32,
    'epochs': 100,
    'patience_early_stop': 10,
    'patience_lr_reduce': 5,
    'validation_split': 0.1,
    'test_split': 0.2,
    'lstm_units_1': 64,
    'lstm_units_2': 32,
    'dropout_rate': 0.2,
    'learning_rate_factor': 0.5,
    'min_learning_rate': 1e-7
}

# Technical indicator calculation parameters
TECH_PARAMS = {
    'rsi_window': 14,
    'ema_window': 30,
    'sma_10_window': 10,
    'sma_50_window': 50,
    'bollinger_window': 20,
    'bollinger_std': 2
}


def calculate_rsi(prices: pd.Series, window: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index momentum oscillator.
    
    Args:
        prices: Price series
        window: Period for RSI calculation
        
    Returns:
        RSI values as pandas Series
    """
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_ema(prices: pd.Series, window: int = 30) -> pd.Series:
    """
    Calculate Exponential Moving Average with exponentially decreasing weights.
    
    Args:
        prices: Price series
        window: Period for EMA calculation
        
    Returns:
        EMA values as pandas Series
    """
    return prices.ewm(span=window, adjust=False).mean()


def calculate_sma(prices: pd.Series, window: int) -> pd.Series:
    """
    Calculate Simple Moving Average as arithmetic mean.
    
    Args:
        prices: Price series
        window: Period for SMA calculation
        
    Returns:
        SMA values as pandas Series
    """
    return prices.rolling(window=window).mean()


def calculate_bollinger_bands(prices: pd.Series, window: int = 20, 
                            num_std: int = 2) -> Tuple[pd.Series, pd.Series]:
    """
    Calculate Bollinger Bands volatility indicator.
    
    Args:
        prices: Price series
        window: Period for moving average calculation
        num_std: Number of standard deviations for band width
        
    Returns:
        Tuple of (upper_band, lower_band)
    """
    sma = prices.rolling(window=window).mean()
    std = prices.rolling(window=window).std()
    upper_band = sma + (std * num_std)
    lower_band = sma - (std * num_std)
    return upper_band, lower_band


def load_and_prepare_data(csv_file: str) -> pd.DataFrame:
    """
    Load Bitcoin price data and filter to recent years for model training.
    
    Args:
        csv_file: Path to CSV file containing OHLCV data
        
    Returns:
        Prepared DataFrame with recent price data
        
    Raises:
        Exception: If data validation fails or insufficient records
    """
    # Load Bitcoin price data
    df = pd.read_csv(csv_file)
    
    # Check for required price columns
    required_columns = ['date', 'close']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")
    
    # Parse date column for time series analysis
    df['date'] = pd.to_datetime(df['date'])
    
    # Sort chronologically for time series modeling
    df = df.sort_values('date').reset_index(drop=True)
    
    # Use last 10 years of data for training
    end_date = df['date'].max()
    start_date = end_date - timedelta(days=10*365)
    df = df[df['date'] >= start_date].reset_index(drop=True)
    
    # Ensure sufficient data points for LSTM training
    if len(df) < 100:
        raise Exception(f"Insufficient data: only {len(df)} records found. "
                       f"Need at least 100 records for training.")
    
    print(f"Data loaded: {len(df)} records from {df['date'].min()} to {df['date'].max()}")
    
    return df


def engineer_features(df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
    """
    Calculate technical indicators and derived features for LSTM model.
    
    Args:
        df: Input DataFrame with OHLCV price data
        
    Returns:
        Tuple of (feature_array, feature_names)
    """
    # Calculate momentum and trend indicators
    df['rsi_14'] = calculate_rsi(df['close'], window=TECH_PARAMS['rsi_window'])
    df['ema_30'] = calculate_ema(df['close'], window=TECH_PARAMS['ema_window'])
    df['sma_10'] = calculate_sma(df['close'], window=TECH_PARAMS['sma_10_window'])
    df['sma_50'] = calculate_sma(df['close'], window=TECH_PARAMS['sma_50_window'])
    
    # Calculate volatility indicators
    bb_upper, bb_lower = calculate_bollinger_bands(
        df['close'], 
        window=TECH_PARAMS['bollinger_window'],
        num_std=TECH_PARAMS['bollinger_std']
    )
    df['bb_upper'] = bb_upper
    df['bb_lower'] = bb_lower
    
    # Create derived features for better price pattern recognition
    df['bb_width'] = df['bb_upper'] - df['bb_lower']  # Market volatility measure
    df['bb_position'] = (df['close'] - df['bb_lower']) / df['bb_width']  # Price position in bands
    df['price_sma10_ratio'] = df['close'] / df['sma_10']  # Short-term trend strength
    df['price_sma50_ratio'] = df['close'] / df['sma_50']  # Long-term trend strength
    
    # Select feature set for model training
    features = [
        'close', 'rsi_14', 'ema_30', 'sma_10', 'sma_50',
        'bb_upper', 'bb_lower', 'bb_width', 'bb_position',
        'price_sma10_ratio', 'price_sma50_ratio'
    ]
    
    # Remove rows with NaN values from rolling calculations
    df_features = df[features].dropna().reset_index(drop=True)
    
    # Verify sufficient feature data for model training
    if len(df_features) < 100:
        raise Exception(f"Insufficient feature data: only {len(df_features)} records "
                       f"after feature engineering. Need at least 100 records.")
    
    print(f"Features engineered: {df_features.shape}")
    print(f"Features: {features}")
    
    return df_features.values, features


def normalize_features(data: np.ndarray, feature_names: List[str]) -> Tuple[np.ndarray, Dict[str, MinMaxScaler]]:
    """
    Apply individual normalization to each feature for optimal LSTM training.
    
    Args:
        data: Raw feature array
        feature_names: List of feature names
        
    Returns:
        Tuple of (scaled_data, scalers_dict)
    """
    scalers = {}
    scaled_data = np.zeros_like(data)
    
    for i, feature_name in enumerate(feature_names):
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaled_data[:, i] = scaler.fit_transform(data[:, i].reshape(-1, 1)).flatten()
        scalers[feature_name] = scaler
    
    print(f"Applied individual scaling to {len(feature_names)} features")
    
    return scaled_data, scalers


def create_sequences(data: np.ndarray, sequence_length: int, 
                    target_column: int = 0) -> Tuple[np.ndarray, np.ndarray]:
    """
    Create sliding window sequences for LSTM time series training.
    
    Args:
        data: Normalized feature data
        sequence_length: Number of previous time steps to use as input
        target_column: Index of target column (close price)
        
    Returns:
        Tuple of (X, y) arrays for supervised learning
    """
    X, y = [], []
    for i in range(sequence_length, len(data)):
        # Input: historical sequence of all features
        X.append(data[i-sequence_length:i, :])
        # Target: next period's close price
        y.append(data[i, target_column])
    
    return np.array(X), np.array(y)


def build_enhanced_lstm_model(input_shape: Tuple[int, int]) -> Sequential:
    """
    Build LSTM neural network with dropout regularization for price prediction.
    
    Args:
        input_shape: Shape of input sequences (sequence_length, n_features)
        
    Returns:
        Compiled Keras LSTM model
    """
    model = Sequential()
    
    # Primary LSTM layer for sequence pattern learning
    model.add(LSTM(
        HYPERPARAMS['lstm_units_1'], 
        return_sequences=True, 
        input_shape=input_shape,
        name='lstm_1'
    ))
    model.add(Dropout(HYPERPARAMS['dropout_rate'], name='dropout_1'))
    
    # Secondary LSTM layer for higher-level pattern extraction
    model.add(LSTM(HYPERPARAMS['lstm_units_2'], name='lstm_2'))
    model.add(Dropout(HYPERPARAMS['dropout_rate'], name='dropout_2'))
    
    # Output layer for price prediction
    model.add(Dense(1, name='output'))
    
    # Use Huber loss for robustness to outliers
    model.compile(optimizer='adam', loss=Huber(), metrics=['mae'])
    
    return model


def plot_enhanced_results(actual: np.ndarray, predicted: np.ndarray, 
                         save_dir: str) -> None:
    """
    Generate comprehensive visualization of model performance.
    
    Args:
        actual: Actual Bitcoin prices
        predicted: Model predicted prices
        save_dir: Directory to save plot files
    """
    # Create output directory for plots
    os.makedirs(save_dir, exist_ok=True)
    
    # Time series comparison plot
    plt.figure(figsize=(15, 8))
    plt.plot(actual, label='Actual Prices', color='blue', linewidth=2, alpha=0.7)
    plt.plot(predicted, label='Predicted Prices', color='red', linewidth=2, alpha=0.7)
    plt.title('Actual vs Predicted Bitcoin Prices', fontsize=16, fontweight='bold')
    plt.xlabel('Time Steps', fontsize=12)
    plt.ylabel('Bitcoin Price (USD)', fontsize=12)
    plt.legend(fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{save_dir}/price_comparison.png", dpi=300, bbox_inches='tight')
    plt.show()
    
    # Prediction accuracy scatter plot
    plt.figure(figsize=(10, 8))
    plt.scatter(actual, predicted, alpha=0.6, color='purple', s=20)
    
    # Perfect prediction reference line
    min_price = min(actual.min(), predicted.min())
    max_price = max(actual.max(), predicted.max())
    plt.plot([min_price, max_price], [min_price, max_price], 
             'r--', linewidth=2, label='Perfect Prediction')
    
    plt.xlabel('Actual Prices (USD)', fontsize=12)
    plt.ylabel('Predicted Prices (USD)', fontsize=12)
    plt.title('Actual vs Predicted Prices Scatter Plot', fontsize=14, fontweight='bold')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Display correlation coefficient
    correlation_matrix = np.corrcoef(actual, predicted)
    r_squared = correlation_matrix[0, 1] ** 2
    plt.text(0.05, 0.95, f'R² = {r_squared:.4f}', 
             transform=plt.gca().transAxes, fontsize=12,
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    plt.tight_layout()
    plt.savefig(f"{save_dir}/scatter_plot.png", dpi=300, bbox_inches='tight')
    plt.show()


def plot_training_history(history: tf.keras.callbacks.History, 
                         save_dir: str) -> None:
    """
    Visualize LSTM model training progress and validation performance.
    
    Args:
        history: Keras training history object
        save_dir: Directory to save training plots
    """
    os.makedirs(save_dir, exist_ok=True)
    
    plt.figure(figsize=(15, 5))
    
    # Training and validation loss progression
    plt.subplot(1, 2, 1)
    plt.plot(history.history['loss'], label='Training Loss', color='blue')
    plt.plot(history.history['val_loss'], label='Validation Loss', color='orange')
    plt.title('Model Loss', fontsize=14, fontweight='bold')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Training and validation accuracy progression
    plt.subplot(1, 2, 2)
    plt.plot(history.history['mae'], label='Training MAE', color='green')
    plt.plot(history.history['val_mae'], label='Validation MAE', color='red')
    plt.title('Model MAE', fontsize=14, fontweight='bold')
    plt.xlabel('Epoch')
    plt.ylabel('Mean Absolute Error')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(f"{save_dir}/training_history.png", dpi=300, bbox_inches='tight')
    plt.show()


def save_training_history(history: tf.keras.callbacks.History, 
                         save_dir: str) -> None:
    """
    Save training metrics and hyperparameters to JSON file.
    
    Args:
        history: Keras training history object
        save_dir: Directory to save history file
    """
    os.makedirs(save_dir, exist_ok=True)
    
    history_dict = {
        'loss': history.history['loss'],
        'val_loss': history.history['val_loss'],
        'mae': history.history['mae'],
        'val_mae': history.history['val_mae'],
        'epochs': len(history.history['loss']),
        'hyperparameters': HYPERPARAMS,
        'technical_parameters': TECH_PARAMS
    }
    
    with open(f"{save_dir}/training_history.json", 'w') as f:
        json.dump(history_dict, f, indent=2)
    
    print(f"Training history saved to: {save_dir}/training_history.json")


def calculate_metrics(actual: np.ndarray, predicted: np.ndarray) -> Dict[str, float]:
    """
    Calculate comprehensive evaluation metrics for price prediction model.
    
    Args:
        actual: True Bitcoin prices
        predicted: Model predicted prices
        
    Returns:
        Dictionary of performance metrics
    """
    mse = np.mean((actual - predicted) ** 2)
    mae = np.mean(np.abs(actual - predicted))
    rmse = np.sqrt(mse)
    mape = np.mean(np.abs((actual - predicted) / actual)) * 100
    
    # Coefficient of determination
    ss_res = np.sum((actual - predicted) ** 2)
    ss_tot = np.sum((actual - np.mean(actual)) ** 2)
    r2 = 1 - (ss_res / ss_tot)
    
    # Direction prediction accuracy
    actual_direction = np.diff(actual) > 0
    predicted_direction = np.diff(predicted) > 0
    directional_accuracy = np.mean(actual_direction == predicted_direction) * 100
    
    return {
        'mse': mse,
        'mae': mae,
        'rmse': rmse,
        'mape': mape,
        'r2': r2,
        'directional_accuracy': directional_accuracy
    }


def train_enhanced_lstm_model(csv_file: str) -> Tuple[Sequential, Dict[str, MinMaxScaler], 
                                                    np.ndarray, List[str]]:
    """
    Complete pipeline for training LSTM Bitcoin price prediction model.
    
    Args:
        csv_file: Path to Bitcoin price CSV file
        
    Returns:
        Tuple of (trained_model, feature_scalers, scaled_data, feature_names)
    """
    # Setup output directories
    model_dir = "python/models"
    plots_dir = "python/plots"
    os.makedirs(model_dir, exist_ok=True)
    os.makedirs(plots_dir, exist_ok=True)
    
    print("Bitcoin Price Prediction using LSTM Neural Network")
    print("=" * 60)
    
    # Load Bitcoin price data
    print("Step 1: Loading and preparing Bitcoin price data...")
    df = load_and_prepare_data(csv_file)
    
    # Calculate technical indicators for feature engineering
    print("Step 2: Engineering technical analysis features...")
    feature_data, feature_names = engineer_features(df)
    
    # Normalize features for optimal neural network training
    print("Step 3: Normalizing features for neural network...")
    scaled_data, scalers = normalize_features(feature_data, feature_names)
    
    # Create time series sequences for LSTM training
    print("Step 4: Creating time series sequences...")
    X, y = create_sequences(scaled_data, HYPERPARAMS['sequence_length'], target_column=0)
    
    print(f"Created {X.shape[0]} sequences with shape {X.shape}")
    print(f"Target shape: {y.shape}")
    
    # Split data into training and testing sets
    print("Step 5: Splitting data into train/test sets...")
    train_size = int(len(X) * (1 - HYPERPARAMS['test_split']))
    X_train, X_test = X[:train_size], X[train_size:]
    y_train, y_test = y[:train_size], y[train_size:]
    
    print(f"Training set: {X_train.shape[0]} samples")
    print(f"Test set: {X_test.shape[0]} samples")
    
    # Build LSTM neural network architecture
    print("Step 6: Building LSTM neural network...")
    model = build_enhanced_lstm_model((X_train.shape[1], X_train.shape[2]))
    
    print("Model architecture:")
    model.summary()
    
    # Setup training callbacks for optimization
    early_stopping = EarlyStopping(
        monitor='val_loss',
        patience=HYPERPARAMS['patience_early_stop'],
        restore_best_weights=True,
        verbose=1
    )
    
    reduce_lr = ReduceLROnPlateau(
        monitor='val_loss',
        factor=HYPERPARAMS['learning_rate_factor'],
        patience=HYPERPARAMS['patience_lr_reduce'],
        min_lr=HYPERPARAMS['min_learning_rate'],
        verbose=1
    )
    
    # Train LSTM model on Bitcoin price sequences
    print("Step 7: Training LSTM model...")
    history = model.fit(
        X_train, y_train,
        epochs=HYPERPARAMS['epochs'],
        batch_size=HYPERPARAMS['batch_size'],
        validation_split=HYPERPARAMS['validation_split'],
        callbacks=[early_stopping, reduce_lr],
        verbose=1
    )
    
    # Generate training performance visualizations
    plot_training_history(history, plots_dir)
    save_training_history(history, model_dir)
    
    # Generate predictions on test set
    print("Step 8: Generating price predictions...")
    test_predictions = model.predict(X_test, verbose=0)
    
    # Convert normalized predictions back to actual price scale
    close_scaler = scalers['close']
    test_predictions_scaled = close_scaler.inverse_transform(test_predictions).flatten()
    y_test_actual = close_scaler.inverse_transform(y_test.reshape(-1, 1)).flatten()
    
    # Evaluate model performance with multiple metrics
    print("Step 9: Evaluating model performance...")
    metrics = calculate_metrics(y_test_actual, test_predictions_scaled)
    
    print("\nModel Performance Metrics:")
    print("-" * 30)
    for metric, value in metrics.items():
        if metric == 'directional_accuracy':
            print(f"{metric.upper()}: {value:.2f}%")
        elif metric in ['mape']:
            print(f"{metric.upper()}: {value:.2f}%")
        elif metric in ['r2']:
            print(f"{metric.upper()}: {value:.4f}")
        else:
            print(f"{metric.upper()}: ${value:.2f}")
    
    # Create prediction accuracy visualizations
    print("Step 10: Creating prediction visualizations...")
    plot_enhanced_results(y_test_actual, test_predictions_scaled, plots_dir)
    
    # Save trained model and preprocessing components
    print("Step 11: Saving trained model and scalers...")
    model_filename = f"{model_dir}/lstm_model.keras"
    scalers_filename = f"{model_dir}/scalers.joblib"
    scaled_data_filename = f"{model_dir}/scaled_data.npy"
    
    model.save(model_filename)
    joblib.dump(scalers, scalers_filename)
    np.save(scaled_data_filename, scaled_data)
    
    print(f"Model saved as: {model_filename}")
    print(f"Scalers saved as: {scalers_filename}")
    print(f"Scaled data saved as: {scaled_data_filename}")
    
    # Save model configuration and performance metrics
    config = {
        'feature_names': feature_names,
        'hyperparameters': HYPERPARAMS,
        'technical_parameters': TECH_PARAMS,
        'metrics': metrics
    }
    
    config_filename = f"{model_dir}/config.json"
    with open(config_filename, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Configuration saved as: {config_filename}")
    
    return model, scalers, scaled_data, feature_names


def predict_next_day(model: Sequential, scalers: Dict[str, MinMaxScaler], 
                    scaled_data: np.ndarray, sequence_length: int = None) -> float:
    """
    Predict next day's Bitcoin closing price using trained LSTM model.
    
    Args:
        model: Trained LSTM model
        scalers: Feature normalization scalers
        scaled_data: Normalized historical feature data
        sequence_length: Input sequence length for prediction
        
    Returns:
        Predicted Bitcoin closing price
    """
    if sequence_length is None:
        sequence_length = HYPERPARAMS['sequence_length']
    
    # Extract recent historical sequence for prediction
    last_sequence = scaled_data[-sequence_length:].reshape(1, sequence_length, scaled_data.shape[1])
    
    # Generate price prediction
    next_day_prediction = model.predict(last_sequence, verbose=0)
    
    # Convert normalized prediction back to actual price
    close_scaler = scalers['close']
    next_day_price = close_scaler.inverse_transform(next_day_prediction)[0, 0]
    
    return next_day_price


def predict_multi_step(model: Sequential, scalers: Dict[str, MinMaxScaler], 
                      scaled_data: np.ndarray, num_days: int = 7, 
                      sequence_length: int = None) -> np.ndarray:
    """
    Generate multi-day price forecasts using iterative prediction.
    
    Args:
        model: Trained LSTM model
        scalers: Feature normalization scalers
        scaled_data: Normalized historical feature data
        num_days: Number of future days to predict
        sequence_length: Input sequence length for prediction
        
    Returns:
        Array of predicted Bitcoin prices for future days
    """
    if sequence_length is None:
        sequence_length = HYPERPARAMS['sequence_length']
    
    predictions = []
    current_sequence = scaled_data[-sequence_length:].copy()
    
    for i in range(num_days):
        # Prepare sequence for prediction
        sequence_input = current_sequence.reshape(1, sequence_length, scaled_data.shape[1])
        
        # Generate next day prediction
        next_prediction = model.predict(sequence_input, verbose=0)[0, 0]
        
        # Store prediction for output
        predictions.append(next_prediction)
        
        # Update sequence with new prediction for next iteration
        new_row = current_sequence[-1].copy()
        new_row[0] = next_prediction  # Update close price with prediction
        
        # Shift sequence window forward
        current_sequence = np.vstack([current_sequence[1:], new_row])
    
    # Convert normalized predictions to actual price scale
    close_scaler = scalers['close']
    predicted_prices = close_scaler.inverse_transform(np.array(predictions).reshape(-1, 1)).flatten()
    
    return predicted_prices


if __name__ == "__main__":
    # Set random seeds for reproducible results
    np.random.seed(42)
    tf.random.set_seed(42)
    
    try:
        # Execute complete model training pipeline
        model, scalers, scaled_data, feature_names = train_enhanced_lstm_model("python/data/BTC.csv")
        
        # Generate next day price prediction
        print("\nStep 12: Predicting next day's Bitcoin price...")
        next_day_price = predict_next_day(model, scalers, scaled_data)
        
        print(f"\nPredicted next day's Bitcoin closing price: ${next_day_price:.2f}")
        
        # Generate extended price forecast
        print("\nStep 13: Generating 7-day price forecast...")
        multi_predictions = predict_multi_step(model, scalers, scaled_data, num_days=7)
        
        print("\n7-Day Bitcoin Price Forecast:")
        print("-" * 30)
        for i, price in enumerate(multi_predictions, 1):
            print(f"Day +{i}: ${price:.2f}")
        
        print("\nLSTM model training completed successfully!")
        print("\nGenerated files:")
        print(f"- lstm_model.keras (trained LSTM model)")
        print(f"- scalers.joblib (feature normalization scalers)")
        print(f"- config.json (model configuration and metrics)")
        print(f"- training_history.json (training performance data)")
        print(f"- Visualization plots in python/plots/ directory")
        
        print(f"\nTechnical features used: {feature_names}")
        
    except FileNotFoundError:
        print("Error: 'python/data/BTC.csv' file not found!")
        print("Please ensure the CSV file exists and contains 'date', 'close' columns.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()