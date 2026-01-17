import streamlit as st
import pandas as pd
import numpy as np

# ==========================================
# 1. SCIENTIFIC ENGINE (The "Beardsley" Brain)
# ==========================================

class BeardsleyMath:
    """
    Core scientific calculations calibrated to provided data.
    """
    @staticmethod
    def get_rep_multiplier(reps):
        # 10 reps = Baseline (1.0). High reps = High Fatigue. Low reps = Low Fatigue.
        x = [1, 3, 5, 10, 15, 20]
        y = [0.14, 0.45, 0.72, 1.0, 1.55, 2.14] 
        return np.interp(reps, x, y)

    @staticmethod
    def get_rir_multiplier(rir):
        # 0 RIR = Baseline (1.0). Leaving reps in reserve saves significant recovery time.
        x = [0, 1, 2, 3, 4]
        y = [1.0, 0.77, 0.59, 0.45, 0.27]
        if rir > 4: return 0.2
        return np.interp(rir, x, y)

    @staticmethod
    def calculate_recovery_hours(sets, reps, rir, muscle_type, profile_type, recovery_capacity=1.0):
        # Baseline: 1 Set, 10 Reps, 0 RIR = 22.5 Hours recovery
        base_hours = 22.5
        
        rep_mult = BeardsleyMath.get_rep_multiplier(reps)
        rir_mult = BeardsleyMath.get_rir_multiplier(rir)
        
        # Muscle Damage Multipliers
        m_mult = 1.0
        if muscle_type == "Easily Damaged": m_mult = 1.5
        elif muscle_type == "Hardly Damaged": m_mult = 0.81
        
        # Profile Multipliers (Lengthened = More Damage)
        p_mult = 1.0
        if profile_type == "Lengthened": p_mult = 1.125
        elif profile_type == "Shortened": p_mult = 0.83
        
        raw_hours = sets * base_hours * rep_mult * rir_mult * m_mult * p_mult
        
        # Apply User's Recovery Capacity (Sleep/Stress factor)
        # If capacity is 0.8 (poor sleep), recovery takes longer (divide by 0.8)
        return raw_hours / recovery_capacity

    @staticmethod
    def calculate_wns(freq, sets, reps, rir, recovery_hours):
        # 1. Calculate Stimulus (Schoenfeld Curve)
        stim_reps = min(reps, max(0, 5 - rir))
        effective_sets = sets * (stim_reps / 5.0)
        
        if effective_sets <= 0: return 0
        gross_stim = (0.55 * np.log(max(0.1, effective_sets))) + 1.0
        
        # 2. Calculate Penalty & Atrophy
        cycle_hours = 168.0 / freq
        stimulus_duration = 48.0
        
        # Penalty if training before recovered
        penalty = 1.0
        if cycle_hours < recovery_hours:
            # Linear penalty for overlapping fatigue
            penalty = cycle_hours / recovery_hours
            
        # Atrophy if training too infrequent
        time_in_atrophy = max(0, cycle_hours - stimulus_duration)
        atrophy_loss = time_in_atrophy * 0.0134 # 0.322 AU / 24h
        
        net_workout = (gross_stim * penalty) - atrophy_loss
        return max(0, net_workout * freq)

class ConfigurationSolver:
    """
    The 'Solver' that iterates through sets/reps/rir to find the best combo.
    """
    @staticmethod
    def solve_for_best_volume(muscle, freq, time_limit_mins, is_priority, recovery_mod):
        # Define search space based on constraints
        # Priority muscles get allowed higher RPE (lower RIR)
        
        # Sets: 1 to 5 (or capped by time)
        max_sets = 5 if time_limit_mins >= 60 else 3
        possible_sets = range(1, max_sets + 1)
        
        # Reps: Standard Hypertrophy options
        possible_reps = [6, 8, 10, 12, 15]
        
        # RIR: 0-3 (Priority muscles allowed 0-1, others 1-3 to manage fatigue)
        possible_rir = [0, 1, 2] if is_priority else [1, 2, 3]
        
        best_config = None
        best_wns = -1
        
        m_data = MUSCLE_DATA[muscle]
        
        for s in possible_sets:
            for r in possible_reps:
                for rir in possible_rir:
                    
                    rec_hours = BeardsleyMath.calculate_recovery_hours(
                        s, r, rir, m_data["type"], m_data["profile"], recovery_mod
                    )
                    
                    wns = BeardsleyMath.calculate_wns(freq, s, r, rir, rec_hours)
                    
                    # Store if better
                    if wns > best_wns:
                        best_wns = wns
                        best_config = {
                            "Sets": s, "Reps": r, "RIR": rir, 
                            "Rec": rec_hours, "WNS": wns
                        }
        
        return best_config

# ==========================================
# 2. DATA
# ==========================================

