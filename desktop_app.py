import sys
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QLabel, QSplitter, QHeaderView,
                             QTabWidget, QComboBox, QLineEdit, QCheckBox, 
                             QGridLayout, QFileDialog, QMessageBox, QGroupBox, QPlainTextEdit, QProgressBar, QScrollArea, QFrame, QListView, QInputDialog, QMenu, QAction)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QColor, QFont, QIcon
import os
import subprocess
import json
from dataclasses import asdict
import matplotlib
import webbrowser
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.patches import Polygon

from geometry_engine import Airplane, Surface, Section, ControlSurface, PointMass

def run_avl_analysis(*args, **kwargs):
    import time
    time.sleep(0.1)
    return {'CL': 0.5, 'CD': 0.02, 'Cm': -0.1}

class Mpl3DCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=120):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.fig.patch.set_facecolor('#FFFFFF')
        self.fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.ax.set_facecolor('#FFFFFF')
        self.ax.set_axis_off()
        self.ax.view_init(elev=25, azim=-45)
        super().__init__(self.fig)

class MplBlueprintCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=120):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.fig.patch.set_facecolor('#FFFFFF')
        import matplotlib.gridspec as gridspec
        self.gs = gridspec.GridSpec(2, 2, figure=self.fig)
        self.ax_top = self.fig.add_subplot(self.gs[0, :])
        self.ax_front = self.fig.add_subplot(self.gs[1, 0])
        self.ax_side = self.fig.add_subplot(self.gs[1, 1])
        super().__init__(self.fig)

class AlphaSweepWorker(QThread):
    progress = pyqtSignal(int)
    result = pyqtSignal(list, list, list, list) # alphas, CLs, CDs, Cms
    error = pyqtSignal(str)
    
    def __init__(self, avl_file, mass_file, start_a, end_a, step):
        super().__init__()
        self.avl_file = avl_file
        self.mass_file = mass_file
        self.start_a = start_a
        self.end_a = end_a
        self.step = step
        
    def run(self):
        try:
            alphas = np.arange(self.start_a, self.end_a + self.step, self.step)
            CLs, CDs, Cms = [], [], []
            
            for i, a in enumerate(alphas):
                res = run_avl_analysis(self.avl_file, self.mass_file, alpha=float(a))
                CLs.append(res.get('CL', 0))
                CDs.append(res.get('CD', 0))
                Cms.append(res.get('Cm', 0))
                
                # Emit progress percentage
                pct = int((i + 1) / len(alphas) * 100)
                self.progress.emit(pct)
                
            self.result.emit(list(alphas), CLs, CDs, Cms)
        except Exception as e:
            self.error.emit(str(e))

class AVLDesktopApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AVL Design Studio")
        self.setWindowIcon(QIcon("icon.png"))
        self.resize(1400, 900)
        
        self.last_directory = ""
        self.init_data_model()

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)
        

        
        top_bar = QHBoxLayout()
        btn_load = QPushButton("Load Project")
        btn_save = QPushButton("Save Project")
        btn_docs = QPushButton("AVL Documentation")
        chk_dark = QCheckBox("Dark Mode")
        chk_dark.setChecked(True)
        
        btn_load.clicked.connect(self.load_project)
        btn_save.clicked.connect(self.save_project)
        btn_docs.clicked.connect(lambda: webbrowser.open("https://web.mit.edu/drela/Public/web/avl/"))
        chk_dark.stateChanged.connect(lambda state: self.apply_theme(state == Qt.Checked))
        
        top_bar.addWidget(btn_load)
        top_bar.addWidget(btn_save)
        top_bar.addWidget(btn_docs)
        top_bar.addStretch()
        top_bar.addWidget(chk_dark)
        
        main_layout.addLayout(top_bar)
        
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)
        
        self.left_tabs = QTabWidget()
        self.setup_geometry_tab()
        self.setup_mass_tab()
        self.setup_runcase_tab()
        self.left_tabs.currentChanged.connect(lambda _: self.update_plots())
        splitter.addWidget(self.left_tabs)

        self.right_tabs = QTabWidget()
        
        # 3D View Tab with options
        view_3d_tab = QWidget()
        view_3d_lay = QVBoxLayout(view_3d_tab)
        
        toolbar_3d = QHBoxLayout()
        toolbar_3d.addWidget(QLabel("Render Style:"))
        self.combo_render_style = QComboBox()
        self.combo_render_style.setView(QListView())
        self.combo_render_style.addItems(["Solid Shaded", "Wireframe", "Ghost (Transparent)"])
        self.combo_render_style.currentIndexChanged.connect(lambda _: self.update_plots())
        toolbar_3d.addWidget(self.combo_render_style)
        
        toolbar_3d.addWidget(QLabel("  |  View:"))
        btn_iso = QPushButton("Iso")
        btn_top = QPushButton("Top")
        btn_front = QPushButton("Front")
        btn_side = QPushButton("Side")
        for btn in [btn_iso, btn_top, btn_front, btn_side]:
            btn.setStyleSheet("padding: 4px 8px;")
            toolbar_3d.addWidget(btn)
            
        btn_iso.clicked.connect(lambda: self.set_3d_view(25, -45))
        btn_top.clicked.connect(lambda: self.set_3d_view(90, -90))
        btn_front.clicked.connect(lambda: self.set_3d_view(0, 0))
        btn_side.clicked.connect(lambda: self.set_3d_view(0, -90))
        
        toolbar_3d.addStretch()
        
        view_3d_lay.addLayout(toolbar_3d)
        
        self.canvas_3d = Mpl3DCanvas(self)
        view_3d_lay.addWidget(self.canvas_3d)
        
        self.right_tabs.addTab(view_3d_tab, "  3D View  ")
        self.canvas_bp = MplBlueprintCanvas(self)
        self.right_tabs.addTab(self.canvas_bp, "  Blueprint 3-View  ")
        
        # Raw Text Tab
        text_tab = QWidget()
        text_lay = QVBoxLayout(text_tab)
        text_splitter = QSplitter(Qt.Vertical)
        
        avl_group = QGroupBox("AVL Geometry File")
        avl_lay = QVBoxLayout(avl_group)
        self.text_avl = QPlainTextEdit()
        self.text_avl.setReadOnly(True)
        avl_lay.addWidget(self.text_avl)
        
        mass_group = QGroupBox("Mass & Inertia File")
        mass_lay = QVBoxLayout(mass_group)
        self.text_mass = QPlainTextEdit()
        self.text_mass.setReadOnly(True)
        mass_lay.addWidget(self.text_mass)
        
        text_splitter.addWidget(avl_group)
        text_splitter.addWidget(mass_group)
        text_lay.addWidget(text_splitter)
        self.right_tabs.addTab(text_tab, "  Raw Text  ")
        
        # Removed Analysis and Terminal tabs per request to focus strictly on geometry generation
        
        splitter.addWidget(self.right_tabs)
        
        splitter.setSizes([950, 450])
        self.apply_theme(dark_mode=True)
        self.refresh_ui()

    def apply_theme(self, dark_mode=False):
        self.dark_mode = dark_mode
        if dark_mode:
            bg_main = "#232428"          # XFLR5 window bg
            bg_card = "#2B2D32"          # Panels
            bg_input = "#1C1D21"         # Inputs
            bg_plot = "#000000"          # Pure black for 3D View
            border = "#151619"           # Deep dark borders
            border_light = "#41444A"     # Lighter borders for button edges
            text_c = "#D4D4D4"
            text_dim = "#919191"
            header_bg = "#32353B"
            accent_green = "#27ae60"     # Bright neon green
        else:
            bg_main = "#F3F3F3"
            bg_card = "#FFFFFF"
            bg_input = "#FFFFFF"
            bg_plot = "#FFFFFF"
            border = "#CCCCCC"
            border_light = "#E0E0E0"
            text_c = "#1E1E1E"
            text_dim = "#6D6D6D"
            header_bg = "#E5E5E5"
            accent_green = "#27ae60"
            
        self.setStyleSheet(f"""
            QMainWindow, QDialog {{ background-color: {bg_main}; color: {text_c}; font-family: "Cascadia Code", "Consolas", monospace; }}
            QWidget {{ color: {text_c}; font-size: 12px; font-family: "Cascadia Code", "Consolas", monospace; }}
            QMessageBox {{ background-color: {bg_card}; color: {text_c}; }}
            QMessageBox QLabel {{ color: {text_c}; background-color: transparent; }}
            QInputDialog QLabel {{ background-color: transparent; }}
            
            QTabWidget::pane {{ border: 1px solid {border}; background-color: {bg_main}; top: -1px; }}
            QTabBar:focus {{ outline: none; }}
            QTabBar::tab {{ background: {bg_main}; padding: 6px 14px; border: 1px solid {border}; margin-right: 1px; color: {text_dim}; font-size: 12px; }}
            QTabBar::tab:selected {{ background: {bg_card}; border-bottom-color: {bg_card}; color: {text_c}; font-weight: bold; border-top: 2px solid {accent_green}; }}
            QTabBar::tab:hover:!selected {{ background: {header_bg}; }}
            
            QTableWidget, QTableView {{ font-family: "Cascadia Code", "Consolas", monospace; font-size: 12px; background-color: {bg_input}; alternate-background-color: {bg_main}; color: {text_c}; gridline-color: {border}; border: 1px solid {border}; selection-background-color: #4A4D54; selection-color: white; outline: none; border-radius: 2px; }}
            QTableView::item {{ background-color: {bg_input}; border: none; padding: 3px; }}
            QTableView::item:alternate {{ background-color: {bg_main}; }}
            QTableView::item:selected {{ background-color: #4A4D54; color: white; }}
            QHeaderView {{ background-color: {bg_card}; border: none; border-bottom: 1px solid {border}; }}
            QHeaderView::section {{ font-family: "Cascadia Code", "Consolas", monospace; background-color: transparent; padding: 4px; border: none; border-right: 1px solid {border}; color: {text_dim}; font-weight: bold; font-size: 12px; }}
            QTableCornerButton::section {{ background-color: {bg_card}; border: none; border-bottom: 1px solid {border}; border-right: 1px solid {border}; }}
            
            QLineEdit, QComboBox {{ font-family: "Cascadia Code", "Consolas", monospace; font-size: 12px; background-color: {bg_input}; border: 1px solid {border}; padding: 4px 6px; color: {text_c}; min-height: 20px; border-radius: 2px; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox::down-arrow {{ image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 4px solid {text_dim}; margin-right: 8px; }}
            QLineEdit:focus, QComboBox:focus {{ border: 1px solid #5A5D65; background-color: {bg_input}; }}
            
            QPushButton {{ background-color: {header_bg}; color: {text_c}; padding: 5px 12px; border: 1px solid {border}; border-top: 1px solid {border_light}; border-radius: 2px; }}
            QPushButton:hover {{ background-color: #3C3F46; }}
            QPushButton:pressed {{ background-color: {bg_main}; border-top: 1px solid {border}; }}
            
            QComboBox QListView {{ background-color: {bg_input}; color: {text_c}; border: 1px solid {border}; outline: none; }}
            QComboBox QListView::item {{ background-color: {bg_input}; color: {text_c}; padding: 4px; border: none; }}
            QComboBox QListView::item:selected {{ background-color: {border_light}; color: {text_c}; }}
            
            QComboBox#chip_combo {{
                background-color: #2D3139;
                border: 1px solid transparent;
                border-radius: 12px;
                padding: 2px 10px;
                color: #A5B4FC;
                font-weight: bold;
                outline: none;
            }}
            QComboBox#chip_combo:focus {{
                border: 1px solid transparent;
                outline: none;
            }}
            QComboBox#chip_combo:hover {{
                background-color: #383D47;
                border: 1px solid transparent;
            }}
            QComboBox#chip_combo::drop-down {{ border: none; width: 0px; }}
            QComboBox#chip_combo::down-arrow {{ image: none; }}
            QComboBox#chip_combo QAbstractItemView {{
                border: 1px solid #41444A;
                background-color: #2D3139;
                color: #A5B4FC;
                selection-background-color: #4A4D54;
                outline: none;
                border-radius: 0px;
            }}
            QPushButton#primary_btn {{ background-color: {header_bg}; color: {text_c}; }}
            QPushButton#danger_btn {{ background-color: #D32F2F; color: white; border: 1px solid #B71C1C; border-top: 1px solid #EF5350; }}
            QPushButton#danger_btn:hover {{ background-color: #E53935; }}
            QPushButton#success_btn {{ background-color: {accent_green}; color: white; border: 1px solid #2B6B3E; border-top: 1px solid #5CBA7A; padding: 8px; font-weight: bold; font-size: 12px; }}
            QPushButton#success_btn:hover {{ background-color: #4CAF6B; }}
            
            QGroupBox {{ border: 1px solid {border}; margin-top: 12px; background-color: transparent; border-radius: 2px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 8px; padding: 0 4px; color: {text_c}; background-color: {bg_main}; top: 0px; font-weight: bold; }}
            
            QSplitter::handle {{ background-color: {border}; width: 2px; }}
            QScrollArea {{ border: none; background-color: transparent; }}
            QWidget#scroll_content, QWidget#tab_content {{ background-color: {bg_main}; }}
            QPlainTextEdit {{ background-color: {bg_input}; color: {text_c}; font-family: "Cascadia Code", "Consolas", monospace; font-size: 12px; border: 1px solid {border}; padding: 6px; border-radius: 2px; }}
            
            QScrollBar:horizontal {{ border: none; background: {bg_main}; height: 12px; margin: 0px 0px 0px 0px; }}
            QScrollBar::handle:horizontal {{ background: {border_light}; min-width: 20px; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ border: none; background: none; }}
            QScrollBar:vertical {{ border: none; background: {bg_main}; width: 12px; margin: 0px 0px 0px 0px; }}
            QScrollBar::handle:vertical {{ background: {border_light}; min-height: 20px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ border: none; background: none; }}
        """)
        
        if hasattr(self, 'canvas_3d'):
            self.canvas_3d.fig.patch.set_facecolor(bg_plot)
            self.canvas_3d.ax.set_facecolor(bg_plot)
            self.canvas_bp.fig.patch.set_facecolor(bg_plot)
            for ax in [self.canvas_bp.ax_top, self.canvas_bp.ax_front, self.canvas_bp.ax_side]:
                ax.set_facecolor(bg_plot)
            self.update_plots()

    def init_data_model(self):
        self.plane = Airplane(
            name="Shark Hawk Glider",
            surfaces=[
                Surface(
                    name="Main Wing", origin=(0.0, 0.0, 0.0), incidence=1.5,
                    sections=[
                        Section(y=0.0, chord=0.3, airfoil="NACA 2412"),
                        Section(y=0.6, chord=0.22, offset_x=0.02, z=0.15, airfoil="NACA 2412", control=ControlSurface("Aileron", 0.75, -1)),
                        Section(y=1.0, chord=0.15, offset_x=0.05, twist=-2.0, z=0.15, airfoil="NACA 2412", control=ControlSurface("Aileron", 0.75, -1))
                    ]
                ),
                Surface(
                    name="H-Tail", origin=(1.2, 0.0, 0.0), incidence=-1.0,
                    sections=[
                        Section(y=0.0, chord=0.1, airfoil="NACA 0012", control=ControlSurface("Elevator", 0.7, 1)),
                        Section(y=0.3, chord=0.08, offset_x=0.02, airfoil="NACA 0012", control=ControlSurface("Elevator", 0.7, 1))
                    ]
                ),
                Surface(
                    name="V-Tail", origin=(1.2, 0.0, 0.0), incidence=0.0, duplicate_y=False,
                    sections=[
                        Section(y=0.0, chord=0.12, z=0.0, airfoil="NACA 0012", control=ControlSurface("Rudder", 0.7, 1)),
                        Section(y=0.0, chord=0.08, offset_x=0.04, z=0.25, airfoil="NACA 0012", control=ControlSurface("Rudder", 0.7, 1))
                    ]
                )
            ],
            point_masses=[
                PointMass(name="Fuselage", mass=1.5, x=0.3, y=0.0, z=0.0),
                PointMass(name="Battery", mass=0.8, x=0.2, y=0.0, z=-0.05)
            ]
        )
        self.current_surface_idx = 0

    def setup_geometry_tab(self):
        from PyQt5.QtWidgets import QScrollArea, QFrame
        geom_scroll = QScrollArea()
        geom_scroll.setWidgetResizable(True)
        geom_scroll.setFrameShape(QFrame.NoFrame)
        geom_scroll.setObjectName("geom_scroll")
        
        geom_widget = QWidget()
        geom_widget.setObjectName("scroll_content")
        geom_widget.setStyleSheet("QWidget#scroll_content { background-color: transparent; }")
        
        lay = QVBoxLayout(geom_widget)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(25)
        
        ref_grp = QGroupBox("Global Airplane Parameters")
        ref_lay = QGridLayout(ref_grp)
        self.edit_name = QLineEdit()
        self.edit_mach = QLineEdit()
        self.edit_cdp = QLineEdit()
        self.edit_sref = QLineEdit()
        self.edit_cref = QLineEdit()
        self.edit_bref = QLineEdit()
        self.edit_iysym = QLineEdit()
        self.edit_izsym = QLineEdit()
        self.edit_zsym = QLineEdit()
        
        for e in [self.edit_name, self.edit_mach, self.edit_cdp, self.edit_sref, self.edit_cref, self.edit_bref, self.edit_iysym, self.edit_izsym, self.edit_zsym]:
            e.textChanged.connect(self.update_plane_refs)
        
        ref_lay.addWidget(QLabel("Name:"), 0, 0)
        ref_lay.addWidget(self.edit_name, 0, 1, 1, 3)
        ref_lay.addWidget(QLabel("Mach:"), 1, 0)
        ref_lay.addWidget(self.edit_mach, 1, 1)
        ref_lay.addWidget(QLabel("CDp:"), 1, 2)
        ref_lay.addWidget(self.edit_cdp, 1, 3)
        ref_lay.addWidget(QLabel("S_ref:"), 2, 0)
        ref_lay.addWidget(self.edit_sref, 2, 1)
        ref_lay.addWidget(QLabel("C_ref:"), 2, 2)
        ref_lay.addWidget(self.edit_cref, 2, 3)
        ref_lay.addWidget(QLabel("B_ref:"), 2, 4)
        ref_lay.addWidget(self.edit_bref, 2, 5)
        ref_lay.addWidget(QLabel("iYsym:"), 3, 0)
        ref_lay.addWidget(self.edit_iysym, 3, 1)
        ref_lay.addWidget(QLabel("iZsym:"), 3, 2)
        ref_lay.addWidget(self.edit_izsym, 3, 3)
        ref_lay.addWidget(QLabel("Zsym:"), 3, 4)
        ref_lay.addWidget(self.edit_zsym, 3, 5)
        lay.addWidget(ref_grp)

        surf_grp = QGroupBox("Surface Editor")
        surf_lay = QVBoxLayout(surf_grp)
        
        top_h = QHBoxLayout()
        self.combo_surf = QComboBox()
        self.combo_surf.setView(QListView())
        self.combo_surf.currentIndexChanged.connect(self.on_surface_selected)
        btn_add_surf = QPushButton("Add Surf")
        btn_add_surf.setObjectName("primary_btn")
        btn_add_surf.clicked.connect(self.add_surface)
        btn_del_surf = QPushButton("Del Surf")
        btn_del_surf.setObjectName("danger_btn")
        btn_del_surf.clicked.connect(self.del_surface)
        top_h.addWidget(self.combo_surf)
        top_h.addWidget(btn_add_surf)
        top_h.addWidget(btn_del_surf)
        surf_lay.addLayout(top_h)
        
        props_lay = QGridLayout()
        self.edit_surf_name = QLineEdit()
        self.edit_ox = QLineEdit()
        self.edit_oy = QLineEdit()
        self.edit_oz = QLineEdit()
        self.edit_inc = QLineEdit()
        self.edit_nchord = QLineEdit()
        self.edit_cspace = QLineEdit()
        self.chk_dup = QCheckBox("Y-Duplicate (Symmetric)")
        
        for e in [self.edit_surf_name, self.edit_ox, self.edit_oy, self.edit_oz, self.edit_inc, self.edit_nchord, self.edit_cspace]:
            e.textChanged.connect(self.update_surface_props)
        self.chk_dup.stateChanged.connect(self.update_surface_props)
        
        props_lay.addWidget(QLabel("Name:"), 0, 0)
        props_lay.addWidget(self.edit_surf_name, 0, 1, 1, 3)
        props_lay.addWidget(QLabel("Origin X:"), 1, 0)
        props_lay.addWidget(self.edit_ox, 1, 1)
        props_lay.addWidget(QLabel("Origin Y:"), 1, 2)
        props_lay.addWidget(self.edit_oy, 1, 3)
        props_lay.addWidget(QLabel("Origin Z:"), 1, 4)
        props_lay.addWidget(self.edit_oz, 1, 5)
        props_lay.addWidget(QLabel("Incidence:"), 2, 0)
        props_lay.addWidget(self.edit_inc, 2, 1)
        props_lay.addWidget(QLabel("Nchord:"), 2, 2)
        props_lay.addWidget(self.edit_nchord, 2, 3)
        props_lay.addWidget(QLabel("Cspace:"), 2, 4)
        props_lay.addWidget(self.edit_cspace, 2, 5)
        props_lay.addWidget(self.chk_dup, 3, 0, 1, 6)
        surf_lay.addLayout(props_lay)
        
        surf_lay.addWidget(QLabel("Sections Data (Include Nspan, Sspace)"))
        self.sec_table = QTableWidget(0, 11)
        self.sec_table.setHorizontalHeaderLabels(["Y", "Chord", "Off_X", "Dihed(deg)", "Twist", "Airfoil", "Nspan", "Sspace", "Ctrl", "Hinge", "CSym"])
        self.sec_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sec_table.horizontalHeader().setMinimumHeight(40)
        self.sec_table.verticalHeader().setDefaultSectionSize(36)
        self.sec_table.verticalHeader().setMinimumWidth(35)
        self.sec_table.setMinimumHeight(250)
        self.sec_table.setAlternatingRowColors(True)
        self.sec_table.itemChanged.connect(self.on_section_table_changed)
        
        # Context menu for Sections
        self.sec_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sec_table.customContextMenuRequested.connect(self.show_section_context_menu)
        
        surf_lay.addWidget(self.sec_table)
        
        sec_btn_lay = QHBoxLayout()
        btn_add_sec = QPushButton("Add Section")
        btn_add_sec.setObjectName("primary_btn")
        btn_add_sec.clicked.connect(self.add_section)
        btn_del_sec = QPushButton("Del Section")
        btn_del_sec.setObjectName("danger_btn")
        btn_del_sec.clicked.connect(self.del_section)
        sec_btn_lay.addWidget(btn_add_sec)
        sec_btn_lay.addWidget(btn_del_sec)
        surf_lay.addLayout(sec_btn_lay)
        
        lay.addWidget(surf_grp)
        
        btn_export = QPushButton("Export AVL Geometry (.avl)")
        btn_export.setObjectName("success_btn")
        btn_export.clicked.connect(self.export_geom_file)
        btn_import = QPushButton("Import AVL Geometry (.avl)")
        btn_import.setObjectName("primary_btn")
        btn_import.clicked.connect(self.import_avl_file)
        
        io_lay = QHBoxLayout()
        io_lay.addWidget(btn_import)
        io_lay.addWidget(btn_export)
        lay.addLayout(io_lay)

        
        geom_scroll.setWidget(geom_widget)
        self.left_tabs.addTab(geom_scroll, "  Geometry Engine  ")

    def setup_mass_tab(self):
        mass_widget = QWidget()
        mass_widget.setObjectName("tab_content")
        lay = QVBoxLayout(mass_widget)
        lay.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_content.setObjectName("scroll_content")
        scroll_lay = QVBoxLayout(scroll_content)
        scroll_lay.setContentsMargins(15, 15, 15, 15)
        
        gb_mass = QGroupBox("Point Masses")
        gb_lay = QVBoxLayout(gb_mass)
        
        self.mass_table = QTableWidget(0, 5)
        self.mass_table.setHorizontalHeaderLabels(["Name", "Mass", "X", "Y", "Z"])
        self.mass_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mass_table.horizontalHeader().setMinimumHeight(40)
        self.mass_table.verticalHeader().setDefaultSectionSize(36)
        self.mass_table.verticalHeader().setMinimumWidth(35)
        self.mass_table.setMinimumHeight(400)
        self.mass_table.setAlternatingRowColors(True)
        self.mass_table.itemChanged.connect(self.on_mass_table_changed)
        gb_lay.addWidget(self.mass_table)
        
        mass_btn_lay = QHBoxLayout()
        btn_add = QPushButton("Add Point Mass")
        btn_add.clicked.connect(self.add_mass)
        btn_del = QPushButton("Del Point Mass")
        btn_del.setObjectName("danger_btn")
        btn_del.clicked.connect(self.del_mass)
        mass_btn_lay.addWidget(btn_add)
        mass_btn_lay.addWidget(btn_del)
        gb_lay.addLayout(mass_btn_lay)
        
        gb_notes = QGroupBox("Design Notes / Description")
        gb_notes_lay = QVBoxLayout(gb_notes)
        self.txt_notes = QPlainTextEdit()
        self.txt_notes.setPlainText(self.plane.description)
        self.txt_notes.textChanged.connect(lambda: setattr(self.plane, 'description', self.txt_notes.toPlainText()))
        self.txt_notes.setPlaceholderText("Enter design specifications, configuration notes, or descriptions here...")
        self.txt_notes.setMinimumHeight(150)
        gb_notes_lay.addWidget(self.txt_notes)
        
        scroll_lay.addWidget(gb_mass)
        scroll_lay.addWidget(gb_notes)
        scroll_lay.addStretch()
        scroll.setWidget(scroll_content)
        lay.addWidget(scroll)
        
        bottom_lay = QVBoxLayout()
        bottom_lay.setContentsMargins(15, 0, 15, 15)
        
        gb_cg = QGroupBox("Center of gravity")
        gb_cg.setAlignment(Qt.AlignCenter)
        cg_lay = QGridLayout(gb_cg)
        
        self.out_mass = QLineEdit()
        self.out_x_cg = QLineEdit()
        self.out_y_cg = QLineEdit()
        self.out_z_cg = QLineEdit()
        
        for edit in [self.out_mass, self.out_x_cg, self.out_y_cg, self.out_z_cg]:
            edit.setReadOnly(True)
            edit.setAlignment(Qt.AlignRight)

        cg_lay.addWidget(QLabel("Total Mass="), 0, 0, Qt.AlignRight)
        cg_lay.addWidget(self.out_mass, 0, 1)
        cg_lay.addWidget(QLabel("kg"), 0, 2)
        
        cg_lay.addWidget(QLabel("X_CoG="), 1, 0, Qt.AlignRight)
        cg_lay.addWidget(self.out_x_cg, 1, 1)
        cg_lay.addWidget(QLabel("m"), 1, 2)
        
        cg_lay.addWidget(QLabel("Y_CoG="), 2, 0, Qt.AlignRight)
        cg_lay.addWidget(self.out_y_cg, 2, 1)
        cg_lay.addWidget(QLabel("m"), 2, 2)
        
        cg_lay.addWidget(QLabel("Z_CoG="), 3, 0, Qt.AlignRight)
        cg_lay.addWidget(self.out_z_cg, 3, 1)
        cg_lay.addWidget(QLabel("m"), 3, 2)
        
        bottom_lay.addWidget(gb_cg)
        
        btn_import_mass = QPushButton("Import Mass (.mass)")
        btn_import_mass.setObjectName("primary_btn")
        btn_import_mass.clicked.connect(self.import_mass_file)
        
        btn_export_mass = QPushButton("Export Mass (.mass)")
        btn_export_mass.setObjectName("success_btn")
        btn_export_mass.clicked.connect(self.export_mass_file)
        
        mass_io_lay = QHBoxLayout()
        mass_io_lay.addWidget(btn_import_mass)
        mass_io_lay.addWidget(btn_export_mass)
        bottom_lay.addLayout(mass_io_lay)
        
        lay.addLayout(bottom_lay)
        
        self.left_tabs.addTab(mass_widget, "  Mass Inertia  ")

    def setup_runcase_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        runcase_widget = QWidget()
        runcase_widget.setObjectName('scroll_content')
        scroll.setWidget(runcase_widget)
        
        lay = QVBoxLayout(runcase_widget)
        lay.setContentsMargins(15, 15, 15, 15)
        lay.setSpacing(15)

        # --- States ---
        gb_states = QGroupBox("Kinematic States")
        slay = QGridLayout(gb_states)
        
        states_config = [
            ("alpha", ["alpha", "CL", "Cm pitchmom"]),
            ("beta", ["beta", "CY", "Cn yaw mom"]),
            ("pb/2V", ["pb/2V", "Cl roll mom"]),
            ("qc/2V", ["qc/2V", "Cm pitchmom"]),
            ("rb/2V", ["rb/2V", "Cn yaw mom"])
        ]
        
        self.rc_states = {}
        for i, (name, options) in enumerate(states_config):
            lbl = QLabel(f"{name}  ->")
            lbl.setMinimumWidth(80)
            slay.addWidget(lbl, i, 0)
            
            cmb = QComboBox()
            cmb.setObjectName("chip_combo")
            cmb.setView(QListView())
            cmb.addItems(options)
            cmb.setMinimumWidth(120)
            slay.addWidget(cmb, i, 1)
            
            slay.addWidget(QLabel("="), i, 2)
            
            val = QLineEdit("0.0000")
            val.setMaximumWidth(120)
            slay.addWidget(val, i, 3)
            
            self.rc_states[name] = (cmb, val)
            
        slay.setColumnStretch(4, 1)
        lay.addWidget(gb_states)

        # --- Controls ---
        gb_ctrl = QGroupBox("Control Surfaces (Constraints)")
        clay = QGridLayout(gb_ctrl)
        
        ctrls_config = [
            ("aileron", ["Cl roll mom", "aileron"]),
            ("elevator", ["Cm pitchmom", "elevator", "CL"]),
            ("rudder", ["Cn yaw mom", "rudder", "CY"]),
            ("flap", ["flap", "CL"])
        ]
        
        self.rc_ctrls = {}
        for i, (name, options) in enumerate(ctrls_config):
            lbl = QLabel(f"{name}  ->")
            lbl.setMinimumWidth(80)
            clay.addWidget(lbl, i, 0)
            
            cmb = QComboBox()
            cmb.setObjectName("chip_combo")
            cmb.setView(QListView())
            cmb.addItems(options)
            cmb.setMinimumWidth(120)
            clay.addWidget(cmb, i, 1)
            
            clay.addWidget(QLabel("="), i, 2)
            
            val = QLineEdit("0.0000")
            val.setMaximumWidth(120)
            clay.addWidget(val, i, 3)
            
            self.rc_ctrls[name] = (cmb, val)

        clay.setColumnStretch(4, 1)
        # Dynamic refresh button for controls
        btn_refresh_ctrls = QPushButton("Fetch Controls from Geometry")
        # clay.addWidget(btn_refresh_ctrls, len(ctrls_config), 0, 1, 4)  # Placeholder for future dynamic logic
        lay.addWidget(gb_ctrl)
        
        # --- Environment ---
        gb_env = QGroupBox("Environment & Flight Parameters")
        elay = QGridLayout(gb_env)
        
        env_params = [
            ("bank", "0.0000"), ("elevation", "0.0000"),
            ("heading", "0.0000"), ("Mach", "0.0000"), 
            ("velocity", "30.8633"), ("density", "1.2250"), 
            ("grav.acc.", "9.81"), ("turn_rad.", "0.0000"), 
            ("load_fac.", "1.0000")
        ]
        
        self.rc_envs = {}
        for i, (name, default) in enumerate(env_params):
            row, col = i // 2, (i % 2) * 2
            lbl = QLabel(name + " :")
            lbl.setMinimumWidth(80)
            elay.addWidget(lbl, row, col)
            
            val = QLineEdit(default)
            val.setMaximumWidth(120)
            elay.addWidget(val, row, col + 1)
            self.rc_envs[name] = val
            
        elay.setColumnStretch(4, 1)
        lay.addWidget(gb_env)
        
        # --- Mass/CG ---
        gb_mass = QGroupBox("Mass CG Overrides")
        mlay = QGridLayout(gb_mass)
        
        mass_params = [
            ("X_cg", "0.0"), ("Y_cg", "0.0"), ("Z_cg", "0.0"),
            ("mass", "1.0"), ("Ixx", "1.0"), ("Iyy", "1.0"), ("Izz", "1.0")
        ]
        
        self.rc_mass = {}
        for i, (name, default) in enumerate(mass_params):
            row, col = i // 2, (i % 2) * 2
            lbl = QLabel(name + " :")
            lbl.setMinimumWidth(80)
            mlay.addWidget(lbl, row, col)
            
            val = QLineEdit(default)
            val.setMaximumWidth(120)
            mlay.addWidget(val, row, col + 1)
            self.rc_mass[name] = val
            
        mlay.setColumnStretch(4, 1)
        btn_pull_mass = QPushButton("Pull from Mass Inertia Tab")
        btn_pull_mass.clicked.connect(self.pull_mass_data)
        mlay.addWidget(btn_pull_mass, len(mass_params)//2 + 1, 0, 1, 4)
        lay.addWidget(gb_mass)

        btn_export_run = QPushButton("Export Run Case (.run)")
        btn_export_run.setObjectName("success_btn")
        btn_export_run.clicked.connect(self.export_run_file)
        
        lay.addWidget(btn_export_run)
        lay.addStretch()

        self.left_tabs.addTab(scroll, "  Run Case  ")

    def setup_analysis_tab(self):
        analysis_widget = QWidget()
        lay = QVBoxLayout(analysis_widget)
        lay.setContentsMargins(15, 15, 15, 15)
        
        # Alpha Sweep group
        sweep_group = QGroupBox("Automated Alpha Sweep")
        sweep_lay = QGridLayout(sweep_group)
        
        sweep_lay.addWidget(QLabel("Start Alpha (deg):"), 0, 0)
        self.edit_alpha_start = QLineEdit("-5.0")
        sweep_lay.addWidget(self.edit_alpha_start, 0, 1)
        
        sweep_lay.addWidget(QLabel("End Alpha (deg):"), 0, 2)
        self.edit_alpha_end = QLineEdit("15.0")
        sweep_lay.addWidget(self.edit_alpha_end, 0, 3)
        
        sweep_lay.addWidget(QLabel("Step (deg):"), 1, 0)
        self.edit_alpha_step = QLineEdit("1.0")
        sweep_lay.addWidget(self.edit_alpha_step, 1, 1)
        
        self.btn_run_sweep = QPushButton("Run Alpha Sweep")
        self.btn_run_sweep.setObjectName("primary_btn")
        self.btn_run_sweep.clicked.connect(self.run_alpha_sweep)
        sweep_lay.addWidget(self.btn_run_sweep, 1, 2)
        
        self.sweep_progress = QProgressBar()
        self.sweep_progress.setValue(0)
        self.sweep_progress.setVisible(False)
        sweep_lay.addWidget(self.sweep_progress, 2, 0, 1, 4)
        
        lay.addWidget(sweep_group)
        
        # Plots area for sweep results
        self.sweep_fig = Figure(figsize=(8, 4), dpi=100)
        # We will set the facecolor dynamically in refresh_ui or on_sweep_completed
        
        import matplotlib.gridspec as gridspec
        gs = gridspec.GridSpec(1, 3, figure=self.sweep_fig)
        self.ax_cl_alpha = self.sweep_fig.add_subplot(gs[0, 0])
        self.ax_cd_alpha = self.sweep_fig.add_subplot(gs[0, 1])
        self.ax_cm_alpha = self.sweep_fig.add_subplot(gs[0, 2])
        
        self.sweep_canvas = FigureCanvas(self.sweep_fig)
        lay.addWidget(self.sweep_canvas)
        
        self.right_tabs.addTab(analysis_widget, "  Analysis Tools  ")

    def run_alpha_sweep(self):
        try:
            start_a = float(self.edit_alpha_start.text())
            end_a = float(self.edit_alpha_end.text())
            step = float(self.edit_alpha_step.text())
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Please enter valid numbers for the sweep parameters.")
            return
            
        # Serialize current geometry and mass to temporary files
        avl_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_sweep.avl")
        mass_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_sweep.mass")
        
        self.plane.to_avl_file(avl_file)
        self.plane.to_mass_file(mass_file)
        
        self.btn_run_sweep.setEnabled(False)
        self.sweep_progress.setVisible(True)
        self.sweep_progress.setValue(0)
        
        self.worker = AlphaSweepWorker(avl_file, mass_file, start_a, end_a, step)
        self.worker.progress.connect(self.sweep_progress.setValue)
        self.worker.result.connect(self.on_sweep_completed)
        self.worker.error.connect(self.on_sweep_error)
        self.worker.start()
        
    def on_sweep_completed(self, alphas, CLs, CDs, Cms):
        self.btn_run_sweep.setEnabled(True)
        self.sweep_progress.setVisible(False)
        
        bg_color = "#2C2C2E" if self.dark_mode else "#FFFFFF"
        text_color = "#F5F5F7" if self.dark_mode else "#1D1D1F"
        grid_color = "#38383A" if self.dark_mode else "#D2D2D7"
        
        self.sweep_fig.patch.set_facecolor(bg_color)
        
        for ax in [self.ax_cl_alpha, self.ax_cd_alpha, self.ax_cm_alpha]:
            ax.clear()
            ax.set_facecolor(bg_color)
            ax.grid(True, linestyle='--', alpha=0.8, color=grid_color)
            ax.xaxis.label.set_color(text_color)
            ax.yaxis.label.set_color(text_color)
            ax.tick_params(colors=text_color)
            for spine in ax.spines.values():
                spine.set_color(grid_color)
                
        # CL vs Alpha
        self.ax_cl_alpha.plot(alphas, CLs, color='#0A84FF', linewidth=2, marker='o', markersize=4)
        self.ax_cl_alpha.set_title('Lift Coefficient (CL)', color=text_color, fontsize=10, pad=10)
        self.ax_cl_alpha.set_xlabel('Alpha (deg)')
        self.ax_cl_alpha.set_ylabel('CL')
        
        # CD vs Alpha
        self.ax_cd_alpha.plot(alphas, CDs, color='#FF3B30', linewidth=2, marker='o', markersize=4)
        self.ax_cd_alpha.set_title('Drag Coefficient (CD)', color=text_color, fontsize=10, pad=10)
        self.ax_cd_alpha.set_xlabel('Alpha (deg)')
        self.ax_cd_alpha.set_ylabel('CD')
        
        # Cm vs Alpha
        self.ax_cm_alpha.plot(alphas, Cms, color='#34C759', linewidth=2, marker='o', markersize=4)
        self.ax_cm_alpha.set_title('Pitching Moment (Cm)', color=text_color, fontsize=10, pad=10)
        self.ax_cm_alpha.set_xlabel('Alpha (deg)')
        self.ax_cm_alpha.set_ylabel('Cm')
        
        self.sweep_fig.tight_layout()
        self.sweep_canvas.draw()
        
    def on_sweep_error(self, err_msg):
        self.btn_run_sweep.setEnabled(True)
        self.sweep_progress.setVisible(False)
        QMessageBox.critical(self, "Sweep Error", f"An error occurred during the sweep:\n\n{err_msg}")


    def refresh_ui(self):
        for e in [self.edit_name, self.edit_mach, self.edit_cdp, self.edit_sref, self.edit_cref, self.edit_bref, self.edit_iysym, self.edit_izsym, self.edit_zsym, self.combo_surf]:
            e.blockSignals(True)
        
        self.edit_name.setText(self.plane.name)
        self.edit_mach.setText(str(self.plane.mach))
        self.edit_cdp.setText(str(self.plane.cdp))
        self.edit_sref.setText(str(self.plane.s_ref))
        self.edit_cref.setText(str(self.plane.c_ref))
        self.edit_bref.setText(str(self.plane.b_ref))
        self.edit_iysym.setText(str(self.plane.iy_sym))
        self.edit_izsym.setText(str(self.plane.iz_sym))
        self.edit_zsym.setText(str(self.plane.z_sym))
        
        self.combo_surf.clear()
        for s in self.plane.surfaces:
            self.combo_surf.addItem(s.name)
        if self.plane.surfaces:
            self.combo_surf.setCurrentIndex(self.current_surface_idx)
            
        for e in [self.edit_name, self.edit_mach, self.edit_cdp, self.edit_sref, self.edit_cref, self.edit_bref, self.edit_iysym, self.edit_izsym, self.edit_zsym, self.combo_surf]:
            e.blockSignals(False)
        
        self.refresh_surface_ui()
        self.refresh_mass_table()
        self.update_plots()

    def refresh_surface_ui(self):
        if not self.plane.surfaces: return
        surf = self.plane.surfaces[self.current_surface_idx]
        
        for e in [self.edit_surf_name, self.edit_ox, self.edit_oy, self.edit_oz, self.edit_inc, self.edit_nchord, self.edit_cspace, self.chk_dup]:
            e.blockSignals(True)
            
        self.edit_surf_name.setText(surf.name)
        self.edit_ox.setText(str(surf.origin[0]))
        self.edit_oy.setText(str(surf.origin[1]))
        self.edit_oz.setText(str(surf.origin[2]))
        self.edit_inc.setText(str(surf.incidence))
        self.edit_nchord.setText(str(surf.nchord))
        self.edit_cspace.setText(str(surf.cspace))
        self.chk_dup.setChecked(surf.duplicate_y)
        
        for e in [self.edit_surf_name, self.edit_ox, self.edit_oy, self.edit_oz, self.edit_inc, self.edit_nchord, self.edit_cspace, self.chk_dup]:
            e.blockSignals(False)
            
        self.sec_table.blockSignals(True)
        self.sec_table.setRowCount(len(surf.sections))
        
        def create_centered_item(text):
            item = QTableWidgetItem(str(text))
            item.setTextAlignment(Qt.AlignCenter)
            return item
            
        for i, sec in enumerate(surf.sections):
            self.sec_table.setItem(i, 0, create_centered_item(sec.y))
            self.sec_table.setItem(i, 1, create_centered_item(sec.chord))
            self.sec_table.setItem(i, 2, create_centered_item(sec.offset_x))
            
            import math
            dihedral = 0.0
            if i > 0:
                prev = surf.sections[i-1]
                dy = sec.y - prev.y
                dz = sec.z - prev.z
                if dy != 0:
                    dihedral = math.degrees(math.atan2(dz, dy))
            self.sec_table.setItem(i, 3, create_centered_item(round(dihedral, 3)))
            self.sec_table.setItem(i, 4, create_centered_item(sec.twist))
            
            # Create interactive Chip Card for Airfoil
            chip = QPushButton(sec.airfoil)
            chip.setStyleSheet("QPushButton { background-color: #2D4035; color: #4CAF50; border: 1px solid #4CAF50; border-radius: 10px; padding: 2px 8px; font-weight: bold; font-family: 'Cascadia Code', monospace; margin: 2px; } QPushButton:hover { background-color: #385042; }")
            chip.setCursor(Qt.PointingHandCursor)
            chip.clicked.connect(lambda _, r=i: self.edit_airfoil(r))
            
            chip_container = QWidget()
            chip_lay = QHBoxLayout(chip_container)
            chip_lay.setContentsMargins(0, 0, 0, 0)
            chip_lay.setAlignment(Qt.AlignCenter)
            chip_lay.addWidget(chip)
            
            self.sec_table.setCellWidget(i, 5, chip_container)
            self.sec_table.setItem(i, 5, create_centered_item(sec.airfoil)) # Store text in model for data updates
            
            self.sec_table.setItem(i, 6, create_centered_item(sec.nspan))
            self.sec_table.setItem(i, 7, create_centered_item(sec.sspace))
            
            c_name = sec.control.name if sec.control else ""
            c_hinge = str(sec.control.hinge_x_c) if sec.control else ""
            c_sym = str(sec.control.sym) if sec.control else ""
            
            self.sec_table.setItem(i, 8, create_centered_item(c_name))
            self.sec_table.setItem(i, 9, create_centered_item(c_hinge))
            self.sec_table.setItem(i, 10, create_centered_item(c_sym))
        self.sec_table.blockSignals(False)

    def refresh_mass_table(self):
        self.mass_table.blockSignals(True)
        self.mass_table.setRowCount(len(self.plane.point_masses))
        
        def create_centered_item(text):
            item = QTableWidgetItem(str(text))
            item.setTextAlignment(Qt.AlignCenter)
            return item
            
        for i, m in enumerate(self.plane.point_masses):
            self.mass_table.setItem(i, 0, create_centered_item(m.name))
            self.mass_table.setItem(i, 1, create_centered_item(m.mass))
            self.mass_table.setItem(i, 2, create_centered_item(m.x))
            self.mass_table.setItem(i, 3, create_centered_item(m.y))
            self.mass_table.setItem(i, 4, create_centered_item(m.z))
        self.mass_table.blockSignals(False)
        self.update_cg_label()

    def update_plane_refs(self):
        try:
            self.plane.name = self.edit_name.text()
            self.plane.mach = float(self.edit_mach.text())
            self.plane.cdp = float(self.edit_cdp.text())
            self.plane.s_ref = float(self.edit_sref.text())
            self.plane.c_ref = float(self.edit_cref.text())
            self.plane.b_ref = float(self.edit_bref.text())
            self.plane.iy_sym = int(self.edit_iysym.text())
            self.plane.iz_sym = int(self.edit_izsym.text())
            self.plane.z_sym = float(self.edit_zsym.text())
        except ValueError:
            pass

    def on_surface_selected(self, index):
        if index >= 0:
            self.current_surface_idx = index
            self.refresh_surface_ui()

    def update_surface_props(self):
        if not self.plane.surfaces: return
        surf = self.plane.surfaces[self.current_surface_idx]
        try:
            surf.name = self.edit_surf_name.text()
            self.combo_surf.blockSignals(True)
            self.combo_surf.setItemText(self.current_surface_idx, surf.name)
            self.combo_surf.blockSignals(False)
            surf.origin = (float(self.edit_ox.text()), float(self.edit_oy.text()), float(self.edit_oz.text()))
            surf.incidence = float(self.edit_inc.text())
            surf.nchord = int(self.edit_nchord.text())
            surf.cspace = float(self.edit_cspace.text())
            surf.duplicate_y = self.chk_dup.isChecked()
            self.update_plots()
        except ValueError:
            pass

    def edit_airfoil(self, row):
        if not self.plane.surfaces: return
        surf = self.plane.surfaces[self.current_surface_idx]
        if row >= len(surf.sections): return
        
        text, ok = QInputDialog.getText(self, "Edit Airfoil", "Enter airfoil name or file (e.g., NACA 2412):", QLineEdit.Normal, surf.sections[row].airfoil)
        if ok and text.strip():
            surf.sections[row].airfoil = text.strip()
            self.refresh_surface_ui()
            self.update_plots()

    def on_section_table_changed(self, item):
        if not self.plane.surfaces: return
        surf = self.plane.surfaces[self.current_surface_idx]
        
        self.sec_table.blockSignals(True)
        new_secs = []
        for i in range(self.sec_table.rowCount()):
            old_sec = surf.sections[i] if i < len(surf.sections) else Section()
            
            def get_f(col, default):
                it = self.sec_table.item(i, col)
                try:
                    return float(it.text()) if it else default
                except ValueError:
                    return default
                    
            def get_s(col, default, allow_empty=False):
                it = self.sec_table.item(i, col)
                if not it: return default
                txt = it.text().strip()
                if not txt and not allow_empty:
                    return default
                return txt

            y = get_f(0, old_sec.y)
            c = get_f(1, old_sec.chord)
            if c <= 0: c = 0.001
            
            off = get_f(2, old_sec.offset_x)
            
            import math
            default_dih = 0.0
            if i > 0:
                prev_y = new_secs[i-1].y
                prev_z = new_secs[i-1].z
                dy = y - prev_y
                dz = old_sec.z - prev_z
                if dy != 0:
                    default_dih = math.degrees(math.atan2(dz, dy))
                    
            dih_deg = get_f(3, default_dih)
            if i == 0:
                z_val = 0.0
            else:
                prev_sec = new_secs[i-1]
                dy = y - prev_sec.y
                z_val = prev_sec.z + dy * math.tan(math.radians(dih_deg))
                
            twi = get_f(4, old_sec.twist)
            air = get_s(5, old_sec.airfoil)
            nspan = int(get_f(6, old_sec.nspan))
            sspace = get_f(7, old_sec.sspace)
            
            c_name = get_s(8, old_sec.control.name if old_sec.control else "", allow_empty=True)
            ctrl = None
            if c_name:
                h = get_f(9, old_sec.control.hinge_x_c if old_sec.control else 0.7)
                sym = int(get_f(10, old_sec.control.sym if old_sec.control else 1))
                ctrl = ControlSurface(name=c_name, hinge_x_c=h, sym=sym)
                if self.sec_table.item(i, 9): self.sec_table.item(i, 9).setText(str(h))
                if self.sec_table.item(i, 10): self.sec_table.item(i, 10).setText(str(sym))
            else:
                if self.sec_table.item(i, 9): self.sec_table.item(i, 9).setText("")
                if self.sec_table.item(i, 10): self.sec_table.item(i, 10).setText("")
                
            new_secs.append(Section(y=y, chord=c, offset_x=off, z=z_val, twist=twi, airfoil=air, nspan=nspan, sspace=sspace, control=ctrl))
            
            if self.sec_table.item(i, 0): self.sec_table.item(i, 0).setText(str(y))
            if self.sec_table.item(i, 1): self.sec_table.item(i, 1).setText(str(c))
            if self.sec_table.item(i, 2): self.sec_table.item(i, 2).setText(str(off))
            if self.sec_table.item(i, 3): self.sec_table.item(i, 3).setText(str(round(dih_deg, 3)))
            if self.sec_table.item(i, 4): self.sec_table.item(i, 4).setText(str(twi))
            if self.sec_table.item(i, 5): self.sec_table.item(i, 5).setText(air)
            if self.sec_table.item(i, 6): self.sec_table.item(i, 6).setText(str(nspan))
            if self.sec_table.item(i, 7): self.sec_table.item(i, 7).setText(str(sspace))

        surf.sections = new_secs
        self.sec_table.blockSignals(False)
        self.update_plots()

    def on_mass_table_changed(self, item):
        self.mass_table.blockSignals(True)
        new_masses = []
        for i in range(self.mass_table.rowCount()):
            old_m = self.plane.point_masses[i] if i < len(self.plane.point_masses) else PointMass("Mass", 1.0)
            
            def get_f(col, default):
                it = self.mass_table.item(i, col)
                try:
                    return float(it.text()) if it else default
                except ValueError:
                    return default
                    
            def get_s(col, default):
                it = self.mass_table.item(i, col)
                return it.text().strip() if it and it.text().strip() else default
                
            n = get_s(0, old_m.name)
            m = get_f(1, old_m.mass)
            x = get_f(2, old_m.x)
            y = get_f(3, old_m.y)
            z = get_f(4, old_m.z)
            
            new_masses.append(PointMass(name=n, mass=m, x=x, y=y, z=z))
            
            if self.mass_table.item(i, 0): self.mass_table.item(i, 0).setText(n)
            if self.mass_table.item(i, 1): self.mass_table.item(i, 1).setText(str(m))
            if self.mass_table.item(i, 2): self.mass_table.item(i, 2).setText(str(x))
            if self.mass_table.item(i, 3): self.mass_table.item(i, 3).setText(str(y))
            if self.mass_table.item(i, 4): self.mass_table.item(i, 4).setText(str(z))

        self.plane.point_masses = new_masses
        self.mass_table.blockSignals(False)
        self.update_cg_label()
        self.update_plots()

    def update_cg_label(self):
        cg = self.plane.calculate_cg()
        total_mass = sum(m.mass for m in self.plane.point_masses)
        if hasattr(self, 'out_mass'):
            self.out_mass.setText(f"{total_mass:.3f}")
            self.out_x_cg.setText(f"{cg[0]:.3f}")
            self.out_y_cg.setText(f"{cg[1]:.3f}")
            self.out_z_cg.setText(f"{cg[2]:.3f}")

    def add_surface(self):
        self.plane.surfaces.append(Surface(f"Surface {len(self.plane.surfaces)+1}", sections=[Section(chord=0.1)]))
        self.current_surface_idx = len(self.plane.surfaces) - 1
        self.refresh_ui()

    def del_surface(self):
        if len(self.plane.surfaces) > 1:
            self.plane.surfaces.pop(self.current_surface_idx)
            self.current_surface_idx = 0
            self.refresh_ui()

    def add_section(self):
        if not self.plane.surfaces: return
        surf = self.plane.surfaces[self.current_surface_idx]
        new_y = surf.sections[-1].y + 1.0 if surf.sections else 0.0
        surf.sections.append(Section(y=new_y, chord=0.1))
        self.refresh_surface_ui()
        self.update_plots()

    def del_section(self):
        if not self.plane.surfaces: return
        surf = self.plane.surfaces[self.current_surface_idx]
        if len(surf.sections) > 1:
            row = self.sec_table.currentRow()
            if row >= 0:
                surf.sections.pop(row)
            else:
                surf.sections.pop()
            self.refresh_surface_ui()
            self.update_plots()

    def show_section_context_menu(self, pos):
        row = self.sec_table.rowAt(pos.y())
        if row < 0: return
        
        menu = QMenu(self)
        if getattr(self, 'dark_mode', False):
            menu.setStyleSheet("QMenu { background-color: #2B2D32; color: #D4D4D4; border: 1px solid #151619; } QMenu::item { padding: 5px 20px 5px 20px; } QMenu::item:selected { background-color: #41444A; }")
        
        action_before = QAction(f"Insert before section {row + 1}", self)
        action_before.triggered.connect(lambda: self.insert_section(row, before=True))
        
        action_after = QAction(f"Insert after section {row + 1}", self)
        action_after.triggered.connect(lambda: self.insert_section(row, before=False))
        
        action_del = QAction(f"Delete section {row + 1}", self)
        action_del.triggered.connect(lambda: self.delete_section_at(row))
        
        menu.addAction(action_before)
        menu.addAction(action_after)
        menu.addAction(action_del)
        
        menu.exec_(self.sec_table.viewport().mapToGlobal(pos))
        
    def delete_section_at(self, row):
        if not self.plane.surfaces: return
        surf = self.plane.surfaces[self.current_surface_idx]
        if len(surf.sections) > 1:
            surf.sections.pop(row)
            self.refresh_surface_ui()
            self.update_plots()

    def insert_section(self, row, before=True):
        if not self.plane.surfaces: return
        surf = self.plane.surfaces[self.current_surface_idx]
        
        import copy
        new_sec = copy.deepcopy(surf.sections[row])
        # Interpolate Y if possible to avoid exact overlaps
        if before:
            if row > 0:
                new_sec.y = (surf.sections[row].y + surf.sections[row-1].y) / 2.0
            else:
                new_sec.y = surf.sections[row].y - 0.1
            surf.sections.insert(row, new_sec)
        else:
            if row < len(surf.sections) - 1:
                new_sec.y = (surf.sections[row].y + surf.sections[row+1].y) / 2.0
            else:
                new_sec.y = surf.sections[row].y + 0.1
            surf.sections.insert(row + 1, new_sec)
            
        self.refresh_surface_ui()
        self.update_plots()

    def add_mass(self):
        self.plane.point_masses.append(PointMass("New Mass", 1.0))
        self.refresh_mass_table()
        self.update_plots()

    def del_mass(self):
        if len(self.plane.point_masses) > 0:
            row = self.mass_table.currentRow()
            if row >= 0:
                self.plane.point_masses.pop(row)
            else:
                self.plane.point_masses.pop()
            self.refresh_mass_table()
            self.update_plots()

    def pull_mass_data(self):
        try:
            total_mass = sum(pm.mass for pm in self.plane.point_masses)
            cg = self.plane.calculate_cg()
            if total_mass > 0:
                self.rc_mass["mass"].setText(f"{total_mass:.4f}")
                self.rc_mass["X_cg"].setText(f"{cg[0]:.4f}")
                self.rc_mass["Y_cg"].setText(f"{cg[1]:.4f}")
                self.rc_mass["Z_cg"].setText(f"{cg[2]:.4f}")
                
                # Calculate inertia
                Ixx = sum(pm.mass * ((pm.y - cg[1])**2 + (pm.z - cg[2])**2) for pm in self.plane.point_masses)
                Iyy = sum(pm.mass * ((pm.x - cg[0])**2 + (pm.z - cg[2])**2) for pm in self.plane.point_masses)
                Izz = sum(pm.mass * ((pm.x - cg[0])**2 + (pm.y - cg[1])**2) for pm in self.plane.point_masses)
                
                self.rc_mass["Ixx"].setText(f"{Ixx:.4f}")
                self.rc_mass["Iyy"].setText(f"{Iyy:.4f}")
                self.rc_mass["Izz"].setText(f"{Izz:.4f}")
                
                QMessageBox.information(self, "Success", "Pulled Mass, CG, and Inertia data successfully.")
            else:
                QMessageBox.warning(self, "Warning", "Total mass is 0. Add point masses in the Mass Inertia tab first.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to pull data:\n{str(e)}")

    def export_run_file(self):
        options = QFileDialog.Options()
        default_path = os.path.join(self.last_directory, f"{self.plane.name.replace(' ','_')}.run") if self.last_directory else f"{self.plane.name.replace(' ','_')}.run"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Run Case File", default_path, "Run Files (*.run)", options=options)
        if not file_path:
            return
            
        self.last_directory = os.path.dirname(file_path)
        
        try:
            lines = []
            lines.append(" ")
            lines.append("Run case  1:   -unnamed-                              ")
            lines.append(" ")
            
            # States constraints
            for name, (cmb, val) in self.rc_states.items():
                constraint = cmb.currentText()
                value = val.text()
                lines.append(f" {name:<12} ->  {constraint:<11} = {value:>9}")
                
            # Control constraints
            for name, (cmb, val) in self.rc_ctrls.items():
                constraint = cmb.currentText()
                value = val.text()
                lines.append(f" {name:<12} ->  {constraint:<11} = {value:>9}")
                
            lines.append(" ")
            
            # Print state values block (AVL expects these even if they are 0 or overridden by constraints)
            lines.append(" alpha     =   0.00000                                     ")
            lines.append(" beta      =   0.00000                                     ")
            lines.append(" pb/2V     =   0.00000                                     ")
            lines.append(" qc/2V     =   0.00000                                     ")
            lines.append(" rb/2V     =   0.00000                                     ")
            lines.append(" CL        =   0.00000                                     ")
            lines.append(" CDo       =   0.00000                                     ")
            
            # Environment
            for name in ["bank", "elevation", "heading", "Mach", "velocity", "density", "grav.acc.", "turn_rad.", "load_fac."]:
                val = self.rc_envs[name].text()
                lines.append(f" {name:<9} = {float(val):>9.5f}")
                
            # Mass & CG
            for name in ["X_cg", "Y_cg", "Z_cg", "mass", "Ixx", "Iyy", "Izz"]:
                val = self.rc_mass[name].text()
                lines.append(f" {name:<9} = {float(val):>9.5f}")
                
            # Rest of default parameters
            lines.append(" Ixy       =   0.00000                                     ")
            lines.append(" Iyz       =   0.00000                                     ")
            lines.append(" Izx       =   0.00000                                     ")
            lines.append(" visc CL_a =   0.00000                                     ")
            lines.append(" visc CL_u =   0.00000                                     ")
            lines.append(" visc CM_a =   0.00000                                     ")
            lines.append(" visc CM_u =   0.00000                                     ")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines) + "\n")
                
            QMessageBox.information(self, "Success", f"Successfully exported run case to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export run case:\n{str(e)}")

    def import_avl_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "Import AVL Geometry", self.last_directory, "AVL Files (*.avl);;All Files (*)", options=options)
        if file_path:
            self.last_directory = os.path.dirname(file_path)
            try:
                from geometry_engine import Airplane
                imported_plane = Airplane.parse_avl_file(file_path)
                # Keep existing point masses to prevent data loss
                imported_plane.point_masses = self.plane.point_masses
                self.plane = imported_plane
                
                # Full UI Refresh
                self.refresh_ui()
                self.update_plane_refs()
                self.update_plots()
                
                QMessageBox.information(self, "Success", f"Successfully imported {os.path.basename(file_path)}")
            except Exception as e:
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"Failed to import AVL file:\n{str(e)}")

    def export_geom_file(self):
        options = QFileDialog.Options()
        default_path = os.path.join(self.last_directory, f"{self.plane.name.replace(' ','_')}.avl") if self.last_directory else f"{self.plane.name.replace(' ','_')}.avl"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save AVL Geometry", default_path, "AVL Files (*.avl)", options=options)
        if file_path:
            self.last_directory = os.path.dirname(file_path)
            try:
                self.plane.to_avl_file(file_path)
                QMessageBox.information(self, "Success", f"Successfully exported geometry to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def import_mass_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Mass File", self.last_directory, "Mass Files (*.mass);;All Files (*)", options=options)
        if file_path:
            self.last_directory = os.path.dirname(file_path)
            try:
                from geometry_engine import Airplane
                Airplane.parse_mass_file(file_path, self.plane)
                
                import re
                def parse_scale(unit_str, is_mass=False):
                    match = re.search(r"([\d\.]+)\s*([a-zA-Z]+)", unit_str.strip())
                    if match:
                        val = float(match.group(1))
                        unit = match.group(2).lower()
                        if is_mass:
                            if unit in ['kg']: return val
                            if unit in ['g', 'gram', 'grams']: return val * 0.001
                            if unit in ['oz', 'ounce']: return val * 0.0283495
                            if unit in ['lb', 'lbs', 'pound']: return val * 0.453592
                        else:
                            if unit in ['m']: return val
                            if unit in ['cm']: return val * 0.01
                            if unit in ['mm']: return val * 0.001
                            if unit in ['in', 'inch']: return val * 0.0254
                            if unit in ['ft', 'feet']: return val * 0.3048
                        return val
                    return 1.0
                
                l_scale = parse_scale(self.plane.lunit, False)
                m_scale = parse_scale(self.plane.munit, True)
                
                if abs(l_scale - 1.0) > 1e-5 or abs(m_scale - 1.0) > 1e-5:
                    self.plane.b_ref *= l_scale
                    self.plane.c_ref *= l_scale
                    self.plane.s_ref *= (l_scale ** 2)
                    self.plane.cg = (self.plane.cg[0] * l_scale, self.plane.cg[1] * l_scale, self.plane.cg[2] * l_scale)
                    
                    for m in self.plane.point_masses:
                        m.x *= l_scale
                        m.y *= l_scale
                        m.z *= l_scale
                        m.mass *= m_scale
                        
                    for surf in self.plane.surfaces:
                        surf.origin = (surf.origin[0] * l_scale, surf.origin[1] * l_scale, surf.origin[2] * l_scale)
                        for sec in surf.sections:
                            sec.y *= l_scale
                            sec.offset_x *= l_scale
                            sec.z *= l_scale
                            sec.chord *= l_scale
                            
                    self.plane.lunit = "1.0 m"
                    self.plane.munit = "1.0 kg"
                    QMessageBox.information(self, "Units Converted", f"Detected non-standard units.\nAutomatically scaled entire geometry and mass data to standard Metric (1.0 m, 1.0 kg).")
                    
                self.refresh_ui()
                self.update_plots()
                QMessageBox.information(self, "Success", f"Successfully imported {os.path.basename(file_path)}")
            except Exception as e:
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"Failed to import Mass file:\n{str(e)}")

    def export_mass_file(self):
        options = QFileDialog.Options()
        default_path = os.path.join(self.last_directory, f"{self.plane.name.replace(' ','_')}.mass") if self.last_directory else f"{self.plane.name.replace(' ','_')}.mass"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Mass File", default_path, "Mass Files (*.mass)", options=options)
        if file_path:
            self.last_directory = os.path.dirname(file_path)
            try:
                self.plane.to_mass_file(file_path)
                QMessageBox.information(self, "Success", f"Successfully exported mass data to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def save_project(self):
        self.plane.description = self.txt_notes.toPlainText()
        options = QFileDialog.Options()
        default_path = os.path.join(self.last_directory, f"{self.plane.name.replace(' ','_')}_project.json") if self.last_directory else f"{self.plane.name.replace(' ','_')}_project.json"
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Project", default_path, "JSON Files (*.json)", options=options)
        if not filepath: return
        self.last_directory = os.path.dirname(filepath)
        try:
            data = asdict(self.plane)
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=4)
            QMessageBox.information(self, "Success", f"Project saved to {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project:\n{str(e)}")

    def load_project(self):
        options = QFileDialog.Options()
        default_path = self.last_directory if self.last_directory else ""
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Project", default_path, "JSON Files (*.json)", options=options)
        if not filepath: return
        self.last_directory = os.path.dirname(filepath)
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            surfaces = []
            for surf_data in data.get('surfaces', []):
                sections = []
                for sec_data in surf_data.get('sections', []):
                    ctrl_data = sec_data.get('control')
                    if ctrl_data:
                        ctrl = ControlSurface(**ctrl_data)
                        sec_data['control'] = ctrl
                    sections.append(Section(**sec_data))
                surf_data['sections'] = sections
                surfaces.append(Surface(**surf_data))
            
            point_masses = [PointMass(**pm) for pm in data.get('point_masses', [])]
                
            self.plane = Airplane(
                name=data.get('name', 'Imported Airplane'),
                description=data.get('description', ''),
                s_ref=data.get('s_ref', 1.0),
                c_ref=data.get('c_ref', 1.0),
                b_ref=data.get('b_ref', 1.0),
                cg=tuple(data.get('cg', (0.0, 0.0, 0.0))),
                surfaces=surfaces,
                point_masses=point_masses
            )
            self.txt_notes.setPlainText(self.plane.description)
            self.current_surface_idx = 0
            self.refresh_ui()
            self.refresh_surface_ui()
            self.refresh_mass_table()
            self.update_plots()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load project:\n{str(e)}")

    def update_plots(self):
        self.plot_3d()
        self.plot_blueprint()
        self.update_raw_text()

    def update_raw_text(self):
        try:
            self.text_avl.setPlainText(self.plane.to_avl_string())
            self.text_mass.setPlainText(self.plane.to_mass_string())
        except Exception as e:
            self.text_avl.setPlainText(f"Error generating text: {e}")

    def set_3d_view(self, elev, azim):
        self.canvas_3d.ax.view_init(elev=elev, azim=azim)
        self.canvas_3d.draw()

    def plot_3d(self):
        elev = getattr(self.canvas_3d.ax, 'elev', 25)
        azim = getattr(self.canvas_3d.ax, 'azim', -45)
        
        self.canvas_3d.ax.cla()
        self.canvas_3d.ax.set_axis_off()
        bg_plot = '#000000' if getattr(self, 'dark_mode', False) else '#FFFFFF'
        self.canvas_3d.ax.set_facecolor(bg_plot)
        self.canvas_3d.fig.patch.set_facecolor(bg_plot)
        
        colors = ['#0071E3', '#34C759', '#FF9500', '#AF52DE']

        for idx, surf in enumerate(self.plane.surfaces):
            c = colors[idx % len(colors)]
            mesh = surf.generate_3d_mesh()
            sides = [1, -1] if surf.duplicate_y else [1]
            for side in sides:
                for i in range(len(mesh)-1):
                    s1 = mesh[i]
                    s2 = mesh[i+1]
                    
                    x = [s1["x_le"], s1["x_te"], s2["x_te"], s2["x_le"]]
                    y = [s1["y"]*side, s1["y"]*side, s2["y"]*side, s2["y"]*side]
                    z = [s1["z_le"], s1["z_te"], s2["z_te"], s2["z_le"]]
                    
                    # Ensure auto-scaling bounds
                    self.canvas_3d.ax.plot(x + [x[0]], y + [y[0]], z + [z[0]], color='none')
                    
                    render_style = getattr(self, 'combo_render_style', None)
                    style_txt = render_style.currentText() if render_style else "Solid Shaded"
                    
                    if style_txt == "Wireframe":
                        self.canvas_3d.ax.plot(x + [x[0]], y + [y[0]], z + [z[0]], color=c, linewidth=1.5, alpha=0.9)
                        if s1["ctrl_name"] and s1["ctrl_name"] == s2["ctrl_name"]:
                            cx = [s1["x_hinge"], s1["x_te"], s2["x_te"], s2["x_hinge"], s1["x_hinge"]]
                            cy = [s1["y"]*side, s1["y"]*side, s2["y"]*side, s2["y"]*side, s1["y"]*side]
                            cz = [s1["z_hinge"], s1["z_te"], s2["z_te"], s2["z_hinge"], s1["z_hinge"]]
                            self.canvas_3d.ax.plot(cx, cy, cz, color='#FF3B30', linewidth=2.0)
                    else:
                        alpha = 0.1 if style_txt == "Ghost (Transparent)" else 0.5
                        edge = c if style_txt == "Ghost (Transparent)" else '#1D1D1F'
                        verts = [list(zip(x, y, z))]
                        poly = Poly3DCollection(verts, alpha=alpha, facecolor=c, edgecolors=edge, linewidths=0.8)
                        self.canvas_3d.ax.add_collection3d(poly)
                        
                        if s1["ctrl_name"] and s1["ctrl_name"] == s2["ctrl_name"]:
                            cx = [s1["x_hinge"], s1["x_te"], s2["x_te"], s2["x_hinge"]]
                            cy = [s1["y"]*side, s1["y"]*side, s2["y"]*side, s2["y"]*side]
                            cz = [s1["z_hinge"]+0.002, s1["z_te"]+0.002, s2["z_te"]+0.002, s2["z_hinge"]+0.002]
                            
                            cverts = [list(zip(cx, cy, cz))]
                            c_alpha = 0.2 if style_txt == "Ghost (Transparent)" else 0.9
                            c_edge = '#FF3B30' if style_txt == "Ghost (Transparent)" else '#1D1D1F'
                            cpoly = Poly3DCollection(cverts, alpha=c_alpha, facecolor='#FF3B30', edgecolors=c_edge, linewidths=0.8)
                            self.canvas_3d.ax.add_collection3d(cpoly)

        if self.plane.point_masses and self.left_tabs.currentIndex() == 1:
            mx = [m.x for m in self.plane.point_masses]
            my = [m.y for m in self.plane.point_masses]
            mz = [m.z for m in self.plane.point_masses]
            self.canvas_3d.ax.scatter(mx, my, mz, color='#0071E3', s=60, marker='o', alpha=0.9)
            
            text_c = '#E2E8F0' if getattr(self, 'dark_mode', False) else '#1E293B'
            bg_c = '#1E293B' if getattr(self, 'dark_mode', False) else '#F8FAFC'
            border_c = '#334155' if getattr(self, 'dark_mode', False) else '#CBD5E1'
            
            for m in self.plane.point_masses:
                self.canvas_3d.ax.text(m.x, m.y, m.z + 0.05, f" {m.name} ", color=text_c, fontsize=8, 
                                       fontweight='bold', fontfamily='monospace',
                                       bbox=dict(facecolor=bg_c, edgecolor=border_c, alpha=0.8, boxstyle='round,pad=0.3'))
                
            cg = self.plane.calculate_cg()
            self.canvas_3d.ax.scatter([cg[0]], [cg[1]], [cg[2]], color='#FF3B30', s=120, marker='X')
            self.canvas_3d.ax.text(cg[0], cg[1], cg[2] + 0.05, " CG ", color='#FFFFFF', fontsize=9, fontweight='bold', fontfamily='monospace',
                                   bbox=dict(facecolor='#EF4444', edgecolor='none', alpha=0.9, boxstyle='round,pad=0.3'))

        # Auto-scale view elegantly
        self.canvas_3d.ax.set_box_aspect([1, 1, 1])
        try:
            self.canvas_3d.ax.set_aspect('equal')
        except:
            pass
        self.canvas_3d.ax.view_init(elev=elev, azim=azim)
        self.canvas_3d.draw()

    def plot_blueprint(self):
        text_c = '#F5F5F7' if getattr(self, 'dark_mode', False) else '#1D1D1F'
        dim_c = '#86868B'
        border_c = '#38383A' if getattr(self, 'dark_mode', False) else '#D2D2D7'
        grid_c = '#38383A' if getattr(self, 'dark_mode', False) else '#E5E5EA'
        bg_plot = '#000000' if getattr(self, 'dark_mode', False) else '#FFFFFF'
        self.canvas_bp.fig.patch.set_facecolor(bg_plot)
        
        for ax in [self.canvas_bp.ax_top, self.canvas_bp.ax_front, self.canvas_bp.ax_side]:
            ax.cla()
            ax.set_facecolor(bg_plot)
            ax.tick_params(colors=dim_c, labelsize=9)
            for spine in ax.spines.values():
                spine.set_edgecolor(border_c)
            ax.grid(True, color=grid_c, linestyle='-')
            ax.axhline(0, color=border_c, lw=1, ls='-.')
            ax.axvline(0, color=border_c, lw=1, ls='-.')

        self.canvas_bp.ax_top.set_title("TOP VIEW", color=text_c, fontsize=10, weight='bold')
        self.canvas_bp.ax_front.set_title("FRONT VIEW", color=text_c, fontsize=10, weight='bold')
        self.canvas_bp.ax_side.set_title("SIDE VIEW", color=text_c, fontsize=10, weight='bold')

        for surf in self.plane.surfaces:
            mesh = surf.generate_3d_mesh()
            sides = [1, -1] if surf.duplicate_y else [1]
            for side in sides:
                for i in range(len(mesh)-1):
                    s1 = mesh[i]
                    s2 = mesh[i+1]
                    
                    yp = [s1["y"]*side, s2["y"]*side, s2["y"]*side, s1["y"]*side]
                    
                    # Top View (Y, X)
                    xp = [s1["x_le"], s2["x_le"], s2["x_te"], s1["x_te"]]
                    self.canvas_bp.ax_top.plot(yp + [yp[0]], xp + [xp[0]], color='none') # For autoscaling
                    self.canvas_bp.ax_top.add_patch(Polygon(list(zip(yp, xp)), facecolor='#0071E3', edgecolor='#1D1D1F', alpha=0.5, linewidth=0.8))
                    
                    if s1["ctrl_name"] and s1["ctrl_name"] == s2["ctrl_name"]:
                        cx = [s1["x_hinge"], s2["x_hinge"], s2["x_te"], s1["x_te"]]
                        self.canvas_bp.ax_top.add_patch(Polygon(list(zip(yp, cx)), facecolor='#FF3B30', edgecolor='#1D1D1F', alpha=0.9, linewidth=0.8, hatch='////'))
                        
                    # Front View (Y, Z)
                    zp_f = [s1["z_le"], s2["z_le"], s2["z_te"], s1["z_te"]]
                    self.canvas_bp.ax_front.plot(yp + [yp[0]], zp_f + [zp_f[0]], color='none')
                    self.canvas_bp.ax_front.add_patch(Polygon(list(zip(yp, zp_f)), facecolor='#0071E3', edgecolor='#1D1D1F', alpha=0.5, linewidth=0.8))
                    
                    if s1["ctrl_name"] and s1["ctrl_name"] == s2["ctrl_name"]:
                        cz_f = [s1["z_hinge"], s2["z_hinge"], s2["z_te"], s1["z_te"]]
                        self.canvas_bp.ax_front.add_patch(Polygon(list(zip(yp, cz_f)), facecolor='#FF3B30', edgecolor='#1D1D1F', alpha=0.9, linewidth=0.8, hatch='////'))
                    
                    # Side View (X, Z)
                    self.canvas_bp.ax_side.plot(xp + [xp[0]], zp_f + [zp_f[0]], color='none')
                    self.canvas_bp.ax_side.add_patch(Polygon(list(zip(xp, zp_f)), facecolor='#0071E3', edgecolor='#1D1D1F', alpha=0.5, linewidth=0.8))
                    
                    if s1["ctrl_name"] and s1["ctrl_name"] == s2["ctrl_name"]:
                        self.canvas_bp.ax_side.add_patch(Polygon(list(zip(cx, cz_f)), facecolor='#FF3B30', edgecolor='#1D1D1F', alpha=0.9, linewidth=0.8, hatch='////'))

        if self.plane.point_masses and self.left_tabs.currentIndex() == 1:
            cg = self.plane.calculate_cg()
            self.canvas_bp.ax_top.scatter([cg[1]], [cg[0]], color='#FF3B30', s=80, marker='X')
            self.canvas_bp.ax_front.scatter([cg[1]], [cg[2]], color='#FF3B30', s=80, marker='X')
            self.canvas_bp.ax_side.scatter([cg[0]], [cg[2]], color='#FF3B30', s=80, marker='X')
            self.canvas_bp.ax_top.text(cg[1], cg[0] + 0.05, "CG", color='#FF3B30', fontsize=9, fontweight='bold')
            
            for m in self.plane.point_masses:
                self.canvas_bp.ax_top.scatter([m.y], [m.x], color='#0071E3', s=40, marker='o')
                self.canvas_bp.ax_front.scatter([m.y], [m.z], color='#0071E3', s=40, marker='o')
                self.canvas_bp.ax_side.scatter([m.x], [m.z], color='#0071E3', s=40, marker='o')
                self.canvas_bp.ax_top.text(m.y, m.x - 0.05, m.name, color=text_c, fontsize=8)

        self.canvas_bp.ax_top.invert_yaxis()
        self.canvas_bp.ax_side.invert_xaxis()
        self.canvas_bp.ax_top.set_aspect('equal')
        self.canvas_bp.ax_front.set_aspect('equal')
        self.canvas_bp.ax_side.set_aspect('equal')
        self.canvas_bp.fig.tight_layout(pad=2.0)
        self.canvas_bp.draw()



