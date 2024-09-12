import os
from langchain_core.prompts import PromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
from langchain.memory import ConversationBufferMemory
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import time
import re
import json
import logging

class TranscriptProcessor:
    def __init__(self, input_folder, output_folder, log_folder, api_base_url, api_key, model_name, max_tokens, retry_limit=3):
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.log_folder = log_folder
        self.api_base_url = api_base_url
        self.api_key = api_key
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.retry_limit = retry_limit
        
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)
            
        if not os.path.exists(self.log_folder):
            os.makedirs(self.log_folder)

        self.setup_prompt_template()
        self.setup_pipe()

    def setup_prompt_template(self):
        with open('./template.txt', 'r') as f:
            template = f.read()
        
        with open('./template2.txt', 'r') as f:
            template2 = f.read()
            
        with open('./template3.txt', 'r') as f:
            template3 = f.read()
            
        self.prompt = PromptTemplate.from_template(template)
        self.prompt2 = PromptTemplate.from_template(template2)
        self.prompt3 = PromptTemplate.from_template(template3)
        
    def setup_pipe(self):
        if (self.api_base_url):
            self.llm = ChatOpenAI(
                openai_api_base=self.api_base_url, 
                openai_api_key=self.api_key,
                model_name=self.model_name,
                max_tokens=self.max_tokens,
                streaming=True
            )
        else:
            self.llm = ChatOpenAI(
                openai_api_key=self.api_key,
                model_name=self.model_name,
                max_tokens=self.max_tokens,
                streaming=True
            )
            
        self.long_output_llm = ChatOpenAI(
            openai_api_base = "https://api-sg.moonshot.ai/v1", # Out of China mainland 
            openai_api_key = os.getenv("MOONSHOT_API_KEY"),
            model_name = "moonshot-v1-128k",
            max_tokens = 20288,
            streaming=True
        )
            
        self.output_parser = StrOutputParser()
        self.pipe = self.prompt | self.llm | self.output_parser
        self.pipe2 = self.prompt2 | self.llm | self.output_parser
        self.pipe3 = self.prompt3 | self.long_output_llm | self.output_parser
        
    def generate_long_output_with_memory(self):
        raise NotImplementedError("This method is not implemented yet.")
        
    def read_transcript(self, input_path):
        self.raw_transcription = ""
        cnt = 0
        with open(input_path, "r") as f:
            self.text = f.readlines()
            
            for index in range(2, len(self.text), 4):
                item = self.text[index]
                self.raw_transcription += f"{cnt}. " + item
                cnt += 1
                if not item.endswith("\n"):
                    self.raw_transcription += "\n"
                    
    def check_file_name_exist(self, file_name):
        """
        Check if the file_name exists in the output folder
        file_name can be with or without extension name (./srt, ./txt)
        """
        file_name = file_name.replace(".srt", "").replace(".txt", "")
        files = os.listdir(self.output_folder)
        for file in files:
            if file_name in file:
                return True
        return False

    
    def set_logger(self, file_name):
        # file_name is without extension name
        self.log_path = os.path.join(self.log_folder, file_name + ".log")
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.WARNING)
        
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
        
        file_handler = logging.FileHandler(self.log_path, mode='w')
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.logger.addHandler(file_handler)
        
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.WARNING)
        stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.logger.addHandler(stream_handler)
        
    def process_transcript(self, file_name):
        if self.check_file_name_exist(file_name):
            if self.predefined_input[3] is not None:
                opt = self.predefined_input[3]
            else:
                opt = input(f"\n{file_name} already exists, do you want to overwrite it? (Y/N)\n")
            if opt.lower() != "y":
                return
        
        self.logger.warning(f"Processing {file_name}...")
        
        response = self.pipe.invoke({"raw_transcription": self.raw_transcription, "context": self.context})
        self.postprocess_transcript(file_name, response)
        
        self.logger.warning(f"Finished processing {file_name} for pipeline1.")
         
    def replace_and_filter_speaker(self, session_content, speaker_map, i):
        add1 = False
        if "Session 0" not in speaker_map:
            add1 = True
        speaker_map = {key: value[f"Session {i + add1}"] for key, value in speaker_map.items() if "Session" not in key}
            
        try:
            for index in range(len(session_content)):
                for key, value in speaker_map.items():
                    session_content[index] = session_content[index].replace(key, value)
                    
            # Fiter uninvolved and unknown speaker
            session_content_copy = session_content.copy()
            session_content = []
            for item in session_content_copy:
                if "Uninvolved" not in item and "[SPEAKER_" not in item and "Others" not in item:
                    session_content.append(item)
                elif "Uninvolved" in item:
                    message = f"Uninvolved speaker detected: {item}"
                    logging.warning(message)
                elif "Others" in item:
                    message = f"Others speaker detected: {item}"
                    logging.warning(message)
                else:
                    message = f"Unknown speaker detected: {item}"
                    logging.warning(message)         
            
        except Exception as e:
            print(f"Error replacing speaker: {e}")
        
        return session_content
    
    
    def extend_to_include_marker(self, transcription_lines, session_content, dict, session_keys, end, i):
        next_start = len(transcription_lines)
        if i < len(session_keys) - 1:
            next_start = dict[session_keys[i + 1]][0]
            
        sub_transcription = transcription_lines[end:next_start]
        sub_transcription = self.replace_and_filter_speaker(sub_transcription, dict, i)
            
        last_marker_index = None
        for line in reversed(sub_transcription):
            if "Marker" in line:
                last_marker_index = sub_transcription.index(line)
                break
        if last_marker_index:
            last_coach_or_coachee_index = None
            if last_marker_index != len(sub_transcription) - 1:
                last_marker_index += 1 # To include coach/coachee after the last marker
                    
            for line in reversed(sub_transcription[:last_marker_index + 1]):
                if "Coach" in line or "Coachee" in line:
                    last_coach_or_coachee_index = sub_transcription.index(line)
                    print(line)
                    break
            if last_coach_or_coachee_index:
                session_content.extend(sub_transcription[:last_coach_or_coachee_index + 1])
            # else:
            #     session_content.extend(sub_transcription[:last_marker_index]) # No need to + 1
        
        return session_content
            
            
    def revert_and_save(self, session_content, file_name, i = None, only_one = None):
        if i:
            # file_name is with .srt extension name
            output_path = os.path.join(self.output_folder, file_name.replace(".srt", f"_({i}).txt"))
        
            if only_one:
                output_path = os.path.join(self.output_folder, file_name.replace(".srt", ".txt"))
        else:
            output_path = os.path.join(self.output_folder, file_name) # For further processing situation
                
        with open(output_path, "w") as f:
            for item in session_content:
                if "." not in item:
                    continue
                
                match = re.match(r'^\d+\.\s', item)
                if match:
                    content_without_number = item[match.end():]
                else:
                    content_without_number = item
                
                index = int(item.split(". ")[0])
                try:
                    f.write(self.text[4 * index])
                    f.write(self.text[4 * index + 1])
                    f.write(content_without_number)
                    f.write("\n\n")
                except IndexError as e:
                    print(f"Error writing to file: {e}")
                    print(f"Index: {index}")
                    print(f"Item: {item}")
    
    def postprocess_transcript(self, file_name, response):
        # file_name is with .srt extension name
        # response_path = os.path.join(self.log_folder, file_name.replace(".srt", "_response.txt"))
        # with open(response_path, "w") as f:
        #     f.write(response)
        
        self.logger.warning(f"Pipeline 1 response:\n{response}")
        
        try:
            json_str = response[response.index("{"):response.rindex("}")+1]
            dict = json.loads(json_str)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"Error extracting JSON: {e}")
            return
        
        transcription_lines = self.raw_transcription.split("\n")
        session_keys = [key for key in dict.keys() if key.startswith("Session")]
                
        # Process each session
        for i, session_key in enumerate(session_keys):
            session_range = dict[session_key]
            start, end = session_range[0], session_range[1] + 1
            session_content = transcription_lines[start:end]
            
            session_content = self.replace_and_filter_speaker(session_content, dict, i)
            
            # session_content = self.extend_to_include_marker(transcription_lines, session_content, dict, session_keys, end, i)
            
            self.revert_and_save(session_content, file_name, i + 1, len(session_keys) == 1)
                

    def further_process(self, futher_process_file_name):
        # futher_process_file_name is without extension name
        files = os.listdir(self.output_folder)
        for file_name in files: # File_name is with .txt extension namr
            if futher_process_file_name in file_name:
                file_path = os.path.join(self.output_folder, file_name)
                
                self.read_transcript(file_path)

                response = self.pipe3.invoke({"raw_transcription": self.raw_transcription})
                
                # with open("test.txt", "r") as f:   
                #     response = f.read()
                
                self.logger.warning(f"Further process response:\n{response}")
                print("repsone:", response)
                
                response_lines = response.split("\n")
                for i, line in enumerate(response_lines):
                    label = re.findall(r'\[.*?\]', line)
                    if label:
                        label = label[0].replace('[', '').replace(']', '')
                        
                        # Remove label like [Coachee]
                        line = re.sub(r'\[.*?\]', '', line)
                        # Use label to replace the original speaker
                        line = re.sub(r'\.(.*?)\:', f'. {label}:', line)
                        
                        line = line.replace("Marker (Third-party)", "Marker")
                        response_lines[i] = line
                                    
                # i = 1, only_one = True
                # match = re.search(r'_\((\d+)\)\.txt', file_name)
                # if match:
                #     only_one = False
                #     i = int(match.group(1))
                
                self.revert_and_save(response_lines, file_name)
        

    def process_all_transcripts(self):
        # files = os.listdir(self.input_folder)
        # for file_name in files:
        #     if file_name.endswith(".srt"):
        #         self.process_transcript(file_name)
        
        last_name = None
        begin_from = None
        
        self.predefined_input = ["Y", "John is the Coach, Raj Anderson is the Marker. There is only one coaching session. ", "Y" , "Y", "Y"]
        
        # self.predefined_input = [None, None, None, None, None]
        
        if last_name == None and begin_from == None:
            begin_from = input("Please input the file name to begin from: (Only press enter to start from the beginning)\n")
            
        if len(begin_from) == 0:
            begin_from = None
        
        flag = (last_name == None and begin_from == None)
        if last_name == None and begin_from:
            last_name = my_list[my_list.index(begin_from) - 1]
        
        for file_name in my_list:
            # file_name is without extension name
            if flag == False:
                if file_name == last_name:
                    flag = True
                continue
            
            # Step 0: Ask for context
            file_name_with_srt = file_name + ".srt"
            
            if self.predefined_input[0] is not None:
                str = self.predefined_input[0]
            else:
                str = input(f"\nDoes {file_name} have marker(s)? (skip/Y/N/Enter/context)\n")
            if str.lower() == "skip":
                continue
            elif str == "N":
                self.context = "No markers in the transcripts"
            elif str == "Y":
                self.context = "The transcripts have marker(s)"
            elif len(str) <= 1:
                self.context = ""
            else:
                self.context = str
                
                
            if self.predefined_input[1] is not None:
                str = self.predefined_input[1]
            else:
                str = input(f"Who are the speakers in {file_name}? (skip/Enter/context)\n")
            if str.lower() == "skip":
                continue
            elif str.isdigit():
                self.context = f"{str} coaching sessions in the transcripts"
            elif len(str) <= 1:
                self.context += ""
            else:
                self.context += str
            
            # Step 1: Initialize
            input_path = os.path.join(self.input_folder, file_name_with_srt)
            self.read_transcript(input_path)
            self.set_logger(file_name)
            
            # Step 2: Process the transcript
            self.process_transcript(file_name_with_srt)
            
            # Step 3: Pipeline 2
            if self.predefined_input[3] is not None:
                opt = self.predefined_input[3]
            else:
                opt = input(f"\nDo you want have pipeline 2? (Y/N)\n")
            if opt.lower() == "y":
                response = self.pipe2.invoke({"raw_transcription":self.raw_transcription})
                self.logger.warning(f"Pipeline 2 response:\n{response}")
            
            # Step 4: Further process if needed
            if self.predefined_input[4] is not None:
                opt = self.predefined_input[4]
            else:
                opt = input(f"\n{file_name_with_srt} finished. Do you need further process? (Y/N)\n")     
            if opt.lower() == "n" or opt == "":
                continue
            else:
                self.further_process(file_name)
                print(f"{file_name} further processed.")