MUSCLE_DATA = {
    "Chest": {"type": "Middle", "profile": "Lengthened"}, 
    "Back": {"type": "Middle", "profile": "Shortened"}, 
    "Quads": {"type": "Easily Damaged", "profile": "Lengthened"}, 
    "Hamstrings": {"type": "Easily Damaged", "profile": "Lengthened"}, 
    "Shoulders": {"type": "Hardly Damaged", "profile": "Shortened"}, 
    "Triceps": {"type": "Middle", "profile": "Even"},
    "Biceps": {"type": "Middle", "profile": "Lengthened"}, 
    "Calves": {"type": "Hardly Damaged", "profile": "Shortened"}
}

EXERCISE_MAP = {
    "Chest": ["Bench Press", "Incline DB Press", "Cable Fly"],
    "Back": ["Pull Up", "Barbell Row", "Lat Pulldown"],
    "Quads": ["Squat", "Leg Press", "Leg Extension"],
    "Hamstrings": ["RDL", "Seated Leg Curl", "Lying Leg Curl"],
    "Shoulders": ["Overhead Press", "Lateral Raise", "Rear Delt Fly"],
    "Triceps": ["Skull Crusher", "Pushdown", "Dip"],
    "Biceps": ["Barbell Curl", "Incline Curl", "Hammer Curl"],
    "Calves": ["Standing Calf Raise", "Seated Calf Raise"]
}

# ==========================================
# 3. STREAMLIT APP
# ==========================================

st.set_page_config(layout="wide", page_title="WNS Architect Pro")

st.title("🧬 WNS Architect Pro")
st.caption("Scientific Hypertrophy Solver based on Beardsley's Weekly Net Stimulus Model.")

tab1, tab2, tab3 = st.tabs(["🏗️ Program Generator", "🔍 Program Analyzer", "📈 Overload Tracker"])

# --- TAB 1: GENERATOR ---
with tab1:
    col_settings, col_results = st.columns([1, 2])
    
    with col_settings:
        st.subheader("1. Profile")
        level = st.selectbox("Experience", ["Beginner", "Intermediate", "Advanced"])
        minutes = st.number_input("Session Limit (mins)", 30, 180, 75, step=5)
        
        # New Feature: Recovery Mod
        st.subheader("2. Recovery Context")
        sleep_quality = st.select_slider("Sleep & Stress Levels", options=["Poor", "Average", "Good", "Perfect"], value="Average")
        rec_mod = {"Poor": 0.8, "Average": 1.0, "Good": 1.1, "Perfect": 1.2}[sleep_quality]
        
        st.subheader("3. Muscles")
        muscles = st.multiselect("Select Muscles", list(MUSCLE_DATA.keys()), default=["Chest", "Back", "Quads"])
        
        priorities = st.multiselect("Prioritize (Max 2)", muscles, max_selections=2, help="These muscles will be optimized for maximum stimulus, potentially using higher fatigue protocols.")
        
        st.subheader("4. Split Strategy")
        
        # Auto Toggle
        auto_split = st.checkbox("🤖 Auto-Split Optimizer", value=True, help="Automatically calculates the best Frequency and Split based on your specific muscle selection and recovery capacity.")
        
        if not auto_split:
            manual_split_type = st.selectbox("Split Structure", ["Upper/Lower", "Full Body", "Bro Split", "Push/Pull/Legs"])
            manual_freq = st.selectbox("Training Frequency (Total Days)", [1, 2, 3, 4, 5, 6], index=2)
            
            # Map structure to freq per muscle approximation
            # For simplicity in manual mode, we ask user "Frequency per Muscle"
            freq_per_muscle = st.slider("Frequency Per Muscle (Weekly)", 1, 4, 2, help="How often do you hit each muscle?")
        else:
            st.info("Optimizer will calculate the ideal frequency.")

        gen_btn = st.button("Generate Optimized Program", type="primary")

    with col_results:
        if gen_btn:
            st.divider()
            
            # 1. Determine Frequency
            final_freq = 0
            best_split_name = ""
            
            if auto_split:
                # Run Simulation for 1x, 2x, 3x
                scores = {}
                for f in [1, 2, 3]:
                    total_wns = 0
                    for m in muscles:
                        is_prio = m in priorities
                        # Solve for best WNS at this freq
                        cfg = ConfigurationSolver.solve_for_best_volume(m, f, minutes, is_prio, rec_mod)
                        total_wns += cfg["WNS"]
                    scores[f] = total_wns
                
                # Pick winner
                best_f = max(scores, key=scores.get)
                final_freq = best_f
                best_split_name = {1: "Bro Split", 2: "Upper/Lower (or PPL)", 3: "Full Body"}[best_f]
                
                st.success(f"🏆 **Optimal Strategy Found:** {best_split_name} ({final_freq}x Frequency)")
                with st.expander("See Optimizer Logic"):
                    st.write(f"Comparative WNS Scores: {scores}")
                    st.caption(f"Based on your recovery capacity ({sleep_quality}), this frequency allows the highest net stimulus.")
            else:
                final_freq = freq_per_muscle
                best_split_name = manual_split_type
                st.info(f"Using Manual Settings: {manual_split_type} ({final_freq}x Frequency per muscle)")

            # 2. Generate Data
            prog_data = []
            
            for m in muscles:
                is_prio = m in priorities
                
                # The SOLVER: Finds the exact Sets/Reps/RIR for this scenario
                best = ConfigurationSolver.solve_for_best_volume(m, final_freq, minutes, is_prio, rec_mod)
                
                # Check for warnings
                cycle_time = 168/final_freq
                status = "✅ Optimized"
                if best["Rec"] > cycle_time: 
                    # This shouldn't happen often with the solver, but possible if constraints are tight
                    status = "⚠️ Recovery Tight"
                
                prog_data.append({
                    "Muscle": m,
                    "Priority": "⭐" if is_prio else "-",
                    "Exercise": EXERCISE_MAP[m][0],
                    "Sets": best["Sets"],
                    "Reps": best["Reps"],
                    "RIR": best["RIR"],
                    "Est. Recovery": f"{int(best['Rec'])}h",
                    "WNS Score": round(best["WNS"], 2),
                    "Status": status
                })
            
            # Display
            df_res = pd.DataFrame(prog_data)
            st.dataframe(df_res, use_container_width=True)
            
            st.caption("Note: 'Sets' and 'Reps' are calculated dynamically to fit your recovery window. Priority muscles are allowed closer proximity to failure.")


