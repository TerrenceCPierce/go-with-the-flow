import tkinter as tk
from tkinter import ttk
import os
import webbrowser
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import serial 
from datetime import datetime
import webbrowser
import csv
import time
import pandas as pd
import numpy as np


root = tk.Tk()
pos_var= tk.StringVar()
thrust_var = tk.StringVar()
port_var = tk.StringVar()

ArduinoConnectStr_var = tk.StringVar()
ArduinoConnectStr_var.set("Not Connected")

isTest = 0
air_density = 1.298351265 # kg/m^3

global df
global file


def open_file():
    file_path = "Users/vpatel07/Downloads/Manual_Sp25VIPSfile.pdf"  # Replace with your file path
    try:
        # os.startfile(file_path) # For Windows
        os.system(f"open {file_path}") # For macOS and Linux
    except FileNotFoundError:
        print("File not found.")

'''Callback for 
newfile
arduinoConnect
labdetails


Collect:
Variables 
thrust
position
'''
def newfile_Callback():
    global file
    global timestamp
    try:
        file.close()
    except:
        #File doesn't exist yet
        ignore=1
    now = datetime.now()
    # Format it as 'YYYY-MM-DD_HH-MM-SS'

    # DEBUG
    curdir = os.getcwd()
    print('My current directory is {}'.format(curdir))

    
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    file = open("arduino_data"+timestamp+".csv", "w", newline="")
    print("Writing data to arduino_data.csv...")
    writer = csv.writer(file)
    writer.writerow(["x (mm)", "Pressure (Pa)", "Ambient (Pa)", "Thrust(g)"])  # Header
    file.flush()

newfile_Callback()

def arduinoConnect_Callback():
    # UPDATE with port number once variable is made
    global arduino
    #print('COM'+ port_var.get())
    
    
    arduino = serial.Serial(port='COM'+ port_var.get(), baudrate=115200, timeout=.1)
    ArduinoConnectStr_var.set("Connected") #Will throw error if doesn't work, find better way to communicate through GUI

def labdetails_Callback():
    webbrowser.open_new(r"https://drive.google.com/file/d/1WX5xK7Xqua2Vz-lO5Z7_klDieToz0dC8/view?usp=sharing")
 
def collect_Callback():
    # DEBUG
    # writer = csv.writer(file)
    # x_pos = pos_var.get()
    # print(x_pos)
    # thrust = thrust_var.get()
    # print(thrust)
    # writer.writerow([x_pos, 0, 0, thrust])
    # file.flush()
    global df
    notCollected = True
    writer = csv.writer(file)
    while notCollected:
        if arduino.readline().decode("utf-8").strip('\n').strip('\r') == "Arduino Ready":
                print("Arduino Ready")
                
                
                # Clear any backlog of Arduino messages
                while arduino.in_waiting:
                    arduino.read()
                    print("In Waiting 1")
                    #time.sleep(0.1)
                
                # Write code to Arduino
                # a Take data
                # b Take Ambient Pressure
                
                code = 'a'
                
                x_pos = pos_var.get()
                thrust = thrust_var.get()
                    
                    
                # Clear any backlog of Arduino messages
                while arduino.in_waiting:
                    arduino.read()
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
                
                writer.writerow([x_pos, pitot_press_str, ambient_press_str, thrust])
                file.flush()
                print("Wrote to CSV")
                notCollected = False
                df = pd.read_csv(file.name)



# Window
root.title('Thrust Stand Experiment')
root.geometry('1440x900')
root.configure(bg='#f8f8fb')

# Grid
for i in range(4):
    root.grid_columnconfigure(i, weight=1)
for j in range(4):
    root.grid_rowconfigure(j, weight=1)

# Buttons
btn_new_file = tk.Button(root, text='New File', bg='#1E90FF', command=newfile_Callback)
btn_new_file.grid(column=2, row=0, sticky='ew')

btn_exit = tk.Button(root, text='Exit', bg='#D9D9D9', command=root.quit)
btn_exit.grid(column=3, row=3, sticky='ew')

btn_lab_details = tk.Button(root, text='Lab Details', bg='#B4DCEB', command=labdetails_Callback)
btn_lab_details.grid(column=3, row=0, sticky='ew')

# Widgets
lbl_title = tk.Label(root, text='Thrust Stand Experiment', bg='white', fg='black')
lbl_title.grid(column=0, row=0, sticky='nsew')

# Collect Button
btn_collect = tk.Button(root, text='Collect', bg='#B0CA99', command= collect_Callback)
btn_collect.grid(column=1, row=3,  sticky='ew')

btn_connect = tk.Button(root, text='Connect', bg='#B0CA99', command= arduinoConnect_Callback)
btn_connect.grid(column=1, row=4,  sticky='ew')



# Arduino Status
frame_status = tk.Frame(root)
frame_status.grid(column=2, row=3, sticky='nsew')
for i in range(2):
    frame_status.grid_columnconfigure(i, weight=1)
for j in range(2):
    frame_status.grid_rowconfigure(j, weight=1)

lbl_arduino = tk.Label(frame_status, text='Arduino Status:')
lbl_arduino.grid(column=0, row=0, columnspan=2, sticky='nsew')

lbl_not_conn = tk.Label(frame_status, textvariable=ArduinoConnectStr_var)
lbl_not_conn.grid(column=0, row=1, sticky='nw')

lbl_thrust = tk.Label(frame_status, text='Port:')
lbl_thrust.grid(column=0, row=2, sticky='ew')

port_entry = tk.Entry(frame_status, textvariable=port_var)
port_entry.grid(column=1, row=2, sticky='nsew')

#lbl_connected = tk.Label(frame_status, text='Connected')
#lbl_connected.grid(column=0, row=1, sticky='nw')

