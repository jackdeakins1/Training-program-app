import streamlit as st
import pandas as pd
import numpy as np
import math

# ==========================================
# 1. SCIENTIFIC MODELS (Beardsley/Schoenfeld)
# ==========================================

class BeardsleyModel:
    """
    Core engine for calculating Stimulus and Recovery based on the
    provided research papers and diagrams.
    """

    @staticmethod
    def calculate_effective_sets(raw_sets, reps, rir):
        """
        Calculates 'Effective Sets' based on Proximity to Failure.
        Logic: 5 Stimulating Reps = 1 Effective Set.
        Standard Set to Failure (0 RIR) = 5 Stimulating Reps = 1.0 Effective Set.
        """
        # Cap stimulating reps at the number of reps performed (e.g., 3 rep set can't have 5 stimulating reps)
        # And cap at 5 (standard physiological limit per set)
        stimulating_reps = min(reps, max(0, 5 - rir))
        effective_set_value = stimulating_reps / 5.0
        return raw_sets * effective_set_value

    @staticmethod
    def calculate_gross_stimulus(effective_sets):
        """
        Calculates Hypertrophy Stimulus (Arbitrary Units) using the Schoenfeld Curve.
        Points: 1 set=1.0, 3 sets=1.61, 9 sets=2.23.
        Fit: y = 0.55 * ln(x) + 1.0
        """
        if effective_sets <= 0:
            return 0.0
        # Determine the base stimulus from the log curve
        # We ensure effective_sets is at least slightly > 0 to avoid log errors
        eff = max(0.1, effective_sets)
        return (0.55 * np.log(eff)) + 1.0

    @staticmethod
    def calculate_recovery_hours(sets, rep_range_type, muscle_profile, rir):
        """
        Calculates Recovery Time based on the provided 'Strength training recovery' data.
        Base: Moderate load (6-15RM) to failure ~14 hours per set (linear approx from chart).
        """
        base_hours_per_set = 14.0

        # Multipliers based on User's Data
        # 1. Load Multiplier (Heavy loads recover FASTER than moderate/light due to less Ca+ accumulation)
        if rep_range_type == 'Heavy (1-5)':
            load_mult = 0.6
        elif rep_range_type == 'Moderate (6-15)':
            load_mult = 1.0
        else: # Light (16+)
            load_mult = 1.5

            # 2. RIR Multiplier (Training to failure increases fatigue)
        # If RIR > 1, fatigue drops significantly.
        rir_mult = 1.0 if rir <= 1 else 0.8

        # 3. Muscle/Exercise Profile Multiplier
        # Lengthened/Stretched positions take longer to recover.
        profile_mult = 1.25 if muscle_profile == "Lengthened" else 1.0

        # Fast twitch (Easily damaged) penalty
        # We will apply this in the main logic if the muscle is "Easily Damaged"

        total_hours = sets * base_hours_per_set * load_mult * rir_mult * profile_mult
        return total_hours

    @staticmethod
    def calculate_wns(workouts_per_week, gross_stimulus_per_workout, recovery_hours):
        """
        Calculates Weekly Net Stimulus (WNS).
        Formula: WNS = (Gross Stimulus - Atrophy Loss) * Frequency
        """
        cycle_hours = 168.0 / workouts_per_week
        stimulus_duration = 48.0 # Fixed biological constant

        # 1. Check Recovery Penalty
        # If training before recovered, the new stimulus is blunted
        recovery_penalty = 0.0
        if cycle_hours < recovery_hours:
            # Simple linear penalty: if you train 24h early, you lose efficacy
            deficit = recovery_hours - cycle_hours
            recovery_penalty = (deficit / recovery_hours) * 0.5 # Arbitrary scaling for penalty

        # 2. Calculate Atrophy
        # Atrophy starts after Stimulus Duration expires
        time_in_atrophy = max(0, cycle_hours - stimulus_duration)

        # Rate: 3 sets (1.61 AU) maintains size over 5 days (120h) of atrophy.
        # Rate = 1.61 / 120 = 0.0134 AU/hour
        atrophy_rate = 0.0134
        atrophy_loss = time_in_atrophy * atrophy_rate

        net_stimulus_per_workout = (gross_stimulus_per_workout * (1 - recovery_penalty)) - atrophy_loss

        return max(0, net_stimulus_per_workout * workouts_per_week)

