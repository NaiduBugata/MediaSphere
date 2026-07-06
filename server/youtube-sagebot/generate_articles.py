import json
import time
import re
from groq import Groq
class ArticleGenerator:
    def __init__(self, api_key, model="llama-3.3-70b-versatile"):
        self.client = Groq(api_key=api_key)
        self.model = model
        self.cache_file = 'data/article_cache.json'
        self.load_cache()
    
    def load_cache(self):
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                self.cache = json.load(f)
        except:
            self.cache = {}
    
    def save_cache(self):
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)
    
    def remove_tv_phrases(self, text):
        """Remove TV news anchor phrases from generated text"""
        tv_phrases = [
            # Remove these patterns
            r'మా\s*ప్రతినిధి',
            r'మరిన్ని\s*వివరాలు',
            r'ఇదే\s*అంశానికి\s*సంబంధించి',
            r'కరస్పాండెంట్',
            r'రిపోర్టర్',
            r'చూడండి',
            r'వినండి',
            r'తెలుసుకుందాం',
            r'వివరాల్లోకి\s*వెళితే',
            r'ఇప్పుడు\s*చూద్దాం',
            r'వివరాలు\s*తెలుసుకుందాం',
            r'పూర్తి\s*వివరాలు',
            r'లైవ్',
            r'బ్రేకింగ్\s*న్యూస్',
            r'^[^.]*?\s*రిపోర్ట్\s*చేస్తున్నారు',
        ]
        
        for pattern in tv_phrases:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def generate_article(self, story, max_retries=3):
        """Generate newspaper-style article from a story"""
        story_id = story['story_id']
        
        # Check cache first
        if story_id in self.cache:
            return self.cache[story_id]
        
        # Prepare the prompt
        prompt = self.create_newspaper_prompt(story)
        
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": """You are a professional Telugu newspaper journalist. 
                            Your task is to write news articles in pure newspaper style.
                            
                            CRITICAL RULES:
                            1. NEVER use TV anchor language (మా ప్రతినిధి, మరిన్ని వివరాలు, etc.)
                            2. Write in third-person newspaper style only
                            3. Start with the most important facts
                            4. Use objective, factual language
                            5. No dramatic or sensational language
                            6. No direct address to readers/viewers
                            7. No promotional language
                            8. Keep it concise and professional
                            
                            NEWSPAPER STYLE EXAMPLES:
                            ✓ "తుళ్లూరు మండలంలో సోమవారం కురిసిన భారీ వర్షంతో..."
                            ✗ "మా ప్రతినిధి తుళ్లూరు నుండి..."
                            ✗ "చూడండి ఎలా మారిందో పరిస్థితి..." """
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.3,  # Lower temperature for more consistent output
                    max_tokens=2000,
                    top_p=0.9
                )
                
                # Extract and clean the generated article
                raw_article = response.choices[0].message.content
                cleaned_article = self.post_process_article(raw_article)
                
                # Cache the result
                self.cache[story_id] = cleaned_article
                self.save_cache()
                
                return cleaned_article
                
            except Exception as e:
                if '429' in str(e) and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 30  # Exponential backoff
                    time.sleep(wait_time)
                    continue
                raise
    
    def create_newspaper_prompt(self, story):
        """Create a prompt for newspaper-style article generation"""
        prompt = f"""SOURCE TRANSCRIPT (Multiple sources combined):
{story['clean_text'][:3000]}

STORY DETAILS:
- Sources: {', '.join(story['sources'])}
- Number of channels reporting: {story['source_count']}
- Location context: This is from Palnadu district area

TASK:
Write a professional Telugu newspaper article based on the above information.

REQUIREMENTS:
1. Write ONLY in Telugu
2. Use newspaper style (పత్రికా శైలి)
3. Start with the most important fact (dateline-style)
4. Include relevant details from all sources
5. Maintain factual accuracy
6. NO TV anchor language
7. NO మా ప్రతినిధి, మరిన్ని వివరాలు, etc.
8. Write 3-4 paragraphs maximum

OUTPUT FORMAT (JSON):
{{
    "title": "Newspaper-style headline in Telugu",
    "content": "Complete newspaper article in Telugu",
    "summary": "One-line summary in Telugu"
}}

EXAMPLE OUTPUT:
{{
    "title": "తుళ్లూరులో భారీ వర్షం.. జలమయమైన రహదారులు",
    "content": "తుళ్లూరు మండలంలో సోమవారం సాయంత్రం కురిసిన భారీ వర్షం కారణంగా రహదారులు, డ్రైనేజీలు నీటితో నిండిపోయాయి.\\n\\nగుంటూరు-తుళ్లూరు ప్రధాన రోడ్డుపై నీరు నిలిచిపోవడంతో వాహనాల రాకపోకలకు అంతరాయం ఏర్పడింది.\\n\\nపలు గ్రామాల్లో కాలువలు పొంగిపొర్లి రోడ్లపైకి నీరు చేరడంతో ప్రజలు ఇబ్బందులు పడ్డారు.",
    "summary": "తుళ్లూరు మండలంలో భారీ వర్షం కారణంగా రహదారులు జలమయమయ్యాయి."
}}"""
        
        return prompt
    
    def post_process_article(self, raw_article):
        """Clean and validate the generated article"""
        try:
            # Try to parse JSON response
            if isinstance(raw_article, str):
                # Sometimes the model wraps JSON in code blocks
                raw_article = raw_article.replace('```json', '').replace('```', '')
                article_dict = json.loads(raw_article)
            else:
                article_dict = raw_article
            
            # Clean each field
            title = self.remove_tv_phrases(article_dict.get('title', ''))
            content = self.remove_tv_phrases(article_dict.get('content', ''))
            summary = self.remove_tv_phrases(article_dict.get('summary', ''))
            
            # Validate content quality
            if any(phrase in content for phrase in [
                'మా ప్రతినిధి', 'మరిన్ని వివరాలు', 'కరస్పాండెంట్'
            ]):
                # Additional cleaning if TV phrases found
                content = self.deep_clean(content)
            
            return {
                'title': title,
                'content': content,
                'summary': summary
            }
            
        except json.JSONDecodeError:
            # If JSON parsing fails, treat as plain text
            cleaned = self.remove_tv_phrases(raw_article)
            lines = cleaned.split('\n')
            title = lines[0] if lines else ''
            content = '\n'.join(lines[1:]) if len(lines) > 1 else ''
            
            return {
                'title': title.strip(),
                'content': content.strip(),
                'summary': title.strip()
            }
    
    def deep_clean(self, text):
        """Aggressive cleaning for TV-speak removal"""
        # Remove sentences containing TV phrases
        sentences = text.split('.')
        clean_sentences = []
        
        tv_indicators = [
            'ప్రతినిధి', 'వివరాలు', 'కరస్పాండెంట్', 'రిపోర్టర్',
            'చూడండి', 'వినండి', 'తెలుసుకుందాం', 'లైవ్'
        ]
        
        for sentence in sentences:
            if not any(indicator in sentence for indicator in tv_indicators):
                clean_sentences.append(sentence)
        
        return '.'.join(clean_sentences).strip()