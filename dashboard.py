import os

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

email_sent = False


# 🔥 ML PREDICTION FUNCTION
def predict_spoilage(mq135, temp, hum):

    scaled = scaler.transform([[mq135, temp, hum]])
    input_data = scaled.reshape(1, 1, 3)

    pred = model.predict(input_data, verbose=0)[0]

    idx   = np.argmax(pred)
    label = le.inverse_transform([idx])[0]

    confidence    = float(np.max(pred) * 100)
    fresh_prob    = float(pred[0] * 100)
    ripening_prob = float(pred[1] * 100)
    spoiled_prob  = float(pred[2] * 100)

    risk_percent = (ripening_prob * 0.6 + spoiled_prob * 1.0)

    sensor_risk = 0
    temp_risk   = min(max((temp - 20) / 15 * 25, 0), 25)
    sensor_risk += temp_risk

    if hum > 85:
        sensor_risk += min((hum - 85) * 1, 5)

    if mq135 > 400:
        sensor_risk += min((mq135 - 400) * 0.02, 10)

    risk_percent = min(100, risk_percent + sensor_risk)

    print(f"ML Probs: F:{fresh_prob:.1f}% R:{ripening_prob:.1f}% S:{spoiled_prob:.1f}%")
    print(f"Sensor Risk: +{sensor_risk:.1f}% → Total Risk: {risk_percent:.1f}%")

    return label, confidence, round(risk_percent, 1)


# 📧 EMAIL ALERT FUNCTION
def send_email_alert(temp, hum, mq135):

    sender_email   = "kaliesboopathy@gmail.com"
    receiver_email = "anbu200516@gmail.com"
    app_password   = "dkapfvmfpwtgawku"

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
    msg['From']    = sender_email
    msg['To']      = receiver_email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)
        server.quit()
        print("📧 Email Alert Sent!")

    except Exception as e:
        print(f"❌ Email Error: {e}")


# 🔥 ESP8266 DATA ROUTE — accepts both GET and POST
@app.route("/update", methods=["GET", "POST"])
def update():

    global latest_data
    global email_sent

    try:
        # ✅ Read from POST body OR GET query params — whichever has data
        if request.method == "POST":
            raw_mq135 = request.form.get("mq135") or request.args.get("mq135")
            raw_temp  = request.form.get("temp")  or request.args.get("temp")
            raw_hum   = request.form.get("hum")   or request.args.get("hum")
            print(f"🔍 POST form: {request.form}  args: {request.args}")
        else:
            raw_mq135 = request.args.get("mq135")
            raw_temp  = request.args.get("temp")
            raw_hum   = request.args.get("hum")
            print(f"🔍 GET args: {request.args}")

        # ✅ Guard: reject if any param is missing
        if raw_mq135 is None or raw_temp is None or raw_hum is None:
            print(f"⚠️ Missing params → mq135={raw_mq135} temp={raw_temp} hum={raw_hum}")
            return jsonify({"status": "error", "reason": "missing parameters"}), 400

        mq135 = int(float(raw_mq135))
        temp  = round(float(raw_temp), 1)
        hum   = round(float(raw_hum), 1)

        print(f"📥 Received → Temp: {temp}°C  Hum: {hum}%  MQ135: {mq135}")

        # ML Prediction
        label, confidence, spoil_risk = predict_spoilage(mq135, temp, hum)

        # Send email only once when ripening starts
        if label.lower() == "ripening" and not email_sent:
            send_email_alert(temp, hum, mq135)
            email_sent = True

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        latest_data = {
            "label"      : str(label),
            "confidence" : round(float(confidence), 2),
            "spoil_risk" : round(float(spoil_risk), 1),
            "mq135"      : int(mq135),
            "temp"       : float(temp),
            "hum"        : float(hum),
            "timestamp"  : current_time
        }

        print(f"📊 Sending to Firebase: {latest_data}")

        # 🔥 Firebase push — isolated error handling
        try:
            firebase_ref.push(latest_data)
            print("✅ Firebase Saved Successfully!")
        except Exception as firebase_err:
            print(f"❌ Firebase Push Error: {firebase_err}")

        return jsonify({"status": "ok", "data": latest_data})

    except ValueError as e:
        print(f"❌ Invalid value: {e}")
        return jsonify({"status": "error", "reason": "invalid parameter value"}), 400

    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        return jsonify({"status": "error", "reason": str(e)}), 500


# 🔥 DASHBOARD ROUTES
@app.route("/")
def index():
    return send_from_directory('.', 'index.html')


@app.route("/data")
def data():
    return jsonify(latest_data)


# 🔥 START SERVER
if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run_server(host='0.0.0.0', port=port, debug=False)
