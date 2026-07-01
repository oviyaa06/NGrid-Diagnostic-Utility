# to suppress warnings
import os
os.environ["QT_LOGGING_RULES"] = "*.debug=false;*.warning=false;*.critical=false"
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt5")

#imports
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QTimer, QDateTime, pyqtSignal
from PyQt5.QtGui import QFont, QColor   
import sys, json
import pandas as pd
import matplotlib
matplotlib.use("Qt5Agg")          
import matplotlib.pyplot as plt
import pyqtgraph as pg
from client import get_system_stats, get_process_stats  

pg.setConfigOption("useOpenGL", False)
pg.setConfigOption("enableExperimental", False)

# to open GUI
app = QApplication(sys.argv)
app.setStyle("Fusion")           

win = QWidget()
win.setWindowTitle("NGGrid Diagnostic Utility")

BG_DARK   = "#0a1924"
BG_CARD   = "#1e1e2f"
BG_TABLE  = "#1D2951"
BTN_BLUE  = "#27427a"
BTN_HOVER = "#3a559f"
BORDER    = "#4c6fff"

RUNNING_STYLE = "background-color:green;color:white;border-radius:10px;padding:5px;"
STOPPED_STYLE = "background-color:red;color:white;border-radius:10px;padding:5px;"

CARD_STYLE = (
    f"QFrame{{background-color:{BG_CARD};border:1px solid {BORDER};border-radius:12px;}}"
    f"QFrame:hover{{background-color:#2b2b40;border:1px solid {BORDER};border-radius:12px;}}"
)

win.setStyleSheet(f"""
    QWidget {{
        background-color: {BG_DARK};
    }}
    QPushButton {{
        background-color: {BTN_BLUE};
        color: white;
        border: none;
        border-radius: 5px;
        padding: 5px;
    }}
    QPushButton:hover {{
        background-color: {BTN_HOVER};
    }}
    QSpinBox, QDateTimeEdit {{
        background-color: {BG_TABLE};
        color: white;
        border: 1px solid gray;
        padding: 5px;
    }}
    QTabWidget::pane {{
        border: 1px solid {BORDER};
        background-color: {BG_DARK};
    }}
    QTabBar::tab {{
        background-color: {BTN_BLUE};
        color: white;
        padding: 8px 18px;
        margin-right: 2px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        min-width: 100px;
    }}
    QTabBar::tab:selected {{
        background-color: {BORDER};
        color: white;
    }}
    QTabBar::tab:hover:!selected {{
        background-color: {BTN_HOVER};
    }}
    QCalendarWidget QWidget {{
        background-color: {BG_TABLE};
        color: white;
    }}
    QCalendarWidget QToolButton {{
        background-color: {BTN_BLUE};
        color: white;
    }}
    QCalendarWidget QMenu {{
        background-color: {BG_TABLE};
        color: white;
    }}
    QCalendarWidget QSpinBox {{
        background-color: {BG_TABLE};
        color: white;
    }}
    QCalendarWidget QAbstractItemView {{
        background-color: {BG_TABLE};
        color: white;
        selection-background-color: {BTN_HOVER};
        selection-color: white;
    }}
""")

# set json file containing machine ip address
product = "machine_details"
product_path = os.path.join(os.getcwd(), f"{product}.json")
with open(product_path, "r") as f:
    data = json.load(f)

# set json file containing process names
machine_path = os.path.join(os.getcwd(), "PPC4.5.0.json")
with open(machine_path, "r") as f:
    machine_data = json.load(f)

hmi_processes = machine_data["machines"]["HMI Machine"]["processes"]
core_processes = machine_data["machines"]["Core Machine"]["processes"]

MACHINE_IP = {name: info["ip_address"] for name, info in data["machines"].items()}
HMI_IP     = MACHINE_IP.get("HMI Machine",  "127.0.0.1")
CORE_IP    = MACHINE_IP.get("Core Machine", "127.0.0.1")

# used for graph x-axis labels
class TimeAxisItem(pg.AxisItem):
    def __init__(self, timestamps):
        super().__init__(orientation="bottom")
        self.timestamps = timestamps
    # to converts graph index positions into time strings
    def tickStrings(self, values, scale, spacing):
        strings = []
        for value in values:
            idx = int(value)
            if 0 <= idx < len(self.timestamps):
                strings.append(
                    self.timestamps[idx].strftime("%H:%M:%S")
                )
            else:
                strings.append("")
        return strings

# to make graph cards clickable
class ClickableFrame(QFrame):
    clicked = pyqtSignal()
    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

