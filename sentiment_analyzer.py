# -*- coding: utf-8 -*-
import re
from typing import Dict, List, Tuple, Optional

class SentimentAnalyzer:
    def __init__(self):
        self._init_data()

    def _init_data(self):
        # ==================== 1. 基础情绪库 (Tag: 关键词/正则, 基础分, 优先级) ====================
        # 优先级(Priority): 越高越容易覆盖其他情绪 (0=普通, 1=高优先, 2=绝对优先)
        self.EMOTION_NODES = {
            "morning": {
                "keywords": ["早安", "早上好", "早啊", "哦哈哟", "早"],
                "regex": [r"早$"],
                "emojis": ["🌅", "☕", "🐔", "☀️"],
                "base_score": 5.0,
                "priority": 0
            },
            "sanity": {
                "keywords": ["晚安", "睡了", "睡觉", "好梦", "累", "休息", "洗澡", "困"],
                "regex": [r"(去|要)睡", r"好{0,2}累", r"困.*死"],
                "emojis": ["💤", "🌙", "🛌", "🥱", "😪"],
                "base_score": 4.0,
                "priority": 0
            },
            "dont_cry": {
                "keywords": ["痛苦", "想哭", "破防", "崩溃", "难受", "甚至想笑", "地狱", "玉玉", "emo", "呜"],
                "regex": [r"好{0,2}(痛|苦)", r"呜{3,}", r"不想.*活"],
                "emojis": ["😭", "😢", "💔", "🥀", "💧"],
                "base_score": 6.0,
                "priority": 1
            },
            "comfort": {
                "keywords": ["救命", "害怕", "恐怖", "吓人", "难过", "伤心", "委屈", "help"],
                "regex": [r"被.*吓", r"好{0,2}怕", r"救.*命"],
                "emojis": ["😱", "😨", "😖", "🆘"],
                "base_score": 6.0,
                "priority": 2  # 救命是高优先级的
            },
            "fail": {
                "keywords": ["失败", "输了", "白给", "寄了", "如果", "假如", "后悔", "麻了", "菜"],
                "regex": [r"打.*不过", r"过.*不去"],
                "emojis": ["🏳️", "💀", "👎"],
                "base_score": 5.0,
                "priority": 0
            },
            "company": {
                "keywords": ["孤独", "寂寞", "没人", "一个人", "无聊", "冷清"],
                "regex": [r"理.*我"],
                "emojis": ["🍃", "🍂", "🪹"],
                "base_score": 4.0,
                "priority": 0
            },
            "trust": {
                "keywords": ["抱抱", "贴贴", "喜欢", "爱", "老婆", "特雷西娅", "殿下", "想你"],
                "regex": [r"最.*喜欢", r"爱.*你", r"想.*你"],
                "emojis": ["❤️", "🥰", "🤗", "😘", "💍"],
                "base_score": 5.0,
                "priority": 0
            },
            "poke": {
                "keywords": ["戳", "揉", "摸", "捣"],
                "regex": [],
                "emojis": ["👈", "👆"],
                "base_score": 3.0,
                "priority": 0
            }
        }

        # ==================== 2. 修饰符逻辑 (Vector Modifiers) ====================
        # 词汇: 权重系数 ( >1 为增强, <1 为削弱, <0 为反转)
        self.MODIFIERS = {
            # 增强 (Intensifiers)
            "super":  {"words": ["好", "太", "真", "非常", "超级", "死", "特别", "巨", "极其", "超", "爆"], "weight": 1.5},
            "mid":    {"words": ["比较", "还", "挺", "蛮"], "weight": 1.2},
            
            # 削弱 (Diminishers)
            "little": {"words": ["一点", "有点", "有些", "似"], "weight": 0.8},
            
            # 反转 (Negations) - 设置为 -0.5 表示变为负分(即不匹配)甚至扣分
            "negate": {"words": ["不", "没", "别", "勿", "无", "非", "假"], "weight": -1.0}
        }
        
        # 搜索修饰符的窗口大小（字符数）
        self.WINDOW_SIZE = 5 

    def analyze(self, text: str, enable_negation: bool = True) -> Tuple[Optional[str], float]:
        """
        执行算法：基于加权滑动窗口的情绪累加分析
        """
        text_lower = text.lower()
        
        # 最终得分容器 {tag: score}
        final_scores = {tag: 0.0 for tag in self.EMOTION_NODES}
        # 优先级记录 {tag: priority}
        max_priorities = {tag: 0 for tag in self.EMOTION_NODES}

        # 1. 标点符号预处理 (全局加成)
        global_boost = 1.0
        if "!" in text or "！" in text: global_boost += 0.2
        if "..." in text or "…" in text: global_boost += 0.1
        if "?" in text or "？" in text: global_boost += 0.1

        # 2. 遍历所有情绪节点
        for tag, data in self.EMOTION_NODES.items():
            base = data['base_score']
            priority = data['priority']
            
            # --- A. 关键词扫描 ---
            for kw in data['keywords']:
                # 使用 finditer 找到所有出现的位置，实现累加
                for match in re.finditer(re.escape(kw), text_lower):
                    score = self._calculate_node_weight(text_lower, match.start(), match.end(), base)
                    final_scores[tag] += score
                    max_priorities[tag] = max(max_priorities[tag], priority)

            # --- B. 正则扫描 (正则匹配通常权重更高) ---
            for pattern in data['regex']:
                for match in re.finditer(pattern, text_lower):
                    # 正则匹配基础分 + 2
                    score = self._calculate_node_weight(text_lower, match.start(), match.end(), base + 2.0)
                    final_scores[tag] += score
                    max_priorities[tag] = max(max_priorities[tag], priority)

            # --- C. Emoji 扫描 ---
            for emoji in data['emojis']:
                if emoji in text:
                    # Emoji 每一个算 1.5 分
                    final_scores[tag] += 1.5 * text.count(emoji)

        # 3. 结果决策 (Decision Making)
        best_tag = None
        best_score = 0.0
        
        # 过滤掉负分（被否定词反转的）和过低的分数
        candidates = {k: v * global_boost for k, v in final_scores.items() if v > 0}

        if not candidates:
            return None, 0

        # 排序策略：优先看 Priority，其次看 Score
        # 将字典转为列表 [(tag, score, priority), ...]
        sorted_candidates = sorted(
            [(k, v, max_priorities[k]) for k, v in candidates.items()],
            key=lambda item: (item[2], item[1]), # 先按优先级排，再按分数排
            reverse=True
        )

        best_tag, best_score, best_prio = sorted_candidates[0]

        # 阈值检查：如果分太低，视为误触 (Emoji除外，Emoji通常很准)
        if best_score < 3.0: 
            return None, 0

        return best_tag, best_score

    def _calculate_node_weight(self, text: str, start_idx: int, end_idx: int, base_score: float) -> float:
        """
        核心算法：计算单个节点的加权得分
        在关键词的前方(窗口内)搜索修饰符
        """
        # 定义窗口范围
        window_start = max(0, start_idx - self.WINDOW_SIZE)
        window_text = text[window_start:start_idx]
        
        current_multiplier = 1.0
        
        # 遍历修饰符库
        for mod_type, mod_data in self.MODIFIERS.items():
            for word in mod_data['words']:
                if word in window_text:
                    # 距离衰减算法: 
                    # 修饰词离关键词越近，效果越强。
                    # 这里简化处理：只要在窗口内就生效，如果想要更复杂可以引入 distance 计算
                    current_multiplier *= mod_data['weight']
                    
                    # 只要匹配到一个同类型的，就跳出该类型循环(避免 "超级非常" 乘两次爆炸，或者按需求改成累乘)
                    break 
        
        return base_score * current_multiplier