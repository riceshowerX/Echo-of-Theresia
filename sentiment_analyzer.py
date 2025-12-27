# -*- coding: utf-8 -*-
import re
import time
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class AnalysisResult:
    """情感分析结果"""
    tag: Optional[str]
    score: float
    priority: int
    confidence: float
    details: Dict[str, any]
    mixed_emotions: List[Tuple[str, float]]

@dataclass
class FeedbackRecord:
    """用户反馈记录"""
    text: str
    predicted_tag: str
    correct_tag: Optional[str]
    timestamp: float
    user_id: Optional[str] = None
    confidence: float = 0.0

@dataclass
class UserPreferences:
    """用户偏好"""
    user_id: str
    emotion_weights: Dict[str, float] = field(default_factory=dict)
    common_phrases: Dict[str, str] = field(default_factory=dict)
    last_active: float = 0.0
    total_interactions: int = 0

class SentimentAnalyzer:
    
    def __init__(self, data_dir: Optional[Path] = None):
        self._compile_patterns()
        self._init_data()
        self._init_advanced_features()
        self._init_learning_system(data_dir)
        
        # 性能统计
        self.stats = {
            "total_analyzed": 0,
            "cache_hits": 0,
            "avg_time": 0.0,
            "feedback_count": 0,
            "learning_updates": 0
        }

    def _compile_patterns(self):
        self.re_repeat_chars = re.compile(r"(.)\1{2,}")
        self.re_question = re.compile(r"(你|您|特|皇|殿).*[?？吗]")
        self.re_negation_scope = re.compile(r"(不|没|别|勿|无|非|假|莫|未|否|禁止)[^\s，。！？]{0,10}")
        self.re_conjunction = re.compile(r"(但是|可是|然而|不过|虽然|尽管)")

    def _init_advanced_features(self):
        self.ADVANCED_CONFIG = {
            "enable_position_weight": True,
            "enable_context_aware": True,
            "enable_mixed_emotion": True,
            "enable_text_length_norm": True,
            "enable_word_order": True,
            "enable_learning": True,
            "enable_personalization": True,
            "position_decay": 0.8,
            "text_length_factor": 0.1,
            "conjunction_penalty": 0.5,
            "negation_scope": 8,
            "learning_rate": 0.1,
            "feedback_threshold": 5,
            "max_weight_adjustment": 2.0
        }

    def _init_learning_system(self, data_dir: Optional[Path] = None):
        """初始化学习系统"""
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.feedback_file = self.data_dir / "feedback.json"
        self.preferences_file = self.data_dir / "user_preferences.json"
        
        # 反馈记录
        self.feedback_records: List[FeedbackRecord] = []
        self._load_feedback()
        
        # 用户偏好
        self.user_preferences: Dict[str, UserPreferences] = {}
        self._load_user_preferences()

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
                "position_bonus": 1.2,
                "category": "greeting"
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
                "position_bonus": 1.0,
                "category": "fatigue"
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
                "position_bonus": 1.3,
                "category": "sadness"
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
                "position_bonus": 1.5,
                "category": "fear"
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
                "position_bonus": 1.1,
                "category": "failure"
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
                "position_bonus": 1.0,
                "category": "loneliness"
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
                "position_bonus": 1.2,
                "category": "affection"
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
                "position_bonus": 1.0,
                "category": "interaction"
            },

            "anger": {
                "keywords": [
                    "生气", "愤怒", "火大", "烦", "烦死了", "滚", "滚蛋",
                    "讨厌", "恶心", "恶心", "暴躁", "炸了", "气死",
                    "无语", "无语", "靠", "操", "tmd", "tm", "cnm",
                    "愤怒", "怒", "恼火", "不爽", "不爽"
                ],
                "regex": [
                    r"好{0,2}(烦|气|怒)", r"烦.*死", r"气.*死", r"炸.*了",
                    r"滚.*蛋", r"无.*语", r"不.*爽"
                ],
                "emojis": ["😡", "😤", "🤬", "💢", "💥", "🔥", "👊"],
                "base_score": 7.0,
                "priority": 1,
                "position_bonus": 1.3,
                "category": "anger"
            },

            "surprise": {
                "keywords": [
                    "哇", "天哪", "天啊", "震惊", "惊讶", "意外", "没想到",
                    "真的吗", "不会吧", "居然", "竟然", "难以置信",
                    "wow", "omg", "天", "啊", "诶", "咦"
                ],
                "regex": [
                    r"哇{2,}", r"天.*哪", r"天.*啊", r"震.*惊",
                    r"意.*外", r"没.*想.*到", r"居然", r"竟然"
                ],
                "emojis": ["😲", "😮", "😯", "🤯", "😱", "😳", "🙀"],
                "base_score": 5.5,
                "priority": 0,
                "position_bonus": 1.1,
                "category": "surprise"
            },

            "hope": {
                "keywords": [
                    "期待", "加油", "相信", "希望", "努力", "坚持", "奋斗",
                    "一定", "肯定", "会好的", "没问题", "能行", "可以",
                    "未来", "明天", "梦想", "目标", "理想", "愿望"
                ],
                "regex": [
                    r"加.*油", r"相.*信", r"希.*望", r"一.*定",
                    r"肯.*定", r"没.*问.*题", r"能.*行"
                ],
                "emojis": ["💪", "🌟", "✨", "🌈", "🎯", "🚀", "💫"],
                "base_score": 5.5,
                "priority": 0,
                "position_bonus": 1.1,
                "category": "hope"
            },

            "gratitude": {
                "keywords": [
                    "谢谢", "感谢", "辛苦了", "多谢", "感谢", "谢啦",
                    "thank", "thanks", "感激", "拜托", "麻烦", "不好意思"
                ],
                "regex": [
                    r"谢.*谢", r"感.*谢", r"辛.*苦", r"多.*谢",
                    r"拜.*托", r"麻.*烦"
                ],
                "emojis": ["🙏", "🙌", "💐", "🎁", "❤️", "🤝"],
                "base_score": 5.0,
                "priority": 0,
                "position_bonus": 1.0,
                "category": "gratitude"
            },

            "confusion": {
                "keywords": [
                    "不懂", "不理解", "为什么", "怎么回事", "啥", "什么",
                    "搞不懂", "不知道", "不明白", "疑问", "疑惑", "困惑",
                    "how", "why", "what", "怎么", "如何"
                ],
                "regex": [
                    r"不.*懂", r"不.*理.*解", r"为.*什.*么", r"怎.*么.*回.*事",
                    r"搞.*不.*懂", r"不.*明.*白"
                ],
                "emojis": ["🤔", "❓", "❓", "🤷", "🤷‍♂️", "🤷‍♀️"],
                "base_score": 4.5,
                "priority": 0,
                "position_bonus": 1.0,
                "category": "confusion"
            },

            "excitement": {
                "keywords": [
                    "太棒了", "激动", "开心", "快乐", "兴奋", "爽", "爽了",
                    "厉害", "牛", "牛逼", "666", "强", "强啊", "太强了",
                    "happy", "joy", "太好了", "太开心了", "太爽了"
                ],
                "regex": [
                    r"太.*棒", r"激.*动", r"开.*心", r"快.*乐",
                    r"爽.*了", r"牛.*逼", r"666", r"太.*好", r"太.*强"
                ],
                "emojis": ["🎉", "🎊", "🥳", "😄", "😁", "🤩", "✨", "🌟"],
                "base_score": 6.5,
                "priority": 0,
                "position_bonus": 1.2,
                "category": "excitement"
            },

            "disappointment": {
                "keywords": [
                    "失望", "没意思", "无聊", "没劲", "没趣", "没意思",
                    "算了", "算了算了", "无所谓", "不在乎", "随便", "随便吧",
                    "没劲", "没意思", "没趣", "没意思"
                ],
                "regex": [
                    r"失.*望", r"没.*意.*思", r"无.*聊", r"没.*劲",
                    r"算.*了", r"无.*所.*谓", r"随.*便"
                ],
                "emojis": ["😑", "😒", "🙄", "😞", "😔", "💔"],
                "base_score": 4.5,
                "priority": 0,
                "position_bonus": 1.0,
                "category": "disappointment"
            },

            "pride": {
                "keywords": [
                    "骄傲", "自豪", "厉害", "牛", "牛逼", "强", "强啊",
                    "太强了", "太厉害了", "太牛了", "太牛逼了", "太骄傲了",
                    "awesome", "great", "amazing", "excellent"
                ],
                "regex": [
                    r"骄.*傲", r"自.*豪", r"厉.*害", r"牛.*逼",
                    r"太.*强", r"太.*牛", r"太.*厉.*害"
                ],
                "emojis": ["🏆", "🥇", "🌟", "✨", "💪", "🎖️"],
                "base_score": 6.0,
                "priority": 0,
                "position_bonus": 1.2,
                "category": "pride"
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

    def analyze(self, text: str, user_id: Optional[str] = None, enable_negation: bool = True) -> Tuple[Optional[str], float]:
        start_time = time.time()
        self.stats["total_analyzed"] += 1
        
        result = self._analyze_advanced(text, user_id, enable_negation)
        
        elapsed = time.time() - start_time
        self.stats["avg_time"] = (
            self.stats["avg_time"] * (self.stats["total_analyzed"] - 1) + elapsed
        ) / self.stats["total_analyzed"]
        
        return result.tag, result.score

    def _analyze_advanced(self, text: str, user_id: Optional[str], enable_negation: bool) -> AnalysisResult:
        text_lower = text.lower()
        text_len = len(text)
        
        final_scores = {tag: 0.0 for tag in self.EMOTION_NODES}
        max_priorities = {tag: 0 for tag in self.EMOTION_NODES}
        match_details = defaultdict(list)
        
        global_boost = self._calculate_global_boost(text)
        question_penalty = self._calculate_question_penalty(text)
        text_norm_factor = self._calculate_text_length_norm(text_len)
        
        # 应用用户个性化权重
        user_weight_multiplier = self._get_user_weight_multiplier(user_id, text)
        
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
                        
                        # 应用用户个性化权重
                        score *= user_weight_multiplier.get(tag, 1.0)
                        
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
                    
                    score *= user_weight_multiplier.get(tag, 1.0)
                    
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
                    score *= user_weight_multiplier.get(tag, 1.0)
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
                "text_norm_factor": text_norm_factor,
                "user_weight_multiplier": user_weight_multiplier
            },
            mixed_emotions=mixed_emotions
        )

    def _get_user_weight_multiplier(self, user_id: Optional[str], text: str) -> Dict[str, float]:
        """获取用户个性化权重乘数"""
        if not user_id or not self.ADVANCED_CONFIG["enable_personalization"]:
            return {}
        
        if user_id not in self.user_preferences:
            return {}
        
        prefs = self.user_preferences[user_id]
        multiplier = {}
        
        for tag, weight in prefs.emotion_weights.items():
            if weight != 1.0:
                multiplier[tag] = weight
        
        return multiplier

    def record_feedback(self, text: str, predicted_tag: str, correct_tag: Optional[str], user_id: Optional[str] = None):
        """记录用户反馈"""
        record = FeedbackRecord(
            text=text,
            predicted_tag=predicted_tag,
            correct_tag=correct_tag,
            timestamp=time.time(),
            user_id=user_id
        )
        
        self.feedback_records.append(record)
        self.stats["feedback_count"] += 1
        
        # 触发学习更新
        if len(self.feedback_records) >= self.ADVANCED_CONFIG["feedback_threshold"]:
            self._update_weights_from_feedback()
        
        # 更新用户偏好
        if user_id and correct_tag:
            self._update_user_preferences(user_id, text, correct_tag)
        
        # 保存反馈
        self._save_feedback()

    def _update_weights_from_feedback(self):
        """根据反馈更新权重"""
        if not self.ADVANCED_CONFIG["enable_learning"]:
            return
        
        learning_rate = self.ADVANCED_CONFIG["learning_rate"]
        max_adjustment = self.ADVANCED_CONFIG["max_weight_adjustment"]
        
        # 统计每个标签的反馈
        feedback_stats = defaultdict(lambda: {"correct": 0, "wrong": 0})
        
        for record in self.feedback_records[-100:]:  # 只用最近100条
            if record.correct_tag:
                if record.predicted_tag == record.correct_tag:
                    feedback_stats[record.correct_tag]["correct"] += 1
                else:
                    feedback_stats[record.predicted_tag]["wrong"] += 1
        
        # 更新基础分数
        for tag, stats in feedback_stats.items():
            if tag not in self.EMOTION_NODES:
                continue
            
            total = stats["correct"] + stats["wrong"]
            if total == 0:
                continue
            
            accuracy = stats["correct"] / total
            
            # 准确率高则增加权重，准确率低则降低权重
            adjustment = (accuracy - 0.5) * 2 * learning_rate
            adjustment = max(min(adjustment, max_adjustment), -max_adjustment)
            
            self.EMOTION_NODES[tag]["base_score"] = max(
                self.EMOTION_NODES[tag]["base_score"] * (1 + adjustment),
                1.0  # 最小值为1.0
            )
        
        self.stats["learning_updates"] += 1
        self._save_emotion_nodes()

    def _update_user_preferences(self, user_id: str, text: str, correct_tag: str):
        """更新用户偏好"""
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = UserPreferences(user_id=user_id)
        
        prefs = self.user_preferences[user_id]
        prefs.last_active = time.time()
        prefs.total_interactions += 1
        
        # 更新情感权重
        if correct_tag not in prefs.emotion_weights:
            prefs.emotion_weights[correct_tag] = 1.0
        
        # 增加该情感的权重
        prefs.emotion_weights[correct_tag] = min(
            prefs.emotion_weights[correct_tag] + 0.05,
            2.0  # 最大2.0倍
        )
        
        # 记录常用短语
        if len(text) <= 20:
            prefs.common_phrases[text] = correct_tag
        
        self._save_user_preferences()

    def _load_feedback(self):
        """加载反馈记录"""
        if not self.feedback_file.exists():
            return
        
        try:
            with open(self.feedback_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.feedback_records = [
                    FeedbackRecord(**record) for record in data
                ]
        except Exception as e:
            print(f"加载反馈记录失败: {e}")

    def _save_feedback(self):
        """保存反馈记录"""
        try:
            data = [
                {
                    "text": r.text,
                    "predicted_tag": r.predicted_tag,
                    "correct_tag": r.correct_tag,
                    "timestamp": r.timestamp,
                    "user_id": r.user_id,
                    "confidence": r.confidence
                }
                for r in self.feedback_records[-500:]  # 只保留最近500条
            ]
            with open(self.feedback_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存反馈记录失败: {e}")

    def _load_user_preferences(self):
        """加载用户偏好"""
        if not self.preferences_file.exists():
            return
        
        try:
            with open(self.preferences_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for user_id, prefs_data in data.items():
                    self.user_preferences[user_id] = UserPreferences(
                        user_id=user_id,
                        emotion_weights=prefs_data.get("emotion_weights", {}),
                        common_phrases=prefs_data.get("common_phrases", {}),
                        last_active=prefs_data.get("last_active", 0.0),
                        total_interactions=prefs_data.get("total_interactions", 0)
                    )
        except Exception as e:
            print(f"加载用户偏好失败: {e}")

    def _save_user_preferences(self):
        """保存用户偏好"""
        try:
            data = {
                user_id: {
                    "emotion_weights": prefs.emotion_weights,
                    "common_phrases": prefs.common_phrases,
                    "last_active": prefs.last_active,
                    "total_interactions": prefs.total_interactions
                }
                for user_id, prefs in self.user_preferences.items()
            }
            with open(self.preferences_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存用户偏好失败: {e}")

    def _save_emotion_nodes(self):
        """保存情感节点（可选，用于持久化学习结果）"""
        nodes_file = self.data_dir / "emotion_nodes.json"
        try:
            with open(nodes_file, 'w', encoding='utf-8') as f:
                json.dump(self.EMOTION_NODES, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存情感节点失败: {e}")

    def _calculate_global_boost(self, text: str) -> float:
        boost = 1.0
        
        if "!" in text or "！" in text:
            boost += 0.2
        if "..." in text or "…" in text:
            boost += 0.1
        if self.re_repeat_chars.search(text):
            boost += 0.3
        
        return boost

    def _calculate_question_penalty(self, text: str) -> float:
        if self.re_question.search(text):
            return 0.4
        return 1.0

    def _calculate_text_length_norm(self, text_len: int) -> float:
        if not self.ADVANCED_CONFIG["enable_text_length_norm"]:
            return 1.0
        
        if text_len < 10:
            return 1.0
        elif text_len < 50:
            return 1.0 - (text_len - 10) * self.ADVANCED_CONFIG["text_length_factor"] * 0.01
        else:
            return 0.6

    def _calculate_position_weight(self, pos: int, text_len: int, bonus: float) -> float:
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
        window_start = max(0, start_idx - self.WINDOW_SIZE)
        window_text = text[window_start:start_idx]
        
        multiplier = 1.0
        
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
        
        if self._is_in_negation_scope(text, start_idx):
            multiplier *= -0.5
        
        return base_score * multiplier * pos_weight

    def _is_in_negation_scope(self, text: str, pos: int) -> bool:
        scope_start = max(0, pos - self.ADVANCED_CONFIG["negation_scope"])
        scope_text = text[scope_start:pos]
        
        return any(neg in scope_text for neg in self.MODIFIERS["negate"]["words"])

    def _calculate_confidence(self, score: float, threshold: float, priority: int) -> float:
        if threshold == 0:
            return 0.0
        
        base_confidence = min((score - threshold) / threshold, 1.0)
        
        if priority == 2:
            base_confidence = min(base_confidence + 0.2, 1.0)
        elif priority == 1:
            base_confidence = min(base_confidence + 0.1, 1.0)
        
        return max(base_confidence, 0.0)

    def _detect_mixed_emotions(self, candidates: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        if len(candidates) < 2:
            return []
        
        total = sum(v for _, v in candidates)
        
        mixed = []
        for tag, score in candidates:
            ratio = score / total
            if ratio > 0.2:
                mixed.append((tag, ratio))
        
        return sorted(mixed, key=lambda x: x[1], reverse=True)[:3]

    def get_analysis_details(self, text: str, user_id: Optional[str] = None, enable_negation: bool = True) -> AnalysisResult:
        return self._analyze_advanced(text, user_id, enable_negation)

    def get_statistics(self) -> Dict[str, any]:
        return {
            "total_analyzed": self.stats["total_analyzed"],
            "avg_time_ms": self.stats["avg_time"] * 1000,
            "feedback_count": self.stats["feedback_count"],
            "learning_updates": self.stats["learning_updates"],
            "user_count": len(self.user_preferences),
            "cache_hit_rate": (
                self.stats["cache_hits"] / self.stats["total_analyzed"]
                if self.stats["total_analyzed"] > 0 else 0
            )
        }

    def reset_statistics(self):
        self.stats = {
            "total_analyzed": 0,
            "cache_hits": 0,
            "avg_time": 0.0,
            "feedback_count": 0,
            "learning_updates": 0
        }

    def get_user_preferences(self, user_id: str) -> Optional[UserPreferences]:
        """获取用户偏好"""
        return self.user_preferences.get(user_id)

    def get_learning_summary(self) -> Dict[str, any]:
        """获取学习总结"""
        if not self.feedback_records:
            return {"message": "暂无反馈数据"}
        
        recent_feedback = self.feedback_records[-50:]
        
        accuracy_stats = defaultdict(lambda: {"correct": 0, "total": 0})
        for record in recent_feedback:
            if record.correct_tag:
                accuracy_stats[record.predicted_tag]["total"] += 1
                if record.predicted_tag == record.correct_tag:
                    accuracy_stats[record.predicted_tag]["correct"] += 1
        
        accuracy_by_tag = {}
        for tag, stats in accuracy_stats.items():
            if stats["total"] > 0:
                accuracy_by_tag[tag] = {
                    "accuracy": stats["correct"] / stats["total"],
                    "total": stats["total"]
                }
        
        return {
            "total_feedback": len(self.feedback_records),
            "recent_feedback": len(recent_feedback),
            "accuracy_by_tag": accuracy_by_tag,
            "learning_updates": self.stats["learning_updates"],
            "active_users": len(self.user_preferences)
        }