# ==========================================
# 2. EXERCISE LIBRARY & DATA
# ==========================================

EXERCISE_DB = {
    "Chest": {
        "compounds": ["Flat Bench Press", "Dip", "Weighted Pushup"],
        "isolations": ["DB Fly", "Cable Crossover", "Pec Deck"],
        "subdivisions": {
            "Clavicular": ["Incline DB Press", "Reverse Grip Bench"],
            "Sternal": ["Flat DB Press", "Chest Press Machine"],
            "Costal": ["Decline Press", "High-to-Low Cable"]
        },
        "profile": "Lengthened", # Chest is often trained at long lengths
        "damaged": True # Fast twitch dominance
    },
    "Back": {
        "compounds": ["Pull Up", "Barbell Row", "Deadlift"],
        "isolations": ["Straight Arm Pulldown", "Face Pull"],
        "subdivisions": {
            "Upper/Lat": ["Lat Pulldown (Wide)", "Pull Up"],
            "Mid/Trap": ["Chest Supported Row", "T-Bar Row"],
            "Lower/Erector": ["Rack Pull", "Back Extension"]
        },
        "profile": "Shortened", # Most rows peak in shortening, unless specified
        "damaged": False
    },
    "Quads": {
        "compounds": ["Barbell Squat", "Leg Press", "Hack Squat"],
        "isolations": ["Leg Extension"],
        "subdivisions": {"General": ["Squat"]}, # Advanced usually just adds volume or variation
        "profile": "Lengthened",
        "damaged": True
    },
    "Hamstrings": {
        "compounds": ["RDL", "Stiff Leg Deadlift"],
        "isolations": ["Seated Leg Curl", "Lying Leg Curl"],
        "subdivisions": {"General": ["RDL"]},
        "profile": "Lengthened",
        "damaged": True
    },
    "Shoulders": {
        "compounds": ["Overhead Press (BB)", "Seated DB Press"],
        "isolations": ["Lateral Raise", "Rear Delt Fly"],
        "subdivisions": {
            "Front": ["OHP"],
            "Side": ["Cable Lateral Raise", "DB Lateral Raise"],
            "Rear": ["Reverse Pec Deck"]
        },
        "profile": "Shortened",
        "damaged": False
    },
    "Triceps": {
        "compounds": ["Close Grip Bench", "Dip"],
        "isolations": ["Skull Crusher", "Cable Pushdown", "Overhead Ext"],
        "subdivisions": {"Long Head": ["Overhead Ext"], "Medial/Lateral": ["Pushdown"]},
        "profile": "Mid",
        "damaged": False
    },
    "Biceps": {
        "compounds": ["Chin Up (Supinated)"],
        "isolations": ["Barbell Curl", "Incline DB Curl", "Preacher Curl"],
        "subdivisions": {"Long Head": ["Incline Curl"], "Short Head": ["Preacher Curl"]},
        "profile": "Lengthened", # Incline curls etc
        "damaged": False
    },
    "Calves": {
        "compounds": [],
        "isolations": ["Standing Calf Raise", "Seated Calf Raise"],
        "subdivisions": {"Gastrocnemius": ["Standing Raise"], "Soleus": ["Seated Raise"]},
        "profile": "Shortened",
        "damaged": False
    }
}

# ==========================================
# 3. APP LOGIC
# ==========================================

