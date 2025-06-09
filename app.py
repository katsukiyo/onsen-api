# 📁 構成ファイル例
#
# - app.py（Flask本体）
# - requirements.txt（Render用ライブラリ）
# - .env（Render上で環境変数として設定）
# - distance_matrix.csv
# - spot-id-master.csv

# ==== app.py ====
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import os
import math
import requests
from dotenv import load_dotenv
from flask import send_file

# ==== 環境設定 ====
load_dotenv()
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# ==== アプリ初期化 ====
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ==== CSV ファイル読み込み ====
DISTANCE_CSV = "distance_matrix.csv"
SPOT_CSV = "spot-id-master.csv"
STATION_CSV = "stations_cleaned.csv"

spot_df = pd.read_csv(SPOT_CSV, encoding="utf-8-sig")
df = pd.read_csv(DISTANCE_CSV, encoding="utf-8-sig")
station_df = pd.read_csv(STATION_CSV, encoding="utf-8-sig")

spot_df.columns = spot_df.columns.str.strip()
station_df.columns = station_df.columns.str.strip()

# ==== 緯度・経度マッピング ====
spot_coords = {
    str(row["施設ID"]).strip(): f"{row['緯度']},{row['経度']}"
    for _, row in spot_df.iterrows()
}
station_coords = {
    str(row["駅名"]).strip(): f"{row['緯度']},{row['経度']}"
    for _, row in station_df.iterrows()
}
id_to_coords = {**spot_coords, **station_coords}

# ==== CSV 提供エンドポイント ====
@app.route('/spot_master_csv', methods=['GET'])
def get_spot_master_csv():
    return send_file(SPOT_CSV, mimetype='text/csv')

@app.route('/distance_matrix_csv', methods=['GET'])
def get_distance_matrix_csv():
    return send_file(DISTANCE_CSV, mimetype='text/csv')

@app.route('/tourist_spots_csv', methods=['GET'])
def get_tourist_spots_csv():
    return send_file("tourist-spots-3.csv", mimetype='text/csv')

# ==== 距離取得API（GET） ====
@app.route("/get_duration", methods=["GET"])
def get_duration():
    from_id = request.args.get("from_id")
    to_id = request.args.get("to_id")
    if not from_id or not to_id:
        return jsonify({"error": "パラメータ from_id と to_id は必須です"}), 400

    match = df[(df["from_id"] == from_id) & (df["to_id"] == to_id)]
    if not match.empty:
        minutes = match.iloc[0].get("driving_minutes")
        return jsonify({"from_id": from_id, "to_id": to_id, "minutes": minutes})

    origin = id_to_coords.get(from_id)
    destination = id_to_coords.get(to_id)
    if not origin or not destination:
        return jsonify({"error": "緯度経度情報が見つかりません"}), 404

    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={origin}&destination={destination}&mode=driving&key={API_KEY}"
    res = requests.get(url)
    data = res.json()
    if data["status"] == "OK":
        duration_sec = data["routes"][0]["legs"][0]["duration"]["value"]
        minutes = int(round(duration_sec / 60 / 5.0)) * 5
        # df.loc[len(df.index)] = [from_id, "", to_id, "", None, minutes]  # Renderでは書き込み不可
        # df.to_csv(DISTANCE_CSV, index=False, encoding="utf-8-sig")
        return jsonify({"from_id": from_id, "to_id": to_id, "minutes": minutes})
    else:
        return jsonify({"error": data.get("status")}), 400

# ==== 距離取得API（POST + JSON） ====
@app.route("/get_duration_api", methods=["POST"])
def get_duration_api():
    data = request.json
    from_id = data.get("from_id")
    to_id = data.get("to_id")

    origin = id_to_coords.get(from_id)
    destination = id_to_coords.get(to_id)

    if not origin or not destination:
        return jsonify({"error": "座標が見つかりません"}), 400

    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={origin}&destination={destination}&mode=driving&key={API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        if data["status"] == "OK":
            duration_sec = data["routes"][0]["legs"][0]["duration"]["value"]
            return jsonify({
                "from_id": from_id,
                "to_id": to_id,
                "minutes": round(duration_sec / 60)
            })
        else:
            return jsonify({"error": f"API Error: {data['status']}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==== 詳細距離API（POST + JSON） ====
@app.route('/realtime_distance', methods=['POST'])
def realtime_distance():
    data = request.get_json()
    from_id = data.get("from_id")
    to_id = data.get("to_id")

    origin = id_to_coords.get(from_id)
    destination = id_to_coords.get(to_id)

    if not origin or not destination:
        return jsonify({"error": "座標が見つかりません"}), 400

    url = (
        f"https://maps.googleapis.com/maps/api/directions/json"
        f"?origin={origin}&destination={destination}"
        f"&mode=driving&key={API_KEY}"
    )
    try:
        response = requests.get(url)
        result = response.json()
        if result.get("status") == "OK":
            leg = result["routes"][0]["legs"][0]
            duration_sec = leg["duration"]["value"]
            distance_m = leg["distance"]["value"]
            raw_minutes     = duration_sec / 60.0
            rounded_minutes = math.ceil(raw_minutes / 5.0) * 5
            return jsonify({
                "from_id":         from_id,
                "to_id":           to_id,
                "driving_minutes": int(rounded_minutes),
                "distance_km":      round(distance_m / 1000, 1)
            })
        else:
            return jsonify({"error": result.get("status", "unknown error")}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==== 実行 ====
if __name__ == '__main__':
    app.run(debug=True)
