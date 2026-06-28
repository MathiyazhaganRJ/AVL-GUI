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
    dihedral: float = 0.0            # Dihedral angle to the NEXT section
    twist: float = 0.0               # Pitch angle / incidence of this section
    airfoil: str = "NACA 0012"
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

        z_rel_accum = 0.0
        actual_y = []
        
        for i, sec in enumerate(self.sections):
            if i == 0:
                current_y = sec.y
            else:
                prev_sec = self.sections[i-1]
                d_span = sec.y - prev_sec.y
                
                if abs(sec.dihedral - 90.0) < 1.0:
                    z_rel_accum += d_span
                    current_y = actual_y[-1]
                else:
                    z_rel_accum += d_span * np.tan(np.radians(sec.dihedral))
                    current_y = actual_y[-1] + d_span
            
            actual_y.append(current_y)

            # Apply Surface Incidence (pitch around surface origin)
            x_rot = self.origin[0] + sec.offset_x * cos_inc - z_rel_accum * sin_inc
            z_rot = self.origin[2] + sec.offset_x * sin_inc + z_rel_accum * cos_inc
            
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
            f"10 1.0" # Nchord, Cspace
        ]
        
        if self.duplicate_y:
            lines.extend(["YDUPLICATE", "0.0"])
            
        lines.extend([f"ANGLE", f"{self.incidence:.4f}"])
        
        # Calculate AVL relative Z coordinates (un-rotated by incidence)
        z_rel_accum = 0.0
        actual_y = []
        
        for i, sec in enumerate(self.sections):
            if i == 0:
                current_y = sec.y
            else:
                prev_sec = self.sections[i-1]
                d_span = sec.y - prev_sec.y
                if abs(sec.dihedral - 90.0) < 1.0:
                    z_rel_accum += d_span
                    current_y = actual_y[-1]
                else:
                    z_rel_accum += d_span * np.tan(np.radians(sec.dihedral))
                    current_y = actual_y[-1] + d_span
                    
            actual_y.append(current_y)
                    
            x_abs = self.origin[0] + sec.offset_x
            z_abs = self.origin[2] + z_rel_accum
            
            # Nspan and Sspace logic (0 for tip section)
            nspan = 5 if i < len(self.sections) - 1 else 0
            sspace = -2.0 if i < len(self.sections) - 1 else 0.0
            
            lines.append(f"SECTION")
            lines.append(f"{x_abs:.4f} {self.origin[1] + current_y:.4f} {z_abs:.4f} {sec.chord:.4f} {sec.twist:.4f} {nspan} {sspace}")
            
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
    s_ref: float = 1.0
    c_ref: float = 1.0
    b_ref: float = 1.0
    cg: Tuple[float, float, float] = (0.0, 0.0, 0.0)
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

    def to_mass_string(self) -> str:
        """Returns the AVL .mass file content as a string."""
        lines = [
            f"# Mass & Inertia file for {self.name}",
            f"Lunit = 1.0 m",
            f"Munit = 1.0 kg",
            f"Tunit = 1.0 s",
            f"",
            f"g   = 9.81",
            f"rho = 1.225",
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
            "0.0",
            "0 0 0.0",
            f"{self.s_ref:.4f} {self.c_ref:.4f} {self.b_ref:.4f}",
            f"{self.cg[0]:.4f} {self.cg[1]:.4f} {self.cg[2]:.4f}",
            "0.01" # Cdp
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
            Section(y=1.2, chord=0.25, offset_x=0.25, twist=-2.0, dihedral=2.0, control=ControlSurface("Aileron", 0.75, -1))
        ]
    )
    
    plane = Airplane("Robust_Plane", s_ref=0.8, c_ref=0.35, b_ref=2.4, cg=(0.1, 0.0, 0.0), surfaces=[wing])
    plane.to_avl_file("robust_plane_test.avl")
    print(f"Generated robust_plane_test.avl successfully with {len(wing.generate_3d_mesh())} section coordinates calculated.")
