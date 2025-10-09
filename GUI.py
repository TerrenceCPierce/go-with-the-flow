import tkinter as tk
from tkinter import ttk
import os
import webbrowser
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import serial 
import serial.tools.list_ports
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
    global arduino
    
    try:
        port = port_var.get().strip()  # Get the port string from GUI input
        
        # If the user only provides a number (e.g., "3"), assume it's a Windows COM port
        if port.isdigit():
            port = 'COM' + port  
        
        # Try to open serial connection
        arduino = serial.Serial(port=port, baudrate=115200, timeout=0.1)
        
        ArduinoConnectStr_var.set(f"Connected to {port}")
        arduino_str = ""
        while (arduino_str == ""):
            arduino_str = arduino.readline().decode("utf-8").strip('\n').strip('\r')
            print("!"+ arduino_str)
            arduino.write("GReady\n".encode())
            print("GUI Ready")
            time.sleep(0.5)
    
    except serial.SerialException as e:
        ArduinoConnectStr_var.set(f"Connection failed: {e}")
        arduino = None
    
    


ports = serial.tools.list_ports.comports()
for port in ports:
    print(port.device, "-", port.description)



def labdetails_Callback():
    webbrowser.open_new(r"https://drive.google.com/file/d/1WX5xK7Xqua2Vz-lO5Z7_klDieToz0dC8/view?usp=sharing")
 
def collect_Callback():
    arduino.flushInput()
    arduino.flushOutput()
    time.sleep(0.05)
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
        test_str = arduino.readline().decode("utf-8").strip('\n').strip('\r')
        print(test_str)
        if test_str == "Arduino Ready 1":
                print("Arduino Ready")
                
                
                # Clear any backlog of Arduino messages
                while arduino.in_waiting:
                    print(arduino.read())
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
                    print(arduino.read())
                    print("In Waiting 2")
                    time.sleep(1)
                
                # Send 3 times in case of dropped packets
                arduino.write((code + "\n").encode())
                time.sleep(0.05)
                #arduino.write((code + "\n").encode())
                #time.sleep(0.05)
                #arduino.write((code + "\n").encode())
                #time.sleep(0.05)
                
                returned_str = arduino.readline().decode("utf-8").strip('\n').strip('\r')
                print(returned_str)
                while(not returned_str.startswith("Arduino Data Ready")):
                    #arduino.flushInput()
                    #arduino.flushOutput()
                    arduino.write((code + "\n").encode())
                    time.sleep(3)
                    returned_str = arduino.readline().decode("utf-8").strip('\n').strip('\r')
                    print(returned_str + "1")
                
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
                
                writer.writerow([x_pos, str(float(pitot_press_str)*100), str(float(ambient_press_str)*100), thrust])
                file.flush()
                print("Wrote to CSV")
                notCollected = False
                df = pd.read_csv(file.name)
                arduino.flushInput()
                arduino.flushOutput()


# Window
root.title('Thrust Stand Experiment')
root.geometry('1440x900')
root.configure(bg='#f8f8fb')

# Grid
'''for i in range(4):
    root.grid_columnconfigure(i, weight=1)'''

root.columnconfigure(0, weight=3)
root.grid_columnconfigure(1, weight=3)
root.grid_columnconfigure(2, weight=1)
root.grid_columnconfigure(3, weight=1)

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
lbl_title.grid(column=0, row=0, columnspan=2, sticky='nsew')

# Collect Button
btn_collect = tk.Button(root, text='Collect', bg='#B0CA99', command= collect_Callback)
btn_collect.grid(column=1, row=3, sticky='ew')



# Arduino Status
frame_status = tk.Frame(root)
frame_status.grid(column=0, row=3, sticky='nsew')
for i in range(2):
    frame_status.grid_columnconfigure(i, weight=1)
for j in range(3):
    frame_status.grid_rowconfigure(j, weight=1)

lbl_arduino = tk.Label(frame_status, text='Arduino Status:', fg='red')
lbl_arduino.grid(column=0, row=0, sticky='ew')

lbl_not_conn = tk.Label(frame_status, textvariable=ArduinoConnectStr_var)
lbl_not_conn.grid(column=1, row=0, sticky='ew')

lbl_thrust = tk.Label(frame_status, text='Port:')
lbl_thrust.grid(column=0, row=1, sticky='ew')

port_entry = tk.Entry(frame_status, textvariable=port_var)
port_entry.grid(column=1, row=1, sticky='ew')

btn_connect = tk.Button(frame_status, text='Connect', bg='#B0CA99', command= arduinoConnect_Callback)
btn_connect.grid(column=0, row=2, columnspan=2, sticky='ew')

#lbl_connected = tk.Label(frame_status, text='Connected')
#lbl_connected.grid(column=0, row=1, sticky='nw')

# add connection command if/then statement
#canvas = tk.Canvas(frame, width=200, height=200)
#canvas.pack()

