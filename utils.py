# utils.py

# utils.py
import os
import requests
import json
import cohere
import re  # Import the regular expression module
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from models import Base, StudyPlan, DATABASE_URL # Make sure models.py defines these

load_dotenv()

# --- Database Setup ---
# The connect_args is specific to SQLite for multi-threading (like in Streamlit)
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- API Keys and Clients ---
COHERE_API_KEY = os.getenv('COHERE_API_KEY')
SERPER_API_KEY = os.getenv('SERPER_API_KEY')

co = cohere.Client(COHERE_API_KEY) if COHERE_API_KEY else None
if not co:
    print("Warning: COHERE_API_KEY not found. AI features may be limited.")
if not SERPER_API_KEY:
    print("Warning: SERPER_API_KEY not found. Web search features will be disabled.")


# --- Web Search ---
def perform_web_search(query, num_results=3):
    """Performs a web search using Serper API."""
    if not SERPER_API_KEY:
        return "Web search disabled. SERPER_API_KEY missing."

    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query, "num": num_results})
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=15) # Increased timeout slightly
        response.raise_for_status()
        results = response.json()

        search_context = []
        if 'organic' in results:
            for item in results['organic']:
                search_context.append({
                    "title": item.get('title', 'N/A'),
                    "link": item.get('link', '#'),
                    "snippet": item.get('snippet', 'N/A')
                })

        if not search_context:
            return "No relevant search results found or search failed."

        # Format for AI context
        formatted_context = "Web Search Results:\n"
        for i, item in enumerate(search_context):
            formatted_context += f"{i+1}. Title: {item['title']}\n   Snippet: {item['snippet']}\n   Link: {item['link']}\n\n"
        return formatted_context.strip() # Remove trailing newlines

    except requests.exceptions.Timeout:
        print("Error during web search: Request timed out.")
        return "Error: Web search request timed out."
    except requests.exceptions.RequestException as e:
        print(f"Error during web search: {e}")
        # Check for specific status codes if needed (e.g., 401 Unauthorized, 429 Rate Limit)
        error_detail = str(e)
        if response is not None:
            error_detail = f"{e} - Status Code: {response.status_code}"
        return f"Error performing web search: {error_detail}"
    except Exception as e:
        print(f"An unexpected error occurred during search: {e}")
        return f"An unexpected error occurred during search: {e}"


# --- AI Content Generation ---
def create_study_plan_prompt(subject, goals, duration, search_results):
    """Creates a detailed prompt for the AI model with specific formatting instructions."""
    prompt = f"""
    You are an expert study planner AI assistant. Create a comprehensive study plan based on the user's request and relevant web search results.

    User Request:
    Subject: {subject}
    Goals: {goals}
    Available Duration: {duration}

    Relevant Web Search Information (use this for context and resources):
    {search_results}

    Instructions:
    Generate the following sections clearly separated.
    **VERY IMPORTANT:** Use **Markdown H3 headings starting with '###'** for each section title, exactly as shown below (e.g., `### Study Plan`, `### Study Tips`).
    Start the content for each section on a new line immediately after its heading.

    ### Study Plan
    Provide a structured plan (e.g., weekly breakdown). Suggest specific activities (reading, practice, projects). Reference resources from the search results if relevant. Be detailed and practical.

    ### Study Tips
    Give 3-5 actionable tips specific to learning '{subject}', potentially referencing search results or common learning strategies for the subject.

    ### Subject Roadmap
    Outline the typical topic progression for '{subject}', starting from fundamentals and moving towards more advanced concepts mentioned in the goals or search results.

    ### Course/Resource Suggestions
    List 1-3 relevant courses, tutorials, websites, or books *found in the search results*. Briefly describe them based *only* on the search snippet/title. Include links if available in the search results. If no specific resources were found in the search results or the search failed, state that clearly within this section. Do not invent resources.

    Format your entire response using Markdown. Be practical, encouraging, and ensure the plan aligns with the user's goals and duration.
    """
    return prompt

