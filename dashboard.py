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

# 🔥 FIREBASE
cred = credentials.Certificate("servicesAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://applemonitor-d8626-default-rtdb.firebaseio.com/'
})
firebase_ref = db.reference("sensor_data")

print("🔥 Firebase Connected!")

# 🔥 LOAD MODEL
model = keras.models.load_model('apple_lstm_model.keras')
scaler = joblib.load('scaler.pkl')
le = joblib.load('label_encoder.pkl')

print("✅ Model Loaded!")

# 🔥 GLOBALS
MQ_BASELINE = 200   # 🔥 CHANGE after measuring clean air
SEQ_LENGTH = 10

sequence_buffer = []
last_email_time = None
EMAIL_INTERVAL = 300  # 5 min

latest_data = {
    "label": "Waiting...",
    "confidence": 0,
    "spoil_risk": 0,
    "mq135": 0,
    "temp": 0,
    "hum": 0,
    "timestamp": ""
}

# 🔥 RULE BASED FALLBACK
def rule_based_prediction(mq_diff, temp, hum):

    if mq_diff < 80 and temp < 28:
        return "Fresh", 85, 10

    elif mq_diff < 180:
        return "Ripening", 80, 40

    else:
        return "Spoiled", 90, 80


# 🔥 ML + HYBRID PREDICTION
def predict_spoilage(mq135, temp, hum):

    global sequence_buffer

    # ✅ Baseline correction
    mq_diff = max(mq135 - MQ_BASELINE, 0)

    # Prepare input
    input_features = [mq_diff, temp, hum]
    scaled = scaler.transform([input_features])[0]

    sequence_buffer.append(scaled)

    if len(sequence_buffer) > SEQ_LENGTH:
        sequence_buffer.pop(0)

    # 🔥 If not enough data → fallback
    if len(sequence_buffer) < SEQ_LENGTH:
        return rule_based_prediction(mq_diff, temp, hum)

    # 🔥 LSTM Prediction
    seq = np.array(sequence_buffer).reshape(1, SEQ_LENGTH, 3)

    pred = model.predict(seq, verbose=0)[0]

    idx = np.argmax(pred)
    label = le.inverse_transform([idx])[0]
    confidence = float(np.max(pred) * 100)

    fresh_prob = pred[0] * 100
    ripening_prob = pred[1] * 100
    spoiled_prob = pred[2] * 100

    # 🔥 Risk calculation
    risk = (ripening_prob * 0.6 + spoiled_prob)

    # Add sensor effects
    if temp > 30:
        risk += (temp - 30) * 1.5

    if mq_diff > 100:
        risk += mq_diff * 0.05

    risk = min(100, risk)

    print(f"MQ_DIFF: {mq_diff}")
    print(f"ML → F:{fresh_prob:.1f} R:{ripening_prob:.1f} S:{spoiled_prob:.1f}")
    print(f"FINAL RISK: {risk:.1f}%")

    return label, round(confidence,2), round(risk,1)


# 📧 EMAIL ALERT
def send_email_alert(temp, hum, mq135):

    sender_email = "kaliesboopathy@gmail.com"
    receiver_email = "anbu200516@gmail.com"
    app_password = "dkapfvmfpwtgawku"

    subject = "⚠️ Apple Spoiled Alert 🍎"

    body = f"""
Apple spoilage detected!

Temperature: {temp} °C
Humidity: {hum} %
Gas Level: {mq135}

Check immediately!
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
        print("Email Error:", e)


# 🔥 ROUTE
@app.route("/update", methods=["GET"])
def update():

    global latest_data
    global last_email_time

    try:
        mq135 = float(request.args.get("mq135"))
        temp = float(request.args.get("temp"))
        hum = float(request.args.get("hum"))

        label, confidence, spoil_risk = predict_spoilage(mq135, temp, hum)

        # 🔥 MULTIPLE EMAIL ALERTS (COOLDOWN)
        now = datetime.now()

        if label.lower() == "spoiled":
            if last_email_time is None or (now - last_email_time).seconds > EMAIL_INTERVAL:
                send_email_alert(temp, hum, mq135)
                last_email_time = now

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        latest_data = {
            "label": label,
            "confidence": confidence,
            "spoil_risk": spoil_risk,
            "mq135": mq135,
            "temp": temp,
            "hum": hum,
            "timestamp": current_time
        }

        firebase_ref.push(latest_data)

        print("📊 Stored:", latest_data)

        return jsonify({"status": "ok"})

    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"status": "error"})


# 🔥 DASHBOARD
@app.route("/")
def index():
    return send_from_directory('.', 'index.html')


@app.route("/data")
def data():
    return jsonify(latest_data)


# 🔥 RUN
if __name__ == "__main__":
    print("🌐 Running → http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)