import os
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

from google.adk.agents import Agent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.exceptions import DocumentNotFoundException

# Load environment variables from .env file
load_dotenv()


USER_ID = "Chris"


# --- Enhanced Couchbase Memory Class ---
class CouchbaseMemory:
    def __init__(
        self,
        conn_str,
        username,
        password,
        bucket_name,
        scope_name="_default",
        collection_name="_default",
    ):
        self.cluster = Cluster(
            conn_str, ClusterOptions(PasswordAuthenticator(username, password))
        )
        self.bucket = self.cluster.bucket(bucket_name)
        self.scope = self.bucket.scope(scope_name)
        self.collection = self.scope.collection(collection_name)
        print("[Memory System] Connected to Couchbase Capella")

    def _doc_id(self, user_id: str):
        return f"user::{user_id}"

    def initialize_user_schema(self, user_id: str, user_data: Optional[dict] = None):
        """Initialize a user document with the structured schema"""
        doc_id = self._doc_id(user_id)
        
        default_schema = {
            "personal_info": {
                "name": "",
                "age": 0,
                "domain": ""
            },
            "daily_routine": {
                "meal_timings": {
                    "breakfast": "",
                    "lunch": "",
                    "dinner": ""
                },
                "working_hours": {
                    "start": "",
                    "end": "",
                    "timezone": ""
                },
                "workout_preferences": []
            },
            "habits_and_behaviors": {
                "procrastination_habits": [],
                "known_blockers": []
            },
            "task_tracking": {
                "current_tasks": [],
                "completed_tasks": []
            },
            "productivity_insights": {
                "best_focus_times": [],
                "energy_levels": {
                    "morning": "",
                    "afternoon": "",
                    "evening": ""
                },
                "habit_streaks": {
                    "workout_streak_days": 0,
                    "task_completion_streak": 0
                }
            },
            "preferences": {
                "notifications": {
                    "reminder_frequency": "",
                    "preferred_channels": []
                },
                "motivation_style": ""
            },
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "version": 1
            }
        }
        
        # Merge with provided user data if any
        if user_data:
            default_schema.update(user_data)
            
        # Update metadata
        default_schema["metadata"]["last_updated"] = datetime.now().isoformat()
        
        try:
            # Check if document exists
            existing_doc = self.collection.get(doc_id).content_as[dict]
            # Merge with existing data
            for key, value in default_schema.items():
                if key not in existing_doc:
                    existing_doc[key] = value
            existing_doc["metadata"]["last_updated"] = datetime.now().isoformat()
            self.collection.upsert(doc_id, existing_doc)
            print(f"[Memory System] Updated existing schema for user '{user_id}'")
        except DocumentNotFoundException:
            # Create new document
            self.collection.upsert(doc_id, default_schema)
            print(f"[Memory System] Created new user schema for user '{user_id}'")
        
        return True

    def update_user_section(self, user_id: str, section: str, data: dict):
        """Update a specific section of the user document"""
        doc_id = self._doc_id(user_id)
        try:
            doc = self.collection.get(doc_id).content_as[dict]
        except DocumentNotFoundException:
            # Initialize schema if document doesn't exist
            self.initialize_user_schema(user_id)
            doc = self.collection.get(doc_id).content_as[dict]
        
        # Ensure metadata structure exists
        if "metadata" not in doc:
            doc["metadata"] = {
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "version": 1
            }
        
        # Update the specified section
        if section in doc:
            if isinstance(doc[section], dict) and isinstance(data, dict):
                doc[section].update(data)
            else:
                doc[section] = data
        else:
            doc[section] = data
        
        # Update metadata
        doc["metadata"]["last_updated"] = datetime.now().isoformat()
        
        self.collection.upsert(doc_id, doc)
        print(f"[Memory System] Updated section '{section}' for user '{user_id}'")
        return True

    def get_user_section(self, user_id: str, section: Optional[str] = None):
        """Get a specific section or the entire user document"""
        doc_id = self._doc_id(user_id)
        try:
            doc = self.collection.get(doc_id).content_as[dict]
            if section:
                return doc.get(section, {})
            return doc
        except DocumentNotFoundException:
            print(f"[Memory System] No document found for user '{user_id}'")
            return {} if section else {}

    def _add_task(self, user_id: str, task_data: dict):
        """Add a new task to current_tasks"""
        doc_id = self._doc_id(user_id)
        try:
            doc = self.collection.get(doc_id).content_as[dict]
        except DocumentNotFoundException:
            self.initialize_user_schema(user_id)
            doc = self.collection.get(doc_id).content_as[dict]
        
        # Ensure task_tracking structure exists
        if "task_tracking" not in doc:
            doc["task_tracking"] = {"current_tasks": [], "completed_tasks": []}
        if "current_tasks" not in doc["task_tracking"]:
            doc["task_tracking"]["current_tasks"] = []
        
        # Ensure metadata structure exists
        if "metadata" not in doc:
            doc["metadata"] = {
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "version": 1
            }
        
        # Add task with timestamp
        task_data["last_activity"] = datetime.now().isoformat()
        doc["task_tracking"]["current_tasks"].append(task_data)
        doc["metadata"]["last_updated"] = datetime.now().isoformat()
        
        self.collection.upsert(doc_id, doc)
        print(f"[Memory System] Added task '{task_data.get('description', 'Unknown')}' for user '{user_id}'")
        return True

    def _complete_task(self, user_id: str, task_id: str):
        """Move a task from current_tasks to completed_tasks"""
        doc_id = self._doc_id(user_id)
        try:
            doc = self.collection.get(doc_id).content_as[dict]
        except DocumentNotFoundException:
            return False
        
        # Ensure task_tracking structure exists
        if "task_tracking" not in doc:
            doc["task_tracking"] = {"current_tasks": [], "completed_tasks": []}
        if "current_tasks" not in doc["task_tracking"]:
            doc["task_tracking"]["current_tasks"] = []
        if "completed_tasks" not in doc["task_tracking"]:
            doc["task_tracking"]["completed_tasks"] = []
        
        # Find and remove task from current_tasks
        current_tasks = doc["task_tracking"]["current_tasks"]
        completed_task = None
        
        for i, task in enumerate(current_tasks):
            if task.get("task_id") == task_id:
                completed_task = current_tasks.pop(i)
                break
        
        if completed_task:
            # Ensure metadata structure exists
            if "metadata" not in doc:
                doc["metadata"] = {
                    "created_at": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "version": 1
                }
            
            # Add to completed_tasks
            completed_task["completed_on"] = datetime.now().isoformat()
            completed_task["status"] = "completed"
            doc["task_tracking"]["completed_tasks"].append(completed_task)
            doc["metadata"]["last_updated"] = datetime.now().isoformat()
            
            self.collection.upsert(doc_id, doc)
            print(f"[Memory System] Completed task '{completed_task.get('description', 'Unknown')}' for user '{user_id}'")
            return True
        
        return False

    def _update_productivity_insights(self, user_id: str, insights: dict):
        """Update productivity insights"""
        return self.update_user_section(user_id, "productivity_insights", insights)

    def update_habit_streaks(self, user_id: str, streaks: dict):
        """Update habit streaks"""
        doc_id = self._doc_id(user_id)
        try:
            doc = self.collection.get(doc_id).content_as[dict]
        except DocumentNotFoundException:
            self.initialize_user_schema(user_id)
            doc = self.collection.get(doc_id).content_as[dict]
        
        # Ensure productivity_insights structure exists
        if "productivity_insights" not in doc:
            doc["productivity_insights"] = {
                "best_focus_times": [],
                "energy_levels": {"morning": "", "afternoon": "", "evening": ""},
                "habit_streaks": {"workout_streak_days": 0, "task_completion_streak": 0}
            }
        if "habit_streaks" not in doc["productivity_insights"]:
            doc["productivity_insights"]["habit_streaks"] = {
                "workout_streak_days": 0, 
                "task_completion_streak": 0
            }
        
        # Ensure metadata structure exists
        if "metadata" not in doc:
            doc["metadata"] = {
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "version": 1
            }
        
        doc["productivity_insights"]["habit_streaks"].update(streaks)
        doc["metadata"]["last_updated"] = datetime.now().isoformat()
        
        self.collection.upsert(doc_id, doc)
        print(f"[Memory System] Updated habit streaks for user '{user_id}'")
        return True




