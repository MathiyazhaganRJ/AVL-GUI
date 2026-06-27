"""
AVL — Airplane Geometry, Design & Stability (RJ Aero)
Improved version: AVL export fixes, CG-based reference, valid SECTION format, code cleanups.
"""
import streamlit as st
import pandas as pd
import numpy as np
import io
import json
import subprocess
import os
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import matplotlib.gridspec as gridspec

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Airplane Geometry, Design & Stability", layout="wide", page_icon="✈️")

# --- 2. PLOT THEME ENGINE ---
if "plot_dark_mode" not in st.session_state:
    st.session_state["plot_dark_mode"] = True

# Top Right Toggle Container
top_container = st.container()
with top_container:
    col_head, col_toggle = st.columns([6, 1])

    with col_toggle:
        st.write("")
        st.write("")
        is_dark_plots = st.toggle("🎨 Dark Plots", value=st.session_state["plot_dark_mode"])
        st.session_state["plot_dark_mode"] = is_dark_plots

    # Define Plot Specific Colors
    if is_dark_plots:
        PLOT_BG = "#000000"
        AXIS_COLOR = "white"
        GRID_COLOR = "#333333"
    else:
        PLOT_BG = "#FFFFFF"
        AXIS_COLOR = "black"
        GRID_COLOR = "#E5E5E5"

    with col_head:
        st.markdown("""
        <div style="background-color:#111; padding:20px; border-radius:10px; border-bottom:5px solid #00AAFF; box-shadow: 0 4px 10px rgba(0,0,0,0.3); display:flex; justify-content:space-between; align-items:flex-end;">
            <div>
                <h1 style="color:#FFFF00; margin:0; font-size:40px; font-family:sans-serif;">AVL</h1>
                <p style="color:#00AAFF; margin:0;">Aerodynamic Analysis & Design</p>
            </div>
            <div style="text-align:right;">
                <h2 style="color:white; margin:0; font-style:italic;">RJ Aero</h2>
            </div>
        </div>
        """, unsafe_allow_html=True)

# --- 3. GLOBAL CSS ---
st.markdown(f"""
<style>
    .stApp {{ background-color: #FFFFFF !important; color: #000000 !important; }}

    .stTextInput input, .stNumberInput input, div[data-baseweb="select"] > div {{
        background-color: #F0F2F6 !important; color: #000000 !important; border: 1px solid #D3D3D3 !important;
    }}
    div[data-testid="stDataFrame"] {{ background-color: #F0F2F6 !important; border: 1px solid #D3D3D3; }}
    div[data-testid="stDataFrame"] div {{ color: #000000 !important; }}

    .viewer-container {{
        background-color: {PLOT_BG}; border-radius: 8px; padding: 0px; margin-bottom: 10px; border: none !important;
    }}

    div.stButton > button {{ width: 100%; border-radius: 6px; font-weight: 600; border: 1px solid #00AAFF; color: #00AAFF; background-color: transparent; }}
    div.stButton > button:hover {{ background-color: #00AAFF; color: white; }}
    [data-testid="stFormSubmitButton"] > button {{ background-color: #00AAFF !important; color: white !important; border: none !important; }}
    button[kind="primary"] {{ background-color: #32CD32 !important; color: black !important; border: none !important; }}

    .stTabs [data-baseweb="tab"] {{ font-weight: bold; font-size: 1.0rem; color: #000000 !important; }}
    .stTabs [aria-selected="true"] {{ color: #00AAFF !important; border-bottom-color: #00AAFF !important; }}

    [data-testid="stMetricLabel"] {{ color: #000000 !important; opacity: 0.8; }}
    [data-testid="stMetricValue"] {{ color: #00AAFF !important; font-family: 'Courier New', Courier, monospace !important; font-weight: 700; font-size: 1.2rem !important; }}
</style>
""", unsafe_allow_html=True)

# COLORS
C_SURFACE = '#32CD32'
C_CTRL    = '#FF4500'
C_MASS    = '#0000FF'
C_CG      = AXIS_COLOR
C_EDGE    = AXIS_COLOR

if os.name == 'nt':
    AVL_EXE = "avl.exe"
else:
    AVL_EXE = "./avl"

# Default Nspan/Sspace for SECTION (AVL: -2 = sine spacing)
DEFAULT_NSPAN = 5
DEFAULT_SSPACE = -2.0

# --- 4. INITIALIZATION ---
if "flight_data" not in st.session_state:
    st.session_state["flight_data"] = {
        "meta": {"name": "Concept_Plane"},
        "run": {"alpha": 0.0, "velocity": 15.0, "density": 1.225, "g": 9.81},
        "surfaces": {
            "Main Wing": {
                "origin": [0.0, 0.0, 0.0],
                "incidence": 0.0,
                "duplicate_y": True,
                "df": pd.DataFrame([
                    {"Y": 0.0, "Chord": 0.45, "Offset": 0.0, "Dihedral": 0.0, "Twist": 0.0, "Airfoil": "NACA 2412", "Ctrl": "", "Hinge": 0.0, "Sym": 0},
                    {"Y": 1.2, "Chord": 0.25, "Offset": 0.25, "Dihedral": 2.0, "Twist": 0.0, "Airfoil": "NACA 2412", "Ctrl": "Aileron", "Hinge": 0.75, "Sym": -1}
                ])
            },
            "H-Tail": {
                "origin": [1.8, 0.0, 0.0],
                "incidence": -2.0,
                "duplicate_y": True,
                "df": pd.DataFrame([
                    {"Y": 0.0, "Chord": 0.30, "Offset": 0.0, "Dihedral": 0.0, "Twist": 0.0, "Airfoil": "NACA 0012", "Ctrl": "", "Hinge": 0.0, "Sym": 0},
                    {"Y": 0.6, "Chord": 0.15, "Offset": 0.1, "Dihedral": 0.0, "Twist": 0.0, "Airfoil": "NACA 0012", "Ctrl": "Elevator", "Hinge": 0.7, "Sym": 1}
                ])
            },
            "V-Tail": {
                "origin": [1.8, 0.0, 0.0],
                "incidence": 0.0,
                "duplicate_y": False,
                "df": pd.DataFrame([
                    {"Y": 0.0, "Chord": 0.35, "Offset": 0.0, "Dihedral": 90.0, "Twist": 0.0, "Airfoil": "NACA 0012", "Ctrl": "", "Hinge": 0.0, "Sym": 0},
                    {"Y": 0.5, "Chord": 0.20, "Offset": 0.2, "Dihedral": 90.0, "Twist": 0.0, "Airfoil": "NACA 0012", "Ctrl": "Rudder", "Hinge": 0.7, "Sym": 1}
                ])
            }
        },
        "masses": pd.DataFrame([
            {"Name": "Fuselage", "Mass (kg)": 1.0, "X": 0.5, "Y": 0.0, "Z": 0.0},
            {"Name": "Motor", "Mass (kg)": 0.2, "X": -0.1, "Y": 0.0, "Z": 0.0},
            {"Name": "Battery", "Mass (kg)": 0.5, "X": 0.3, "Y": 0.0, "Z": 0.0}
        ]),
        "order": ["Main Wing", "H-Tail", "V-Tail"]
    }

