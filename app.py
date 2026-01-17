import streamlit as st
import pandas as pd
import numpy as np

# ==========================================
# 1. SCIENTIFIC CORE (Calibrated to Your Data)
# ==========================================

class RecoveryEngine:
    """
    Reverse-engineered logic from the Recovery Estimator data points provided.
    Baseline Reference: 1 Set, 10 Reps, 0 RIR, Middle Muscle, Even Profile = 22.5 Hours.
    """
    
    @staticmethod
    def get_rep_multiplier(reps):
        """
        Calibrated against Test B Data:
        1r:3h, 3r:10h, 5r:16h, 10r:22h, 15r:34h, 20r:47h.
        Base (1.0) is 10 reps (22h).
        """
        # Linear interpolation between known data points for maximum accuracy
        x = [1, 3, 5, 10, 15, 20]
        # Ratios relative to 10 reps (22h)
        y = [3/22, 10/22, 16/22, 1.0, 34/22, 47/22] 
        return np.interp(reps, x, y)

    @staticmethod
    def get_rir_multiplier(rir):
        """
        Calibrated against Test C Data:
        0 RIR: 100%, 1 RIR: 77%, 2 RIR: 59%, 3 RIR: 45%, 4 RIR: 27%.
        """
        x = [0, 1, 2, 3, 4]
        y = [1.0, 17/22, 13/22, 10/22, 6/22]
        # Cap at 4 RIR (minimal fatigue)
        if rir > 4: return 0.2
        return np.interp(rir, x, y)

    @staticmethod
    def calculate_recovery(sets, reps, rir, muscle_type, profile_type):
        """
        Calculates hours required to recover.
        """
        # 1. Base Constant (Hours per set for Standard conditions)
        # Derived from 8 sets = 180h -> 22.5h per set
        base_hours_per_set = 22.5
        
        # 2. Variable Multipliers
        rep_mult = RecoveryEngine.get_rep_multiplier(reps)
        rir_mult = RecoveryEngine.get_rir_multiplier(rir)
        
        # Muscle Type Multipliers (Derived from screenshots)
        # Hardly: 13/16 = 0.81
        # Middle: 1.0
        # Easily: 24/16 = 1.5
        m_mult = 1.0
        if muscle_type == "Easily Damaged": m_mult = 1.5
        elif muscle_type == "Hardly Damaged": m_mult = 0.81
        
        # Profile Multipliers (Derived from screenshots)
        # Ascending: ~0.83, Even: 1.0, Descending (Lengthened): ~1.125
        p_mult = 1.0
        if profile_type == "Lengthened (Descending)": p_mult = 1.125
        elif profile_type == "Shortened (Ascending)": p_mult = 0.83
        
        total_hours = sets * base_hours_per_set * rep_mult * rir_mult * m_mult * p_mult
        return total_hours

class StimulusEngine:
    """
    Weekly Net Stimulus Model.
    """
    @staticmethod
    def calculate_effective_sets(raw_sets, reps, rir):
        # 5 stimulating reps = 1 effective set.
        # Capped at rep count (e.g. 3 reps @ 0 RIR = 3 stim reps = 0.6 sets)
        stim_reps = min(reps, max(0, 5 - rir))
        return raw_sets * (stim_reps / 5.0)

    @staticmethod
    def get_schoenfeld_stimulus(effective_sets):
        # Schoenfeld Curve: 1set=1.0, 3sets=1.61, 9sets=2.23
        # Log fit: y = 0.55 * ln(x) + 1.0
        if effective_sets <= 0: return 0.0
        # Determine gross stimulus (AU)
        eff = max(0.1, effective_sets)
        return (0.55 * np.log(eff)) + 1.0

    @staticmethod
    def calculate_wns(freq, gross_stim, recovery_hours):
        """
        Calculates Net Stimulus accounting for frequency and atrophy.
        """
        cycle_hours = 168.0 / freq
        stimulus_duration = 48.0
        
        # 1. Recovery Penalty (Training while fatigued blunts stimulus)
        penalty_factor = 1.0
        if cycle_hours < recovery_hours:
            # If you train at 24h but need 48h, you are 50% recovered.
            # We apply a penalty proportional to the deficit.
            recovered_ratio = cycle_hours / recovery_hours
            penalty_factor = recovered_ratio # Simple linear penalty
            
        # 2. Atrophy Calculation
        # Atrophy starts after 48h.
        # Rate: 0.322 AU per day (1.61 AU / 5 days) = 0.0134 AU/hr
        time_in_atrophy = max(0, cycle_hours - stimulus_duration)
        atrophy_loss = time_in_atrophy * 0.0134
        
        # Net for one workout
        net_workout = (gross_stim * penalty_factor) - atrophy_loss
        
        # Total Weekly
        return max(0, net_workout * freq)

# ==========================================
# 2. EXERCISE DATABASE
# ==========================================

