import os
from langchain_core.prompts import PromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import time
import re
import json

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
            text = f.readlines()
            for index in range(2, len(text), 4):
                item = text[index]
                cnt += 1
                self.raw_transcription += f"{cnt}. " + item
                if not item.endswith("\n"):
                    self.raw_transcription += "\n"

    def process_transcript(self, file_name):
        input_path = os.path.join(self.input_folder, file_name)
        self.read_transcript(input_path)
        
        response = self.pipe.invoke({"raw_transcription": self.raw_transcription})
        
        self.save_output(file_name, response)
                        
    def replace_speaker(self, text, speaker_map):
        try:
            for key, value in speaker_map.items():
                if "Session" in key:
                    continue
                if isinstance(value, list):
                    if (len(value) == 1): value = value[0]
                    else: value = (value[0] + " and " + value[1])
                text = text.replace(key, value)
        except Exception as e:
            print(f"Error replacing speaker: {e}")
            
        return text
    
    def save_output(self, file_name, response):
        log_path = os.path.join(self.log_folder, file_name.replace(".srt", ".txt"))
        with open(log_path, "w") as f:
            f.write(response)
        
        try:
            json_str = response[response.index("{"):response.rindex("}")+1]
            dict = json.loads(json_str)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"Error extracting JSON: {e}")
            return
        
        self.raw_transcription = self.replace_speaker(self.raw_transcription, dict)
        transcription_lines = self.raw_transcription.split("\n")

        session_keys = [key for key in dict.keys() if key.startswith("Session")]
        
        for i, session_key in enumerate(session_keys):
            session_range = dict[session_key]
            start, end = session_range[0], session_range[1]

            session_content = transcription_lines[start-1:end]

            output_path = os.path.join(self.output_folder, file_name.replace(".srt", f"_{i}.txt"))
            
            with open(output_path, "w") as f:
                f.write("\n".join(session_content))
                
            # print(f"Session {i} saved to {output_path}")

    def process_all_transcripts(self):
        files = os.listdir(self.input_folder)
        for file_name in files:
            if file_name.endswith(".srt"):
                flag = self.process_transcript(file_name)
                if flag:
                    print(f"Finished processing {file_name}.", end=" ")
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
        max_tokens = 2048,
        
        # api_base_url = None,
        # model_name = "gpt-4o-2024-08-06",
        # api_key = os.getenv("OPENAI_API_KEY"),
        # max_tokens = 2048,
    )
    
    # processor.process_all_transcripts()
    
    # For single file processing
    processor.process_transcript("5daydUwrsSo.srt")
    # processor.process_transcript("7qVNnXiSwks.srt")
    # processor.process_transcript("rUTAh4gFGaQ.srt")