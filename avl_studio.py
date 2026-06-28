import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import io
import os

from geometry_engine import Airplane, Surface, Section, ControlSurface, PointMass

st.set_page_config(page_title="AVL Design Studio (XFLR5 Style)", layout="wide", page_icon="✈️")

# ==========================================
# 1. STATE INITIALIZATION
# ==========================================
if "plane" not in st.session_state:
    st.session_state.plane = Airplane(
        name="Shark_Hawk_Concept",
        surfaces=[
            Surface(
                name="Main Wing", 
                origin=(0.0, 0.0, 0.0),
                incidence=1.5,
                sections=[
                    Section(y=0.0, chord=0.3, airfoil="NACA 2412"),
                    Section(y=1.0, chord=0.15, offset_x=0.05, twist=-2.0, dihedral=3.0, airfoil="NACA 2412", control=ControlSurface("Aileron", 0.75, -1))
                ]
            ),
            Surface(
                name="H-Tail",
                origin=(1.2, 0.0, 0.0),
                incidence=-1.0,
                sections=[
                    Section(y=0.0, chord=0.1, airfoil="NACA 0012"),
                    Section(y=0.3, chord=0.08, offset_x=0.02, airfoil="NACA 0012", control=ControlSurface("Elevator", 0.7, 1))
                ]
            ),
            Surface(
                name="V-Tail",
                origin=(1.2, 0.0, 0.0),
                duplicate_y=False,
                sections=[
                    Section(y=0.0, chord=0.12, offset_x=0.0, dihedral=90.0, airfoil="NACA 0012"),
                    Section(y=0.25, chord=0.08, offset_x=0.03, dihedral=90.0, airfoil="NACA 0012", control=ControlSurface("Rudder", 0.7, 1))
                ]
            )
        ],
        point_masses=[
            PointMass(name="Fuselage", mass=1.5, x=0.3, y=0.0, z=0.0),
            PointMass(name="Motor", mass=0.4, x=-0.1, y=0.0, z=0.0),
            PointMass(name="Battery", mass=0.8, x=0.2, y=0.0, z=-0.05)
        ]
    )
    st.session_state.plane.calculate_cg()

