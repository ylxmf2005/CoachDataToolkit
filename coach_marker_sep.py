import re
import os

file_name = "0trESExbPq0.txt"
file_path = os.path.join("./outputs", file_name)

with open(file_path, "r") as f:
    lines = f.readlines()
        
with open(file_path, "w") as f:
    for i, line in enumerate(lines):
        if "[" in line and "]" in line:
            label = re.findall(r'\[.*?\]', line)[0].replace('[', '').replace(']', '')
            # print(label)
            if label:
                first_colon = line.find(':')
                last_bracket = line.rfind('[')
                content = line[first_colon + 2:last_bracket-1]
                line = f"{label}: {content}\n"
                line = line.replace("Marker (Third-party)", "Marker")
        f.write(line)
    
# Coachee: And those things have nothing to do with what I have, what's on my resume or what's on my Strava account or my Instagram, you know, like all of that. [Coachee]