import re
import math
from typing import List, Dict, Any, Optional
from docx import Document
import io

class TextProcessor:
    def __init__(self, max_chars: int = 1500, min_chars_to_merge: int = 30):
        if max_chars <= 0:
            raise ValueError("max_chars must be a positive number.")
        self.max_chars = max_chars
        self.min_chars_to_merge = min_chars_to_merge
        
        # Pre-compile regex for performance
        self.LINE_BREAKS_REGEX = re.compile(r'\r\n|\r')
        self.MULTI_NEWLINE_REGEX = re.compile(r'\n{2,}')
        self.CONTROL_CHARS_REGEX = re.compile(r'[\x00-\x08\x0b-\x1f\x7f]')
        self.MULTI_SPACE_REGEX = re.compile(r'[ \t]+')
        self.VIETNAMESE_ABBR_REGEX = re.compile(r'(TP|P|Q|H|T|S|P\.S|V\.V|V\.N|T\.P|Q\.L|N\.X\.B|T\.S|K\.S|B\.S|T\.H|T\.C|C\.T|C\.P|U\.B|H\.Đ|N\.D|N\.N|T\.Ư|T\.T|P\.T|P\.V|C\.A|Q\.Đ|H\.Q|T\.C|T\.D|T\.L|K\.T|X\.H|V\.H|G\.D|Y\.T|K\.H|C\.N|M\.T|D\.V|T\.M|B\.L|H\.S|K\.L|T\.N|P\.L|Q\.T|H\.Đ|N\.Q|C\.Q|T\.B|H\.B|P\.B|T\.C|V\.P|B\.T|T\.G|T\.K|T\.P|T\.X|H\.T|X\.T|C\.T|N\.T|P\.T|D\.T|K\.T|V\.T|S\.T|B\.T|L\.T|M\.T|N\.T|P\.T|Q\.T|R\.T|S\.T|T\.T|U\.T|V\.T|W\.T|X\.T|Y\.T|Z\.T)\.', re.IGNORECASE)
        self.SENTENCE_SPLIT_REGEX = re.compile(r'(?<=[.?!])\s+')

    def clean_text(self, text: str) -> str:
        cleaned = self.LINE_BREAKS_REGEX.sub('\n', text)
        cleaned = self.MULTI_NEWLINE_REGEX.sub('\n', cleaned)
        cleaned = self.CONTROL_CHARS_REGEX.sub('', cleaned)
        lines = cleaned.split('\n')
        cleaned_lines = [self.MULTI_SPACE_REGEX.sub(' ', line).strip() for line in lines]
        return '\n'.join(cleaned_lines).strip()

    def split_long_sentence(self, sentence: str) -> List[str]:
        sub_sentences = []
        current_part = sentence
        delimiters = ['. ', ', ', '! ', '? ', ': ', '; ', ' ']
        
        while len(current_part) > self.max_chars:
            cut_pos = -1
            for delim in delimiters:
                found_pos = current_part.rfind(delim, 0, self.max_chars)
                if found_pos != -1:
                    cut_pos = found_pos + len(delim)
                    break
            if cut_pos == -1:
                cut_pos = self.max_chars
            sub_sentences.append(current_part[:cut_pos].strip())
            current_part = current_part[cut_pos:].strip()
        if current_part:
            sub_sentences.append(current_part)
        return sub_sentences

    def process(self, text: str) -> List[str]:
        cleaned_text = self.clean_text(text)
        # Protect abbreviations from being split
        protected_text = self.VIETNAMESE_ABBR_REGEX.sub(lambda m: m.group(0).replace('.', '___DOT___'), cleaned_text)
        
        paragraphs = [p for p in protected_text.split('\n') if p]
        all_sentences = []

        for para in paragraphs:
            sentences_in_para = [s.strip() for s in self.SENTENCE_SPLIT_REGEX.split(para) if s.strip()]
            sentences_in_para = [s.replace('___DOT___', '.') for s in sentences_in_para]
            all_sentences.extend(sentences_in_para)
        
        chunks = []
        current_chunk = ""

        for sentence in all_sentences:
            if len(sentence) > self.max_chars:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = ""
                chunks.extend(self.split_long_sentence(sentence))
                continue
            if len(current_chunk) + len(sentence) + 1 > self.max_chars:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
            else:
                current_chunk = f"{current_chunk} {sentence}" if current_chunk else sentence
        if current_chunk:
            chunks.append(current_chunk)

        if len(chunks) >= 2 and len(chunks[-1]) < self.min_chars_to_merge:
            last_chunk = chunks.pop()
            second_to_last_chunk = chunks[-1]

            if len(second_to_last_chunk) + len(last_chunk) + 1 <= self.max_chars:
                chunks[-1] += " " + last_chunk
            else:
                sentences_in_chunk = self.SENTENCE_SPLIT_REGEX.split(second_to_last_chunk)
                if len(sentences_in_chunk) > 1:
                    sentence_to_move = sentences_in_chunk.pop()
                    new_last_chunk = f"{sentence_to_move} {last_chunk}"

                    if len(new_last_chunk) <= self.max_chars:
                        chunks[-1] = " ".join(sentences_in_chunk)
                        chunks.append(new_last_chunk)
                    else:
                        chunks.append(last_chunk)
                else:
                    chunks.append(last_chunk)
        return [c for c in chunks if len(c) > 0]

