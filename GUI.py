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
thrust_var = tk.StringVar()
port_var = tk.StringVar()

ArduinoConnectStr_var = tk.StringVar()
AIR_DENSITY = 1.298351265  # kg/m^3
LAB_DETAILS_URL = "https://drive.google.com/file/d/1WX5xK7Xqua2Vz-lO5Z7_klDieToz0dC8/view?usp=sharing"


def launch_thrust_stand(master=None):
    _launch_experiment(master, "Thrust Stand Experiment")


def launch_pipe_flow(master=None):
    _launch_experiment(master, "Pipe Flow Experiment")


def launch_wind_tunnel(master=None):
    _launch_experiment(master, "Wind Tunnel Experiment")


def _launch_experiment(master, window_title):
    standalone_root = None

    if master is None:
        standalone_root = tk.Tk()
        standalone_root.withdraw()
        master = standalone_root
    else:
        master.withdraw()

    root = tk.Toplevel(master)
    root.title(window_title)
    root.geometry("1440x900")
    root.minsize(1200, 700)
    root.configure(bg="white")

    pos_var = tk.StringVar()
    thrust_var = tk.StringVar()
    port_var = tk.StringVar()
    arduino_status_var = tk.StringVar(value="Not Connected")

    arduino = None
    file_handle = None
    timestamp = None
    df = pd.DataFrame(columns=["x (mm)", "Pressure (Pa)", "Ambient (Pa)", "Thrust(g)"])

    def on_close():
        nonlocal arduino, file_handle
        try:
            if arduino is not None and arduino.is_open:
                arduino.close()
        except Exception:
            pass

        try:
            if file_handle is not None and not file_handle.closed:
                file_handle.close()
        except Exception:
            pass

        root.destroy()

        if standalone_root is not None:
            standalone_root.destroy()
        else:
            master.deiconify()

    root.protocol("WM_DELETE_WINDOW", on_close)

    def open_lab_details():
        webbrowser.open_new(LAB_DETAILS_URL)

    def newfile_Callback():
        nonlocal file_handle, timestamp, df

        try:
            if file_handle is not None and not file_handle.closed:
                file_handle.close()
        except Exception:
            pass

        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"arduino_data{timestamp}.csv"

        print(f"My current directory is {os.getcwd()}")
        print(f"Writing data to {filename}...")

        file_handle = open(filename, "w", newline="")
        writer = csv.writer(file_handle)
        writer.writerow(["x (mm)", "Pressure (Pa)", "Ambient (Pa)", "Thrust(g)"])
        file_handle.flush()

        df = pd.read_csv(file_handle.name)
        refresh_all(df)

    def find_arduino_port():
        ports = serial.tools.list_ports.comports()
        for port in ports:
            desc = port.description or ""
            print(port.device, "-", desc)
            if (
                "Arduino" in desc
                or "USB Serial" in desc
                or "USB to UART" in desc
            ):
                print(f"Found Arduino on port: {port.device}")
                return port.device
        print("No Arduino found")
        return None

    def arduinoConnect_Callback():
        nonlocal arduino

        try:
            port = port_var.get().strip()

            if not port:
                arduino_status_var.set("Enter a port or use auto-detect")
                lbl_not_conn.config(fg="red")
                return

            if port.isdigit():
                port = "COM" + port

            arduino = serial.Serial(port=port, baudrate=115200, timeout=0.1)

            arduino_status_var.set(f"Connected to {port}")
            lbl_not_conn.config(fg="green")

            arduino_str = ""
            while arduino_str == "":
                arduino_str = (
                    arduino.readline()
                    .decode("utf-8", errors="ignore")
                    .strip("\n")
                    .strip("\r")
                )
                print("!" + arduino_str)
                arduino.write("GReady\n".encode())
                print("GUI Ready")
                time.sleep(0.5)

        except serial.SerialException as e:
            arduino_status_var.set(f"Connection failed: {e}")
            lbl_not_conn.config(fg="red")
            arduino = None

    def auto_connect_arduino():
        arduino_status_var.set("Scanning for Arduino…")
        lbl_not_conn.config(fg="black")
        root.update_idletasks()

        try:
            port = find_arduino_port()
            if not port:
                arduino_status_var.set("No Arduino found. Plug it in and try again.")
                lbl_not_conn.config(fg="red")
                return

            port_var.set(port)
            arduino_status_var.set(f"Found {port}. Connecting…")
            root.update_idletasks()

            arduinoConnect_Callback()

        except Exception as e:
            arduino_status_var.set(f"Error: {type(e).__name__}: {e}")
            lbl_not_conn.config(fg="red")
            root.update_idletasks()

    def collect_Callback():
        nonlocal df

        if arduino is None:
            arduino_status_var.set("Not connected to Arduino")
            lbl_not_conn.config(fg="red")
            return

        if file_handle is None or file_handle.closed:
            arduino_status_var.set("No active CSV file. Click New File first.")
            lbl_not_conn.config(fg="red")
            return

        try:
            arduino.reset_input_buffer()
            arduino.reset_output_buffer()
        except Exception:
            arduino.flushInput()
            arduino.flushOutput()

        time.sleep(0.05)

        writer = csv.writer(file_handle)
        not_collected = True

        while not_collected:
            test_str = (
                arduino.readline()
                .decode("utf-8", errors="ignore")
                .strip("\n")
                .strip("\r")
            )
            print(test_str)

            if test_str == "Arduino Ready 1":
                print("Arduino Ready")

                while arduino.in_waiting:
                    print(arduino.read())
                    print("In Waiting 1")

                code = "a"
                x_pos = pos_var.get()
                thrust = thrust_var.get()

                while arduino.in_waiting:
                    print(arduino.read())
                    print("In Waiting 2")
                    time.sleep(1)

                arduino.write((code + "\n").encode())
                time.sleep(0.05)

                returned_str = (
                    arduino.readline()
                    .decode("utf-8", errors="ignore")
                    .strip("\n")
                    .strip("\r")
                )
                print(returned_str)

                while not returned_str.startswith("Arduino Data Ready"):
                    arduino.write((code + "\n").encode())
                    time.sleep(3)
                    returned_str = (
                        arduino.readline()
                        .decode("utf-8", errors="ignore")
                        .strip("\n")
                        .strip("\r")
                    )
                    print(returned_str + "1")

                arduino.write("SendData".encode())

                returned_str = (
                    arduino.readline()
                    .decode("utf-8", errors="ignore")
                    .strip("\n")
                    .strip("\r")
                )
                while not returned_str.startswith("Data"):
                    time.sleep(0.05)
                    returned_str = (
                        arduino.readline()
                        .decode("utf-8", errors="ignore")
                        .strip("\n")
                        .strip("\r")
                    )

                print(returned_str)

                modified_str = returned_str.split("Data:,", 1)[1]
                pitot_press_str, ambient_press_str = modified_str.split(",", 1)

                writer.writerow([
                    x_pos,
                    str(float(pitot_press_str) * 100),
                    str(float(ambient_press_str) * 100),
                    thrust,
                ])
                file_handle.flush()

                print("Wrote to CSV")
                df = pd.read_csv(file_handle.name)
                refresh_all(df)
                not_collected = False

                try:
                    arduino.reset_input_buffer()
                    arduino.reset_output_buffer()
                except Exception:
                    arduino.flushInput()
                    arduino.flushOutput()

    def display_dataframe_as_table(parent, df_example):
        tree = ttk.Treeview(parent, columns=list(df_example.columns), show="headings")

        for col in df_example.columns:
            tree.heading(col, text=col)
            tree.column(col, anchor="center", minwidth=0, width=150, stretch=True)

        for _, row in df_example.iterrows():
            tree.insert("", tk.END, values=list(row))

        vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        return tree

    def refresh_plots(dataframe):
        ax1.clear()
        ax1.plot(dataframe["x (mm)"], dataframe["Pressure (Pa)"], color="red")
        ax1.set_xlabel("x (mm)", fontsize=12)
        ax1.set_ylabel("Pressure (Pa)", fontsize=12)

        ax2.clear()
        velocity = np.sqrt(
            np.maximum(
                0,
                2 * (dataframe["Pressure (Pa)"] - dataframe["Ambient (Pa)"]) / AIR_DENSITY,
            )
        )
        ax2.plot(dataframe["x (mm)"], velocity, color="red")
        ax2.set_xlabel("x (mm)", fontsize=12)
        ax2.set_ylabel("V (m/s)", fontsize=12)

        fig_press.canvas.draw()
        fig_velo.canvas.draw()

    def refresh_table(dataframe):
        for row in table.get_children():
            table.delete(row)
        for _, row in dataframe.iterrows():
            table.insert("", tk.END, values=list(row))

    def refresh_all(dataframe):
        refresh_plots(dataframe)
        refresh_table(dataframe)

    def update_gui():
        nonlocal df
        try:
            if file_handle is not None and os.path.exists(file_handle.name):
                new_df = pd.read_csv(file_handle.name)
                df = new_df
                refresh_all(new_df)

            root.after(1000, update_gui)

        except Exception as e:
            print(f"Error during update: {e}")
            root.after(2000, update_gui)

    # ---------- Window layout ----------
    root.grid_columnconfigure(0, weight=3)
    root.grid_columnconfigure(1, weight=2)
    root.grid_columnconfigure(2, weight=1)
    root.grid_columnconfigure(3, weight=1)

    root.grid_rowconfigure(0, weight=0)
    root.grid_rowconfigure(1, weight=3)
    root.grid_rowconfigure(2, weight=3)
    root.grid_rowconfigure(3, weight=1)

    # Top buttons
    btn_lab_details = tk.Button(root, text="Lab Details", bg="#B4DCEB", command=open_lab_details)
    btn_lab_details.grid(column=2, row=0, sticky="ew", padx=4, pady=4)

    btn_exit = tk.Button(root, text="Exit", bg="#F28484", command=on_close)
    btn_exit.grid(column=3, row=0, sticky="ew", padx=4, pady=4)

    # Pressure graph frame
    frame_PX = tk.Frame(root, bg="white")
    frame_PX.grid(column=0, row=1, columnspan=2, sticky="nsew", padx=8, pady=8)
    frame_PX.grid_columnconfigure(0, weight=1)
    frame_PX.grid_rowconfigure(1, weight=1)

    lbl_PX = tk.Label(
        frame_PX,
        text="Absolute Pressure vs X-Position",
        font=("Arial", 20),
        bg="white",
    )
    lbl_PX.grid(column=0, row=0, sticky="nsew")

    fig_press = plt.Figure(figsize=(2.5, 2.5), dpi=100)
    canvas_press = FigureCanvasTkAgg(fig_press, frame_PX)
    canvas_press.get_tk_widget().grid(column=0, row=1, sticky="nsew")
    ax1 = fig_press.add_subplot(111)
    fig_press.tight_layout(pad=2.0)
    fig_press.set_constrained_layout(True)

    # Velocity graph frame
    frame_VX = tk.Frame(root, bg="white")
    frame_VX.grid(column=0, row=2, columnspan=2, sticky="nsew", padx=8, pady=8)
    frame_VX.grid_columnconfigure(0, weight=1)
    frame_VX.grid_rowconfigure(1, weight=1)

    lbl_VX = tk.Label(
        frame_VX,
        text="Velocity vs X-Position",
        bg="white",
        font=("Arial", 20),
    )
    lbl_VX.grid(column=0, row=0, sticky="nsew")

    fig_velo = plt.Figure(figsize=(2.5, 2.5), dpi=100)
    canvas_velo = FigureCanvasTkAgg(fig_velo, frame_VX)
    canvas_velo.get_tk_widget().grid(column=0, row=1, sticky="nsew")
    ax2 = fig_velo.add_subplot(111)
    fig_velo.tight_layout(pad=2.0)
    fig_velo.set_constrained_layout(True)

    # Data table
    frame_DT = tk.Frame(root, bg="white")
    frame_DT.grid(column=2, row=1, columnspan=2, rowspan=2, sticky="nsew", padx=8, pady=8)

    table = display_dataframe_as_table(frame_DT, df)

    # Arduino status
    frame_status = tk.Frame(root, bg="white")
    frame_status.grid(column=0, row=3, sticky="nsew", padx=15, pady=15)

    for i in range(2):
        frame_status.grid_columnconfigure(i, weight=1, minsize=120)
    for j in range(3):
        frame_status.grid_rowconfigure(j, weight=1, minsize=30)

    lbl_arduino = tk.Label(frame_status, text="Arduino Status:", bg="white")
    lbl_arduino.grid(column=0, row=0, sticky="ew")

    lbl_not_conn = tk.Label(frame_status, textvariable=arduino_status_var, fg="red", bg="white")
    lbl_not_conn.grid(column=1, row=0, sticky="ew")

    lbl_port = tk.Label(frame_status, text="Port:", bg="white")
    lbl_port.grid(column=0, row=1, sticky="ew")

    port_entry = tk.Entry(frame_status, textvariable=port_var)
    port_entry.grid(column=1, row=1, sticky="ew")

    btn_connect = tk.Button(frame_status, text="Connect", bg="#B0CA99", command=auto_connect_arduino)
    btn_connect.grid(column=0, row=2, columnspan=2, sticky="ew", pady=(8, 0))

    # Thrust / position frame
    frame_tp = tk.Frame(root, bg="white")
    frame_tp.grid(column=1, row=3, sticky="nsew", padx=15, pady=15)
    frame_tp.grid_columnconfigure(0, weight=1, minsize=200)

    for i in range(4):
        frame_tp.grid_rowconfigure(i, weight=1)

    lbl_thrust = tk.Label(frame_tp, text="Thrust (g)", bg="white")
    lbl_thrust.grid(column=0, row=0, sticky="ew")

    thrust_entry = tk.Entry(frame_tp, textvariable=thrust_var)
    thrust_entry.grid(column=0, row=1, sticky="ew")

    lbl_position = tk.Label(frame_tp, text="Position:", bg="white")
    lbl_position.grid(column=0, row=2, sticky="ew")

    position_entry = tk.Entry(frame_tp, textvariable=pos_var)
    position_entry.grid(column=0, row=3, sticky="ew")

    # Bottom buttons
    btn_collect = tk.Button(root, text="Collect", bg="#B0CA99", command=collect_Callback)
    btn_collect.grid(column=2, row=3, sticky="nsew", padx=8, pady=15, ipady=18)

    btn_new_file = tk.Button(root, text="New File", bg="#1E90FF", command=newfile_Callback)
    btn_new_file.grid(column=3, row=3, sticky="nsew", padx=8, pady=15, ipady=18)

    # Initialize file + plots
    newfile_Callback()
    update_gui()

    if standalone_root is not None:
        standalone_root.mainloop()


