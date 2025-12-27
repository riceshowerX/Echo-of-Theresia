# -*- coding: utf-8 -*-
import re
import time
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict
from dataclasses import dataclass

@dataclass
class AnalysisResult:
    """情感分析结果"""
    tag: Optional[str]
    score: float
    priority: int
    confidence: float
    details: Dict[str, any]
    mixed_emotions: List[Tuple[str, float]]

class SentimentAnalyzer:
    
    def __init__(self):
        self._compile_patterns()
        self._init_data()
        self._init_advanced_features()
        
        # 性能统计
        self.stats = {
            "total_analyzed": 0,
            "cache_hits": 0,
            "avg_time": 0.0
        }

    def _compile_patterns(self):
        self.re_repeat_chars = re.compile(r"(.)\1{2,}")
        self.re_question = re.compile(r"(你|您|特|皇|殿).*[?？吗]")
        self.re_negation_scope = re.compile(r"(不|没|别|勿|无|非|假|莫|未|否|禁止)[^\s，。！？]{0,10}")
        self.re_conjunction = re.compile(r"(但是|可是|然而|不过|虽然|尽管)")

    def _init_advanced_features(self):
        # 高级特征配置
        self.ADVANCED_CONFIG = {
            "enable_position_weight": True,      # 启用位置权重
            "enable_context_aware": True,        # 启用上下文感知
            "enable_mixed_emotion": True,        # 启用混合情感检测
            "enable_text_length_norm": True,     # 启用文本长度归一化
            "enable_word_order": True,           # 启用词序权重
            "position_decay": 0.8,              # 位置衰减系数
            "text_length_factor": 0.1,           # 文本长度归一化因子
            "conjunction_penalty": 0.5,          # 转折词惩罚系数
            "negation_scope": 8,                 # 否定词作用范围（字符数）
        }

    def _init_data(self):
        self.EMOTION_NODES = {
            "morning": {
                "keywords": [
                    "早安", "早上好", "早啊", "哦哈哟", "早", "启动", "醒了", 
                    "起飞", "morning", "hi", "哈喽", "你好", "您好", "早上", 
                    "刚醒", "困死", "睁眼", "提神", "咖啡", "打卡"
                ],
                "regex": [r"早$", r"早.*好", r"^早", r"morning"],
                "emojis": ["🌅", "☕", "🐔", "☀️", "👋", "🥪", "🥛"],
                "base_score": 6.0,
                "priority": 0,
                "position_bonus": 1.2  # 出现在开头有额外加成
            },

            "sanity": {
                "keywords": [
                    "晚安", "睡了", "睡觉", "累", "休息", "困", "休眠", "下班", 
                    "午睡", "躺平", "歇会", "乏", "倦", "挂机",
                    "理智", "碎石", "吃石头", "搓玉", "肝", "1-7", "刷材料", 
                    "长草", "基建", "排班", "换班", "清理智", "剿灭", "代理",
                    "加班", "猝死", "通宵", "熬夜", "做题", "赶ddl", "开会",
                    "摸鱼", "不想动", "瘫", "累死"
                ],
                "regex": [
                    r"(去|要|想)睡", r"好{0,2}累", r"困.*死", r"眼.*睁不开", 
                    r"肝.*疼", r"理.*智.*(无|没|光|0)", r"下.*班", r"晚.*安"
                ],
                "emojis": ["💤", "🌙", "🛌", "🥱", "😪", "🌃", "🔋", "🪫"],
                "base_score": 6.0,
                "priority": 0,
                "position_bonus": 1.0
            },

            "dont_cry": {
                "keywords": [
                    "痛苦", "想哭", "难受", "伤心", "悲伤", "流泪", "哭",
                    "破防", "崩溃", "甚至想笑", "emo", "呜", "玉玉", "地狱", 
                    "寄", "似了", "裂开", "麻了", "小丑", "红温", "心态崩",
                    "致郁", "刀", "发病", "遗憾", "唉", "叹气"
                ],
                "regex": [
                    r"好{0,2}(痛|苦)", r"呜{3,}", r"不想.*活", r"心.*态.*崩", 
                    r"破.*大.*防", r"救.*我", r"笑.*不.*出.*来"
                ],
                "emojis": ["😭", "😢", "💔", "🥀", "💧", "🌧️", "😿", "😞", "🩸"],
                "base_score": 7.5,
                "priority": 1,
                "position_bonus": 1.3
            },

            "comfort": {
                "keywords": [
                    "救命", "害怕", "恐怖", "吓人", "委屈", "怕", "阴间", 
                    "噩梦", "鬼", "焦虑", "紧张", "压力", "窒息", "慌", 
                    "help", "sos", "不敢", "发抖", "吓死"
                ],
                "regex": [
                    r"被.*吓", r"好{0,2}怕", r"救.*命", r"吓.*死", 
                    r"别.*吓.*我", r"帮.*帮.*我"
                ],
                "emojis": ["😱", "😨", "😖", "🆘", "👻", "🧟", "🕷️", "😰"],
                "base_score": 8.0,
                "priority": 2,
                "position_bonus": 1.5
            },

            "fail": {
                "keywords": [
                    "失败", "输了", "白给", "如果", "假如", "后悔", "菜", "弱",
                    "沉船", "保底", "蓝天白云", "紫气东来", "潜能", "歪了", 
                    "漏怪", "代理失误", "演我", "丝血", "翻车", "手残", 
                    "脑溢血", "血压", "下饭", "操作变形", "打不过", "卡关"
                ],
                "regex": [
                    r"打.*不过", r"过.*不去", r"输.*了", r"高.*血.*压", 
                    r"抽.*不.*到", r"歪.*了"
                ],
                "emojis": ["🏳️", "💀", "👎", "🤡", "📉", "💩"],
                "base_score": 6.0,
                "priority": 0,
                "position_bonus": 1.1
            },

            "company": {
                "keywords": [
                    "孤独", "寂寞", "没人", "一个人", "无聊", "冷清", "理我", 
                    "自闭", "孤单", "落寞", "空虚", "没人爱", "孤寡", 
                    "只有你", "陪我", "聊聊", "说话"
                ],
                "regex": [
                    r"理.*我", r"在.*吗", r"没.*人", r"一.*个.*人", r"陪.*陪.*我"
                ],
                "emojis": ["🍃", "🍂", "🪹", "😶", "🌫️", "🚶"],
                "base_score": 5.0,
                "priority": 0,
                "position_bonus": 1.0
            },

            "trust": {
                "keywords": [
                    "老婆", "特雷西娅", "殿下", "皇女", "特蕾西娅", "女王",
                    "抱抱", "贴贴", "喜欢", "爱", "太强", "厉害", "想你", 
                    "亲亲", "结婚", "戒指", "羁绊", "想念", "心动", "可爱",
                    "温柔", "天使", "妈妈", "我爱你", "love"
                ],
                "regex": [
                    r"最.*喜欢", r"爱.*你", r"想.*你", r"结.*婚", r"老.*婆", 
                    r"贴.*贴", r"抱.*抱"
                ],
                "emojis": ["❤️", "🥰", "🤗", "😘", "💍", "🌹", "✨", "😻", "💕"],
                "base_score": 5.0,
                "priority": 0,
                "position_bonus": 1.2
            },

            "poke": {
                "keywords": [
                    "戳", "揉", "摸", "捣", "rua", "捏", "敲", "拍", 
                    "摸摸", "摸头", "把玩", "指指点点"
                ],
                "regex": [r"戳.*戳", r"摸.*摸"],
                "emojis": ["👈", "👆", "🤏", "👋"],
                "base_score": 4.0,
                "priority": 0,
                "position_bonus": 1.0
            }
        }

        self.MODIFIERS = {
            "super": {
                "words": [
                    "好", "太", "真", "非常", "超级", "死", "特别", "巨", "极其", 
                    "超", "爆", "绝", "顶级", "剧烈", "究极", "完全", "彻底"
                ], 
                "weight": 1.5,
                "priority": 3
            },
            "mid": {
                "words": ["比较", "还", "挺", "蛮", "相当"], 
                "weight": 1.2,
                "priority": 2
            },
            "little": {
                "words": ["一点", "有点", "有些", "似", "微", "稍"], 
                "weight": 0.8,
                "priority": 1
            },
            "negate": {
                "words": [
                    "不", "没", "别", "勿", "无", "非", "假", "莫", 
                    "未", "否", "禁止"
                ], 
                "weight": -1.0,
                "priority": 10
            }
        }
        
        self.WINDOW_SIZE = 6

    def analyze(self, text: str, enable_negation: bool = True) -> Tuple[Optional[str], float]:
        start_time = time.time()
        self.stats["total_analyzed"] += 1
        
        result = self._analyze_advanced(text, enable_negation)
        
        elapsed = time.time() - start_time
        self.stats["avg_time"] = (
            self.stats["avg_time"] * (self.stats["total_analyzed"] - 1) + elapsed
        ) / self.stats["total_analyzed"]
        
        return result.tag, result.score

    def _analyze_advanced(self, text: str, enable_negation: bool) -> AnalysisResult:
        """高级情感分析"""
        text_lower = text.lower()
        text_len = len(text)
        
        final_scores = {tag: 0.0 for tag in self.EMOTION_NODES}
        max_priorities = {tag: 0 for tag in self.EMOTION_NODES}
        match_details = defaultdict(list)
        
        global_boost = self._calculate_global_boost(text)
        question_penalty = self._calculate_question_penalty(text)
        text_norm_factor = self._calculate_text_length_norm(text_len)
        
        for tag, data in self.EMOTION_NODES.items():
            base = data['base_score']
            priority = data['priority']
            position_bonus = data.get('position_bonus', 1.0)
            
            tag_matches = []
            
            for kw in data['keywords']:
                if kw in text_lower:
                    for match in re.finditer(re.escape(kw), text_lower):
                        pos_weight = self._calculate_position_weight(
                            match.start(), text_len, position_bonus
                        )
                        
                        score = self._calculate_node_weight(
                            text_lower, match.start(), match.end(), base, pos_weight
                        )
                        
                        final_scores[tag] += score
                        max_priorities[tag] = max(max_priorities[tag], priority)
                        
                        tag_matches.append({
                            "type": "keyword",
                            "text": kw,
                            "pos": match.start(),
                            "score": score
                        })
            
            for pattern in data['regex']:
                for match in re.finditer(pattern, text_lower):
                    pos_weight = self._calculate_position_weight(
                        match.start(), text_len, position_bonus
                    )
                    
                    score = self._calculate_node_weight(
                        text_lower, match.start(), match.end(), base + 2.0, pos_weight
                    )
                    
                    final_scores[tag] += score
                    max_priorities[tag] = max(max_priorities[tag], priority)
                    
                    tag_matches.append({
                        "type": "regex",
                        "text": match.group(),
                        "pos": match.start(),
                        "score": score
                    })
            
            for emoji in data['emojis']:
                if emoji in text:
                    count = text.count(emoji)
                    score = 1.5 * count
                    final_scores[tag] += score
                    
                    tag_matches.append({
                        "type": "emoji",
                        "text": emoji,
                        "pos": text.find(emoji),
                        "score": score
                    })
            
            match_details[tag] = tag_matches
        
        candidates = {}
        for k, v in final_scores.items():
            final_v = v * global_boost * question_penalty * text_norm_factor
            if final_v > 0:
                candidates[k] = final_v
        
        if not candidates:
            return AnalysisResult(None, 0, 0, 0, {}, [])
        
        sorted_candidates = sorted(
            [(k, v, max_priorities[k]) for k, v in candidates.items()],
            key=lambda item: (item[2], item[1]),
            reverse=True
        )
        
        best_tag, best_score, best_priority = sorted_candidates[0]
        
        threshold = 2.5 if best_priority > 0 else 3.5
        
        if best_score < threshold:
            return AnalysisResult(None, 0, 0, 0, {}, [])
        
        confidence = self._calculate_confidence(best_score, threshold, best_priority)
        
        mixed_emotions = []
        if self.ADVANCED_CONFIG["enable_mixed_emotion"]:
            mixed_emotions = self._detect_mixed_emotions(
                [(k, v) for k, v in candidates.items() if v > threshold * 0.7]
            )
        
        return AnalysisResult(
            tag=best_tag,
            score=best_score,
            priority=best_priority,
            confidence=confidence,
            details={
                "matches": match_details[best_tag],
                "global_boost": global_boost,
                "question_penalty": question_penalty,
                "text_norm_factor": text_norm_factor
            },
            mixed_emotions=mixed_emotions
        )

    def _calculate_global_boost(self, text: str) -> float:
        """计算全局特征加成"""
        boost = 1.0
        
        if "!" in text or "！" in text:
            boost += 0.2
        if "..." in text or "…" in text:
            boost += 0.1
        if self.re_repeat_chars.search(text):
            boost += 0.3
        
        return boost

    def _calculate_question_penalty(self, text: str) -> float:
        """计算疑问句惩罚"""
        if self.re_question.search(text):
            return 0.4
        return 1.0

    def _calculate_text_length_norm(self, text_len: int) -> float:
        """计算文本长度归一化因子"""
        if not self.ADVANCED_CONFIG["enable_text_length_norm"]:
            return 1.0
        
        if text_len < 10:
            return 1.0
        elif text_len < 50:
            return 1.0 - (text_len - 10) * self.ADVANCED_CONFIG["text_length_factor"] * 0.01
        else:
            return 0.6

    def _calculate_position_weight(self, pos: int, text_len: int, bonus: float) -> float:
        """计算位置权重"""
        if not self.ADVANCED_CONFIG["enable_position_weight"]:
            return 1.0
        
        if text_len == 0:
            return 1.0
        
        relative_pos = pos / text_len
        
        if relative_pos < 0.2:
            return bonus * 1.3
        elif relative_pos < 0.5:
            return bonus * 1.1
        elif relative_pos < 0.8:
            return bonus * 1.0
        else:
            return bonus * 0.9

    def _calculate_node_weight(
        self, 
        text: str, 
        start_idx: int, 
        end_idx: int, 
        base_score: float,
        pos_weight: float = 1.0
    ) -> float:
        """计算节点权重（增强版）"""
        window_start = max(0, start_idx - self.WINDOW_SIZE)
        window_text = text[window_start:start_idx]
        
        multiplier = 1.0
        
        # 按优先级排序修饰符
        sorted_modifiers = sorted(
            self.MODIFIERS.items(),
            key=lambda x: x[1]['priority'],
            reverse=True
        )
        
        for mod_type, mod_data in sorted_modifiers:
            for word in mod_data['words']:
                if word in window_text:
                    multiplier *= mod_data['weight']
                    break
        
        # 检查否定词作用范围
        if self._is_in_negation_scope(text, start_idx):
            multiplier *= -0.5
        
        return base_score * multiplier * pos_weight

    def _is_in_negation_scope(self, text: str, pos: int) -> bool:
        """检查是否在否定词作用范围内"""
        scope_start = max(0, pos - self.ADVANCED_CONFIG["negation_scope"])
        scope_text = text[scope_start:pos]
        
        return any(neg in scope_text for neg in self.MODIFIERS["negate"]["words"])

    def _calculate_confidence(self, score: float, threshold: float, priority: int) -> float:
        """计算置信度"""
        if threshold == 0:
            return 0.0
        
        base_confidence = min((score - threshold) / threshold, 1.0)
        
        if priority == 2:
            base_confidence = min(base_confidence + 0.2, 1.0)
        elif priority == 1:
            base_confidence = min(base_confidence + 0.1, 1.0)
        
        return max(base_confidence, 0.0)

    def _detect_mixed_emotions(self, candidates: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """检测混合情感"""
        if len(candidates) < 2:
            return []
        
        total = sum(v for _, v in candidates)
        
        mixed = []
        for tag, score in candidates:
            ratio = score / total
            if ratio > 0.2:
                mixed.append((tag, ratio))
        
        return sorted(mixed, key=lambda x: x[1], reverse=True)[:3]

    def get_analysis_details(self, text: str, enable_negation: bool = True) -> AnalysisResult:
        """获取详细分析结果"""
        return self._analyze_advanced(text, enable_negation)

    def get_statistics(self) -> Dict[str, any]:
        """获取统计信息"""
        return {
            "total_analyzed": self.stats["total_analyzed"],
            "avg_time_ms": self.stats["avg_time"] * 1000,
            "cache_hit_rate": (
                self.stats["cache_hits"] / self.stats["total_analyzed"]
                if self.stats["total_analyzed"] > 0 else 0
            )
        }

    def reset_statistics(self):
        """重置统计信息"""
        self.stats = {
            "total_analyzed": 0,
            "cache_hits": 0,
            "avg_time": 0.0
        }