class TextFilterService:
    UNITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
    GROUPS = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ", "tỷ tỷ"]
    
    DYNAMIC_JUNK_PATTERNS = [
        re.compile(r'^\d+\s+nhận\s+xét$', re.IGNORECASE),
        re.compile(r'^\d+\s+còn\s+lại$', re.IGNORECASE),
        re.compile(r'^\d+\s+left$', re.IGNORECASE),
        re.compile(r'^bỏ\s+phiếu$', re.IGNORECASE),
        re.compile(r'^\d+\s+bình\s+luận$', re.IGNORECASE),
        re.compile(r'^bình\s+luận$', re.IGNORECASE), 
        re.compile(r'^thêm\s+bình\s+luận$', re.IGNORECASE),
        re.compile(r'^\d+\s+comment(s)?$', re.IGNORECASE),
        re.compile(r'^suy\s+nghĩ\s+của\s+người\s+sáng\s+tạo$', re.IGNORECASE),
        re.compile(r'^rắn\s+hồng$', re.IGNORECASE),
        re.compile(r'(?:https?://)?discord\.(?:gg|com/invite)/\S+', re.IGNORECASE),
        re.compile(r'\d+\s+power\s+stones\s*=\s*\d+\s+chương\s+bônus', re.IGNORECASE), 
        re.compile(r'\d+\s+đánh\s+giá\s*=\s*\d+\s+chương\s+bônus', re.IGNORECASE),   
        re.compile(r'\d+\s+stones\s*=\s*\d+\s+bonus', re.IGNORECASE)                  
    ]

    CHAPTER_PATTERN = re.compile(r'^(chapter|chương)\s+\d+', re.IGNORECASE)
    END_NUMBERS_PATTERN = re.compile(r'\s+\d+(\+)?\s*$')
    NUMBER_REGEX = re.compile(r'\d{1,3}(?:\.\d{3})+|\d{4,}')
    WHITESPACE_REGEX = re.compile(r'[^\S\r\n]+')
    EMPTY_LINE_REGEX = re.compile(r'^\s*[\r\n]', re.MULTILINE)

    @classmethod
    def number_to_vietnamese(cls, num_str: str) -> str:
        clean_num = num_str.replace(".", "")
        try:
            val = int(clean_num)
        except ValueError:
            return num_str
        if val == 0: return "không"
        
        pos = len(clean_num)
        chunks = []
        while pos > 0:
            start = max(0, pos - 3)
            chunks.append(clean_num[start:pos].zfill(3))
            pos = start
        
        result = ""
        has_started = False
        for i in range(len(chunks) - 1, -1, -1):
            n = chunks[i]
            v = int(n)
            if v == 0: continue
            
            a = int(n[0])
            b = int(n[1])
            c = int(n[2])
            chunk_text = ""
            
            if has_started:
                if a != 0: chunk_text += cls.UNITS[a] + " trăm "
                else:
                    if b != 0: chunk_text += "không trăm "
                    else: chunk_text += "lẻ "
            else:
                if a != 0: chunk_text += cls.UNITS[a] + " trăm "
            
            if b != 0 and b != 1: chunk_text += cls.UNITS[b] + " mươi "
            elif b == 1: chunk_text += "mười "
            
            if c != 0:
                if c == 1 and b > 1: chunk_text += "mốt"
                elif c == 5 and b > 0: chunk_text += "lăm"
                else: chunk_text += cls.UNITS[c]
            result += chunk_text.strip() + " " + cls.GROUPS[i] + " "
            has_started = True
        return re.sub(r'\s+', ' ', result.strip())

    @classmethod
    def process(cls, text: str, options: Dict[str, bool], junk_keywords: str, phonetic_dict: List[Dict[str, str]]) -> str:
        if not text.strip(): return ''

        lines = text.splitlines()
        keywords = [k.strip().lower() for k in junk_keywords.split(',') if k.strip()]
        
        final_lines = []
        i = 0

        while i < len(lines):
            line = lines[i]
            line_trimmed = line.strip()
            line_lower = line_trimmed.lower()

            if not line_trimmed:
                final_lines.append("")
                i += 1
                continue

            if options.get('removeChapterHeader') and cls.CHAPTER_PATTERN.match(line_trimmed):
                i += 1
                continue

            is_dynamic_junk = any(pattern.match(line_trimmed) for pattern in cls.DYNAMIC_JUNK_PATTERNS)
            if is_dynamic_junk:
                i += 1
                continue

            if options.get('removeJunkBlocks'):
                is_current_junk = any(k in line_lower for k in keywords)
                if is_current_junk:
                    next_junk_idx = -1
                    for j in range(i + 1, min(i + 6, len(lines))):
                        next_line_trimmed = lines[j].strip()
                        next_line_lower = next_line_trimmed.lower()
                        if next_line_lower == "": continue 
                        is_next_dynamic_junk = any(pattern.match(next_line_trimmed) for pattern in cls.DYNAMIC_JUNK_PATTERNS)
                        if is_next_dynamic_junk or any(k in next_line_lower for k in keywords):
                            next_junk_idx = j
                            break

                    if next_junk_idx != -1 or 'discord.gg' in line_lower or 'send gift' in line_lower or 'left' in line_lower or 'power stones' in line_lower:
                        while i < len(lines):
                            check_line_trimmed = lines[i].strip()
                            check_line_lower = check_line_trimmed.lower()
                            is_check_dynamic_junk = any(pattern.match(check_line_trimmed) for pattern in cls.DYNAMIC_JUNK_PATTERNS)
                            if check_line_lower == "" or is_check_dynamic_junk or any(k in check_line_lower for k in keywords):
                                i += 1
                            else:
                                break 
                        continue

            if options.get('removeEndNumbers'):
                line = cls.END_NUMBERS_PATTERN.sub('', line)

            final_lines.append(line)
            i += 1

        result = '\n'.join(final_lines)
        
        if options.get('manualPhonetic'):
            sorted_dict = sorted(phonetic_dict, key=lambda x: len(x['original']), reverse=True)
            for entry in sorted_dict:
                if not entry['original'].strip(): continue
                try:
                    escaped = re.escape(entry['original'])
                    regex = re.compile(rf'\b{escaped}\b', re.IGNORECASE)
                    result = regex.sub(entry['phonetic'], result)
                except Exception as e:
                    print(f"Phonetic replacement error: {e}")

        if options.get('convertLargeNumbers'):
            def replace_num(match):
                match_str = match.group(0)
                clean = match_str.replace(".", "")
                val = int(clean)
                if val >= 1000 and val % 1000 == 0:
                    if val >= 1000000000 and val % 1000000000 == 0: return f"{val // 1000000000} tỷ"
                    if val >= 1000000 and val % 1000000 == 0: return f"{val // 1000000} triệu"
                    if val >= 1000 and val % 1000 == 0: return f"{val // 1000} nghìn"
                return cls.number_to_vietnamese(match_str)
            result = cls.NUMBER_REGEX.sub(replace_num, result)

        if options.get('removeNumbers'):
            result = re.sub(r'[0-9]', '', result)
        
        if options.get('removeWhitespace'):
            result = cls.WHITESPACE_REGEX.sub(' ', result)
            result = cls.EMPTY_LINE_REGEX.sub('', result)
            result = result.strip()

        return result
