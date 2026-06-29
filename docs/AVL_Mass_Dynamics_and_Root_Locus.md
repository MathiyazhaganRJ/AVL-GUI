# AVL Mass Inclusive Dynamic Simulation & Root Locus Guide

While the `.OPER` menu solves for static aerodynamic trim, the `.MODE` menu invokes AVL's internal 6-DOF physics engine to calculate the actual dynamic motion (Eigenvalues and Root Locus) of the aircraft over time. 

To perform this analysis, AVL must merge the aerodynamic stability derivatives with the physical inertia of the airframe.

---

## 1. The `.mass` File (The Rigid Body Definition)
To calculate a Root Locus, you must provide AVL with a `.mass` file. This file tells AVL how heavy the aircraft is and exactly how that mass is distributed.

*   **Mass ($m$):** Used to calculate acceleration ($F=ma$).
*   **CG Location ($X_{cg}, Y_{cg}, Z_{cg}$):** The pivot point for all rotational dynamics.
*   **Inertia Tensor ($I_{xx}, I_{yy}, I_{zz}$):** The rotational resistance. A heavy battery in the nose massively increases $I_{yy}$ (pitch inertia) and $I_{zz}$ (yaw inertia), directly altering the Short Period and Dutch Roll frequencies.

---

## 2. The Dynamic Analysis Workflow
You cannot enter the `.MODE` menu until you have successfully "trimmed" the aircraft in `.OPER`. The dynamic modes are calculated *around* a specific equilibrium flight state.

### Step-by-Step Execution:
1.  **Load Files:** `LOAD plane.avl` and `MASS plane.mass`.
2.  **Trim the Aircraft:** 
    *   Type `OPER` to enter the operations menu.
    *   Set a cruise state (e.g., `A` for Alpha = 2.0).
    *   Trim the elevator (`D1` -> `pm 0`).
    *   Type `X` to execute. **(CRITICAL: The aircraft must be fully trimmed ($C_m=0, C_l=0, C_n=0$) for the Root Locus to be valid).**
3.  **Enter Mode Solver:** 
    *   Hit Enter to return to the main menu, then type `MODE`.
4.  **Calculate Eigenvalues:**
    *   Type `N` (Calculate Eigenvalues). AVL will output the mathematical poles (Eigenvalues) for the Phugoid, Short Period, Dutch Roll, Roll Subsidence, and Spiral modes directly to the terminal.
5.  **Plot the Root Locus:**
    *   Type `P` (Plot root locus). AVL will open an interactive graphical plot showing the poles on the Complex Plane. (Note: You can type `B` to blow up/zoom the window, and `R` to reset it to normal size).

---

## 3. Interpreting the Root Locus & Mode Behaviors

When you plot the Root Locus (or read the Eigenvalues), the poles are plotted on a grid with a **Real Axis (X)** and an **Imaginary Axis (Y)**.

### The Mathematics of the Grid:
*   **Real Axis (Left side / Negative):** Determines **Damping**. The further left the point is, the faster the motion decays and stabilizes.
*   **Real Axis (Right side / Positive):** **DANGER!** Any point on the right side of the Y-axis means the aircraft is dynamically unstable and will diverge (crash) exponentially over time.
*   **Imaginary Axis (Up/Down):** Determines **Frequency** (Oscillation). If a mode has points above and below the X-axis (a conjugate pair), the aircraft will physically oscillate or wobble.

### The 5 Classical Modes:

1.  **Short Period Mode (Pitch):** 
    *   *Root Locus location:* Two points far to the left, slightly off the X-axis.
    *   *Behavior:* A very fast, heavily damped pitch oscillation. When hit by a gust, the nose jerks up and snaps back to level almost instantly.
2.  **Phugoid Mode (Pitch):**
    *   *Root Locus location:* Two points very close to the Y-axis, near the origin.
    *   *Behavior:* A slow, lumbering exchange of altitude and airspeed. Because it is so close to the Y-axis, it has very little aerodynamic damping and can take minutes to decay.
3.  **Dutch Roll (Yaw/Roll):**
    *   *Root Locus location:* Two points moderately to the left, significantly high up on the Y-axis.
    *   *Behavior:* A coupled, highly oscillatory "tail wagging" and wing-rocking motion. 
4.  **Roll Subsidence (Roll):**
    *   *Root Locus location:* A single point sitting directly on the far-left X-axis.
    *   *Behavior:* Non-oscillatory. It represents the aerodynamic roll damping ($C_{l_p}$) instantly catching the aircraft and stopping the roll rate when you let go of the ailerons.
5.  **Spiral Divergence (Yaw/Roll):**
    *   *Root Locus location:* A single point sitting very close to the origin. (If it slips into the positive right side, the plane is spirally unstable!)
    *   *Behavior:* Non-oscillatory. A slow tendency for the aircraft to over-bank itself into a steeper and steeper turning dive. Almost all aircraft are slightly spirally unstable; the pilot simply corrects it without noticing.