# Updated Parsing Function
def extract_section(text, section_title):
    """
    Extracts text under a specific section heading (e.g., '### Section Title') using regex.
    Looks for the heading case-insensitively and captures content until the next H3 heading or end of text.
    """
    # Regex Breakdown:
    # ^\s*                     # Start of a line, optional leading whitespace
    # ###\s+                   # Match '###' followed by one or more spaces
    # ({re.escape(section_title)}) # Match the section title (case-insensitive, group 1)
    # \s*                      # Optional trailing whitespace after title
    # (?:\n|$)                # Non-capturing group: newline OR end of line after title
    # (.*?)                    # Capture the content (non-greedy, group 2)
    # (?=                      # Positive lookahead (checks what follows without consuming)
    #   \n\s*###\s+            # Look for a newline, optional space, then the start of the *next* H3 heading
    #   |                      # OR
    #   \Z                     # Look for the absolute end of the string
    # )
    pattern = re.compile(
        r"^\s*###\s+(" + re.escape(section_title) + r")\s*(?:\n|$)(.*?)(?=\n\s*###\s+|\Z)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL
    )

    match = pattern.search(text)

    if match:
        # Return the captured content (group 2), stripped of leading/trailing whitespace
        return match.group(2).strip()
    else:
        print(f"Warning: Could not find or parse section '{section_title}' with expected H3 format.")
        return None # Explicitly return None if not found

# Updated Generate Content Function
def generate_content(prompt, model='command-r', max_tokens=2500, temperature=0.6):
    """Generates content using the Cohere API Chat endpoint and parses sections."""
    if not co:
        return {"error": "Error: AI generation disabled. COHERE_API_KEY missing or client not initialized."}

    print(f"--- Sending Prompt to Cohere (model: {model}) ---")
    # print(prompt) # Uncomment for debugging the full prompt
    print("--- End of Prompt ---")

    try:
        response = co.chat(
            model=model,
            message=prompt,
            temperature=temperature,
            # max_tokens=max_tokens, # Chat endpoint might manage tokens differently, monitor usage
        )
        if hasattr(response, 'text'):
             full_text = response.text
             print("--- Received Response from Cohere ---")
             # print(full_text) # Uncomment for debugging the full AI response
             print("--- End of Response ---")

             # Use the improved extract_section function
             plan = extract_section(full_text, "Study Plan")
             tips = extract_section(full_text, "Study Tips")
             roadmap = extract_section(full_text, "Subject Roadmap")
             courses = extract_section(full_text, "Course/Resource Suggestions")

             # Provide default messages ONLY if parsing explicitly failed (returned None)
             return {
                "full_response": full_text,
                "plan": plan if plan is not None else "*AI response received, but couldn't parse the 'Study Plan' section. Check the full response below.*",
                "tips": tips if tips is not None else "*AI response received, but couldn't parse the 'Study Tips' section. Check the full response below.*",
                "roadmap": roadmap if roadmap is not None else "*AI response received, but couldn't parse the 'Subject Roadmap' section. Check the full response below.*",
                "courses": courses if courses is not None else "*AI response received, but couldn't parse the 'Course/Resource Suggestions' section. Check the full response below.*"
             }
        else:
             # Handle cases where the response object doesn't have 'text'
             print(f"Unexpected Cohere response structure: {response}")
             return {"error": "Error: Could not parse AI response structure (missing 'text' attribute)."}

    except cohere.CohereError as e:
        print(f"Cohere API error: {e}")
        # Attempt to provide more specific feedback
        error_message = str(e)
        if hasattr(e, 'http_status'):
            error_message += f" (HTTP Status: {e.http_status})"
        if "rate limit" in error_message.lower():
            error_message += " - Please wait and try again later."
        elif "invalid api key" in error_message.lower():
             error_message += " - Please check your COHERE_API_KEY."

        return {"error": f"Error generating content via Cohere API: {error_message}"}
    except Exception as e:
        # Catch other potential errors (network issues, timeouts handled separately in search)
        print(f"An unexpected error occurred during AI generation: {e}")
        return {"error": f"An unexpected error occurred during AI generation: {e}"}