def show_welcome_screen():
    root = tk.Tk()
    root.title("Welcome")
    root.geometry("1100x800")
    root.minsize(900, 650)
    root.configure(bg="#dbe6f5")

    root.grid_columnconfigure(0, weight=1)
    for r in range(7):
        root.grid_rowconfigure(r, weight=1)

    title = tk.Label(
        root,
        text="Laboratory Control Suite",
        font=("Arial", 38, "bold"),
        bg="#dbe6f5",
        fg="#0c366b",
    )
    title.grid(row=1, column=0, pady=(30, 10))

    subtitle = tk.Label(
        root,
        text="Select an experiment to begin",
        font=("Arial", 20),
        bg="#dbe6f5",
        fg="#0c366b",
    )
    subtitle.grid(row=2, column=0, pady=(0, 30))

    button_frame = tk.Frame(root, bg="#dbe6f5")
    button_frame.grid(row=3, column=0)

    btn_thrust = tk.Button(
        button_frame,
        text="Launch Thrust Stand",
        font=("Arial", 18, "bold"),
        bg="#1e90ff",
        fg="white",
        width=24,
        height=2,
        command=lambda: launch_thrust_stand(root),
    )
    btn_thrust.grid(row=0, column=0, pady=10)

    btn_pipe = tk.Button(
        button_frame,
        text="Launch Pipe Flow",
        font=("Arial", 18, "bold"),
        bg="#28a745",
        fg="white",
        width=24,
        height=2,
        command=lambda: launch_pipe_flow(root),
    )
    btn_pipe.grid(row=1, column=0, pady=10)

    btn_wind = tk.Button(
        button_frame,
        text="Launch Wind Tunnel",
        font=("Arial", 18, "bold"),
        bg="#ff8c00",
        fg="white",
        width=24,
        height=2,
        command=lambda: launch_wind_tunnel(root),
    )
    btn_wind.grid(row=2, column=0, pady=10)

    root.mainloop()


if __name__ == "__main__":
    show_welcome_screen()