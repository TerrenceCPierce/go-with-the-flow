# -*- coding: utf-8 -*-
"""
Created on Tue Feb 25 17:07:57 2025

@author: t4mar
"""

# Import important libraries
import cv2
import numpy as np
import os
import glob
from matplotlib import pyplot as plt
from scipy.spatial.transform import Rotation
import math
import socket
import random
import serial 
import time 
import csv
from datetime import datetime

# Get current datetime
now = datetime.now()

# Format it as 'YYYY-MM-DD_HH-MM-SS'
timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")

# Initialize Serial Port connection to Arduino
arduino = serial.Serial(port='COM5', baudrate=115200, timeout=.1) 

# User-set parameter regarding saving vs loading data
isVideo = 0

take_data_code = 'a'
take_amb_p_code = 'b'

with open("arduino_data"+timestamp+".csv", "w", newline="") as file:
    print("Writing data to arduino_data.csv...")
    writer = csv.writer(file)
    writer.writerow(["x", "Pressure", "Ambient"])  # Header
    file.flush()

    while True:
        # Check if the arduino is ready to receive data
        if arduino.readline().decode("utf-8").strip('\n').strip('\r') == "Arduino Ready":
            print("Arduino Ready")
            
            # Clear any backlog of Arduino messages
            while arduino.in_waiting:
                arduino.read()
                print("In Waiting 1")
                time.sleep(0.1)
            
            # Write code to Arduino
            # a Take data
            # b Take Ambient Pressure
            
            code_orig = input("Enter Code\n")
            
            if code_orig == take_data_code:
                x_pos = input("Enter x position\n")
                code = code_orig
                
            else:
                code = code_orig
                
            # Clear any backlog of Arduino messages
            while arduino.in_waiting:
                print(arduino.read())
                print("In Waiting 2")
                #time.sleep(0.1)
            
            # Send 3 times in case of dropped packets
            arduino.write(code.encode())
            time.sleep(0.05)
            
            returned_str = arduino.readline().decode("utf-8").strip('\n').strip('\r')
            while(not returned_str.startswith("Arduino Data Ready")):
                time.sleep(0.05)
                returned_str = arduino.readline().decode("utf-8").strip('\n').strip('\r')
                print(returned_str)
            
            arduino.write("SendData".encode())
            
            returned_str = arduino.readline().decode("utf-8").strip('\n').strip('\r')
            while(not returned_str.startswith("Data")):
                time.sleep(0.05)
                returned_str = arduino.readline().decode("utf-8").strip('\n').strip('\r')
                #print(returned_str)
            
            print(returned_str)
            
            modified_str = returned_str.split("Data:,", 1)[1]
            
            pitot_press_str = modified_str.split(",", 1)[0]
            ambient_press_str = modified_str.split(",", 1)[1]
            
            
            if code_orig == take_data_code:
                writer.writerow([x_pos, pitot_press_str, ambient_press_str])
                file.flush()
                print("Wrote to CSV")
                
                
            elif code_orig == take_amb_p_code:
                writer.writerow(["-", "-", modified_str])
                file.flush()
                print("Wrote to CSV")
                    
            