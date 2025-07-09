import streamlit as st
import os
from dotenv import load_dotenv
import google.generativeai as genai
import requests
from datetime import datetime

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Initialize the Gemini model
model = genai.GenerativeModel('gemini-2.5-flash')

# Initialize chat history and user preferences
if "messages" not in st.session_state:
    st.session_state.messages = []
    
if "user_prefs" not in st.session_state:
    st.session_state.user_prefs = {
        "name": None,
        "location": None
    }
    st.session_state.awaiting_preference = "name"  # Track which preference we're asking for

# Set up the Streamlit app
st.title("Rapid Bot 🤖")
st.caption("I can help with tasks, weather and more!")

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ========== API Integration Functions ==========

def get_weather(location):
    """Get current weather for a location using WeatherAPI"""
    api_key = os.getenv("WEATHER_API_KEY")
    base_url = "http://api.weatherapi.com/v1/current.json"
    params = {
        'key': api_key,
        'q': location,
        'aqi': 'no'
    }
    try:
        response = requests.get(base_url, params=params)
        data = response.json()
        if 'error' in data:
            return f"Could not get weather: {data['error']['message']}"
        
        current = data['current']
        return (
            f"🌤️ Weather in {location}:\n\n"
            f"☁️ Condition: {current['condition']['text']}\n"
            f"\n🌡️ Temperature: {current['temp_c']}°C ({current['temp_f']}°F)\n"
            f"\n💧 Humidity: {current['humidity']}%\n"
            f"\n🌬️ Wind: {current['wind_kph']} km/h ({current['wind_mph']} mph)\n"
            f"\n🌞 UV Index: {current.get('uv', 'N/A')}"
        )
    except Exception as e:
        return f"Error getting weather: {str(e)}"

def get_tasks():
    """Get tasks from Todoist"""
    api_key = os.getenv("TODOIST_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        response = requests.get(
            "https://api.todoist.com/rest/v2/tasks",
            headers=headers
        )
        
        # Check for successful response
        if response.status_code != 200:
            return f"Todoist API error: Status {response.status_code}"
        
        # Safely parse JSON
        try:
            tasks = response.json()
        except ValueError:
            return "Invalid response format from Todoist"
        
        # Check if we got a list of tasks
        if not isinstance(tasks, list):
            return "Unexpected response format from Todoist"
        
        # Safely get first 5 tasks
        task_list = []
        for task in tasks[:5]:  # This will work now that we've verified tasks is a list
            if isinstance(task, dict) and 'content' in task:
                task_list.append(f"- {task['content']}")
            else:
                continue
                
        if not task_list:
            return "No valid tasks found in your Todoist!"
        
        return "Here are your upcoming tasks:\n" + "\n".join(task_list)
        
    except Exception as e:
        return f"Error getting tasks: {str(e)}"


def update_preferences(updates):
    """Update user preferences"""
    st.session_state.user_prefs.update(updates)
    if "awaiting_preference" in st.session_state:
        del st.session_state.awaiting_preference
    return "Preferences updated successfully!"

# ========== Preference Setup Flow ==========

def ask_preference_questions():
    """Ask the user for their preferences if not set"""
    if st.session_state.user_prefs["name"] is None:
        st.session_state.awaiting_preference = "name"
        return "Welcome! To personalize your experience, may I know your name?"
    elif st.session_state.user_prefs["location"] is None:
        st.session_state.awaiting_preference = "location"
        return f"Thanks {st.session_state.user_prefs['name']}! Where are you located? (This helps with weather reports)"
        return "Finally, what are your typical work hours? (e.g., 9am-5pm)"
    return None

# ========== Updated Quick Actions Implementation ==========

def handle_quick_action(action):
    """Process quick action button clicks"""
    if action == "weather":
        return get_weather(st.session_state.user_prefs.get("location", "Colombo"))
    elif action == "tasks":
        return get_tasks()
    return "Unknown action"


# ========== Response Generation ==========

def generate_response(prompt):
    """Generate appropriate response based on user input"""
    # Handle preference setting flow
    if "awaiting_preference" in st.session_state:
        pref_type = st.session_state.awaiting_preference
        if pref_type == "name":
            response = update_preferences({"name": prompt})
        elif pref_type == "location":
            response = update_preferences({"location": prompt})
        
        next_question = ask_preference_questions()
        if next_question:
            return response + "\n\n" + next_question
        return response
    
    user_prefs = st.session_state.user_prefs
    
    # Check for manual preference updates
    if "my name is" in prompt.lower():
        name = prompt.lower().split("my name is")[1].strip()
        return update_preferences({"name": name})
    elif "set location to" in prompt.lower():
        location = prompt.lower().split("set location to")[1].strip()
        return update_preferences({"location": location})
    
    # Check if all preferences are set
    preference_question = ask_preference_questions()
    if preference_question:
        return preference_question
    
    # Check for specific commands
    if "weather" in prompt.lower():
        location = prompt.lower().replace("weather", "").strip()
        if not location:
            location = user_prefs["location"]
        return get_weather(location)
    elif "tasks" in prompt.lower() or "todo" in prompt.lower():
        return get_tasks()
    elif "who am i" in prompt.lower():
        return (f"You are {user_prefs['name']}, located in {user_prefs['location']}. "
               )
    elif "help" in prompt.lower():
        return ("I can help with:\n"
               "- Weather information (try 'weather [location]')\n"
               "- Todoist tasks (try 'show my tasks')\n"
               "- Set preferences (try 'my name is...', 'set location to...')\n"
               "- Or ask me anything else!")
    else:
        # Use Gemini for general queries
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Sorry, I encountered an error: {str(e)}"

# ========== Chat Interface ==========

# Chat input
if prompt := st.chat_input("How can I help you today?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Generate assistant response
    with st.chat_message("assistant"):
        response = generate_response(prompt)
        st.markdown(response)
    
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})

# Ask initial preference questions if not set
if all(v is None for v in st.session_state.user_prefs.values()) and not st.session_state.messages:
    with st.chat_message("assistant"):
        initial_question = ask_preference_questions()
        st.markdown(initial_question)
        st.session_state.messages.append({"role": "assistant", "content": initial_question})

# Sidebar with user preferences
with st.sidebar:
    st.header("Your Preferences 👤")
    for key, value in st.session_state.user_prefs.items():
        st.write(f"{key.capitalize()}: {value if value is not None else 'Not set'}")
    
    st.header("Quick Actions ⚙️")
    if st.button("Check Weather 🍃", key="weather_btn"):
        st.session_state.messages.append({"role": "user", "content": "weather"})
        st.session_state.messages.append({"role": "assistant", "content": handle_quick_action("weather")})
        st.rerun()
    
    if st.button("Show Tasks 📋", key="tasks_btn"):
        st.session_state.messages.append({"role": "user", "content": "show my tasks"})
        st.session_state.messages.append({"role": "assistant", "content": handle_quick_action("tasks")})
        st.rerun()
    
    
    if st.button("Clear Chat 🔄", key="clear_chat_btn"):
        st.session_state.messages = []  # Clear chat history
        st.rerun()
    
    st.header("About 📌")
    st.write("This is a personalized digital assistant that helps with daily tasks.")
    st.write("It integrates with Todoist, WeatherAPI.")