# --- Replace with your Capella credentials ---
COUCHBASE_CONN_STR = os.getenv("COUCHBASE_CONN_STR")
COUCHBASE_USERNAME = os.getenv("COUCHBASE_USERNAME")
COUCHBASE_PASSWORD = os.getenv("COUCHBASE_PASSWORD")
COUCHBASE_BUCKET = os.getenv("COUCHBASE_BUCKET")

persistent_data = CouchbaseMemory(
    conn_str=COUCHBASE_CONN_STR,
    username=COUCHBASE_USERNAME,
    password=COUCHBASE_PASSWORD,
    bucket_name=COUCHBASE_BUCKET,
    scope_name="_default",  # using default scope
    collection_name="_default",  # using default collection
)


# --- New Schema-based Functions ---
def initialize_user_profile() -> dict:
    """Initialize user profile with structured schema"""
    user_id = getattr(initialize_user_profile, "user_id", USER_ID)
    
    success = persistent_data.initialize_user_schema(user_id, None)
    if success:
        return {"status": "success", "message": f"User profile initialized for {user_id}"}
    return {"status": "error", "message": "Failed to initialize user profile"}


def update_personal_info(personal_updates: Dict[str, Any]) -> dict:
    """Update personal information. Pass a dict with keys: name, age, domain"""
    user_id = getattr(update_personal_info, "user_id", USER_ID)
    
    personal_info = {}
    
    # Extract and validate the personal updates
    if "name" in personal_updates and personal_updates["name"]:
        personal_info["name"] = personal_updates["name"]
    if "age" in personal_updates and personal_updates["age"]:
        personal_info["age"] = personal_updates["age"]
    if "domain" in personal_updates and personal_updates["domain"]:
        personal_info["domain"] = personal_updates["domain"]
    
    if personal_info:
        success = persistent_data.update_user_section(user_id, "personal_info", personal_info)
        if success:
            return {"status": "success", "message": "Personal information updated"}
    
    return {"status": "error", "message": "No information provided to update"}


