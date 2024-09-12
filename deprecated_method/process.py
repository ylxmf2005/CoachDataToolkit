import os
from langchain_core.prompts import PromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import time
import re

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
            template1 = f.read()
            
        # with open('./template2.txt', 'r') as f:
        #     template2 = f.read()
            
        self.chat_prompt1 = PromptTemplate.from_template(template1)
        # self.chat_prompt2 = PromptTemplate.from_template(template2)
        # system_prompt = SystemMessagePromptTemplate.from_template((template1)) # Nested brackets is required
        # human_prompt = HumanMessagePromptTemplate.from_template(("self.raw_transcription: {self.raw_transcription}"))
        # self.chat_prompt1 = ChatPromptTemplate.from_messages([
        #     system_prompt,
        #     human_prompt
        # ]) 
        # For deeepseek prompt caching
        
        
        
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
        # self.pipe = self.chat_prompt1 | self.llm | self.output_parser | self.chat_prompt2 | self.llm | self.output_parser
        
        self.pipe = self.chat_prompt1 | self.llm | self.output_parser

    def process_transcript(self, file_name, flag = False):
        if flag == False:
            self.start_time = time.time()
            print(f"Processing {file_name}...")
        
        input_path = os.path.join(self.input_folder, file_name)
        self.read_transcript(input_path)
        
        retry_count = 0
        success = False
        response = None
        
        while retry_count < self.retry_limit and not success:
            try:
                response = self.pipe.invoke({"raw_transcription": self.raw_transcription})                
                
                success = True
            except Exception as e:
                retry_count += 1
                print(f"Error processing file {file_name}: {str(e)}. Retry {retry_count}")
                time.sleep(1)  
        
        if response == None:
            opt = input(f"Failed to process file {file_name}. Still retry?(Y/N)\n")
            if opt == "Y":
                self.process_transcript(file_name, flag = True)
            else:
                print(f"Skipping file {file_name}.")
        
        else:    
            response = response.replace("```", "")
            if response is not None:
                self.save_output(file_name, response)
            end_time = time.time()
            print(f"Time taken: {end_time - self.start_time} seconds.")

    def read_transcript(self, input_path):
        self.raw_transcription = ""
        cnt = 1
        with open(input_path, "r") as f:
            text = f.readlines()
            for index in range(2, len(text), 4):
                item = text[index]
                self.raw_transcription += f"{cnt}. " + item
                cnt += 1
                if not item.endswith("\n"):
                    self.raw_transcription += "\n"
                        
    def replace_speaker(self, text, label):
        text = re.sub(r"\](.*)", f"] {label}", text)
    
    def save_output(self, file_name, response):
        log_path = os.path.join(self.log_folder, file_name.replace(".srt", ".log"))
        
        with open(log_path, "w") as f:
            f.write(response)
        
        response = response.split('\n')
        cnt = 0
        file_path = os.path.join(self.output_folder, file_name.replace(".srt", f".txt_{cnt}"))
        
        lines = self.raw_transcription.split("\n")
        
        replacements = {
            "start_coaching_with_coach_to_coachee": "Coach",
            "end_coaching_with_coach_to_coachee": "Coach",
            "coach_to_coachee": "Coach",
            "start_coaching_with_coachee_to_coach": "Coachee",
            "end_coaching_with_coachee_to_coach": "Coachee",
            "coachee_to_coach": "Coachee"
        }
        
        for i, item in enumerate(response):
            if "before" in item or "after" in item:
                continue
            
            if "start_coaching" in item:
                file_path = os.path.join(self.output_folder, file_name.replace(".srt", f".txt_{cnt}")) 
                cnt += 1
                # clear
                with open(file_path, "w") as f:
                    pass
            
                for old, new in replacements.items():
                    item = item.replace(old, new)
            
            item = item.replace("marker", "Marker")
            
            with open(file_path, "a") as f:
                # line = self.replace_speaker(lines[i], item) + "\n"
                line = item + "\n"
                f.write(line)
        
        # output_list = response.split("###")
        # for i, item in enumerate(output_list):
        #     if len(output_list) > 1:
        #         output_path = os.path.join(self.output_folder, file_name.replace(".srt", f"_{i}.txt"))
        #     else:
        #         output_path = os.path.join(self.output_folder, file_name.replace(".srt", ".txt"))
        #     with open(output_path, "w") as f:
        #         if item.startswith("\n"):
        #             f.write(item[1:])
        #         else:
        #             f.write(item)
                
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
        input_folder = "./outputs/0",
        output_folder = "./outputs",
        log_folder = "./logs",
        
        # api_base_url = "https://api.moonshot.cn/v1/",
        
        api_base_url = "https://api-sg.moonshot.ai/v1", # Out of China mainland 
        api_key = os.getenv("MOONSHOT_API_KEY"),
        model_name = "moonshot-v1-128k",
        max_tokens = 16384,
    
        # api_base_url = "https://api.deepseek.com",
        # api_base_url="https://api.deepseek.com/beta",
        # api_key = os.getenv("DEEPSEEK_API_KEY"),
        # model_name = "deepseek-chat",
        # max_tokens = 4096,
        
        # api_base_url = None,
        # model_name = "gpt-4o-2024-08-06",
        # api_key = os.getenv("OPENAI_API_KEY"),
        # max_tokens = 4096,
    )
    
    # processor.process_all_transcripts()
    
    # For single file processing
    # processor.process_transcript("5daydUwrsSo.srt")
    processor.process_transcript("7qVNnXiSwks.srt")
    # processor.process_transcript("rUTAh4gFGaQ.srt")