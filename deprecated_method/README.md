## CoachDataToolkit
- Currently not use asynchronous methods.
- The model might merge consecutive speeches by the same speaker with similar themes into one paragraph. You can specify in the prompt to avoid merging speeches.

### Usage
- Prompt: ./template.txt
- Input: ./transcripts
- AI Result: ./output
- Human Result: ./human

Install requirements.txt, set the your API Key in .env file, and then run `python process.py`

Recommended model: 
- Moonshot-v1-128k (maximum 128*1024 output tokens, but have TPM).
- gpt-4o-2024-08-06 (maximum 16*1024 output tokens)

### Example 
- 5daydUwrsSo.srt (with marker and human comparison)
- rUTAh4gFGaQ.srt (with multiple sessions and human comparison)
- 7qVNnXiSwks.srt (with multiple sessions, marker and human comparison)