# ==========================================
# 2. PLOTTING ENGINE (Plotly)
# ==========================================
def render_plane_3d(plane: Airplane):
    fig = go.Figure()
    
    colors = ["#00AAFF", "#32CD32", "#FFD700", "#9370DB", "#FF4500"]
    
    # Render Surfaces
    for idx, surf in enumerate(plane.surfaces):
        mesh_data = surf.generate_3d_mesh()
        if not mesh_data:
            continue
            
        sides = [1, -1] if surf.duplicate_y else [1]
        surf_color = colors[idx % len(colors)]
        
        for side in sides:
            for i in range(len(mesh_data) - 1):
                sec1 = mesh_data[i]
                sec2 = mesh_data[i+1]
                
                # Wing Surface coordinates
                x = [sec1["x_le"], sec1["x_te"], sec2["x_te"], sec2["x_le"]]
                y = [sec1["y"] * side, sec1["y"] * side, sec2["y"] * side, sec2["y"] * side]
                z = [sec1["z_le"], sec1["z_te"], sec2["z_te"], sec2["z_le"]]
                
                if side == 1:
                    i_idx, j_idx, k_idx = [0, 0], [1, 2], [2, 3]
                else:
                    i_idx, j_idx, k_idx = [0, 0], [3, 2], [2, 1]
                    
                fig.add_trace(go.Mesh3d(
                    x=x, y=y, z=z, 
                    i=i_idx, j=j_idx, k=k_idx,
                    color=surf_color,
                    opacity=0.9,
                    flatshading=True,
                    name=surf.name,
                    showlegend=False
                ))
                
                # Control Surface coordinates
                if sec2["ctrl_name"]:
                    cs_x = [sec1["x_hinge"], sec1["x_te"], sec2["x_te"], sec2["x_hinge"]]
                    cs_y = [sec1["y"] * side, sec1["y"] * side, sec2["y"] * side, sec2["y"] * side]
                    cs_z = [sec1["z_hinge"]+0.002, sec1["z_te"]+0.002, sec2["z_te"]+0.002, sec2["z_hinge"]+0.002]
                    
                    fig.add_trace(go.Mesh3d(
                        x=cs_x, y=cs_y, z=cs_z,
                        i=i_idx, j=j_idx, k=k_idx,
                        color="#FF4500", opacity=1.0,
                        flatshading=True, name=sec2["ctrl_name"], showlegend=False
                    ))
                
                # Wireframe outline
                z_wire = [v + 0.002 for v in z]
                fig.add_trace(go.Scatter3d(
                    x=x + [x[0]], y=y + [y[0]], z=z_wire + [z_wire[0]],
                    mode='lines', line=dict(color="black", width=3),
                    showlegend=False, hoverinfo='skip'
                ))
                
    # Render Masses
    if plane.point_masses:
        m_x = [m.x for m in plane.point_masses]
        m_y = [m.y for m in plane.point_masses]
        m_z = [m.z for m in plane.point_masses]
        m_names = [m.name for m in plane.point_masses]
        
        fig.add_trace(go.Scatter3d(
            x=m_x, y=m_y, z=m_z,
            mode='markers+text',
            marker=dict(size=6, color='blue', symbol='square'),
            text=m_names, textposition="bottom center",
            name="Point Masses"
        ))
        
        # Render CG
        plane.calculate_cg()
        fig.add_trace(go.Scatter3d(
            x=[plane.cg[0]], y=[plane.cg[1]], z=[plane.cg[2]],
            mode='markers+text',
            marker=dict(size=12, color='black', symbol='diamond'),
            text=["CG"], textposition="top center",
            name="Center of Gravity",
            textfont=dict(color='black', size=14, family='Arial Black')
        ))
                
    fig.update_layout(
        scene=dict(
            aspectmode='data',
            xaxis=dict(visible=False, showgrid=False), 
            yaxis=dict(visible=False, showgrid=False), 
            zaxis=dict(visible=False, showgrid=False),
            camera=dict(eye=dict(x=-1.5, y=-1.5, z=0.5))
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=800,
        paper_bgcolor="#E5E7EB",
    )
    return fig

# ==========================================
# 3. USER INTERFACE (XFLR5 Layout)
# ==========================================
st.markdown("""
    <style>
        .stApp { background-color: #F3F4F6; }
        .block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 95%; }
        h3 { color: #1F2937; font-family: sans-serif; }
        .css-1d391kg { background-color: white; border-radius: 10px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h2 style='text-align: center; color: #111827; font-weight: 800; font-family: sans-serif;'>✈️ AVL Design Studio <span style='font-weight: 400; color: #6B7280; font-size: 0.6em;'>(XFLR5 Environment)</span></h2>", unsafe_allow_html=True)

col_editor, col_viewer = st.columns([1.1, 2])

with col_editor:
    st.markdown("### 🛠️ Geometry & Mass Editor")
    
    # Tabs for XFLR5 modules
    tab_geom, tab_mass = st.tabs(["📐 Surfaces & Geometry", "⚖️ Mass & Inertia"])
    
    # ---------------------------------------------------------
    # TAB: GEOMETRY
    # ---------------------------------------------------------
    with tab_geom:
        with st.expander("✈️ Airplane Reference Data", expanded=False):
            plane = st.session_state.plane
            plane.name = st.text_input("Project Name", value=plane.name)
            c1, c2, c3 = st.columns(3)
            plane.s_ref = c1.number_input("S_ref (Area)", value=plane.s_ref, step=0.1)
            plane.c_ref = c2.number_input("C_ref (Chord)", value=plane.c_ref, step=0.1)
            plane.b_ref = c3.number_input("B_ref (Span)", value=plane.b_ref, step=0.1)
            
            # CG is now calculated automatically
            st.info(f"Auto CG: X={plane.cg[0]:.3f}, Y={plane.cg[1]:.3f}, Z={plane.cg[2]:.3f}")

        st.markdown("#### 📐 Surfaces")
        surface_names = [s.name for s in st.session_state.plane.surfaces]
        
        col_sel, col_add, col_del = st.columns([3, 1, 1])
        selected_surface_name = col_sel.selectbox("Current Surface", surface_names, label_visibility="collapsed")
        
        if col_add.button("➕ Add"):
            new_surf = Surface(name=f"Surface {len(surface_names)+1}", sections=[Section(y=0.0, chord=0.1)])
            st.session_state.plane.surfaces.append(new_surf)
            st.rerun()
            
        if col_del.button("🗑️ Del") and len(surface_names) > 1:
            st.session_state.plane.surfaces = [s for s in st.session_state.plane.surfaces if s.name != selected_surface_name]
            st.rerun()
        
        if not st.session_state.plane.surfaces:
            st.stop()
            
        surf = next((s for s in st.session_state.plane.surfaces if s.name == selected_surface_name), st.session_state.plane.surfaces[0])
        
        surf.name = st.text_input("Surface Name", value=surf.name)
        
        col_x, col_y, col_z = st.columns(3)
        surf.origin = (
            col_x.number_input("Origin X", value=surf.origin[0], step=0.01, format="%.3f"),
            col_y.number_input("Origin Y", value=surf.origin[1], step=0.01, format="%.3f"),
            col_z.number_input("Origin Z", value=surf.origin[2], step=0.01, format="%.3f")
        )
        
        col_inc, col_dup = st.columns(2)
        surf.incidence = col_inc.number_input("Incidence (°)", value=surf.incidence, step=0.1, format="%.2f")
        surf.duplicate_y = col_dup.checkbox("Y-Duplicate (Symmetry)", value=surf.duplicate_y)
        
        # Sections Data Editor
        st.markdown("#### 🔪 Airfoil & Control Sections")
        
        df_data = []
        for s in surf.sections:
            df_data.append({
                "Y (Span)": float(s.y), 
                "Chord": float(s.chord), 
                "Offset X": float(s.offset_x),
                "Dihedral": float(s.dihedral), 
                "Twist": float(s.twist), 
                "Airfoil": str(s.airfoil),
                "Ctrl Name": str(s.control.name) if s.control else "",
                "Hinge X/C": float(s.control.hinge_x_c) if s.control else 0.7,
                "Ctrl Sym": int(s.control.sym) if s.control else 1
            })
        df = pd.DataFrame(df_data)
        
        edited_df = st.data_editor(
            df, 
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key=f"editor_{surf.name}"
        )
        
        try:
            new_sections = []
            for _, row in edited_df.iterrows():
                # Handle control surface creation
                ctrl_name = str(row.get("Ctrl Name", "")).strip()
                ctrl = None
                if ctrl_name and ctrl_name.lower() != "nan":
                    ctrl = ControlSurface(
                        name=ctrl_name,
                        hinge_x_c=float(row.get("Hinge X/C", 0.7)),
                        sym=int(row.get("Ctrl Sym", 1))
                    )
                
                new_sections.append(Section(
                    y=float(row["Y (Span)"]),
                    chord=float(row["Chord"]),
                    offset_x=float(row["Offset X"]),
                    dihedral=float(row["Dihedral"]),
                    twist=float(row["Twist"]),
                    airfoil=str(row["Airfoil"]),
                    control=ctrl
                ))
            surf.sections = new_sections
        except Exception as e:
            st.error(f"Invalid table data: {e}")

    # ---------------------------------------------------------
    # TAB: MASS & INERTIA
    # ---------------------------------------------------------
    with tab_mass:
        st.markdown("#### ⚖️ Point Masses")
        st.caption("Define point masses to auto-calculate the CG (just like XFLR5).")
        
        mass_data = []
        for m in st.session_state.plane.point_masses:
            mass_data.append({
                "Name": m.name,
                "Mass (kg)": m.mass,
                "X": m.x,
                "Y": m.y,
                "Z": m.z
            })
        
        if not mass_data:
            mass_data = [{"Name": "New Mass", "Mass (kg)": 0.0, "X": 0.0, "Y": 0.0, "Z": 0.0}]
            
        df_mass = pd.DataFrame(mass_data)
        edited_mass_df = st.data_editor(
            df_mass,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="mass_editor"
        )
        
        try:
            new_masses = []
            for _, row in edited_mass_df.iterrows():
                if float(row["Mass (kg)"]) > 0 or str(row["Name"]).strip() != "New Mass":
                    new_masses.append(PointMass(
                        name=str(row["Name"]),
                        mass=float(row["Mass (kg)"]),
                        x=float(row["X"]),
                        y=float(row["Y"]),
                        z=float(row["Z"])
                    ))
            st.session_state.plane.point_masses = new_masses
            # Recompute CG immediately
            st.session_state.plane.calculate_cg()
        except Exception as e:
            st.error(f"Invalid mass data: {e}")
            
        total_m = sum(m.mass for m in st.session_state.plane.point_masses)
        st.success(f"**Total Mass:** {total_m:.3f} kg | **Auto CG:** X={plane.cg[0]:.3f}, Y={plane.cg[1]:.3f}, Z={plane.cg[2]:.3f}")

    st.markdown("---")
    
    # -- EXPORT --
    if st.button("💾 Export to AVL (.avl & .mass)", use_container_width=True, type="primary"):
        base_name = st.session_state.plane.name.replace(' ', '_')
        avl_path = f"{base_name}.avl"
        mass_path = f"{base_name}.mass"
        try:
            st.session_state.plane.to_avl_file(avl_path)
            st.session_state.plane.to_mass_file(mass_path)
            
            # Need to link the mass file in the AVL file conceptually, but usually user runs `mass file.mass` in AVL.
            st.success(f"✅ Successfully exported to `{avl_path}` and `{mass_path}`")
        except Exception as e:
            st.error(f"Export failed: {e}")

with col_viewer:
    st.markdown("<div style='background-color: white; border-radius: 10px; padding: 10px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);'>", unsafe_allow_html=True)
    # The 3D plot dynamically renders based on the exact state of the plane
    fig = render_plane_3d(st.session_state.plane)
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': True})
    st.markdown("</div>", unsafe_allow_html=True)
