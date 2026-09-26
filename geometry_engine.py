from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import numpy as np

@dataclass
class ControlSurface:
    name: str
    hinge_x_c: float = 0.7  # Hinge location as fraction of chord
    sym: int = 1            # 1 for symmetric (elevator), -1 for anti-symmetric (aileron)

@dataclass
class PointMass:
    name: str
    mass: float
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

@dataclass
class Section:
    y: float = 0.0                   # Absolute Y (span) coordinate
    chord: float = 1.0               # Chord length (> 0)
    offset_x: float = 0.0            # Absolute X offset from root
    z: float = 0.0                   # Absolute Z coordinate
    twist: float = 0.0               # Pitch angle / incidence of this section
    airfoil: str = "NACA 0012"
    nspan: int = 5                   # Spanwise vortices to next section
    sspace: float = -2.0             # Spanwise spacing distribution
    control: Optional[ControlSurface] = None

    def __post_init__(self):
        if self.chord <= 0:
            raise ValueError(f"Chord must be positive, got {self.chord}")

@dataclass
class Surface:
    name: str
    origin: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    incidence: float = 0.0           # Angle of incidence for the whole surface
    duplicate_y: bool = True         # Symmetry across XZ plane
    nchord: int = 10                 # Chordwise vortices
    cspace: float = 1.0              # Chordwise spacing distribution
    sections: List[Section] = field(default_factory=list)

    def __post_init__(self):
        # Always ensure sections are sorted purely by Y-coordinate
        self.sections.sort(key=lambda s: s.y)

    def generate_3d_mesh(self) -> List[dict]:
        """
        Calculates the absolute 3D coordinates (X, Y, Z) for the leading and trailing edges, 
        incorporating dihedral, twist, and surface incidence robustly.
        """
        if not self.sections:
            return []

        coords = []
        inc_rad = np.radians(self.incidence)
        cos_inc = np.cos(inc_rad)
        sin_inc = np.sin(inc_rad)

        for i, sec in enumerate(self.sections):
            current_y = sec.y

            # Apply Surface Incidence (pitch around surface origin)
            x_rot = self.origin[0] + sec.offset_x * cos_inc - sec.z * sin_inc
            z_rot = self.origin[2] + sec.offset_x * sin_inc + sec.z * cos_inc
            
            # Twist kinematics (pitch around the section's leading edge)
            twist_rad = np.radians(sec.twist)
            x_te = x_rot + sec.chord * np.cos(twist_rad)
            z_te = z_rot - sec.chord * np.sin(twist_rad)
            
            # Control hinge coordinates (default to 0.7c if no control defined for visual continuity)
            hinge_frac = sec.control.hinge_x_c if sec.control else 0.7
            x_hinge = x_rot + sec.chord * hinge_frac * np.cos(twist_rad)
            z_hinge = z_rot - sec.chord * hinge_frac * np.sin(twist_rad)

            coords.append({
                "x_le": x_rot, "y": self.origin[1] + current_y, "z_le": z_rot,
                "x_te": x_te, "z_te": z_te,
                "x_hinge": x_hinge, "z_hinge": z_hinge,
                "chord": sec.chord, "airfoil": sec.airfoil,
                "ctrl_name": sec.control.name if sec.control else "",
                "ctrl_sym": sec.control.sym if sec.control else 0
            })
            
        return coords

    def to_avl_string(self) -> str:
        """Robustly generates the AVL text block for this specific surface."""
        if not self.sections:
            return ""
            
        lines = [
            f"SURFACE",
            f"{self.name}",
            f"{self.nchord} {self.cspace:.4f}" # Nchord, Cspace
        ]
        
        if self.duplicate_y:
            lines.extend(["YDUPLICATE", "0.0"])
            
        lines.extend([f"ANGLE", f"{self.incidence:.4f}"])
        
        for i, sec in enumerate(self.sections):
            x_abs = self.origin[0] + sec.offset_x
            z_abs = self.origin[2] + sec.z
            y_abs = self.origin[1] + sec.y
            
            # Nspan and Sspace logic (0 for tip section)
            nspan_val = sec.nspan if i < len(self.sections) - 1 else 0
            sspace_val = sec.sspace if i < len(self.sections) - 1 else 0.0
            
            lines.append(f"SECTION")
            lines.append(f"{x_abs:.4f} {y_abs:.4f} {z_abs:.4f} {sec.chord:.4f} {sec.twist:.4f} {nspan_val} {sspace_val:.4f}")
            
            # Airfoil handling
            af = sec.airfoil.strip()
            if af.upper().startswith("NACA"):
                naca_num = af.upper().replace('NACA', '').strip() or '0012'
                lines.extend(["NACA", naca_num])
            else:
                if not af.lower().endswith(".dat"):
                    af += ".dat"
                lines.extend(["AFILE", af])
                
            # Control handling
            if sec.control:
                lines.append(f"CONTROL")
                # Hinge vector (0 0 0) forces AVL to auto-calculate the correct hinge axis
                lines.append(f"{sec.control.name} 1.0 {sec.control.hinge_x_c:.4f} 0.0 0.0 0.0 {sec.control.sym}")
                
        return "\n".join(lines) + "\n"