# Mapped based on biological profiles
MUSCLE_DATA = {
    "Chest": {"type": "Middle", "profile": "Lengthened (Descending)"}, # Flys/Presses stretch well
    "Back": {"type": "Middle", "profile": "Shortened (Ascending)"}, # Rows peak at shortening
    "Quads": {"type": "Easily Damaged", "profile": "Lengthened (Descending)"}, # Squats stretch, high damage
    "Hamstrings": {"type": "Easily Damaged", "profile": "Lengthened (Descending)"}, # RDLs are pure stretch
    "Shoulders": {"type": "Hardly Damaged", "profile": "Shortened (Ascending)"}, # Laterals
    "Triceps": {"type": "Middle", "profile": "Even"},
    "Biceps": {"type": "Middle", "profile": "Lengthened (Descending)"}, # Incline curls etc
    "Calves": {"type": "Hardly Damaged", "profile": "Shortened (Ascending)"}
}

EXERCISE_LIST = {
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

st.set_page_config(layout="wide", page_title="WNS Optimizer")

st.title("🧬 WNS Training Architect")
st.markdown("Optimization based on **Weekly Net Stimulus** & **Recovery Costs**.")

# --- SIDEBAR: User Inputs ---
with st.sidebar:
    st.header("1. User Constraints")
    level = st.selectbox("Experience Level", ["Beginner", "Intermediate", "Advanced"])
    freq_label = st.selectbox("Frequency", ["2x/week (Upper/Lower)", "3x/week (Full Body)"])
    freq = 2 if "2x" in freq_label else 3
    
    time_limit = st.radio("Session Duration", ["> 60 mins", "< 60 mins"])
    is_short_time = True if "< 60" in time_limit else False
    
    st.header("2. Goal Specifics")
    goal = st.selectbox("Priority", ["Hypertrophy", "Strength (Bench Focus)"])
    
    muscles_selected = st.multiselect("Muscles to Train", list(MUSCLE_DATA.keys()), default=list(MUSCLE_DATA.keys()))

    run_btn = st.button("Generate & Optimize")

# --- MAIN LOGIC ---

if run_btn:
    st.divider()
    col1, col2 = st.columns([2, 1])
    
    # 1. Setup Defaults based on Goal
    if is_short_time:
        default_sets = 2
        default_reps = 10 # 10 reps = 22h base
        default_rir = 1
    else:
        default_sets = 3
        default_reps = 8
        default_rir = 0 # Failure for max data accuracy in testing
        
    if goal == "Strength (Bench Focus)":
        bench_sets = 5
        bench_reps = 3 # Low fatigue per set (see curve)
        bench_rir = 2 # Low fatigue multiplier
    
    results = []
    
    # 2. Optimization Loop
    with col1:
        st.subheader(f"📅 Optimized {freq_label} Plan")
        
        # Calculate Cycle Limit
        cycle_limit = 168.0 / freq
        
        for muscle in muscles_selected:
            m_data = MUSCLE_DATA[muscle]
            
            # Set params
            current_sets = default_sets
            current_reps = default_reps
            current_rir = default_rir
            
            # Apply Strength Override for Chest if selected
            if muscle == "Chest" and "Strength" in goal:
                current_sets = bench_sets
                current_reps = bench_reps
                current_rir = bench_rir
            
            # --- The Optimization Step ---
            # Calculate Recovery Cost
            cost = RecoveryEngine.calculate_recovery(
                current_sets, current_reps, current_rir, m_data["type"], m_data["profile"]
            )
            
            # If Cost > Cycle Limit, Reduce Sets until it fits
            # (Unless it's the Strength priority, then we might accept the risk or reduce accessories)
            adjusted = False
            while cost > cycle_limit and current_sets > 1:
                current_sets -= 1
                cost = RecoveryEngine.calculate_recovery(
                    current_sets, current_reps, current_rir, m_data["type"], m_data["profile"]
                )
                adjusted = True
            
            # Calculate WNS
            eff_sets = StimulusEngine.calculate_effective_sets(current_sets, current_reps, current_rir)
            gross_stim = StimulusEngine.get_schoenfeld_stimulus(eff_sets)
            wns = StimulusEngine.calculate_wns(freq, gross_stim, cost)
            
            # Pick Exercise
            ex_name = EXERCISE_LIST[muscle][0]
            
            results.append({
                "Muscle": muscle,
                "Exercise": ex_name,
                "Sets": current_sets,
                "Reps": current_reps,
                "RIR": current_rir,
                "Recovery (h)": round(cost, 1),
                "WNS Score": round(wns, 2),
                "Note": "⚠️ Sets reduced for recovery" if adjusted else "✅ Optimized"
            })

        # Display Program
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
        
        st.caption(f"Cycle Duration: {round(cycle_limit)} hours. Recovery times exceeding this result in diminishing WNS.")

    # 3. Analytics
    with col2:
        st.subheader("📊 Analysis")
        st.bar_chart(df.set_index("Muscle")["WNS Score"])
        
        st.info("""
        **How to Read This:**
        - **WNS Score:** Measures net growth. If this is 0, you are maintaining. High scores > 2.0 are excellent.
        - **Recovery:** If this matches your cycle time, you are training at maximum frequency efficiency.
        """)
        
        # Specific Feedback
        avg_wns = df["WNS Score"].mean()
        if avg_wns < 0.5:
            st.error("⚠️ Overall stimulus is low. This frequency might be too low for the reduced volume.")
        elif avg_wns > 2.0:
            st.success("🚀 High hypertrophy stimulus detected.")