# --- Database Operations ---
def save_plan_to_db(user_query, subject, generated_data):
    """Saves the generated plan details to the database."""
    # Ensure generated_data is a dict and get values safely
    plan = generated_data.get('plan') if isinstance(generated_data, dict) else None
    tips = generated_data.get('tips') if isinstance(generated_data, dict) else None
    roadmap = generated_data.get('roadmap') if isinstance(generated_data, dict) else None
    # You could add courses here too if you add it to the DB model
    # courses = generated_data.get('courses') if isinstance(generated_data, dict) else None

    db = SessionLocal()
    try:
        new_plan = StudyPlan(
            user_query=user_query,
            subject=subject,
            generated_plan=plan,
            generated_tips=tips,
            generated_roadmap=roadmap
            # Add other fields if needed
        )
        db.add(new_plan)
        db.commit()
        db.refresh(new_plan)
        print(f"Saved plan with ID: {new_plan.id}")
        return new_plan.id
    except Exception as e:
        db.rollback()
        print(f"Database Error saving plan: {e}")
        # Optionally, log the full error traceback for debugging
        # import traceback
        # traceback.print_exc()
        return None
    finally:
        db.close()

def load_all_plans_from_db():
    """Loads all saved study plans from the database."""
    db = SessionLocal()
    try:
        # Query StudyPlan objects, order by created_at descending
        plans = db.query(StudyPlan).order_by(StudyPlan.created_at.desc()).all()
        # Convert each StudyPlan object to a dictionary using its to_dict method
        return [plan.to_dict() for plan in plans]
    except Exception as e:
        print(f"Database Error loading plans: {e}")
        # import traceback
        # traceback.print_exc()
        return [] # Return empty list on error
    finally:
        db.close()

# --- Initialize Database ---
def initialize_database():
    """Creates database tables if they don't exist."""
    try:
        # Use the engine associated with the Base metadata
        Base.metadata.create_all(bind=engine)
        print("Database tables checked/created successfully.")
    except Exception as e:
        print(f"Error initializing database tables: {e}")
        # Consider raising the error or exiting if the DB is critical
        # raise e

# Example of how to call initialize_database (usually done once at app startup)
# if __name__ == "__main__":
#     print("Initializing database (if run directly)...")
#     initialize_database()
#     print("Initialization complete.")