# analyze window
class AnalyzeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Analyze Parquet File")
        self.setMinimumSize(900, 700)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {BG_DARK}; }}
            QLabel {{ color: white; }}
            QPushButton {{
                background-color: {BTN_BLUE}; color: white;
                border: none; border-radius: 5px; padding: 6px 12px;
            }}
            QPushButton:hover {{ background-color: {BTN_HOVER}; }}
            QPushButton:disabled {{ background-color: #555; color: #999; }}
            QLineEdit {{ 
                background-color: {BG_TABLE}; color: white;
                border: 1px solid gray; border-radius: 4px; padding: 5px;
            }}
            QDateTimeEdit {{
                background-color: {BG_TABLE}; color: white;
                border: 1px solid gray; padding: 5px;
            }}
            QListWidget {{
                background-color: {BG_TABLE}; color: white;
                border: 1px solid {BORDER}; border-radius: 4px;
            }}
            QListWidget::item:selected {{ background-color: {BTN_HOVER}; }}
            QScrollArea {{ border: none; }}
            QCalendarWidget QWidget {{ background-color: {BG_TABLE}; color: white; }}
            QCalendarWidget QToolButton {{ background-color: {BTN_BLUE}; color: white; }}
            QCalendarWidget QAbstractItemView {{
                background-color: {BG_TABLE}; color: white;
                selection-background-color: {BTN_HOVER};
            }}
        """)
        self._df = None
        self._parquet_path = None
        self._graph_widgets = []   
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # title
        title = QLabel("📊  Analyze Parquet File")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        main_layout.addWidget(title)
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{BORDER};")
        main_layout.addWidget(sep)

        # file label
        file_row = QHBoxLayout()
        file_lbl = QLabel("Parquet File:")
        file_lbl.setFixedWidth(90)
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Select a .parquet file…")

        # browse button
        browse_btn = QPushButton("Browse")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(file_lbl)
        file_row.addWidget(self.file_edit)
        file_row.addWidget(browse_btn)
        main_layout.addLayout(file_row)
        dt_row = QHBoxLayout()
        dt_row.setSpacing(10)

        # start calender
        start_lbl = QLabel("Start:")
        start_lbl.setFixedWidth(40)
        self.start_dt = QDateTimeEdit()
        self.start_dt.setCalendarPopup(True)
        self.start_dt.setDisplayFormat("dd-MM-yyyy hh:mm:ss AP")
        self.start_dt.setDateTime(QDateTime.currentDateTime().addSecs(-3600))
        self.start_dt.setFixedWidth(220)

        # stop calender
        stop_lbl = QLabel("Stop:")
        stop_lbl.setFixedWidth(38)
        self.stop_dt = QDateTimeEdit()
        self.stop_dt.setCalendarPopup(True)
        self.stop_dt.setDisplayFormat("dd-MM-yyyy hh:mm:ss AP")
        self.stop_dt.setDateTime(QDateTime.currentDateTime())
        self.stop_dt.setFixedWidth(220)

        # export csv button
        self.export_btn = QPushButton("Export as CSV")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_csv)
        dt_row.addWidget(start_lbl)
        dt_row.addWidget(self.start_dt)
        dt_row.addSpacing(14)
        dt_row.addWidget(stop_lbl)
        dt_row.addWidget(self.stop_dt)
        dt_row.addStretch()
        dt_row.addWidget(self.export_btn)
        main_layout.addLayout(dt_row)
        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"color:{BORDER};")
        main_layout.addWidget(sep2)

        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setHandleWidth(4)
        content_splitter.setStyleSheet(f"QSplitter::handle{{background:{BORDER};}}")

        # list widget to display process names
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        proc_lbl = QLabel("Select Processes:")
        proc_lbl.setFont(QFont("Arial", 10, QFont.Bold))
        left_layout.addWidget(proc_lbl)
        self.proc_list = QListWidget()
        self.proc_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.proc_list.setMinimumWidth(180)
        self.proc_list.itemSelectionChanged.connect(self._refresh_graphs)
        left_layout.addWidget(self.proc_list)

        # to display graphs
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        graph_lbl = QLabel("  Graphs")
        graph_lbl.setFont(QFont("Arial", 10, QFont.Bold))
        right_layout.addWidget(graph_lbl)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.graph_container = QWidget()
        self.graph_container.setStyleSheet(f"background-color:{BG_DARK};")
        self.graph_hbox = QHBoxLayout(self.graph_container)
        self.graph_hbox.setSpacing(10)
        self.graph_hbox.setContentsMargins(6, 6, 6, 6)
        self.graph_hbox.addStretch()

        self.scroll_area.setWidget(self.graph_container)
        right_layout.addWidget(self.scroll_area)

        content_splitter.addWidget(left_panel)
        content_splitter.addWidget(right_panel)
        content_splitter.setStretchFactor(0, 0)
        content_splitter.setStretchFactor(1, 1)
        content_splitter.setSizes([200, 680])

        main_layout.addWidget(content_splitter, stretch=1)

        self.status_lbl = QLabel("Load a parquet file to begin.")
        self.status_lbl.setStyleSheet("color:#aaa; font-size:11px;")
        main_layout.addWidget(self.status_lbl)

    # to open/browse parquet file
    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Parquet File", "", "Parquet Files (*.parquet)"
        )
        if path:
            self.file_edit.setText(path)
            self._load_parquet(path)

    # to load parquet file into dataframe
    def _load_parquet(self, path):
        try:
            df = pd.read_parquet(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read parquet:\n{e}")
            return

        self._df = df
        self._parquet_path = path
        self._is_system_profile = "Process Name" not in df.columns
        self.export_btn.setEnabled(True)

        # set minimum timestamp to start box & maximum to stop box
        if "Timestamp" in df.columns:
            try:
                df["_ts"] = pd.to_datetime(df["Timestamp"],format="%d-%m-%Y %I:%M:%S.%f %p",errors="coerce")
                mn = df["_ts"].min(); mx = df["_ts"].max() 
                if pd.notna(mn):
                    self.start_dt.setDateTime(
                        QDateTime.fromString(mn.strftime("%d-%m-%Y %I:%M:%S %p"), "dd-MM-yyyy hh:mm:ss AP"))
                if pd.notna(mx):
                    self.stop_dt.setDateTime(
                        QDateTime.fromString(mx.strftime("%d-%m-%Y %I:%M:%S %p"), "dd-MM-yyyy hh:mm:ss AP"))
            except Exception:
                pass

        self.proc_list.clear()

        # display loaded file path
        if self._is_system_profile:
            self.proc_list.setEnabled(False)
            self.status_lbl.setText(
                f"Loaded (System Profile): {os.path.basename(path)}   |   {len(df)} rows"
            )
            self._show_system_graphs()
        else:
            self.proc_list.setEnabled(True)
            processes = sorted(df["Process Name"].dropna().unique())
            for p in processes:
                self.proc_list.addItem(p)
            self.status_lbl.setText(
                f"Loaded: {os.path.basename(path)}   |   {len(df)} rows   |   "
                f"{len(processes)} process(es)"
            )

    # to filter user selected date time for graph plotting
    def _filtered_df(self):
        df = self._df.copy()
        if "Timestamp" in df.columns:
            try:
                df["_ts"] = pd.to_datetime(df["Timestamp"],format="%d-%m-%Y %I:%M:%S.%f %p",errors="coerce")
                start = self.start_dt.dateTime().toPyDateTime()
                stop  = self.stop_dt.dateTime().toPyDateTime()
                df = df[(df["_ts"] >= start) & (df["_ts"] <= stop)]
            except Exception:
                pass
        return df
    
    # to export csv file
    def _export_csv(self):
        if self._df is None or self._parquet_path is None:
            return
        csv_path = os.path.splitext(self._parquet_path)[0] + ".csv"
        try:
            self._filtered_df().drop(columns=["_ts"], errors="ignore").to_csv(
                csv_path, index=False
            )
            QMessageBox.information(
                self, "Export CSV",
                f"CSV saved successfully:\n{csv_path}",
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    # to plot graphs
    def _make_pg_plot(self, title_text, x_data, y_data, y_label, color="w",large=False):
        import numpy as np
        plot = pg.PlotWidget(axisItems={"bottom": TimeAxisItem(x_data)})
        plot.setBackground(BG_TABLE)
        plot.setStyleSheet(f"border:none; background-color:{BG_TABLE};")
        plot.setTitle(f"<span style='color:white;font-size:10pt;'>{title_text}</span>")
        plot.setLabel("left",  f"<span style='color:white;'>{y_label}</span>")
        plot.setLabel("bottom", "<span style='color:white;'>Time</span>")
        plot.getAxis("left").setTextPen("white")
        plot.getAxis("bottom").setTextPen("white")
        if large:
            plot.setMinimumSize(1000, 700)
        else:
            plot.setMinimumSize(260,180)
            plot.setFixedWidth(300)
        
        # to set axis values
        import pandas as _pd
        y_numeric = _pd.to_numeric(
            _pd.Series(list(y_data) if not hasattr(y_data, "__iter__") else y_data),
            errors="coerce"
        ).fillna(0.0).values.astype(float)

        x_numeric = np.arange(len(y_numeric), dtype=float)

        if len(y_numeric) > 0:
            plot.plot(x_numeric, y_numeric, pen=pg.mkPen(color, width=2))

        hist = list(y_numeric)
        
        # to display values when hovered over graph
        def mouse_moved(event):
            vb = plot.plotItem.vb
            mp = vb.mapSceneToView(event)
            xi = int(mp.x())
            if 0 <= xi < len(hist):
                QToolTip.showText(
                    plot.mapToGlobal(plot.mapFromScene(event)),
                    f"{y_label} : {round(float(hist[xi]), 2)}"
                )
        plot.scene().sigMouseMoved.connect(mouse_moved)
        return plot

    # to expand graph cards when clicked
    def _show_graph_dialog(self, data):
        large_graph = self._make_pg_plot(
            data["title"],
            data["timestamps"],
            data["values"],
            data["ylabel"],
            data["color"],
            large = True
        )        
        large_graph.setMinimumSize(1000,700)
        dlg = QDialog(self)
        dlg.setWindowTitle(data["title"])
        dlg.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        layout = QVBoxLayout(dlg)
        layout.addWidget(large_graph,1)
        large_graph.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        dlg.resize(1200,800)
        dlg.show()

    # to show whole system graphs
    def _show_system_graphs(self):
        while self.graph_hbox.count() > 1:
            item = self.graph_hbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._graph_widgets.clear()

        df = self._filtered_df()

        col_map = {
            "RAM":     ["Memory(MB)", "Memory MB", "RAM GB"],
            "CPU":     ["CPU %"],
            "Disk I/O":["Disk I/O(MB/s)", "Disk I/O (MB/s)", "Disk I/O"],
        }
        units  = {"RAM": "MB/GB", "CPU": "%", "Disk I/O": "MB/s"}
        colors = {"RAM": "#4fc3f7", "CPU": "#81c784", "Disk I/O": "#ffb74d"}

        def find_col(candidates):
            for c in candidates:
                if c in df.columns:
                    return c
            return None

        col_frame = QFrame()
        col_frame.setStyleSheet(
            f"QFrame{{background-color:{BG_CARD}; border:1px solid {BORDER};"
            f"border-radius:8px;}}"
        )
        col_frame.setFixedWidth(320)
        col_layout = QVBoxLayout(col_frame)
        col_layout.setContentsMargins(8, 8, 8, 8)
        col_layout.setSpacing(8)

        sys_title = QLabel("System")
        sys_title.setFont(QFont("Arial", 11, QFont.Bold))
        sys_title.setStyleSheet("color:white; border:none;")
        sys_title.setAlignment(Qt.AlignCenter)
        col_layout.addWidget(sys_title)

        for metric, candidates in col_map.items():
            col_name = find_col(candidates)
            y = df[col_name].values if col_name else []
            timestamps = df["_ts"].tolist()
            graph_data = {
                "title": metric,
                "timestamps": timestamps,
                "values": y,
                "ylabel": f"{metric} ({units[metric]})",
                "color": colors[metric]
            }
            
            card = ClickableFrame()
            card.setStyleSheet(
                f"""
                QFrame {{
                    background-color: {BG_TABLE};
                    border: 1px solid {BORDER};
                    border-radius: 8px
                }}
                QFrame:hover {{
                    background-color: #2b2b40;
                }}
                """
            )
            card_layout = QVBoxLayout(card)
            graph = self._make_pg_plot(metric, timestamps, y,f"{metric} ({units[metric]})", colors[metric])
            card_layout.addWidget(graph)
            card.clicked.connect(lambda checked = False, d = graph_data: self._show_graph_dialog(d))
            col_layout.addWidget(card)
            self._graph_widgets.append(graph)

        self.graph_hbox.insertWidget(self.graph_hbox.count() - 1, col_frame)
        self.graph_container.setMinimumWidth(340)

    # graph is refreshed whenever new process is clicked
    def _refresh_graphs(self):
        if self._df is None:
            return

        while self.graph_hbox.count() > 1:          
            item = self.graph_hbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._graph_widgets.clear()

        selected = [item.text() for item in self.proc_list.selectedItems()]
        if not selected:
            return

        df = self._filtered_df()

        col_map = {
            "ram":  ["Memory(MB)", "Memory MB", "RAM GB"],
            "cpu":  ["CPU %"],
            "disk": ["Disk I/O(MB/s)", "Disk I/O (MB/s)", "Disk I/O"],
        }

        def find_col(candidates, df):
            for c in candidates:
                if c in df.columns:
                    return c
            return None

        for proc in selected:
            pdf = df[df["Process Name"] == proc].reset_index(drop=True)

            col_frame = QFrame()
            col_frame.setStyleSheet(
                f"QFrame{{background-color:{BG_CARD}; border:1px solid {BORDER};"
                f"border-radius:8px;}}"
            )
            col_frame.setFixedWidth(320)
            col_layout = QVBoxLayout(col_frame)
            col_layout.setContentsMargins(8, 8, 8, 8)
            col_layout.setSpacing(8)

            proc_title = QLabel(proc)
            proc_title.setFont(QFont("Arial", 11, QFont.Bold))
            proc_title.setStyleSheet("color:white; border:none;")
            proc_title.setAlignment(Qt.AlignCenter)
            col_layout.addWidget(proc_title)

            metrics = [
                ("RAM", col_map["ram"], "MB", "#4fc3f7"),
                ("CPU", col_map["cpu"], "%", "#81c784"),
                ("Disk I/O", col_map["disk"], "MB/s",  "#ffb74d"),
            ]
            for label, candidates, unit, color in metrics:
                col_name = find_col(candidates, pdf)
                import pandas as _pd
                y = _pd.to_numeric(
                    _pd.Series(pdf[col_name].values if col_name else []),
                    errors="coerce"
                ).fillna(0.0).values if col_name else []
                timestamps = pdf["_ts"].tolist()
                graph_data = {
                    "title": label,
                    "timestamps": timestamps,
                    "values": y,
                    "ylabel": f"{label} ({unit})",
                    "color": color
                }
                card = ClickableFrame()
                card.setStyleSheet(
                    f"""
                    QFrame {{
                        background-color: {BG_TABLE};
                        border: 1px solid {BORDER};
                        border-radius: 8px
                    }}
                    QFrame:hover {{
                        background-color: #2b2b40;
                    }}
                    """
                )
                card_layout = QVBoxLayout(card)
                graph = self._make_pg_plot(label,timestamps,y,f"{label} ({unit})",color)
                graph.setFixedHeight(180)
                card_layout.addWidget(graph)
                card.clicked.connect(lambda checked = False, d = graph_data: self._show_graph_dialog(d))
                col_layout.addWidget(card)
                self._graph_widgets.append(graph)

            self.graph_hbox.insertWidget(self.graph_hbox.count() - 1, col_frame)

        self.graph_container.setMinimumWidth(
            max(330 * len(selected) + 20, self.scroll_area.width())
        )

# display product name and version at top of page
label1 = QLabel(f"{data['product_name']} V{data['version']}")
label1.setFont(QFont("Arial", 16, QFont.Bold))
label1.setStyleSheet("color:white")

# whole process start stop buttons near title
tot_start = QPushButton("▶")
tot_stop  = QPushButton("■")
tot_start.setStyleSheet(RUNNING_STYLE)
tot_stop.setStyleSheet(STOPPED_STYLE)
for b in (tot_start, tot_stop):
    b.setFixedSize(30, 30)
tot_start.setFont(QFont("Arial", 16, QFont.Bold))
tot_stop.setFont(QFont("Arial", 10, QFont.Bold))

# analyze button to open analyze dialog box
analyze_btn = QPushButton("🔍 Analyze")
analyze_btn.setFixedHeight(40)
analyze_btn.setFont(QFont("Arial", 10, QFont.Bold))
analyze_btn.setStyleSheet(
    f"QPushButton{{background-color:{BTN_BLUE};color:white;border:none;"
    f"border-radius:5px;padding:5px 12px;}}"
    f"QPushButton:hover{{background-color:{BTN_HOVER};}}"
)

# to open analyze dialog box
def open_analyze_dialog():
    dlg = AnalyzeDialog(win)
    dlg.exec_()

analyze_btn.clicked.connect(open_analyze_dialog)

# layout for title, version and analyze button
header_layout = QHBoxLayout()
header_layout.addStretch()
header_layout.addWidget(label1)
#header_layout.addWidget(tot_start)
#header_layout.addWidget(tot_stop)
header_layout.addStretch()
header_layout.addWidget(analyze_btn)

# creating tabs 
tabs      = QTabWidget()
utility_tab = QWidget()
hmi_tab     = QWidget()
core_tab    = QWidget()
tabs.addTab(utility_tab, "Utility")
tabs.addTab(hmi_tab,     "HMI Machine")
tabs.addTab(core_tab,    "Core Machine")

# to build cards which shows machine names in Utility page
def build_utility_card(machine_name, tab_index):
    card = QFrame()
    card.setStyleSheet(CARD_STYLE)
    card.setFixedSize(260, 100)
    card.setCursor(Qt.PointingHandCursor)

    title = QLabel(machine_name)
    title.setFont(QFont("Arial", 16, QFont.Bold))
    title.setAlignment(Qt.AlignCenter)
    title.setStyleSheet("color:white; border:none;")

    layout = QVBoxLayout()
    layout.setContentsMargins(12, 10, 12, 10)
    layout.addStretch()
    layout.addWidget(title)
    layout.addStretch()
    card.setLayout(layout)
    card.mousePressEvent = lambda e: tabs.setCurrentIndex(tab_index)
    return card

# cards for machine names
machine_names = list(data["machines"].keys())
hmi_card  = build_utility_card(machine_names[0], 1)
core_card = build_utility_card(machine_names[1], 2)

# layout for adding machine name cards
machine_layout = QHBoxLayout()
machine_layout.setSpacing(30)
machine_layout.addWidget(hmi_card)
machine_layout.addWidget(core_card)

h_center = QHBoxLayout()
h_center.addStretch()
h_center.addLayout(machine_layout)
h_center.addStretch()

utility_layout = QVBoxLayout()
utility_layout.addStretch()
utility_layout.addLayout(h_center)
utility_layout.addStretch()
utility_tab.setLayout(utility_layout)

# data shown in each machine tab
def build_machine_tab(parent_tab, process_list):
    process_data         = [
        [
            p["name"], p["cpu_threshold"], p["memory_threshold"], p["disk_threshold"]
        ] 
        for p in process_list
    ]
    checkboxes           = []
    buttons              = []
    status_labels        = []
    recorded_data        = []
    cpu_graphs           = {}
    mem_graphs           = {}
    cpu_process_history  = {}
    mem_process_history  = {}
    process_profile_data = {}

    # to store graph values history for dynamic plotting
    cpu_history   = []
    mem_history   = []
    disk_history  = []
    read_history  = []
    write_history = []

    # to create graphs 
    def make_plot(title_text):
        g = pg.PlotWidget()
        g.setBackground(BG_TABLE)
        g.setStyleSheet(f"border:none; background-color:{BG_TABLE};")
        g.setTitle(f"<span style='color:white;'>{title_text}</span>")
        g.setMinimumHeight(80)
        g.setMaximumHeight(110)
        g.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return g

    # creating system graphs
    cpu_graph = make_plot("CPU Usage")
    mem_graph = make_plot("RAM Usage")
    diskio_graph = make_plot("Disk I/O")
    read_graph = make_plot("Read Bytes")
    write_graph = make_plot("Write Bytes")

    diskio_line = diskio_graph.plot([], pen="w")
    read_line   = read_graph.plot([],   pen="w")
    write_line  = write_graph.plot([],  pen="w")

    # show values in tooltip when we hover over graph
    def setup_hover(graph, history, label, unit):
        def mouse_moved(event):
            vb = graph.plotItem.vb
            mp = vb.mapSceneToView(event)
            x  = int(mp.x())
            if 0 <= x < len(history):
                QToolTip.showText(
                    graph.mapToGlobal(graph.mapFromScene(event)),
                    f"{label} : {round(history[x], 2)} {unit}"
                )
        graph.scene().sigMouseMoved.connect(mouse_moved)

    setup_hover(cpu_graph, cpu_history, "CPU", "%")
    setup_hover(mem_graph, mem_history, "RAM", "GB")
    setup_hover(diskio_graph, disk_history, "Disk I/O", "MB/s")
    setup_hover(read_graph, read_history, "Read", "MB/s")
    setup_hover(write_graph, write_history, "Write", "MB/s")

    # show system info below graph
    cpu_info   = QLabel("🖥 0 cores   0%")
    ram_label  = QLabel("💾 0.00 GB / 0.00 GB")
    disk_total = QLabel("💿 0.00 MB/s")
    disk_read  = QLabel("⬇ 0.00 MB/s")
    disk_write = QLabel("⬆ 0.00 MB/s")

    for lbl in [cpu_info, ram_label, disk_total, disk_read, disk_write]:
        lbl.setStyleSheet("border:none; color:white;")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(False)
    
    # make cards to show system graphs and related info 
    def make_card(graph, lbl):
        card = QFrame()
        card.setStyleSheet(CARD_STYLE)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QVBoxLayout()
        lay.setContentsMargins(6, 6, 6, 4)
        lay.setSpacing(2)
        lay.addWidget(graph)
        lay.addWidget(lbl, alignment=Qt.AlignCenter)
        card.setLayout(lay)
        return card

    dashboard = QHBoxLayout()
    dashboard.setSpacing(6)
    dashboard.addWidget(make_card(cpu_graph, cpu_info))
    dashboard.addWidget(make_card(mem_graph, ram_label))
    dashboard.addWidget(make_card(diskio_graph, disk_total))
    dashboard.addWidget(make_card(read_graph, disk_read))
    dashboard.addWidget(make_card(write_graph, disk_write))

    # create main table
    table = QTableWidget()
    table.setRowCount(len(process_data))
    table.setColumnCount(11)
    table.setHorizontalHeaderLabels([
        "", "Process", "Status", "Start/Stop",
        "CPU %", "CPU Graph", "Memory (MB)", "Memory Graph",
        "Disk I/O (MB/s)", "Read (MB/s)", "Write (MB/s)",
    ])
    table.setStyleSheet(f"""
        QTableWidget {{
            background-color: {BG_DARK};
            color: white;
            gridline-color: gray;
        }}
        QTableWidget::item {{
            background-color: #1D2951;
            padding: 2px 4px;
        }}
        QHeaderView::section {{
            background-color: {BTN_BLUE};
            color: white;
            font-weight: bold;
            border: 1px solid gray;
            padding: 5px;
        }}
        QCheckBox {{
            background-color: {BG_TABLE};
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid white;
            background-color: {BG_TABLE};
        }}
        QCheckBox::indicator:checked {{
            border: 2px solid white;
            background-color: white;
        }}
        QScrollBar:vertical {{
            width: 15px;
        }}
    """)

    # create an item in the table
    def createItem(value):
        item = QTableWidgetItem(value)
        item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    # when start or stop button is clicked - change the text to running/stopped and change button icon
    def button_clicked(row, button):
        sl = status_labels[row]
        if sl.text() == "Stopped":
            sl.setText("Running"); 
            button.setText("■"); button.setFont(QFont("Arial", 10, QFont.Bold))
            button.setStyleSheet(STOPPED_STYLE)
        else:
            sl.setText("Stopped"); 
            button.setText("▶"); button.setFont(QFont("Arial", 16, QFont.Bold))
            button.setStyleSheet(RUNNING_STYLE)

    # changes the text to running of all selected proccess by checkbox 
    def run_selected():
        for row, check in enumerate(checkboxes):
            if check.isChecked():
                sl = status_labels[row]
                cb = buttons[row]
                if sl.text() == "Stopped":
                    sl.setText("Running")
                    cb.setText("■"); cb.setFont(QFont("Arial", 10, QFont.Bold))

    # first column (checkbox column) header is a button - when clicked changes the text of selected process to running
    header_button = QPushButton("▶")
    header_button.setFixedSize(30, 30)
    header_button.setFont(QFont("Arial", 16, QFont.Bold))
    header_button.setStyleSheet(f"""
        QPushButton {{ background-color:{BTN_BLUE}; color:white; border-radius:5px; }}
        QPushButton:hover {{ background-color:{BTN_HOVER}; }}
    """)
    header_button.clicked.connect(run_selected)
    GRAPH_COL_W = 140

    # to create one table row for each monitored process
    for row, process in enumerate(process_data):
        # checkbox column used for multi-process selection
        name = process[0]
        check = QCheckBox()
        ctr   = QWidget(); ctr.setStyleSheet(f"background-color:{BG_TABLE};")
        cl    = QHBoxLayout(); cl.addWidget(check, alignment=Qt.AlignCenter)
        cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0); ctr.setLayout(cl)
        checkboxes.append(check)
        table.setCellWidget(row, 0, ctr)

        # process name column
        table.setItem(row, 1, createItem(name))

        # status column showing current process state
        sl = QLabel("Stopped"); sl.setStyleSheet("color:white; background:transparent;")
        sl.setAlignment(Qt.AlignCenter)
        status_labels.append(sl)
        sc = QWidget(); sc.setStyleSheet(f"background-color:{BG_TABLE};")
        sl2 = QHBoxLayout(); sl2.addWidget(sl, alignment=Qt.AlignCenter)
        sl2.setContentsMargins(0, 0, 0, 0); sl2.setSpacing(0); sc.setLayout(sl2)
        table.setCellWidget(row, 2, sc)

        # start/stop control button for the process
        b1 = QPushButton("▶")
        b1.setFixedSize(30, 30)
        b1.setFont(QFont("Arial", 16, QFont.Bold))
        b1.setStyleSheet(RUNNING_STYLE)
        bc = QWidget(); bc.setStyleSheet(f"background-color:{BG_TABLE};")
        bl = QHBoxLayout(); bl.addWidget(b1, alignment=Qt.AlignCenter)
        bl.setContentsMargins(0, 0, 0, 0); bl.setSpacing(0); bc.setLayout(bl)
        b1.clicked.connect(lambda checked, r=row, btn=b1: button_clicked(r, btn))
        table.setCellWidget(row, 3, bc)
        buttons.append(b1)

        # initialize statistics columns with default values
        # CPU %, Memory, Disk I/O, Read and Write
        for col in (4, 6, 8, 9, 10):
            table.setItem(row, col, createItem("0.00"))

        # plot cpu graphs process wise
        cpu_plot = pg.PlotWidget()
        cpu_plot.setBackground(BG_TABLE)
        cpu_plot.setFixedSize(GRAPH_COL_W, 44)
        cpu_plot.hideAxis("left"); cpu_plot.hideAxis("bottom")
        table.setCellWidget(row, 5, cpu_plot)
        cpu_plot.setMaximumWidth(140)
        cpu_plot.setMinimumWidth(140)

        # plot memory graphs process wise
        mem_plot = pg.PlotWidget()
        mem_plot.setBackground(BG_TABLE)
        mem_plot.setFixedSize(GRAPH_COL_W, 44)
        mem_plot.hideAxis("left"); mem_plot.hideAxis("bottom")
        table.setCellWidget(row, 7, mem_plot)
        mem_plot.setMaximumWidth(140)
        mem_plot.setMinimumWidth(140)

        cpu_plot.setContentsMargins(0,0,0,0)
        cpu_plot.getPlotItem().setContentsMargins(0,0,0,0)

        mem_plot.setContentsMargins(0,0,0,0)
        mem_plot.getPlotItem().setContentsMargins(0,0,0,0)

        # append to history list
        cpu_process_history[name] = []
        mem_process_history[name] = []
        cpu_graphs[name]          = cpu_plot
        mem_graphs[name]          = mem_plot
        setup_hover(cpu_plot, cpu_process_history[name], "CPU", "%")
        setup_hover(mem_plot, mem_process_history[name], "RAM", "MB")
        process_profile_data[name] = []

        table.setRowHeight(row, 54)

    # configure process table layout
    # fixed widths for checkbox, status, button and graph columns
    # stretch remaining columns to use available space
    # enable scrollbars and hide row numbers

    hdr = table.horizontalHeader()
    table.setColumnWidth(0,50)

    hdr.setSectionResizeMode(2, QHeaderView.Fixed)
    table.setColumnWidth(2,100)

    hdr.setSectionResizeMode(3, QHeaderView.Fixed)
    table.setColumnWidth(3,100)

    hdr.setSectionResizeMode(1, QHeaderView.Stretch)

    hdr.setSectionResizeMode(4, QHeaderView.Stretch)
    hdr.setSectionResizeMode(5, QHeaderView.Fixed)
    table.setColumnWidth(5, 160)
    hdr.setSectionResizeMode(6, QHeaderView.Stretch)
    hdr.setSectionResizeMode(7, QHeaderView.Fixed)
    table.setColumnWidth(7, 160)
    hdr.setSectionResizeMode(8, QHeaderView.Stretch)
    hdr.setSectionResizeMode(9, QHeaderView.Stretch)
    hdr.setSectionResizeMode(10, QHeaderView.Stretch)

    table.horizontalHeaderItem(0).setTextAlignment(Qt.AlignCenter)
    table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    table.verticalHeader().hide()

    # checkbox column (0) and start/stop button column (3) hidden for now - not implemented yet
    table.setColumnHidden(3, True)
    table.setColumnHidden(0,True)

    #header_button.setParent(table)
    #header_button.move(5, 8)
    #header_button.raise_()
    #header_button.show()
    
    # recording button
    record_label = QLabel("Record every")
    record_label.setFont(QFont("Arial", 10, QFont.Bold))
    record_label.setStyleSheet("color:white")
    till_label = QLabel("Till")
    till_label.setFont(QFont("Arial", 10, QFont.Bold))
    till_label.setStyleSheet("color:white")

    # to enter seconds
    sec_box = QSpinBox()
    sec_box.setMinimum(1); sec_box.setMaximum(3600)
    sec_box.setFixedWidth(70); sec_box.setValue(5)
    sec_label = QLabel("sec"); sec_label.setStyleSheet("color:white")

    # start stop button for recording
    record_start = QPushButton("▶"); record_end = QPushButton("■")
    record_start.setStyleSheet(RUNNING_STYLE); record_end.setStyleSheet(STOPPED_STYLE)
    record_end.setEnabled(False) 
    for b in (record_start, record_end):
        b.setFixedSize(30, 30)
    record_start.setFont(QFont("Arial", 16, QFont.Bold))
    record_end.setFont(QFont("Arial", 10, QFont.Bold))

    # date time box to select until what date & time to record
    till_box = QDateTimeEdit(); till_box.setCalendarPopup(True)
    till_box.setDisplayFormat("dd-MM-yyyy hh:mm AP")
    future_time = QDateTime.currentDateTime().addSecs(60)
    till_box.setDateTime(future_time)
    till_box.setMinimumDateTime(future_time)
    till_box.setFixedWidth(200)

    record_timer = QTimer()

    # to check if selected time is greater than current time
    def check_time():
        record_start.setEnabled(till_box.dateTime() > QDateTime.currentDateTime())
    till_box.dateTimeChanged.connect(check_time)
    timer_check = QTimer()

    timer_check.timeout.connect(check_time)
    timer_check.start(1000)

    # to display file path of any parquet file saved
    file_path_label = QLabel("No File Saved")
    file_path_label.setStyleSheet("color:white")
    file_path_label.setFont(QFont("Arial", 7, QFont.Bold))
    file_label = QLabel("File Location:")
    file_label.setFixedWidth(100); file_label.setStyleSheet("color:white")
    file_label.setFont(QFont("Arial", 8, QFont.Bold))
    
    # to save recorded data & graphs to folder
    def save_recording():
        recording_folder = os.path.join(os.getcwd(),"Recording")
        graphs_folder = os.path.join(recording_folder,"Graphs")
        os.makedirs(graphs_folder,exist_ok=True)
        parquet_path = os.path.join(recording_folder,"recording_data.parquet")
        columns = ["Timestamp","Process Name","Status","CPU %","Memory(MB)","Disk I/O(MB/s)","Disk Read(MB/s)","Disk Write(MB/s)"]
        df = pd.DataFrame(recorded_data,columns = columns)
        df.to_parquet(parquet_path,index = False)
        file_path_label.setText(parquet_path)
        os.makedirs(graphs_folder,exist_ok = True)

        # to save process wise graphs
        for process_name in df["Process Name"].unique():
            process_df = df[df["Process Name"] == process_name].copy()
            process_df["Timestamp"] = pd.to_datetime(process_df["Timestamp"], format="%d-%m-%Y %I:%M:%S.%f %p")
            if len(process_df) < 2:
                continue
            plt.figure(figsize = (16, 12))
            plt.subplot(321)
            plt.plot(process_df["Timestamp"], process_df["CPU %"])
            plt.xticks(rotation=45)
            plt.title(f"{process_name} CPU")
            plt.subplot(322)
            plt.plot(process_df["Timestamp"], process_df["Memory(MB)"])
            plt.xticks(rotation=45)
            plt.title(f"{process_name} Memory")
            plt.subplot(323)
            plt.plot(process_df["Timestamp"], process_df["Disk I/O(MB/s)"])
            plt.xticks(rotation=45)
            plt.title(f"{process_name} Disk I/O")
            plt.subplot(324)
            plt.plot(process_df["Timestamp"],process_df["Disk Read(MB/s)"])
            plt.xticks(rotation=45)
            plt.title(f"{process_name} Read")
            plt.subplot(325)
            plt.plot(process_df["Timestamp"],process_df["Disk Write(MB/s)"])
            plt.xticks(rotation=45)
            plt.title(f"{process_name} Write")
            safe_name = process_name.replace("/","_").replace("\\","_")
            plt.subplots_adjust(hspace=0.5,wspace=0.3)
            plt.gcf().autofmt_xdate()
            plt.savefig(os.path.join(graphs_folder,f"{safe_name}.png"))
            plt.close()
        msg = QMessageBox()
        msg.setWindowTitle("Recording")
        msg.setText("Recording file & graphs saved successfully")
        msg.setStyleSheet(
            "QLabel{color:white;}"
            "QPushButton{color:white;background-color:#27427a;}"
            "QMessageBox{background-color:#0a1924;}"
        )
        msg.exec_()
    
     # to save process wise data of table
    def record_values():
        ts = QDateTime.currentDateTime().toString("dd-MM-yyyy hh:mm:ss.zzz AP")
        for row in range(table.rowCount()):
            recorded_data.append([
                ts,
                table.item(row, 1).text(),
                status_labels[row].text(),
                table.item(row, 4).text(),
                table.item(row, 6).text(),
                table.item(row, 8).text(),
                table.item(row, 9).text(),
                table.item(row, 10).text()
            ])
        if QDateTime.currentDateTime() > till_box.dateTime():
            record_timer.stop()
            save_recording()
            record_end.setEnabled(False)
            record_start.setEnabled(True)

    # to start recording
    def record():
        recorded_data.clear()
        msg = QMessageBox(); msg.setWindowTitle("Recording")
        msg.setText("Recording started successfully")
        record_end.setEnabled(True); record_start.setEnabled(False)
        msg.setStyleSheet("QLabel{color:white;} QPushButton{color:white;background-color:#27427a;} QMessageBox{background-color:#0a1924;}")
        msg.exec_()
        try: record_timer.timeout.disconnect()
        except TypeError: pass
        record_values()
        record_timer.timeout.connect(record_values)
        record_timer.start(sec_box.value() * 1000)

    # to stop recording
    def stop_record():
        record_timer.stop()
        save_recording()
        record_end.setEnabled(False)
        record_start.setEnabled(True)

    record_start.clicked.connect(record)
    record_end.clicked.connect(stop_record)

    # profiling label
    profile_label = QLabel("Profiling:")
    profile_label.setFont(QFont("Arial", 10, QFont.Bold))
    profile_label.setStyleSheet("color:white")

    # start stop button for profiling
    profile_start = QPushButton("▶"); profile_stop = QPushButton("■")
    profile_start.setStyleSheet(RUNNING_STYLE); profile_stop.setStyleSheet(STOPPED_STYLE)
    profile_stop.setEnabled(False)
    for b in (profile_start, profile_stop):
        b.setFixedSize(30, 30)
    profile_start.setFont(QFont("Arial", 16, QFont.Bold))
    profile_stop.setFont(QFont("Arial", 10, QFont.Bold))

    profile_data  = []
    profile_timer = QTimer()

    # to collect info for profiling
    def collect_profile():
        ts = QDateTime.currentDateTime().toString("dd-MM-yyyy hh:mm:ss.zzz AP")
        try:
            cpu_val = float(cpu_info.text().split()[-1].replace("%","").replace("[OFFLINE]","0"))
        except: cpu_val = 0.0
        try:
            ram_val = float(ram_label.text().split()[1])
        except: ram_val = 0.0
        try:
            io_val = float(disk_total.text().split()[1])
        except: io_val = 0.0
        try:
            r_val = float(disk_read.text().split()[1])
        except: r_val = 0.0
        try:
            w_val = float(disk_write.text().split()[1])
        except: w_val = 0.0
        profile_data.append([ts, cpu_val, ram_val, io_val, r_val, w_val])
        
        # process wise info
        for row in range(table.rowCount()):
            name = process_data[row][0]
            try:
                process_profile_data[name].append([
                    ts,
                    float(table.item(row, 4).text()),
                    float(table.item(row, 6).text()),
                    float(table.item(row, 8).text()),
                    float(table.item(row, 9).text()),
                    float(table.item(row, 10).text()),
                ])
            except: continue

    # to start profiling
    def start_profile():
        profile_stop.setEnabled(True); profile_start.setEnabled(False)
        msg = QMessageBox(); msg.setWindowTitle("Profiling")
        msg.setText("Profiling started successfully")
        msg.setStyleSheet("QLabel{color:white;} QPushButton{color:white;background-color:#27427a;} QMessageBox{background-color:#0a1924;}")
        msg.exec_()
        profile_data.clear()
        try: profile_timer.timeout.disconnect()
        except TypeError: pass
        profile_timer.timeout.connect(collect_profile)
        profile_timer.start(1000)
        for name in process_profile_data:
            process_profile_data[name].clear()

    # to save profiling data to parquet file
    def save_profile():
        profiling_folder = os.path.join(os.getcwd(),"Profiling")
        graphs_folder = os.path.join(profiling_folder,"Graphs")
        os.makedirs(graphs_folder,exist_ok=True)
        df_sys   = pd.DataFrame(profile_data,
                                columns=["Timestamp","CPU %","RAM GB","Disk I/O (MB/s)","Read (MB/s)","Write (MB/s)"])
        sys_path = os.path.join(profiling_folder,"system_profile.parquet")
        df_sys.to_parquet(sys_path)
        df_sys["Timestamp"] = pd.to_datetime(df_sys["Timestamp"],format="%d-%m-%Y %I:%M:%S.%f %p")

        # save graphs from profiling parquet file
        plt.figure(figsize=(16,12))

        plt.subplot(321)
        plt.plot(df_sys["Timestamp"], df_sys["CPU %"])
        plt.xticks(rotation=45)
        plt.title("System CPU")

        plt.subplot(322)
        plt.plot(df_sys["Timestamp"], df_sys["RAM GB"])
        plt.xticks(rotation=45)
        plt.title("System Memory")

        plt.subplot(323)
        plt.plot(df_sys["Timestamp"], df_sys["Disk I/O (MB/s)"])
        plt.xticks(rotation=45)
        plt.title("System Disk I/O")

        plt.subplot(324)
        plt.plot(df_sys["Timestamp"], df_sys["Read (MB/s)"])
        plt.xticks(rotation=45)
        plt.title("System Read")

        plt.subplot(325)
        plt.plot(df_sys["Timestamp"], df_sys["Write (MB/s)"])
        plt.xticks(rotation=45)
        plt.title("System Write")
        plt.subplots_adjust(hspace=0.5,wspace=0.3)
        plt.gcf().autofmt_xdate()
        plt.savefig(os.path.join(graphs_folder,"system_profile.png"))
        plt.close()
        # process wise profiling data graphs
        for pname, pdata in process_profile_data.items():
            if len(pdata) < 2:
                continue
            df = pd.DataFrame(pdata,columns=["Timestamp","CPU %","Memory MB","Disk I/O","Read","Write"])
            df["Timestamp"] = pd.to_datetime(df["Timestamp"],format="%d-%m-%Y %I:%M:%S.%f %p")

            plt.figure(figsize=(16,12))

            plt.subplot(321)
            plt.plot(df["Timestamp"], df["CPU %"])
            plt.xticks(rotation=45)
            plt.title(f"{pname} CPU")

            plt.subplot(322)
            plt.plot(df["Timestamp"], df["Memory MB"])
            plt.xticks(rotation=45)
            plt.title(f"{pname} Memory")

            plt.subplot(323)
            plt.plot(df["Timestamp"], df["Disk I/O"])
            plt.xticks(rotation=45)
            plt.title(f"{pname} Disk I/O")

            plt.subplot(324)
            plt.plot(df["Timestamp"], df["Read"])
            plt.xticks(rotation=45)
            plt.title(f"{pname} Read")

            plt.subplot(325)
            plt.plot(df["Timestamp"], df["Write"])
            plt.xticks(rotation=45)
            plt.title(f"{pname} Write")
            safe_name = pname.replace("/", "_")
            safe_name = safe_name.replace("\\", "_")
            plt.subplots_adjust(hspace=0.5,wspace=0.3)
            plt.gcf().autofmt_xdate()
            plt.savefig(os.path.join(graphs_folder,f"{safe_name}.png"))
            plt.close()
        rows = []
        # process wise profiling data
        for pname, pdata in process_profile_data.items():
            for r in pdata: rows.append([pname] + r)
        df_proc   = pd.DataFrame(rows,
                                 columns=["Process Name","Timestamp","CPU %","Memory MB",
                                          "Disk I/O (MB/s)","Read (MB/s)","Write (MB/s)"])
        proc_path = os.path.join(profiling_folder, "process_profile.parquet")
        df_proc.to_parquet(proc_path)

        file_path_label.setText(sys_path + "\n" + proc_path)

    # to stop profiling
    def stop_profile():
        profile_start.setEnabled(True); profile_stop.setEnabled(False)
        profile_timer.stop(); save_profile()
        msg = QMessageBox(); msg.setWindowTitle("Profiling")
        msg.setText("Profiling files & graphs saved successfully")
        msg.setStyleSheet("QLabel{color:white;} QPushButton{color:white;background-color:#27427a;} QMessageBox{background-color:#0a1924;}")
        msg.exec_()

    profile_start.clicked.connect(start_profile)
    profile_stop.clicked.connect(stop_profile)

    # bottom layout which contains profiling, recording and file path info
    bottom_bar = QHBoxLayout()
    bottom_bar.setContentsMargins(8, 4, 8, 4)
    bottom_bar.setSpacing(8)

    bottom_bar.addWidget(profile_label)
    bottom_bar.addWidget(profile_start)
    bottom_bar.addWidget(profile_stop)

    sep1 = QFrame(); sep1.setFrameShape(QFrame.VLine)
    sep1.setStyleSheet(f"color:{BORDER};")
    bottom_bar.addWidget(sep1)

    bottom_bar.addWidget(record_label)
    bottom_bar.addWidget(sec_box)
    bottom_bar.addWidget(sec_label)
    bottom_bar.addWidget(till_label)
    bottom_bar.addWidget(till_box)
    bottom_bar.addWidget(record_start)
    bottom_bar.addWidget(record_end)

    sep2 = QFrame(); sep2.setFrameShape(QFrame.VLine)
    sep2.setStyleSheet(f"color:{BORDER};")
    bottom_bar.addWidget(sep2)

    bottom_bar.addWidget(file_label)
    bottom_bar.addWidget(file_path_label, 1)

    tab_layout = QVBoxLayout()
    tab_layout.setContentsMargins(6, 6, 6, 6)
    tab_layout.setSpacing(6)
    tab_layout.addLayout(dashboard)
    tab_layout.addWidget(table, stretch=1)
    tab_layout.addLayout(bottom_bar)
    parent_tab.setLayout(tab_layout)

    # function to start all process - change all process status text to running
    def tot_start_click():
        for r in range(table.rowCount()):
            status_labels[r].setText("Running") 
            buttons[r].setText("■")
            buttons[r].setFont(QFont("Arial", 10, QFont.Bold))

    # function to stop all process - change all process status text to stopped
    def tot_stop_click():
        for r in range(table.rowCount()):
            status_labels[r].setText("Stopped")
            buttons[r].setText("▶")
            buttons[r].setFont(QFont("Arial", 16, QFont.Bold))

    # returns all process & system data & graph for each machine
    return {
        "process_data":        process_data,
        "cpu_history":         cpu_history,
        "mem_history":         mem_history,
        "disk_history":        disk_history,
        "read_history":        read_history,
        "write_history":       write_history,
        "cpu_graph":           cpu_graph,
        "mem_graph":           mem_graph,
        "diskio_line":         diskio_line,
        "read_line":           read_line,
        "write_line":          write_line,
        "cpu_info":            cpu_info,
        "ram_label":           ram_label,
        "disk_total":          disk_total,
        "disk_read":           disk_read,
        "disk_write":          disk_write,
        "cpu_graphs":          cpu_graphs,
        "mem_graphs":          mem_graphs,
        "cpu_process_history": cpu_process_history,
        "mem_process_history": mem_process_history,
        "table":               table,
        "status_labels":       status_labels,
        "tot_start_click":     tot_start_click,
        "tot_stop_click":      tot_stop_click,
    }

# create different tabs for each machine
hmi  = build_machine_tab(hmi_tab,  hmi_processes)
core = build_machine_tab(core_tab, core_processes)

# function to start all process - change all process status text to running in that specific tab
def tot_start_click():
    idx = tabs.currentIndex()
    if idx == 1:   hmi["tot_start_click"]()
    elif idx == 2: core["tot_start_click"]()

# function to stop all process - change all process status text to stopped in that specific tab
def tot_stop_click():
    idx = tabs.currentIndex()
    if idx == 1:   hmi["tot_stop_click"]()
    elif idx == 2: core["tot_stop_click"]()

tot_start.clicked.connect(tot_start_click)
tot_stop.clicked.connect(tot_stop_click)

layout = QVBoxLayout()
layout.setContentsMargins(15, 15, 15, 15)
layout.setSpacing(10)
layout.addLayout(header_layout)
layout.addWidget(tabs, stretch=1)
win.setLayout(layout)
win.showMaximized()

# function to round to 2 decimal places
def r2(v):
    return round(float(v), 2)

# update each machine values every second
def update_machine(ctx, ip):
    sys_stats = get_system_stats(ip)
    if sys_stats:
        cpu_per       = r2(sys_stats.total_cpu)
        used_ram      = r2(sys_stats.total_ram_used)
        total_ram_val = r2(sys_stats.total_ram)
        io            = r2(sys_stats.total_disk_io)
        read_mb       = r2(sys_stats.total_read)
        write_mb      = r2(sys_stats.total_write)
        cores         = sys_stats.logical_cores
        suffix        = ""
    else:
        cpu_per = used_ram = total_ram_val = io = read_mb = write_mb = 0.0
        cores  = 0
        suffix = " [OFFLINE]"

    def trim(lst):
        if len(lst) > 15: lst.pop(0)

    # for dynamic plotting save graph data history in list
    ctx["cpu_history"].append(cpu_per);    trim(ctx["cpu_history"])
    ctx["mem_history"].append(used_ram);   trim(ctx["mem_history"])
    ctx["disk_history"].append(io);        trim(ctx["disk_history"])
    ctx["read_history"].append(read_mb);   trim(ctx["read_history"])
    ctx["write_history"].append(write_mb); trim(ctx["write_history"])

    # system graphs
    ctx["cpu_graph"].clear();  ctx["cpu_graph"].plot(ctx["cpu_history"])
    ctx["mem_graph"].clear();  ctx["mem_graph"].plot(ctx["mem_history"])
    ctx["diskio_line"].setData(ctx["disk_history"])
    ctx["read_line"].setData(ctx["read_history"])
    ctx["write_line"].setData(ctx["write_history"])

    # system info
    ctx["cpu_info"].setText(  f"🖥 {cores} cores   {cpu_per}%{suffix}")
    ctx["ram_label"].setText( f"💾 {used_ram} GB / {total_ram_val} GB{suffix}")
    ctx["disk_total"].setText(f"💿 {io} MB/s{suffix}")
    ctx["disk_read"].setText( f"⬇ {read_mb} MB/s{suffix}")
    ctx["disk_write"].setText(f"⬆ {write_mb} MB/s{suffix}")

# process Statistics Update
# fetch process metrics from remote machine
# update table values
# maintain CPU and memory history
# refresh per-process graphs

    proc_names = [p[0] for p in ctx["process_data"]]
    proc_stats = get_process_stats(ip, proc_names)
    stat_map   = {s.name: s for s in proc_stats}

    table = ctx["table"]
    # update process metrics for all running processes
    for row, process in enumerate(ctx["process_data"]):
        name = process[0]
        cpu_threshold = process[1]
        mem_threshold = process[2]
        disk_threshold = process[3]
        stat = stat_map.get(name)
        status_label = ctx["status_labels"][row]
        if stat and stat.running:
            status_label.setText("Running")
        else:
            status_label.setText("Stopped")
        if stat and stat.running:
            # current process resource utilization
            cpu_v = r2(stat.cpu);     mem_v = r2(stat.memory_mb)
            io_v  = r2(stat.disk_io); r_v   = r2(stat.read_mb); w_v = r2(stat.write_mb)

             # maintain fixed-size history used by sparkline graphs
            ctx["cpu_process_history"][name].append(cpu_v)
            ctx["mem_process_history"][name].append(mem_v)
            if len(ctx["cpu_process_history"][name]) > 15:
                ctx["cpu_process_history"][name].pop(0)
            if len(ctx["mem_process_history"][name]) > 15:
                ctx["mem_process_history"][name].pop(0)

            # refresh CPU usage graph
            ctx["cpu_graphs"][name].clear()
            ctx["cpu_graphs"][name].plot(
                ctx["cpu_process_history"][name],
                pen="w"
            )
            ctx["cpu_graphs"][name].setXRange(0, 14, padding=0)
            
             # refresh memory usage graph
            ctx["mem_graphs"][name].clear()
            ctx["mem_graphs"][name].plot(
                ctx["mem_process_history"][name],
                pen="w"
            )
            ctx["mem_graphs"][name].setXRange(0, 14, padding=0)

            # update process statistics displayed in the table
            table.item(row, 4).setText(str(cpu_v))
            table.item(row, 6).setText(str(mem_v))
            table.item(row, 8).setText(str(io_v))
            table.item(row, 9).setText(str(r_v))
            table.item(row, 10).setText(str(w_v))

            # checking threshold
            cpu_item = table.item(row, 4)
            mem_item = table.item(row, 6)
            disk_item = table.item(row, 8)
            name_item = table.item(row, 1)

            # set to white first
            cpu_item.setForeground(QColor("white"))
            mem_item.setForeground(QColor("white"))
            disk_item.setForeground(QColor("white"))
            name_item.setForeground(QColor("white"))

            # if above threshold change color to red
            alarm = False
            if cpu_v > cpu_threshold:
                cpu_item.setForeground(QColor("#FF4444"))
                alarm = True

            if mem_v > mem_threshold:
                mem_item.setForeground(QColor("#FF4444"))
                alarm = True

            if io_v > disk_threshold:
                disk_item.setForeground(QColor("#FF4444"))
                alarm = True

            if alarm:
                name_item.setForeground(QColor("#FF4444"))
        else: # when process status changes to stopped - set all values to 0 and clear graph
            status_label.setText("Stopped")
            table.item(row, 4).setText("0.0")
            table.item(row, 6).setText("0.0")
            table.item(row, 8).setText("0.0")
            table.item(row, 9).setText("0.0")
            table.item(row,10).setText("0.0")
            
            ctx["cpu_process_history"][name].clear()
            ctx["cpu_graphs"][name].clear()
            ctx["mem_process_history"][name].clear()
            ctx["mem_graphs"][name].clear()

            # when process is stopped text color will become white
            table.item(row, 1).setForeground(QColor("white"))
            table.item(row, 4).setForeground(QColor("white"))
            table.item(row, 6).setForeground(QColor("white"))
            table.item(row, 8).setForeground(QColor("white"))

# periodically refresh monitoring data for both machines
def update_all():
    update_machine(hmi,  HMI_IP)
    update_machine(core, CORE_IP)

# refresh dashboard every second
timer = QTimer()
timer.timeout.connect(update_all)
timer.start(1000)

update_all()

sys.exit(app.exec_())