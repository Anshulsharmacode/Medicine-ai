import streamlit as st
import requests
import json

st.set_page_config(page_title="Medical Chatbot", page_icon="🏥", layout="wide")

st.title("Medical Chatbot")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


def display_medicine_info(item):
    with st.expander(f"{item.get('medicine_name', 'Unknown Medicine')}"):
        col1, col2 = st.columns([1, 2])
        with col1:
            if "image_url" in item:
                st.image(item["image_url"], use_column_width=True)
        with col2:
            st.markdown(f"**Composition:** {item.get('composition', 'N/A')}")
            st.markdown(f"**Uses:** {item.get('uses', 'N/A')}")
            st.markdown(f"**Side Effects:** {item.get('sideeffects', 'N/A')}")
            st.markdown(f"**Manufacturer:** {item.get('manufacturer', 'N/A')}")
            st.markdown(f"**Price:** {item.get('price', 'N/A')}")
            st.markdown(f"**Pack Size:** {item.get('packsizelabel', 'N/A')}")
            st.markdown(f"**Type:** {item.get('type', 'N/A')}")

# Chat input
query = st.chat_input("Ask about medicines, compositions, or uses:")

if query:
    # Display user message in chat message container
    st.chat_message("user").markdown(query)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": query})

    # Send request to backend
    try:
        response = requests.post("http://localhost:8000/answer", json={"text": query})
        response.raise_for_status()
        answer = response.json()

        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            st.markdown("### AI Response:")
            st.markdown(answer["gemini_answer"])

            # if answer["exact_matches"]:
            #     st.markdown("### Exact Matches:")
            #     for item in answer["exact_matches"]:
            #         display_medicine_info(item)

            if answer["data"]:
                st.markdown("### Related Medicines:")
                for item in answer["data"]:
                    display_medicine_info(item)

        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": answer["gemini_answer"]})
        
    except requests.exceptions.RequestException as e:
        st.error(f"Error connecting to the server: {str(e)}")


