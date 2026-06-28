# The Physics of Rotation Rates in AVL

In flight dynamics, an airplane doesn't just move in straight lines—it constantly rotates. AVL represents these rotations as **Non-Dimensional Rates** (`pb/2V`, `qc/2V`, `rb/2V`). 

Understanding these three variables is the key to understanding how an airplane actually flies through the air, especially in a thermal.

---

## 1. Pitch Rate (`qc/2V`)
*The rate at which the nose is sweeping "up" or "down" relative to the pilot's head.*

*   **The Physics:** Pitch rate is NOT climbing. It is pure rotation. If you fly perfectly level but pull back on the elevator to do a backflip, your pitch rate is massive, even before you start climbing.
*   **The Thermal Glider Example:** In a banked turn (like circling a thermal), you must constantly pull back on the elevator just to keep the nose from dropping. Because you are constantly pulling back, the airplane is constantly rotating its nose "upward" relative to its own wings. Therefore, **you cannot turn in a circle without a positive Pitch Rate!**
*   **Aerodynamic Effect:** Because the airplane is rotating, the tail is sweeping downward through the air. This creates "Pitch Damping" (drag on the tail), which means you need to trim extra Up-Elevator to hold the turn.

## 2. Roll Rate (`pb/2V`)
*The rate at which the wings are banking or flipping over.*

*   **The Physics:** When you apply ailerons, the airplane accelerates into a roll. As it spins faster, the wings smash into the air, creating Roll Damping. The Roll Rate stabilizes when the Aileron force is perfectly cancelled out by the Roll Damping.
*   **The Thermal Glider Example:** In a steady thermal turn, you hold a constant 30-degree bank. Because the bank angle is locked and not changing, your **Roll Rate = 0.0**, even though you are turning!

## 3. Yaw Rate (`rb/2V`)
*The rate at which the nose is sweeping left or right across the horizon.*

*   **The Physics:** Think of the airplane sitting flat on a turntable like a vinyl record. If you spin the turntable, that motion is Yaw Rate. 
*   **The Thermal Glider Example:** When you bank the airplane, the tilted lift vector pulls the glider into a circular path. Because it is flying in a circle, the nose must constantly sweep across the horizon to follow the curve. This means **the Bank Angle physically induces the Yaw Rate!**
*   **Aerodynamic Effect (Roll Due to Yaw):** Because the airplane is spinning on the turntable, the wing on the *outside* of the turn is moving faster through the air than the inside wing. Faster air = More Lift. This extra lift causes the airplane to roll further into the turn! (This is why you have to hold slight opposite aileron while thermalling).

---

## What are the "Dashed/Primed" Variables? (`p'b/2V` and `r'b/2V`)

In AVL outputs, you will see two versions of Roll and Yaw rates:
*   `pb/2V` and `rb/2V` (Body Axis)
*   `p'b/2V` and `r'b/2V` (Stability Axis - note the little `'` prime symbol)

**The Difference:**
If your airplane is flying at a high Angle of Attack (Alpha), the physical fuselage is pointing slightly up into the sky, but the *wind* is coming straight horizontally.

*   **Body Axis (Unprimed):** Measures rotation exactly relative to the physical carbon-fiber fuselage. 
*   **Stability Axis (Primed):** Measures rotation exactly relative to the *oncoming wind*.

**Why it matters:** 
If you have a high Angle of Attack and you yaw the airplane left (Body Axis Yaw), the nose doesn't just swing left—because it's tilted up, it actually sweeps in an arc that causes the wings to tilt relative to the wind! So a pure Yaw in the Body Axis actually creates a phantom "Roll" relative to the wind. The primed variables (`p'` and `r'`) do the complex trigonometry to show you exactly how the airplane is rotating relative to the airmass itself, which is critical for predicting spins and stalls!
