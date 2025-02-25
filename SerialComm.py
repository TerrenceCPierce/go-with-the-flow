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

# Initialize Serial Port connection to Arduino
arduino = serial.Serial(port='COM5', baudrate=115200, timeout=.1) 

# User-set parameter regarding saving vs loading data
isVideo = 0

take_data_code = 'a'
take_amb_p_code = 'b'

with open("arduino_data.csv", "w") as file:
    print("Writing data to arduino_data.csv...")

    while True:
        # Check if the arduino is ready to receive data
        if arduino.readline().decode("utf-8").strip('\n').strip('\r') == "Arduino Ready":
            print("Arduino Ready")
            
            # Clear any backlog of Arduino messages
            while arduino.in_waiting:
                arduino.read()
                # print("In Waiting")
            
            # Write code to Arduino
            # a Take data
            # b Take Ambient Pressure
            
            code_orig = input("Enter Code\n")
            
            if code_orig == take_data_code:
                x_pos = input("Enter x position\n")
                code = code_orig
                
            else:
                code = code_orig
            
            
            # Send 3 times in case of dropped packets
            arduino.write(code.encode())
            time.sleep(0.05)
            
            
            #Clear the arduino queue to get an accurate reading
            while arduino.in_waiting:
                print(arduino.read())
                print("In Waiting")
                time.sleep(0.1)
            
            returned_str = arduino.readline().decode("utf-8").strip()
            print(returned_str)
            
            
            if code_orig == take_data_code:
                file.write(returned_str+","+x_pos + "\n")  # Save to file
                file.flush()  # Ensure data is written
                
            elif code_orig == take_amb_p_code:
                file.write(returned_str + ","+"press"+"\n")  # Save to file
                file.flush()  # Ensure data is written
                    
            