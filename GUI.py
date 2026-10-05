import tkinter as tk
from tkinter import ttk
import os
import webbrowser
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import serial
import serial.tools.list_ports
from datetime import datetime
import csv
import time
import pandas as pd
import numpy as np
from tkmacosx import Button
import customtkinter as ctk

AIR_DENSITY = 1.298351265  # kg/m^3
LAB_DETAILS_URL = "https://drive.google.com/file/d/1WX5xK7Xqua2Vz-lO5Z7_klDieToz0dC8/view?usp=sharing"

SENSOR_COLORS = ["#1E90FF", "#F28484", "#28A745", "#FF8C00"]


def launch_thrust_stand(master=None):
    _launch_experiment(master, "Thrust Stand Experiment")


def launch_pipe_flow(master=None):
    _launch_pipe_flow_window(master)


def launch_wind_tunnel(master=None):
    _launch_wind_tunnel_window(master)


def launch_diagnostic(master=None):
    _launch_diagnostic_window(master)


# ---------------------------------------------------------------------------
#  DIAGNOSTIC WINDOW
# ---------------------------------------------------------------------------

def _launch_diagnostic_window(master):
    standalone_root = None

    if master is None:
        standalone_root = tk.Tk()
        standalone_root.withdraw()
        master = standalone_root
    else:
        master.withdraw()

    root = tk.Toplevel(master)
    root.title("Diagnostic Test")
    root.geometry("1000x700")
    root.configure(bg="white")

    arduino = None
    running = False
    times = []
    sensor_pressures = []
    start_time = None

    def on_close():
        nonlocal running
        running = False
        try:
            if arduino is not None and arduino.is_open:
                arduino.close()
        except Exception:
            pass
        root.destroy()
        if standalone_root is not None:
            standalone_root.destroy()
        else:
            master.deiconify()

    root.protocol("WM_DELETE_WINDOW", on_close)

    arduino_status_var = tk.StringVar(value="Not Connected")
    port_var = tk.StringVar()

    def find_arduino_port():
        ports = serial.tools.list_ports.comports()
        for port in ports:
            desc = (port.description or "").lower()
            if any(k in desc for k in ["arduino", "usb serial", "usb to uart", "ch340", "cp210", "silicon labs"]):
                return port.device
        return None

    def connect_arduino():
        nonlocal arduino
        port = port_var.get().strip() or find_arduino_port()
        if not port:
            arduino_status_var.set("No Arduino found")
            lbl_status.config(fg="red")
            return
        try:
            port_var.set(port)
            arduino = serial.Serial(port=port, baudrate=115200, timeout=0.1)
            arduino_status_var.set(f"Connected: {port}")
            lbl_status.config(fg="green")
        except serial.SerialException as e:
            arduino_status_var.set(f"Failed: {e}")
            lbl_status.config(fg="red")
            arduino = None

    def poll_arduino():
        nonlocal running, start_time
        if not running:
            return
        if arduino is None or not arduino.is_open:
            root.after(500, poll_arduino)
            return

        try:
            line = arduino.readline().decode("utf-8", errors="ignore").strip()
            if line.startswith("Data:,"):
                parts = line.split("Data:,", 1)[1].split(",")
                values = []
                for p in parts:
                    try:
                        values.append(float(p) * 100)
                    except ValueError:
                        values.append(None)

                if not sensor_pressures:
                    for _ in values:
                        sensor_pressures.append([])

                elapsed = time.time() - start_time
                times.append(elapsed)
                for i, v in enumerate(values):
                    if i < len(sensor_pressures):
                        sensor_pressures[i].append(v)

                cutoff = elapsed - 60
                while times and times[0] < cutoff:
                    times.pop(0)
                    for sp in sensor_pressures:
                        if sp:
                            sp.pop(0)

                ax.clear()
                for i, sp in enumerate(sensor_pressures):
                    ax.plot(times[:len(sp)], sp,
                            color=SENSOR_COLORS[i % len(SENSOR_COLORS)],
                            linewidth=1.5,
                            label=f"Sensor {i + 1}")
                ax.set_xlabel("Time (s)", fontsize=16)
                ax.set_ylabel("Pressure (Pa)", fontsize=16)
                ax.set_title("Live Pressure", fontsize=20)
                ax.legend()
                fig.tight_layout()
                canvas.draw()
        except Exception:
            pass

        root.after(100, poll_arduino)

    def start_stop():
        nonlocal running, start_time, times, sensor_pressures, arduino
        if not running:
            if arduino is None:
                arduino_status_var.set("Connect to Arduino first")
                lbl_status.config(fg="red")
                return
            times.clear()
            sensor_pressures.clear()
            start_time = time.time()
            running = True
            arduino.write("DIAG\n".encode())
            arduino.flush()
            btn_startstop.config(text="Stop", bg="#F28484")
            poll_arduino()
        else:
            running = False
            arduino.write("STOP\n".encode())
            arduino.flush()
            btn_startstop.config(text="Start", bg="#B0CA99")

    root.grid_rowconfigure(0, weight=1)
    root.grid_rowconfigure(1, weight=0)
    root.grid_columnconfigure(0, weight=1)

    frame_plot = tk.Frame(root, bg="white")
    frame_plot.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
    frame_plot.grid_rowconfigure(0, weight=1)
    frame_plot.grid_columnconfigure(0, weight=1)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.set_xlabel("Time (s)", fontsize=16)
    ax.set_ylabel("Pressure (Pa)", fontsize=16)
    ax.set_title("Live Pressure", fontsize=20, fontweight="bold")
    canvas = FigureCanvasTkAgg(fig, frame_plot)
    canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

    frame_ctrl = tk.Frame(root, bg="white")
    frame_ctrl.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

    tk.Label(frame_ctrl, text="Port:", bg="white", font=("Arial", 14)).pack(side="left", padx=(0, 4))
    tk.Entry(frame_ctrl, textvariable=port_var, font=("Arial", 14), width=14).pack(side="left", padx=(0, 8))

    Button(frame_ctrl, text="Connect", bg="#B0CA99", font=("Arial", 14),
           command=connect_arduino).pack(side="left", padx=(0, 8))

    lbl_status = tk.Label(frame_ctrl, textvariable=arduino_status_var,
                          fg="red", bg="white", font=("Arial", 14))
    lbl_status.pack(side="left", padx=(0, 20))

    Button(frame_ctrl, text="Exit", bg="#F28484", font=("Arial", 14),
           command=on_close).pack(side="right", padx=(8, 0))

    btn_startstop = Button(frame_ctrl, text="Start", bg="#B0CA99",
                           font=("Arial", 14), command=start_stop)
    btn_startstop.pack(side="right", padx=(0, 8))

    if standalone_root is not None:
        standalone_root.mainloop()


