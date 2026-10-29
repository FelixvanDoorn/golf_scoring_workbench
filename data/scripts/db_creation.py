import sqlite3

import pandas as pd

df_xlsx = pd.read_excel("../raw/score_analyse.xlsx", sheet_name=None)
df_scores = pd.concat([df_xlsx[year] for year in df_xlsx.keys() if "20" in year])
df_pars = df_xlsx["Course Pars"].drop(columns="Tee").drop_duplicates()
df_course = pd.DataFrame(df_pars["Course"])
df_course["num_holes"] = df_pars.notnull().sum(axis=1) - 1
df_course = df_course.reset_index(drop=True)
df_course = df_course.rename(columns={"Course": "course_name"})
df_tee = df_xlsx["Course Ratings"][["Course", "Tee"]]
df_stroke_indices_unmelted = df_xlsx.get("Stroke Indices")
conn = sqlite3.connect("../golf_workbench.db")
cursor = conn.cursor()

cursor.executescript(
    """
DROP TABLE IF EXISTS dim_course;
CREATE TABLE IF NOT EXISTS dim_course (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_name TEXT,
    num_holes INTEGER
);
DROP TABLE IF EXISTS dim_tee;
CREATE TABLE IF NOT EXISTS dim_tee (
    tee_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tee_name TEXT,
    course_id INTEGER,
    slope_rating INTEGER,
    course_rating DOUBLE
);
DROP TABLE IF EXISTS dim_hole;
CREATE TABLE IF NOT EXISTS dim_hole (
    hole_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER,
    hole_number INTEGER,
    tee_id INTEGER,
    par INTEGER,
    stroke_index INTEGER,
    hole_length DOUBLE,
    description TEXT
);
DROP TABLE IF EXISTS fact_score;
CREATE TABLE IF NOT EXISTS fact_score (
    score_id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER,
    hole_id INTEGER,
    total_score INTEGER,
    adjusted_score INTEGER
);

"""
)
df_course.to_sql("dim_course", conn, if_exists="append", index=False)
conn.commit()

df_course_id_mappings = pd.DataFrame(
    cursor.execute("SELECT DISTINCT course_name, course_id FROM dim_course").fetchall()
)

df_course_id_mappings_col_names = [description[0] for description in cursor.description]
df_course_id_mappings.columns = df_course_id_mappings_col_names

df_tee = df_tee.merge(df_course_id_mappings, how="inner", left_on="Course", right_on="course_name")

df_slope_course = df_xlsx["Course Ratings"]

df_tee_with_slope_and_course = df_tee.merge(
    df_slope_course,
    left_on=["course_name", "Tee"],
    right_on=["Course", "Tee"],
    how="inner",
)


df_tee_with_slope_and_course = df_tee_with_slope_and_course.drop(
    columns=["course_name", "Course_x", "Course_y", "Par"]
)

df_tee_with_slope_and_course.columns = [
    "tee_name",
    "course_id",
    "course_rating",
    "slope_rating",
]

df_tee_with_slope_and_course.to_sql("dim_tee", conn, if_exists="append", index=False)
conn.commit()

df_holes_unmelted = df_pars.copy()

df_holes_unmelted.columns = [col.replace("Par Hole", "") for col in df_holes_unmelted.columns]

df_holes = df_holes_unmelted.melt(
    id_vars=["Course"], var_name="hole_number", value_name="par"
).dropna()

df_holes = df_holes.merge(
    df_course_id_mappings, how="inner", left_on="Course", right_on="course_name"
)
df_holes = df_holes.drop(columns=["course_name", "Course"])

tee_ids = pd.DataFrame(
    cursor.execute("SELECT DISTINCT course_id, tee_id, tee_name AS Tee FROM dim_tee").fetchall()
)
tee_id_col_names = [description[0] for description in cursor.description]
tee_ids.columns = tee_id_col_names
df_holes = df_holes.merge(tee_ids, how="inner", on="course_id")
df_holes["hole_number"] = df_holes["hole_number"].astype(int)
df_holes["description"] = ""
df_hole_lengths_unmelted = df_xlsx["Hole Lengths"]

df_hole_lengths_unmelted.columns = [
    col.replace("Hole ", "") for col in df_hole_lengths_unmelted.columns
]

df_hole_lengths = df_hole_lengths_unmelted.melt(
    id_vars=["Course", "Tee"], var_name="hole_number", value_name="hole_length"
).dropna()

df_hole_lengths["hole_number"] = df_hole_lengths["hole_number"].astype(int)


df_hole_lengths = df_hole_lengths.merge(
    df_course_id_mappings, how="left", left_on="Course", right_on="course_name"
)


df_hole_lengths = df_hole_lengths.merge(tee_ids, how="left", on=["course_id", "Tee"])

df_hole_lengths = df_hole_lengths.drop(columns=["Course", "course_name", "Tee"])


df_stroke_indices_unmelted.columns = [
    col.replace("Hole ", "") for col in df_stroke_indices_unmelted.columns
]

df_stroke_indices = df_stroke_indices_unmelted.melt(
    id_vars=["Course", "Tee"], var_name="hole_number", value_name="stroke_index"
)

df_stroke_indices["hole_number"] = df_stroke_indices["hole_number"].astype(int)

df_stroke_indices = df_stroke_indices.merge(
    df_course_id_mappings, how="left", left_on="Course", right_on="course_name"
)

df_stroke_indices = df_stroke_indices.merge(tee_ids, on=["course_id", "Tee"])
df_stroke_indices = df_stroke_indices.drop(columns=["Course", "course_name", "Tee"])
df_stroke_indices = df_stroke_indices.drop_duplicates()

df_holes = df_holes.merge(
    df_hole_lengths, how="left", on=["course_id", "tee_id", "hole_number"]
).drop_duplicates()

df_holes = df_holes.merge(
    df_stroke_indices, how="left", on=["course_id", "tee_id", "hole_number"]
).drop_duplicates()

df_holes = df_holes[
    [
        "course_id",
        "hole_number",
        "tee_id",
        "par",
        "stroke_index",
        "hole_length",
        "description",
    ]
]

df_holes.to_sql("dim_hole", conn, if_exists="append", index=False)
conn.commit()
conn.close()