# add connection command if/then statement
#canvas = tk.Canvas(frame, width=200, height=200)
#canvas.pack()

#circle = canvas.create_oval(frame_status, fill="red")
#circle.grid(column=1, row=1, sticky='nsew')



# Thrust/Position Frame
frame_tp = tk.Frame(root)
frame_tp.grid(column=3, row=1, sticky='ew')
frame_tp.grid_columnconfigure(0, weight=1)
for i in range(4):
    frame_tp.grid_rowconfigure(i, weight=1)

# Thrust
lbl_thrust = tk.Label(frame_tp, text='Thrust (g)')
lbl_thrust.grid(column=0, row=0, sticky='ew')

thrust_entry = tk.Entry(frame_tp, textvariable=thrust_var)
thrust_entry.grid(column=0, row=1, sticky='ew')
# thrust_entry.pack(side='bottom', fill='x', expand=True)

# Position
lbl_position = tk.Label(frame_tp, text="Position:")
lbl_position.grid(column=0, row=2, sticky='ew')

position_entry = tk.Entry(frame_tp, textvariable=pos_var)
position_entry.grid(column=0, row=3, sticky='nsew')
# position_entry.pack(side='bottom', fill='x', expand=True)


# Inspiration from https://stackoverflow.com/questions/67280510/how-to-display-matplotlib-charts-in-tkinter


# Pressure Graph Frame
frame_PX = tk.Frame(root)
frame_PX.grid(column=0, row=1, sticky='ew')
frame_PX.grid_columnconfigure(0, weight=1)
for i in range(1):
    frame_tp.grid_rowconfigure(i, weight=1)

lbl_PX = tk.Label(frame_PX, text='Absolute Pressure vs X-Position', bg='#fff')
lbl_PX.grid(column=0, row=0, sticky='nsew')

if isTest:
    file_name = r"C:\Users\Terrence\Python\go-with-the-flow\Test Data\arduino_data2025-04-04_09-41-00.csv"
    df = pd.read_csv(file_name)
else:
    df = pd.read_csv(file.name)

fig_press = plt.Figure(figsize=(2, 1), dpi=100)
scatter = FigureCanvasTkAgg(fig_press, frame_PX)
scatter.get_tk_widget().grid(column=0, row=1, sticky='nsew')  # use only .grid()

ax1 = fig_press.add_subplot(111)
ax1.plot(df['x (mm)'], df['Pressure (Pa)'], color='red')
ax1.set_xlabel('x (mm)', fontsize=8)
ax1.set_ylabel('Pressure (Pa)', fontsize=7)

fig_press.tight_layout(pad=2.0)  # Fix cutoff labels
fig_press.set_constrained_layout(True)





# Velocity Graph Frame
frame_VX = tk.Frame(root)
frame_VX.grid(column=0, row=2, rowspan=2, sticky='nsew')
frame_VX.grid_columnconfigure(0, weight=1)
for i in range(1):
    frame_tp.grid_rowconfigure(i, weight=1)

lbl_VX = tk.Label(frame_VX, text='Velocity vs X-Position', bg='#fff')
lbl_VX.grid(column=0, row=0, sticky='nsew')

fig_velo = plt.Figure(figsize=(2, 1), dpi=100)
scatter = FigureCanvasTkAgg(fig_velo, frame_VX)
scatter.get_tk_widget().grid(column=0, row=1, sticky='nsew')  # use only .grid()

ax1 = fig_velo.add_subplot(111)
ax1.plot(df['x (mm)'], np.sqrt(2*(df['Pressure (Pa)']-df['Ambient (Pa)'])/air_density), color='red')
ax1.set_xlabel('x (mm)', fontsize=8)
ax1.set_ylabel('V (m/s)', fontsize=7)

fig_velo.tight_layout(pad=2.0)  # Fix cutoff labels
fig_velo.set_constrained_layout(True)

def display_dataframe_as_table(parent, df_example):
    # Create Treeview
    tree = ttk.Treeview(parent, columns=list(df_example.columns), show='headings')

    # Set column headers
    for col in df_example.columns:
        tree.heading(col, text=col)
        tree.column(col, anchor='center', stretch=True)

    # Insert data into Treeview
    for _, row in df_example.iterrows():
        tree.insert('', tk.END, values=list(row))

    # Add vertical scrollbar
    vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)

    # Layout
    tree.grid(row=0, column=0, sticky='nsew')
    vsb.grid(row=0, column=1, sticky='ns')

    # Configure column/row weights for resizing
    parent.grid_rowconfigure(0, weight=1)
    parent.grid_columnconfigure(0, weight=1)

    return tree

# Data Table Frame
frame_DT = tk.Frame(root)
frame_DT.grid(column=1, row=1, columnspan=2, rowspan=2, sticky='nsew')
display_dataframe_as_table(frame_DT, df)
"""
for i in range(4):
    frame_DT.grid_columnconfigure(i, weight=1)
for i in range(3):
    frame_tp.grid_rowconfigure(i, weight=1)

lbl_Data_Table = tk.Label(frame_DT, text='Data Table')
lbl_Data_Table.grid(column=0, row=0, sticky='nsew')

lbl_x = tk.Label(frame_DT, text='x (cm)')
lbl_x.grid(column=0, row=1, sticky='ew')

lbl_Ambient = tk.Label(frame_DT, text='Ambient Pressure (Pa)')
lbl_Ambient.grid(column=1, row=1, sticky='ew')

lbl_Pitot_Tube = tk.Label(frame_DT, text='Stagnation (Pa)')
lbl_Pitot_Tube.grid(column=2, row=1, sticky='ew')

lbl_Thrust_DT = tk.Label(frame_DT, text='Thrust (g)')
lbl_Thrust_DT.grid(column=3, row=1, sticky='ew')
"""

root.mainloop()
