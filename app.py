from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/validate', methods=['POST'])
def validate():
    data = request.json
    results = {
        "status": "success",
        "alerts": [],
        "metrics": {}
    }

    try:
        # --- 設備設計資料 ---
        tower_rt = float(data.get('tower_rt', 0))
        motor_np_kw = float(data.get('motor_np_kw', 0))
        fan_np_kw = float(data.get('fan_np_kw', 0))
        
        # --- 現場量測資料 ---
        flow_meas = float(data.get('flow_meas', 0))
        pump_kw_meas = float(data.get('pump_kw_meas', 0))
        fan_kw_meas = float(data.get('fan_kw_meas', 0))
        t_out = float(data.get('t_out', 0))
        t_basin = float(data.get('t_basin', 0))
        t_wet = float(data.get('t_wet', 0))
        t_in = float(data.get('t_in', 0))

        # --- 1. 流量合理性判定 (改用 1 RT = 12 LPM 估算) ---
        if tower_rt > 0 and flow_meas > 0:
            # 依據溫差 5.4~5.5°C 設計基準，1 RT 約需 12 LPM 的循環水量
            estimated_flow = tower_rt * 12.0
            results['metrics']['estimated_flow'] = f"{estimated_flow:.1f} LPM"
            
            flow_ratio = flow_meas / estimated_flow
            results['metrics']['flow_ratio'] = f"{flow_ratio * 100:.1f}%"
            
            if flow_ratio > 1.20:
                results['alerts'].append("⚠ 流量警告：實際流量超出水塔設計需求 20% 以上。水流速過快會縮短在散熱片上的停留時間，導致熱交換不完全。")
            elif flow_ratio < 0.80:
                results['alerts'].append("⚠ 流量警告：實際流量低於水塔設計需求 20% 以上。水流過慢會造成散熱片佈水不均，增加結垢風險，並降低水塔整體排熱能力。")

        # --- 2. 水泵耗電合理性判定 ---
        if motor_np_kw > 0 and pump_kw_meas > 0:
            motor_load = pump_kw_meas / motor_np_kw
            results['metrics']['motor_load'] = f"{motor_load * 100:.1f}%"
            if motor_load > 1.0:
                results['alerts'].append("❌ 耗電錯誤：水泵馬達過載 (負載率 > 100%)。實際耗電不可高於馬達銘牌額定功率。")
            elif motor_load < 0.3:
                results['alerts'].append("⚠ 耗電警告：水泵負載率極低 (<30%)。請確認系統閥門是否過度關閉或吸空。")

        # --- 3. 水塔風扇耗電合理性判定 ---
        if fan_np_kw > 0 and fan_kw_meas > 0:
            fan_load = fan_kw_meas / fan_np_kw
            results['metrics']['fan_load'] = f"{fan_load * 100:.1f}%"
            if fan_load > 1.0:
                results['alerts'].append("❌ 耗電錯誤：風扇馬達過載 (負載率 > 100%)。請檢查皮帶張力或葉片角度設定。")

        # --- 4. 水塔儲水槽水溫與出水溫度比對 ---
        if t_basin > 0 and t_out > 0:
            temp_diff = abs(t_basin - t_out)
            if temp_diff > 1.0:
                results['alerts'].append(f"⚠ 溫度警告：儲水槽水溫({t_basin}°C)與出水管水溫({t_out}°C) 差異達 {temp_diff:.1f}°C。請留意散熱死角或短迴路現象。")

        # --- 5. 基本熱力學驗證 ---
        if t_out > 0 and t_wet > 0 and t_out < t_wet:
            results['alerts'].append("❌ 熱力學錯誤：出水溫度不可低於外氣濕球溫度。")
        
        # --- 6. 趨近溫度與近似效率計算 ---
        if t_out > 0 and t_wet > 0 and t_out >= t_wet:
            approach = t_out - t_wet
            results['metrics']['approach'] = f"{approach:.2f} °C"
        
        if t_in > 0 and (t_in - t_wet) > 0 and t_out >= t_wet:
            effectiveness = ((t_in - t_out) / (t_in - t_wet)) * 100
            results['metrics']['effectiveness'] = f"{effectiveness:.1f} %"

        if not results['alerts']:
            results['alerts'].append("✅ 所有量測數據均符合設備設計與熱力學合理性。")

    except ValueError:
        results['status'] = "error"
        results['alerts'].append("資料解析錯誤，請確認輸入數值。")

    return jsonify(results)

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
