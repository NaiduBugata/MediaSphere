import pandas as pd
import random
import os
from pathlib import Path

# -----------------------------
# CONFIGURATION
# -----------------------------
INPUT_FILE = r"C:\Users\aaksh\Downloads\Students list semwise.xlsx"
OUTPUT_FILE = r"C:\Users\aaksh\Downloads\Random_Students_1400.xlsx"

# Total students required
TOTAL_REQUIRED = 1400

# Sheets to combine
SHEETS = ["III-I", "IV-I", "II-II"]

# -----------------------------
# READ DATA
# -----------------------------
dfs = []

for sheet in SHEETS:
    # Read the entire sheet without setting a header yet
    df_raw = pd.read_excel(INPUT_FILE, sheet_name=sheet, header=None)
    
    # Find the row containing "Sl.No" - this is our header row
    header_row = None
    for idx, row in df_raw.iterrows():
        if "Sl.No" in row.values:
            header_row = idx
            break
    
    if header_row is None:
        print(f"Warning: Could not find header row in sheet {sheet}")
        continue
    
    # Read the sheet again with the correct header row
    df = pd.read_excel(INPUT_FILE, sheet_name=sheet, header=header_row)

    # Standardize column names - remove extra spaces and non-breaking spaces
    df.columns = df.columns.str.replace('\xa0', ' ').str.replace(r'\s+', ' ', regex=True).str.strip()

    # Keep only required columns
    df = df[[
        "Registerno",
        "Name",
        "Branch",
        "Current year",
        "semester",
        "Section"
    ]]

    dfs.append(df)

# Merge all students
students = pd.concat(dfs, ignore_index=True)

# Number of output sets
NUM_SETS = 20
STUDENTS_PER_SET = TOTAL_REQUIRED // NUM_SETS

# Select 1400 total students first (balanced across sections)
print(f"Selecting {TOTAL_REQUIRED} total students...")

selected = []

# Group by section
groups = students.groupby("Section")

# Shuffle every section independently
section_data = {}

for sec, grp in groups:
    grp = grp.sample(frac=1, random_state=random.randint(1,100000))
    section_data[sec] = grp.reset_index(drop=True)

# Round Robin Picking to select 1400 students
finished = False
i = 0

while len(selected) < TOTAL_REQUIRED and not finished:

    finished = True

    for sec in list(section_data.keys()):

        grp = section_data[sec]

        if i < len(grp):
            selected.append(grp.iloc[i])
            finished = False

            if len(selected) == TOTAL_REQUIRED:
                break

    i += 1

# Convert to DataFrame and shuffle
all_students = pd.DataFrame(selected)
all_students = all_students.sample(frac=1, random_state=random.randint(1,100000)).reset_index(drop=True)

print(f"Total students selected: {len(all_students)}")

# Split into 20 sets
for set_num in range(1, NUM_SETS + 1):
    start_idx = (set_num - 1) * STUDENTS_PER_SET
    end_idx = start_idx + STUDENTS_PER_SET
    
    result = all_students.iloc[start_idx:end_idx].copy()

    # Add Serial Number
    result.insert(0, "SI No", range(1, len(result)+1))

    # Rename columns
    result.rename(columns={
        "Registerno": "Register No",
        "Current year": "Current Year",
        "semester": "Semester"
    }, inplace=True)

    # Create output filename for this set
    output_file = OUTPUT_FILE.replace(".xlsx", f"_Set_{set_num:02d}.xlsx")
    
    # Remove existing file if it exists
    if os.path.exists(output_file):
        try:
            os.remove(output_file)
        except Exception as e:
            print(f"Warning: Could not delete {output_file}: {e}")
    
    # Save with error handling
    try:
        result.to_excel(output_file, index=False)
        print(f"Set {set_num}: Generated {len(result)} students -> {output_file}")
    except PermissionError:
        print(f"Error: File {output_file} is locked (possibly open in Excel). Skipping this set.")
        print(f"Please close any open Excel files and run the script again.")
        continue
    except Exception as e:
        print(f"Error writing {output_file}: {e}")
        continue

print(f"\nDone!")
print(f"Total students: {TOTAL_REQUIRED}")
print(f"Number of sets: {NUM_SETS}")
print(f"Students per set: {STUDENTS_PER_SET}")