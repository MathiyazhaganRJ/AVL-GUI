"""
AVL (Athena Vortex Lattice) Input File Generator — Streamlit GUI
Universal GUI for generating AVL geometry input files.
"""
import re
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# Page config
st.set_page_config(page_title="AVL Input Generator", layout="wide", initial_sidebar_state="expanded")

# ---------------------------------------------------------------------------
# Session state: surfaces list (persists across reruns)
# ---------------------------------------------------------------------------
def init_session_state():
    if "surfaces" not in st.session_state:
        st.session_state.surfaces = []
    if "surface_counter" not in st.session_state:
        st.session_state.surface_counter = 0

def default_section():
    return {
        "xle": 0.0, "yle": 0.0, "zle": 0.0,
        "chord": 1.0, "ainc": 0.0,
        "airfoil_type": "NACA", "airfoil_value": "0012",
        "nspan": 5, "sspace": -2.0,
        "controls": [],
    }

def default_control():
    return {
        "name": "elevator", "gain": 1.0, "xhinge": 0.7,
        "hinge_x": 0.0, "hinge_y": 1.0, "hinge_z": 0.0,
        "sign_duplicate": 1.0,
    }

def default_surface():
    st.session_state.surface_counter += 1
    return {
        "name": f"Surface_{st.session_state.surface_counter}",
        "component": 1,
        "y_duplicate": 0.0,
        "angle": 0.0,
        "nchord": 5,
        "cspace": 1.0,
        "sections": [default_section(), default_section()],
    }

init_session_state()

# ---------------------------------------------------------------------------
# Sidebar: Global Parameters & Reference Values
# ---------------------------------------------------------------------------
st.sidebar.header("Global Parameters")
case_title = st.sidebar.text_input("Case title", value="AVL Configuration")
mach = st.sidebar.number_input("Mach", value=0.0, format="%.3f")
cdp = st.sidebar.number_input("CDp (Parasite Drag)", value=0.02, format="%.4f")

st.sidebar.subheader("Symmetry (AVL iYsym iZsym Zsym)")
i_ysym = st.sidebar.selectbox("iYsym (1=half model)", [1, 0, -1], index=0, format_func=lambda x: {1: "1 (symmetric Y)", 0: "0 (full)", -1: "-1 (antisym Y)"}[x])
i_zsym = st.sidebar.selectbox("iZsym", [0, 1, -1], index=0, format_func=lambda x: {0: "0", 1: "1", -1: "-1"}[x])
z_sym = st.sidebar.number_input("Zsym", value=0.0, format="%.2f")

st.sidebar.header("Reference Values")
sref = st.sidebar.number_input("Sref (Area)", value=1.0, format="%.4f")
cref = st.sidebar.number_input("Cref (Chord)", value=0.5, format="%.4f")
bref = st.sidebar.number_input("Bref (Span)", value=2.0, format="%.4f")
xref = st.sidebar.number_input("Xref (CG X)", value=0.25, format="%.4f")
yref = st.sidebar.number_input("Yref (CG Y)", value=0.0, format="%.4f")
zref = st.sidebar.number_input("Zref (CG Z)", value=0.0, format="%.4f")

st.sidebar.header("Mass & Inertias (.mass file)")
mass = st.sidebar.number_input("Mass", value=1.0, format="%.4f")
gravity = st.sidebar.number_input("Gravity (g)", value=9.81, format="%.2f")
ix = st.sidebar.number_input("Ix", value=0.1, format="%.4f")
iy = st.sidebar.number_input("Iy", value=0.1, format="%.4f")
iz = st.sidebar.number_input("Iz", value=0.1, format="%.4f")
ixz = st.sidebar.number_input("Ixz", value=0.0, format="%.4f")

# ---------------------------------------------------------------------------
# Main: Title and surface list management
# ---------------------------------------------------------------------------
st.title("AVL Input File Generator")
st.caption("Define lifting surfaces, sections, and control surfaces; preview geometry and download aircraft.avl")

col_add, _ = st.columns([1, 4])
with col_add:
    if st.button("➕ Add Surface"):
        st.session_state.surfaces.append(default_surface())
        st.rerun()

if not st.session_state.surfaces:
    st.info("Add at least one surface to begin. Use **Add Surface** above.")