class OutputReaderThread(QThread):
    new_output = pyqtSignal(str)

    def __init__(self, process):
        super().__init__()
        self.process = process

    def run(self):
        while True:
            char = self.process.stdout.read(1)
            if not char:
                break
            self.new_output.emit(char)

class HistoryLineEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.history = []
        self.history_idx = 0

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            if self.history and self.history_idx > 0:
                self.history_idx -= 1
                self.setText(self.history[self.history_idx])
        elif event.key() == Qt.Key_Down:
            if self.history and self.history_idx < len(self.history) - 1:
                self.history_idx += 1
                self.setText(self.history[self.history_idx])
            elif self.history_idx == len(self.history) - 1:
                self.history_idx += 1
                self.clear()
        else:
            super().keyPressEvent(event)

    def append_history(self, text):
        if text and (not self.history or self.history[-1] != text):
            self.history.append(text)
        self.history_idx = len(self.history)

class AVLTerminal(QWidget):
    def __init__(self, main_app=None, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.process = None
        
        lay = QVBoxLayout(self)
        
        btn_start = QPushButton("Start AVL Session")
        btn_start.setObjectName("success_btn")
        btn_start.setStyleSheet("padding: 10px; font-weight: bold; font-size: 14px;")
        btn_start.clicked.connect(self.start_avl)
        
        self.display = QPlainTextEdit()
        self.display.setReadOnly(True)
        self.display.setObjectName("terminal_display")
        self.display.setStyleSheet("QPlainTextEdit#terminal_display { font-family: Consolas, monospace; background-color: #0C0C0C; color: #CCCCCC; font-size: 13px; border: 1px solid #333333; padding: 5px; }")
        
        self.input = HistoryLineEdit()
        self.input.setObjectName("terminal_input")
        self.input.setStyleSheet("QLineEdit#terminal_input { font-family: Consolas, monospace; background-color: #0C0C0C; color: #CCCCCC; font-size: 14px; border: 1px solid #333333; padding: 5px; }")
        self.input.setPlaceholderText("Type AVL command here and press Enter...")
        self.input.returnPressed.connect(self.send_command)
        
        lay.addWidget(btn_start)
        lay.addWidget(self.display)
        lay.addWidget(self.input)
        
    def start_avl(self):
        if self.process:
            self.process.kill()
            self.display.appendPlainText("\n--- Restarting AVL Session ---\n")
            
        base_dir = os.path.dirname(os.path.abspath(__file__))
        avl_exe = os.path.join(base_dir, "avl.exe")
        
        if not os.path.exists(avl_exe):
            self.display.appendPlainText("Error: avl.exe not found in directory!")
            return
            
        if self.main_app and hasattr(self.main_app, 'plane'):
            with open(os.path.join(base_dir, "plane.avl"), "w") as f:
                f.write(self.main_app.plane.to_avl_string())
            with open(os.path.join(base_dir, "plane.mass"), "w") as f:
                f.write(self.main_app.plane.to_mass_string())
            
        self.process = subprocess.Popen(
            [avl_exe],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=base_dir,
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        self.reader = OutputReaderThread(self.process)
        self.reader.new_output.connect(self.append_text)
        self.reader.start()
        self.input.setFocus()
        
    def append_text(self, text):
        self.display.moveCursor(QTextCursor.End)
        self.display.insertPlainText(text)
        self.display.verticalScrollBar().setValue(self.display.verticalScrollBar().maximum())
        
    def send_command(self):
        if self.process and self.process.poll() is None:
            raw_cmd = self.input.text()
            self.input.append_history(raw_cmd)
            cmd = raw_cmd + "\n"
            self.process.stdin.write(cmd)
            self.process.stdin.flush()
            self.display.moveCursor(QTextCursor.End)
            
            self.display.insertPlainText(cmd)
            self.input.clear()

if __name__ == "__main__":
    try:
        import ctypes
        myappid = 'avl.design.studio.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setWindowIcon(QIcon("icon.png"))
    window = AVLDesktopApp()
    window.show()
    sys.exit(app.exec_())
