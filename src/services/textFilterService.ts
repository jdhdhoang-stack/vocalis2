
export interface PhoneticEntry {
    id: string;
    original: string;
    phonetic: string;
}

export interface FilterOptions {
    removeJunkBlocks: boolean;
    removeChapterHeader: boolean;
    removeEndNumbers: boolean;
    convertLargeNumbers: boolean;
    removeNumbers: boolean;
    removeWhitespace: boolean;
    manualPhonetic: boolean;
}

export class TextFilterService {
    private static readonly UNITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"];
    private static readonly GROUPS = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ", "tỷ tỷ"];
    
    private static readonly DYNAMIC_JUNK_PATTERNS = [
        /^\d+\s+nhận\s+xét$/i,
        /^\d+\s+còn\s+lại$/i,
        /^\d+\s+left$/i,
        /^bỏ\s+phiếu$/i,
        /^\d+\s+bình\s+luận$/i,
        /^bình\s+luận$/i, 
        /^thêm\s+bình\s+luận$/i,
        /^\d+\s+comment(s)?$/i,
        /^suy\s+nghĩ\s+của\s+người\s+sáng\s+tạo$/i,
        /^rắn\s+hồng$/i,
        /(?:https?:\/\/)?discord\.(?:gg|com\/invite)\/\S+/i,
        /\d+\s+power\s+stones\s*=\s*\d+\s+chương\s+bônus/i, 
        /\d+\s+đánh\s+giá\s*=\s*\d+\s+chương\s+bônus/i,   
        /\d+\s+stones\s*=\s*\d+\s+bonus/i                  
    ];

    private static readonly CHAPTER_PATTERN = /^(chapter|chương)\s+\d+/i;
    private static readonly END_NUMBERS_PATTERN = /\s+\d+(\+)?\s*$/;
    private static readonly NUMBER_REGEX = /\d{1,3}(?:\.\d{3})+|\d{4,}/g;
    private static readonly WHITESPACE_REGEX = /[^\S\r\n]+/g;
    private static readonly EMPTY_LINE_REGEX = /^\s*[\r\n]/gm;

    public static numberToVietnamese(numStr: string): string {
        const cleanNum = numStr.replace(/\./g, "");
        if (isNaN(Number(cleanNum))) return numStr;
        const n = BigInt(cleanNum);
        if (n === 0n) return "không";
        
        const readThreeDigits = (threeDigits: string, isFirstChunk: boolean): string => {
            const a = parseInt(threeDigits[0]);
            const b = parseInt(threeDigits[1]);
            const c = parseInt(threeDigits[2]);
            let res = "";

            if (a !== 0) {
                res += this.UNITS[a] + " trăm ";
            } else if (!isFirstChunk) {
                if (b !== 0 || c !== 0) res += "không trăm ";
            }

            if (b !== 0 && b !== 1) {
                res += this.UNITS[b] + " mươi ";
            } else if (b === 1) {
                res += "mười ";
            } else if (!isFirstChunk && b === 0 && c !== 0 && a !== 0) {
                res += "lẻ ";
            } else if (isFirstChunk && b === 0 && c !== 0 && a !== 0) {
                res += "lẻ ";
            } else if (b === 0 && c !== 0 && res.includes("trăm")) {
                res += "lẻ ";
            }

            if (c !== 0) {
                if (c === 1 && b > 1) res += "mốt";
                else if (c === 5 && b > 0) res += "lăm";
                else res += this.UNITS[c];
            }
            return res.trim();
        };

        let str = cleanNum;
        const chunks: string[] = [];
        while (str.length > 0) {
            const chunk = str.slice(-3).padStart(3, '0');
            chunks.push(chunk);
            str = str.slice(0, -3);
        }

        let result = "";
        for (let i = chunks.length - 1; i >= 0; i--) {
            const chunkText = readThreeDigits(chunks[i], i === chunks.length - 1);
            if (chunkText) {
                result += chunkText + " " + (this.GROUPS[i] || "") + " ";
            }
        }

        return result.trim().replace(/\s+/g, ' ');
    }

