"""
LLM Generation Module - Generates interview questions from context
"""
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

# Load FLAN-T5 model once
print("⏳ Loading FLAN-T5 model...")
tokenizer = AutoTokenizer.from_pretrained("google/flan-t5-small")
model = AutoModelForSeq2SeqLM.from_pretrained("google/flan-t5-small")
print("✅ Model loaded!")


def generate_interview_question(context, concept=None):
    """
    Generate a technical interview question from given context
    
    Args:
        context: The source material/context
        concept: Optional specific concept to focus on
    
    Returns:
        str: Generated interview question
    """
    if not context or len(context.strip()) < 30:
        return "Unable to generate question - insufficient context"
    
    # Clean context to avoid poor quality
    context_clean = context[:400].replace("\n", " ").strip()
    
    # Build prompt for question generation
    if concept:
        prompt = f"""Based on this material, create a clear technical interview question about '{concept}'.

Material: {context_clean}

Create ONE question that:
1. Tests understanding, not memorization
2. Is specific and answerable
3. Uses 'Explain', 'Describe', 'What', or 'How'
4. Does NOT ask to generate or create
5. Is 10-20 words

Question:"""
    else:
        prompt = f"""Based on this material, create a clear technical interview question.

Material: {context_clean}

Create ONE question that:
1. Tests understanding, not memorization
2. Is specific and answerable
3. Uses 'Explain', 'Describe', 'What', or 'How'
4. Does NOT ask to generate or create
5. Is 10-20 words

Question:"""

    try:
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        
        outputs = model.generate(
            **inputs,
            max_length=60,
            min_length=8,
            do_sample=False,
            temperature=0.2,
            top_p=0.9,
            repetition_penalty=2.0  # Prevent repetition
        )
        
        question = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
        
        # Remove common junk patterns
        question = question.replace("based on this context", "")
        question = question.replace("based on the context", "")
        question = question.replace("material:", "").strip()
        
        # Quality checks
        if (len(question.split()) < 5 or 
            "generate" in question.lower() or 
            "create" in question.lower() or
            "context" in question.lower() or
            "material" in question.lower() or
            "?" not in question):
            
            # Fallback: Extract key terms from context
            words = [w for w in context_clean.split() if len(w) > 4][:3]
            if words:
                topic = ' '.join(words)
                return f"Explain how {topic} works and why it is important in computer networks."
            else:
                return "What are the key characteristics of this concept and how is it applied?"
        
        # Ensure question ends with ?
        if not question.endswith("?"):
            question = question.rstrip(".") + "?"
        
        return question
    
    except Exception as e:
        print(f"❌ Error generating question: {e}")
        return "Unable to generate question at this time."


def generate_reference_answer(context):
    """
    Extract or summarize a reference answer from context
    
    Args:
        context: The source material
    
    Returns:
        str: Reference answer/explanation
    """
    if not context or len(context.strip()) < 30:
        return "No reference available"
    
    # For PDFs, we return a summarized portion of the context
    sentences = context.split('.')
    reference = '. '.join(sentences[:3]) + '.'  # First 3 sentences
    
    return reference[:300] + "..." if len(reference) > 300 else reference


def generate_explanation(context, topic):
    """
    Generate an explanation for a specific topic
    
    Args:
        context: The source material
        topic: The topic to explain
    
    Returns:
        str: Generated explanation
    """
    if not context or len(context.strip()) < 30:
        return "Insufficient context to generate explanation."
    
    context_clean = context[:300].replace("\n", " ").strip()
    
    prompt = f"""Explain '{topic}' clearly and concisely.

Source material: {context_clean}

Provide a 2-3 sentence explanation that:
1. Defines the concept
2. Explains its purpose or function
3. Gives a practical example

Explanation:"""

    try:
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=400)
        
        outputs = model.generate(
            **inputs,
            max_length=100,
            min_length=15,
            do_sample=False,
            temperature=0.2,
            repetition_penalty=2.5,  # Strong penalty for repetition
            top_p=0.9
        )
        
        explanation = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
        
        # Remove junk
        explanation = explanation.replace("source material:", "").replace("material:", "").strip()
        
        # Detect and fix repetition (if same word appears 3+ times in short text)
        words = explanation.split()
        word_counts = {}
        for w in words:
            word_counts[w] = word_counts.get(w, 0) + 1
        
        # If repetition detected, return first 2-3 sentences
        if any(count >= 3 for count in word_counts.values() if len(words) > 0):
            sentences = explanation.split('.')
            return '. '.join(sentences[:2]).strip() + '.'
        
        return explanation if explanation else context_clean[:150] + "..."
    
    except Exception as e:
        print(f"⚠️  Error generating explanation, using source text")
        return context_clean[:150] + "..."
