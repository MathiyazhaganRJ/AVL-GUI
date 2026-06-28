# ATHENA VORTEX LATTICE (AVL) 
## AERODYNAMIC DESIGN AND VALIDATION MANUAL

### PREFACE & ACKNOWLEDGEMENTS
This manual and the accompanying graphical interface are built upon the foundational work of **Dr. Mark Drela** and **Harold Youngren** of the Massachusetts Institute of Technology (MIT). Athena Vortex Lattice (AVL) remains a cornerstone of preliminary aircraft design, providing aerodynamicists with an incredibly powerful, mathematically rigorous tool for analyzing the flight dynamics of rigid aircraft. 

The purpose of this document is for me to use AVL properly to its full potential, extracting critical stability derivatives, sizing control surfaces, and predicting dynamic modal responses before an aircraft ever leaves the ground. We owe the success of countless aerospace projects to the robust vortex lattice framework they established.

---

### 1.0 THEORETICAL BASIS & LIMITATIONS

AVL employs an extended vortex lattice model (VLM) for the calculation of aerodynamic forces and moments. Lifting surfaces are discretized into horseshoe vortices. Induced drag is calculated via Trefftz-plane analysis, ensuring high fidelity for spanwise efficiency metrics.

**Fundamental Limitations:**
*   **Inviscid Flow:** AVL assumes inviscid, incompressible flow (with Prandtl-Glauert compressibility corrections). It does not natively predict viscous profile drag.
*   **No Flow Separation:** The solver assumes fully attached flow. AVL cannot predict stall behavior or maximum lift boundaries (Cl_max).
*   **Linear Scaling:** Results near extreme limits (e.g., very high angles of attack) are non-physical. Empirical viscous data (via XFOIL) must be externally supplied to account for profile drag.

---

### 2.0 CORE AERODYNAMIC ANALYSES

The following methodologies define the standard suite of aerodynamic tests that should be executed within the AVL environment to validate an aircraft design.

#### 2.1 Longitudinal Static Stability Test (Alpha Sweep)
**Objective:** Determine the aerodynamic center (neutral point) and validate restoring pitch stability.
*   **Methodology:** Fix sideslip (Beta = 0) and all rotation rates (P, Q, R = 0). Sweep the angle of attack (Alpha) across the operational envelope.
*   **Evaluation Criteria:** 
    *   The slope of the pitching moment curve (dCm/da) must be strictly negative.
    *   The Center of Gravity (CG) must be located forward of the Neutral Point (Xnp). The difference (Xnp - Xcg) divided by the mean aerodynamic chord is the Static Margin, which should nominally fall between 5% and 15%.

#### 2.2 Lateral-Directional Static Stability Test (Beta Sweep)
**Objective:** Validate weather-cocking (directional) stability and dihedral effect (lateral stability).
*   **Methodology:** Fix angle of attack (Alpha) at the cruise state. Sweep the sideslip angle (Beta) from -10 to +10 degrees.
*   **Evaluation Criteria:**
    *   **Directional Stability (Cn_beta > 0):** The yawing moment must oppose the sideslip. If this fails, the vertical tail volume must be increased.
    *   **Dihedral Effect (Cl_beta < 0):** The rolling moment must induce a roll away from the sideslip. 

#### 2.3 Control Authority and Trim Sizing
**Objective:** Ensure control surfaces possess sufficient aerodynamic volume to achieve trim across the flight envelope without approaching deflection limits.
*   **Methodology:** In the OPER menu, constrain the Lift Coefficient (CL) to the target cruise value. Constrain the Pitching Moment (PM) to exactly 0.0. Assign the Elevator as the free variable.
*   **Evaluation Criteria:** AVL will output the required elevator deflection (delta_e). If the magnitude exceeds 10 degrees for steady cruise, the tail volume is inadequate or the CG is improperly placed, resulting in excessive trim drag.

