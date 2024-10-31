import streamlit as st
from pymongo import MongoClient
from bson.objectid import ObjectId
import bcrypt
import openai
import google.generativeai as genai
import os
from dotenv import load_dotenv
import uuid  # For generating unique keys

# Load environment variables from .env file
load_dotenv()

# MongoDB Atlas connection
client = MongoClient("mongodb+srv://navi:navi@skillnavigator.narra.mongodb.net/?retryWrites=true&w=majority&appName=skillnavigator")
db_candidate = client["candidate"]
db_admin = client["admin"]

# Set up OpenAI API key for Gemini-1.5-flash
genai.configure(api_key=os.getenv("GOOGLE_GEN_AI_API_KEY"))

# Helper functions
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed)

# Streamlit App
st.set_page_config(page_title="Skill Navigator", layout="wide")

# Landing Page
def landing_page():
    st.title("Skill Navigator")
    st.write("Welcome to the Skill Navigator Application!")
    st.write("An intelligent platform for candidates and admins to manage skills and allocations effectively.")
    
    # Use a unique key for each button
    if st.button("New Candidate Signup", key="signup_button"):
        signup_page()
    if st.button("Login", key="login_button"):
        login_page()

# Signup Page
def signup_page():
    st.title("Candidate Signup")
    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Signup", key="signup_submit"):
        hashed_pw = hash_password(password)
        if db_candidate.users.find_one({"email": email}) is None:
            db_candidate.users.insert_one({"username": username, "email": email, "password": hashed_pw})
            st.success("Signup successful! Redirecting to login.")
            login_page()
        else:
            st.warning("Email already exists. Please try logging in.")

# Login Page
def login_page():
    st.title("Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login", key="login_submit"):
        candidate_user = db_candidate.users.find_one({"email": email})
        admin_user = db_admin.users.find_one({"email": email})

        if candidate_user and verify_password(password, candidate_user["password"]):
            candidate_dashboard(candidate_user)
        elif admin_user and verify_password(password, admin_user["password"]):
            admin_dashboard()
        else:
            st.error("Invalid credentials.")

# Candidate Dashboard
def candidate_dashboard(user):
    st.sidebar.title(f"Welcome, {user['username']}")
    option = st.sidebar.selectbox("Navigation", ["Home", "Candidate Info", "Batch Allocation", "Course Recommendation", "Tests and Scores", "Logout"])

    if option == "Home":
        st.write(f"Welcome, {user['username']}")
        st.write("Batch Allocation:", user.get("batch_allocation", "Not allocated yet"))
        st.write("Previous Test Scores:")
        if "scores" in user:
            st.bar_chart(user["scores"])
        else:
            st.write("No test scores available.")
        if st.button("Click to fill Candidate Info"):
            candidate_info(user)
    elif option == "Candidate Info":
        candidate_info(user)
    elif option == "Batch Allocation":
        batch_allocation(user)
    elif option == "Course Recommendation":
        course_recommendation(user)
    elif option == "Tests and Scores":
        tests_and_scores(user)
    elif option == "Logout":
        landing_page()

def candidate_info(user):
    st.title("Candidate Info")
    name = st.text_input("Name", value=user.get("name", ""))
    email_id = st.text_input("Email ID", value=user.get("email", ""))
    degree = st.text_input("Degree", value=user.get("degree", ""))
    specialization = st.text_input("Specialization", value=user.get("specialization", ""))
    phone_number = st.text_input("Phone Number", value=user.get("phone_number", ""))
    certifications = st.selectbox("Certifications", ["Java and AWS", ".NET and Azure", "Python and SQL"])
    internship_details = st.text_input("Internship Details", value=user.get("internship_details", ""))
    courses_completed = st.text_area("Courses Completed (Udemy, Coursera, etc.)", value=user.get("courses_completed", ""))
    linkedin = st.text_input("LinkedIn Profile Link", value=user.get("linkedin", ""))
    github = st.text_input("GitHub Profile Link", value=user.get("github", ""))
    programming_languages = st.text_input("Programming Languages Known", value=user.get("programming_languages", ""))
    resume = st.file_uploader("Upload Resume", type=["pdf", "doc", "docx"])

    if st.button("Submit Info"):
        update_data = {
            "name": name,
            "degree": degree,
            "specialization": specialization,
            "phone_number": phone_number,
            "certifications": certifications,
            "internship_details": internship_details,
            "courses_completed": courses_completed,
            "linkedin": linkedin,
            "github": github,
            "programming_languages": programming_languages
        }
        
        # Check for uploaded file
        if resume is not None:
            # Save the uploaded resume to a folder (make sure the path exists)
            resume_path = f"uploads/{resume.name}"
            with open(resume_path, "wb") as f:
                f.write(resume.getbuffer())
            update_data["resume"] = resume_path
        
        db_candidate.users.update_one({"_id": user["_id"]}, {"$set": update_data})
        st.success("Information saved successfully!")