@dataclass
class Airplane:
    name: str
    description: str = ""
    mach: float = 0.0
    iy_sym: int = 0
    iz_sym: int = 0
    z_sym: float = 0.0
    cdp: float = 0.01
    s_ref: float = 1.0
    c_ref: float = 1.0
    b_ref: float = 1.0
    cg: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    lunit: str = "1.0 m"
    munit: str = "1.0 kg"
    tunit: str = "1.0 s"
    g: float = 9.81
    rho: float = 1.225
    surfaces: List[Surface] = field(default_factory=list)
    point_masses: List[PointMass] = field(default_factory=list)

    def calculate_cg(self) -> Tuple[float, float, float]:
        """Calculates the center of gravity based on point masses."""
        if not self.point_masses:
            return (0.0, 0.0, 0.0)
        
        total_mass = sum(m.mass for m in self.point_masses)
        if total_mass <= 0:
            return (0.0, 0.0, 0.0)
            
        cg_x = sum(m.mass * m.x for m in self.point_masses) / total_mass
        cg_y = sum(m.mass * m.y for m in self.point_masses) / total_mass
        cg_z = sum(m.mass * m.z for m in self.point_masses) / total_mass
        
        self.cg = (cg_x, cg_y, cg_z)
        return self.cg


    @classmethod
    def parse_avl_file(cls, filepath: str) -> 'Airplane':
        with open(filepath, 'r') as f:
            lines = []
            for line in f:
                # Strip out comments starting with ! or #
                cleaned = line.split('!')[0].split('#')[0].strip()
                if cleaned:
                    lines.append(cleaned)
        
        if len(lines) < 6:
            raise ValueError("Invalid AVL file: Not enough header lines.")

        name = lines[0]
        mach = float(lines[1].split()[0])
        
        sym_parts = lines[2].split()
        iy_sym = int(float(sym_parts[0]))
        iz_sym = int(float(sym_parts[1]))
        z_sym = float(sym_parts[2])
        
        ref_parts = lines[3].split()
        s_ref = float(ref_parts[0])
        c_ref = float(ref_parts[1])
        b_ref = float(ref_parts[2])
        
        cg_parts = lines[4].split()
        cg = (float(cg_parts[0]), float(cg_parts[1]), float(cg_parts[2]))
        
        cdp = 0.0
        idx = 5
        try:
            if not lines[idx].upper().startswith(('SURFACE', 'BODY')):
                cdp = float(lines[idx].split()[0])
                idx += 1
        except Exception:
            pass

        plane = cls(name=name, mach=mach, iy_sym=iy_sym, iz_sym=iz_sym, z_sym=z_sym,
                         s_ref=s_ref, c_ref=c_ref, b_ref=b_ref, cg=cg, cdp=cdp)
        
        current_surf = None
        current_sec = None
        
        # Temp storage for Z values to calculate dihedral later
        z_vals = []

        while idx < len(lines):
            line = lines[idx]
            tokens = line.split()
            if not tokens:
                idx += 1
                continue
            keyword = tokens[0].upper()

            if keyword == "SURFACE":
                if current_surf:
                    plane.surfaces.append(current_surf)
                idx += 1
                surf_name = lines[idx]
                idx += 1
                nchord_cspace = lines[idx].split()
                nchord = int(float(nchord_cspace[0])) if len(nchord_cspace) > 0 else 10
                cspace = float(nchord_cspace[1]) if len(nchord_cspace) > 1 else 1.0
                current_surf = Surface(name=surf_name, nchord=nchord, cspace=cspace)
                current_surf.duplicate_y = False # Default to False, override if YDUPLICATE found
                current_sec = None
                current_scale = (1.0, 1.0, 1.0)
                z_vals = []
            elif keyword == "SCALE":
                if current_surf:
                    idx += 1
                    scales = lines[idx].split()
                    current_scale = (float(scales[0]), float(scales[1]), float(scales[2]))
            elif keyword == "YDUPLICATE":
                if current_surf:
                    current_surf.duplicate_y = True
            elif keyword == "ANGLE":
                if current_surf:
                    idx += 1
                    current_surf.incidence = float(lines[idx].split()[0])
            elif keyword == "TRANSLATE":
                if current_surf:
                    idx += 1
                    transl = lines[idx].split()
                    current_surf.origin = (float(transl[0]), float(transl[1]), float(transl[2]))
            elif keyword == "SECTION":
                idx += 1
                sec_params = lines[idx].split()
                x = float(sec_params[0]) * current_scale[0]
                y = float(sec_params[1]) * current_scale[1]
                z = float(sec_params[2]) * current_scale[2]
                chord = float(sec_params[3]) * current_scale[0]
                twist = float(sec_params[4])
                nspan = int(float(sec_params[5])) if len(sec_params) > 5 else 5
                sspace = float(sec_params[6]) if len(sec_params) > 6 else 1.0
                
                offset_x = x
                y_rel = y
                z_rel = z
                
                current_sec = Section(y=y_rel, chord=chord, offset_x=offset_x, z=z_rel, twist=twist, nspan=nspan, sspace=sspace)
                
                if current_surf:
                    current_surf.sections.append(current_sec)
            elif keyword == "NACA":
                idx += 1
                if current_sec:
                    current_sec.airfoil = f"NACA {lines[idx].strip()}"
            elif keyword == "AFILE" or keyword == "AFIL":
                idx += 1
                if current_sec:
                    current_sec.airfoil = lines[idx].strip()
            elif keyword == "CONTROL":
                idx += 1
                ctrl_params = lines[idx].split()
                cname = ctrl_params[0]
                gain = float(ctrl_params[1])
                xhinge = float(ctrl_params[2])
                sym = int(float(ctrl_params[6])) if len(ctrl_params) > 6 else 1
                if current_sec:
                    current_sec.control = ControlSurface(name=cname, hinge_x_c=xhinge, sym=sym)
            idx += 1
            
        if current_surf:
            plane.surfaces.append(current_surf)
            
        return plane


    @classmethod
    def parse_mass_file(cls, filepath: str, plane: 'Airplane') -> None:
        with open(filepath, 'r') as f:
            raw_lines = f.readlines()
            
        plane.point_masses = []
        
        m_mult, x_mult, y_mult, z_mult = 1.0, 1.0, 1.0, 1.0
        m_add, x_add, y_add, z_add = 0.0, 0.0, 0.0, 0.0
        
        for raw_line in raw_lines:
            line = raw_line.strip()
            if not line or line.startswith('#'): 
                continue
                
            if '=' in line:
                key = line.split('=')[0].strip().lower()
                val_str = line.split('=', 1)[1].split('!')[0].strip()
                if key == 'lunit': plane.lunit = val_str
                elif key == 'munit': plane.munit = val_str
                elif key == 'tunit': plane.tunit = val_str
                elif key == 'g': 
                    try: plane.g = float(val_str)
                    except ValueError: pass
                elif key == 'rho': 
                    try: plane.rho = float(val_str)
                    except ValueError: pass
                continue
                
            name = f"Mass {len(plane.point_masses)+1}"
            if '!' in line:
                name_part = line.split('!', 1)[1].strip()
                if name_part:
                    name = name_part
                line = line.split('!')[0].strip()
                
            tokens = line.split()
            if not tokens:
                continue
                
            if tokens[0] == '*':
                if len(tokens) >= 5:
                    m_mult, x_mult, y_mult, z_mult = float(tokens[1]), float(tokens[2]), float(tokens[3]), float(tokens[4])
                continue
            elif tokens[0] == '+':
                if len(tokens) >= 5:
                    m_add, x_add, y_add, z_add = float(tokens[1]), float(tokens[2]), float(tokens[3]), float(tokens[4])
                continue
                
            if len(tokens) >= 4:
                try:
                    mass = float(tokens[0]) * m_mult + m_add
                    x = float(tokens[1]) * x_mult + x_add
                    y = float(tokens[2]) * y_mult + y_add
                    z = float(tokens[3]) * z_mult + z_add
                    plane.point_masses.append(PointMass(name=name, mass=mass, x=x, y=y, z=z))
                except ValueError:
                    pass

    def to_mass_string(self) -> str:
        """Returns the AVL .mass file content as a string."""
        lines = [
            f"# Mass & Inertia file for {self.name}",
            f"Lunit = {self.lunit}",
            f"Munit = {self.munit}",
            f"Tunit = {self.tunit}",
            f"",
            f"g   = {self.g}",
            f"rho = {self.rho}",
            f"",
            f"#-------------------------",
            f"#  Mass    X      Y      Z      Ixx    Iyy    Izz    Ixy    Ixz    Iyz",
            f"*"
        ]
        
        for m in self.point_masses:
            lines.append(f"   {m.mass:.3f}   {m.x:.3f}   {m.y:.3f}   {m.z:.3f}   0.0    0.0    0.0    0.0    0.0    0.0   ! {m.name}")
            
        return "\n".join(lines) + "\n"

    def to_mass_file(self, filepath: str):
        """Generates the AVL .mass file for inertia analysis."""
        with open(filepath, "w") as f:
            f.write(self.to_mass_string())
            
    def to_avl_string(self) -> str:
        """Returns the AVL geometry file content as a string."""
        if self.point_masses:
            self.calculate_cg()
            
        lines = [
            self.name,
            f"{self.mach:.4f}",
            f"{self.iy_sym} {self.iz_sym} {self.z_sym:.4f}",
            f"{self.s_ref:.4f} {self.c_ref:.4f} {self.b_ref:.4f}",
            f"{self.cg[0]:.4f} {self.cg[1]:.4f} {self.cg[2]:.4f}",
            f"{self.cdp:.4f}"
        ]
        
        full_text = "\n".join(lines) + "\n"
        for surf in self.surfaces:
            full_text += surf.to_avl_string()
            
        return full_text

    def to_avl_file(self, filepath: str):
        with open(filepath, "w") as f:
            f.write(self.to_avl_string())

# --- Test Script ---
if __name__ == "__main__":
    wing = Surface(
        name="Main Wing",
        origin=(0.0, 0.0, 0.0),
        incidence=1.5,
        duplicate_y=True,
        sections=[
            Section(y=0.0, chord=0.45, twist=0.0, airfoil="NACA 2412"),
            Section(y=1.2, chord=0.25, offset_x=0.25, twist=-2.0, z=0.1, control=ControlSurface("Aileron", 0.75, -1))
        ]
    )
    
    plane = Airplane("Robust_Plane", s_ref=0.8, c_ref=0.35, b_ref=2.4, cg=(0.1, 0.0, 0.0), surfaces=[wing])
    plane.to_avl_file("robust_plane_test.avl")
    print(f"Generated robust_plane_test.avl successfully with {len(wing.generate_3d_mesh())} section coordinates calculated.")