#### 2.4 Spanwise Load Optimization (Trefftz Plane Analysis)
**Objective:** Minimize induced drag (CDi) by optimizing the geometric twist and taper ratio.
*   **Methodology:** Execute a single-point trim at the design cruise CL. Utilize the strip forces (fs) command to plot the spanwise load distribution.
*   **Evaluation Criteria:** 
    *   For optimal induced efficiency, the spanwise lift curve should approach an elliptical distribution.
    *   The local lift coefficient (Cl) should peak inboard of the wingtips to ensure that root-stall precedes tip-stall, preserving aileron authority near stall limits.

#### 2.5 Dynamic Stability (Eigenmode Analysis)
**Objective:** Quantify the time-domain oscillatory characteristics of the unpiloted airframe.
*   **Methodology:** Populate the `.mass` file with high-fidelity point mass locations to construct the inertia matrix. Trim the aircraft in OPER, then execute the eigenvalue solver in the MODE menu.
*   **Evaluation Criteria:**
    *   **Phugoid & Short Period:** Real components of the eigenvalues must be negative. 
    *   **Dutch Roll:** Often lightly damped in UAVs. If the real component is positive (unstable), vertical tail volume must be increased or an active yaw damper implemented.
    *   **Spiral Mode:** A slightly positive real component (slow divergence) is universally acceptable, as it is easily compensated by the flight controller.

#### 2.6 Steady Coordinated Turn Analysis
**Objective:** Calculate the exact control surface deflections required to maintain a steady, constant-altitude bank angle.
*   **Methodology:** 
    1. Calculate the turn rate: Omega = (g * tan(Phi)) / V (where Phi is bank angle, V is velocity).
    2. Resolve rotation rates: Pitch Rate (q) = Omega * sin(Phi), Yaw Rate (r) = Omega * cos(Phi).
    3. Input q and r into AVL as non-dimensional variables (qc/2V and rb/2V).
    4. Constrain Roll Rate to 0, Sideslip to 0. Constrain all moments (PM, RM, YM) to 0.
    5. Allow AVL to solve for Aileron, Elevator, and Rudder deflections.
*   **Evaluation Criteria:** Confirms if servo maximum deflections are exceeded during steep loiter maneuvers.

#### 2.7 Steady State Roll Performance
**Objective:** Determine the maximum achievable roll rate for a given aileron deflection.
*   **Methodology:** Constrain the Aileron to its maximum deflection limit (e.g., 20 degrees). Constrain the Rolling Moment (RM) to 0.0, and allow AVL to solve for the Roll Rate (pb/2V).
*   **Evaluation Criteria:** Non-dimensional roll rate is converted back to degrees/second to ensure the airframe meets agility requirements.

#### 2.8 Hinge Moment Estimation (Servo Sizing)
**Objective:** Calculate the aerodynamic torque applied to the control surfaces to appropriately size electromechanical servos.
*   **Methodology:** Define the hinge line fraction (Xhinge) in the geometry file. Run the aircraft at the maximum design dive speed (Vne) with maximum control deflections.
*   **Evaluation Criteria:** Extract the hinge moment coefficient (Ch). Servo torque is calculated as: Torque = Ch * dynamic_pressure * control_area * control_chord.

#### 2.9 Asymmetric Thrust Control (Engine-Out)
**Objective:** Define the Minimum Control Speed (Vmc) following a unilateral propulsion failure.
*   **Methodology:** Apply an external asymmetric drag or yawing moment corresponding to the dead engine. Constrain the aircraft to straight flight (Sideslip = 0). Force AVL to solve for the Rudder deflection required to balance the yawing moment.
*   **Evaluation Criteria:** If the required rudder deflection exceeds the geometric limits, the vertical tail is undersized for the proposed engine baseline.

#### 2.10 Ground Effect Simulation
**Objective:** Quantify the reduction in induced drag and shift in aerodynamic center during landing flare.
*   **Methodology:** Set the Zsym parameter to 1.0 in the main `.avl` file. Offset the aircraft Z-coordinates to represent the height above the runway (e.g., Z = +2.0). 
*   **Evaluation Criteria:** AVL mirrors the geometry across the Z=0 plane. Expect a notable increase in lift curve slope and a reduction in induced drag (CDi), useful for predicting landing "float".
