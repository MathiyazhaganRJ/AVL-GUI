# 3D Rendering Engines Available

The AVL GUI apps support multiple 3D rendering engines for visualizing aircraft geometry.

## Currently Implemented

### 1. **Plotly (Interactive)** ✅ Default
- **Library:** `plotly` (already installed)
- **Features:**
  - Fully interactive: rotate, zoom, pan with mouse
  - Smooth mesh rendering with lighting
  - Control surfaces highlighted in orange
  - Edge lines for clarity
  - Works in browser (WebGL)
- **Best for:** Interactive exploration, presentations
- **Camera presets:** Default, Top, Front, Side, Isometric

### 2. **Matplotlib 3D** ✅
- **Library:** `matplotlib` (already installed, uses `mpl_toolkits.mplot3d`)
- **Features:**
  - Wireframe + scatter points
  - Clean line-drawing style
  - Good for technical documentation
  - Can export high-res PNG
- **Best for:** Static figures, reports, publications
- **Camera presets:** Default, Top, Front, Side, Isometric (via `view_init`)

### 3. **PyVista (VTK)** ✅ Optional
- **Library:** `pyvista` (install with `pip install pyvista`)
- **Features:**
  - High-quality mesh rendering (VTK backend)
  - Professional visualization
  - Edge highlighting
  - Renders to image (screenshot)
- **Best for:** High-quality static images, advanced mesh visualization
- **Installation:** `pip install pyvista`
- **Note:** Only appears in engine list if installed

## Other Available Options (Not Yet Implemented)

### 4. **Open3D**
- **Library:** `open3d`
- **Features:** Point clouds, mesh processing, advanced rendering
- **Use case:** Point cloud visualization, mesh analysis
- **Installation:** `pip install open3d`

### 5. **Bokeh 3D**
- **Library:** `bokeh`
- **Features:** Web-based 3D plots, interactive widgets
- **Use case:** Dashboards with 3D + controls
- **Installation:** `pip install bokeh`

### 6. **Mayavi**
- **Library:** `mayavi`
- **Features:** Scientific 3D visualization (VTK-based)
- **Use case:** Complex scientific visualizations
- **Installation:** `pip install mayavi`
- **Note:** Can be heavy; PyVista is lighter alternative

### 7. **Three.js via pydeck**
- **Library:** `pydeck` (Deck.gl)
- **Features:** WebGL 3D, geospatial focus
- **Use case:** 3D maps, geospatial data
- **Installation:** `pip install pydeck`

### 8. **VTK (Direct)**
- **Library:** `vtk`
- **Features:** Low-level VTK access
- **Use case:** Custom rendering pipelines
- **Installation:** `pip install vtk`
- **Note:** PyVista wraps VTK more easily

## Usage

In both **avl_rj_improved.py** and **avl_rj_v2.py**:

1. Go to **3D View** / **3D Interactive** tab
2. Select **Camera** preset (Default, Top, Front, Side, Isometric)
3. Choose **3D engine**:
   - **Plotly (interactive)** — always available
   - **Matplotlib 3D** — always available
   - **PyVista (VTK)** — appears if `pyvista` is installed

## Recommendations

- **For interactive exploration:** Use **Plotly**
- **For documentation/reports:** Use **Matplotlib 3D** or **PyVista**
- **For highest quality:** Install and use **PyVista**

## Adding More Engines

To add another engine (e.g., Open3D):

1. Add rendering function: `plot_3d_open3d(data_dict, show_mass, view_preset)`
2. Check import: `try: import open3d; engine_options.append("Open3D")`
3. Add rendering call in the UI tab
4. Update this document