# --- TAB 2: ANALYZER ---
with tab2:
    st.header("Program Audit")
    
    # Simple input method
    col_audit_in, col_audit_out = st.columns([1, 1])
    
    with col_audit_in:
        with st.form("audit_form"):
            st.write("Input a specific muscle scenario:")
            a_muscle = st.selectbox("Muscle", list(MUSCLE_DATA.keys()))
            a_sets = st.slider("Sets", 1, 10, 3)
            a_reps = st.slider("Reps", 1, 30, 10)
            a_rir = st.slider("RIR", 0, 5, 1)
            a_freq = st.slider("Frequency (Times/Week)", 1, 4, 2)
            audit_submit = st.form_submit_button("Analyze")
            
    with col_audit_out:
        if audit_submit:
            # Run Calcs
            m_data = MUSCLE_DATA[a_muscle]
            # Use average recovery mod
            rec = BeardsleyMath.calculate_recovery_hours(a_sets, a_reps, a_rir, m_data["type"], m_data["profile"], 1.0)
            
            eff_sets = a_sets * (min(a_reps, 5-a_rir)/5.0)
            gross = (0.55 * np.log(max(0.1, eff_sets))) + 1.0
            wns = BeardsleyMath.calculate_wns(a_freq, gross, rec, rec) # passing rec twice as dummy logic fix
            
            # Visuals
            st.metric("Weekly Net Stimulus", round(wns, 2))
            st.metric("Recovery Time", f"{int(rec)} hours")
            
            cycle_time = 168/a_freq
            if rec > cycle_time:
                st.error(f"❌ **Recovery Debt:** You need {int(rec)}h but only have {int(cycle_time)}h between sessions.")
            else:
                st.success("✅ Recoverable within frequency.")
            
            # Effective vs Junk
            eff_vol = round(eff_sets, 1)
            junk_vol = round(a_sets - eff_sets, 1)
            st.write(f"**Volume Quality:** {eff_vol} Effective Sets vs {junk_vol} Low-Stimulus Sets")


# --- TAB 3: OVERLOAD TRACKER ---
with tab3:
    st.header("Smart Progressive Overload")
    
    col_track1, col_track2 = st.columns(2)
    
    with col_track1:
        t_ex = st.selectbox("Exercise", EXERCISE_MAP["Chest"] + EXERCISE_MAP["Quads"]) # Simplified list
        t_weight = st.number_input("Last Weight (kg)", value=100.0)
        t_reps = st.number_input("Reps Performed", value=12)
        
        # New Feature: Systemic 1RM Tracking (Simulated)
        est_1rm = t_weight * (1 + t_reps/30)
        st.caption(f"Estimated 1RM: {int(est_1rm)} kg")
        
    with col_track2:
        st.subheader("Recommendation")
        
        target_reps = 8 # Example target bottom range
        
        if t_reps > 10:
            # Over range -> Increase weight
            new_load = est_1rm / (1 + target_reps/30)
            rounded_load = round(new_load / 2.5) * 2.5
            diff = rounded_load - t_weight
            st.success(f"🚀 **Increase Weight by {diff} kg**")
            st.write(f"New Load: **{rounded_load} kg**")
            st.write(f"Goal: Drop reps to **{target_reps}** to restore mechanical tension.")
        elif t_reps < 6:
            st.warning("⚠️ **Reduce Weight** or Improve Recovery")
            st.write("Reps too low for optimal hypertrophy volume accumulation.")
        else:
            st.info("✅ **Keep Weight**")
            st.write("You are in the optimal zone. Add reps until you hit 10+.")
