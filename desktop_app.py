import sys
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QLabel, QSplitter, QHeaderView,
                             QTabWidget, QComboBox, QLineEdit, QCheckBox, 
                             QGridLayout, QFileDialog, QMessageBox, QGroupBox, QPlainTextEdit)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QColor, QFont
import os
import subprocess
import json
from dataclasses import asdict
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.patches import Polygon

from geometry_engine import Airplane, Surface, Section, ControlSurface, PointMass
from avl_runner import run_avl_analysis

class Mpl3DCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=120):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.fig.patch.set_facecolor('#FFFFFF')
        self.fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.ax.set_facecolor('#FFFFFF')
        # Pure CAD look - hide axis completely
        self.ax.set_axis_off()
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

class AVLDesktopApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AVL Design Studio")
        self.resize(1400, 900)
        
        self.init_data_model()

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)
        

        
        top_bar = QHBoxLayout()
        btn_load = QPushButton("Load Project")
        btn_save = QPushButton("Save Project")
        chk_dark = QCheckBox("Dark Mode")
        chk_dark.setChecked(True)
        
        btn_load.clicked.connect(self.load_project)
        btn_save.clicked.connect(self.save_project)
        chk_dark.stateChanged.connect(lambda state: self.apply_theme(state == Qt.Checked))
        
        top_bar.addWidget(btn_load)
        top_bar.addWidget(btn_save)
        top_bar.addStretch()
        top_bar.addWidget(chk_dark)
        
        main_layout.addLayout(top_bar)
        
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)
        
        self.left_tabs = QTabWidget()
        self.setup_geometry_tab()
        self.setup_mass_tab()
        self.left_tabs.currentChanged.connect(lambda _: self.update_plots())
        splitter.addWidget(self.left_tabs)

        self.right_tabs = QTabWidget()
        
        # 3D View Tab with options
        view_3d_tab = QWidget()
        view_3d_lay = QVBoxLayout(view_3d_tab)
        
        toolbar_3d = QHBoxLayout()
        toolbar_3d.addWidget(QLabel("Render Style:"))
        self.combo_render_style = QComboBox()
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
            
        btn_iso.clicked.connect(lambda: self.set_3d_view(25, -125))
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
        
        self.terminal_tab = AVLTerminal(main_app=self)
        self.right_tabs.addTab(self.terminal_tab, "  AVL Terminal  ")
        
        splitter.addWidget(self.right_tabs)
        
        splitter.setSizes([450, 950])
        self.apply_theme(dark_mode=True)
        self.refresh_ui()

    def apply_theme(self, dark_mode=False):
        self.dark_mode = dark_mode
        if dark_mode:
            bg_main = "#1C1C1E"
            bg_card = "#2C2C2E"
            border = "#38383A"
            text_c = "#F5F5F7"
            text_dim = "#86868B"
            accent = "#0A84FF"
        else:
            bg_main = "#F5F5F7"
            bg_card = "#FFFFFF"
            border = "#D2D2D7"
            text_c = "#1D1D1F"
            text_dim = "#86868B"
            accent = "#0071E3"
            
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {bg_main}; color: {text_c}; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
            QWidget {{ color: {text_c}; font-size: 13px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
            QMessageBox {{ background-color: {bg_card}; color: {text_c}; }}
            QMessageBox QLabel {{ color: {text_c}; background-color: transparent; }}
            QTabWidget::pane {{ border: 1px solid {border}; background-color: {bg_card}; border-radius: 8px; top: -1px; }}
            QTabBar:focus {{ outline: none; }}
            QTabBar::tab {{ background: {bg_main}; padding: 6px 12px; border: 1px solid {border}; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; outline: none; color: {text_dim}; font-weight: bold; }}
            QTabBar::tab:selected {{ background: {bg_card}; border-bottom-color: {bg_card}; color: {text_c}; font-weight: bold; }}
            QTableWidget, QTableView {{ background-color: {bg_card}; alternate-background-color: {bg_main}; color: {text_c}; gridline-color: {border}; border: 1px solid {border}; border-radius: 6px; selection-background-color: {accent}; selection-color: white; outline: none; }}
            QTableView::item {{ background-color: {bg_card}; border: none; padding: 2px; }}
            QTableView::item:alternate {{ background-color: {bg_main}; }}
            QTableView::item:selected {{ background-color: {accent}; color: white; }}
            QTableWidget::item:focus {{ outline: none; }}
            QTableCornerButton::section {{ background-color: {bg_main}; border: none; border-bottom: 1px solid {border}; border-right: 1px solid {border}; }}
            QHeaderView, QHeaderView::section {{ background-color: {bg_main}; padding: 4px; border: none; border-bottom: 1px solid {border}; border-right: 1px solid {border}; font-weight: 600; color: {text_c}; outline: none; }}
            QLineEdit, QComboBox {{ background-color: {bg_card}; border: 1px solid {border}; padding: 6px 10px; border-radius: 6px; selection-background-color: {accent}; color: {text_c}; min-height: 22px; }}
            QComboBox QAbstractItemView {{ background-color: {bg_card}; color: {text_c}; border: 1px solid {border}; selection-background-color: {accent}; border-radius: 6px; }}
            QLineEdit:focus, QComboBox:focus {{ border: 1.5px solid {accent}; }}
            QPushButton {{ background-color: {bg_card}; color: {text_c}; padding: 6px 14px; border-radius: 6px; font-weight: 600; border: 1px solid {border}; outline: none; }}
            QPushButton:hover {{ background-color: {border}; }}
            QPushButton:pressed {{ background-color: {bg_main}; }}
            QPushButton#primary_btn {{ background-color: {accent}; color: white; border: none; }}
            QPushButton#primary_btn:hover {{ background-color: #0077ED; }}
            QPushButton#danger_btn {{ background-color: #FF3B30; color: white; border: none; }}
            QPushButton#danger_btn:hover {{ background-color: #FF453A; }}
            QPushButton#success_btn {{ background-color: #34C759; color: white; border: none; }}
            QPushButton#success_btn:hover {{ background-color: #30D158; }}
            QGroupBox {{ border: 1px solid {border}; border-radius: 8px; margin-top: 14px; font-weight: 600; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {text_dim}; }}
            QSplitter::handle {{ background-color: {border}; width: 1px; }}
            QPlainTextEdit {{ background-color: {bg_card}; color: {text_c}; font-family: "SF Mono", Consolas, monospace; font-size: 13px; border: 1px solid {border}; outline: none; border-radius: 6px; padding: 6px; }}
        """)
        
        if hasattr(self, 'canvas_3d'):
            self.canvas_3d.fig.patch.set_facecolor(bg_card)
            self.canvas_3d.ax.set_facecolor(bg_card)
            self.canvas_bp.fig.patch.set_facecolor(bg_card)
            for ax in [self.canvas_bp.ax_top, self.canvas_bp.ax_front, self.canvas_bp.ax_side]:
                ax.set_facecolor(bg_card)
            self.update_plots()

    def init_data_model(self):
        self.plane = Airplane(
            name="Shark Hawk Concept",
            surfaces=[
                Surface(
                    name="Main Wing", origin=(0.0, 0.0, 0.0), incidence=1.5,
                    sections=[
                        Section(y=0.0, chord=0.3, airfoil="NACA 2412", control=ControlSurface("Aileron", 0.75, -1)),
                        Section(y=1.0, chord=0.15, offset_x=0.05, twist=-2.0, dihedral=3.0, airfoil="NACA 2412", control=ControlSurface("Aileron", 0.75, -1))
                    ]
                ),
                Surface(
                    name="H-Tail", origin=(1.2, 0.0, 0.0), incidence=-1.0,
                    sections=[
                        Section(y=0.0, chord=0.1, airfoil="NACA 0012", control=ControlSurface("Elevator", 0.7, 1)),
                        Section(y=0.3, chord=0.08, offset_x=0.02, airfoil="NACA 0012")
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
        geom_widget = QWidget()
        lay = QVBoxLayout(geom_widget)
        lay.setContentsMargins(15, 15, 15, 15)
        
        ref_grp = QGroupBox("Airplane Reference")
        ref_lay = QGridLayout(ref_grp)
        self.edit_name = QLineEdit()
        self.edit_sref = QLineEdit()
        self.edit_cref = QLineEdit()
        self.edit_bref = QLineEdit()
        
        for e in [self.edit_name, self.edit_sref, self.edit_cref, self.edit_bref]:
            e.textChanged.connect(self.update_plane_refs)
        
        ref_lay.addWidget(QLabel("Name:"), 0, 0)
        ref_lay.addWidget(self.edit_name, 0, 1, 1, 3)
        ref_lay.addWidget(QLabel("S_ref:"), 1, 0)
        ref_lay.addWidget(self.edit_sref, 1, 1)
        ref_lay.addWidget(QLabel("C_ref:"), 1, 2)
        ref_lay.addWidget(self.edit_cref, 1, 3)
        ref_lay.addWidget(QLabel("B_ref:"), 2, 0)
        ref_lay.addWidget(self.edit_bref, 2, 1)
        lay.addWidget(ref_grp)

        surf_grp = QGroupBox("Surface Editor")
        surf_lay = QVBoxLayout(surf_grp)
        
        top_h = QHBoxLayout()
        self.combo_surf = QComboBox()
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
        self.chk_dup = QCheckBox("Y-Duplicate (Symmetric)")
        
        for e in [self.edit_surf_name, self.edit_ox, self.edit_oy, self.edit_oz, self.edit_inc]:
            e.textChanged.connect(self.update_surface_props)
        self.chk_dup.stateChanged.connect(self.update_surface_props)
        
        props_lay.addWidget(QLabel("Name:"), 0, 0)
        props_lay.addWidget(self.edit_surf_name, 0, 1, 1, 3)
        props_lay.addWidget(QLabel("Origin X:"), 1, 0)
        props_lay.addWidget(self.edit_ox, 1, 1)
        props_lay.addWidget(QLabel("Origin Y:"), 1, 2)
        props_lay.addWidget(self.edit_oy, 1, 3)
        props_lay.addWidget(QLabel("Origin Z:"), 2, 0)
        props_lay.addWidget(self.edit_oz, 2, 1)
        props_lay.addWidget(QLabel("Incidence:"), 2, 2)
        props_lay.addWidget(self.edit_inc, 2, 3)
        props_lay.addWidget(self.chk_dup, 3, 0, 1, 4)
        surf_lay.addLayout(props_lay)
        
        surf_lay.addWidget(QLabel("Sections Data"))
        self.sec_table = QTableWidget(0, 9)
        self.sec_table.setHorizontalHeaderLabels(["Y", "Chord", "Off_X", "Dihed", "Twist", "Airfoil", "Ctrl", "Hinge", "CSym"])
        self.sec_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sec_table.horizontalHeader().setMinimumHeight(40)
        self.sec_table.verticalHeader().setDefaultSectionSize(36)
        self.sec_table.verticalHeader().setMinimumWidth(35)
        self.sec_table.setAlternatingRowColors(True)
        self.sec_table.itemChanged.connect(self.on_section_table_changed)
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
        
        btn_export = QPushButton("Export Geometry (.avl)")
        btn_export.setObjectName("success_btn")
        btn_export.clicked.connect(self.export_geom_file)
        lay.addWidget(btn_export)
        
        self.left_tabs.addTab(geom_widget, "  Geometry  ")

    def setup_mass_tab(self):
        mass_widget = QWidget()
        lay = QVBoxLayout(mass_widget)
        lay.setContentsMargins(15, 15, 15, 15)
        
        lay.addWidget(QLabel("Point Masses"))
        self.mass_table = QTableWidget(0, 5)
        self.mass_table.setHorizontalHeaderLabels(["Name", "Mass", "X", "Y", "Z"])
        self.mass_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mass_table.horizontalHeader().setMinimumHeight(40)
        self.mass_table.verticalHeader().setDefaultSectionSize(36)
        self.mass_table.verticalHeader().setMinimumWidth(35)
        self.mass_table.setAlternatingRowColors(True)
        self.mass_table.itemChanged.connect(self.on_mass_table_changed)
        lay.addWidget(self.mass_table)
        
        mass_btn_lay = QHBoxLayout()
        btn_add = QPushButton("Add Point Mass")
        btn_add.clicked.connect(self.add_mass)
        btn_del = QPushButton("Del Point Mass")
        btn_del.setStyleSheet("background-color: #FF3B30;")
        btn_del.clicked.connect(self.del_mass)
        mass_btn_lay.addWidget(btn_add)
        mass_btn_lay.addWidget(btn_del)
        lay.addLayout(mass_btn_lay)
        
        self.lbl_cg = QLabel("CG: (0.0, 0.0, 0.0)")
        self.lbl_cg.setStyleSheet("font-size: 15px; font-weight: bold; margin-top: 15px;")
        lay.addWidget(self.lbl_cg)
        
        btn_export_mass = QPushButton("Export Mass (.mass)")
        btn_export_mass.setStyleSheet("background-color: #34C759; padding: 10px; font-size: 14px; margin-top: 10px;")
        btn_export_mass.clicked.connect(self.export_mass_file)
        lay.addWidget(btn_export_mass)
        
        self.left_tabs.addTab(mass_widget, "  Mass & Inertia  ")

    def refresh_ui(self):
        self.edit_name.blockSignals(True)
        self.edit_sref.blockSignals(True)
        self.edit_cref.blockSignals(True)
        self.edit_bref.blockSignals(True)
        self.combo_surf.blockSignals(True)
        
        self.edit_name.setText(self.plane.name)
        self.edit_sref.setText(str(self.plane.s_ref))
        self.edit_cref.setText(str(self.plane.c_ref))
        self.edit_bref.setText(str(self.plane.b_ref))
        
        self.combo_surf.clear()
        for s in self.plane.surfaces:
            self.combo_surf.addItem(s.name)
        if self.plane.surfaces:
            self.combo_surf.setCurrentIndex(self.current_surface_idx)
            
        self.edit_name.blockSignals(False)
        self.edit_sref.blockSignals(False)
        self.edit_cref.blockSignals(False)
        self.edit_bref.blockSignals(False)
        self.combo_surf.blockSignals(False)
        
        self.refresh_surface_ui()
        self.refresh_mass_table()
        self.update_plots()

    def refresh_surface_ui(self):
        if not self.plane.surfaces: return
        surf = self.plane.surfaces[self.current_surface_idx]
        
        for e in [self.edit_surf_name, self.edit_ox, self.edit_oy, self.edit_oz, self.edit_inc, self.chk_dup]:
            e.blockSignals(True)
            
        self.edit_surf_name.setText(surf.name)
        self.edit_ox.setText(str(surf.origin[0]))
        self.edit_oy.setText(str(surf.origin[1]))
        self.edit_oz.setText(str(surf.origin[2]))
        self.edit_inc.setText(str(surf.incidence))
        self.chk_dup.setChecked(surf.duplicate_y)
        
        for e in [self.edit_surf_name, self.edit_ox, self.edit_oy, self.edit_oz, self.edit_inc, self.chk_dup]:
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
            self.sec_table.setItem(i, 3, create_centered_item(sec.dihedral))
            self.sec_table.setItem(i, 4, create_centered_item(sec.twist))
            self.sec_table.setItem(i, 5, create_centered_item(sec.airfoil))
            
            c_name = sec.control.name if sec.control else ""
            c_hinge = str(sec.control.hinge_x_c) if sec.control else ""
            c_sym = str(sec.control.sym) if sec.control else ""
            
            self.sec_table.setItem(i, 6, create_centered_item(c_name))
            self.sec_table.setItem(i, 7, create_centered_item(c_hinge))
            self.sec_table.setItem(i, 8, create_centered_item(c_sym))
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
            self.plane.s_ref = float(self.edit_sref.text())
            self.plane.c_ref = float(self.edit_cref.text())
            self.plane.b_ref = float(self.edit_bref.text())
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
            surf.duplicate_y = self.chk_dup.isChecked()
            self.update_plots()
        except ValueError:
            pass

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
            dih = get_f(3, old_sec.dihedral)
            twi = get_f(4, old_sec.twist)
            air = get_s(5, old_sec.airfoil)
            
            c_name = get_s(6, old_sec.control.name if old_sec.control else "", allow_empty=True)
            ctrl = None
            if c_name:
                h = get_f(7, old_sec.control.hinge_x_c if old_sec.control else 0.7)
                sym = int(get_f(8, old_sec.control.sym if old_sec.control else 1))
                ctrl = ControlSurface(name=c_name, hinge_x_c=h, sym=sym)
                if self.sec_table.item(i, 7): self.sec_table.item(i, 7).setText(str(h))
                if self.sec_table.item(i, 8): self.sec_table.item(i, 8).setText(str(sym))
            else:
                if self.sec_table.item(i, 7): self.sec_table.item(i, 7).setText("")
                if self.sec_table.item(i, 8): self.sec_table.item(i, 8).setText("")
                
            new_secs.append(Section(y=y, chord=c, offset_x=off, dihedral=dih, twist=twi, airfoil=air, control=ctrl))
            
            if self.sec_table.item(i, 0): self.sec_table.item(i, 0).setText(str(y))
            if self.sec_table.item(i, 1): self.sec_table.item(i, 1).setText(str(c))
            if self.sec_table.item(i, 2): self.sec_table.item(i, 2).setText(str(off))
            if self.sec_table.item(i, 3): self.sec_table.item(i, 3).setText(str(dih))
            if self.sec_table.item(i, 4): self.sec_table.item(i, 4).setText(str(twi))
            if self.sec_table.item(i, 5): self.sec_table.item(i, 5).setText(air)

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
        self.lbl_cg.setText(f"Total Mass: {total_mass:.3f} kg   |   CG: X={cg[0]:.3f}   Y={cg[1]:.3f}   Z={cg[2]:.3f}")

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

    def export_geom_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save AVL Geometry", f"{self.plane.name.replace(' ','_')}.avl", "AVL Files (*.avl)", options=options)
        if file_path:
            try:
                self.plane.to_avl_file(file_path)
                QMessageBox.information(self, "Success", f"Successfully exported geometry to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def export_mass_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Mass File", f"{self.plane.name.replace(' ','_')}.mass", "Mass Files (*.mass)", options=options)
        if file_path:
            try:
                self.plane.to_mass_file(file_path)
                QMessageBox.information(self, "Success", f"Successfully exported mass data to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def save_project(self):
        options = QFileDialog.Options()
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Project", f"{self.plane.name.replace(' ','_')}_project.json", "JSON Files (*.json)", options=options)
        if not filepath: return
        try:
            data = asdict(self.plane)
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=4)
            QMessageBox.information(self, "Success", f"Project saved to {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project:\n{str(e)}")

    def load_project(self):
        options = QFileDialog.Options()
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "JSON Files (*.json)", options=options)
        if not filepath: return
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
                s_ref=data.get('s_ref', 1.0),
                c_ref=data.get('c_ref', 1.0),
                b_ref=data.get('b_ref', 1.0),
                cg=tuple(data.get('cg', (0.0, 0.0, 0.0))),
                surfaces=surfaces,
                point_masses=point_masses
            )
            
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
        azim = getattr(self.canvas_3d.ax, 'azim', -125)
        
        self.canvas_3d.ax.cla()
        self.canvas_3d.ax.set_axis_off()
        bg_card = '#2C2C2E' if getattr(self, 'dark_mode', False) else '#FFFFFF'
        self.canvas_3d.ax.set_facecolor(bg_card)
        self.canvas_3d.fig.patch.set_facecolor(bg_card)
        
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
            
            text_c = '#F5F5F7' if getattr(self, 'dark_mode', False) else '#1D1D1F'
            for m in self.plane.point_masses:
                self.canvas_3d.ax.text(m.x, m.y, m.z + 0.05, m.name, color=text_c, fontsize=9, fontweight='bold')
                
            cg = self.plane.calculate_cg()
            self.canvas_3d.ax.scatter([cg[0]], [cg[1]], [cg[2]], color='#FF3B30', s=120, marker='X')
            self.canvas_3d.ax.text(cg[0], cg[1], cg[2] + 0.05, "CG", color='#FF3B30', fontsize=10, fontweight='bold')

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
        bg_card = '#2C2C2E' if getattr(self, 'dark_mode', False) else '#FFFFFF'
        
        for ax in [self.canvas_bp.ax_top, self.canvas_bp.ax_front, self.canvas_bp.ax_side]:
            ax.cla()
            ax.set_facecolor(bg_card)
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
        self.display.setStyleSheet("font-family: Consolas, monospace; background-color: #1E1E1E; color: #D4D4D4; font-size: 13px;")
        
        self.input = QLineEdit()
        self.input.setStyleSheet("font-family: Consolas, monospace; background-color: #1E1E1E; color: #FFFFFF; font-size: 14px; padding: 5px;")
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
            cmd = self.input.text() + "\n"
            self.process.stdin.write(cmd)
            self.process.stdin.flush()
            self.display.moveCursor(QTextCursor.End)
            
            # Apply cyan bold color for user input
            fmt = QTextCharFormat()
            fmt.setForeground(QColor("#00FFFF"))
            fmt.setFontWeight(QFont.Bold)
            self.display.setCurrentCharFormat(fmt)
            
            self.display.insertPlainText(cmd)
            
            # Revert to standard terminal text color for AVL output
            fmt = QTextCharFormat()
            fmt.setForeground(QColor("#D4D4D4"))
            fmt.setFontWeight(QFont.Normal)
            self.display.setCurrentCharFormat(fmt)
            
            self.input.clear()

if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = AVLDesktopApp()
    window.show()
    sys.exit(app.exec_())