def get_rep_scheme(goal, available_time_short):
    """
    Returns (Reps, RIR, Load Type) based on constraints.
    """
    if available_time_short:
        # Constraint: < 60 mins -> Force 10-12 reps (Moderate/Light) to save rest time
        return "10-12", 1, "Moderate (6-15)"

    if goal == "Strength Priority":
        return "1-3", 2, "Heavy (1-5)"

    # Default Hypertrophy
    return "6-10", 0, "Moderate (6-15)"

def generate_program_structure(level, split_days, priorities, muscle_list):
    """
    Generates the raw skeleton of the program based on Reg Park / Reeves / Modern splits.
    """
    program = {}

    # --- Split Logic ---
    if split_days == 2:
        # Upper / Lower
        days = ["Day 1: Upper", "Day 2: Lower"]
        muscle_map = {
            "Day 1: Upper": ["Chest", "Back", "Shoulders", "Triceps", "Biceps"],
            "Day 2: Lower": ["Quads", "Hamstrings", "Calves"]
        }
    elif split_days == 3:
        # Full Body (Reg Park style)
        days = ["Day 1: Full Body A", "Day 2: Full Body B", "Day 3: Full Body A"]
        # Basic mapping, simplified for code brevity
        all_muscles = ["Quads", "Chest", "Back", "Hamstrings", "Shoulders", "Triceps", "Biceps", "Calves"]
        muscle_map = {d: all_muscles for d in days}
    else:
        # Default fallback to FB
        days = ["Day 1", "Day 2"]
        muscle_map = {"Day 1": muscle_list, "Day 2": muscle_list}

    # --- Exercise Selection Logic ---
    for day in days:
        program[day] = []
        todays_muscles = muscle_map[day]

        # Sort muscles: Priorities goes first
        sorted_muscles = [m for m in todays_muscles if m in priorities] + \
                         [m for m in todays_muscles if m not in priorities]

        for muscle in sorted_muscles:
            if muscle not in muscle_list: continue # Skip if user didn't select

            data = EXERCISE_DB[muscle]
            exercises_to_add = []

            # Logic by Level
            if level == "Beginner":
                # 1 Compound per muscle
                if data["compounds"]:
                    exercises_to_add.append(data["compounds"][0])
                elif data["isolations"]:
                    exercises_to_add.append(data["isolations"][0])

            elif level == "Intermediate":
                # Priority: 2 Exercises (Compound + Iso)
                # Normal: 1 Compound (or Iso if no Compound)
                # + Always add leg extension/tricep ext if relevant

                if muscle in priorities:
                    if data["compounds"]: exercises_to_add.append(data["compounds"][0])
                    if data["isolations"]: exercises_to_add.append(data["isolations"][0])
                else:
                    if data["compounds"]: exercises_to_add.append(data["compounds"][0])
                    elif data["isolations"]: exercises_to_add.append(data["isolations"][0])

                # Special Intermediate Rules (Reg Park/Reeves modernization)
                if muscle == "Quads" and "Leg Extension" not in exercises_to_add:
                    exercises_to_add.append("Leg Extension")
                if muscle == "Triceps" and "Overhead Ext" not in exercises_to_add:
                    exercises_to_add.append("Overhead Ext")

            elif level == "Advanced":
                # 1 Exercise per subdivision
                for sub_name, sub_exs in data["subdivisions"].items():
                    exercises_to_add.append(f"{sub_exs[0]} ({sub_name})")

            # Add to daily program
            for ex in exercises_to_add:
                entry = {
                    "Muscle": muscle,
                    "Exercise": ex,
                    "Sets": 3, # Default baseline, optimized later
                    "Type": "Compound" if ex in data["compounds"] else "Isolation"
                }
                program[day].append(entry)

    return program