'''import os
import requests
import json
import cohere
from dotenv import load_dotenv
from models import SessionLocal, StudyPlan

load_dotenv()

# --- API Keys and Clients ---
COHERE_API_KEY = os.getenv('COHERE_API_KEY')
SERPER_API_KEY = os.getenv('SERPER_API_KEY')

co = cohere.Client(COHERE_API_KEY) if COHERE_API_KEY else None
if not co:
    print("Warning: COHERE_API_KEY not found. AI features may be limited.")

# --- Web Search ---
def perform_web_search(query, num_results=3):
    """Performs a web search using Serper API."""
    if not SERPER_API_KEY:
        return "Web search disabled. SERPER_API_KEY missing."

    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query, "num": num_results})
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        results = response.json()

        search_context = []
        if 'organic' in results:
            for item in results['organic']:
                search_context.append({
                    "title": item.get('title', 'N/A'),
                    "link": item.get('link', '#'),
                    "snippet": item.get('snippet', 'N/A')
                })

        if not search_context:
            return "No relevant search results found."

        formatted_context = "Web Search Results:\n"
        for i, item in enumerate(search_context):
            formatted_context += f"{i+1}. Title: {item['title']}\n   Snippet: {item['snippet']}\n   Link: {item['link']}\n\n"
        return formatted_context

    except requests.exceptions.RequestException as e:
        print(f"Error during web search: {e}")
        return f"Error performing web search: {e}"
    except Exception as e:
        print(f"An unexpected error during search: {e}")
        return f"An unexpected error occurred during search: {e}"


# --- AI Content Generation ---
def create_study_plan_prompt(subject, goals, duration, search_results):
    """Creates a detailed prompt for the AI model."""
    # (Same prompt structure as in the Flask example)
    prompt = f"""
    You are an expert study planner AI assistant. Create a comprehensive study plan.

    User Request:
    Subject: {subject}
    Goals: {goals}
    Available Duration: {duration}

    Relevant Web Search Information (use this for context and resources):
    {search_results}

    Instructions:
    Generate the following sections clearly separated:

    **1. Study Plan:**
    Provide a structured plan (e.g., weekly breakdown). Suggest specific activities (reading, practice, projects). Reference resources from the search results if relevant.

    **2. Study Tips:**
    Give 3-5 actionable tips specific to learning '{subject}', potentially referencing search results.

    **3. Subject Roadmap:**
    Outline the typical topic progression for '{subject}'.

    **4. Course/Resource Suggestions:**
    List 1-3 relevant courses/resources *found in the search results*. Briefly describe them based *only* on the snippet/title. If none found, state that.

    Format your entire response using Markdown. Use headings (e.g., `### Study Plan`). Be practical and encouraging.
    """
    return prompt

def generate_content(prompt, model='command-r', max_tokens=2000, temperature=0.6):
    """Generates content using the Cohere API Chat endpoint."""
    if not co:
        return "Error: AI generation disabled. COHERE_API_KEY missing or client not initialized."

    try:
        # Using the Chat endpoint is generally preferred now
        response = co.chat(
            model=model,
            message=prompt,
            temperature=temperature,
             # Adjust max_tokens if needed, but Chat endpoint might handle length differently
             # max_tokens=max_tokens
        )
        if hasattr(response, 'text'):
             # Attempt basic parsing based on Markdown headings
             full_text = response.text
             plan = extract_section(full_text, "Study Plan")
             tips = extract_section(full_text, "Study Tips")
             roadmap = extract_section(full_text, "Subject Roadmap")
             courses = extract_section(full_text, "Course/Resource Suggestions") # Example

             return {
                "full_response": full_text,
                "plan": plan or "Could not parse plan.",
                "tips": tips or "Could not parse tips.",
                "roadmap": roadmap or "Could not parse roadmap.",
                "courses": courses or "Could not parse course suggestions."
             }

        else:
             print(f"Unexpected Cohere response structure: {response}")
             return {"error": "Error: Could not parse AI response."}

    except cohere.CohereError as e:
        print(f"Cohere API error: {e}")
        return {"error": f"Error generating content: {e}"}
    except Exception as e:
        print(f"An unexpected error occurred during AI generation: {e}")
        return {"error": f"An unexpected error occurred during AI generation: {e}"}

def extract_section(text, section_title):
    """Simple helper to extract text under a Markdown heading."""
    # Uses simple string splitting, might need improvement (e.g., regex)
    try:
        parts = text.split(f"**{section_title}**")
        if len(parts) > 1:
            content = parts[1]
            # Try to find the start of the *next* section to delimit current one
            next_heading_pos = content.find("\n**")
            if next_heading_pos != -1:
                return content[:next_heading_pos].strip()
            else:
                return content.strip() # It's the last section
        return None
    except Exception:
        return None # Parsing failed


# --- Database Operations ---
def save_plan_to_db(user_query, subject, generated_data):
    """Saves the generated plan details to the database."""
    db = SessionLocal()
    try:
        new_plan = StudyPlan(
            user_query=user_query,
            subject=subject,
            generated_plan=generated_data.get('plan'),
            generated_tips=generated_data.get('tips'),
            generated_roadmap=generated_data.get('roadmap')
            # Add other fields like 'generated_courses' if needed
        )
        db.add(new_plan)
        db.commit()
        db.refresh(new_plan)
        print(f"Saved plan with ID: {new_plan.id}")
        return new_plan.id
    except Exception as e:
        db.rollback()
        print(f"Database Error saving plan: {e}")
        return None
    finally:
        db.close()

def load_all_plans_from_db():
    """Loads all saved study plans from the database."""
    db = SessionLocal()
    try:
        plans = db.query(StudyPlan).order_by(StudyPlan.created_at.desc()).all()
        # Convert to list of dicts for easier use in Streamlit
        return [plan.to_dict() for plan in plans]
    except Exception as e:
        print(f"Database Error loading plans: {e}")
        return []
    finally:
        db.close()

# --- Initialize Database ---
# Call this function once when the app starts or when needed.
# It's often placed in the main app script before the UI elements.
from models import create_db_and_tables
def initialize_database():
    create_db_and_tables()
    print("Database tables checked/created.")'''