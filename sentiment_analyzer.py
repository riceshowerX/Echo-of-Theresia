# -*- coding: utf-8 -*-
import re
from typing import Dict, List, Tuple, Optional

class SentimentAnalyzer:
    def __init__(self):
        self._init_data()

    def _init_data(self):
        # 优先级(Priority): 越高越容易覆盖其他情绪 (0=普通, 1=高优先, 2=绝对优先)
        self.EMOTION_NODES = {
            "morning": {
                "keywords": ["早安", "早上好", "早啊", "哦哈哟", "早", "启动"],
                "regex": [r"早$"],
                "emojis": ["🌅", "☕", "🐔", "☀️"],
                "base_score": 6.0,
                "priority": 0
            },
            "sanity": { # 对应语音：闲置 ("累了吗？那就休息吧")
                "keywords": ["晚安", "睡了", "睡觉", "累", "休息", "困", "休眠", "下班"],
                "regex": [r"(去|要)睡", r"好{0,2}累", r"困.*死"],
                "emojis": ["💤", "🌙", "🛌", "🥱", "😪"],
                "base_score": 6.0, # 提高分数，因为这条语音很万能
                "priority": 0
            },
            "dont_cry": { # 对应语音：作战中4 ("别哭，很快就结束了")
                "keywords": ["痛苦", "想哭", "破防", "崩溃", "难受", "甚至想笑", "emo", "呜"],
                "regex": [r"好{0,2}(痛|苦)", r"呜{3,}", r"不想.*活"],
                "emojis": ["😭", "😢", "💔", "🥀", "💧"],
                "base_score": 7.0,
                "priority": 1
            },
            "comfort": { # 对应语音：选中干员2 ("别怕，我在")
                "keywords": ["救命", "害怕", "恐怖", "吓人", "难过", "伤心", "委屈", "怕"],
                "regex": [r"被.*吓", r"好{0,2}怕", r"救.*命"],
                "emojis": ["😱", "😨", "😖", "🆘"],
                "base_score": 7.0,
                "priority": 2
            },
            "fail": { # 对应语音：行动失败 ("我们一定可以跨过这些伤痛")
                "keywords": ["失败", "输了", "白给", "寄了", "如果", "假如", "后悔", "麻了", "菜"],
                "regex": [r"打.*不过", r"过.*不去", r"输.*了"],
                "emojis": ["🏳️", "💀", "👎"],
                "base_score": 6.0,
                "priority": 0
            },
            "company": { # 对应语音：部署2 ("我在这儿呢")
                "keywords": ["孤独", "寂寞", "没人", "一个人", "无聊", "冷清", "理我"],
                "regex": [r"理.*我", r"在.*吗"],
                "emojis": ["🍃", "🍂", "🪹"],
                "base_score": 5.0,
                "priority": 0
            },
            "trust": { # 对应语音：信赖触摸 ("我在注视着你") / 3星结束
                "keywords": ["抱抱", "贴贴", "喜欢", "爱", "老婆", "特雷西娅", "殿下", "太强", "厉害"],
                "regex": [r"最.*喜欢", r"爱.*你", r"想.*你"],
                "emojis": ["❤️", "🥰", "🤗", "😘", "💍"],
                "base_score": 5.0,
                "priority": 0
            },
            "poke": { # 对应语音：戳一下 ("哈！被吓到了吗？")
                "keywords": ["戳", "揉", "摸", "捣"],
                "regex": [],
                "emojis": ["👈", "👆"],
                "base_score": 4.0,
                "priority": 0
            }
        }

        self.MODIFIERS = {
            "super":  {"words": ["好", "太", "真", "非常", "超级", "死", "特别", "巨", "极其", "超"], "weight": 1.5},
            "mid":    {"words": ["比较", "还", "挺", "蛮"], "weight": 1.2},
            "little": {"words": ["一点", "有点", "有些", "似"], "weight": 0.8},
            "negate": {"words": ["不", "没", "别", "勿", "无", "非", "假"], "weight": -1.0}
        }
        self.WINDOW_SIZE = 5 

    def analyze(self, text: str, enable_negation: bool = True) -> Tuple[Optional[str], float]:
        text_lower = text.lower()
        final_scores = {tag: 0.0 for tag in self.EMOTION_NODES}
        max_priorities = {tag: 0 for tag in self.EMOTION_NODES}

        global_boost = 1.0
        if "!" in text or "！" in text: global_boost += 0.2
        if "..." in text or "…" in text: global_boost += 0.1
        if "?" in text or "？" in text: global_boost += 0.1

        for tag, data in self.EMOTION_NODES.items():
            base = data['base_score']
            priority = data['priority']
            
            for kw in data['keywords']:
                for match in re.finditer(re.escape(kw), text_lower):
                    score = self._calculate_node_weight(text_lower, match.start(), match.end(), base)
                    final_scores[tag] += score
                    max_priorities[tag] = max(max_priorities[tag], priority)

            for pattern in data['regex']:
                for match in re.finditer(pattern, text_lower):
                    score = self._calculate_node_weight(text_lower, match.start(), match.end(), base + 2.0)
                    final_scores[tag] += score
                    max_priorities[tag] = max(max_priorities[tag], priority)

            for emoji in data['emojis']:
                if emoji in text:
                    final_scores[tag] += 1.5 * text.count(emoji)

        candidates = {k: v * global_boost for k, v in final_scores.items() if v > 0}
        if not candidates: return None, 0

        sorted_candidates = sorted(
            [(k, v, max_priorities[k]) for k, v in candidates.items()],
            key=lambda item: (item[2], item[1]),
            reverse=True
        )

        best_tag, best_score, _ = sorted_candidates[0]
        if best_score < 3.0: return None, 0

        return best_tag, best_score

    def _calculate_node_weight(self, text: str, start_idx: int, end_idx: int, base_score: float) -> float:
        window_start = max(0, start_idx - self.WINDOW_SIZE)
        window_text = text[window_start:start_idx]
        current_multiplier = 1.0
        
        for mod_type, mod_data in self.MODIFIERS.items():
            for word in mod_data['words']:
                if word in window_text:
                    current_multiplier *= mod_data['weight']
                    break 
        
        return base_score * current_multiplier