def batch_allocation(user):
    st.title("Batch Allocation")
    certs = user.get("certifications", "")
    if certs == "Java and AWS":
        batch = "Java Batch"
    elif certs == ".NET and Azure":
        batch = ".NET Batch"
    else:
        batch = "Data Engineer Batch"
    db_candidate.users.update_one({"_id": user["_id"]}, {"$set": {"batch_allocation": batch}})
    st.write(f"Allocated Batch: {batch}")

def course_recommendation(user):
    st.title("Course Recommendations and Batch Allocation")
    
    # Check if recommendations already allocated
    if "courses_allocated" in user:
        st.write("Courses and Job Roles already allocated:")
        st.write(user["courses_allocated"], unsafe_allow_html=True)
    else:
        # Batch Allocation based on skill
        skill = user.get("skill", "general IT")  # Default to general if skill not specified
        if skill.lower() in ["java", "aws"]:
            batch = "Java Batch"
        elif skill.lower() in ["azure", ".net"]:
            batch = ".NET Batch"
        else:
            batch = "Data Engineer Batch"
        
        # Store batch allocation in MongoDB
        db_candidate.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"batch_allocation": batch}}
        )

        # Define course recommendations based on the batch allocation
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            f"Provide a list of 5 relevant e-books, websites, and 5 job roles for someone in the {batch}. "
            "Format it in an HTML table with columns: 'Course/Resource', 'Type', and 'Job Role'. Use CSS styling: "
            "table {{ width: 100%; border-collapse: collapse; font-family: sans-serif; }} "
            "th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }} "
            "th {{ background-color: #3498db; color: white; }}"
        )
        
        # Generate recommendations using Gemini model
        response = model.generate_content(prompt)
        recommendations = response.text.strip()

        # Store recommendations in MongoDB
        db_candidate.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"courses_allocated": recommendations}}
        )
        
        # Display recommendations in the Streamlit app
        st.markdown(f"<h2>Course Recommendations</h2>", unsafe_allow_html=True)

def generate_mcq_questions(batch):
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"Generate 15 multiple-choice questions for {batch} with four answer options each, and identify the correct answer for each question."
    response = model.generate_content(prompt)
    questions = response.text.strip().split("\n\n")
    return [q.splitlines() for q in questions]

# Tests and Scores page
def tests_and_scores(user):
    st.title("Tests and Scores")
    
    # Fetch batch allocation
    batch = user.get("batch_allocation", "")
    if not batch:
        st.warning("Batch allocation is missing. Please complete your profile.")
        return

    # Fetch or generate test questions
    if "questions" not in st.session_state:
        st.session_state.questions = generate_mcq_questions(batch)
        st.session_state.current_score = 0
        st.session_state.current_question_index = 0
    
    # Display questions and options
    questions = st.session_state.questions
    index = st.session_state.current_question_index
    
    if index < len(questions):
        question = questions[index]
        st.write(f"Q{index + 1}: {question[0]}")
        
        # Show answer options
        answer = st.radio("Select an answer:", options=question[1:5])
        
        if st.button("Submit Answer"):
            correct_answer = question[5].split(":")[1].strip()  # Assuming format like "Answer: A"
            if answer == correct_answer:
                st.session_state.current_score += 1
            st.session_state.current_question_index += 1
    else:
        # Test completion and score storage
        st.success("Test completed!")
        score = st.session_state.current_score
        st.write(f"Your score: {score} out of {len(questions)}")

        # Update scores in MongoDB, maintaining only the latest 5
        scores = user.get("scores", [])
        if len(scores) >= 5:
            scores.pop(0)
        scores.append(score)
        db_candidate.users.update_one({"_id": user["_id"]}, {"$set": {"scores": scores}})
        
        # Display the bar chart of the last 5 scores
        st.bar_chart(scores)
        
        # Reset session state for a new test
        if st.button("Take Test Again"):
            st.session_state.questions = generate_mcq_questions(batch)
            st.session_state.current_score = 0
            st.session_state.current_question_index = 0

# Admin Dashboard
def admin_dashboard():
    st.title("Admin Dashboard")
    users = list(db_candidate.users.find())
    st.write("User Overview")
    java_batch = data_engineer_batch = net_batch = 0

    for user in users:
        if user["batch_allocation"] == "Java Batch":
            java_batch += 1
        elif user["batch_allocation"] == "Data Engineer Batch":
            data_engineer_batch += 1
        elif user["batch_allocation"] == ".NET Batch":
            net_batch += 1

    st.write(f"Java Batch: {java_batch}")
    st.write(f"Data Engineer Batch: {data_engineer_batch}")
    st.write(f".NET Batch: {net_batch}")

    for user in users:
        st.write(user["name"], user["batch_allocation"], user["specialization"])
        if st.button("Delete", key=user["_id"]):
            db_candidate.users.delete_one({"_id": user["_id"]})
            st.success("User deleted.")

# Run the app
if "page" not in st.session_state:
    st.session_state.page = landing_page()

if __name__ == "__main__":
    landing_page()