else:
    for idx, surf in enumerate(st.session_state.surfaces):
        with st.expander(f"**{surf['name']}** (Component {surf['component']})", expanded=(idx == 0)):
            c1, c2, c3 = st.columns(3)
            with c1:
                surf["name"] = st.text_input("Surface name", value=surf["name"], key=f"sn_{idx}")
                surf["component"] = int(st.number_input("Component number", value=surf["component"], min_value=1, key=f"sc_{idx}"))
            with c2:
                surf["y_duplicate"] = st.number_input("Y-Duplicate (mirror plane Y)", value=float(surf["y_duplicate"]), format="%.2f", key=f"sy_{idx}")
                surf["angle"] = st.number_input("Angle (incidence deg)", value=float(surf["angle"]), format="%.2f", key=f"sa_{idx}")
            with c3:
                surf["nchord"] = int(st.number_input("Nchord", value=surf["nchord"], min_value=1, key=f"nc_{idx}"))
                surf["cspace"] = st.number_input("Cspace", value=float(surf["cspace"]), format="%.2f", key=f"cs_{idx}")

            st.subheader("Sections")
            for s_idx, sec in enumerate(surf["sections"]):
                with st.container():
                    sec_cols = st.columns([1, 2, 2])
                    with sec_cols[0]:
                        st.markdown(f"**Section {s_idx + 1}**")
                        if st.button("Remove section", key=f"rsec_{idx}_{s_idx}"):
                            if len(surf["sections"]) > 2:
                                surf["sections"].pop(s_idx)
                                st.rerun()
                    with sec_cols[1]:
                        sec["xle"] = st.number_input("Xle", value=sec["xle"], format="%.4f", key=f"xle_{idx}_{s_idx}")
                        sec["yle"] = st.number_input("Yle", value=sec["yle"], format="%.4f", key=f"yle_{idx}_{s_idx}")
                        sec["zle"] = st.number_input("Zle", value=sec["zle"], format="%.4f", key=f"zle_{idx}_{s_idx}")
                        sec["chord"] = st.number_input("Chord", value=sec["chord"], format="%.4f", key=f"ch_{idx}_{s_idx}")
                        sec["ainc"] = st.number_input("Ainc (deg)", value=sec["ainc"], format="%.2f", key=f"ainc_{idx}_{s_idx}")
                        sec["nspan"] = int(st.number_input("Nspan", value=sec["nspan"], min_value=1, key=f"nsp_{idx}_{s_idx}"))
                        sec["sspace"] = st.number_input("Sspace", value=sec["sspace"], format="%.2f", key=f"ssp_{idx}_{s_idx}")
                    with sec_cols[2]:
                        sec["airfoil_type"] = st.radio("Airfoil", ["NACA", ".dat file"], key=f"aft_{idx}_{s_idx}", horizontal=True)
                        if sec["airfoil_type"] == "NACA":
                            sec["airfoil_value"] = st.text_input("NACA 4-digit", value=sec.get("airfoil_value", "0012"), key=f"anaca_{idx}_{s_idx}")
                        else:
                            sec["airfoil_value"] = st.text_input(".dat filename", value=sec.get("airfoil_value", "airfoil.dat"), key=f"adat_{idx}_{s_idx}")

                    # Control surface(s) for this section
                    st.markdown("**Control surface (optional)**")
                    for c_idx, ctrl in enumerate(sec["controls"]):
                        cc = st.columns([2, 1, 1, 1, 1])
                        with cc[0]: ctrl["name"] = st.text_input("Name", value=ctrl["name"], key=f"cn_{idx}_{s_idx}_{c_idx}")
                        with cc[1]: ctrl["gain"] = st.number_input("Gain", value=ctrl["gain"], format="%.2f", key=f"cg_{idx}_{s_idx}_{c_idx}")
                        with cc[2]: ctrl["xhinge"] = st.number_input("Hinge x/c", value=ctrl["xhinge"], format="%.2f", key=f"ch_{idx}_{s_idx}_{c_idx}")
                        with cc[3]: ctrl["sign_duplicate"] = st.number_input("Sign Dup", value=ctrl["sign_duplicate"], format="%.1f", key=f"csd_{idx}_{s_idx}_{c_idx}")
                        with cc[4]:
                            if st.button("Remove control", key=f"rctrl_{idx}_{s_idx}_{c_idx}"):
                                sec["controls"].pop(c_idx)
                                st.rerun()
                    if st.button("Add control to this section", key=f"actrl_{idx}_{s_idx}"):
                        sec["controls"].append(default_control())
                        st.rerun()
                st.divider()

            if st.button("Add section", key=f"addsec_{idx}"):
                surf["sections"].append(default_section())
                st.rerun()

            if st.button("Remove this surface", key=f"rsurf_{idx}"):
                st.session_state.surfaces.pop(idx)
                st.rerun()

