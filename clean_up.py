import pandas as pd
import re


def load_original_csv(path="libros_ax.csv"):
    df = pd.read_csv(path)
    df.rename(columns={"Unnamed: 0": "Lugar"}, inplace=True)
    df.drop("Unnamed: 7", axis="columns", inplace=True)
    return df

def unroll_lugar(df):
    df = df.copy()
    current_lugar = None
    for i, row in df.iterrows():
        if pd.isna(row["Lugar"]):
            df.loc[i, "Lugar"] = current_lugar
        else:
            current_lugar = row["Lugar"]
    
    return df

loc_pat = re.compile(r"R(\d),? ?(C(\d))?,? ?([FBMab])?$")

def guardado_transform(string):
    if pd.isna(string):
        return {"Row": None, "Column": None, "Subrow": None}

    match = loc_pat.match(string)
    if match is None:
        print("Bad location string:", string)
        return {"Row": None, "Column": None, "Subrow": None}

    groups = match.groups()
    return {"Row": groups[0], "Column": groups[2], "Subrow": groups[3]}


def extract_location_fields(df):
    return df.join(pd.DataFrame(list(df["Guardado"].apply(guardado_transform))))


if __name__ == "__main__":
    df = load_original_csv()
    df = unroll_lugar(df)
    df = extract_location_fields(df)
    df.to_csv("libros_ax_clean.csv", index=False, encoding='utf-8-sig')