def update_daily_routine(routine_updates: Dict[str, Any]) -> dict:
    """Update daily routine information. Pass a dict with keys: meal_timings, working_hours, workout_preferences"""
    user_id = getattr(update_daily_routine, "user_id", USER_ID)
    
    routine_data = {}
    
    # Extract and validate the routine updates
    if "meal_timings" in routine_updates and routine_updates["meal_timings"]:
        routine_data["meal_timings"] = routine_updates["meal_timings"]
    if "working_hours" in routine_updates and routine_updates["working_hours"]:
        routine_data["working_hours"] = routine_updates["working_hours"]
    if "workout_preferences" in routine_updates and routine_updates["workout_preferences"]:
        routine_data["workout_preferences"] = routine_updates["workout_preferences"]
    
    if routine_data:
        success = persistent_data.update_user_section(user_id, "daily_routine", routine_data)
        if success:
            return {"status": "success", "message": "Daily routine updated"}
    
    return {"status": "error", "message": "No routine information provided"}


def add_task(task_description: str, priority: str, due_date: str) -> dict:
    """Add a new task to the user's task list"""
    user_id = getattr(add_task, "user_id", USER_ID)
    
    # Generate task ID
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    task_data = {
        "task_id": task_id,
        "description": task_description,
        "priority": priority,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    
    if due_date and due_date.strip():
        task_data["due_date"] = due_date
    
    success = persistent_data._add_task(user_id, task_data)
    if success:
        return {"status": "success", "message": f"Task '{task_description}' added with ID: {task_id}", "task_id": task_id}
    
    return {"status": "error", "message": "Failed to add task"}


def complete_task(task_id: str) -> dict:
    """Mark a task as completed"""
    user_id = getattr(complete_task, "user_id", USER_ID)
    
    success = persistent_data._complete_task(user_id, task_id)
    if success:
        return {"status": "success", "message": f"Task {task_id} marked as completed"}
    
    return {"status": "error", "message": f"Failed to complete task {task_id} - task not found"}


def get_current_tasks() -> dict:
    """Get all current tasks for the user"""
    user_id = getattr(get_current_tasks, "user_id", USER_ID)
    
    tasks = persistent_data.get_user_section(user_id, "task_tracking")
    current_tasks = tasks.get("current_tasks", [])
    
    return {"status": "success", "current_tasks": current_tasks, "count": len(current_tasks)}


def update_productivity_insights(insights_updates: Dict[str, Any]) -> dict:
    """Update productivity insights. Pass a dict with keys: best_focus_times, energy_levels, habit_streaks"""
    user_id = getattr(update_productivity_insights, "user_id", USER_ID)
    
    insights = {}
    
    # Extract and validate the insights updates
    if "best_focus_times" in insights_updates and insights_updates["best_focus_times"]:
        insights["best_focus_times"] = insights_updates["best_focus_times"]
    if "energy_levels" in insights_updates and insights_updates["energy_levels"]:
        insights["energy_levels"] = insights_updates["energy_levels"]
    if "habit_streaks" in insights_updates and insights_updates["habit_streaks"]:
        insights["habit_streaks"] = insights_updates["habit_streaks"]
    
    if insights:
        success = persistent_data._update_productivity_insights(user_id, insights)
        if success:
            return {"status": "success", "message": "Productivity insights updated"}
    
    return {"status": "error", "message": "No insights provided"}


def add_habit_or_blocker(category: str, item: str) -> dict:
    """Add a habit or blocker to the user's profile"""
    user_id = getattr(add_habit_or_blocker, "user_id", USER_ID)
    
    if category not in ["procrastination_habits", "known_blockers"]:
        return {"status": "error", "message": "Category must be 'procrastination_habits' or 'known_blockers'"}
    
    habits_data = persistent_data.get_user_section(user_id, "habits_and_behaviors")
    if category not in habits_data:
        habits_data[category] = []
    
    if item not in habits_data[category]:
        habits_data[category].append(item)
        success = persistent_data.update_user_section(user_id, "habits_and_behaviors", habits_data)
        if success:
            return {"status": "success", "message": f"Added '{item}' to {category}"}
    
    return {"status": "info", "message": f"'{item}' already exists in {category}"}


def get_user_profile(section: str) -> dict:
    """Get user profile or a specific section. Use empty string for full profile"""
    user_id = getattr(get_user_profile, "user_id", USER_ID)
    
    if section and section.strip():
        data = persistent_data.get_user_section(user_id, section)
        return {"status": "success", "section": section, "data": data}
    else:
        data = persistent_data.get_user_section(user_id)
        return {"status": "success", "profile": data}





productivity_agent = Agent(
    name="productivity_assistant",
    model="gemini-2.5-flash",
    description="A comprehensive productivity assistant that helps with task management, habit tracking, and personalized recommendations using structured user profiles.",
    instruction="""
You are a comprehensive Productivity Assistant with access to a rich user profile system. Your goal is to help users be more productive by understanding their habits, preferences, and patterns.

User Profile Structure:
- Personal Info: name, age, domain
- Daily Routine: meal timings, working hours, workout preferences
- Habits & Behaviors: procrastination habits, known blockers
- Task Tracking: current tasks, completed tasks
- Productivity Insights: best focus times, energy levels, habit streaks
- Preferences: notifications, motivation style

Core Functions:
1. **Task Management**: Add, complete, and track tasks
2. **Profile Management**: Update personal info, daily routines, habits
3. **Productivity Insights**: Track and analyze productivity patterns
4. **Habit Tracking**: Monitor procrastination habits and productivity blockers

Workflow:
1. For new users, help them set up their profile using `initialize_user_profile`
2. For task requests, use `add_task` (requires priority and due_date), `complete_task`, and `get_current_tasks`
3. For productivity insights, use `update_productivity_insights` with a dict containing updates
4. For habits/blockers, use `add_habit_or_blocker`
5. Always check existing profile data with `get_user_profile` (use empty string for full profile) before making recommendations
6. For personal info updates, use `update_personal_info` with a dict containing the fields to update
7. For routine updates, use `update_daily_routine` with a dict containing meal_timings, working_hours, or workout_preferences

Interaction Style:
- Be proactive in collecting profile information
- Use the user's data to provide personalized recommendations
- Help identify patterns in their productivity and habits
- Offer specific suggestions based on their known blockers and preferences
- Focus on productivity improvement and habit formation
- Provide data-driven insights and progress tracking
""",
    tools=[
        initialize_user_profile,
        update_personal_info,
        update_daily_routine,
        add_task,
        complete_task,
        get_current_tasks,
        update_productivity_insights,
        add_habit_or_blocker,
        get_user_profile,
    ],
)


session_service = InMemorySessionService()
APP_NAME = "productivity_assistant_app"
SESSION_ID = "session_001"

runner = Runner(
    agent=productivity_agent,
    app_name=APP_NAME,
    session_service=session_service,
)


async def call_agent_async(query: str, user_id: str, session_id: str):
    print(f"\n>>> User ({user_id}): {query}")
    content = types.Content(role="user", parts=[types.Part(text=query)])
    
    # Set user_id for all productivity functions
    setattr(initialize_user_profile, "user_id", user_id)
    setattr(update_personal_info, "user_id", user_id)
    setattr(update_daily_routine, "user_id", user_id)
    setattr(add_task, "user_id", user_id)
    setattr(complete_task, "user_id", user_id)
    setattr(get_current_tasks, "user_id", user_id)
    setattr(update_productivity_insights, "user_id", user_id)
    setattr(add_habit_or_blocker, "user_id", user_id)
    setattr(get_user_profile, "user_id", user_id)

    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=content
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_response = event.content.parts[0].text
            print(f"<<< Assistant: {final_response}")
            return final_response

    return "No response received."



async def interactive_chat():
    print("--- Starting Interactive Productivity Assistant ---")
    print("Commands: 'setup' (configure profile), 'profile' (show profile), 'quit' (exit)")
    
    # Check if user has a profile, if not offer to set one up
    profile = get_user_profile("")
    if not profile.get("profile"):
        print("\nWelcome! It looks like you don't have a profile yet.")
        setup_profile = input("Would you like me to set up your productivity profile? (y/n): ").lower()
        if setup_profile == 'y':
            await setup_initial_profile()
    
    while True:
        user_query = input("\n> ")
        
        if user_query.lower() in ["quit", "exit"]:
            print("Ending session. Goodbye!")
            break
        elif user_query.lower() == "setup":
            await setup_initial_profile()
        elif user_query.lower() in ["profile", "show profile"]:
            show_user_profile()
        else:
            await call_agent_async(query=user_query, user_id=USER_ID, session_id=SESSION_ID)

async def setup_initial_profile():
    """Set up initial user profile"""
    print("\n--- Setting Up Your Productivity Profile ---")
    
    # Personal info
    name = input("What's your name? ")
    age_input = input("What's your age? ")
    age = int(age_input) if age_input.isdigit() else 0
    domain = input("What's your professional domain? ")
    
    if name or age or domain:
        personal_updates = {}
        if name: personal_updates["name"] = name
        if age: personal_updates["age"] = age
        if domain: personal_updates["domain"] = domain
        update_personal_info(personal_updates)
    
    # Daily routine
    print("\n--- Daily Routine ---")
    breakfast = input("What time do you usually have breakfast? (e.g., 08:00) ")
    lunch = input("What time do you usually have lunch? (e.g., 13:00) ")
    dinner = input("What time do you usually have dinner? (e.g., 20:00) ")
    
    work_start = input("What time do you start work? (e.g., 09:30) ")
    work_end = input("What time do you end work? (e.g., 18:30) ")
    timezone = input("What's your timezone? (e.g., Europe/Dublin) ")
    
    if any([breakfast, lunch, dinner, work_start, work_end, timezone]):
        meal_timings = {}
        if breakfast: meal_timings["breakfast"] = breakfast
        if lunch: meal_timings["lunch"] = lunch
        if dinner: meal_timings["dinner"] = dinner
        
        working_hours = {}
        if work_start: working_hours["start"] = work_start
        if work_end: working_hours["end"] = work_end
        if timezone: working_hours["timezone"] = timezone
        
        routine_updates = {}
        if meal_timings: routine_updates["meal_timings"] = meal_timings
        if working_hours: routine_updates["working_hours"] = working_hours
        update_daily_routine(routine_updates)
    
    # Habits and blockers
    print("\n--- Habits & Blockers ---")
    procrastination = input("What's your main procrastination habit? ")
    if procrastination:
        add_habit_or_blocker("procrastination_habits", procrastination)
    
    blocker = input("What's your biggest productivity blocker? ")
    if blocker:
        add_habit_or_blocker("known_blockers", blocker)
    
    print("\n✅ Profile setup complete! You can now start using the productivity assistant.")


def show_user_profile():
    """Display user profile in a readable format"""
    print("\n--- Your Productivity Profile ---")
    profile = get_user_profile("")
    
    if not profile.get("profile"):
        print("No profile found. Use 'setup' to create one!")
        return
    
    data = profile["profile"]
    
    # Personal info
    personal = data.get("personal_info", {})
    if personal:
        print(f"\n👤 Personal Info:")
        if personal.get("name"): print(f"   Name: {personal['name']}")
        if personal.get("age"): print(f"   Age: {personal['age']}")
        if personal.get("domain"): print(f"   Domain: {personal['domain']}")
    
    # Daily routine
    routine = data.get("daily_routine", {})
    if routine:
        print(f"\n📅 Daily Routine:")
        meals = routine.get("meal_timings", {})
        if meals:
            print(f"   Meal times: {meals}")
        work = routine.get("working_hours", {})
        if work:
            print(f"   Work hours: {work}")
        workout = routine.get("workout_preferences", [])
        if workout:
            print(f"   Workout preferences: {workout}")
    
    # Task tracking
    tasks = data.get("task_tracking", {})
    if tasks:
        current = tasks.get("current_tasks", [])
        completed = tasks.get("completed_tasks", [])
        print(f"\n📋 Tasks:")
        print(f"   Current: {len(current)} tasks")
        print(f"   Completed: {len(completed)} tasks")
    
    # Productivity insights
    insights = data.get("productivity_insights", {})
    if insights:
        print(f"\n📊 Productivity Insights:")
        focus_times = insights.get("best_focus_times", [])
        if focus_times:
            print(f"   Best focus times: {focus_times}")
        energy = insights.get("energy_levels", {})
        if energy:
            print(f"   Energy levels: {energy}")
        streaks = insights.get("habit_streaks", {})
        if streaks:
            print(f"   Habit streaks: {streaks}")
    
    print()


async def create_session():
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )


