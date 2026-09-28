import streamlit as st

import agent
import mail

st.set_page_config(page_title="Email Assistant", page_icon="📧")
st.title("📧 Email Assistant")

with st.sidebar:
    st.header("Login")
    email = st.text_input("Email")
    password = st.text_input("App password", type="password")
    if st.button("Login"):
        try:
            mail.login(email, password)
            with st.spinner("Reading your emails..."):
                agent.index_emails(mail.fetch_emails(limit=50))
            st.session_state.logged_in = True
        except Exception as e:
            st.error(f"Login failed: {e}")
    st.caption("Gmail: turn on 2-Step Verification, then create an App Password.")

    st.divider()
    if st.button("Try the demo inbox"):
        mail.start_sandbox()
        agent.index_emails(mail.fetch_emails())
        st.session_state.logged_in = True

    if mail.SANDBOX:
        st.success("Demo mode: nothing is really sent or deleted.")

if not st.session_state.get("logged_in"):
    st.info("Log in from the sidebar to start.")
    st.stop()

inbox_tab, chat_tab = st.tabs(["Inbox", "Chat"])

with inbox_tab:
    if st.button("Refresh & classify"):
        with st.spinner("Classifying..."):
            emails = mail.fetch_emails(limit=15)
            agent.index_emails(emails)
            for e in emails:
                e["category"] = agent.classify(e)
            st.session_state.emails = emails

    category = st.selectbox("Category", ["all"] + agent.CATEGORIES)
    for e in st.session_state.get("emails", []):
        if category in ("all", e["category"]):
            with st.expander(f"[{e['category']}] {e['subject']} — {e['from']}"):
                st.caption(e["date"])
                st.write(e["text"])

with chat_tab:
    if "chat" not in st.session_state:
        st.session_state.chat = []

    for role, text in st.session_state.chat:
        st.chat_message(role).write(text)

    if question := st.chat_input("e.g. Summarize my unread emails"):
        st.chat_message("user").write(question)
        with st.spinner("Thinking..."):
            answer = agent.ask(question)
        st.chat_message("assistant").write(answer)
        st.session_state.chat += [("user", question), ("assistant", answer)]
