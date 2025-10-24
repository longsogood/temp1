import streamlit as st
import pandas as pd

# Create a sample DataFrame
data = {'Name': ['Alice', 'Bob', 'Charlie', 'David'],
        'Age': [25, 30, 35, 40],
        'City': ['New York', 'London', 'Paris', 'Tokyo']}
df = pd.DataFrame(data)

st.subheader("Data Editor with Row Selection")

# Display the data editor with multi-row selection enabled
edited_df = st.data_editor(
    df,
    key="my_data_editor",
    # num_rows="dynamic",
    hide_index=True,
    # on_select="rerun",  # Rerun the app when a selection changes
    # selection_mode=["multi-row"], # Allow multiple rows to be selected
)

print(st.session_state["my_data_editor"])
# Retrieve the selected rows
selected_rows_indices = st.session_state["my_data_editor"]["selected_rows"]
selected_rows_data = df.iloc[selected_rows_indices]

if not selected_rows_data.empty:
    st.subheader("Selected Rows:")
    st.dataframe(selected_rows_data)
else:
    st.write("No rows selected.")

st.subheader("Full Edited Data:")
st.dataframe(edited_df)