# ---------------------------------------------------------------------------
#  PIPE FLOW WINDOW  — 4 pressure sensors, dedicated layout
# ---------------------------------------------------------------------------

def _launch_pipe_flow_window(master):
    standalone_root = None

    if master is None:
        standalone_root = tk.Tk()
        standalone_root.withdraw()
        master = standalone_root
    else:
        master.withdraw()

    root = tk.Toplevel(master)
    root.title("Pipe Flow Experiment")
    root.geometry("1440x900")
    root.minsize(1100, 700)
    root.configure(bg="white")

    # ── state ──────────────────────────────────────────────────────────────
    pos_var           = tk.StringVar(value="0")
    level_var         = tk.IntVar(value=1)
    port_var          = tk.StringVar()
    arduino_status_var = tk.StringVar(value="Not Connected")

    arduino        = None
    file_handle    = None
    NUM_SENSORS    = 4
    detected_ports = []
    CSV_COLS       = ["data #"] + [f"Sensor {i+1} - Pressure (Pa)" for i in range(NUM_SENSORS)]

    df = pd.DataFrame(columns=CSV_COLS)

    def _get_csv_cols():
        if detected_ports:
            return ["data #"] + [f"MUX Port {p} - Pressure (Pa)" for p in detected_ports]
        return ["data #"] + [f"Port {i} - Pressure (Pa)" for i in range(NUM_SENSORS)]

    # ── helpers ────────────────────────────────────────────────────────────

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
        nonlocal file_handle, df, table

        CSV_COLS[:] = _get_csv_cols()

        for widget in frame_DT.winfo_children():
            widget.destroy()
        table = build_table(frame_DT)

        try:
            if file_handle is not None and not file_handle.closed:
                file_handle.close()
        except Exception:
            pass

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename  = f"pipe_flow_{timestamp}.csv"

        save_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.isdir(save_dir):
            save_dir = os.path.expanduser("~")
        if not os.access(save_dir, os.W_OK):
            save_dir = os.getcwd()

        filepath = os.path.join(save_dir, filename)
        print(f"Writing pipe flow data to {filepath}…")

        try:
            file_handle = open(filepath, "w", newline="")
            writer = csv.writer(file_handle)
            writer.writerow(CSV_COLS)
            file_handle.flush()

            df = pd.DataFrame(columns=CSV_COLS)
            refresh_all(df)
        except Exception as e:
            print(f"Error creating CSV: {e}")
            arduino_status_var.set(f"Can't create file: {e}")
            lbl_not_conn.config(fg="red")
            file_handle = None

    def find_arduino_port():
        ports = serial.tools.list_ports.comports()
        for port in ports:
            desc = (port.description or "").lower()
            print(port.device, "-", desc)
            if any(k in desc for k in ["arduino", "usb serial", "usb to uart", "ch340", "cp210", "silicon labs"]):
                print(f"Found Arduino on port: {port.device}")
                return port.device
        print("No Arduino found")
        return None

    def query_ports():
        if arduino is None:
            return
        arduino.write("PORTS\n".encode())
        arduino.flush()
        deadline = time.time() + 3
        while time.time() < deadline:
            if arduino.in_waiting:
                line = arduino.readline().decode("utf-8", errors="ignore").strip()
                if line.startswith("Ports:,"):
                    parts = line.split("Ports:,", 1)[1].split(",")
                    detected_ports[:] = [int(p) for p in parts if p.strip().isdigit()]
                    print(f"Detected MUX ports: {detected_ports}")
                    break
            else:
                time.sleep(0.1)

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

            arduino = serial.Serial(port=port, baudrate=115200, timeout=1.0)
            time.sleep(2)
            arduino.reset_input_buffer()
            arduino.write("GReady\n".encode())
            time.sleep(0.5)

            attempts = 0
            while attempts < 10:
                if arduino.in_waiting:
                    line = arduino.readline().decode("utf-8", errors="ignore").strip()
                    print(f"Arduino says: {line}")
                    if "Arduino Ready" in line or "Ready" in line:
                        break
                else:
                    arduino.write("GReady\n".encode())
                    time.sleep(0.5)
                attempts += 1

            query_ports()
            if detected_ports:
                newfile_Callback()
            arduino_status_var.set(f"Connected to {port}")
            lbl_not_conn.config(fg="green")

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

        writer  = csv.writer(file_handle)
        x_pos   = pos_var.get()

        arduino.write("a\n".encode())
        arduino.flush()
        print("Sent 'a' command")

        timeout  = time.time() + 15
        got_data = False

        while time.time() < timeout:
            if arduino.in_waiting:
                line = arduino.readline().decode("utf-8", errors="ignore").strip()
                print(f"Received: {line}")

                if line.startswith("Data:,"):
                    try:
                        raw_vals = line.split("Data:,", 1)[1].split(",")
                        # Convert hPa → Pa, pad with 0.0 if fewer than NUM_SENSORS values
                        pressures = []
                        for i in range(NUM_SENSORS):
                            try:
                                pressures.append(float(raw_vals[i]) * 100)
                            except (IndexError, ValueError):
                                pressures.append(0.0)

                        row = [x_pos] + [str(p) for p in pressures]
                        writer.writerow(row)
                        file_handle.flush()
                        print(f"Wrote to CSV: {row}")

                        df = pd.read_csv(file_handle.name)
                        refresh_all(df)
                        got_data = True

                        # Auto-increment position
                        try:
                            current_pos = float(pos_var.get())
                            pos_var.set(str(int(current_pos + level_var.get())))
                        except ValueError:
                            pass
                        break

                    except Exception as e:
                        print(f"Parse error: {e} — line was: {line}")
                        continue
            else:
                time.sleep(0.1)

        if not got_data:
            arduino_status_var.set("Timeout: no data received. Check sensors.")
            lbl_not_conn.config(fg="red")
            print("Collect timed out")

        try:
            arduino.reset_input_buffer()
            arduino.reset_output_buffer()
        except Exception:
            arduino.flushInput()
            arduino.flushOutput()

    # ── plotting ────────────────────────────────────────────────────────────

    def refresh_plots(dataframe):
        pressure_cols = CSV_COLS[1:]  # skip "data #"
        for i, ax in enumerate(axes):
            ax.clear()
            col = pressure_cols[i] if i < len(pressure_cols) else None
            ax.set_xlabel("data #", fontsize=10)
            ax.set_ylabel("Pressure (Pa)", fontsize=10)
            ax.set_title(col or f"Sensor {i+1}", fontsize=12, fontweight="bold",
                         color=SENSOR_COLORS[i])
            if not dataframe.empty and col and col in dataframe.columns:
                ax.plot(dataframe["data #"], dataframe[col],
                        color=SENSOR_COLORS[i], linewidth=1.8)
            figs[i].tight_layout()
            canvases[i].draw()

    # ── table ───────────────────────────────────────────────────────────────

    def build_table(parent):
        tree = ttk.Treeview(parent, columns=CSV_COLS, show="headings")
        for col in CSV_COLS:
            tree.heading(col, text=col)
            tree.column(col, anchor="center", width=110, stretch=True)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        return tree

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
        except Exception as e:
            print(f"Update error: {e}")
        root.after(1000, update_gui)

    # ── layout ──────────────────────────────────────────────────────────────
    #
    #  col 0-1 : 2×2 graph grid   col 2-3 : table + controls
    #  row 0   : top bar
    #  row 1-2 : graphs / table
    #  row 3   : bottom controls

    root.grid_columnconfigure(0, weight=3)
    root.grid_columnconfigure(1, weight=3)
    root.grid_columnconfigure(2, weight=2)
    root.grid_columnconfigure(3, weight=2)
    for r in range(4):
        root.grid_rowconfigure(r, weight=1 if r in (1, 2) else 0)

    # Top bar
    Button(root, text="Lab Details", bg="#B4DCEB", font=("Arial", 13),
           command=open_lab_details).grid(row=0, column=2, sticky="ew", padx=4, pady=4)
    Button(root, text="Exit", bg="#F28484", font=("Arial", 13),
           command=on_close).grid(row=0, column=3, sticky="ew", padx=4, pady=4)

    # ── 2×2 graph grid ──────────────────────────────────────────────────────
    graph_positions = [(1, 0), (1, 1), (2, 0), (2, 1)]
    figs, axes, canvases = [], [], []

    for idx, (grow, gcol) in enumerate(graph_positions):
        frame = tk.Frame(root, bg="white", relief="flat", bd=1)
        frame.grid(row=grow, column=gcol, sticky="nsew", padx=6, pady=6)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        fig, ax = plt.subplots(figsize=(4, 2.8))
        ax.set_xlabel("data #", fontsize=10)
        ax.set_ylabel("Pressure (Pa)", fontsize=10)
        ax.set_title(f"Sensor {idx+1}", fontsize=12, fontweight="bold",
                     color=SENSOR_COLORS[idx])
        fig.tight_layout()

        cv = FigureCanvasTkAgg(fig, frame)
        cv.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        figs.append(fig)
        axes.append(ax)
        canvases.append(cv)

    # ── data table ──────────────────────────────────────────────────────────
    frame_DT = tk.Frame(root, bg="white")
    frame_DT.grid(row=1, column=2, columnspan=2, rowspan=2,
                  sticky="nsew", padx=8, pady=8)
    table = build_table(frame_DT)

    # ── arduino status ──────────────────────────────────────────────────────
    frame_status = tk.Frame(root, bg="white")
    frame_status.grid(row=3, column=0, sticky="nsew", padx=15, pady=10)
    for i in range(2):
        frame_status.grid_columnconfigure(i, weight=1, minsize=120)
    for j in range(3):
        frame_status.grid_rowconfigure(j, weight=1, minsize=30)

    tk.Label(frame_status, text="Arduino Status:", bg="white",
             font=("Arial", 15)).grid(row=0, column=0, sticky="ew")
    lbl_not_conn = tk.Label(frame_status, textvariable=arduino_status_var,
                            fg="red", bg="white", font=("Arial", 15))
    lbl_not_conn.grid(row=0, column=1, sticky="ew")

    tk.Label(frame_status, text="Port:", bg="white",
             font=("Arial", 15)).grid(row=1, column=0, sticky="ew")
    tk.Entry(frame_status, textvariable=port_var,
             font=("Arial", 13)).grid(row=1, column=1, sticky="ew")

    Button(frame_status, text="Connect", bg="#B0CA99", font=("Arial", 14),
           command=auto_connect_arduino).grid(row=2, column=0, columnspan=2,
                                              sticky="ew", pady=(8, 0))

    # ── position / level ────────────────────────────────────────────────────
    frame_tp = tk.Frame(root, bg="white")
    frame_tp.grid(row=3, column=1, sticky="nsew", padx=15, pady=10)
    frame_tp.grid_columnconfigure(0, weight=1)
    for i in range(6):
        frame_tp.grid_rowconfigure(i, weight=1)

    tk.Label(frame_tp, text="Data Collection number:", bg="white",
             font=("Arial", 15)).grid(row=0, column=0, sticky="ew")
    tk.Entry(frame_tp, textvariable=pos_var,
             font=("Arial", 13)).grid(row=1, column=0, sticky="ew")

    auto_increment_var = ctk.BooleanVar(value=True)
    ctk.CTkSwitch(frame_tp, text="Auto-increment (+1)", variable=auto_increment_var,
                  font=("Arial", 13),
                  command=lambda: level_var.set(1 if auto_increment_var.get() else 0)
                  ).grid(row=2, column=0, sticky="w", pady=(8, 0))

    # ── bottom action buttons ───────────────────────────────────────────────
    Button(root, text="Collect", bg="#B0CA99", font=("Arial", 16),
           command=collect_Callback).grid(row=3, column=2, sticky="nsew",
                                          padx=8, pady=12, ipady=16)
    Button(root, text="New File", bg="#1E90FF", font=("Arial", 16),
           command=newfile_Callback).grid(row=3, column=3, sticky="nsew",
                                          padx=8, pady=12, ipady=16)

    # ── init ────────────────────────────────────────────────────────────────
    newfile_Callback()
    update_gui()

    if standalone_root is not None:
        standalone_root.mainloop()