if __name__ == "__main__":
    load_dotenv()
    
    my_list  = [
        "EbuP0obt_XI", "WyRM31mmjyQ", "RiOU_8UyaDU", "1BQJffFiCOo",     "OjKRSHIb7yk", 
        "Dx5jYRl0_wA", "WoP9LIHFK6k", "XvqOTUyv-wE", "P-Ysn2CCaqw",     "S2z_mvuEXPQ", 
        "ifIb00t2_Wk", "tQWRQwWybw0", "QgQvPII9BKg", "2C8aIPA82UY",     "k85pqOKawDE", 
        "VBFHUSnrru8", "_77BrZyFxuM", "0NE6s3jYbo4", "0trESExbPq0",     "4yBC6KnZ7bw", 
        "7JQ__QnrR6Q", "7o1HCAXUH2s", "8AgZ4o2rM88", "bbdaJPhIETo",     "DSgFH9QR1ek", 
        "gU_TIDlQfOU", "Hep5-CWN0RI", "hJqmCtP6IR0", "HjrmxRP46t0",     "JwMacxqpiPc", 
        "ksQ_PW6MA9k", "nxEmzfH4SYY", "qnfgViugVqA", "s8Qnz7PD3k4",     "SdCzvEJH0n8", 
        "t9UczuKe9EI", "vRUOXFspjgc", "WxjJTCG3Lws", "YM_2lA0RhBc",     "YyEFsOIej3k"
    ]
    
    processor = TranscriptProcessor(
        # input_folder = "./transcripts",
        input_folder = "./inputs",
        output_folder = "./outputs",
        log_folder = "./logs",
        
        # api_base_url = "https://api.moonshot.cn/v1/",
        
        # api_base_url = "https://api-sg.moonshot.ai/v1", # Out of China mainland 
        # api_key = os.getenv("MOONSHOT_API_KEY"),
        # model_name = "moonshot-v1-128k",
        # max_tokens = 2048,
    
        api_base_url = "https://api.deepseek.com",
        # api_base_url="https://api.deepseek.com/beta",
        api_key = os.getenv("DEEPSEEK_API_KEY"),
        model_name = "deepseek-chat",
        max_tokens = 4096,
        
        # api_base_url = None,
        # model_name = "gpt-4-turbo",
        # api_key = os.getenv("OPENAI_API_KEY"),
        # max_tokens = 4096,
    )
    
    processor.process_all_transcripts()
    
    # For single file processing
    # processor.process_transcript("5daydUwrsSo.srt")
    # processor.process_transcript("7qVNnXiSwks.srt")
    # processor.process_transcript("rUTAh4gFGaQ.srt")
    
# 