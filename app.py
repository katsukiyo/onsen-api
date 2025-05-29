# 📁 構成ファイル例
#
# - app.py（Flask本体）
# - requirements.txt（Render用ライブラリ）
# - .env（Render上で環境変数として設定）
# - distance_matrix.csv
# - spot-id-master.csv

# ==== app.py ====
from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import os
from dotenv import load_dotenv
from flask import send_file

app = Flask(__name__)
CORS(app)

@app.route('/spot_master_csv', methods=['GET'])
def get_spot_master_csv():
    return send_file("spot-id-master.csv", mimetype='text/csv')

@app.route('/distance_matrix_csv', methods=['GET'])
def get_distance_matrix_csv():
    return send_file("distance_matrix.csv", mimetype='text/csv')

@app.route('/tourist_spots_csv', methods=['GET'])
def get_tourist_spots_csv():
    return send_file("tourist-spots-3.csv", mimetype='text/csv')


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



# ✅ .env 読み込み
load_dotenv()

# ✅ APIキーは環境変数から読み込む
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# ✅ CSVファイルの読み込み（Renderでは相対パスで対応）
DISTANCE_CSV = "distance_matrix.csv"
SPOT_CSV = "spot-id-master.csv"

df = pd.read_csv(DISTANCE_CSV, encoding="utf-8-sig")
spot_df = pd.read_csv(SPOT_CSV, encoding="utf-8-sig")

# ✅ 緯度・経度辞書作成
spot_df.columns = spot_df.columns.str.strip()
id_to_coords = {
    row["施設ID"]: f"{row['緯度']},{row['経度']}"
    for _, row in spot_df.iterrows()
}

# ✅ 距離検索API
@app.route("/get_duration", methods=["GET"])
def get_duration():
    from_id = request.args.get("from_id")
    to_id = request.args.get("to_id")
    if not from_id or not to_id:
        return jsonify({"error": "パラメータ from_id と to_id は必須です"}), 400

    # CSVから探す
    match = df[(df["from_id"] == from_id) & (df["to_id"] == to_id)]
    if not match.empty:
        minutes = match.iloc[0].get("driving_minutes")
        return jsonify({"from_id": from_id, "to_id": to_id, "minutes": minutes})

    # 緯度経度がなければ終了
    origin = id_to_coords.get(from_id)
    destination = id_to_coords.get(to_id)
    if not origin or not destination:
        return jsonify({"error": "緯度経度情報が見つかりません"}), 404

    # Google Directions APIに問い合わせ
    import requests
    url = (
        f"https://maps.googleapis.com/maps/api/directions/json?origin={origin}&destination={destination}"
        f"&mode=driving&key={API_KEY}"
    )
    res = requests.get(url)
    data = res.json()
    if data["status"] == "OK":
        duration_sec = data["routes"][0]["legs"][0]["duration"]["value"]
        minutes = int(round(duration_sec / 60 / 5.0)) * 5  # ← 5分単位に切り上げ

        # ✅ CSVにも追記（Renderは書き込み不可な場合あり、コメントアウト可能）
        df.loc[len(df.index)] = [from_id, "", to_id, "", None, minutes]
        df.to_csv(DISTANCE_CSV, index=False, encoding="utf-8-sig")

        return jsonify({"from_id": from_id, "to_id": to_id, "minutes": minutes})
    else:
        return jsonify({"error": data.get("status")}), 400

if __name__ == "__main__":
    app.run(debug=True)
