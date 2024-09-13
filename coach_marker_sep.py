import os

import re

def process_lines(text_lines, output_file):
    valid_lines = []
    all_lines = text_lines[:]
    
    for i, line in enumerate(text_lines):
        if "Coach:" in line or "Coachee:" in line or "Marker:" in line:
            valid_lines.append((i, line))
            # i 是原文的行数

    coachee_lines = [(i, line) for i, line in valid_lines if 'Coachee:' in line]
    # 这里的 i 也是原来的行数
    
    # print(coachee_lines[:10])

    for i in range(len(coachee_lines) - 1):
        i_line = coachee_lines[i]
        j_line = coachee_lines[i + 1]
        # 得到的 i_line, j_line 实际上都是原文的行

        # print(f"i_line: {i_line}, j_line: {j_line}")

        coach_count = 0
        has_marker = False
        
        i_line_idx = valid_lines.index(i_line)
        j_line_idx = valid_lines.index(j_line)
        # 在 valid_lines 中的索引

        for k in range(i_line_idx + 1, j_line_idx):
            if 'Coach:' in valid_lines[k][1]:
                coach_count += 1
            if 'Marker:' in valid_lines[k][1]:
                has_marker = True

        if has_marker or coach_count >= 10:
            l = i_line_idx + 1
            while True:
                if "Marker:" in valid_lines[l][1]:
                    print("Marker Found")
                    break
                
                str = valid_lines[l][1].strip()
                user_input = input(f'From left, Marker (Coach)? (Y/N):\n"{str}"\n').strip().upper()
                if user_input == 'Y':
                    break
                l += 1
                if l >= len(valid_lines) or l == j_line_idx:
                    print("l >= len(valid_lines) or l == j_line")
                    break
            
            r = j_line_idx - 1
            
            # print(f"l: {l}, r: {r}")
            # # print l~r
            # for k in range(l, r + 1):
            #     print(valid_lines[k][1])
        
            while True:
                if "Marker:" in valid_lines[r][1]:
                    print("Marker Found")
                    break
                
                str = valid_lines[r][1].strip()
                user_input = input(f'From right, Marker (Coach)? (Y/N):\n"{str}"\n').strip().upper()
                if user_input == 'Y':
                    break
                r -= 1
                if r <= l:
                    print("r <= l")
                    break

            for k in range(l, r + 1):
                if 'Coach:' in valid_lines[k][1]:
                    valid_lines[k] = (valid_lines[k][0], valid_lines[k][1].replace('Coach:', 'Marker (Coach):'))
    
    with open(output_file, 'w', encoding='utf-8') as f_out:
        for i, line in enumerate(all_lines):
            if i in dict(valid_lines):
                f_out.write(dict(valid_lines)[i] + '\n')
            else:
                f_out.write(line)

files = os.listdir("./outputs")

selected_file_name = "DSgFH9QR1ek.txt"

for file_name in files:
    if selected_file_name and selected_file_name != file_name:
        continue
    
    op = input(f"Do you want to process {file_name}? (y/n) ")
    if op.lower() == "n":
        continue
    
    file_path = os.path.join("./outputs", file_name)
    
    with open(file_path, "r", encoding='utf-8') as f:
        lines = f.readlines()
    
    process_lines(lines, file_path.replace('.txt', '_processed.txt'))
        
# "Coach: Like, all right, we'll take it."
# nxEmzfH4SYY.txt
# 7JQ__QnrR6Q.txt