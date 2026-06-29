# AVL Flight Envelope & Simulation Protocols

The true power of AVL lies in its mathematical constraint solver (the `.OPER` menu). By linking different variables to different moments, you can force AVL to simulate highly complex, real-world flight scenarios.

Below are the most critical simulation protocols (constraint matrices) used by aerospace engineers to extract flight dynamics behavior.

---

## Scenario 1: Straight & Level Cruise Trim
*Find the exact elevator deflection required to fly level at your target cruise speed/angle of attack.*

**Flight State Configuration:**
*   `Alpha` -> set to your cruise angle (e.g., `2.0` degrees)
*   `Elevator` -> constrain to `pm` (Pitching Moment) = `0.0`
*   **Result:** When you execute (`x`), AVL tells you the exact Elevator trim required. If the number is incredibly high (e.g., > 10 degrees), your CG is wrong or your tail is too small.

---

## Scenario 2: Maximum Steady Roll Rate
*Find out how fast your aircraft will spin if you jam the stick all the way to the side.*

**Flight State Configuration:**
*   `Aileron` -> set to your max physical deflection (e.g., `15.0` degrees)
*   `Roll rate (p)` -> constrain to `rm` (Rolling Moment) = `0.0`
*   **Result:** The `pb/2V` output is your maximum roll velocity. (It stops accelerating when aerodynamic damping perfectly cancels the aileron force).

---

## Scenario 3: The Coordinated Turn (Adverse Yaw)
*When you roll, drag on the down-going aileron pulls the nose the wrong way (Adverse Yaw). Find out exactly how much Rudder you need to mix in to fix it.*

**Flight State Configuration:**
*   `Aileron` -> set to `10.0`
*   `Roll rate (p)` -> constrain to `rm` (Rolling Moment) = `0.0`
*   `Rudder` -> constrain to `ym` (Yawing Moment) = `0.0`
*   **Result:** AVL calculates the max roll rate AND automatically deflects the Rudder just enough to keep the nose perfectly straight. You can program this exact ratio into your ArduPilot or RC transmitter as an "Aileron-to-Rudder Mix"!

---

## Scenario 4: Crosswind Landing (Steady Slip)
*You are landing in a heavy crosswind (Sideslip). Find out if you have enough rudder authority to keep the nose pointed at the runway, and enough aileron to keep the wing from flipping over.*

**Flight State Configuration:**
*   `Beta` -> set to a heavy crosswind angle (e.g., `10.0` degrees)
*   `Rudder` -> constrain to `ym` (Yawing Moment) = `0.0`
*   `Aileron` -> constrain to `rm` (Rolling Moment) = `0.0`
*   **Result:** The output will show exactly how much opposite Aileron and Rudder you must hold on the sticks. If AVL says you need `35` degrees of Rudder, but your servo only throws `20` degrees... you cannot safely land in that crosswind!

---

## Scenario 5: The Sustained Loop (High-G Pull-up)
*When pulling a tight loop, the plane rotates, meaning the tail sweeps downward through the air. Find out how much extra elevator you need to hold the loop.*

**Flight State Configuration:**
*   `Alpha` -> set to a high angle (e.g., `12.0` degrees, right before stall)
*   `Pitch rate (q)` -> set to a positive rotation rate (e.g., `0.05`)
*   `Elevator` -> constrain to `pm` (Pitching Moment) = `0.0`
*   **Result:** The calculated Elevator deflection will be significantly higher than Scenario 1 because it must fight the `Cmq` (Pitch Damping) caused by the loop rotation.

---

## Scenario 6: Engine-Out Asymmetric Thrust Trim
*If your multi-engine UAV loses a motor, you must fly with asymmetric thrust. Find out if your rudder is large enough to counter the off-center pulling force.*

**Flight State Configuration:**
*   `Alpha` -> set to cruise (e.g., `2.0` degrees)
*   `Rudder` -> constrain to `ym` (Yawing Moment) = `[Value of Asymmetric Thrust Moment]` (Calculate this manually: Thrust force * distance from centerline)
*   **Result:** AVL will trim the Rudder to counter the dead engine's yaw moment. If it hits the maximum physical throw of the rudder (e.g., > 25 deg), the aircraft is uncontrollable on one engine!

---

## Scenario 7: Banked Thermal Soaring (The C1 Command)
*Simulate the aircraft in a continuous, steady banked circle (like riding a thermal).*

**The Physics:** An aircraft in a steady banked turn does not just roll; it constantly pitches up to maintain altitude and constantly yaws to follow the circular path. This requires coupled rotational rates ($q$ and $r$).

**Flight State Configuration (The C1 Wizard):**
*   Inside the `.OPER` menu, type `C1`. 
*   AVL will prompt you for a `Bank Angle` (e.g., `30.0` degrees), a `Velocity` (or `C_L`), and the `Air Density`.
*   **Result:** AVL's internal kinematics engine instantly calculates the exact Pitch Rate ($q$) and Yaw Rate ($r$) required to perfectly trace that circle in 3D space. It automatically locks these rates into the state matrix. You can then constrain your Elevator to `pm 0` and Rudder to `ym 0` to see exactly what control deflections are required to hold the plane in that thermal.

---

## Scenario 8: Ground Effect (Landing Flare)
*Find out how much your induced drag decreases, and how your pitching moment shifts, when the plane is inches above the runway.*

**Flight State Configuration:**
*   You must configure this BEFORE entering `.OPER`. 
*   In the main AVL menu, type `g`.
*   Type `z` (to set Z-symmetry / ground plane). Type `0` to set the ground plane exactly at Z=0. (Make sure your airplane's Z-coordinates are shifted up to the landing gear height!)
*   Enter `.OPER` and run Scenario 1. 
*   **Result:** You will see your `CDind` drop massively, and your `Cma` change due to the downwash bouncing off the runway.

---

## Scenario 9: Steady Pitch Rate / High-G Loop (The C2 Command)
*Find out how much elevator authority you need to pull out of a steep dive or execute a sustained loop.*

**The Physics:** Pulling out of a dive requires a sustained pitch rate, generating massive pitch damping ($C_{m_q}$) across the tail that fights the elevator.

**Flight State Configuration (The C2 Wizard):**
*   Inside the `.OPER` menu, type `C2`.
*   AVL will prompt you for a `Velocity` and a `Load Factor` (e.g., `3.0` for 3 Gs) or a turn radius.
*   **Result:** AVL automatically calculates the required steady-state Pitch Rate ($q$) to sustain that load factor and locks it into the matrix. You can then constrain your Elevator to `pm 0` to verify if the control surface physically possesses enough authority to pull the requested Gs against the resulting aerodynamic damping.
