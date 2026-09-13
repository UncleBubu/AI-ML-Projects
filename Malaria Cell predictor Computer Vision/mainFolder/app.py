from flask import Flask, render_template, request
import pickle
import numpy as np
import os
print (os.getcwd)
print("cake")

app = Flask("__name__")

with open(r"C:\Users\chukw\Documents\RAIN\AIML 2ND SEMESTER (File responses)\Rain Class\Week 12 Deployment\mainFolder\battery_percent_model.pkl","rb") as f:
    reg_model = pickle.load(f)
    
with open(r"C:\Users\chukw\Documents\RAIN\AIML 2ND SEMESTER (File responses)\Rain Class\Week 12 Deployment\mainFolder\rec_action_model.pkl","rb") as f:
    class_model = pickle.load(f)
    # rb = read binary wb = write binary
with open(r"C:\Users\chukw\Documents\RAIN\AIML 2ND SEMESTER (File responses)\Rain Class\Week 12 Deployment\mainFolder\background_encoder.pkl","rb") as f:
    background_enc = pickle.load(f)
    
@app.route('/',methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template(r"index.html")
    elif request.method == "POST":
        device_age = int(request.form.get("device_age"))
        battery_capacity = float(request.form.get("battery_capacity"))
        average_screen_time_hours = float(request.form.get("average_screen_time_hours"))
        avg_charge_cycle = float(request.form.get("avg_charge_cycle"))
        avg_temp = float(request.form.get("avg_temp"))
        fast_charging = float(request.form.get("fast_charging"))
        overnight_charging_per_week = int(request.form.get("overnight_charging_per_week"))
        gaming_hours_per_week = float(request.form.get("gaming_hours_per_week"))
        video_streaming_hours_per_week = float(request.form.get("video_streaming_hours_per_week"))
        background_app_usage = background_enc.transform([request.form.get("background_app_usage")])[0]
        charging_habit_score = int(request.form.get("charging_habit_score"))
        usage_intensity_score = int(request.form.get("usage_intensity_score"))
        thermal_stress_index = float(request.form.get("thermal_stress_index"))
        # IT must be created in a 2d array because the model was trained on a 2d array [[]]
        datapoint = np.array([[device_age,battery_capacity,average_screen_time_hours,avg_charge_cycle,avg_temp,fast_charging,overnight_charging_per_week,gaming_hours_per_week,video_streaming_hours_per_week,background_app_usage,charging_habit_score,usage_intensity_score,thermal_stress_index]])

        predicted_battery_health = reg_model.predict(datapoint)[0]
        recommended_action = class_model.predict(datapoint)[0]
        print(predicted_battery_health)
        print(recommended_action)

        return render_template("index.html",predicted_battery_health=round(predicted_battery_health,2),recommended_action=recommended_action)
        

        


if __name__ == '__main__':
    app.run(host="0.0.0.0",port=5000,debug=True)
