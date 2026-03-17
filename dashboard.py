import os
import json
from flask import Flask, request, jsonify, send_from_directory
import numpy as np
import joblib
from tensorflow import keras
from datetime import datetime, timezone, timedelta
import firebase_admin
from firebase_admin import credentials, db
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__, static_folder='.')

# ─────────────────────────────────────
# TIMEZONE — IST
# ─────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))

# ─────────────────────────────────────
# FIREBASE CONNECTION
# ─────────────────────────────────────
firebase_key_json = json.loads(os.environ.get("FIREBASE_KEY"))
cred = credentials.Certificate(firebase_key_json)

firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://applemonitor-d8626-default-rtdb.firebaseio.com/'
})

firebase_ref = db.reference("sensor_data")
print("🔥 Firebase Connected!")

# ─────────────────────────────────────
# LOAD ML MODEL
# ─────────────────────────────────────
print("🔄 Loading LSTM model...")
model  = keras.models.load_model('apple_lstm_model.h5')
scaler = joblib.load('scaler.pkl')
le     = joblib.load('label_encoder.pkl')
print("✅ Model Loaded!")

latest_data = {
    "label"      : "Waiting...",
    "confidence" : 0,
    "spoil_risk" : 0,
    "mq135"      : 0,
    "temp"       : 0,
    "hum"        : 0,
    "timestamp"  : ""
}

email_sent = False


# ─────────────────────────────────────
# ML PREDICTION
# ─────────────────────────────────────
def predict_spoilage(mq135, temp, hum):

    scaled     = scaler.transform([[mq135, temp, hum]])
    input_data = scaled.reshape(1, 1, 3)

    pred = model.predict(input_data, verbose=0)[0]

    idx   = np.argmax(pred)
    label = le.inverse_transform([idx])[0]

    confidence    = float(np.max(pred) * 100)
    fresh_prob    = float(pred[0] * 100)
    ripening_prob = float(pred[1] * 100)
    spoiled_prob  = float(pred[2] * 100)

    # Risk calculation
    risk_percent = (ripening_prob * 0.6 + spoiled_prob * 1.0)

    sensor_risk = 0

    # Temperature risk
    temp_risk    = min(max((temp - 20) / 15 * 25, 0), 25)
    sensor_risk += temp_risk

    # Humidity risk
    if hum > 85:
        sensor_risk += min((hum - 85) * 1, 5)

    # Gas risk
    if mq135 > 400:
        sensor_risk += min((mq135 - 400) * 0.02, 10)

    risk_percent = min(100, risk_percent + sensor_risk)

    print(f"ML Probs  : Fresh={fresh_prob:.1f}%  Ripening={ripening_prob:.1f}%  Spoiled={spoiled_prob:.1f}%")
    print(f"Sensor Risk: +{sensor_risk:.1f}%  →  Total Risk: {risk_percent:.1f}%")

    return label, confidence, round(risk_percent, 1)


# ─────────────────────────────────────
# EMAIL ALERT
# ─────────────────────────────────────
def send_email_alert(temp, hum, mq135, label):

    sender_email   = "kaliesboopathy@gmail.com"
    receiver_email = "anbu200516@gmail.com"
    app_password   = "dkapfvmfpwtgawku"

    if label.lower() == "ripening":
        subject = "🍎 Apple Ripening Started!"
        body    = f"""
Apple Ripening has started!

Sensor Readings:
──────────────────
Temperature : {temp} °C
Humidity    : {hum} %
Gas Level   : {mq135}
Status      : {label}
Time (IST)  : {datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")}
──────────────────

Please check the storage condition immediately.
"""

    elif label.lower() == "spoiled":
        subject = "🚨 Apple Spoiled Alert!"
        body    = f"""
Apple has SPOILED!

Sensor Readings:
──────────────────
Temperature : {temp} °C
Humidity    : {hum} %
Gas Level   : {mq135}
Status      : {label}
Time (IST)  : {datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")}
──────────────────

Immediate action required!
"""

    msg            = MIMEText(body)
    msg['Subject'] = subject
    msg['From']    = sender_email
    msg['To']      = receiver_email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)
        server.quit()
        print(f"📧 Email Alert Sent → {subject}")

    except Exception as e:
        print(f"❌ Email Error: {e}")


# ─────────────────────────────────────
# ESP8266 DATA ROUTE
# ─────────────────────────────────────
@app.route("/update", methods=["GET", "POST"])
def update():

    global latest_data
    global email_sent

    try:
        if request.method == "POST":
            raw_mq135 = request.form.get("mq135") or request.args.get("mq135")
            raw_temp  = request.form.get("temp")  or request.args.get("temp")
            raw_hum   = request.form.get("hum")   or request.args.get("hum")
            print(f"🔍 POST → form: {request.form}  args: {request.args}")
        else:
            raw_mq135 = request.args.get("mq135")
            raw_temp  = request.args.get("temp")
            raw_hum   = request.args.get("hum")
            print(f"🔍 GET → args: {request.args}")

        # Guard — reject if any param missing
        if raw_mq135 is None or raw_temp is None or raw_hum is None:
            print(f"⚠️ Missing params → mq135={raw_mq135} temp={raw_temp} hum={raw_hum}")
            return jsonify({"status": "error", "reason": "missing parameters"}), 400

        mq135 = int(float(raw_mq135))
        temp  = round(float(raw_temp), 1)
        hum   = round(float(raw_hum), 1)

        print(f"📥 Received → Temp: {temp}°C  Hum: {hum}%  MQ135: {mq135}")

        # ML Prediction
        label, confidence, spoil_risk = predict_spoilage(mq135, temp, hum)

        # Email alert — ripening (once)
        if label.lower() == "ripening" and not email_sent:
            send_email_alert(temp, hum, mq135, label)
            email_sent = True

        # Email alert — spoiled (every time)
        if label.lower() == "spoiled":
            send_email_alert(temp, hum, mq135, label)

        # IST timestamp
        current_time = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

        latest_data = {
            "label"      : str(label),
            "confidence" : round(float(confidence), 2),
            "spoil_risk" : round(float(spoil_risk), 1),
            "mq135"      : int(mq135),
            "temp"       : float(temp),
            "hum"        : float(hum),
            "timestamp"  : current_time
        }

        print(f"📊 Result → Label: {label}  Risk: {spoil_risk}%  Time: {current_time}")

        # Save to Firebase
        try:
            firebase_ref.push(latest_data)
            print("✅ Firebase Saved!")
        except Exception as firebase_err:
            print(f"❌ Firebase Error: {firebase_err}")

        return jsonify({"status": "ok", "data": latest_data})

    except ValueError as e:
        print(f"❌ Invalid value: {e}")
        return jsonify({"status": "error", "reason": "invalid parameter value"}), 400

    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        return jsonify({"status": "error", "reason": str(e)}), 500


# ─────────────────────────────────────
# DASHBOARD ROUTES
# ─────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory('.', 'index.html')


@app.route("/data")
def data():
    return jsonify(latest_data)


# ─────────────────────────────────────
# START SERVER
# ─────────────────────────────────────
if __name__ == "__main__":
    print("🌐 Dashboard Running")
    print("👉 http://localhost:5000")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)