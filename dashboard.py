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
# FIREBASE
# ─────────────────────────────────────
firebase_key_json = json.loads(os.environ.get("FIREBASE_KEY"))
cred = credentials.Certificate(firebase_key_json)

firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://applemonitor-d8626-default-rtdb.firebaseio.com/'
})

firebase_ref = db.reference("sensor_data")
print("🔥 Firebase Connected!")

# ─────────────────────────────────────
# LOAD MODEL
# ─────────────────────────────────────
print("🔄 Loading LSTM model...")
model  = keras.models.load_model('apple_lstm_model.h5')
scaler = joblib.load('scaler.pkl')
le     = joblib.load('label_encoder.pkl')
print("✅ Model Loaded!")

# ─────────────────────────────────────
# 🔥 BASELINE (IMPORTANT)
# ─────────────────────────────────────
MQ_BASELINE = 250   # 🔥 CHANGE after measuring clean air

# ─────────────────────────────────────
# EMAIL CONTROL
# ─────────────────────────────────────
last_email_time = None
EMAIL_INTERVAL = 300  # 5 min

latest_data = {
    "label":"Waiting...",
    "confidence":0,
    "spoil_risk":0,
    "mq135":0,
    "temp":0,
    "hum":0,
    "timestamp":""
}

# ─────────────────────────────────────
# ML PREDICTION (WITH BASELINE FIX)
# ─────────────────────────────────────
def predict_spoilage(mq135, temp, hum):

    # ✅ BASELINE CORRECTION
    mq_diff = max(mq135 - MQ_BASELINE, 0)

    # Use corrected value
    scaled = scaler.transform([[mq_diff, temp, hum]])
    input_data = scaled.reshape(1,1,3)

    pred = model.predict(input_data, verbose=0)[0]

    idx   = np.argmax(pred)
    label = le.inverse_transform([idx])[0]

    fresh_prob    = float(pred[0]*100)
    ripening_prob = float(pred[1]*100)
    spoiled_prob  = float(pred[2]*100)

    confidence = float(np.max(pred)*100)

    # 🔥 ML RISK
    risk_percent = spoiled_prob + (ripening_prob * 0.5)

    # 🔥 SMALL SENSOR ADJUSTMENT (STABILITY)
    if mq_diff > 150:
        risk_percent += 5
    if temp > 32:
        risk_percent += 5

    risk_percent = min(100, max(0, risk_percent))

    print(f"MQ Raw={mq135}  Diff={mq_diff}")
    print(f"ML → F:{fresh_prob:.1f}% R:{ripening_prob:.1f}% S:{spoiled_prob:.1f}%")
    print(f"Risk → {risk_percent:.1f}%")

    return label, confidence, round(risk_percent,1)

# ─────────────────────────────────────
# EMAIL ALERT
# ─────────────────────────────────────
def send_email_alert(temp, hum, mq135, label):

    sender_email   = "kaliesboopathy@gmail.com"
    receiver_email = "anbu200516@gmail.com"
    app_password   = "bqfkqmskhhndegbj"

    subject = f"🍎 Apple Status: {label.upper()}"

    body = f"""
Apple Status Alert!

Status      : {label}
Temperature : {temp} °C
Humidity    : {hum} %
Gas Level   : {mq135}
Time (IST)  : {datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")}

Check system.
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
        print("📧 Email Sent!")
    except Exception as e:
        print("❌ Email Error:", e)

# ─────────────────────────────────────
# UPDATE ROUTE
# ─────────────────────────────────────
@app.route("/update", methods=["GET","POST"])
def update():

    global latest_data, last_email_time

    try:
        raw_mq135 = request.args.get("mq135")
        raw_temp  = request.args.get("temp")
        raw_hum   = request.args.get("hum")

        if raw_mq135 is None or raw_temp is None or raw_hum is None:
            return jsonify({"error":"missing parameters"}),400

        mq135 = int(float(raw_mq135))
        temp  = round(float(raw_temp),1)
        hum   = round(float(raw_hum),1)

        label, confidence, spoil_risk = predict_spoilage(mq135, temp, hum)

        # 🔥 SMART EMAIL SYSTEM
        now = datetime.now()

        if label.lower() in ["ripening","spoiled"]:
            if last_email_time is None or (now - last_email_time).seconds > EMAIL_INTERVAL:
                send_email_alert(temp, hum, mq135, label)
                last_email_time = now

        current_time = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

        latest_data = {
            "label":label,
            "confidence":round(confidence,2),
            "spoil_risk":spoil_risk,
            "mq135":mq135,
            "temp":temp,
            "hum":hum,
            "timestamp":current_time
        }

        firebase_ref.push(latest_data)

        return jsonify({"status":"ok","data":latest_data})

    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"error":str(e)}),500

# ─────────────────────────────────────
# ROUTES
# ─────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory('.', 'index.html')

@app.route("/data")
def data():
    return jsonify(latest_data)

# ─────────────────────────────────────
# RUN
# ─────────────────────────────────────
if __name__ == "__main__":
    print("🌐 Server Running...")
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port)