#  WIND TUNNEL WINDOW  

def _launch_wind_tunnel_window(master):
    standalone_root = None

    if master is None:
        standalone_root = tk.Tk()
        standalone_root.withdraw()
        master = standalone_root
    else:
        master.withdraw()

    root = tk.Toplevel(master)
    root.title("Wind Tunnel Experiment")
    root.geometry("1440x900")
    root.minsize(1100, 700)
    root.configure(bg="white")

    # ── state ──────────────────────────────────────────────────────────────
    pos_var            = tk.StringVar(value="0")
    level_var          = tk.IntVar(value=1)
    drag_var           = tk.StringVar()
    object_var         = tk.StringVar(value="Big Teardrop")
    port_var           = tk.StringVar()
    arduino_status_var = tk.StringVar(value="Not Connected")

    OBJECT_TYPES   = ["Big Teardrop", "Small Teardrop", "Half-Sphere"]
    detected_ports = []
    CSV_COLS       = ["data #", "Object Type", "Drag Force (N)",
                      "Port 0 - Static Ambient Pressure (Pa)", "Port 1 - Static Inside Pressure (Pa)"]

    arduino     = None
    file_handle = None
    df          = pd.DataFrame(columns=CSV_COLS)

    def _get_csv_cols():
        if len(detected_ports) >= 2:
            return ["data #", "Object Type", "Drag Force (N)",
                    f"MUX Port {detected_ports[0]} - Static Ambient Pressure (Pa)",
                    f"MUX Port {detected_ports[1]} - Static Inside Pressure (Pa)"]
        return ["data #", "Object Type", "Drag Force (N)",
                "Port 0 - Static Ambient Pressure (Pa)", "Port 1 - Static Inside Pressure (Pa)"]

    # ── helpers ────────────────────────────────────────────────────────────

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
        nonlocal file_handle, df, table

        CSV_COLS[:] = _get_csv_cols()

        for widget in frame_DT.winfo_children():
            widget.destroy()
        table = build_table(frame_DT)

        try:
            if file_handle is not None and not file_handle.closed:
                file_handle.close()
        except Exception:
            pass

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename  = f"wind_tunnel_{timestamp}.csv"

        save_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.isdir(save_dir):
            save_dir = os.path.expanduser("~")
        if not os.access(save_dir, os.W_OK):
            save_dir = os.getcwd()

        filepath = os.path.join(save_dir, filename)
        print(f"Writing wind tunnel data to {filepath}…")

        try:
            file_handle = open(filepath, "w", newline="")
            writer = csv.writer(file_handle)
            writer.writerow(CSV_COLS)
            file_handle.flush()
            df = pd.DataFrame(columns=CSV_COLS)
            refresh_all(df)
        except Exception as e:
            print(f"Error creating CSV: {e}")
            arduino_status_var.set(f"Can't create file: {e}")
            lbl_not_conn.config(fg="red")
            file_handle = None

    def find_arduino_port():
        ports = serial.tools.list_ports.comports()
        for port in ports:
            desc = (port.description or "").lower()
            if any(k in desc for k in ["arduino", "usb serial", "usb to uart", "ch340", "cp210", "silicon labs"]):
                return port.device
        return None

    def query_ports():
        if arduino is None:
            return
        arduino.write("PORTS\n".encode())
        arduino.flush()
        deadline = time.time() + 3
        while time.time() < deadline:
            if arduino.in_waiting:
                line = arduino.readline().decode("utf-8", errors="ignore").strip()
                if line.startswith("Ports:,"):
                    parts = line.split("Ports:,", 1)[1].split(",")
                    detected_ports[:] = [int(p) for p in parts if p.strip().isdigit()]
                    print(f"Detected MUX ports: {detected_ports}")
                    break
            else:
                time.sleep(0.1)

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

            arduino = serial.Serial(port=port, baudrate=115200, timeout=1.0)
            time.sleep(2)
            arduino.reset_input_buffer()
            arduino.write("GReady\n".encode())
            time.sleep(0.5)

            attempts = 0
            while attempts < 10:
                if arduino.in_waiting:
                    line = arduino.readline().decode("utf-8", errors="ignore").strip()
                    if "Arduino Ready" in line or "Ready" in line:
                        break
                else:
                    arduino.write("GReady\n".encode())
                    time.sleep(0.5)
                attempts += 1

            query_ports()
            if detected_ports:
                newfile_Callback()
            arduino_status_var.set(f"Connected to {port}")
            lbl_not_conn.config(fg="green")

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

        writer      = csv.writer(file_handle)
        x_pos       = pos_var.get()
        drag        = drag_var.get()
        object_type = object_var.get()

        arduino.write("a\n".encode())
        arduino.flush()

        timeout  = time.time() + 15
        got_data = False

        while time.time() < timeout:
            if arduino.in_waiting:
                line = arduino.readline().decode("utf-8", errors="ignore").strip()
                print(f"Received: {line}")

                if line.startswith("Data:,"):
                    try:
                        parts = line.split("Data:,", 1)[1].split(",")
                        ambient_press = float(parts[0]) * 100 if len(parts) > 0 else 0.0
                        inside_press  = float(parts[1]) * 100 if len(parts) > 1 else 0.0

                        row = [x_pos, object_type, drag,
                               str(ambient_press), str(inside_press)]
                        writer.writerow(row)
                        file_handle.flush()
                        print(f"Wrote to CSV: {row}")

                        df = pd.read_csv(file_handle.name)
                        refresh_all(df)
                        got_data = True

                        try:
                            current_pos = float(pos_var.get())
                            pos_var.set(str(int(current_pos + level_var.get())))
                        except ValueError:
                            pass
                        break

                    except Exception as e:
                        print(f"Parse error: {e} — line was: {line}")
                        continue
            else:
                time.sleep(0.1)

        if not got_data:
            arduino_status_var.set("Timeout: no data received. Check sensors.")
            lbl_not_conn.config(fg="red")

        try:
            arduino.reset_input_buffer()
            arduino.reset_output_buffer()
        except Exception:
            arduino.flushInput()
            arduino.flushOutput()

    # ── plotting ────────────────────────────────────────────────────────────

    def refresh_plots(dataframe):
        ax_amb.clear()
        ax_amb.set_xlabel("data #", fontsize=11)
        ax_amb.set_ylabel("Pressure (Pa)", fontsize=11)
        ax_amb.set_title("Static Ambient Pressure", fontsize=13, fontweight="bold",
                         color=SENSOR_COLORS[0])
        amb_col = CSV_COLS[3]
        if not dataframe.empty and amb_col in dataframe.columns:
            ax_amb.plot(dataframe["data #"], dataframe[amb_col],
                        color=SENSOR_COLORS[0], linewidth=1.8)
        fig_amb.tight_layout()
        canvas_amb.draw()

        ins_col = CSV_COLS[4]
        ax_ins.clear()
        ax_ins.set_xlabel("data #", fontsize=11)
        ax_ins.set_ylabel("Pressure (Pa)", fontsize=11)
        ax_ins.set_title("Static Inside Pressure", fontsize=13, fontweight="bold",
                         color=SENSOR_COLORS[1])
        if not dataframe.empty and ins_col in dataframe.columns:
            ax_ins.plot(dataframe["data #"], dataframe[ins_col],
                        color=SENSOR_COLORS[1], linewidth=1.8)
        fig_ins.tight_layout()
        canvas_ins.draw()



    def build_table(parent):
        tree = ttk.Treeview(parent, columns=CSV_COLS, show="headings")
        for col in CSV_COLS:
            tree.heading(col, text=col)
            tree.column(col, anchor="center", width=130, stretch=True)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        return tree

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
        except Exception as e:
            print(f"Update error: {e}")
        root.after(1000, update_gui)


    root.grid_columnconfigure(0, weight=3)
    root.grid_columnconfigure(1, weight=3)
    root.grid_columnconfigure(2, weight=2)
    root.grid_columnconfigure(3, weight=2)
    for r in range(4):
        root.grid_rowconfigure(r, weight=1 if r in (1, 2) else 0)

    # Top bar
    Button(root, text="Lab Details", bg="#B4DCEB", font=("Arial", 13),
           command=open_lab_details).grid(row=0, column=2, sticky="ew", padx=4, pady=4)
    Button(root, text="Exit", bg="#F28484", font=("Arial", 13),
           command=on_close).grid(row=0, column=3, sticky="ew", padx=4, pady=4)

    # ── ambient pressure graph ──────────────────────────────────────────────
    frame_amb = tk.Frame(root, bg="white")
    frame_amb.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)
    frame_amb.grid_rowconfigure(0, weight=1)
    frame_amb.grid_columnconfigure(0, weight=1)

    fig_amb, ax_amb = plt.subplots(figsize=(5, 2.8))
    ax_amb.set_xlabel("data #", fontsize=11)
    ax_amb.set_ylabel("Pressure (Pa)", fontsize=11)
    ax_amb.set_title("Static Ambient Pressure", fontsize=13, fontweight="bold",
                     color=SENSOR_COLORS[0])
    fig_amb.tight_layout()
    canvas_amb = FigureCanvasTkAgg(fig_amb, frame_amb)
    canvas_amb.get_tk_widget().grid(row=0, column=0, sticky="nsew")

    # ── inside pressure graph ───────────────────────────────────────────────
    frame_ins = tk.Frame(root, bg="white")
    frame_ins.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)
    frame_ins.grid_rowconfigure(0, weight=1)
    frame_ins.grid_columnconfigure(0, weight=1)

    fig_ins, ax_ins = plt.subplots(figsize=(5, 2.8))
    ax_ins.set_xlabel("data #", fontsize=11)
    ax_ins.set_ylabel("Pressure (Pa)", fontsize=11)
    ax_ins.set_title("Static Inside Pressure", fontsize=13, fontweight="bold",
                     color=SENSOR_COLORS[1])
    fig_ins.tight_layout()
    canvas_ins = FigureCanvasTkAgg(fig_ins, frame_ins)
    canvas_ins.get_tk_widget().grid(row=0, column=0, sticky="nsew")

    # ── data table ──────────────────────────────────────────────────────────
    frame_DT = tk.Frame(root, bg="white")
    frame_DT.grid(row=1, column=2, columnspan=2, rowspan=2,
                  sticky="nsew", padx=8, pady=8)
    table = build_table(frame_DT)

    # ── arduino status ──────────────────────────────────────────────────────
    frame_status = tk.Frame(root, bg="white")
    frame_status.grid(row=3, column=0, sticky="nsew", padx=15, pady=10)
    for i in range(2):
        frame_status.grid_columnconfigure(i, weight=1, minsize=120)
    for j in range(3):
        frame_status.grid_rowconfigure(j, weight=1, minsize=30)

    tk.Label(frame_status, text="Arduino Status:", bg="white",
             font=("Arial", 15)).grid(row=0, column=0, sticky="ew")
    lbl_not_conn = tk.Label(frame_status, textvariable=arduino_status_var,
                            fg="red", bg="white", font=("Arial", 15))
    lbl_not_conn.grid(row=0, column=1, sticky="ew")

    tk.Label(frame_status, text="Port:", bg="white",
             font=("Arial", 15)).grid(row=1, column=0, sticky="ew")
    tk.Entry(frame_status, textvariable=port_var,
             font=("Arial", 13)).grid(row=1, column=1, sticky="ew")

    Button(frame_status, text="Connect", bg="#B0CA99", font=("Arial", 14),
           command=auto_connect_arduino).grid(row=2, column=0, columnspan=2,
                                              sticky="ew", pady=(8, 0))

    # ── experiment inputs ───────────────────────────────────────────────────
    _script_dir = os.path.dirname(os.path.abspath(__file__))

    def _load_image(filename, size=50):
        path = os.path.join(_script_dir, filename)
        if not os.path.isfile(path):
            return None
        try:
            from PIL import Image, ImageTk
            img = Image.open(path).convert("RGBA")
            img.thumbnail((size, size), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except ImportError:
            photo = tk.PhotoImage(file=path)
            factor = max(1, photo.width() // size, photo.height() // size)
            return photo.subsample(factor, factor)

    _object_images = {
        "Big Teardrop":   _load_image("Large_Teardrop.webp", size=90),
        "Small Teardrop": _load_image("Small_Teardrop.webp", size=50),
        "Half-Sphere":    _load_image("Half_Sphere.png",     size=70),
    }

    frame_inputs = tk.Frame(root, bg="white")
    frame_inputs.grid(row=3, column=1, sticky="nsew", padx=15, pady=10)
    frame_inputs.grid_columnconfigure(0, weight=1)
    for i in range(8):
        frame_inputs.grid_rowconfigure(i, weight=1)

    tk.Label(frame_inputs, text="Object Type:", bg="white",
             font=("Arial", 15)).grid(row=0, column=0, sticky="w")

    lbl_obj_img = tk.Label(frame_inputs, bg="white")
    lbl_obj_img.grid(row=1, column=0, pady=(2, 4))

    combo_obj = ttk.Combobox(frame_inputs, textvariable=object_var, values=OBJECT_TYPES,
                             state="readonly", font=("Arial", 13))
    combo_obj.grid(row=2, column=0, sticky="ew")

    def _update_object_image(*_):
        img = _object_images.get(object_var.get())
        if img:
            lbl_obj_img.config(image=img, text="")
            lbl_obj_img.image = img
        else:
            lbl_obj_img.config(image="", text="(no image)")
            lbl_obj_img.image = None

    object_var.trace_add("write", _update_object_image)
    _update_object_image()

    tk.Label(frame_inputs, text="Drag Force (N):", bg="white",
             font=("Arial", 15)).grid(row=3, column=0, sticky="w", pady=(8, 0))
    tk.Entry(frame_inputs, textvariable=drag_var,
             font=("Arial", 13)).grid(row=4, column=0, sticky="ew")

    tk.Label(frame_inputs, text="Data # :", bg="white",
             font=("Arial", 15)).grid(row=5, column=0, sticky="w", pady=(8, 0))
    tk.Entry(frame_inputs, textvariable=pos_var,
             font=("Arial", 13)).grid(row=6, column=0, sticky="ew")

    auto_increment_var = ctk.BooleanVar(value=True)
    ctk.CTkSwitch(frame_inputs, text="Auto-increment (+1)", variable=auto_increment_var,
                  font=("Arial", 13),
                  command=lambda: level_var.set(1 if auto_increment_var.get() else 0)
                  ).grid(row=7, column=0, sticky="w", pady=(4, 0))

    # ── bottom action buttons ───────────────────────────────────────────────
    Button(root, text="Collect", bg="#B0CA99", font=("Arial", 18),
           command=collect_Callback).grid(row=3, column=2, sticky="nsew",
                                          padx=8, pady=12, ipady=16)
    Button(root, text="New File", bg="#1E90FF", font=("Arial", 18),
           command=newfile_Callback).grid(row=3, column=3, sticky="nsew",
                                          padx=8, pady=12, ipady=16)

    # ── init ────────────────────────────────────────────────────────────────
    newfile_Callback()
    update_gui()

    if standalone_root is not None:
        standalone_root.mainloop()



#  GENERIC EXPERIMENT (Thrust Stand / Wind Tunnel)

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

    pos_var = tk.StringVar(value="0")
    level_var = tk.IntVar(value=1)
    thrust_var = tk.StringVar()
    port_var = tk.StringVar()
    arduino_status_var = tk.StringVar(value="Not Connected")

    arduino        = None
    file_handle    = None
    timestamp      = None
    detected_ports = []
    CSV_COLS       = ["x (mm)", "Port 0 - Pressure (Pa)", "Port 1 - Ambient (Pa)", "Thrust(g)"]
    df             = pd.DataFrame(columns=CSV_COLS)

    def _get_csv_cols():
        if len(detected_ports) >= 2:
            return ["x (mm)",
                    f"MUX Port {detected_ports[0]} - Pressure (Pa)",
                    f"MUX Port {detected_ports[1]} - Ambient (Pa)",
                    "Thrust(g)"]
        return ["x (mm)", "Port 0 - Pressure (Pa)", "Port 1 - Ambient (Pa)", "Thrust(g)"]

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
        nonlocal file_handle, timestamp, df, table

        CSV_COLS[:] = _get_csv_cols()

        for widget in frame_DT.winfo_children():
            widget.destroy()
        table = display_dataframe_as_table(frame_DT, pd.DataFrame(columns=CSV_COLS))

        try:
            if file_handle is not None and not file_handle.closed:
                file_handle.close()
        except Exception:
            pass

        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"arduino_data{timestamp}.csv"

        save_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.isdir(save_dir):
            save_dir = os.path.expanduser("~")
        if not os.access(save_dir, os.W_OK):
            save_dir = os.getcwd()

        filepath = os.path.join(save_dir, filename)
        print(f"Writing data to {filepath}...")

        CSV_COLS[:] = _get_csv_cols()

        try:
            file_handle = open(filepath, "w", newline="")
            writer = csv.writer(file_handle)
            writer.writerow(CSV_COLS)
            file_handle.flush()
            df = pd.read_csv(file_handle.name)
            refresh_all(df)
        except Exception as e:
            print(f"Error creating CSV file: {e}")
            arduino_status_var.set(f"Can't create file: {e}")
            lbl_not_conn.config(fg="red")
            file_handle = None

    def find_arduino_port():
        ports = serial.tools.list_ports.comports()
        for port in ports:
            desc = (port.description or "").lower()
            print(port.device, "-", desc)
            if any(k in desc for k in ["arduino", "usb serial", "usb to uart", "ch340", "cp210", "silicon labs"]):
                print(f"Found Arduino on port: {port.device}")
                return port.device
        print("No Arduino found")
        return None

    def query_ports():
        if arduino is None:
            return
        arduino.write("PORTS\n".encode())
        arduino.flush()
        deadline = time.time() + 3
        while time.time() < deadline:
            if arduino.in_waiting:
                line = arduino.readline().decode("utf-8", errors="ignore").strip()
                if line.startswith("Ports:,"):
                    parts = line.split("Ports:,", 1)[1].split(",")
                    detected_ports[:] = [int(p) for p in parts if p.strip().isdigit()]
                    print(f"Detected MUX ports: {detected_ports}")
                    break
            else:
                time.sleep(0.1)

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

            arduino = serial.Serial(port=port, baudrate=115200, timeout=1.0)
            time.sleep(2)
            arduino.reset_input_buffer()
            arduino.write("GReady\n".encode())
            time.sleep(0.5)

            attempts = 0
            while attempts < 10:
                if arduino.in_waiting:
                    line = arduino.readline().decode("utf-8", errors="ignore").strip()
                    print(f"Arduino says: {line}")
                    if "Arduino Ready" in line or "Ready" in line:
                        break
                else:
                    arduino.write("GReady\n".encode())
                    time.sleep(0.5)
                attempts += 1

            query_ports()
            if detected_ports:
                newfile_Callback()
            arduino_status_var.set(f"Connected to {port}")
            lbl_not_conn.config(fg="green")

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
        x_pos = pos_var.get()
        thrust = thrust_var.get()

        arduino.write("a\n".encode())
        arduino.flush()
        print("Sent 'a' command")

        timeout = time.time() + 15
        got_data = False

        while time.time() < timeout:
            if arduino.in_waiting:
                line = arduino.readline().decode("utf-8", errors="ignore").strip()
                print(f"Received: {line}")

                if line.startswith("Data:,"):
                    try:
                        modified_str = line.split("Data:,", 1)[1]
                        pressure_values = modified_str.split(",")

                        if len(pressure_values) >= 2:
                            pitot_press   = float(pressure_values[0]) * 100
                            ambient_press = float(pressure_values[1]) * 100
                        elif len(pressure_values) == 1:
                            pitot_press   = float(pressure_values[0]) * 100
                            ambient_press = 0.0
                        else:
                            continue

                        writer.writerow([x_pos, str(pitot_press), str(ambient_press), thrust])
                        file_handle.flush()
                        print("Wrote to CSV")
                        df = pd.read_csv(file_handle.name)
                        refresh_all(df)
                        got_data = True
                        try:
                            current_pos = float(pos_var.get())
                            pos_var.set(str(int(current_pos + level_var.get())))
                        except ValueError:
                            pass
                        break

                    except (ValueError, IndexError) as e:
                        print(f"Parse error: {e} — line was: {line}")
                        continue
            else:
                time.sleep(0.1)

        if not got_data:
            arduino_status_var.set("Timeout: no data received. Check sensors.")
            lbl_not_conn.config(fg="red")
            print("Collect timed out")

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
        press_col = CSV_COLS[1]
        amb_col   = CSV_COLS[2]
        if not dataframe.empty and press_col in dataframe.columns:
            ax1.plot(dataframe["x (mm)"], dataframe[press_col], color="red")
        ax1.set_xlabel("x (mm)", fontsize=12)
        ax1.set_ylabel("Pressure (Pa)", fontsize=12)

        ax2.clear()
        velocity = np.sqrt(
            np.maximum(
                0,
                2 * (dataframe[press_col] - dataframe[amb_col]) / AIR_DENSITY,
            )
        ) if not dataframe.empty and press_col in dataframe.columns and amb_col in dataframe.columns else np.array([])
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

    root.grid_columnconfigure(0, weight=3)
    root.grid_columnconfigure(1, weight=2)
    root.grid_columnconfigure(2, weight=1)
    root.grid_columnconfigure(3, weight=1)
    root.grid_rowconfigure(0, weight=0)
    root.grid_rowconfigure(1, weight=3)
    root.grid_rowconfigure(2, weight=3)
    root.grid_rowconfigure(3, weight=1)

    btn_lab_details = Button(root, text="Lab Details", bg="#B4DCEB", command=open_lab_details)
    btn_lab_details.grid(column=2, row=0, sticky="ew", padx=4, pady=4)
    btn_exit = Button(root, text="Exit", bg="#F28484", command=on_close)
    btn_exit.grid(column=3, row=0, sticky="ew", padx=4, pady=4)

    frame_PX = tk.Frame(root, bg="white")
    frame_PX.grid(column=0, row=1, columnspan=2, sticky="nsew", padx=8, pady=8)
    frame_PX.grid_columnconfigure(0, weight=1)
    frame_PX.grid_rowconfigure(1, weight=1)
    tk.Label(frame_PX, text="Absolute Pressure vs X-Position",
             font=("Arial", 20), bg="white").grid(column=0, row=0, sticky="nsew")
    fig_press = plt.Figure(figsize=(2.5, 2.5), dpi=100)
    canvas_press = FigureCanvasTkAgg(fig_press, frame_PX)
    canvas_press.get_tk_widget().grid(column=0, row=1, sticky="nsew")
    ax1 = fig_press.add_subplot(111)
    fig_press.tight_layout(pad=2.0)
    fig_press.set_constrained_layout(True)

    frame_VX = tk.Frame(root, bg="white")
    frame_VX.grid(column=0, row=2, columnspan=2, sticky="nsew", padx=8, pady=8)
    frame_VX.grid_columnconfigure(0, weight=1)
    frame_VX.grid_rowconfigure(1, weight=1)
    tk.Label(frame_VX, text="Velocity vs X-Position",
             bg="white", font=("Arial", 20)).grid(column=0, row=0, sticky="nsew")
    fig_velo = plt.Figure(figsize=(2.5, 2.5), dpi=100)
    canvas_velo = FigureCanvasTkAgg(fig_velo, frame_VX)
    canvas_velo.get_tk_widget().grid(column=0, row=1, sticky="nsew")
    ax2 = fig_velo.add_subplot(111)
    fig_velo.tight_layout(pad=2.0)
    fig_velo.set_constrained_layout(True)

    frame_DT = tk.Frame(root, bg="white")
    frame_DT.grid(column=2, row=1, columnspan=2, rowspan=2, sticky="nsew", padx=8, pady=8)
    table = display_dataframe_as_table(frame_DT, df)

    frame_status = tk.Frame(root, bg="white")
    frame_status.grid(column=0, row=3, sticky="nsew", padx=15, pady=15)
    for i in range(2):
        frame_status.grid_columnconfigure(i, weight=1, minsize=120)
    for j in range(3):
        frame_status.grid_rowconfigure(j, weight=1, minsize=30)

    tk.Label(frame_status, text="Arduino Status:", bg="white",
             font=("Arial", 16)).grid(column=0, row=0, sticky="ew")
    lbl_not_conn = tk.Label(frame_status, textvariable=arduino_status_var,
                            fg="red", bg="white", font=("Arial", 16))
    lbl_not_conn.grid(column=1, row=0, sticky="ew")
    tk.Label(frame_status, text="Port:", bg="white",
             font=("Arial", 16)).grid(column=0, row=1, sticky="ew")
    tk.Entry(frame_status, textvariable=port_var).grid(column=1, row=1, sticky="ew")
    Button(frame_status, text="Connect", bg="#B0CA99", command=auto_connect_arduino,
           font=("Arial", 15)).grid(column=0, row=2, columnspan=2, sticky="ew", pady=(8, 0))

    frame_tp = tk.Frame(root, bg="white")
    frame_tp.grid(column=1, row=3, sticky="nsew", padx=15, pady=15)
    frame_tp.grid_columnconfigure(0, weight=1, minsize=200)
    for i in range(6):
        frame_tp.grid_rowconfigure(i, weight=1)

    tk.Label(frame_tp, text="Thrust (g):", bg="white",
             font=("Arial", 16)).grid(column=0, row=0, sticky="w")
    tk.Entry(frame_tp, textvariable=thrust_var).grid(column=0, row=1, sticky="ew")
    tk.Label(frame_tp, text="Position (mm):", bg="white",
             font=("Arial", 16)).grid(column=0, row=2, sticky="w")
    tk.Entry(frame_tp, textvariable=pos_var).grid(column=0, row=3, sticky="ew")
    auto_increment_var = ctk.BooleanVar(value=False)
    level_var.set(1)

    def on_increment_toggle():
        if auto_increment_var.get():
            level_var.set(2)
            increment_switch.configure(text="(+2 mm)")
        else:
            level_var.set(1)
            increment_switch.configure(text="(+1 mm)")

    increment_switch = ctk.CTkSwitch(frame_tp, text="(+1 mm)",
                                     variable=auto_increment_var, font=("Arial", 16),
                                    command=on_increment_toggle)
    increment_switch.grid(column=0, row=2, sticky="e", pady=(8, 0))

    Button(root, text="Collect", bg="#B0CA99", command=collect_Callback,
           font=("Arial", 18)).grid(column=2, row=3, sticky="nsew", padx=8, pady=15, ipady=18)
    Button(root, text="New File", bg="#1E90FF", command=newfile_Callback,
           font=("Arial", 18)).grid(column=3, row=3, sticky="nsew", padx=8, pady=15, ipady=18)

    newfile_Callback()
    update_gui()

    if standalone_root is not None:
        standalone_root.mainloop()


# ---------------------------------------------------------------------------
#  WELCOME SCREEN
# ---------------------------------------------------------------------------

def show_welcome_screen():
    root = tk.Tk()
    root.title("Welcome")
    root.geometry("1100x800")
    root.minsize(900, 650)
    root.configure(bg="#dbe6f5")

    root.grid_columnconfigure(0, weight=1)
    for r in range(7):
        root.grid_rowconfigure(r, weight=1)

    tk.Label(root, text="Laboratory Control Suite", font=("Arial", 38, "bold"),
             bg="#dbe6f5", fg="#0c366b").grid(row=1, column=0, pady=(30, 10))
    tk.Label(root, text="Select an experiment to begin", font=("Arial", 20),
             bg="#dbe6f5", fg="#0c366b").grid(row=2, column=0, pady=(0, 30))

    button_frame = tk.Frame(root, bg="#dbe6f5")
    button_frame.grid(row=3, column=0)

    Button(button_frame, text="Launch Thrust Stand", font=("Arial", 18, "bold"),
           bg="#1e90ff", fg="white", width=300, height=55,
           command=lambda: launch_thrust_stand(root)).grid(row=0, column=0, pady=10)

    Button(button_frame, text="Launch Pipe Flow", font=("Arial", 18, "bold"),
           bg="#28a745", fg="white", width=300, height=55,
           command=lambda: launch_pipe_flow(root)).grid(row=1, column=0, pady=10)

    Button(button_frame, text="Launch Wind Tunnel", font=("Arial", 18, "bold"),
           bg="#ff8c00", fg="white", width=300, height=55,
           command=lambda: launch_wind_tunnel(root)).grid(row=2, column=0, pady=10)

    Button(button_frame, text="Launch Diagnostic", font=("Arial", 18, "bold"),
           bg="#6a5acd", fg="white", width=300, height=55,
           command=lambda: launch_diagnostic(root)).grid(row=3, column=0, pady=10)

    root.mainloop()


if __name__ == "__main__":
    show_welcome_screen()