    public static process(text: string, options: FilterOptions, junkKeywords: string, phoneticDict: PhoneticEntry[]): string {
        if (!text.trim()) return '';

        let lines = text.split(/\r?\n/);
        const keywords = junkKeywords.split(',').map(k => k.trim().toLowerCase()).filter(k => k !== "");
        
        let finalLines: string[] = [];
        let i = 0;

        while (i < lines.length) {
            let line = lines[i];
            let lineTrimmed = line.trim();
            let lineLower = lineTrimmed.toLowerCase();

            if (!lineTrimmed) {
                finalLines.push("");
                i++;
                continue;
            }

            if (options.removeChapterHeader && this.CHAPTER_PATTERN.test(lineTrimmed)) {
                i++;
                continue;
            }

            const isDynamicJunk = this.DYNAMIC_JUNK_PATTERNS.some(pattern => pattern.test(lineTrimmed));
            if (isDynamicJunk) {
                i++;
                continue;
            }

            if (options.removeJunkBlocks) {
                let isCurrentJunk = keywords.some(k => lineLower.includes(k));
                if (isCurrentJunk) {
                    let nextJunkIdx = -1;
                    for (let j = i + 1; j < Math.min(i + 6, lines.length); j++) {
                        let nextLineTrimmed = lines[j].trim();
                        let nextLineLower = nextLineTrimmed.toLowerCase();
                        if (nextLineLower === "") continue; 
                        const isNextDynamicJunk = this.DYNAMIC_JUNK_PATTERNS.some(pattern => pattern.test(nextLineTrimmed));
                        if (isNextDynamicJunk || keywords.some(k => nextLineLower.includes(k))) {
                            nextJunkIdx = j;
                            break;
                        }
                    }

                    if (nextJunkIdx !== -1 || lineLower.includes('discord.gg') || lineLower.includes('send gift') || lineLower.includes('left') || lineLower.includes('power stones')) {
                        while (i < lines.length) {
                            let checkLineTrimmed = lines[i].trim();
                            let checkLineLower = checkLineTrimmed.toLowerCase();
                            const isCheckDynamicJunk = this.DYNAMIC_JUNK_PATTERNS.some(pattern => pattern.test(checkLineTrimmed));
                            if (checkLineLower === "" || isCheckDynamicJunk || keywords.some(k => checkLineLower.includes(k))) {
                                i++;
                            } else {
                                break; 
                            }
                        }
                        continue;
                    }
                }
            }

            if (options.removeEndNumbers) {
                line = line.replace(this.END_NUMBERS_PATTERN, '');
            }

            finalLines.push(line);
            i++;
        }

        let result = finalLines.join('\n');
        
        if (options.manualPhonetic) {
            const sortedDict = [...phoneticDict].sort((a, b) => b.original.length - a.original.length);
            sortedDict.forEach(entry => {
                if (!entry.original.trim()) return;
                try {
                    const escaped = entry.original.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                    const regex = new RegExp(`\\b${escaped}\\b`, 'gi');
                    result = result.replace(regex, entry.phonetic);
                } catch (e) {
                    console.error("Phonetic replacement error", e);
                }
            });
        }

        if (options.convertLargeNumbers) {
            result = result.replace(this.NUMBER_REGEX, (match) => {
                const clean = match.replace(/\./g, "");
                const val = parseInt(clean);
                if (val >= 1000 && val % 1000 === 0) {
                    if (val >= 1000000000 && val % 1000000000 === 0) return (val / 1000000000) + " tỷ";
                    if (val >= 1000000 && val % 1000000 === 0) return (val / 1000000) + " triệu";
                    if (val >= 1000 && val % 1000 === 0) return (val / 1000) + " nghìn";
                }
                return this.numberToVietnamese(match);
            });
        }

        if (options.removeNumbers) {
            result = result.replace(/[0-9]/g, '');
        }
        
        if (options.removeWhitespace) {
            result = result.replace(this.WHITESPACE_REGEX, ' ') 
                           .replace(this.EMPTY_LINE_REGEX, '') 
                           .trim();
        }

        return result;
    }
}
