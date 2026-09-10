from collections import deque
from uuid import uuid4

import streamlit as st


def set_selectbox_index_button():
    st.session_state['select_chat'] = None


def set_signin_state():
    st.session_state["auth_init"] = "sign_in"


def set_login_state():
    st.session_state["auth_init"] = "login"


def get_chat_history(session_id: str) -> list[str]:
    assert session_id in st.session_state['local_chat_history']
    return st.session_state['local_chat_history'][session_id]


def chat_submit_callback(chat_session_id: str | None = None):
    if not chat_session_id:
        chat_session_id = str(uuid4())
        st.session_state['sessions'].appendleft(chat_session_id)
        st.session_state['session_names'][chat_session_id] = "name" + chat_session_id
        st.session_state['select_chat'] = chat_session_id
        st.session_state['local_chat_history'][chat_session_id] = st.session_state['messages']


# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

if "sessions" not in st.session_state:
    st.session_state['sessions'] = deque()
    st.session_state['session_names'] = {}

if 'select_index' not in st.session_state:
    st.session_state['select_index'] = None

if 'local_chat_history' not in st.session_state:
    st.session_state['local_chat_history'] = {}

with st.empty():
    with st.container():
        st.button("Sign in", on_click=set_signin_state, key="sign_in_1")
        st.button("Login", on_click=set_login_state, key="login_1")
    if st.session_state.get("auth_init") == "sign_in":
        with st.container():
            with st.form("sign_in_form"):
                username = st.text_input("username", key="username_signin")
                email = st.text_input("email", type="email", key="email_signin")
                password = st.text_input(
                    "password", type="password", key="password_signin"
                )
                submit = st.form_submit_button("Submit")
                if submit:
                    assert (
                            isinstance(username, str)
                            and isinstance(email, str)
                            and isinstance(password, str)
                    )
                    if username.strip() and email.strip() and password.split():
                        st.session_state["jwt"] = "temp"
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
                    if username.strip() and password.split():
                        st.session_state["jwt"] = "temp"
                    else:
                        st.error("Form not filled")
            st.button("Sign in", on_click=set_signin_state, key="sign_in_2")
    if st.session_state.get("jwt"):
        with st.container():
            chat_session_id: str = st.selectbox(
                "Select Previous Chat",
                options=st.session_state["sessions"],
                format_func=st.session_state["session_names"].get,
                index=None,
                key='select_chat'
            )
            new_chat = st.button("New Chat", on_click=set_selectbox_index_button)
            if chat_session_id:
                st.session_state["messages"] = get_chat_history(chat_session_id)
            else:
                st.session_state["messages"] = deque()

if st.session_state.get("jwt"):
    for i, message in enumerate(st.session_state["messages"]):
        if (i % 2) == 0:
            with st.chat_message("user"):
                st.write(message)
        else:
            with st.chat_message("assistant"):
                st.write(message)

    if prompt := st.chat_input("User Message", on_submit=chat_submit_callback,
                               kwargs={"chat_session_id": chat_session_id}):
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            st.write("Echoing " + prompt)
        st.session_state["messages"].append(prompt)
        st.session_state["messages"].append("Echoing " + prompt)