def optimize_volume(program, freq, level, short_on_time_global, priority_strength_muscles):
    """
    The Simulator Loop: Adjusts sets based on Recovery & Time Constraints.
    """
    optimized_program = {}
    report_log = []

    cycle_hours = 168.0 / freq

    for day, exercises in program.items():
        daily_log = []

        # 1. Apply Time Constraint (Short on Time = Halve Volume)
        if short_on_time_global:
            daily_log.append("Global Constraint: Short on Time detected. Switching to A/B split volume (sets halved).")
            for ex in exercises:
                ex["Sets"] = max(1, int(ex["Sets"] / 2))

        # 2. Apply Strength Priority Overrides
        for ex in exercises:
            if ex["Muscle"] in priority_strength_muscles and ex["Type"] == "Compound":
                ex["Reps"] = "1-3"
                ex["RIR"] = 2
                ex["Load"] = "Heavy (1-5)"
                ex["Sets"] = 5 # Strength usually needs more sets
                daily_log.append(f"Strength Priority: {ex['Exercise']} converted to 5x3 @ 2 RIR.")
            else:
                # Defaults
                if short_on_time_global:
                    ex["Reps"] = "10-12" # Faster tempo
                    ex["RIR"] = 1
                    ex["Load"] = "Moderate (6-15)"
                else:
                    ex["Reps"] = "6-10"
                    ex["RIR"] = 0 if level != "Beginner" else 2 # Beginners shouldn't fail
                    ex["Load"] = "Moderate (6-15)"

        # 3. Recovery Check (The Beardsley Layer)
        # We calculate total fatigue for the muscle group across the session
        muscle_groups_in_session = set([x["Muscle"] for x in exercises])

        for muscle in muscle_groups_in_session:
            muscle_exercises = [x for x in exercises if x["Muscle"] == muscle]
            total_sets = sum(x["Sets"] for x in muscle_exercises)

            # Get parameters for calc
            # We average the params if multiple exercises, or take worst case
            m_profile = EXERCISE_DB[muscle]["profile"]
            m_damaged = EXERCISE_DB[muscle]["damaged"]

            # Base calc
            # Note: We take the first exercise's load/rir as proxy for now
            rep_scheme = muscle_exercises[0]["Load"]
            rir_scheme = muscle_exercises[0]["RIR"]

            req_recovery = BeardsleyModel.calculate_recovery_hours(
                total_sets, rep_scheme, m_profile, rir_scheme
            )

            # Apply "Easily Damaged" multiplier
            if m_damaged:
                req_recovery *= 1.2

            # Optimization: If Recovery > Cycle Time, Reduce Sets
            if req_recovery > cycle_hours:
                reduction = 1
                while req_recovery > cycle_hours and total_sets > 1:
                    # Reduce 1 set from the last exercise of this muscle
                    target_ex = muscle_exercises[-1]
                    if target_ex["Sets"] > 1:
                        target_ex["Sets"] -= 1
                        total_sets -= 1
                        daily_log.append(f"Recovery Limit Exceeded ({int(req_recovery)}h > {int(cycle_hours)}h). Reduced sets for {target_ex['Exercise']}.")
                    else:
                        break # Cannot reduce further

                    # Recalc
                    req_recovery = BeardsleyModel.calculate_recovery_hours(total_sets, rep_scheme, m_profile, rir_scheme)
                    if m_damaged: req_recovery *= 1.2

            # Calculate WNS for this muscle
            eff_sets = BeardsleyModel.calculate_effective_sets(total_sets, 10, rir_scheme) # assuming 10 reps avg
            gross_stim = BeardsleyModel.calculate_gross_stimulus(eff_sets)
            wns = BeardsleyModel.calculate_wns(freq, gross_stim, req_recovery)

            # Tag the WNS to the first exercise for display
            muscle_exercises[0]["WNS_Score"] = round(wns, 2)
            muscle_exercises[0]["Recovery_Hours"] = int(req_recovery)

        optimized_program[day] = exercises
        report_log.append(daily_log)

    return optimized_program, report_log

# ==========================================
# 4. STREAMLIT UI
# ==========================================

st.set_page_config(page_title="WNS Hypertrophy Architect", layout="wide")

