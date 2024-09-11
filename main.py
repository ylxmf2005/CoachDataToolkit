import os
from langchain_core.prompts import PromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
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

        self.setup_prompt_template()
        self.setup_pipe()

    def setup_prompt_template(self):
        with open('./template.txt', 'r') as f:
            template = f.read()
            
        self.prompt = PromptTemplate.from_template(template)
    
        
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
            
        self.output_parser = StrOutputParser()
        self.pipe = self.prompt | self.llm | self.output_parser
        
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

    def process_transcript(self, file_name):
        # print(f"Processing {file_name}...")
        self.log_path = os.path.join(self.log_folder, file_name.replace(".srt", ".log"))
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        
        if logger.hasHandlers():
            logger.handlers.clear()
        
        file_handler = logging.FileHandler(self.log_path, mode='w')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        logger.addHandler(file_handler)
        
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        logger.addHandler(stream_handler)
        
        logger.info(f"Processing {file_name}...")
        
        input_path = os.path.join(self.input_folder, file_name)
        self.read_transcript(input_path)
        response = self.pipe.invoke({"raw_transcription": self.raw_transcription})
        self.save_output(file_name, response)
        
        logger.info(f"Finished processing {file_name}.")
         
    def replace_speaker(self, session_content, speaker_map, i):
        add1 = False
        if "Session 0" not in speaker_map:
            add1 = True
        speaker_map = {key: value[f"Session {i + add1}"] for key, value in speaker_map.items() if "Session" not in key}
            
        try:
            for index in range(len(session_content)):
                for key, value in speaker_map.items():
                    session_content[index] = session_content[index].replace(key, value)
                    
            # Fiter uninvolved and unknown speaker and ask for human help
            # session_content = [item for item in session_content if "Uninvolved" not in item]
            session_content_copy = session_content.copy()
            session_content = []
            
            for item in session_content_copy:
                if "Uninvolved" not in item and "[SPEAKER_" not in item:
                    session_content.append(item)
                elif "Uninvolved" in item:
                    message = f"Uninvolved speaker detected: {item}"
                    logging.warning(message)
                else:
                    message = f"Unknown speaker detected: {item}"
                    logging.warning(message)
                    
            
        except Exception as e:
            print(f"Error replacing speaker: {e}")
        
        return session_content
    
    def save_output(self, file_name, response):
        response_path = os.path.join(self.log_folder, file_name.replace(".srt", "_response.txt"))
        
        with open(response_path, "w") as f:
            f.write(response)
        
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
            
            # Replace speaker
            session_content = self.replace_speaker(session_content, dict, i)
            
            # Extend the session content, need human removal here.
            next_start = len(transcription_lines)
            if i < len(session_keys) - 1:
                next_start = dict[session_keys[i + 1]][0]
            
            sub_transcription = transcription_lines[end:next_start]
            sub_transcription = self.replace_speaker(sub_transcription, dict, i)
            
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
            
                        
            # Revert and Save the session content
            output_path = os.path.join(self.output_folder, file_name.replace(".srt", f"_({i + 1}).txt"))
                        
            with open(output_path, "w") as f:
                for item in session_content:
                    match = re.match(r'^\d+\.\s', item)
                    if match:
                        content_without_number = item[match.end():]
                    else:
                        content_without_number = item
                    
                    index = int(item.split(". ")[0])
                    f.write(self.text[4 * index])
                    f.write(self.text[4 * index + 1])
                    f.write(content_without_number)
                    f.write("\n\n")
                

    def process_all_transcripts(self):
        files = os.listdir(self.input_folder)
        for file_name in files:
            # print(f"Processing {file_name}...")
            if file_name.endswith(".srt"):
                self.process_transcript(file_name)
                    
            # time.sleep(1)

if __name__ == "__main__":
    load_dotenv()
    processor = TranscriptProcessor(
        input_folder = "./transcripts",
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
        # model_name = "gpt-4o-2024-08-06",
        # api_key = os.getenv("OPENAI_API_KEY"),
        # max_tokens = 2048,
    )
    
    processor.process_all_transcripts()
    
    # For single file processing
    # processor.process_transcript("5daydUwrsSo.srt")
    # processor.process_transcript("7qVNnXiSwks.srt")
    # processor.process_transcript("rUTAh4gFGaQ.srt")