# ---------------------------------------------------------------------------
# Top-down (X-Y) geometry plot — planform LE/TE for tail arm check
# ---------------------------------------------------------------------------
st.header("Top-Down View (X-Y)")
if st.session_state.surfaces:
    fig, ax = plt.subplots(figsize=(10, 6))
    for surf in st.session_state.surfaces:
        x_le = np.array([sec["xle"] for sec in surf["sections"]])
        y_le = np.array([sec["yle"] for sec in surf["sections"]])
        x_te = np.array([sec["xle"] + sec["chord"] for sec in surf["sections"]])
        y_te = np.array([sec["yle"] for sec in surf["sections"]])
        ax.plot(x_le, y_le, "o-", label=surf["name"], linewidth=2, markersize=6)
        ax.plot(x_te, y_te, "s-", color=ax.get_lines()[-1].get_color(), linewidth=2, markersize=5)
        ax.plot([x_le[0], x_te[0]], [y_le[0], y_te[0]], "-", color=ax.get_lines()[-1].get_color(), linewidth=1.5)
        ax.plot([x_le[-1], x_te[-1]], [y_le[-1], y_te[-1]], "-", color=ax.get_lines()[-1].get_color(), linewidth=1.5)
        y_dupl = surf.get("y_duplicate", 0)
        if y_dupl != 0:
            ax.plot(x_le, 2 * y_dupl - y_le, "o--", alpha=0.7, linewidth=1.5)
            ax.plot(x_te, 2 * y_dupl - y_te, "s--", alpha=0.7, linewidth=1.5)
    ax.axhline(0, color="gray", linestyle=":", alpha=0.7)
    ax.axvline(0, color="gray", linestyle=":", alpha=0.7)
    ax.scatter([xref], [yref], s=120, c="red", zorder=5, label="CG (Xref,Yref)")
    ax.set_xlabel("X (streamwise)")
    ax.set_ylabel("Y (span)")
    ax.set_aspect("equal")
    ax.legend(loc="best", fontsize=8)
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)
    plt.close()
else:
    st.info("Add surfaces to see the top-down geometry.")

# ---------------------------------------------------------------------------
# AVL file generation (strict syntax)
# ---------------------------------------------------------------------------
def build_avl_content():
    lines = []
    lines.append(case_title)
    lines.append(f"{mach}")
    lines.append(f"{i_ysym} {i_zsym} {z_sym}")
    lines.append(f"{sref} {cref} {bref}")
    lines.append(f"{xref} {yref} {zref}")
    lines.append(f"{cdp}")

    for surf in st.session_state.surfaces:
        lines.append("SURFACE")
        lines.append(surf["name"])
        lines.append(f"{surf['nchord']} {surf['cspace']}")
        lines.append("COMPONENT")
        lines.append(str(surf["component"]))
        if surf.get("y_duplicate", 0) != 0:
            lines.append("YDUPLICATE")
            lines.append(f"{surf['y_duplicate']}")
        if surf.get("angle", 0) != 0:
            lines.append("ANGLE")
            lines.append(f"{surf['angle']}")

        for sec in surf["sections"]:
            lines.append("SECTION")
            # Xle Yle Zle Chord Ainc [Nspan Sspace]
            line_sec = f"{sec['xle']} {sec['yle']} {sec['zle']} {sec['chord']} {sec['ainc']} {sec['nspan']} {sec['sspace']}"
            lines.append(line_sec)
            if sec["airfoil_type"] == "NACA":
                naca_val = sec.get("airfoil_value", "0012")
                if re.match(r"^\d{4}$", naca_val.strip()):
                    lines.append("NACA")
                    lines.append(naca_val.strip())
                else:
                    lines.append("NACA")
                    lines.append("0012")
            else:
                lines.append("AFILE")
                lines.append(sec.get("airfoil_value", "airfoil.dat").strip())
            for ctrl in sec.get("controls", []):
                lines.append("CONTROL")
                # name gain Xhinge XYZhvec SgnDup
                hx = ctrl.get("hinge_x", 0)
                hy = ctrl.get("hinge_y", 1)
                hz = ctrl.get("hinge_z", 0)
                line_ctrl = f"{ctrl['name']} {ctrl['gain']} {ctrl['xhinge']} {hx} {hy} {hz} {ctrl['sign_duplicate']}"
                lines.append(line_ctrl)
    return "\n".join(lines)

def build_mass_content():
    lines = []
    lines.append("Lunit = 1.0 m")
    lines.append("Munit = 1.0 kg")
    lines.append("Tunit = 1.0 s")
    lines.append(f"{mass} {ix} {iy} {iz} {ixz}")
    lines.append(f"{gravity}")
    return "\n".join(lines)

st.header("Generate & Download")
if st.session_state.surfaces:
    avl_text = build_avl_content()
    st.download_button(
        label="Download aircraft.avl",
        data=avl_text,
        file_name="aircraft.avl",
        mime="text/plain",
    )
    mass_text = build_mass_content()
    st.download_button(
        label="Download aircraft.mass",
        data=mass_text,
        file_name="aircraft.mass",
        mime="text/plain",
    )
    with st.expander("Preview aircraft.avl"):
        st.text(avl_text)
else:
    st.warning("Add at least one surface before generating the AVL file.")
