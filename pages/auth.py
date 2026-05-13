"""
Login / Signup page.

Flow:
  - Existing users sign in with username + password.
  - New users create an account (first account becomes admin automatically).
  - On success, user_id / username / is_admin are written to session state
    and app.py takes over from there.
"""

import streamlit as st

from core.auth import authenticate, create_user, init_users_db, user_count


def render() -> None:
    st.title("PrivateAI")
    st.markdown(
        "Your documents. Your key. Your data — fully encrypted and never shared."
    )
    st.divider()

    init_users_db()

    is_first_user = user_count() == 0
    if is_first_user:
        st.info(
            "No accounts exist yet. Create the first account — it will be the **admin** account."
        )

    tab_login, tab_signup = st.tabs(["Sign In", "Create Account"])

    # ── Sign In ───────────────────────────────────────────────────────────────
    with tab_login:
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Sign In", type="primary", key="login_btn", use_container_width=True):
            if not username or not password:
                st.error("Enter your username and password.")
            else:
                user = authenticate(username, password)
                if user:
                    st.session_state["user_id"] = user["id"]
                    st.session_state["username"] = user["username"]
                    st.session_state["is_admin"] = bool(user["is_admin"])
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

    # ── Create Account ────────────────────────────────────────────────────────
    with tab_signup:
        new_username = st.text_input("Choose a username", key="signup_username")
        new_password = st.text_input(
            "Choose a password (min 8 characters)", type="password", key="signup_password"
        )
        confirm_password = st.text_input(
            "Confirm password", type="password", key="signup_confirm"
        )

        if st.button("Create Account", type="primary", key="signup_btn", use_container_width=True):
            if not new_username or not new_password:
                st.error("Username and password are required.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            elif len(new_password) < 8:
                st.error("Password must be at least 8 characters.")
            else:
                try:
                    create_user(new_username, new_password)
                    st.success("Account created! Sign in with your new credentials.")
                except Exception as exc:
                    if "UNIQUE" in str(exc):
                        st.error("That username is already taken.")
                    else:
                        st.error(f"Could not create account: {exc}")