# --- Example Usage Functions ---
def create_example_user_profile():
    """Create an example user profile matching your schema"""
    example_data = {
        "personal_info": {
            "name": "Shubham Dalvi",
            "age": 28,
            "domain": "Data Engineering"
        },
        "daily_routine": {
            "meal_timings": {
                "breakfast": "08:00",
                "lunch": "13:00",
                "dinner": "20:00"
            },
            "working_hours": {
                "start": "09:30",
                "end": "18:30",
                "timezone": "Europe/Dublin"
            },
            "workout_preferences": ["swimming", "walking"]
        },
        "habits_and_behaviors": {
            "procrastination_habits": [
                "doom scrolling",
                "thinking the task is easy and delaying it",
                "gaming"
            ],
            "known_blockers": [
                "lack of clarity in task",
                "frequent context switching",
                "low energy after meals"
            ]
        },
        "productivity_insights": {
            "best_focus_times": ["10:00-12:00", "15:00-17:00"],
            "energy_levels": {
                "morning": "high",
                "afternoon": "low",
                "evening": "medium"
            },
            "habit_streaks": {
                "workout_streak_days": 5,
                "task_completion_streak": 3
            }
        },
        "preferences": {
            "notifications": {
                "reminder_frequency": "every 2 hours",
                "preferred_channels": ["push", "email"]
            },
            "motivation_style": "data-driven feedback and progress visualization"
        }
    }
    
    return persistent_data.initialize_user_schema("Shubham", example_data)