#circle = canvas.create_oval(frame_status, fill="red")
#circle.grid(column=1, row=1, sticky='nsew')



# Thrust/Position Frame
frame_tp = tk.Frame(root)
frame_tp.grid(column=2, row=3, sticky='ew')
frame_tp.grid_columnconfigure(0, weight=1, minsize=200)
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
frame_PX.grid(column=0, row=1, columnspan=2, sticky='ew')
frame_PX.grid_columnconfigure(0, weight=1)
for i in range(1):
    frame_tp.grid_rowconfigure(i, weight=1)

lbl_PX = tk.Label(frame_PX, text='Absolute Pressure vs X-Position', bg='#fff', font=("Arial",20))
lbl_PX.grid(column=0, row=0, sticky='nsew')

if isTest:
    #file_name = r"C:\Users\Terrence\Python\go-with-the-flow\Test Data\arduino_data2025-04-04_09-41-00.csv"
    file_name = r"C:\Users\t4mar\Documents\VIP_Team\go-with-the-flow\Test Data\arduino_data2025-04-04_09-41-00.csv"
    df = pd.read_csv(file_name)
else:
    df = pd.read_csv(file.name)

fig_press = plt.Figure(figsize=(2, 2), dpi=100)
scatter = FigureCanvasTkAgg(fig_press, frame_PX)
scatter.get_tk_widget().grid(column=0, row=1, sticky='nsew')  # use only .grid()

ax1 = fig_press.add_subplot(111)
ax1.plot(df['x (mm)'], df['Pressure (Pa)'], color='red')
ax1.set_xlabel('x (mm)', fontsize=15)
ax1.set_ylabel('Pressure (Pa)', fontsize=15)

fig_press.tight_layout(pad=2.0)  # Fix cutoff labels
fig_press.set_constrained_layout(True)





# Velocity Graph Frame
frame_VX = tk.Frame(root)
frame_VX.grid(column=0, row=2, columnspan=2, sticky='ew')
frame_VX.grid_columnconfigure(0, weight=1)
for i in range(1):
    frame_tp.grid_rowconfigure(i, weight=1)

lbl_VX = tk.Label(frame_VX, text='Velocity vs X-Position', bg='#fff', font=("Arial",20))
lbl_VX.grid(column=0, row=0, sticky='nsew')

fig_velo = plt.Figure(figsize=(2, 2), dpi=100)
scatter = FigureCanvasTkAgg(fig_velo, frame_VX)
scatter.get_tk_widget().grid(column=0, row=1, sticky='nsew')  # use only .grid()

ax2 = fig_velo.add_subplot(111)
ax2.plot(df['x (mm)'], np.sqrt(np.maximum(0, 2*(df['Pressure (Pa)'] - df['Ambient (Pa)']) / air_density)), color='red')
ax2.set_xlabel('x (mm)', fontsize=15)
ax2.set_ylabel('V (m/s)', fontsize=15)

fig_velo.tight_layout(pad=2.0)  # Fix cutoff labels
fig_velo.set_constrained_layout(True)

def display_dataframe_as_table(parent, df_example):
    # Create Treeview
    tree = ttk.Treeview(parent, columns=list(df_example.columns), show='headings')

    # Set column headers
    for col in df_example.columns:
        tree.heading(col, text=col)
        tree.column(col, anchor='center', minwidth=0, width=150, stretch=True)

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
frame_DT.grid(column=2, row=1, columnspan=2, rowspan=2, sticky='nsew')
table = display_dataframe_as_table(frame_DT, df)
#print("Looping root")
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

def update_gui():
    try:
        # Reload CSV (if it exists and has data)
        if os.path.exists(file.name):
            new_df = pd.read_csv(file.name)

            # --- Update Pressure Graph ---
            ax1.clear()
            ax1.plot(new_df['x (mm)'], new_df['Pressure (Pa)'], color='red')
            ax1.set_xlabel('x (mm)', fontsize=8)
            ax1.set_ylabel('Pressure (Pa)', fontsize=7)
            fig_press.canvas.draw()

            # --- Update Velocity Graph ---
            ax2.clear()
            ax2.plot(new_df['x (mm)'], np.sqrt(np.maximum(0, 2*(new_df['Pressure (Pa)'] - new_df['Ambient (Pa)']) / air_density)), color='red')
            ax2.set_xlabel('x (mm)', fontsize=8)
            ax2.set_ylabel('V (m/s)', fontsize=7)
            fig_velo.canvas.draw()

            # --- Update Table ---
            for row in table.get_children():
                table.delete(row)
            for _, row in new_df.iterrows():
                table.insert('', tk.END, values=list(row))

        # Schedule the next update
        root.after(1000, update_gui)  # Every 1000 ms

    except Exception as e:
        print(f"Error during update: {e}")
        root.after(2000, update_gui)  # Retry after 2 seconds if something went wrong


update_gui()
root.mainloop()
