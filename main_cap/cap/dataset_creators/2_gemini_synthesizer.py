from google import genai
from google.genai import types
from pydantic import BaseModel
import json
import time
import os

# 1. Force strict JSON structure
class Triplet(BaseModel):
    anchor: str
    positive: str
    negative: str

class TripletList(BaseModel):
    triplets: list[Triplet]

# --- MUST BE A KEY FROM A BRAND NEW GMAIL ACCOUNT ---
client = genai.Client(api_key="AIzaSyAf3s7bhO4XGdznVry4ucNX-alyu1OtBgY")

# 2. Load the raw Tavily data
with open("tavily_raw_context.json", "r") as f:
    raw_data = json.load(f)

# 3. Auto-Resume logic: Load existing progress so we never lose data!
training_triplets = []
if os.path.exists("sbert_training_data.json"):
    with open("sbert_training_data.json", "r") as f:
        try:
            training_triplets = json.load(f)
            print(f"🔄 Resuming with {len(training_triplets)} existing triplets...")
        except:
            pass

print("🚀 Synthesizing Triplets... ⏳")

# Calculate where to start based on what's already saved
start_index = len(training_triplets) // 3

for index in range(start_index, len(raw_data)):
    item = raw_data[index]
    
    # TRUNCATION FIX: Slice to 8,000 characters to absolutely guarantee we stay under token limits
    safe_text = str(item.get('raw_content', ''))[:8000]
    
    prompt = f"""
    Extract 3 technical interview concepts from this text: {safe_text}
    
    For each concept, generate:
    1. 'anchor': The perfect, textbook reference answer.
    2. 'positive': A technically correct answer written in casual, spoken English.
    3. 'negative': A completely wrong answer that maliciously uses the exact same technical keywords.
    """
    
    max_retries = 3
    success = False
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=TripletList,
                    temperature=0.2 
                )
            )
            
            generated_data = json.loads(response.text)
            
            for t in generated_data['triplets']:
                training_triplets.append({
                    "anchor": t['anchor'],
                    "positive": t['positive'],
                    "negative": t['negative']
                })
                
            print(f"✅ Chunk {index + 1}/{len(raw_data)}: Synthesized {len(generated_data['triplets'])} triplets...")
            
            # INCREMENTAL SAVE FIX: Save to disk immediately so you never lose progress
            with open("sbert_training_data.json", "w") as f:
                json.dump(training_triplets, f, indent=4)
                
            success = True
            time.sleep(5) # Safe RPM sleep
            break # Break out of the retry loop on success
            
        except Exception as e:
            error_msg = str(e)
            
            # RAW ERROR EXPOSURE: Print exactly why it failed
            print(f"\n⚠️ RAW ERROR ON CHUNK {index + 1}: {error_msg}\n")
            
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower():
                print(f"🛑 Rate/Quota limit! Sleeping 60s... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(60)
            else:
                print(f"⏭️ Skipping chunk {index + 1} due to unfixable parsing/API error.")
                break
    
    if not success and attempt == max_retries - 1:
        print(f"❌ Failed chunk {index + 1} after 3 retries. Moving to next chunk.")

print(f"🎉 Synthesis complete! Total triplets saved to disk: {len(training_triplets)}")