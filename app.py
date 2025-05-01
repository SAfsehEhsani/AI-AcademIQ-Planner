# app.py
import streamlit as st
from utils import (
    perform_web_search,
    create_study_plan_prompt,
    generate_content,
    save_plan_to_db,
    load_all_plans_from_db,
    initialize_database,
    co # Import cohere client to check if available
)

# --- Page Config ---
st.set_page_config(page_title="AI Study Planner", layout="wide")

# --- Initialize Database ---
# This ensures tables exist when the app starts
initialize_database()

# --- Check API Key Availability ---
if not co:
    st.error("Cohere API Key not found. Please set the COHERE_API_KEY environment variable. AI features are disabled.")
    # Optionally prevent the rest of the app from running fully
    # return

# --- App Title ---
st.title("🎓 Personalized AI Study Planner")
st.caption("Enter your study goals and get a plan powered by AI and web search.")

# --- Input Form ---
with st.form("study_plan_form"):
    st.subheader("Tell us about your study needs:")
    subject = st.text_input("Subject:", placeholder="e.g., Python Programming, Quantum Physics")
    goals = st.text_area("Goals:", placeholder="e.g., Build a web app, Understand core concepts, Prepare for exam in 4 weeks")
    duration = st.text_input("Available Duration:", placeholder="e.g., 3 weeks, 2 months, 10 hours/week")

    submitted = st.form_submit_button("✨ Generate Plan")

# --- Processing Logic ---
if submitted:
    if not subject or not goals or not duration:
        st.warning("Please fill in all fields (Subject, Goals, Duration).")
    elif not co:
         st.error("Cannot generate plan: Cohere API key is missing.")
    else:
        st.info("Generating your personalized study plan... This may take a moment.")
        with st.spinner("Searching the web and consulting the AI..."):
            # 1. Perform Web Search
            search_query = f"study plan resources tips roadmap for {subject} {goals} {duration}"
            search_results = perform_web_search(search_query)
            # st.write("Debug: Search Context Snippet:") # Optional debug
            # st.text(search_results[:300] + "...")      # Optional debug

            # 2. Create Prompt
            prompt = create_study_plan_prompt(subject, goals, duration, search_results)
            # st.write("Debug: Prompt Snippet:") # Optional debug
            # st.text(prompt[:300] + "...")      # Optional debug

            # 3. Call AI Model
            generated_data = generate_content(prompt)

        if "error" in generated_data:
            st.error(f"Failed to generate plan: {generated_data['error']}")
            st.session_state['generated_plan'] = None # Clear previous results if error
        else:
            st.success("Your personalized study plan is ready!")
            # Store result in session state to persist across potential re-runs
            st.session_state['generated_plan'] = generated_data
            st.session_state['subject'] = subject # Store subject for display

            # 4. Save to Database
            user_query = f"Subject: {subject}, Goals: {goals}, Duration: {duration}"
            save_plan_to_db(user_query, subject, generated_data)
            # Force a refresh of the saved plans list if needed (Streamlit usually handles this)

# --- Display Results ---
if 'generated_plan' in st.session_state and st.session_state['generated_plan']:
    st.markdown("---")
    st.header(f"📚 Your Plan for: {st.session_state.get('subject', 'the requested subject')}")

    plan_data = st.session_state['generated_plan']

    # Use columns for better layout
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🗓️ Study Plan")
        st.markdown(plan_data.get('plan', "Not available."))
        st.subheader("🗺️ Subject Roadmap")
        st.markdown(plan_data.get('roadmap', "Not available."))

    with col2:
        st.subheader("💡 Study Tips")
        st.markdown(plan_data.get('tips', "Not available."))
        st.subheader("🔗 Course/Resource Suggestions")
        st.markdown(plan_data.get('courses', "Not available."))

    # Optionally show the full response in an expander
    with st.expander("View Full AI Response"):
        st.text(plan_data.get('full_response', "Full response not available."))


# --- Display Saved Plans ---
st.markdown("---")
st.header("💾 Previously Generated Plans")

saved_plans = load_all_plans_from_db()

if not saved_plans:
    st.info("No study plans have been saved yet.")
else:
    # Display plans, maybe newest first
    for plan in saved_plans:
        with st.expander(f"Plan for **{plan['subject']}** (Created: {plan['created_at']})"):
            st.caption(f"Original Query: {plan['user_query']}")
            st.markdown("**Plan:**")
            st.markdown(plan.get('generated_plan', "N/A"))
            st.markdown("**Tips:**")
            st.markdown(plan.get('generated_tips', "N/A"))
            st.markdown("**Roadmap:**")
            st.markdown(plan.get('generated_roadmap', "N/A"))
            # Add other fields if you stored them