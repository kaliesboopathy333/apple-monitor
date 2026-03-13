from flask import Flask, request, jsonify, send_from_directory
import numpy as np
import joblib
from tensorflow import keras
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, db
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__, static_folder='.')

# 🔥 FIREBASE CONNECTION
cred = credentials.Certificate("servicesAccountKey.json")

firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://applemonitor-d8626-default-rtdb.firebaseio.com/'
})

firebase_ref = db.reference("sensor_data")

print("🔥 Firebase Connected!")

# 🔥 LOAD ML MODEL
print("🔄 Loading LSTM model...")
model = keras.models.load_model('apple_lstm_model.keras')
scaler = joblib.load('scaler.pkl')
le = joblib.load('label_encoder.pkl')
print("✅ Model Loaded!")

latest_data = {
    "label": "Waiting...",
    "confidence": 0,
    "spoil_risk": 0,
    "mq135": 0,
    "temp": 0,
    "hum": 0,
    "timestamp": ""
}

# Email flag (prevents multiple alerts)
email_sent = False


# 🔥 ML PREDICTION FUNCTION
def predict_spoilage(mq135, temp, hum):

    scaled = scaler.transform([[mq135, temp, hum]])
    input_data = scaled.reshape(1,1,3)

    pred = model.predict(input_data, verbose=0)[0]

    idx = np.argmax(pred)
    label = le.inverse_transform([idx])[0]

    confidence = float(np.max(pred) * 100)

    fresh_prob = pred[0] * 100
    ripening_prob = pred[1] * 100
    spoiled_prob = pred[2] * 100

    # ML risk calculation
    risk_percent = (ripening_prob * 0.6 + spoiled_prob * 1.0)

    # Sensor based risk
    sensor_risk = 0

    # Temperature risk
    temp_risk = min(max((temp - 20) / 15 * 25, 0), 25)
    sensor_risk += temp_risk

    # Humidity risk
    if hum > 85:
        sensor_risk += min((hum - 85) * 1, 5)

    # Gas risk
    if mq135 > 400:
        sensor_risk += min((mq135 - 400) * 0.02, 10)

    risk_percent = min(100, risk_percent + sensor_risk)

    print(f"ML Probs: F:{fresh_prob:.1f}% R:{ripening_prob:.1f}% S:{spoiled_prob:.1f}%")
    print(f"Sensor Risk: +{sensor_risk:.1f}% → Total Risk: {risk_percent:.1f}%")

    return label, confidence, round(risk_percent,1)


# 📧 EMAIL ALERT FUNCTION
def send_email_alert(temp, hum, mq135):

    sender_email = "kaliesboopathy@gmail.com"
    receiver_email = "anbu200516@gmail.com"
    app_password = "dkapfvmfpwtgawku"

    subject = "Apple Ripening Started 🍎"

    body = f"""
Apple ripening has started.

Sensor Data:
Temperature: {temp} °C
Humidity: {hum} %
Gas Level: {mq135}

Please check the storage condition.
"""

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = receiver_email

    try:

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, app_password)

        server.send_message(msg)
        server.quit()

        print("📧 Email Alert Sent!")

    except Exception as e:
        print("Email error:", e)


# 🔥 ESP8266 DATA ROUTE
@app.route("/update", methods=["GET"])
def update():

    global latest_data
    global email_sent

    try:

        mq135 = float(request.args.get("mq135"))
        temp = float(request.args.get("temp"))
        hum = float(request.args.get("hum"))

        # ML Prediction
        label, confidence, spoil_risk = predict_spoilage(mq135, temp, hum)

        # Send email only once when ripening starts
        if label.lower() == "ripening" and not email_sent:
            send_email_alert(temp, hum, mq135)
            email_sent = True

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        latest_data = {
            "label": label,
            "confidence": round(confidence,2),
            "spoil_risk": spoil_risk,
            "mq135": mq135,
            "temp": temp,
            "hum": hum,
            "timestamp": current_time
        }

        # Save to Firebase
        firebase_ref.push(latest_data)

        print("📊 Data Stored:", latest_data)

        return jsonify({"status":"ok"})

    except Exception as e:

        print("❌ Error:", e)
        return jsonify({"status":"error"})


# 🔥 DASHBOARD ROUTES
@app.route("/")
def index():
    return send_from_directory('.', 'index.html')


@app.route("/data")
def data():
    return jsonify(latest_data)


# 🔥 START SERVER
if __name__ == "__main__":

    print("🌐 Dashboard Running")
    print("👉 http://localhost:5000")

    app.run(host="0.0.0.0", port=5000, debug=True)