def demo_new_schema():
    """Demonstrate the new schema functionality"""
    print("\n=== Demo: New Schema Functionality ===")
    
    # Initialize user profile
    print("1. Initializing user profile...")
    create_example_user_profile()
    
    # Add a task
    print("\n2. Adding a task...")
    task_result = add_task("Finish ETL pipeline testing", "high", "2025-07-06")
    task_id = task_result.get("task_id")
    print(f"Task added: {task_result}")
    
    # Get current tasks
    print("\n3. Getting current tasks...")
    current_tasks = get_current_tasks()
    print(f"Current tasks: {current_tasks}")
    
    # Update productivity insights
    print("\n4. Updating productivity insights...")
    insights_result = update_productivity_insights({
        "best_focus_times": ["09:00-11:00", "14:00-16:00"],
        "energy_levels": {"morning": "high", "afternoon": "medium", "evening": "low"}
    })
    print(f"Insights updated: {insights_result}")
    
    # Get user profile
    print("\n5. Getting user profile...")
    profile = get_user_profile("")
    print(f"User profile keys: {list(profile.get('profile', {}).keys())}")
    
    # Complete task if we have a task_id
    if task_id:
        print(f"\n6. Completing task {task_id}...")
        complete_result = complete_task(task_id)
        print(f"Task completion: {complete_result}")
    
    print("\n=== Demo Complete ===")


async def main():
    """Main function to choose between demo or interactive chat"""
    print("=== Productivity Assistant with Structured Couchbase Schema ===")
    print("Choose an option:")
    print("1. Run Demo (shows productivity schema functionality)")
    print("2. Interactive Chat (talk with the productivity assistant)")
    print("3. Create Example User Profile (Shubham's profile)")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == "1":
        # Run the demo
        demo_new_schema()
    elif choice == "2":
        # Start interactive chat
        await create_session()
        await interactive_chat()
    elif choice == "3":
        # Create example profile
        print("\nCreating Shubham's example profile...")
        success = create_example_user_profile()
        if success:
            print("✅ Example profile created successfully!")
            print("You can now use option 2 to interact with the productivity assistant.")
        else:
            print("❌ Failed to create example profile.")
    else:
        print("Invalid choice. Please run the script again.")


if __name__ == "__main__":
    if (
        not os.getenv("GOOGLE_API_KEY")
        or os.getenv("GOOGLE_API_KEY") == "YOUR_GOOGLE_API_KEY_HERE"
    ):
        print(
            "ERROR: Please set your GOOGLE_API_KEY environment variable to run this script."
        )
    else:
        asyncio.run(main())
