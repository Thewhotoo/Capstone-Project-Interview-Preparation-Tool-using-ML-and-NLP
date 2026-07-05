import pandas as pd
import random

data = []

# Generate 500 rows of synthetic training data
for _ in range(500):
    # Randomly simulate SBERT similarity (0.0 to 1.0)
    sbert_sim = random.uniform(0.1, 1.0)
    
    # Simulate Word Count and Grammar
    word_count = random.randint(2, 40)
    grammar_valid = 1 if word_count > 4 else 0
    
    # Simulate NLI scores based on SBERT to keep it somewhat realistic
    if sbert_sim > 0.8:
        nli_entail = random.uniform(0.6, 0.99)
        nli_contra = random.uniform(0.01, 0.2)
    elif sbert_sim < 0.4:
        nli_entail = random.uniform(0.01, 0.3)
        nli_contra = random.uniform(0.4, 0.9)
    else:
        nli_entail = random.uniform(0.2, 0.7)
        nli_contra = random.uniform(0.1, 0.8)
        
    # --- The "Human" Grading Logic (Target Score) ---
    if word_count < 5 or grammar_valid == 0:
        human_score = random.uniform(0.0, 0.2)
    elif nli_contra > 0.6: # High contradiction = immediate fail
        human_score = random.uniform(0.1, 0.3)
    elif sbert_sim > 0.9 and nli_entail > 0.8: # Perfect answer
        human_score = random.uniform(0.9, 1.0)
    else:
        # Blended score for average answers
        human_score = (sbert_sim * 0.6) + (nli_entail * 0.4)
        
    # Ensure score stays between 0 and 1
    human_score = max(0.0, min(1.0, human_score))
    
    data.append([sbert_sim, nli_contra, nli_entail, word_count, grammar_valid, round(human_score, 3)])

# Save to CSV
df = pd.DataFrame(data, columns=['SBERT_Sim', 'NLI_Contradiction', 'NLI_Entailment', 'Word_Count', 'Grammar_Valid', 'Human_Score'])
df.to_csv("meta_training_data.csv", index=False)
print("✅ Generated meta_training_data.csv with 500 examples!")