import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
import pickle
from sklearn.metrics import r2_score, classification_report

X= pd.read_csv(r"C:\Users\chukw\Documents\RAIN\AIML 1ST SEMESTER (File responses)\exam aiml 112\smartphone_battery_features.csv")
y =pd.read_csv(r"C:\Users\chukw\Documents\RAIN\AIML 1ST SEMESTER (File responses)\exam aiml 112\smartphone_battery_targets.csv")

X = X.drop(['Device_ID','signal_strength_avg'],axis=1)
y_reg = y["current_battery_health_percent"]
y_class = y["recommended_action"]

X_reg_train,X_reg_test,y_reg_train,y_reg_test=train_test_split(X,y_reg,test_size=0.2,random_state=101)

X_class_train,X_class_test,y_class_train,y_class_test=train_test_split(X,y_class,test_size=0.2,random_state=101,stratify=y_class)


background_enc = LabelEncoder()

X_reg_train["background_app_usage_level"] = background_enc.fit_transform(X_reg_train["background_app_usage_level"])
X_reg_test["background_app_usage_level"] = background_enc.transform(X_reg_test["background_app_usage_level"])

X_class_train["background_app_usage_level"] = background_enc.fit_transform(X_class_train["background_app_usage_level"])
X_class_test["background_app_usage_level"] = background_enc.transform(X_class_test["background_app_usage_level"])


reg_model = LinearRegression()
class_model = LogisticRegression()

reg_model.fit(X_reg_train,y_reg_train)
class_model.fit(X_class_train,y_class_train)

y_reg_pred = reg_model.predict(X_reg_test)
y_class_pred = class_model.predict(X_class_test)

print(r2_score(y_reg_test,reg_model.predict(X_reg_test)))
print(classification_report(y_class_test,class_model.predict(X_class_test)))

with open("battery_percent_model.pkl", "wb") as f:
    pickle.dump(reg_model,f)

with open("rec_action_model.pkl", "wb") as f:
    pickle.dump(class_model,f)

with open("background_encoder.pkl", "wb") as f:
    pickle.dump(background_enc,f)
