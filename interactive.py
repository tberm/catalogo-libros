import streamlit as st
import pandas as pd
from functools import partial
from pathlib import Path
from threading import Thread
from streamlit_gsheets import GSheetsConnection
from gspread.exceptions import WorksheetNotFound



st.set_page_config(layout="wide")

st.title("Catálogo libros")


if not st.experimental_user.is_logged_in:
    st.write("Click to log in with your Google account")
    if st.button("Log in"):
        st.login()
    st.stop()

st.write(f"Logged in as {st.experimental_user.email}")

if st.button("Log out"):
    st.logout()

if st.experimental_user.email not in st.secrets["allowed_users"]:
    st.write("User not authorised")
    st.stop()


st.header("How to use")
st.markdown("""
1. Use form to filter books to specific rooms and row/column, or to search.
2. Select books by clicking in the left-most column of the table.
3. As you pick out books to take to el Remate, select them and click "Añadir al carrito"
4. Once you've picked all your books, switch to the "Carrito" tab where you can get the list of books selected.

Don't forget...
* The carrito list is tied to your login. Several people can log in at once with
  separate accounts and make their own carritos. Don't login as the same user in
  several places at once or you will overwrite the carrito.
* All the data shown here is saved in Google Sheets. You can access it [here](https://docs.google.com/spreadsheets/d/1JuEc3qxMzNzyvzJy_dkin70ydD3bxxbRHAw-xVLcF0k/edit?gid=1534151630#gid=1534151630).
* If you need to make changes to the catalogue, edit the above sheet, but don't rename the columns or move them or my app will be sad :(
* Also don't add/remove rows in the spreadsheet while you have things in the carrito or it will get confused.
* The app doesn't move things to "Lugar: Enviado a Remate" because we stopped updating that a long time ago.
""")


carrito_name = "carrito_" + st.experimental_user.given_name


def blank_carrito_df(main_df):
    # reorder cols for easy copy paste
    output_cols = ["Titulo", "Autor", "Año"]
    cols = output_cols + [c for c in main_df.columns if c not in output_cols] + ["orig_idx"]
    return pd.DataFrame(columns=cols)


def sync_carrito(carrito_df):
    try:
        sheets_conn.update(worksheet=carrito_name, data=carrito_df)
    except WorksheetNotFound:
        sheets_conn.create(worksheet=carrito_name, data=carrito_df)


def load_data():
    if not st.experimental_user.is_logged_in:
        return None, None

    df = sheets_conn.read(worksheet="catalogo", dtype="str")
    cols = df.columns
    df = df[cols[0:4]].join([df[cols[11:14]], df[cols[4:11]]])

    try:
        carrito_df = pd.read_csv(carrito_name + ".csv", dtype="str")
    except FileNotFoundError:
        try:
            carrito_df = sheets_conn.read(worksheet=carrito_name, dtype="str")
        except WorksheetNotFound:
            carrito_df = blank_carrito_df(df)
            carrito_df = sheets_conn.create(worksheet=carrito_name, data=carrito_df)
        
        carrito_df.to_csv(carrito_name + ".csv", index=False)
    else:
        target = partial(sync_carrito, carrito_df)
        thread = Thread(target=target)
        thread.start()


    carrito_df["orig_idx"] = carrito_df["orig_idx"].astype("int")
    carrito_df = carrito_df.set_index("orig_idx")
    df.drop(index=carrito_df.index, inplace=True)

    return df, carrito_df


def save_checked(df):
    st.session_state.checked = df["Selected"]


def filter_by_search(search_str):
    return df[
        df["Titulo"].str.lower().str.contains(search_str) |
        df["Autor"].str.lower().str.contains(search_str) |
        df["Año"].str.lower().str.contains(search_str)
    ]

sheets_conn = st.connection("gsheets", type=GSheetsConnection)

full_df, carrito_df = load_data()

main_tab, carrito_tab  = st.tabs(["Catálogo", "Carrito"])

with main_tab:
    lugar_w = st.pills(
        "Lugar",
        options=full_df["Lugar"].unique(),
        default=set(full_df["Lugar"].unique()) - {"Enviado a Remate"},
        selection_mode="multi",
    )

    df = full_df[full_df["Lugar"].isin(lugar_w)]

    col1, col2, col3 = st.columns(3)

    row_nums = sorted([int(r) for r in df["Row"].unique() if not pd.isna(r)])
    row_w = col1.selectbox("Row", ["All"] + row_nums)
    col_nums = sorted([int(c) for c in df["Column"].unique() if not pd.isna(c)])
    column_w = col2.selectbox("Column", ["All"] + col_nums)
    subrow_w = col3.selectbox("Subrow", ["All"] + list(df["Subrow"].unique()))
    search_w = col1.text_input("Search")

    if search_w:
        df = filter_by_search(search_w)

    button_ph = st.empty()

    table = st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="multi-row",
    )
    print(st.session_state)

    def rows_to_carrito():
        global carrito_df
        rows = table.selection["rows"]
        carrito_df = pd.concat([carrito_df, df.iloc[rows]])
        carrito_df["orig_idx"] = carrito_df.index
        carrito_df.to_csv(carrito_name + ".csv", index=False)

    button_ph.button(
        "Añadir seleccionados al carrito",
        on_click=rows_to_carrito,
        disabled=not table.selection["rows"],
    )

with carrito_tab:

    def empty_carrito():
        global carrito_df
        carrito_df = blank_carrito_df(df)
        carrito_df.to_csv(carrito_name + ".csv", index=False)

    rm_button_ph = st.empty()
    rm_all_button = st.button(
        "Vaciar carrito",
        on_click=empty_carrito
    )

    carrito_table = st.dataframe(
        carrito_df,
        use_container_width=True,
        hide_index=True
    )

    out_lines = []
    for i, (_, row) in enumerate(carrito_df.iterrows()):
        line = f"{i+1}. {row['Titulo']}"
        if row['Autor'] and row['Autor'] != '-':
            line += f" -- {row['Autor']}"
        if not pd.isna(row["Año"]):
            line += f" ({row['Año']})"
        out_lines.append(line)

    st.write("\n".join(out_lines))