# --- 5. MATH ENGINE ---
def clean_dataframe(df):
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)
    for col in ["Y", "Chord", "Offset", "Dihedral", "Twist", "Hinge", "Sym", "Mass (kg)", "X", "Z"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    for col in ["Ctrl", "Name"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)
    if "Airfoil" in df.columns:
        # Normalize and default airfoil input for UI table
        # - blank / NaN / None -> "NACA 0012"
        # - "NACA" (no digits) -> "NACA 0012"
        df["Airfoil"] = df["Airfoil"].fillna("").astype(str).map(lambda s: s.strip())
        def _norm_airfoil(s: str) -> str:
            sl = s.lower()
            if (not s) or sl in {"nan", "none"}:
                return "NACA 0012"
            if sl == "naca":
                return "NACA 0012"
            return s
        df["Airfoil"] = df["Airfoil"].map(_norm_airfoil)
    if "Y" in df.columns:
        df = df.sort_values("Y")
    return df


def _safe_float(val, default=0.0):
    """Coerce to float for AVL/geometry; use default if NaN or invalid."""
    try:
        f = float(val)
        return f if np.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def calculate_coords(surface_origin, df, incidence_angle):
    """Coordinates for visualization: applies surface incidence to (X,Z). Dihedral in geometry."""
    df = clean_dataframe(df)
    coords = []
    inc_rad = np.radians(_safe_float(incidence_angle))
    cos_inc = np.cos(inc_rad)
    sin_inc = np.sin(inc_rad)
    try:
        z_rel_accum = 0.0
        if len(df) > 0:
            row0 = df.iloc[0]
            y_rel = _safe_float(row0["Y"])
            x_rel = _safe_float(row0["Offset"])
            x_rot_abs = surface_origin[0] + x_rel * cos_inc - z_rel_accum * sin_inc
            z_rot_abs = surface_origin[2] + x_rel * sin_inc + z_rel_accum * cos_inc
            coords.append({"X": x_rot_abs, "Y": surface_origin[1] + y_rel, "Z": z_rot_abs, "Chord": _safe_float(row0["Chord"], 1.0), "Twist": _safe_float(row0["Twist"]), "Airfoil": str(row0["Airfoil"]), "Ctrl": str(row0["Ctrl"]), "Hinge": _safe_float(row0["Hinge"]), "Sym": int(_safe_float(row0["Sym"], 0))})
            prev_y = y_rel
            for i in range(1, len(df)):
                row = df.iloc[i]
                prev_row = df.iloc[i-1]
                d_span = _safe_float(row["Y"]) - prev_y
                prev_dihed = _safe_float(prev_row["Dihedral"])
                if abs(prev_dihed - 90.0) < 1.0:
                    dz_rel = d_span  # vertical: span step entirely in Z
                    y_rel = prev_y   # keep Y constant so segment is vertical (90°)
                else:
                    dz_rel = d_span * np.tan(np.radians(prev_dihed))
                    y_rel = _safe_float(row["Y"])
                prev_y = y_rel
                x_rel = _safe_float(row["Offset"])
                z_rel_accum += dz_rel
                x_rot_abs = surface_origin[0] + x_rel * cos_inc - z_rel_accum * sin_inc
                z_rot_abs = surface_origin[2] + x_rel * sin_inc + z_rel_accum * cos_inc
                coords.append({"X": x_rot_abs, "Y": surface_origin[1] + y_rel, "Z": z_rot_abs, "Chord": _safe_float(row["Chord"], 1.0), "Twist": _safe_float(row["Twist"]), "Airfoil": str(row["Airfoil"]), "Ctrl": str(row["Ctrl"]), "Hinge": _safe_float(row["Hinge"]), "Sym": int(_safe_float(row["Sym"], 0))})
    except Exception as e:
        st.error(f"Error in coordinate calculation: {e}")
    return pd.DataFrame(coords)


def calculate_coords_for_avl(surface_origin, df):
    """
    Reference (unrotated) section positions for AVL export.
    AVL: chord along X (TE = Xle+Chord, Yle, Zle). Dihedral is in (Xle,Yle,Zle).
    Total section incidence in AVL = surface ANGLE + section Ainc (twist).
    """
    df = clean_dataframe(df)
    coords = []
    try:
        z_rel_accum = 0.0
        if len(df) == 0:
            return pd.DataFrame(coords)
        row0 = df.iloc[0]
        y_rel = _safe_float(row0["Y"])
        x_rel = _safe_float(row0["Offset"])
        x_abs = surface_origin[0] + x_rel
        z_abs = surface_origin[2] + z_rel_accum
        coords.append({
            "X": x_abs, "Y": surface_origin[1] + y_rel, "Z": z_abs,
            "Chord": _safe_float(row0["Chord"], 1.0),
            "Twist": _safe_float(row0["Twist"]),
            "Airfoil": str(row0["Airfoil"]), "Ctrl": str(row0["Ctrl"]),
            "Hinge": _safe_float(row0["Hinge"]), "Sym": int(_safe_float(row0["Sym"], 0))
        })
        prev_y = y_rel
        for i in range(1, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            d_span = _safe_float(row["Y"]) - prev_y
            dihed_deg = _safe_float(prev_row["Dihedral"])
            if abs(dihed_deg - 90.0) < 1.0:
                dz_rel = d_span   # vertical: span step entirely in Z
                y_rel = prev_y   # keep Y constant so segment is vertical (90°)
            else:
                dz_rel = d_span * np.tan(np.radians(dihed_deg))
                y_rel = _safe_float(row["Y"])
            prev_y = y_rel
            x_rel = _safe_float(row["Offset"])
            z_rel_accum += dz_rel
            x_abs = surface_origin[0] + x_rel
            z_abs = surface_origin[2] + z_rel_accum
            coords.append({
                "X": x_abs, "Y": surface_origin[1] + y_rel, "Z": z_abs,
                "Chord": _safe_float(row["Chord"], 1.0),
                "Twist": _safe_float(row["Twist"]),
                "Airfoil": str(row["Airfoil"]), "Ctrl": str(row["Ctrl"]),
                "Hinge": _safe_float(row["Hinge"]), "Sym": int(_safe_float(row["Sym"], 0))
            })
    except Exception as e:
        st.error(f"Error in AVL coordinate calculation: {e}")
    return pd.DataFrame(coords)


def calculate_cg(mass_df):
    mass_df = clean_dataframe(mass_df)
    if mass_df.empty:
        return 0, [0, 0, 0]
    try:
        total_mass = mass_df["Mass (kg)"].sum()
        if total_mass == 0:
            return 0, [0, 0, 0]
        cg_x = (mass_df["Mass (kg)"] * mass_df["X"]).sum() / total_mass
        cg_y = (mass_df["Mass (kg)"] * mass_df["Y"]).sum() / total_mass
        cg_z = (mass_df["Mass (kg)"] * mass_df["Z"]).sum() / total_mass
        return total_mass, [cg_x, cg_y, cg_z]
    except Exception:
        return 0, [0, 0, 0]

def calculate_wing_metrics(data_dict):
    area = 0.0
    span = 0.0
    ar = 0.0
    target_surf = None
    if "Main Wing" in data_dict["surfaces"]:
        target_surf = data_dict["surfaces"]["Main Wing"]
    elif len(data_dict["order"]) > 0:
        target_surf = data_dict["surfaces"][data_dict["order"][0]]
    if target_surf:
        df = clean_dataframe(target_surf["df"])
        semi_area = 0.0
        max_y = 0.0
        try:
            for i in range(len(df) - 1):
                c_root = df.iloc[i]["Chord"]
                c_tip = df.iloc[i + 1]["Chord"]
                y_root = df.iloc[i]["Y"]
                y_tip = df.iloc[i + 1]["Y"]
                dy = abs(y_tip - y_root)
                semi_area += 0.5 * (c_root + c_tip) * dy
                max_y = max(max_y, y_tip)
            total_area = semi_area * 2
            total_span = max_y * 2
            if total_area > 0:
                ar = (total_span ** 2) / total_area
            return total_area, total_span, ar
        except Exception:
            return 0.0, 0.0, 0.0
    return 0.0, 0.0, 0.0

# --- 7. VISUALIZATION ENGINES ---
# Plotly 3D camera presets (eye x,y,z)
CAMERA_PRESETS = {
    "Default": dict(x=-1.5, y=-1.5, z=0.5),
    "Top": dict(x=0.1, y=0.1, z=2.0),
    "Front": dict(x=2.0, y=0.0, z=0.5),
    "Side": dict(x=0.0, y=2.0, z=0.5),
    "Isometric": dict(x=-1.2, y=-1.2, z=0.8),
}
# Matplotlib 3D view (elev, azim) in degrees
MPL_VIEW_PRESETS = {
    "Default": (25, -135),
    "Top": (90, 0),
    "Front": (0, 0),
    "Side": (0, 90),
    "Isometric": (30, -120),
}

def plot_3d(data_dict, show_mass=True, camera_eye=None):
    if camera_eye is None:
        camera_eye = CAMERA_PRESETS["Default"]
    fig = go.Figure()
    if st.session_state["plot_dark_mode"]:
        lighting = dict(ambient=0.7, diffuse=0.5, specular=0.3, roughness=0.5)
        bg = PLOT_BG
        grid_col = GRID_COLOR
    else:
        lighting = dict(ambient=1.0, diffuse=0.0, specular=0.0, roughness=1.0)
        bg = PLOT_BG
        grid_col = GRID_COLOR

    for name in st.session_state["flight_data"]["order"]:
        if name not in st.session_state["flight_data"]["surfaces"]:
            continue
        surf = st.session_state["flight_data"]["surfaces"][name]
        incidence = surf.get("incidence", 0.0)
        abs_df = calculate_coords(surf["origin"], surf["df"], incidence)
        if abs_df.empty:
            continue
        x = abs_df["X"].values
        y = abs_df["Y"].values
        z = abs_df["Z"].values
        c = abs_df["Chord"].values
        t_rad = np.radians(abs_df["Twist"].values)
        sides = [1] if not surf.get("duplicate_y", True) else [1, -1]
        for side in sides:
            y_mult = side
            for i in range(len(x) - 1):
                x_te_i = x[i] + c[i] * np.cos(t_rad[i])
                z_te_i = z[i] - c[i] * np.sin(t_rad[i])
                x_te_next = x[i + 1] + c[i + 1] * np.cos(t_rad[i + 1])
                z_te_next = z[i + 1] - c[i + 1] * np.sin(t_rad[i + 1])
                x_c = [x[i], x_te_i, x_te_next, x[i + 1]]
                y_c = [y[i] * y_mult, y[i] * y_mult, y[i + 1] * y_mult, y[i + 1] * y_mult]
                z_c = [z[i], z_te_i, z_te_next, z[i + 1]]
                if y_mult == 1:
                    i_idx, j_idx, k_idx = [0, 0], [1, 2], [2, 3]
                else:
                    i_idx, j_idx, k_idx = [0, 0], [3, 2], [2, 1]
                fig.add_trace(go.Mesh3d(x=x_c, y=y_c, z=z_c, i=i_idx, j=j_idx, k=k_idx, color=C_SURFACE, opacity=1.0, flatshading=True, showlegend=False, lighting=lighting, hoverinfo='skip'))
                z_wire = [v + 0.005 for v in z_c]
                fig.add_trace(go.Scatter3d(x=x_c + [x_c[0]], y=y_c + [y_c[0]], z=z_wire + [z_wire[0]], mode='lines', line=dict(color=C_EDGE, width=3), showlegend=False, hoverinfo='skip'))
                ctrl = str(abs_df.iloc[i + 1]["Ctrl"])
                hinge = abs_df.iloc[i + 1]["Hinge"]
                if len(ctrl) > 1 and ctrl.lower() != "nan":
                    x_h_i = x[i] + c[i] * hinge * np.cos(t_rad[i])
                    z_h_i = z[i] - c[i] * hinge * np.sin(t_rad[i])
                    x_h_next = x[i + 1] + c[i + 1] * hinge * np.cos(t_rad[i + 1])
                    z_h_next = z[i + 1] - c[i + 1] * hinge * np.sin(t_rad[i + 1])
                    cs_x = [x_h_i, x_te_i, x_te_next, x_h_next]
                    cs_y = [y[i] * y_mult, y[i] * y_mult, y[i + 1] * y_mult, y[i + 1] * y_mult]
                    cs_z = [z_h_i + 0.002, z_te_i + 0.002, z_te_next + 0.002, z_h_next + 0.002]
                    fig.add_trace(go.Mesh3d(x=cs_x, y=cs_y, z=cs_z, i=i_idx, j=j_idx, k=k_idx, color=C_CTRL, opacity=1.0, flatshading=True, name=ctrl, lighting=lighting))

    if show_mass and not data_dict["masses"].empty:
        m = clean_dataframe(data_dict["masses"])
        fig.add_trace(go.Scatter3d(x=m["X"], y=m["Y"], z=m["Z"], mode='markers', marker=dict(size=5, color=C_MASS), name="Mass"))
        total_m, cg = calculate_cg(m)
        fig.add_trace(go.Scatter3d(x=[cg[0]], y=[cg[1]], z=[cg[2]], mode='markers+text', marker=dict(size=12, color=C_CG, symbol='circle'), text=["CG"], name="CG", textfont=dict(color=AXIS_COLOR)))

    fig.update_layout(scene=dict(aspectmode='data', xaxis=dict(visible=False, backgroundcolor=bg, gridcolor=grid_col), yaxis=dict(visible=False, backgroundcolor=bg, gridcolor=grid_col), zaxis=dict(visible=False, backgroundcolor=bg, gridcolor=grid_col), bgcolor=bg, camera=dict(eye=camera_eye)), margin=dict(l=0, r=0, b=0, t=0), height=500, paper_bgcolor=bg, font=dict(color=AXIS_COLOR))
    return fig

def plot_3d_pyvista(data_dict, show_mass=True, view_preset="Default"):
    """PyVista/VTK 3D rendering (high-quality mesh). Requires: pip install pyvista. view_preset: Default, Top, Front, Side, Isometric."""
    try:
        import pyvista as pv
    except ImportError:
        st.warning("PyVista not installed. Install with: `pip install pyvista`")
        return None
    pv.set_plot_theme("dark" if st.session_state["plot_dark_mode"] else "default")
    plotter = pv.Plotter(off_screen=True, window_size=[800, 600])
    plotter.background_color = PLOT_BG if not st.session_state["plot_dark_mode"] else "#000000"
    for name in st.session_state["flight_data"]["order"]:
        if name not in st.session_state["flight_data"]["surfaces"]:
            continue
        surf = st.session_state["flight_data"]["surfaces"][name]
        abs_df = calculate_coords(surf["origin"], surf["df"], surf.get("incidence", 0.0))
        if abs_df.empty:
            continue
        x, y, z = abs_df["X"].values, abs_df["Y"].values, abs_df["Z"].values
        c = abs_df["Chord"].values
        t_rad = np.radians(abs_df["Twist"].values)
        sides = [1] if not surf.get("duplicate_y", True) else [1, -1]
        for y_mult in sides:
            for i in range(len(x) - 1):
                x_te_i = x[i] + c[i] * np.cos(t_rad[i])
                z_te_i = z[i] - c[i] * np.sin(t_rad[i])
                x_te_next = x[i + 1] + c[i + 1] * np.cos(t_rad[i + 1])
                z_te_next = z[i + 1] - c[i + 1] * np.sin(t_rad[i + 1])
                points = np.array([[x[i], y[i] * y_mult, z[i]], [x_te_i, y[i] * y_mult, z_te_i], [x_te_next, y[i + 1] * y_mult, z_te_next], [x[i + 1], y[i + 1] * y_mult, z[i + 1]]])
                face = [4, 0, 1, 2, 3]
                mesh = pv.PolyData(points, faces=face)
                plotter.add_mesh(mesh, color=C_SURFACE, show_edges=True, edge_color=C_EDGE, line_width=2)
                ctrl = str(abs_df.iloc[i + 1]["Ctrl"])
                hinge = abs_df.iloc[i + 1]["Hinge"]
                if len(ctrl) > 1 and ctrl.lower() != "nan":
                    x_h_i = x[i] + c[i] * hinge * np.cos(t_rad[i])
                    z_h_i = z[i] - c[i] * hinge * np.sin(t_rad[i])
                    x_h_next = x[i + 1] + c[i + 1] * hinge * np.cos(t_rad[i + 1])
                    z_h_next = z[i + 1] - c[i + 1] * hinge * np.sin(t_rad[i + 1])
                    cs_points = np.array([[x_h_i, y[i] * y_mult, z_h_i + 0.002], [x_te_i, y[i] * y_mult, z_te_i + 0.002], [x_te_next, y[i + 1] * y_mult, z_te_next + 0.002], [x_h_next, y[i + 1] * y_mult, z_h_next + 0.002]])
                    cs_mesh = pv.PolyData(cs_points, faces=face)
                    plotter.add_mesh(cs_mesh, color=C_CTRL, show_edges=True, edge_color=C_EDGE)
    if show_mass and not data_dict["masses"].empty:
        m = clean_dataframe(data_dict["masses"])
        mass_points = np.column_stack([m["X"], m["Y"], m["Z"]])
        plotter.add_mesh(pv.PolyData(mass_points), color=C_MASS, point_size=8, render_points_as_spheres=True)
        _, cg = calculate_cg(m)
        plotter.add_mesh(pv.Sphere(radius=0.05, center=cg), color=C_CG)
    elev, azim = MPL_VIEW_PRESETS.get(view_preset, MPL_VIEW_PRESETS["Default"])
    plotter.camera.position = (2, 2, 1)
    plotter.camera.elevation = elev - 90
    plotter.camera.azimuth = azim
    plotter.camera.zoom(0.8)
    img = plotter.screenshot(return_img=True)
    plotter.close()
    return img

def plot_3d_matplotlib(data_dict, show_mass=True, view_preset="Default"):
    """Matplotlib Axes3D view (wireframe + optional fill). view_preset: Default, Top, Front, Side, Isometric."""
    from mpl_toolkits.mplot3d import Axes3D
    if st.session_state["plot_dark_mode"]:
        plt.style.use('dark_background')
    else:
        plt.style.use('default')
    elev, azim = MPL_VIEW_PRESETS.get(view_preset, MPL_VIEW_PRESETS["Default"])
    fig = plt.figure(figsize=(10, 8))
    fig.patch.set_facecolor(PLOT_BG)
    ax = fig.add_subplot(111, projection='3d')
    ax.set_facecolor(PLOT_BG)
    ax.xaxis.pane.fill, ax.yaxis.pane.fill, ax.zaxis.pane.fill = False, False, False
    ax.xaxis.pane.set_edgecolor(AXIS_COLOR)
    ax.yaxis.pane.set_edgecolor(AXIS_COLOR)
    ax.zaxis.pane.set_edgecolor(AXIS_COLOR)
    ax.tick_params(colors=AXIS_COLOR)
    ax.xaxis.label.set_color(AXIS_COLOR)
    ax.yaxis.label.set_color(AXIS_COLOR)
    ax.zaxis.label.set_color(AXIS_COLOR)
    ax.view_init(elev=elev, azim=azim)
    for name in st.session_state["flight_data"]["order"]:
        if name not in st.session_state["flight_data"]["surfaces"]:
            continue
        surf = st.session_state["flight_data"]["surfaces"][name]
        abs_df = calculate_coords(surf["origin"], surf["df"], surf.get("incidence", 0.0))
        if abs_df.empty:
            continue
        x, y, z = abs_df["X"].values, abs_df["Y"].values, abs_df["Z"].values
        c = abs_df["Chord"].values
        t_rad = np.radians(abs_df["Twist"].values)
        sides = [1] if not surf.get("duplicate_y", True) else [1, -1]
        for y_mult in sides:
            for i in range(len(x) - 1):
                x_te_i = x[i] + c[i] * np.cos(t_rad[i])
                z_te_i = z[i] - c[i] * np.sin(t_rad[i])
                x_te_next = x[i + 1] + c[i + 1] * np.cos(t_rad[i + 1])
                z_te_next = z[i + 1] - c[i + 1] * np.sin(t_rad[i + 1])
                x_c = np.array([x[i], x_te_i, x_te_next, x[i + 1], x[i]])
                y_c = np.array([y[i] * y_mult, y[i] * y_mult, y[i + 1] * y_mult, y[i + 1] * y_mult, y[i] * y_mult])
                z_c = np.array([z[i], z_te_i, z_te_next, z[i + 1], z[i]])
                ax.plot(x_c, y_c, z_c, color=C_SURFACE, linewidth=2)
                ax.scatter(x_c[:-1], y_c[:-1], z_c[:-1], color=C_SURFACE, s=20)
                ctrl = str(abs_df.iloc[i + 1]["Ctrl"])
                hinge = abs_df.iloc[i + 1]["Hinge"]
                if len(ctrl) > 1 and ctrl.lower() != "nan":
                    x_h_i = x[i] + c[i] * hinge * np.cos(t_rad[i])
                    z_h_i = z[i] - c[i] * hinge * np.sin(t_rad[i])
                    x_h_next = x[i + 1] + c[i + 1] * hinge * np.cos(t_rad[i + 1])
                    z_h_next = z[i + 1] - c[i + 1] * hinge * np.sin(t_rad[i + 1])
                    cs_x = np.array([x_h_i, x_te_i, x_te_next, x_h_next, x_h_i])
                    cs_z = np.array([z_h_i, z_te_i, z_te_next, z_h_next, z_h_i])
                    ax.plot(cs_x, y_c, cs_z + 0.002, color=C_CTRL, linewidth=1.5)
    if show_mass and not data_dict["masses"].empty:
        m = clean_dataframe(data_dict["masses"])
        ax.scatter(m["X"], m["Y"], m["Z"], color=C_MASS, s=40, marker='x', label="Mass")
        _, cg = calculate_cg(m)
        ax.scatter([cg[0]], [cg[1]], [cg[2]], color=C_CG, s=120, marker='o', edgecolors=AXIS_COLOR, label="CG")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    plt.tight_layout()
    return fig

def plot_3view_blueprint(data_dict, show_mass=True, show_labels=True):
    if st.session_state["plot_dark_mode"]:
        plt.style.use('dark_background')
    else:
        plt.style.use('default')
    fig = plt.figure(figsize=(12, 8), constrained_layout=True)
    fig.patch.set_facecolor(PLOT_BG)
    gs = gridspec.GridSpec(2, 2, figure=fig)
    ax_top = fig.add_subplot(gs[0, :])
    ax_front = fig.add_subplot(gs[1, 0])
    ax_side = fig.add_subplot(gs[1, 1])
    for ax, t, xl, yl in zip([ax_top, ax_front, ax_side], ["TOP VIEW", "FRONT VIEW", "SIDE VIEW"], ["Y", "Y", "X"], ["X", "Z", "Z"]):
        ax.set_title(t, fontweight='bold', fontsize=12, color=AXIS_COLOR)
        ax.set_xlabel(xl, color=AXIS_COLOR)
        ax.set_ylabel(yl, color=AXIS_COLOR)
        ax.grid(True, linestyle='--', alpha=0.3, color=AXIS_COLOR)
        ax.set_aspect('equal')
        ax.set_facecolor(PLOT_BG)
        ax.axhline(0, c=AXIS_COLOR, lw=1, ls='-.')
        ax.axvline(0, c=AXIS_COLOR, lw=1, ls='-.')
        ax.tick_params(colors=AXIS_COLOR)
        for spine in ax.spines.values():
            spine.set_edgecolor(AXIS_COLOR)
    ax_top.invert_yaxis()
    ax_side.invert_xaxis()

    for name in st.session_state["flight_data"]["order"]:
        if name not in st.session_state["flight_data"]["surfaces"]:
            continue
        surf = st.session_state["flight_data"]["surfaces"][name]
        incidence = surf.get("incidence", 0.0)
        abs_df = calculate_coords(surf["origin"], surf["df"], incidence)

        if abs_df.empty:
            continue
        x = abs_df["X"].values
        y = abs_df["Y"].values
        z = abs_df["Z"].values
        c = abs_df["Chord"].values

        t_rad = np.radians(abs_df["Twist"].values)
        cx = np.mean(x)
        cy = np.mean(y)
        if show_labels:
            label_y = cy + 0.8 if "vertical" in name.lower() or "v-tail" in name.lower() else cy
            ax_top.text(label_y, cx, f" {name}", fontsize=9, fontweight='bold', color=AXIS_COLOR, bbox=dict(facecolor=PLOT_BG, alpha=0.7, edgecolor=AXIS_COLOR, pad=1))

        for i in range(len(x) - 1):
            ctrl = str(abs_df.iloc[i + 1]["Ctrl"])
            hinge = abs_df.iloc[i + 1]["Hinge"]
            has_ctrl = (len(ctrl) > 1 and ctrl.lower() != "nan")
            
            x_te_i = x[i] + c[i] * np.cos(t_rad[i])
            x_te_next = x[i + 1] + c[i + 1] * np.cos(t_rad[i + 1])
            z_te_i = z[i] - c[i] * np.sin(t_rad[i])
            z_te_next = z[i + 1] - c[i + 1] * np.sin(t_rad[i + 1])
            h1_x = x[i] + c[i] * hinge * np.cos(t_rad[i])
            h2_x = x[i + 1] + c[i + 1] * hinge * np.cos(t_rad[i + 1])
            h1_z = z[i] - c[i] * hinge * np.sin(t_rad[i])
            h2_z = z[i + 1] - c[i + 1] * hinge * np.sin(t_rad[i + 1])

            def patch(ax, x_pts, y_pts, is_c=False):
                col = C_CTRL if is_c else C_SURFACE
                ax.add_patch(Polygon(list(zip(x_pts, y_pts)), facecolor=col, edgecolor=C_EDGE, alpha=0.9, hatch='////' if is_c else None, linewidth=1.0))

            yp = [y[i], y[i + 1], y[i + 1], y[i]]
            xp = [x[i], x[i + 1], h2_x if has_ctrl else x_te_next, h1_x if has_ctrl else x_te_i]
            patch(ax_top, yp, xp)

            if surf.get("duplicate_y", True):
                patch(ax_top, [-v for v in yp], xp)

            if has_ctrl:
                xcp = [h1_x, h2_x, x_te_next, x_te_i]
                patch(ax_top, yp, xcp, True)
                if show_labels:
                    mid_x = (h1_x + h2_x) / 2 + (x_te_next - h2_x) / 2
                    mid_y = (y[i] + y[i + 1]) / 2
                    ax_top.text(mid_y, mid_x, ctrl, fontsize=7, color=AXIS_COLOR, fontweight='bold', ha='center', bbox=dict(facecolor=PLOT_BG, alpha=0.6, pad=0.3))

                if surf.get("duplicate_y", True):
                    patch(ax_top, [-v for v in yp], xcp, True)
                    if show_labels:
                        ax_top.text(-mid_y, mid_x, ctrl, fontsize=7, color=AXIS_COLOR, fontweight='bold', ha='center', bbox=dict(facecolor=PLOT_BG, alpha=0.6, pad=0.3))

            yf = [y[i], y[i + 1], y[i + 1], y[i]]
            zf = [z[i], z[i + 1], z_te_next, z_te_i]
            patch(ax_front, yf, zf)
            if surf.get("duplicate_y", True):
                patch(ax_front, [-v for v in yf], zf)

            xs = [x[i], x[i + 1], h2_x if has_ctrl else x_te_next, h1_x if has_ctrl else x_te_i]
            zs = [z[i], z[i + 1], h2_z if has_ctrl else z_te_next, h1_z if has_ctrl else z_te_i]
            patch(ax_side, xs, zs)
            if has_ctrl:
                xcs = [h1_x, h2_x, x_te_next, x_te_i]
                zcs = [h1_z, h2_z, z_te_next, z_te_i]
                patch(ax_side, xcs, zcs, True)

    if show_mass and not data_dict["masses"].empty:
        m = clean_dataframe(data_dict["masses"])
        ax_top.scatter(m["Y"], m["X"], c=C_MASS, marker='x', s=50, label="Mass", zorder=10)
        ax_front.scatter(m["Y"], m["Z"], c=C_MASS, marker='x', s=50, zorder=10)
        ax_side.scatter(m["X"], m["Z"], c=C_MASS, marker='x', s=50, zorder=10)
        total_m, cg = calculate_cg(m)
        ax_top.scatter(cg[1], cg[0], c=C_CG, marker='o', s=100, edgecolors=AXIS_COLOR, label="CG", zorder=11)
        ax_front.scatter(cg[1], cg[2], c=C_CG, marker='o', s=100, edgecolors=AXIS_COLOR, zorder=11)
        ax_side.scatter(cg[0], cg[2], c=C_CG, marker='o', s=100, edgecolors=AXIS_COLOR, zorder=11)
        if show_labels:
            ax_top.legend(loc='upper right', framealpha=1.0, facecolor=PLOT_BG, labelcolor=AXIS_COLOR)
    for ax in [ax_top, ax_front, ax_side]:
        ax.autoscale_view()
        ax.relim()
        ax.autoscale()
    return fig

def plot_wing_distribution(data_dict):
    if st.session_state["plot_dark_mode"]:
        plt.style.use('dark_background')
    else:
        plt.style.use('default')
    fig, ax = plt.subplots(2, 1, figsize=(10, 8))
    fig.patch.set_facecolor(PLOT_BG)
    if "Main Wing" in data_dict["surfaces"]:
        surf = data_dict["surfaces"]["Main Wing"]
        incidence = surf.get("incidence", 0.0)
        abs_df = calculate_coords(surf["origin"], surf["df"], incidence)
        if not abs_df.empty:
            y = abs_df["Y"].values
            chord = abs_df["Chord"].values
            twist = abs_df["Twist"].values
            for a in ax:
                a.set_facecolor(PLOT_BG)
                a.tick_params(colors=AXIS_COLOR)
                a.xaxis.label.set_color(AXIS_COLOR)
                a.yaxis.label.set_color(AXIS_COLOR)
                a.title.set_color(AXIS_COLOR)
                for spine in a.spines.values():
                    spine.set_edgecolor(AXIS_COLOR)
            ax[0].plot(y, chord, 'o-', color=C_SURFACE, label="Right", linewidth=2)
            ax[0].plot(-y, chord, 'o--', color=C_SURFACE, label="Left", alpha=0.6)
            ax[0].set_title("Chord Distribution (Main Wing)", fontweight='bold')
            ax[0].set_ylabel("Chord (m)")
            ax[0].grid(True, linestyle=':', alpha=0.6)
            ax[1].plot(y, twist, 'o-', color=C_CTRL, label="Right", linewidth=2)
            ax[1].plot(-y, twist, 'o--', color=C_CTRL, label="Left", alpha=0.6)
            ax[1].set_title("Twist Distribution (Main Wing)", fontweight='bold')
            ax[1].set_xlabel("Span Y (m)")
            ax[1].set_ylabel("Twist (deg)")
            ax[1].grid(True, linestyle=':', alpha=0.6)
    plt.tight_layout()
    return fig

# --- 8. EXPORT & LAUNCH (IMPROVED) ---
def generate_avl_text(ref):
    """
    Generate AVL geometry file (AVL-compliant).
    - Header: title, Mach, iYsym iZsym Zsym, Sref Cref Bref, Xref Yref Zref, CDp.
    - Section positions use REFERENCE geometry (chord along X); tail/surface angle
      is applied only via ANGLE + section Ainc, not by rotating LE positions.
    """
    proj = st.session_state['flight_data']['meta']['name']
    _total_m, cg = calculate_cg(st.session_state["flight_data"]["masses"])
    xref, yref, zref = cg[0], cg[1], cg[2]
    sb = io.StringIO()
    # Line 1: case title
    sb.write(f"{proj}\n")
    sb.write("0.0\n")
    sb.write("0 0 0.0\n")
    sb.write(f"{ref['S']} {ref['C']} {ref['B']}\n")
    sb.write(f"{xref:.4f} {yref:.4f} {zref:.4f}\n")
    sb.write("0.01\n")

    for name in st.session_state["flight_data"]["order"]:
        if name not in st.session_state["flight_data"]["surfaces"]:
            continue
        surf = st.session_state["flight_data"]["surfaces"][name]
        incidence = surf.get("incidence", 0.0)
        # Reference coords (chord along X) so tail angle only in ANGLE/Ainc
        abs_df = calculate_coords_for_avl(surf["origin"], surf["df"])
        if abs_df.empty:
            continue
        sb.write(f"SURFACE\n{name}\n10 1.0\n")
        if surf.get("duplicate_y", True):
            sb.write("YDUPLICATE\n0.0\n")
        # AVL: total section incidence = ANGLE + section Ainc (so Ainc = local twist only)
        sb.write(f"ANGLE\n{_safe_float(incidence):.4f}\n")
        for j, (_, row) in enumerate(abs_df.iterrows()):
            nspan = DEFAULT_NSPAN if j < len(abs_df) - 1 else 0
            sspace = DEFAULT_SSPACE if j < len(abs_df) - 1 else 0.0
            ainc = _safe_float(row["Twist"])  # local twist (deg); AVL adds ANGLE to this
            sb.write(f"SECTION\n{row['X']:.4f} {row['Y']:.4f} {row['Z']:.4f} {row['Chord']:.4f} {ainc:.4f} {nspan} {sspace}\n")
            # Airfoil: accept blank -> default NACA 0012 (for every surface)
            af = str(row.get("Airfoil", "")).strip()
            if (not af) or (af.lower() == "nan"):
                af = "NACA 0012"
            if af.lower().endswith(".dat"):
                sb.write(f"AFILE\n{af}\n")
            else:
                # Allow "NACA 2412" or "2412"; fallback to 0012
                naca_num = af.replace("NACA", "").strip()
                sb.write(f"NACA\n{naca_num or '0012'}\n")
            ctrl_name = str(row["Ctrl"]).strip()
            if len(ctrl_name) > 0 and ctrl_name.lower() != "nan":
                sb.write(f"CONTROL\n{ctrl_name} 1.0 {_safe_float(row['Hinge']):.4f} 0.0 1.0 0.0 {int(_safe_float(row['Sym'], 0))}\n")
    return sb.getvalue()

def generate_mass_file():
    m = st.session_state["flight_data"]["masses"]
    sb = io.StringIO()
    sb.write("Lunit = 1.0 m\nMunit = 1.0 kg\nTunit = 1.0 s\n\n")
    sb.write("g   = 9.81\nrho = 1.225\n\n")
    sb.write("#  mass    x     y     z    Ixx   Iyy   Izz    Ixy   Iyz   Izx\n")
    for _, row in m.iterrows():
        sb.write(f"   {row['Mass (kg)']:.4f}   {row['X']:.4f}   {row['Y']:.4f}   {row['Z']:.4f}   0.001   0.001   0.001   0.0   0.0   0.0   ! {row['Name']}\n")
    return sb.getvalue()

def generate_run_file(run_data, avl_name, mass_name):
    sb = io.StringIO()
    sb.write(f"load {avl_name}\n")
    sb.write(f"mass {mass_name}\n")
    sb.write("mset\n0\n")
    sb.write("oper\n")
    sb.write(f"a a {run_data['alpha']}\n")
    sb.write(f"v {run_data['velocity']}\n")
    sb.write(f"d {run_data['density']}\n")
    sb.write(f"g {run_data['g']}\n")
    sb.write("x\n")
    sb.write("st\n")
    sb.write("fs\n")
    return sb.getvalue()

def run_avl_external(avl_text, mass_text):
    with open("plane.avl", "w") as f:
        f.write(avl_text)
    if mass_text:
        with open("plane.mass", "w") as f:
            f.write(mass_text)
    if os.name == 'nt':
        with open("launch.bat", "w") as f:
            f.write("@echo off\n")
            f.write("echo AVL Launched. Please load your downloaded files manually.\n")
            f.write("echo Command: load <filename>.avl\n")
            f.write(f"{AVL_EXE}\n")
            f.write("pause\n")
        subprocess.Popen(["start", "cmd", "/k", "launch.bat"], shell=True)
    else:
        subprocess.Popen(f"{AVL_EXE}", shell=True)

def serialize_project():
    d = st.session_state["flight_data"]
    surfaces_dict = {}
    for n, s in d["surfaces"].items():
        surfaces_dict[n] = {"origin": s["origin"], "incidence": s.get("incidence", 0.0), "duplicate_y": s.get("duplicate_y", True), "df": s["df"].to_dict(orient="records")}
    return json.dumps({"meta": d["meta"], "run": d["run"], "order": d["order"], "surfaces": surfaces_dict, "masses": d["masses"].to_dict(orient="records")}, indent=4)

def load_project(f):
    try:
        l = json.load(f)
        new_surfaces = {}
        for n, s in l["surfaces"].items():
            new_surfaces[n] = {
                "origin": s["origin"],
                "incidence": s.get("incidence", 0.0),
                "duplicate_y": s.get("duplicate_y", True),
                "df": pd.DataFrame(s["df"])
            }
        st.session_state["flight_data"] = {
            "meta": l["meta"],
            "run": l.get("run", {"alpha": 0.0, "velocity": 15.0, "density": 1.225, "g": 9.81}),
            "order": l["order"],
            "surfaces": new_surfaces,
            "masses": pd.DataFrame(l.get("masses", []))
        }
        st.rerun()
    except Exception as e:
        st.error(f"Load failed: {e}")

# --- 9. UI LAYOUT ---
c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    st.subheader("Airplane Geometry, Design & Stability")
with c2:
    if st.button("Save Project", type="primary"):
        st.download_button("Download JSON", serialize_project(), f"{st.session_state['flight_data']['meta']['name']}.json", "application/json")
with c3:
    up = st.file_uploader("Load Project", type=["json"], label_visibility="collapsed")
    if up:
        load_project(up)

left, right = st.columns([1, 1.2])
with left:
    st.markdown("### Editor")
    st.session_state["flight_data"]["meta"]["name"] = st.text_input("Project Name", st.session_state["flight_data"]["meta"].get("name", "SharkHawk"))
    mode_tab = st.tabs(["Geometry", "Mass & Inertia", "Run Config"])

    with mode_tab[0]:
        st.info("**AVL mapping:** Surface **Incidence** → ANGLE (applies to all sections). Per-section **Twist** → SECTION Ainc (total = Incidence + Twist). **Dihedral** → section (Xle,Yle,Zle) positions. Chord is along X.")
        with st.expander("Surface Manager", expanded=True):
            c_add, c_del = st.columns([3, 1])
            new = c_add.text_input("New", label_visibility="collapsed", placeholder="Surface Name")
            if c_add.button("Add", type="primary") and new and new not in st.session_state["flight_data"]["surfaces"]:
                st.session_state["flight_data"]["surfaces"][new] = {"origin": [0.0, 0.0, 0.0], "incidence": 0.0, "duplicate_y": True, "df": pd.DataFrame([{"Y": 0, "Chord": 0.2, "Offset": 0, "Dihedral": 0, "Twist": 0, "Airfoil": "NACA 0012", "Ctrl": "", "Hinge": 0.0, "Sym": 0}])}
                st.session_state["flight_data"]["order"].append(new)
                st.rerun()

            r1, r2, r3 = st.columns([2, 2, 1])
            rename_options = [s for s in st.session_state["flight_data"]["order"] if s != "Main Wing"]
            target_surf = r1.selectbox("Rename", options=rename_options, key="rename_select", label_visibility="collapsed")
            new_name = r2.text_input("New Name", placeholder="New Name", key="rename_text", label_visibility="collapsed")
            if r3.button("Rename") and new_name and new_name not in st.session_state["flight_data"]["surfaces"]:
                old_data = st.session_state["flight_data"]["surfaces"][target_surf]
                st.session_state["flight_data"]["surfaces"][new_name] = old_data
                idx = st.session_state["flight_data"]["order"].index(target_surf)
                st.session_state["flight_data"]["order"][idx] = new_name
                del st.session_state["flight_data"]["surfaces"][target_surf]
                st.rerun()

            del_list = [s for s in st.session_state["flight_data"]["order"] if s != "Main Wing"]
            to_del = c_del.selectbox("Del", options=[""] + del_list, label_visibility="collapsed")
            if c_del.button("Remove") and to_del:
                st.session_state["flight_data"]["surfaces"].pop(to_del)
                st.session_state["flight_data"]["order"].remove(to_del)
                st.rerun()

        surf_tabs = st.tabs(st.session_state["flight_data"]["order"]) if st.session_state["flight_data"]["order"] else []
        for i, surf in enumerate(st.session_state["flight_data"]["order"]):
            with surf_tabs[i]:
                c1, c2, c3, c4 = st.columns(4)
                o = st.session_state["flight_data"]["surfaces"][surf]["origin"]
                inc = st.session_state["flight_data"]["surfaces"][surf].get("incidence", 0.0)

                nx = c1.number_input("X (Origin)", value=float(o[0]), key=f"x_{surf}")
                ny = c2.number_input("Y (Origin)", value=float(o[1]), key=f"y_{surf}")
                nz = c3.number_input("Z (Origin)", value=float(o[2]), key=f"z_{surf}")
                ni = c4.number_input("Incidence (deg)", value=float(inc), key=f"i_{surf}", help="Surface angle (e.g. H-tail -2°). Exported as AVL ANGLE; geometry uses chord-along-X.")

                st.session_state["flight_data"]["surfaces"][surf]["origin"] = [nx, ny, nz]
                st.session_state["flight_data"]["surfaces"][surf]["incidence"] = ni

                df = clean_dataframe(st.session_state["flight_data"]["surfaces"][surf]["df"])
                col_cfg = {
                    "Y": st.column_config.NumberColumn("Y (span)", format="%.2f", help="Spanwise position (m). With Dihedral, sets section (Y,Z)."),
                    "Chord": st.column_config.NumberColumn(format="%.2f"),
                    "Offset": st.column_config.NumberColumn("Sweep (dX)", format="%.2f", help="Streamwise offset from previous section (m)."),
                    "Dihedral": st.column_config.NumberColumn(format="%.1f", help="Deg: section-to-section. 0=horizontal, 90=vertical (Z step). AVL encodes in (Xle,Yle,Zle)."),
                    "Twist": st.column_config.NumberColumn(format="%.1f", help="Local twist (deg). AVL section Ainc. Total incidence = Surface Incidence + Twist."),
                    "Airfoil": st.column_config.TextColumn(help="'NACA 2412' or 'file.dat'"),
                    "Ctrl": st.column_config.TextColumn(help="Control name (e.g. elevator, aileron) or leave blank."),
                    "Hinge": st.column_config.NumberColumn(format="%.2f", help="Hinge x/c (0–1)."),
                    "Sym": st.column_config.NumberColumn(format="%d", help="+1 elevator, -1 aileron for YDUPLICATE.")
                }

                is_duplicate = st.checkbox("Y-Axis Duplication (Symmetry)", value=st.session_state["flight_data"]["surfaces"][surf].get("duplicate_y", True), key=f"dup_{surf}")
                st.session_state["flight_data"]["surfaces"][surf]["duplicate_y"] = is_duplicate

                with st.form(key=f"form_{surf}"):
                    edited = st.data_editor(df, num_rows="fixed", use_container_width=True, key=f"ed_{surf}", column_config=col_cfg)
                    if st.form_submit_button("🔄 Update Model", type="primary"):
                        st.session_state["flight_data"]["surfaces"][surf]["df"] = clean_dataframe(edited)
                        # IMPORTANT: reset the data_editor widget state so normalized defaults
                        # (e.g. blank Airfoil -> "NACA 0012") show up immediately in the UI.
                        st.session_state.pop(f"ed_{surf}", None)
                        st.rerun()
                r1, r2 = st.columns(2)
                if r1.button("➕ Add Section", key=f"add_{surf}"):
                    new_row = pd.DataFrame([{"Y": 0.0, "Chord": 0.5, "Offset": 0.0, "Dihedral": 0.0, "Twist": 0.0, "Airfoil": "NACA 0012", "Ctrl": "", "Hinge": 0.0, "Sym": 0}])
                    st.session_state["flight_data"]["surfaces"][surf]["df"] = clean_dataframe(pd.concat([df, new_row], ignore_index=True))
                    st.rerun()
                if r2.button("➖ Remove Last", key=f"rem_{surf}"):
                    if len(df) > 1:
                        st.session_state["flight_data"]["surfaces"][surf]["df"] = df.iloc[:-1]
                        st.rerun()

    with mode_tab[1]:
        st.info("Define Mass Points.")
        mass_df = clean_dataframe(st.session_state["flight_data"]["masses"])
        with st.form("mass_form"):
            edited_m = st.data_editor(mass_df, num_rows="dynamic", use_container_width=True, key="mass_editor")
            if st.form_submit_button("🔄 Update Mass"):
                st.session_state["flight_data"]["masses"] = clean_dataframe(edited_m)
                st.rerun()
        tm, cg = calculate_cg(st.session_state["flight_data"]["masses"])
        st.markdown("---")
        c_m1, c_m2 = st.columns(2)
        c_m1.metric("Total Mass", f"{tm:.3f} kg")
        c_m2.metric("CG Location", f"{cg[0]:.2f}, {cg[1]:.2f}, {cg[2]:.2f}")

    with mode_tab[2]:
        st.info("Define Flight Condition for .run file.")
        rd = st.session_state["flight_data"]["run"]
        c_r1, c_r2 = st.columns(2)
        rd["velocity"] = c_r1.number_input("Velocity (m/s)", value=rd.get("velocity", 15.0), key="v_input")
        rd["density"] = c_r2.number_input("Density (kg/m^3)", value=rd.get("density", 1.225), key="rho_input")
        c_r3, c_r4 = st.columns(2)
        rd["alpha"] = c_r3.number_input("Alpha (deg)", value=rd.get("alpha", 0.0), key="alpha_input")
        rd["g"] = c_r4.number_input("Gravity (m/s^2)", value=rd.get("g", 9.81), key="g_input")

with right:
    st.write("**Visual Validation**")
    c_show1, c_show2 = st.columns(2)
    show_m = c_show1.checkbox("Show Mass", value=True)
    show_l = c_show2.checkbox("Show Labels", value=True)
    t1, t2, t3, t4, t5 = st.tabs(["3D Interactive", "2D Blueprints", "Wing Data", "File Inspector", "AVL Reference"])
    with t1:
        c_cam, c_engine = st.columns(2)
        with c_cam:
            cam_choice = st.selectbox("Camera", list(CAMERA_PRESETS.keys()), key="cam_3d")
        with c_engine:
            engine_options = ["Plotly (interactive)", "Matplotlib 3D"]
            try:
                import pyvista
                engine_options.append("PyVista (VTK)")
            except ImportError:
                pass
            engine_3d = st.radio("3D engine", engine_options, horizontal=True, key="eng_3d")
        st.markdown('<div class="viewer-container">', unsafe_allow_html=True)
        try:
            if engine_3d == "Plotly (interactive)":
                st.plotly_chart(plot_3d(st.session_state["flight_data"], show_m, camera_eye=CAMERA_PRESETS[cam_choice]), use_container_width=True)
            elif engine_3d == "Matplotlib 3D":
                st.pyplot(plot_3d_matplotlib(st.session_state["flight_data"], show_m, view_preset=cam_choice), clear_figure=True)
            elif engine_3d == "PyVista (VTK)":
                img = plot_3d_pyvista(st.session_state["flight_data"], show_m, view_preset=cam_choice)
                if img is not None:
                    st.image(img, use_container_width=True)
        except Exception as e:
            st.error(f"3D Error: {e}")
        st.markdown('</div>', unsafe_allow_html=True)
    with t2:
        try:
            st.pyplot(plot_3view_blueprint(st.session_state["flight_data"], show_m, show_l), clear_figure=True)
        except Exception as e:
            st.error(f"2D Error: {e}")
    with t3:
        area, span, ar = calculate_wing_metrics(st.session_state["flight_data"])
        m1, m2, m3 = st.columns(3)
        m1.metric("Area (S)", f"{area:.3f} m²")
        m2.metric("Span (b)", f"{span:.3f} m")
        m3.metric("Aspect Ratio", f"{ar:.2f}")
        st.pyplot(plot_wing_distribution(st.session_state["flight_data"]), clear_figure=True)

    c1, c2, c3 = st.columns(3)
    area, span, _ = calculate_wing_metrics(st.session_state["flight_data"])
    s = c1.number_input("S_ref", value=float(area) if area > 0 else 0.6)
    c = c2.number_input("C_ref", value=0.3)
    b = c3.number_input("B_ref", value=float(span) if span > 0 else 2.0)
    pname = st.session_state["flight_data"]["meta"]["name"].replace(" ", "_")
    avl_text = generate_avl_text({"S": s, "C": c, "B": b})
    mass_text = generate_mass_file()
    run_text = generate_run_file(st.session_state["flight_data"]["run"], f"{pname}.avl", f"{pname}.mass")
    with t4:
        st.markdown("**Geometry File** (Xref,Yref,Zref = CG; section chord along X; tail angle via ANGLE)")
        st.code(avl_text, language="text")
        st.markdown("**Mass File**")
        st.code(mass_text, language="text")
        st.markdown("**Run Script**")
        st.code(run_text, language="text")
    with t5:
        st.markdown("""**1. Load Files**\n`load plane.avl` -> `mass plane.mass` -> `mset` -> `0`\n\n**2. Calculate**\n`oper` -> `a a 5.0` -> `x`\n\n**3. Output**\n`st` (Stability) -> `fs` (Forces) -> `mode` (Eigenmodes)""")
    st.markdown("---")
    b1, b2, b3, b4 = st.columns(4)
    b1.download_button("Download .AVL", avl_text, f"{pname}.avl")
    b2.download_button("Download .MASS", mass_text, f"{pname}.mass")
    b3.download_button("Download .RUN", run_text, f"{pname}.run")
    if b4.button("Open AVL", type="primary"):
        run_avl_external(avl_text, mass_text)
        st.success("AVL Launched")
