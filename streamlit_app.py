import streamlit as st
import requests

API_BASE = "http://127.0.0.1:8000"

# Max seconds to wait for API. Stops UI from hanging.
TIMEOUT = 15
# AI ticket needs longer: 2x Gemini calls (embedding + decision) can take 20-60s.
AI_TIMEOUT = 90

st.set_page_config(page_title="Support Ticket Assistant", page_icon="🎫", layout="centered")

# Session state stores the JWT token and user email across page interactions
if "token" not in st.session_state:
    st.session_state.token = None
if "email" not in st.session_state:
    st.session_state.email = None

def get_headers():
    # Returns the Authorization header with the stored JWT token
    return {"Authorization": f"Bearer {st.session_state.token}"}

def show_login_page():
    st.title("Support Ticket Decision Assistant")
    st.subheader("Login or Register")
    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        st.markdown("#### Login to your account")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            if not email or not password:
                st.error("Please enter both email and password.")
            else:
                # Send login. Timeout stops hang if API is down.
                response = requests.post(f"{API_BASE}/login", json={"email": email, "password": password}, timeout=TIMEOUT)
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.token = data["access_token"]
                    st.session_state.email = email
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid email or password.")

    with tab2:
        st.markdown("#### Create a new account")
        reg_email = st.text_input("Email", key="reg_email")
        reg_password = st.text_input("Password", type="password", key="reg_password")
        if st.button("Register"):
            if not reg_email or not reg_password:
                st.error("Please enter both email and password.")
            else:
                # Send register. Timeout stops hang if API is down.
                response = requests.post(f"{API_BASE}/register", json={"email": reg_email, "password": reg_password}, timeout=TIMEOUT)
                if response.status_code == 201:
                    st.success("Account created! Please login.")
                else:
                    st.error(response.json().get("detail", "Registration failed."))

def show_submit_ticket_page():
    st.title("Submit a Support Ticket")
    st.markdown(f"Logged in as: **{st.session_state.email}**")
    st.divider()
    message = st.text_area("Describe your issue", height=150, placeholder="e.g. My package arrived damaged and I want a refund.")
    if st.button("Submit Ticket"):
        if not message.strip():
            st.error("Please describe your issue before submitting.")
        else:
            with st.spinner("Analysing your ticket with AI... (can take up to 60s)"):
                # Send ticket. AI needs longer timeout than login.
                try:
                    response = requests.post(
                        f"{API_BASE}/tickets",
                        json={"message": message},
                        headers=get_headers(),
                        timeout=AI_TIMEOUT
                    )
                except requests.exceptions.Timeout:
                    st.error("AI is taking longer than expected. Check 'My Tickets' in 30s — your ticket may already be saved.")
                    return
                except requests.exceptions.ConnectionError:
                    st.error("Cannot reach backend at http://127.0.0.1:8000. Is uvicorn running?")
                    return
            if response.status_code == 201:
                data = response.json()
                decision = data["decision"]
                st.success("Ticket submitted successfully!")
                st.divider()
                st.subheader("AI Decision")
                action_colors = {
                    "approve_refund": "green",
                    "deny_refund": "red",
                    "escalate": "orange",
                    "request_more_info": "blue"
                }
                action = decision.get("action", "escalate")
                color = action_colors.get(action, "gray")
                st.markdown(f"**Action:** :{color}[{action.replace('_', ' ').upper()}]")
                st.markdown(f"**Confidence:** {round(decision.get('confidence', 0) * 100)}%")
                st.markdown(f"**Reason:** {decision.get('reason', 'N/A')}")
                st.markdown(f"**Sources used:** {', '.join(decision.get('sources', []))}")
            elif response.status_code == 401:
                st.error("Session expired. Please login again.")
                st.session_state.token = None
                st.rerun()
            else:
                st.error("Something went wrong. Please try again.")

def show_my_tickets_page():
    st.title("My Tickets")
    st.markdown(f"Logged in as: **{st.session_state.email}**")
    st.divider()
    # Load tickets. Timeout stops hang if API is down.
    response = requests.get(f"{API_BASE}/tickets", headers=get_headers(), timeout=TIMEOUT)
    if response.status_code == 200:
        tickets = response.json()
        if not tickets:
            st.info("You have not submitted any tickets yet.")
        else:
            for ticket in tickets:
                with st.expander(f"Ticket #{ticket['id']} — {ticket.get('action', 'Pending').replace('_', ' ').upper()}"):
                    st.markdown(f"**Message:** {ticket['message']}")
                    st.markdown(f"**Action:** {ticket.get('action', 'N/A')}")
                    st.markdown(f"**Confidence:** {round((ticket.get('confidence') or 0) * 100)}%")
                    st.markdown(f"**Submitted:** {ticket['created_at']}")
                    if st.button(f"View Full Details", key=f"details_{ticket['id']}"):
                        # Load one ticket. Timeout stops hang if API is down.
                        detail_response = requests.get(
                            f"{API_BASE}/tickets/{ticket['id']}",
                            headers=get_headers(),
                            timeout=TIMEOUT
                        )
                        if detail_response.status_code == 200:
                            detail = detail_response.json()
                            st.json(detail)
    elif response.status_code == 401:
        st.error("Session expired. Please login again.")
        st.session_state.token = None
        st.rerun()
    else:
        st.error("Failed to load tickets.")

# Sidebar navigation — only shown when logged in
if st.session_state.token:
    st.sidebar.title("Navigation")
    st.sidebar.markdown(f"Logged in as **{st.session_state.email}**")
    page = st.sidebar.radio("Go to", ["Submit Ticket", "My Tickets"])
    if st.sidebar.button("Logout"):
        st.session_state.token = None
        st.session_state.email = None
        st.rerun()
    if page == "Submit Ticket":
        show_submit_ticket_page()
    elif page == "My Tickets":
        show_my_tickets_page()
else:
    show_login_page()