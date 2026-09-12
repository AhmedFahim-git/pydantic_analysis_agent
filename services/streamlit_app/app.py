import os
from collections import deque

import httpx2
import streamlit as st


def set_selectbox_index_button():
    st.session_state["select_chat"] = None
    st.session_state["messages"] = []


def set_signin_state():
    st.session_state["auth_init"] = "sign_in"


def set_login_state():
    st.session_state["auth_init"] = "login"


def get_chat_history():
    session_id = st.session_state["select_chat"]
    if session_id is None:
        st.session_state["messages"] = []
    else:
        res = httpx2.get(
            f"{os.environ['AGENT_APP_URL']}/chat/{session_id}/all_messages",
            headers=st.session_state["header"],
            timeout=20,
        )
        res.raise_for_status()
        st.session_state["messages"] = res.json()["message_list"]
        # messages = res.json()["message_list"]
        # print(messages)
        # return messages


def set_jwt(token: str):
    st.session_state["jwt"] = token
    st.session_state["header"] = {"Authorization": f"Bearer {token}"}


def chat_submit_callback(session_id: str | None = None):
    if not session_id:
        res = httpx2.post(
            f"{os.environ['AGENT_APP_URL']}/chat",
            headers=st.session_state["header"],
            json={"role": "user", "content": st.session_state["user_prompt"]},
            timeout=20,
        )
        res.raise_for_status()
        session = res.json()
        session_id = session["session_id"]
        st.session_state["sessions"].appendleft(session_id)
        st.session_state["session_names"][session_id] = session["session_title"]
        st.session_state["select_chat"] = session_id


# Initialize chat history
if "messages" not in st.session_state:
    st.session_state["messages"] = []

if "sessions" not in st.session_state:
    st.session_state["sessions"] = deque()
    st.session_state["session_names"] = {}

if "select_index" not in st.session_state:
    st.session_state["select_index"] = None


with st.empty():
    with st.container():
        st.button("Sign in", on_click=set_signin_state, key="sign_in_1")
        st.button("Login", on_click=set_login_state, key="login_1")
    if st.session_state.get("auth_init") == "sign_in":
        with st.container():
            with st.form("sign_in_form"):
                username = st.text_input("username", key="username_signin")
                email = st.text_input("email", type="email", key="email_signin")
                fullname = st.text_input("fullname", key="fullname_signin")
                password = st.text_input(
                    "password", type="password", key="password_signin"
                )
                submit = st.form_submit_button("Submit")
                if submit:
                    assert (
                        isinstance(username, str)
                        and isinstance(email, str)
                        and isinstance(fullname, str)
                        and isinstance(password, str)
                    )
                    username, email, fullname, password = (
                        username.strip(),
                        email.strip(),
                        fullname.strip(),
                        password.strip(),
                    )
                    if username and email and password and fullname:
                        res = httpx2.post(
                            f"{os.environ['AGENT_APP_URL']}/user/signup",
                            # "http://agent-app-service:8000",
                            json={
                                "username": username,
                                "password": password,
                                "fullname": fullname,
                                "email": email,
                            },
                        )
                        if res.status_code == 409:
                            st.error(
                                "Username already exists. Please try login instead"
                            )
                        else:
                            res.raise_for_status()
                            set_jwt(res.json()["access_token"])
                    else:
                        st.error("Form not filled")
            st.button("Login", on_click=set_login_state, key="login_2")
    elif st.session_state.get("auth_init") == "login":
        with st.container():
            with st.form("login_form"):
                username = st.text_input("username", key="username_login")
                password = st.text_input(
                    "password", type="password", key="password_login"
                )
                submit = st.form_submit_button("Submit")
                if submit:
                    assert isinstance(username, str) and isinstance(password, str)
                    username, password = username.strip(), password.strip()
                    if username and password:
                        res = httpx2.post(
                            f"{os.environ['AGENT_APP_URL']}/auth/token",
                            # "http://agent-app-service:8000",
                            data={
                                "username": username,
                                "password": password,
                            },
                        )
                        if res.status_code == 401:
                            st.error("Username or password incorrect")
                        else:
                            res.raise_for_status()
                            set_jwt(res.json()["access_token"])
                    else:
                        st.error("Form not filled")
            st.button("Sign in", on_click=set_signin_state, key="sign_in_2")
    if st.session_state.get("jwt"):
        if not st.session_state["sessions"]:
            sessions_res = httpx2.get(
                f"{os.environ['AGENT_APP_URL']}/user/details",
                headers=st.session_state["header"],
            )
            sessions_res.raise_for_status()
            for i in sessions_res.json()["sessions"]:
                session_id = i["session_id"]
                st.session_state["sessions"].appendleft(session_id)
                st.session_state["session_names"][session_id] = i["session_title"]
        with st.container():
            chat_session_id = st.selectbox(
                "Select Previous Chat",
                options=st.session_state["sessions"],
                format_func=st.session_state["session_names"].get,
                index=None,
                key="select_chat",
                on_change=get_chat_history,
            )
            new_chat = st.button("New Chat", on_click=set_selectbox_index_button)
            # if chat_session_id:
            #     st.session_state["messages"] = get_chat_history(chat_session_id)
            # else:
            #     st.session_state["messages"] = []

if st.session_state.get("jwt"):
    for message in st.session_state["messages"]:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    if prompt := st.chat_input(
        "User Message",
        key="user_prompt",
        on_submit=chat_submit_callback,
        kwargs={"session_id": chat_session_id},
    ):
        user_prompt = {"role": "user", "content": prompt}
        with st.chat_message("user"):
            st.write(prompt)
        st.session_state["messages"].append(user_prompt)
        res = httpx2.post(
            f"{os.environ['AGENT_APP_URL']}/chat/{chat_session_id}",
            headers=st.session_state["header"],
            json=user_prompt,
            timeout=20,
        )
        res.raise_for_status()
        ai_response = res.json()
        assert ai_response["role"] == "assistant"
        with st.chat_message(ai_response["role"]):
            st.write(ai_response["content"])
        st.session_state["messages"].append(ai_response)
