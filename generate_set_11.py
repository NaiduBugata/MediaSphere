import pandas as pd
import os

# Read all 1400 students
INPUT_FILE = r"C:\Users\aaksh\Downloads\Students list semwise.xlsx"
OUTPUT_FILE = r"C:\Users\aaksh\Downloads\Random_Students_1400.xlsx"
STUDENTS_PER_SET = 70

# Read and select 1400 students (same as main script)
dfs = []
for sheet in ["III-I", "IV-I", "II-II"]:
    df_raw = pd.read_excel(INPUT_FILE, sheet_name=sheet, header=None)
    header_row = None
    for idx, row in df_raw.iterrows():
        if "Sl.No" in row.values:
            header_row = idx
            break
    
    if header_row is None:
        continue
    
    df = pd.read_excel(INPUT_FILE, sheet_name=sheet, header=header_row)
    df.columns = df.columns.str.replace('\xa0', ' ').str.replace(r'\s+', ' ', regex=True).str.strip()
    df = df[["Registerno", "Name", "Branch", "Current year", "semester", "Section"]]
    dfs.append(df)

students = pd.concat(dfs, ignore_index=True)

# Select 1400 total students
selected = []
groups = students.groupby("Section")
section_data = {}

for sec, grp in groups:
    grp = grp.sample(frac=1, random_state=42)  # Fixed seed for reproducibility
    section_data[sec] = grp.reset_index(drop=True)

finished = False
i = 0
while len(selected) < 1400 and not finished:
    finished = True
    for sec in list(section_data.keys()):
        grp = section_data[sec]
        if i < len(grp):
            selected.append(grp.iloc[i])
            finished = False
            if len(selected) == 1400:
                break
    i += 1

all_students = pd.DataFrame(selected)
all_students = all_students.sample(frac=1, random_state=42).reset_index(drop=True)

# Generate Set 11
set_num = 11
start_idx = (set_num - 1) * STUDENTS_PER_SET
end_idx = start_idx + STUDENTS_PER_SET

result = all_students.iloc[start_idx:end_idx].copy()
result.insert(0, "SI No", range(1, len(result)+1))
result.rename(columns={
    "Registerno": "Register No",
    "Current year": "Current Year",
    "semester": "Semester"
}, inplace=True)

output_file = OUTPUT_FILE.replace(".xlsx", f"_Set_{set_num:02d}.xlsx")

if os.path.exists(output_file):
    try:
        os.remove(output_file)
    except:
        pass

result.to_excel(output_file, index=False)
print(f"Set {set_num}: Generated {len(result)} students -> {output_file}")