st.title("🧬 WNS Hypertrophy Architect")
st.markdown("""
**Based on the Weekly Net Stimulus Model & Effective Sets Theory.**
*Algorithmic design derived from Chris Beardsley & Reg Park principles.*
""")

# --- Sidebar Inputs ---
with st.sidebar:
    st.header("1. Lifter Profile")
    level = st.selectbox("Experience Level", ["Beginner", "Intermediate", "Advanced"])

    st.header("2. Constraints")
    freq_option = st.selectbox("Training Frequency", ["2x/week (Upper/Lower)", "3x/week (Full Body)"])
    session_time = st.radio("Session Duration Limit", ["> 60 mins", "< 60 mins"])

    st.header("3. Goals")
    goal = st.selectbox("Primary Goal", ["Hypertrophy", "Strength Priority"])

    # Dynamic Input for Priorities
    priorities = []
    strength_muscle = []
    all_muscles = list(EXERCISE_DB.keys())

    if level != "Beginner":
        st.subheader("Priorities")
        priorities = st.multiselect("Select Priority Muscles (Trained First)", all_muscles, max_selections=2)

    if goal == "Strength Priority":
        strength_muscle = st.multiselect("Select Lift for Strength Focus (1-3 Reps)", all_muscles, max_selections=1)

    muscle_selection = st.multiselect("Muscles to Train", all_muscles, default=all_muscles)

    if st.button("Generate Program"):
        # Map frequency text to int
        freq_int = 2 if "2x" in freq_option else 3
        short_on_time = True if "< 60" in session_time else False

        # 1. Draft
        draft_prog = generate_program_structure(level, freq_int, priorities, muscle_selection)

        # 2. Optimize
        final_prog, logs = optimize_volume(draft_prog, freq_int, level, short_on_time, strength_muscle)

        # 3. Display
        st.session_state['program'] = final_prog
        st.session_state['logs'] = logs

# --- Main Output ---

if 'program' in st.session_state:
    prog = st.session_state['program']
    logs = st.session_state['logs']

    st.divider()

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📅 Your Optimized Schedule")

        for i, (day, exercises) in enumerate(prog.items()):
            with st.expander(f"{day} - {len(exercises)} Exercises", expanded=True):
                # Convert to DataFrame for pretty display
                df_data = []
                for ex in exercises:
                    row = {
                        "Muscle": ex["Muscle"],
                        "Exercise": ex["Exercise"],
                        "Sets": ex["Sets"],
                        "Reps": ex["Reps"],
                        "RIR": ex["RIR"],
                        "Load Type": ex["Load"],
                    }
                    if "WNS_Score" in ex:
                        row["WNS"] = ex["WNS_Score"]
                        row["Est. Recovery"] = f"{ex['Recovery_Hours']}h"
                    else:
                        row["WNS"] = "-"
                        row["Est. Recovery"] = "-"
                    df_data.append(row)

                st.dataframe(pd.DataFrame(df_data), use_container_width=True)

                # Show optimization logs if any
                if logs[i]:
                    st.warning("⚠️ Optimization Adjustments:")
                    for log in logs[i]:
                        st.markdown(f"- {log}")

    with col2:
        st.subheader("📊 WNS Analysis")
        st.info(f"""
        **Model Logic Used:**
        - **Stimulus:** 5 stimulating reps = 1 Effective Set.
        - **Decay:** Atrophy starts after 48h (Stimulus Duration).
        - **Recovery:** Calculated based on set count, load type, and muscle length.
        """)

        # WNS Chart
        wns_data = {}
        for day, exercises in prog.items():
            for ex in exercises:
                if "WNS_Score" in ex:
                    wns_data[ex["Muscle"]] = ex["WNS_Score"]

        if wns_data:
            df_chart = pd.DataFrame(list(wns_data.items()), columns=["Muscle", "WNS Score"])
            st.bar_chart(df_chart, x="Muscle", y="WNS Score")
            st.caption("Higher score = Greater Net Hypertrophy. Scores account for atrophy penalties if frequency is too low.")