# AVL Input File Generator — Streamlit GUI

A universal GUI for generating **Athena Vortex Lattice (AVL)** input files.

## Features

- **Global parameters**: Mach, inertias (Iy, Iz, Ixz), mass, gravity, CDp; reference values (Sref, Cref, Bref, Xref, Yref, Zref).
- **Dynamic surfaces**: Add, remove, and edit an unlimited number of lifting surfaces (wing, H-stab, V-stab, canard, etc.).
- **Section & geometry**: Per-surface sections with LE (X,Y,Z), chord, incidence, airfoil (NACA 4-digit or .dat), spanwise spacing.
- **Control surfaces**: Optional controls per section (name, gain, hinge x/c, sign duplicate).
- **Top-down (X–Y) plot**: Live geometry preview for tail arm and layout check.
- **AVL file export**: Strict AVL syntax with a download button for `aircraft.avl`.

## Setup

```bash
cd avl_gui
pip install -r requirements.txt
streamlit run app.py
```

## Usage

1. Set **Global Parameters** and **Reference Values** in the sidebar.
2. Use **Add Surface** to create lifting surfaces; edit **Component**, **Y-Duplicate**, **Angle** per surface.
3. For each surface, add **Sections** (root, break, tip) with LE, chord, incidence, airfoil, Nspan.
4. Optionally add **Control Surface** to sections (elevator, aileron, rudder, etc.).
5. Check the **Top-Down View** to verify geometry and tail arm.
6. Click **Generate & Download aircraft.avl** to save the file.

## Tech Stack

Python, Streamlit, NumPy, Matplotlib.

---

## RJ Aero version (improved)

An alternative app with 3D/2D views, mass/CG, and AVL launch is in `avl_rj_improved.py`. Run with:

```bash
pip install -r requirements_rj.txt
streamlit run avl_rj_improved.py
```

Improvements over the original RJ app: AVL export uses **CG for Xref,Yref,Zref**; **YDUPLICATE** only when symmetry is on (no invalid `NOYDUPLICATE`); **SECTION** lines use valid Nspan/Sspace; clearer error handling on load.

### v2 — XFLR5-style layout

Run the XFLR5-style interface (same backend, new GUI):

```bash
streamlit run avl_rj_v2.py
```

- **Sidebar:** Design tree — Plane Definition, Main Wing, H-Tail, V-Tail, Mass & Inertia, Flight Condition. Select a component to edit.
- **Main:** Input panel (left) for the selected component; Output tabs (right): **3D View**, **2D Blueprints**, **Wing Data**, **Export** (refs + download .AVL/.MASS/.RUN + Open AVL).
- Original app remains **avl_rj_improved.py** (unchanged).
