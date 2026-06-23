"""
AVL — RJ Aero v2: XFLR5-style GUI
Input: sidebar design tree (Plane | Wing | Tail(s) | Mass | Run).
Output: 3D View, 2D Blueprints, Wing Data, Export.
Backend unchanged from avl_rj_improved.py (same math, export, plots).
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

st.set_page_config(page_title="AVL — Plane Design", layout="wide", page_icon="✈️", initial_sidebar_state="expanded")

# --- Theme ---
if "plot_dark_mode" not in st.session_state:
    st.session_state["plot_dark_mode"] = True
AVL_EXE = "avl.exe" if os.name == 'nt' else "./avl"
DEFAULT_NSPAN, DEFAULT_SSPACE = 5, -2.0

# --- Init (same as improved) ---
if "flight_data" not in st.session_state:
    st.session_state["flight_data"] = {
        "meta": {"name": "Concept_Plane"},
        "run": {"alpha": 0.0, "velocity": 15.0, "density": 1.225, "g": 9.81},
        "surfaces": {
            "Main Wing": {
                "origin": [0.0, 0.0, 0.0], "incidence": 0.0, "duplicate_y": True,
                "df": pd.DataFrame([
                    {"Y": 0.0, "Chord": 0.45, "Offset": 0.0, "Dihedral": 0.0, "Twist": 0.0, "Airfoil": "NACA 2412", "Ctrl": "", "Hinge": 0.0, "Sym": 0},
                    {"Y": 1.2, "Chord": 0.25, "Offset": 0.25, "Dihedral": 2.0, "Twist": 0.0, "Airfoil": "NACA 2412", "Ctrl": "Aileron", "Hinge": 0.75, "Sym": -1}
                ])
            },
            "H-Tail": {
                "origin": [1.8, 0.0, 0.0], "incidence": -2.0, "duplicate_y": True,
                "df": pd.DataFrame([
                    {"Y": 0.0, "Chord": 0.30, "Offset": 0.0, "Dihedral": 0.0, "Twist": 0.0, "Airfoil": "NACA 0012", "Ctrl": "", "Hinge": 0.0, "Sym": 0},
                    {"Y": 0.6, "Chord": 0.15, "Offset": 0.1, "Dihedral": 0.0, "Twist": 0.0, "Airfoil": "NACA 0012", "Ctrl": "Elevator", "Hinge": 0.7, "Sym": 1}
                ])
            },
            "V-Tail": {
                "origin": [1.8, 0.0, 0.0], "incidence": 0.0, "duplicate_y": False,
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

# --- Backend: same as avl_rj_improved.py ---
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
    try:
        f = float(val)
        return f if np.isfinite(f) else default
    except (TypeError, ValueError):
        return default

def calculate_coords(surface_origin, df, incidence_angle):
    df = clean_dataframe(df)
    coords = []
    inc_rad = np.radians(_safe_float(incidence_angle))
    cos_inc, sin_inc = np.cos(inc_rad), np.sin(inc_rad)
    try:
        x_rel_accum, z_rel_accum = 0.0, 0.0
        if len(df) > 0:
            row0 = df.iloc[0]
            y_rel = _safe_float(row0["Y"])
            x_rel_accum += _safe_float(row0["Offset"])
            x_rot = surface_origin[0] + x_rel_accum * cos_inc - z_rel_accum * sin_inc
            z_rot = surface_origin[2] + x_rel_accum * sin_inc + z_rel_accum * cos_inc
            coords.append({"X": x_rot, "Y": surface_origin[1] + y_rel, "Z": z_rot, "Chord": _safe_float(row0["Chord"], 1.0), "Twist": _safe_float(row0["Twist"]), "Airfoil": str(row0["Airfoil"]), "Ctrl": str(row0["Ctrl"]), "Hinge": _safe_float(row0["Hinge"]), "Sym": int(_safe_float(row0["Sym"], 0))})
            prev_y = y_rel
            for i in range(1, len(df)):
                row = df.iloc[i]
                d_span = _safe_float(row["Y"]) - prev_y
                dihed = _safe_float(row["Dihedral"])
                if abs(dihed - 90.0) < 1.0:
                    dz_rel, y_rel = d_span, prev_y
                else:
                    dz_rel = d_span * np.tan(np.radians(dihed))
                    y_rel = _safe_float(row["Y"])
                    prev_y = y_rel
                x_rel_accum += _safe_float(row["Offset"])
                z_rel_accum += dz_rel
                x_rot = surface_origin[0] + x_rel_accum * cos_inc - z_rel_accum * sin_inc
                z_rot = surface_origin[2] + x_rel_accum * sin_inc + z_rel_accum * cos_inc
                coords.append({"X": x_rot, "Y": surface_origin[1] + y_rel, "Z": z_rot, "Chord": _safe_float(row["Chord"], 1.0), "Twist": _safe_float(row["Twist"]), "Airfoil": str(row["Airfoil"]), "Ctrl": str(row["Ctrl"]), "Hinge": _safe_float(row["Hinge"]), "Sym": int(_safe_float(row["Sym"], 0))})
    except Exception as e:
        st.error(f"Coordinate error: {e}")
    return pd.DataFrame(coords)

def calculate_coords_for_avl(surface_origin, df):
    df = clean_dataframe(df)
    coords = []
    try:
        x_rel_accum, z_rel_accum = 0.0, 0.0
        if len(df) == 0:
            return pd.DataFrame(coords)
        row0 = df.iloc[0]
        y_rel = _safe_float(row0["Y"])
        x_rel_accum += _safe_float(row0["Offset"])
        coords.append({"X": surface_origin[0] + x_rel_accum, "Y": surface_origin[1] + y_rel, "Z": surface_origin[2] + z_rel_accum, "Chord": _safe_float(row0["Chord"], 1.0), "Twist": _safe_float(row0["Twist"]), "Airfoil": str(row0["Airfoil"]), "Ctrl": str(row0["Ctrl"]), "Hinge": _safe_float(row0["Hinge"]), "Sym": int(_safe_float(row0["Sym"], 0))})
        prev_y = y_rel
        for i in range(1, len(df)):
            row = df.iloc[i]
            d_span = _safe_float(row["Y"]) - prev_y
            dihed_deg = _safe_float(row["Dihedral"])
            if abs(dihed_deg - 90.0) < 1.0:
                dz_rel, y_rel = d_span, prev_y
            else:
                dz_rel = d_span * np.tan(np.radians(dihed_deg))
                y_rel = _safe_float(row["Y"])
                prev_y = y_rel
            x_rel_accum += _safe_float(row["Offset"])
            z_rel_accum += dz_rel
            coords.append({"X": surface_origin[0] + x_rel_accum, "Y": surface_origin[1] + y_rel, "Z": surface_origin[2] + z_rel_accum, "Chord": _safe_float(row["Chord"], 1.0), "Twist": _safe_float(row["Twist"]), "Airfoil": str(row["Airfoil"]), "Ctrl": str(row["Ctrl"]), "Hinge": _safe_float(row["Hinge"]), "Sym": int(_safe_float(row["Sym"], 0))})
    except Exception as e:
        st.error(f"AVL coord error: {e}")
    return pd.DataFrame(coords)

def calculate_cg(mass_df):
    mass_df = clean_dataframe(mass_df)
    if mass_df.empty:
        return 0, [0, 0, 0]
    try:
        total_mass = mass_df["Mass (kg)"].sum()
        if total_mass == 0:
            return 0, [0, 0, 0]
        return total_mass, [(mass_df["Mass (kg)"] * mass_df["X"]).sum() / total_mass, (mass_df["Mass (kg)"] * mass_df["Y"]).sum() / total_mass, (mass_df["Mass (kg)"] * mass_df["Z"]).sum() / total_mass]
    except Exception:
        return 0, [0, 0, 0]

def calculate_wing_metrics(data_dict):
    area, span, ar = 0.0, 0.0, 0.0
    target_surf = data_dict["surfaces"].get("Main Wing") or (data_dict["surfaces"].get(data_dict["order"][0]) if data_dict["order"] else None)
    if target_surf:
        df = clean_dataframe(target_surf["df"])
        semi_area, max_y = 0.0, 0.0
        try:
            for i in range(len(df) - 1):
                c_r, c_t = df.iloc[i]["Chord"], df.iloc[i + 1]["Chord"]
                y_r, y_t = df.iloc[i]["Y"], df.iloc[i + 1]["Y"]
                semi_area += 0.5 * (c_r + c_t) * abs(y_t - y_r)
                max_y = max(max_y, y_t)
            total_area, total_span = semi_area * 2, max_y * 2
            if total_area > 0:
                ar = (total_span ** 2) / total_area
            return total_area, total_span, ar
        except Exception:
            pass
    return area, span, ar

def _plot_theme():
    is_dark = st.session_state.get("plot_dark_mode", True)
    return "#000000" if is_dark else "#FFFFFF", "white" if is_dark else "black", "#333333" if is_dark else "#E5E5E5"

CAMERA_PRESETS = {"Default": dict(x=-1.5, y=-1.5, z=0.5), "Top": dict(x=0.1, y=0.1, z=2.0), "Front": dict(x=2.0, y=0.0, z=0.5), "Side": dict(x=0.0, y=2.0, z=0.5), "Isometric": dict(x=-1.2, y=-1.2, z=0.8)}
MPL_VIEW_PRESETS = {"Default": (25, -135), "Top": (90, 0), "Front": (0, 0), "Side": (0, 90), "Isometric": (30, -120)}

def plot_3d(data_dict, show_mass=True, camera_eye=None):
    if camera_eye is None:
        camera_eye = CAMERA_PRESETS["Default"]
    PLOT_BG, AXIS_COLOR, GRID_COLOR = _plot_theme()[0], _plot_theme()[1], _plot_theme()[2]
    C_SURFACE, C_CTRL, C_MASS, C_CG, C_EDGE = '#32CD32', '#FF4500', '#0000FF', AXIS_COLOR, AXIS_COLOR
    fig = go.Figure()
    lighting = dict(ambient=0.7, diffuse=0.5, specular=0.3, roughness=0.5) if st.session_state["plot_dark_mode"] else dict(ambient=1.0, diffuse=0.0, specular=0.0, roughness=1.0)
    for name in st.session_state["flight_data"]["order"]:
        if name not in st.session_state["flight_data"]["surfaces"]:
            continue
        surf = st.session_state["flight_data"]["surfaces"][name]
        abs_df = calculate_coords(surf["origin"], surf["df"], surf.get("incidence", 0.0))
        if abs_df.empty:
            continue
        x, y, z = abs_df["X"].values, abs_df["Y"].values, abs_df["Z"].values
        c = abs_df["Chord"].values
        sides = [1] if not surf.get("duplicate_y", True) else [1, -1]
        for y_mult in sides:
            for i in range(len(x) - 1):
                x_c = [x[i], x[i] + c[i], x[i + 1] + c[i + 1], x[i + 1]]
                y_c = [y[i] * y_mult, y[i] * y_mult, y[i + 1] * y_mult, y[i + 1] * y_mult]
                z_c = [z[i], z[i], z[i + 1], z[i + 1]]
                ijk = ([0, 0], [1, 2], [2, 3]) if y_mult == 1 else ([0, 0], [3, 2], [2, 1])
                fig.add_trace(go.Mesh3d(x=x_c, y=y_c, z=z_c, i=ijk[0], j=ijk[1], k=ijk[2], color=C_SURFACE, opacity=1.0, flatshading=True, showlegend=False, lighting=lighting, hoverinfo='skip'))
                fig.add_trace(go.Scatter3d(x=x_c + [x_c[0]], y=y_c + [y_c[0]], z=[v + 0.005 for v in z_c] + [z_c[0] + 0.005], mode='lines', line=dict(color=C_EDGE, width=3), showlegend=False, hoverinfo='skip'))
                ctrl, hinge = str(abs_df.iloc[i + 1]["Ctrl"]), abs_df.iloc[i + 1]["Hinge"]
                if len(ctrl) > 1 and ctrl.lower() != "nan":
                    cs_x = [x[i] + c[i] * hinge, x[i] + c[i], x[i + 1] + c[i + 1], x[i + 1] + c[i + 1] * hinge]
                    fig.add_trace(go.Mesh3d(x=cs_x, y=y_c, z=[v + 0.002 for v in z_c], i=ijk[0], j=ijk[1], k=ijk[2], color=C_CTRL, opacity=1.0, flatshading=True, name=ctrl, lighting=lighting))
    if show_mass and not data_dict["masses"].empty:
        m = clean_dataframe(data_dict["masses"])
        fig.add_trace(go.Scatter3d(x=m["X"], y=m["Y"], z=m["Z"], mode='markers', marker=dict(size=5, color=C_MASS), name="Mass"))
        _, cg = calculate_cg(m)
        fig.add_trace(go.Scatter3d(x=[cg[0]], y=[cg[1]], z=[cg[2]], mode='markers+text', marker=dict(size=12, color=C_CG, symbol='circle'), text=["CG"], name="CG", textfont=dict(color=AXIS_COLOR)))
    fig.update_layout(scene=dict(aspectmode='data', xaxis=dict(visible=False, backgroundcolor=PLOT_BG, gridcolor=GRID_COLOR), yaxis=dict(visible=False, backgroundcolor=PLOT_BG, gridcolor=GRID_COLOR), zaxis=dict(visible=False, backgroundcolor=PLOT_BG, gridcolor=GRID_COLOR), bgcolor=PLOT_BG, camera=dict(eye=camera_eye)), margin=dict(l=0, r=0, b=0, t=0), height=520, paper_bgcolor=PLOT_BG, font=dict(color=AXIS_COLOR))
    return fig

def plot_3d_pyvista(data_dict, show_mass=True, view_preset="Default"):
    """PyVista/VTK 3D rendering. Requires: pip install pyvista."""
    try:
        import pyvista as pv
    except ImportError:
        st.warning("PyVista not installed. Install with: `pip install pyvista`")
        return None
    PLOT_BG, AXIS_COLOR, _ = _plot_theme()
    C_SURFACE, C_CTRL, C_MASS, C_CG, C_EDGE = '#32CD32', '#FF4500', '#0000FF', AXIS_COLOR, AXIS_COLOR
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
        sides = [1] if not surf.get("duplicate_y", True) else [1, -1]
        for y_mult in sides:
            for i in range(len(x) - 1):
                points = np.array([[x[i], y[i] * y_mult, z[i]], [x[i] + c[i], y[i] * y_mult, z[i]], [x[i + 1] + c[i + 1], y[i + 1] * y_mult, z[i + 1]], [x[i + 1], y[i + 1] * y_mult, z[i + 1]]])
                mesh = pv.PolyData(points, faces=[4, 0, 1, 2, 3])
                plotter.add_mesh(mesh, color=C_SURFACE, show_edges=True, edge_color=C_EDGE, line_width=2)
                ctrl, hinge = str(abs_df.iloc[i + 1]["Ctrl"]), abs_df.iloc[i + 1]["Hinge"]
                if len(ctrl) > 1 and ctrl.lower() != "nan":
                    cs_points = np.array([[x[i] + c[i] * hinge, y[i] * y_mult, z[i] + 0.002], [x[i] + c[i], y[i] * y_mult, z[i] + 0.002], [x[i + 1] + c[i + 1], y[i + 1] * y_mult, z[i + 1] + 0.002], [x[i + 1] + c[i + 1] * hinge, y[i + 1] * y_mult, z[i + 1] + 0.002]])
                    plotter.add_mesh(pv.PolyData(cs_points, faces=[4, 0, 1, 2, 3]), color=C_CTRL, show_edges=True)
    if show_mass and not data_dict["masses"].empty:
        m = clean_dataframe(data_dict["masses"])
        plotter.add_mesh(pv.PolyData(np.column_stack([m["X"], m["Y"], m["Z"]])), color=C_MASS, point_size=8, render_points_as_spheres=True)
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
    from mpl_toolkits.mplot3d import Axes3D
    PLOT_BG, AXIS_COLOR, _ = _plot_theme()
    C_SURFACE, C_CTRL, C_MASS, C_CG = '#32CD32', '#FF4500', '#0000FF', AXIS_COLOR
    plt.style.use('dark_background' if st.session_state["plot_dark_mode"] else 'default')
    elev, azim = MPL_VIEW_PRESETS.get(view_preset, MPL_VIEW_PRESETS["Default"])
    fig = plt.figure(figsize=(10, 8))
    fig.patch.set_facecolor(PLOT_BG)
    ax = fig.add_subplot(111, projection='3d')
    ax.set_facecolor(PLOT_BG)
    ax.xaxis.pane.fill, ax.yaxis.pane.fill, ax.zaxis.pane.fill = False, False, False
    for pane in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
        pane.set_edgecolor(AXIS_COLOR)
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
        sides = [1] if not surf.get("duplicate_y", True) else [1, -1]
        for y_mult in sides:
            for i in range(len(x) - 1):
                x_c = np.array([x[i], x[i] + c[i], x[i + 1] + c[i + 1], x[i + 1], x[i]])
                y_c = np.array([y[i] * y_mult, y[i] * y_mult, y[i + 1] * y_mult, y[i + 1] * y_mult, y[i] * y_mult])
                z_c = np.array([z[i], z[i], z[i + 1], z[i + 1], z[i]])
                ax.plot(x_c, y_c, z_c, color=C_SURFACE, linewidth=2)
                ax.scatter(x_c[:-1], y_c[:-1], z_c[:-1], color=C_SURFACE, s=20)
                ctrl, hinge = str(abs_df.iloc[i + 1]["Ctrl"]), abs_df.iloc[i + 1]["Hinge"]
                if len(ctrl) > 1 and ctrl.lower() != "nan":
                    cs_x = np.array([x[i] + c[i] * hinge, x[i] + c[i], x[i + 1] + c[i + 1], x[i + 1] + c[i + 1] * hinge, x[i] + c[i] * hinge])
                    ax.plot(cs_x, y_c, z_c + 0.002, color=C_CTRL, linewidth=1.5)
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
    PLOT_BG, AXIS_COLOR, GRID_COLOR = _plot_theme()[0], _plot_theme()[1], _plot_theme()[2]
    C_SURFACE, C_CTRL, C_MASS, C_CG, C_EDGE = '#32CD32', '#FF4500', '#0000FF', AXIS_COLOR, AXIS_COLOR
    plt.style.use('dark_background' if st.session_state["plot_dark_mode"] else 'default')
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
        abs_df = calculate_coords(surf["origin"], surf["df"], surf.get("incidence", 0.0))
        if abs_df.empty:
            continue
        x, y, z, c = abs_df["X"].values, abs_df["Y"].values, abs_df["Z"].values, abs_df["Chord"].values
        if show_labels:
            ax_top.text(np.mean(y), np.mean(x), f" {name}", fontsize=9, fontweight='bold', color=AXIS_COLOR, bbox=dict(facecolor=PLOT_BG, alpha=0.7, edgecolor=AXIS_COLOR, pad=1))
        for i in range(len(x) - 1):
            ctrl, hinge = str(abs_df.iloc[i + 1]["Ctrl"]), abs_df.iloc[i + 1]["Hinge"]
            has_ctrl = len(ctrl) > 1 and ctrl.lower() != "nan"
            h1, h2 = x[i] + c[i] * hinge, x[i + 1] + c[i + 1] * hinge
            def patch(ax, x_pts, y_pts, is_c=False):
                ax.add_patch(Polygon(list(zip(x_pts, y_pts)), facecolor=C_CTRL if is_c else C_SURFACE, edgecolor=C_EDGE, alpha=0.9, hatch='////' if is_c else None, linewidth=1.0))
            yp, xp = [y[i], y[i + 1], y[i + 1], y[i]], [x[i], x[i + 1], h2 if has_ctrl else x[i + 1] + c[i + 1], h1 if has_ctrl else x[i] + c[i]]
            patch(ax_top, yp, xp)
            if surf.get("duplicate_y", True):
                patch(ax_top, [-v for v in yp], xp)
            if has_ctrl:
                patch(ax_top, yp, [h1, h2, x[i + 1] + c[i + 1], x[i] + c[i]], True)
                if surf.get("duplicate_y", True):
                    patch(ax_top, [-v for v in yp], [h1, h2, x[i + 1] + c[i + 1], x[i] + c[i]], True)
            yf, zf = [y[i], y[i + 1], y[i + 1], y[i]], [z[i], z[i + 1], z[i + 1], z[i]]
            patch(ax_front, yf, zf)
            if surf.get("duplicate_y", True):
                patch(ax_front, [-v for v in yf], zf)
            xs, zs = [x[i], x[i + 1], h2 if has_ctrl else x[i + 1] + c[i + 1], h1 if has_ctrl else x[i] + c[i]], [z[i], z[i + 1], z[i + 1], z[i]]
            patch(ax_side, xs, zs)
            if has_ctrl:
                patch(ax_side, [h1, h2, x[i + 1] + c[i + 1], x[i] + c[i]], zs, True)
    if show_mass and not data_dict["masses"].empty:
        m = clean_dataframe(data_dict["masses"])
        ax_top.scatter(m["Y"], m["X"], c=C_MASS, marker='x', s=50, label="Mass", zorder=10)
        ax_front.scatter(m["Y"], m["Z"], c=C_MASS, marker='x', s=50, zorder=10)
        ax_side.scatter(m["X"], m["Z"], c=C_MASS, marker='x', s=50, zorder=10)
        _, cg = calculate_cg(m)
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
    PLOT_BG, AXIS_COLOR, _ = _plot_theme()
    C_SURFACE, C_CTRL = '#32CD32', '#FF4500'
    plt.style.use('dark_background' if st.session_state["plot_dark_mode"] else 'default')
    fig, ax = plt.subplots(2, 1, figsize=(10, 8))
    fig.patch.set_facecolor(PLOT_BG)
    if "Main Wing" in data_dict["surfaces"]:
        surf = data_dict["surfaces"]["Main Wing"]
        abs_df = calculate_coords(surf["origin"], surf["df"], surf.get("incidence", 0.0))
        if not abs_df.empty:
            y, chord, twist = abs_df["Y"].values, abs_df["Chord"].values, abs_df["Twist"].values
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
            ax[0].set_title("Chord (Main Wing)")
            ax[0].set_ylabel("Chord (m)")
            ax[0].grid(True, linestyle=':', alpha=0.6)
            ax[1].plot(y, twist, 'o-', color=C_CTRL, label="Right", linewidth=2)
            ax[1].plot(-y, twist, 'o--', color=C_CTRL, label="Left", alpha=0.6)
            ax[1].set_title("Twist (Main Wing)")
            ax[1].set_xlabel("Span Y (m)")
            ax[1].set_ylabel("Twist (deg)")
            ax[1].grid(True, linestyle=':', alpha=0.6)
    plt.tight_layout()
    return fig

def generate_avl_text(ref):
    proj = st.session_state['flight_data']['meta']['name']
    _, cg = calculate_cg(st.session_state["flight_data"]["masses"])
    sb = io.StringIO()
    sb.write(f"{proj}\n0.0\n0 0 0.0\n{ref['S']} {ref['C']} {ref['B']}\n{cg[0]:.4f} {cg[1]:.4f} {cg[2]:.4f}\n0.01\n")
    for name in st.session_state["flight_data"]["order"]:
        if name not in st.session_state["flight_data"]["surfaces"]:
            continue
        surf = st.session_state["flight_data"]["surfaces"][name]
        abs_df = calculate_coords_for_avl(surf["origin"], surf["df"])
        if abs_df.empty:
            continue
        sb.write(f"SURFACE\n{name}\n10 1.0\n")
        if surf.get("duplicate_y", True):
            sb.write("YDUPLICATE\n0.0\n")
        sb.write(f"ANGLE\n{_safe_float(surf.get('incidence', 0.0)):.4f}\n")
        for j, (_, row) in enumerate(abs_df.iterrows()):
            nspan = DEFAULT_NSPAN if j < len(abs_df) - 1 else 0
            sspace = DEFAULT_SSPACE if j < len(abs_df) - 1 else 0.0
            sb.write(f"SECTION\n{row['X']:.4f} {row['Y']:.4f} {row['Z']:.4f} {row['Chord']:.4f} {_safe_float(row['Twist']):.4f} {nspan} {sspace}\n")
            af = str(row["Airfoil"]).strip()
            sb.write(f"AFILE\n{af}\n" if af.lower().endswith(".dat") else f"NACA\n{af.replace('NACA', '').strip() or '0012'}\n")
            ctrl_name = str(row["Ctrl"]).strip()
            if len(ctrl_name) > 0 and ctrl_name.lower() != "nan":
                sb.write(f"CONTROL\n{ctrl_name} 1.0 {_safe_float(row['Hinge']):.4f} 0.0 1.0 0.0 {int(_safe_float(row['Sym'], 0))}\n")
    return sb.getvalue()

def generate_mass_file():
    m = st.session_state["flight_data"]["masses"]
    sb = io.StringIO()
    sb.write("Lunit = 1.0 m\nMunit = 1.0 kg\nTunit = 1.0 s\n\ng   = 9.81\nrho = 1.225\n\n#  mass    x     y     z    Ixx   Iyy   Izz    Ixy   Iyz   Izx\n")
    for _, row in m.iterrows():
        sb.write(f"   {row['Mass (kg)']:.4f}   {row['X']:.4f}   {row['Y']:.4f}   {row['Z']:.4f}   0.001   0.001   0.001   0.0   0.0   0.0   ! {row['Name']}\n")
    return sb.getvalue()

def generate_run_file(run_data, avl_name, mass_name):
    sb = io.StringIO()
    sb.write(f"load {avl_name}\nmass {mass_name}\nmset\n0\noper\na a {run_data['alpha']}\nv {run_data['velocity']}\nd {run_data['density']}\ng {run_data['g']}\nx\nst\nfs\n")
    return sb.getvalue()

def run_avl_external(avl_text, mass_text):
    with open("plane.avl", "w") as f:
        f.write(avl_text)
    if mass_text:
        with open("plane.mass", "w") as f:
            f.write(mass_text)
    if os.name == 'nt':
        with open("launch.bat", "w") as f:
            f.write(f"@echo off\necho AVL Launched.\n{AVL_EXE}\npause\n")
        subprocess.Popen(["start", "cmd", "/k", "launch.bat"], shell=True)
    else:
        subprocess.Popen(f"{AVL_EXE}", shell=True)

def serialize_project():
    d = st.session_state["flight_data"]
    surfaces_dict = {n: {"origin": s["origin"], "incidence": s.get("incidence", 0.0), "duplicate_y": s.get("duplicate_y", True), "df": s["df"].to_dict(orient="records")} for n, s in d["surfaces"].items()}
    return json.dumps({"meta": d["meta"], "run": d["run"], "order": d["order"], "surfaces": surfaces_dict, "masses": d["masses"].to_dict(orient="records")}, indent=4)

def load_project(f):
    try:
        l = json.load(f)
        new_surfaces = {n: {"origin": s["origin"], "incidence": s.get("incidence", 0.0), "duplicate_y": s.get("duplicate_y", True), "df": pd.DataFrame(s["df"])} for n, s in l["surfaces"].items()}
        st.session_state["flight_data"] = {"meta": l["meta"], "run": l.get("run", {"alpha": 0.0, "velocity": 15.0, "density": 1.225, "g": 9.81}), "order": l["order"], "surfaces": new_surfaces, "masses": pd.DataFrame(l.get("masses", []))}
        st.rerun()
    except Exception as e:
        st.error(f"Load failed: {e}")

# --- Column config for section tables ---
def section_column_config():
    return {
        "Y": st.column_config.NumberColumn("Y (span)", format="%.2f"),
        "Chord": st.column_config.NumberColumn(format="%.2f"),
        "Offset": st.column_config.NumberColumn("Sweep (dX)", format="%.2f"),
        "Dihedral": st.column_config.NumberColumn(format="%.1f"),
        "Twist": st.column_config.NumberColumn(format="%.1f"),
        "Airfoil": st.column_config.TextColumn(),
        "Ctrl": st.column_config.TextColumn(),
        "Hinge": st.column_config.NumberColumn(format="%.2f"),
        "Sym": st.column_config.NumberColumn(format="%d"),
    }

# ========== XFLR5-style UI ==========
_plot_bg = _plot_theme()[0]
st.markdown(f"""
<style>
.stApp {{ background: #f8f9fa; }}
.viewer-container {{ background-color: {_plot_bg}; border-radius: 8px; padding: 8px; margin: 4px 0; }}
div.stButton > button {{ border-radius: 6px; font-weight: 600; border: 1px solid #00AAFF; color: #00AAFF; background: transparent; }}
div.stButton > button:hover {{ background: #00AAFF; color: white; }}
.stTabs [aria-selected="true"] {{ color: #00AAFF !important; border-bottom-color: #00AAFF !important; }}
</style>
""", unsafe_allow_html=True)

# ----- Sidebar: Design tree (XFLR5-like) -----
with st.sidebar:
    st.markdown("### ✈️ Plane Design")
    st.session_state["plot_dark_mode"] = st.toggle("Dark plots", value=st.session_state["plot_dark_mode"])
    st.session_state["flight_data"]["meta"]["name"] = st.text_input("Project name", value=st.session_state["flight_data"]["meta"].get("name", "Concept_Plane"), key="proj_name_sb")
    st.download_button("Save project (JSON)", serialize_project(), f"{st.session_state['flight_data']['meta']['name']}.json", "application/json", type="primary", key="dl_json")
    up = st.file_uploader("Load project", type=["json"], key="load_sb", label_visibility="collapsed")
    if up:
        load_project(up)
    st.divider()
    st.markdown("**Design**")
    order = st.session_state["flight_data"]["order"]
    options = ["Plane Definition"] + list(order) + ["Mass & Inertia", "Flight Condition"]
    selected = st.radio("Component", options, key="design_tree", label_visibility="collapsed")

# ----- Main: Input panel (left) + Output (right) -----
col_input, col_output = st.columns([1.1, 1.9])

with col_input:
    st.markdown("#### 📋 Input")
    if selected == "Plane Definition":
        st.caption("Project and surfaces")
        with st.expander("Surfaces", expanded=True):
            new_name = st.text_input("New surface name", key="new_surf_name", placeholder="e.g. Canard")
            if st.button("Add surface", key="add_surf_v2") and new_name and new_name not in st.session_state["flight_data"]["surfaces"]:
                st.session_state["flight_data"]["surfaces"][new_name] = {"origin": [0.0, 0.0, 0.0], "incidence": 0.0, "duplicate_y": True, "df": pd.DataFrame([{"Y": 0, "Chord": 0.2, "Offset": 0, "Dihedral": 0, "Twist": 0, "Airfoil": "NACA 0012", "Ctrl": "", "Hinge": 0.0, "Sym": 0}])}
                st.session_state["flight_data"]["order"].append(new_name)
                st.rerun()
            del_options = [s for s in order if s != "Main Wing"]
            to_del = st.selectbox("Remove surface", [""] + del_options, key="del_surf")
            if st.button("Remove", key="rm_surf") and to_del:
                st.session_state["flight_data"]["surfaces"].pop(to_del)
                st.session_state["flight_data"]["order"].remove(to_del)
                st.rerun()
        st.caption("Reference Sref, Cref, Bref are set in the Export tab.")
    elif selected in st.session_state["flight_data"]["surfaces"]:
        surf = st.session_state["flight_data"]["surfaces"][selected]
        o = surf["origin"]
        c1, c2, c3 = st.columns(3)
        with c1:
            nx = st.number_input("X", value=float(o[0]), key=f"ox_{selected}", format="%.2f")
        with c2:
            ny = st.number_input("Y", value=float(o[1]), key=f"oy_{selected}", format="%.2f")
        with c3:
            nz = st.number_input("Z", value=float(o[2]), key=f"oz_{selected}", format="%.2f")
        surf["origin"] = [nx, ny, nz]
        surf["incidence"] = st.number_input("Incidence (deg)", value=float(surf.get("incidence", 0.0)), key=f"inc_{selected}", format="%.2f")
        surf["duplicate_y"] = st.checkbox("Y duplicate (symmetry)", value=surf.get("duplicate_y", True), key=f"dup_{selected}")
        df = clean_dataframe(surf["df"])
        with st.form(key=f"form_v2_{selected}"):
            edited = st.data_editor(df, num_rows="fixed", use_container_width=True, key=f"ed_v2_{selected}", column_config=section_column_config())
            if st.form_submit_button("Update sections"):
                surf["df"] = clean_dataframe(edited)
                st.rerun()
        r1, r2 = st.columns(2)
        with r1:
            if st.button("➕ Add section", key=f"add_sec_{selected}"):
                surf["df"] = clean_dataframe(pd.concat([df, pd.DataFrame([{"Y": 0.0, "Chord": 0.5, "Offset": 0.0, "Dihedral": 0.0, "Twist": 0.0, "Airfoil": "NACA 0012", "Ctrl": "", "Hinge": 0.0, "Sym": 0}])], ignore_index=True))
                st.rerun()
        with r2:
            if st.button("➖ Remove last", key=f"rem_sec_{selected}") and len(df) > 1:
                surf["df"] = df.iloc[:-1]
                st.rerun()
    elif selected == "Mass & Inertia":
        st.caption("Mass points (kg, X, Y, Z)")
        mass_df = clean_dataframe(st.session_state["flight_data"]["masses"])
        with st.form("mass_form_v2"):
            edited_m = st.data_editor(mass_df, num_rows="dynamic", use_container_width=True, key="mass_ed_v2")
            if st.form_submit_button("Update mass"):
                st.session_state["flight_data"]["masses"] = clean_dataframe(edited_m)
                st.rerun()
        tm, cg = calculate_cg(st.session_state["flight_data"]["masses"])
        st.metric("Total mass", f"{tm:.3f} kg")
        st.metric("CG", f"({cg[0]:.2f}, {cg[1]:.2f}, {cg[2]:.2f})")
    elif selected == "Flight Condition":
        st.caption("Run case for .run file")
        rd = st.session_state["flight_data"]["run"]
        rd["velocity"] = st.number_input("Velocity (m/s)", value=rd.get("velocity", 15.0), key="v_v2")
        rd["density"] = st.number_input("Density (kg/m³)", value=rd.get("density", 1.225), key="rho_v2")
        rd["alpha"] = st.number_input("Alpha (deg)", value=rd.get("alpha", 0.0), key="alpha_v2")
        rd["g"] = st.number_input("Gravity (m/s²)", value=rd.get("g", 9.81), key="g_v2")

with col_output:
    st.markdown("#### 📊 Output")
    show_m = st.checkbox("Show mass & CG", value=True, key="show_m_v2")
    show_l = st.checkbox("Show labels", value=True, key="show_l_v2")
    out_tabs = st.tabs(["3D View", "2D Blueprints", "Wing Data", "Export"])
    with out_tabs[0]:
        cam_choice = st.selectbox("Camera", list(CAMERA_PRESETS.keys()), key="cam_v2")
        engine_options = ["Plotly (interactive)", "Matplotlib 3D"]
        try:
            import pyvista
            engine_options.append("PyVista (VTK)")
        except ImportError:
            pass
        engine_3d = st.radio("3D engine", engine_options, horizontal=True, key="eng_v2")
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
            st.error(str(e))
        st.markdown('</div>', unsafe_allow_html=True)
    with out_tabs[1]:
        try:
            st.pyplot(plot_3view_blueprint(st.session_state["flight_data"], show_m, show_l), clear_figure=True)
        except Exception as e:
            st.error(str(e))
    with out_tabs[2]:
        area, span, ar = calculate_wing_metrics(st.session_state["flight_data"])
        st.metric("Area (S)", f"{area:.3f} m²")
        st.metric("Span (b)", f"{span:.3f} m")
        st.metric("Aspect ratio", f"{ar:.2f}")
        st.pyplot(plot_wing_distribution(st.session_state["flight_data"]), clear_figure=True)
    with out_tabs[3]:
        area, span, _ = calculate_wing_metrics(st.session_state["flight_data"])
        s = st.number_input("Sref", value=float(area) if area > 0 else 0.6, format="%.3f", key="sref_exp")
        c = st.number_input("Cref", value=0.3, format="%.3f", key="cref_exp")
        b = st.number_input("Bref", value=float(span) if span > 0 else 2.0, format="%.3f", key="bref_exp")
        pname = st.session_state["flight_data"]["meta"]["name"].replace(" ", "_")
        avl_text = generate_avl_text({"S": s, "C": c, "B": b})
        mass_text = generate_mass_file()
        run_text = generate_run_file(st.session_state["flight_data"]["run"], f"{pname}.avl", f"{pname}.mass")
        st.code(avl_text, language="text")
        c1, c2, c3, c4 = st.columns(4)
        c1.download_button("Download .AVL", avl_text, f"{pname}.avl")
        c2.download_button("Download .MASS", mass_text, f"{pname}.mass")
        c3.download_button("Download .RUN", run_text, f"{pname}.run")
        if c4.button("Open AVL", type="primary"):
            run_avl_external(avl_text, mass_text)
            st.success("Launched")
