import pandas as pd
import numpy as np
import joblib
from sklearn.preprocessing import MinMaxScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.utils import to_categorical

# 🔥 Load Excel file
df = pd.read_excel("apple_modified_freshness_dataset.xlsx")

# 🔥 Select features
X = df[['MQ135', 'Temperature', 'Humidity']].values
y = df['Label'].values

# 🔥 Encode labels
le = LabelEncoder()
y_encoded = le.fit_transform(y)

# 🔥 Save label encoder
joblib.dump(le, "label_encoder.pkl")

# 🔥 Scale features
scaler = MinMaxScaler()
X_scaled = scaler.fit_transform(X)

# 🔥 Save scaler
joblib.dump(scaler, "scaler.pkl")

# 🔥 Reshape for LSTM (samples, timesteps, features)
X_scaled = X_scaled.reshape(X_scaled.shape[0], 1, 3)

# 🔥 One-hot encode labels
y_cat = to_categorical(y_encoded)

# 🔥 Split dataset
X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y_cat, test_size=0.2, random_state=42
)

# 🔥 Build LSTM model
model = Sequential([
    LSTM(64, input_shape=(1, 3), return_sequences=True),
    Dropout(0.2),
    LSTM(32),
    Dropout(0.2),
    Dense(16, activation='relu'),
    Dense(len(le.classes_), activation='softmax')
])

model.compile(
    optimizer='adam',
    loss='categorical_crossentropy',
    metrics=['accuracy']
)

print("🚀 Training LSTM...")
model.fit(X_train, y_train, epochs=30, batch_size=16, validation_data=(X_test, y_test))

# 🔥 Save in NEW recommended format (NO WARNING)
model.save("apple_lstm_model.keras")

print("✅ Model Saved Successfully!")