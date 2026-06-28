import subprocess
import os
import re
from typing import Dict, Any, Optional

def run_avl_analysis(avl_file: str, mass_file: Optional[str] = None, alpha: float = 0.0) -> Dict[str, Any]:
    """
    Runs avl.exe using the specified geometry and mass files.
    Calculates stability derivatives at the given angle of attack.
    Returns a dictionary of parsed aerodynamic parameters.
    """
    # Ensure paths are absolute for safety
    base_dir = os.path.dirname(os.path.abspath(__file__))
    avl_exe = os.path.join(base_dir, "avl.exe")
    
    if not os.path.exists(avl_exe):
        raise FileNotFoundError(f"avl.exe not found at {avl_exe}. Please ensure the executable is present.")

    st_file_rel = "current_run.st"
    st_file_abs = os.path.join(base_dir, st_file_rel)
    
    # Clean up previous run files if they exist
    if os.path.exists(st_file_abs):
        os.remove(st_file_abs)

    # Build the sequence of commands to pipe into AVL
    avl_basename = os.path.basename(avl_file)
    commands = [
        f"load {avl_basename}"
    ]
    
    if mass_file and os.path.exists(mass_file):
        mass_basename = os.path.basename(mass_file)
        commands.append(f"mass {mass_basename}")
        commands.append("mset 0")  # Apply mass uniformly to all surfaces

    commands.extend([
        "oper",             # Enter OPER sub-menu
        f"a a {alpha}",     # Set Angle of Attack (Alpha)
        "x",                # Execute calculation
        f"st {st_file_rel}", # Save stability derivatives to file
        "O",                # Overwrite if asked (though we deleted it)
        "",                 # Return to main menu
        "quit"              # Exit AVL
    ])
    
    command_str = "\n".join(commands) + "\n"

    # Run AVL invisibly in the background
    try:
        process = subprocess.Popen(
            [avl_exe],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=base_dir,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        stdout, stderr = process.communicate(input=command_str, timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        raise Exception("AVL execution timed out. The geometry might be invalid causing an infinite loop.")
    except Exception as e:
        raise Exception(f"Failed to run AVL: {str(e)}")

    # Parse the output .st file
    try:
        return parse_stability_file(st_file_abs)
    except FileNotFoundError:
        print("--- AVL STDOUT ---")
        print(stdout)
        print("--- AVL STDERR ---")
        print(stderr)
        raise Exception("AVL crashed or rejected the geometry.")


def parse_stability_file(filepath: str) -> Dict[str, Any]:
    """
    Parses the AVL .st file and extracts key aerodynamic coefficients.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError("AVL failed to generate the stability file (.st). Check geometry for errors.")
        
    results = {}
    
    with open(filepath, 'r') as f:
        content = f.read()
        
    # Extract Alpha
    alpha_match = re.search(r'Alpha\s*=\s*([-0-9.]+)', content)
    if alpha_match: results['Alpha'] = float(alpha_match.group(1))
    
    # Extract Core Lift, Drag, and Moment Coefficients
    cl_match = re.search(r'CLtot\s*=\s*([-0-9.]+)', content)
    if cl_match: results['CL'] = float(cl_match.group(1))
    
    cd_match = re.search(r'CDtot\s*=\s*([-0-9.]+)', content)
    if cd_match: results['CD'] = float(cd_match.group(1))
        
    cm_match = re.search(r'Cmtot\s*=\s*([-0-9.]+)', content)
    if cm_match: results['Cm'] = float(cm_match.group(1))
        
    # Extract Neutral Point and Static Margin
    np_match = re.search(r'Neutral point\s*Xnp\s*=\s*([-0-9.]+)', content)
    if np_match: results['Xnp'] = float(np_match.group(1))
    
    # Extract Efficiency Factor (Oswald)
    e_match = re.search(r'Span ef\.\s*e\s*=\s*([-0-9.]+)', content)
    if e_match: results['Oswald_e'] = float(e_match.group(1))
        
    # Extract Stability Derivatives
    cla_match = re.search(r'CLa\s*=\s*([-0-9.]+)', content)
    if cla_match: results['CLa'] = float(cla_match.group(1))
        
    cma_match = re.search(r'Cma\s*=\s*([-0-9.]+)', content)
    if cma_match: results['Cma'] = float(cma_match.group(1))

    return results

if __name__ == "__main__":
    # Quick debug test if run directly
    print("Testing AVL Runner...")
    try:
        data = run_avl_analysis("plane.avl", "plane.mass", alpha=5.0)
        print("Success! Parsed Data:")
        for k, v in data.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"Error: {e}")
