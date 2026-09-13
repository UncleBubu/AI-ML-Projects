import streamlit as st 
import cv2
import tempfile
from tensorflow.keras.models import load_model
import numpy as np


model = load_model(r"malaria_model.keras")

st.title("Malaria parasite detection")
img = st.file_uploader("upload cell image", type = ["png"])
tmp = tempfile.NamedTemporaryFile(delete = False, suffix=".png")
btn = st.button("click to analyze")

if img:
    tmp.write(img.read())
    try:
        cv_img = cv2.imread(tmp.name)
        st.image(cv_img, channels = "BGR", use_container_width=True)

    except:
        st.text("UNABLE TO PROCESS IMAGE!")

if btn:
    if img:
        cv_img = cv2.resize(cv_img,(60,60))
        cv_img = cv_img/255
        cv_img = np.expand_dims(cv_img, axis= 0)
        print(cv_img.shape)
        prob = model.predict(cv_img)
        if prob >=0.6:
            st.text(" MALARIA PARASITE DETECTED")
        else:
            st.text("NO MALARIA PARASITE DETECTED")
    else:
        st.text("PLEASE UPLOAD AN IMAGE")
            
            

        