# -*- coding: utf-8 -*-
import re
import time
import json
import math
import threading
import logging
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set, Any
from collections import defaultdict, OrderedDict
from dataclasses import dataclass, field, asdict

# 配置日志
logger = logging.getLogger("AstrbotSentiment")
logging.basicConfig(level=logging.INFO)

# ================= 数据结构定义 =================

@dataclass
class AnalysisResult:
    """情感分析结果"""
    tag: Optional[str]
    score: float
    priority: int
    confidence: float
    intensity: str  # mild, moderate, severe, extreme
    details: Dict[str, Any]
    mixed_emotions: List[Tuple[str, float]]
    context_influence: float = 0.0

@dataclass
class FeedbackRecord:
    """用户反馈记录"""
    text: str
    predicted_tag: str
    correct_tag: Optional[str]
    timestamp: float
    user_id: Optional[str] = None

@dataclass
class UserPreferences:
    """用户偏好"""
    user_id: str
    emotion_weights: Dict[str, float] = field(default_factory=dict)
    last_active: float = 0.0
    total_interactions: int = 0
    common_phrases: Dict[str, str] = field(default_factory=dict)

@dataclass
class ContextMemory:
    """上下文记忆"""
    user_id: str
    emotion_history: List[Tuple[str, float, float]] = field(default_factory=list)
    current_mood: Optional[str] = None
    mood_intensity: float = 0.0
    last_update: float = 0.0

# ================= 基础组件 =================

class ThreadSafeIO:
    """线程安全的文件操作 Mixin (增强版：修复 Windows 原子写入问题)"""
    _io_locks: Dict[str, threading.Lock] = {}
    _global_lock = threading.Lock()

    def _get_lock(self, path: str) -> threading.Lock:
        with self._global_lock:
            if path not in self._io_locks:
                self._io_locks[path] = threading.Lock()
            return self._io_locks[path]

    def save_json(self, path: Path, data: Any):
        """原子性写入 JSON 文件"""
        lock = self._get_lock(str(path))
        with lock:
            temp_path = path.with_suffix('.tmp')
            try:
                # 写入临时文件
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                # 原子替换 (兼容 Windows)
                if os.name == 'nt':
                    if path.exists():
                        try:
                            path.unlink()
                        except PermissionError:
                            pass # 如果被占用则跳过，等待下次
                    try:
                        temp_path.rename(path)
                    except OSError:
                        pass
                else:
                    # Linux/Unix 原子操作
                    temp_path.replace(path)
            except Exception as e:
                logger.error(f"Save JSON failed for {path}: {e}")
                if temp_path.exists():
                    try: temp_path.unlink()
                    except: pass

    def load_json(self, path: Path, default: Any = None) -> Any:
        """线程安全读取 JSON 文件"""
        lock = self._get_lock(str(path))
        with lock:
            if not path.exists():
                return default if default is not None else {}
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Load JSON failed for {path}: {e}")
                return default if default is not None else {}

class LRUCache:
    """线程安全的 LRU 缓存"""
    def __init__(self, capacity: int = 256):
        self.capacity = capacity
        self.cache: OrderedDict = OrderedDict()
        self.lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if key not in self.cache: return None
            self.cache.move_to_end(key)
            return self.cache[key]
    
    def put(self, key: str, value: Any):
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)
    
    def clear(self):
        with self.lock:
            self.cache.clear()

# ================= 主分析器类 =================

class SentimentAnalyzer(ThreadSafeIO):
    
    def __init__(self, data_dir: Optional[Path] = None, cache_size: int = 256):
        # 初始化路径
        self.data_dir = data_dir if data_dir else Path(__file__).parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.files = {
            "emotions": self.data_dir / "emotion_nodes.json",
            "context": self.data_dir / "context_memory.json",
            "feedback": self.data_dir / "feedback.json",
            "preferences": self.data_dir / "user_preferences.json"
        }

        # 初始化配置与数据
        self._init_config()
        self._init_regex()
        self._load_data()
        
        # LRU缓存
        self.cache = LRUCache(capacity=cache_size)

    def _init_config(self):
        """初始化高级配置"""
        self.CONFIG = {
            "enable_segmentation": True,      # 启用智能分句
            "enable_diminishing": True,       # 启用边际效应递减
            "enable_context": True,           # 启用上下文记忆
            "context_window": 10,             # 上下文记忆长度
            "negation_lookback": 12,          # 分句内否定词回溯距离
            "intensity_thresholds": {
                "mild": 3.0, "moderate": 6.0, "severe": 8.5
            }
        }
        
        self.MODIFIERS = {
            "super": {
                "words": ["好", "太", "真", "非常", "超级", "死", "特别", "巨", "极其", "超", "爆", "绝", "顶级", "究极", "狠狠", "完全", "彻底"], 
                "weight": 1.5
            },
            "mid": {
                "words": ["比较", "还", "挺", "蛮", "相当"], 
                "weight": 1.2
            },
            "negate": {
                "words": ["不", "没", "别", "勿", "无", "非", "假", "莫", "未", "否", "禁止"], 
                "weight": -1.0
            }
        }

        # v3.1: 强制肯定词组 (双重否定/习惯用语)
        self.FORCE_POSITIVE = [
            "不得不", "不能不", "怎能不", "难道不", "不至于不", "没毛病", "不错", "没错", "肯定", "一定"
        ]

    def _init_regex(self):
        """预编译正则表达式"""
        # 分句正则：匹配标点符号
        self.re_split_clause = re.compile(r"([，。！？；…\n\t,!.?;~]+)")
        # 提问正则
        self.re_question = re.compile(r"(你|您|特|皇|殿|博).*[?？吗]")
        # v3.1: 反问句检测正则 (难道不...吗)
        self.re_rhetorical = re.compile(r"(难道|怎么会|岂|哪能|怎会).*[?？吗]")
    
    def _load_data(self):
        """加载数据"""
        # 1. 加载情感字典
        emotions_data = self.load_json(self.files["emotions"], default=None)
        if emotions_data:
            self.EMOTION_NODES = emotions_data
        else:
            self.EMOTION_NODES = self._get_default_emotion_nodes()
            self.save_json(self.files["emotions"], self.EMOTION_NODES)
        
        # 预编译正则 + 反模式正则
        for node in self.EMOTION_NODES.values():
            node['compiled_regex'] = [re.compile(p, re.IGNORECASE) for p in node.get('regex', [])]
            # v3.1: 预编译排除项 (Anti-Patterns)
            node['compiled_skip'] = [re.compile(p, re.IGNORECASE) for p in node.get('skip_patterns', [])]

        # 2. 加载上下文与用户数据
        self.context_memory = {k: ContextMemory(**v) for k, v in self.load_json(self.files["context"], {}).items()}
        self.user_preferences = {k: UserPreferences(**v) for k, v in self.load_json(self.files["preferences"], {}).items()}

    # ================= 核心分析逻辑 =================

    def analyze(self, text: str, user_id: Optional[str] = None) -> Tuple[Optional[str], float]:
        """主入口：执行情感分析"""
        if not text:
            return None, 0.0
        
        # 1. 检查缓存
        cache_key = f"{user_id or 'anon'}:{text[:100]}"
        cached_result = self.cache.get(cache_key)
        if cached_result:
            return cached_result.tag, cached_result.score
        
        # 2. 执行核心分析
        result = self._analyze_core(text, user_id)
        
        # 3. 更新上下文
        if self.CONFIG["enable_context"] and user_id:
            self._update_context(user_id, result)
        
        # 4. 写入缓存
        self.cache.put(cache_key, result)
        return result.tag, result.score

    def get_analysis_details(self, text: str, user_id: Optional[str] = None) -> AnalysisResult:
        """获取详细分析结果"""
        return self._analyze_core(text, user_id)

    def _analyze_core(self, text: str, user_id: Optional[str]) -> AnalysisResult:
        text_lower = text.lower()
        
        # A. 智能分句
        segments = self._segment_text(text_lower)
        
        final_scores = defaultdict(float)
        max_priorities = defaultdict(int)
        match_details = defaultdict(list)
        
        # v3.1: 检测是否为反问句 (反问句通常表示强烈肯定)
        is_rhetorical = bool(self.re_rhetorical.search(text))
        
        # B. 遍历情感节点
        for tag, data in self.EMOTION_NODES.items():
            base_score = data['base_score']
            priority = data['priority']
            compiled_skip = data.get('compiled_skip', [])
            
            # --- 关键词匹配 ---
            for kw in data['keywords']:
                if kw not in text_lower: continue
                
                # v3.1: 检查全局黑名单 (如 "笑死" 不应触发 "death")
                if self._check_skip_patterns(text_lower, compiled_skip):
                    continue

                for seg_idx, segment in enumerate(segments):
                    if kw in segment:
                        # 计算修饰符 (核心逻辑)
                        mod_weight = self._calculate_segment_modifier(segment, kw, is_rhetorical)
                        
                        # 边际效应递减
                        count = segment.count(kw)
                        diminishing = (1 + math.log(count)) if self.CONFIG["enable_diminishing"] else count
                        
                        # 位置加成 (越靠后权重越高)
                        pos_bonus = 1.0 + (0.1 * seg_idx / max(len(segments), 1))
                        
                        score = base_score * mod_weight * diminishing * pos_bonus
                        
                        if score > 0.1: # 忽略微小分数
                            final_scores[tag] += score
                            max_priorities[tag] = max(max_priorities[tag], priority)
                            match_details[tag].append(f"{kw}({mod_weight:.1f})")

            # --- 正则匹配 ---
            for pattern in data['compiled_regex']:
                for match in pattern.finditer(text_lower):
                    # v3.1: 正则也要检查反模式
                    if self._check_skip_patterns(match.group(), compiled_skip):
                        continue
                    
                    score = (base_score + 2.0)
                    final_scores[tag] += score
                    max_priorities[tag] = max(max_priorities[tag], priority)
                    match_details[tag].append(f"REGEX:{match.group()[:10]}")

            # --- Emoji 统计 ---
            emoji_score = 0.0
            for emoji in data.get('emojis', []):
                count = text.count(emoji)
                if count > 0:
                    factor = (1 + math.log10(count)) if self.CONFIG["enable_diminishing"] else count
                    emoji_score += base_score * 0.5 * factor
            if emoji_score > 0:
                final_scores[tag] += emoji_score

        # C. 后处理
        if not final_scores:
            return AnalysisResult(None, 0, 0, 0, "mild", {}, [], 0.0)

        # 全局加强 (感叹号)
        global_boost = 1.0 + (0.15 * min(text.count('!'), 3))
        
        # v3.1: 反问句加强，普通疑问句减弱
        if is_rhetorical:
            global_boost *= 1.3
        elif self.re_question.search(text):
            global_boost *= 0.85

        ctx_influence = self._get_context_influence(user_id)
        
        candidates = []
        for k, v in final_scores.items():
            user_w = self._get_user_weight_multiplier(user_id, k)
            final_v = v * global_boost * user_w
            
            # 上下文惯性
            if k in ctx_influence:
                final_v *= (1.0 + ctx_influence[k])
            
            if final_v > 0.5:
                candidates.append((k, final_v, max_priorities[k]))

        if not candidates:
            return AnalysisResult(None, 0, 0, 0, "mild", {}, [], 0.0)

        # 排序：优先高优先级(且分数足够高)，否则按分数
        sorted_candidates = sorted(
            candidates,
            key=lambda x: (x[2] if x[1] > 4.0 else 0, x[1]),
            reverse=True
        )
        
        best_tag, best_score, best_prio = sorted_candidates[0]
        
        # 强度分级
        intensity = "extreme" if best_score > 8.5 else ("severe" if best_score > 6.0 else ("moderate" if best_score > 3.0 else "mild"))
        
        return AnalysisResult(
            tag=best_tag if best_score > 3.0 else None,
            score=best_score,
            priority=best_prio,
            confidence=min(best_score / 12.0, 1.0),
            intensity=intensity,
            details=dict(match_details[best_tag]),
            mixed_emotions=[(t, s) for t, s, _ in candidates if t != best_tag and s > best_score * 0.6],
            context_influence=ctx_influence.get(best_tag, 0.0)
        )

    def _check_skip_patterns(self, text_segment: str, skip_patterns: List[re.Pattern]) -> bool:
        """检查是否命中反模式 (黑名单)"""
        for pattern in skip_patterns:
            if pattern.search(text_segment):
                return True
        return False

    def _calculate_segment_modifier(self, segment: str, keyword: str, is_rhetorical: bool) -> float:
        """v3.1: 计算修饰符 (双重否定 + 反问逻辑)"""
        kw_idx = segment.find(keyword)
        if kw_idx == -1: return 1.0
        
        pre_text = segment[:kw_idx]
        if not pre_text: return 1.0
        
        multiplier = 1.0
        lookback = self.CONFIG["negation_lookback"]
        
        # 1. 强制肯定词组
        for pos_phrase in self.FORCE_POSITIVE:
            if pos_phrase in pre_text:
                return 1.3 
        
        # 2. 统计否定词数量
        neg_count = 0
        for neg_word in self.MODIFIERS["negate"]["words"]:
            idx = pre_text.rfind(neg_word)
            if idx != -1 and (len(pre_text) - idx) <= lookback:
                neg_count += 1
        
        # 奇数否定翻转，偶数否定(双重否定)加强
        if neg_count % 2 == 1:
            multiplier *= -1.0
        else:
            if neg_count > 0: multiplier *= 1.2
        
        # 3. 反问句翻转逻辑 (反问+否定 = 强烈肯定)
        if is_rhetorical and multiplier < 0:
            multiplier *= -1.5
        
        # 4. 程度副词
        found_mods = set()
        for mod_type, data in self.MODIFIERS.items():
            if mod_type == "negate": continue
            for word in data["words"]:
                if word in pre_text and word not in found_mods:
                    multiplier *= data["weight"]
                    found_mods.add(word)
                    break
                    
        return multiplier

    def _segment_text(self, text: str) -> List[str]:
        parts = self.re_split_clause.split(text)
        return [p for p in parts if p and not self.re_split_clause.match(p)]

    # ================= 上下文系统 =================

    def _get_context_influence(self, user_id: Optional[str]) -> Dict[str, float]:
        if not user_id or user_id not in self.context_memory: return {}
        ctx = self.context_memory[user_id]
        if not ctx.current_mood: return {}
        
        # 平滑衰减 (10分钟)
        elapsed_mins = (time.time() - ctx.last_update) / 60.0
        if elapsed_mins > 10: return {}
        
        decay_factor = max(0, 1.0 - (elapsed_mins / 10.0))
        return {ctx.current_mood: 0.2 * decay_factor}

    def _update_context(self, user_id: str, result: AnalysisResult):
        if user_id not in self.context_memory:
            self.context_memory[user_id] = ContextMemory(user_id=user_id)
        ctx = self.context_memory[user_id]
        now = time.time()
        
        if result.tag:
            ctx.current_mood = result.tag
            ctx.mood_intensity = result.score
            ctx.emotion_history.append((result.tag, result.score, now))
        
        ctx.last_update = now
        if len(ctx.emotion_history) > self.CONFIG["context_window"]:
            ctx.emotion_history.pop(0)
            
        threading.Thread(target=self._save_context_async, args=(user_id,)).start()

    def _save_context_async(self, user_id: str):
        data = {uid: asdict(mem) for uid, mem in self.context_memory.items()}
        self.save_json(self.files["context"], data)

    def _get_user_weight_multiplier(self, user_id: Optional[str], tag: str) -> float:
        if not user_id or user_id not in self.user_preferences: return 1.0
        return self.user_preferences[user_id].emotion_weights.get(tag, 1.0)

    # ================= 全量词库 (v3.1: 恢复所有节点 + 添加反模式) =================

    def _get_default_emotion_nodes(self) -> Dict:
        return {
            "morning": {
                "keywords": ["早安", "早上好", "早啊", "哦哈哟", "早", "启动", "醒了", "起飞", "morning", "hi", "哈喽", "你好", "您好", "早上", "刚醒", "困死", "睁眼", "提神", "咖啡", "打卡"],
                "regex": [r"早$", r"早.*好", r"^早", r"morning"],
                "emojis": ["🌅", "☕", "🐔", "☀️", "👋", "🥪", "🥛"],
                "base_score": 6.0, "priority": 0, "category": "greeting"
            },
            "sanity": {
                "keywords": ["晚安", "睡了", "睡觉", "累", "休息", "困", "休眠", "下班", "午睡", "躺平", "歇会", "乏", "倦", "挂机", "理智", "碎石", "吃石头", "搓玉", "肝", "1-7", "刷材料", "长草", "基建", "排班", "换班", "清理智", "剿灭", "代理", "加班", "猝死", "通宵", "熬夜", "做题", "赶ddl", "开会", "摸鱼", "不想动", "瘫", "累死"],
                "regex": [r"(去|要|想)睡", r"好{0,2}累", r"困.*死", r"眼.*睁不开", r"肝.*疼", r"理.*智.*(无|没|光|0)", r"下.*班", r"晚.*安"],
                "skip_patterns": ["理智.*(恢复|满|多)", "不.*(累|困|想睡)", "精神", "没.*睡", "不下班"],
                "emojis": ["💤", "🌙", "🛌", "🥱", "😪", "🌃", "🔋", "🪫"],
                "base_score": 6.0, "priority": 0, "category": "fatigue"
            },
            "dont_cry": {
                "keywords": ["痛苦", "想哭", "难受", "伤心", "悲伤", "流泪", "哭", "破防", "崩溃", "甚至想笑", "emo", "呜", "玉玉", "地狱", "寄", "似了", "裂开", "麻了", "小丑", "红温", "心态崩", "致郁", "刀", "发病", "遗憾", "唉", "叹气"],
                "regex": [r"好{0,2}(痛|苦)", r"呜{3,}", r"不想.*活", r"心.*态.*崩", r"破.*大.*防", r"救.*我", r"笑.*不.*出.*来"],
                "skip_patterns": ["笑死", "高兴死", "爽死", "乐死", "开心死", "笑不活", "打死", "死耗子"], 
                "emojis": ["😭", "😢", "💔", "🥀", "💧", "🌧️", "😿", "😞", "🩸"],
                "base_score": 7.5, "priority": 1, "category": "sadness"
            },
            "comfort": {
                "keywords": ["救命", "害怕", "恐怖", "吓人", "委屈", "怕", "阴间", "噩梦", "鬼", "焦虑", "紧张", "压力", "窒息", "慌", "help", "sos", "不敢", "发抖", "吓死"],
                "regex": [r"被.*吓", r"好{0,2}怕", r"救.*命", r"吓.*死", r"别.*吓.*我", r"帮.*帮.*我"],
                "skip_patterns": ["不可怕", "没那么怕", "不吓人"],
                "emojis": ["😱", "😨", "😖", "🆘", "👻", "🧟", "🕷️", "😰"],
                "base_score": 8.0, "priority": 2, "category": "fear"
            },
            "fail": {
                "keywords": ["失败", "输了", "白给", "如果", "假如", "后悔", "菜", "弱", "沉船", "保底", "蓝天白云", "紫气东来", "潜能", "歪了", "漏怪", "代理失误", "演我", "丝血", "翻车", "手残", "脑溢血", "血压", "下饭", "操作变形", "打不过", "卡关"],
                "regex": [r"打.*不过", r"过.*不去", r"输.*了", r"高.*血.*压", r"抽.*不.*到", r"歪.*了"],
                "emojis": ["🏳️", "💀", "👎", "🤡", "📉", "💩"],
                "base_score": 6.0, "priority": 0, "category": "failure"
            },
            "company": {
                "keywords": ["孤独", "寂寞", "没人", "一个人", "无聊", "冷清", "理我", "自闭", "孤单", "落寞", "空虚", "没人爱", "孤寡", "只有你", "陪我", "聊聊", "说话"],
                "regex": [r"理.*我", r"在.*吗", r"没.*人", r"一.*个.*人", r"陪.*陪.*我"],
                "emojis": ["🍃", "🍂", "🪹", "😶", "🌫️", "🚶"],
                "base_score": 5.0, "priority": 0, "category": "loneliness"
            },
            "trust": {
                "keywords": ["老婆", "特雷西娅", "殿下", "皇女", "特蕾西娅", "女王", "抱抱", "贴贴", "喜欢", "爱", "太强", "厉害", "想你", "亲亲", "结婚", "戒指", "羁绊", "想念", "心动", "可爱", "温柔", "天使", "妈妈", "我爱你", "love", "凯尔希", "阿米娅", "博士"],
                "regex": [r"最.*喜欢", r"爱.*你", r"想.*你", r"结.*婚", r"老.*婆", r"贴.*贴", r"抱.*抱"],
                "emojis": ["❤️", "🥰", "🤗", "😘", "💍", "🌹", "✨", "😻", "💕"],
                "base_score": 5.0, "priority": 0, "category": "affection"
            },
            "poke": {
                "keywords": ["戳", "揉", "摸", "捣", "rua", "捏", "敲", "拍", "摸摸", "摸头", "把玩", "指指点点"],
                "regex": [r"戳.*戳", r"摸.*摸"],
                "emojis": ["👈", "👆", "🤏", "👋"],
                "base_score": 4.0, "priority": 0, "category": "interaction"
            },
            "anger": {
                "keywords": ["生气", "愤怒", "火大", "烦", "烦死了", "滚", "滚蛋", "讨厌", "恶心", "暴躁", "炸了", "气死", "无语", "靠", "操", "tmd", "tm", "cnm", "愤怒", "怒", "恼火", "不爽", "不爽"],
                "regex": [r"好{0,2}(烦|气|怒)", r"烦.*死", r"气.*死", r"炸.*了", r"滚.*蛋", r"无.*语", r"不.*爽"],
                "skip_patterns": ["不生气", "没生气", "不烦", "别烦", "消消气"],
                "emojis": ["😡", "😤", "🤬", "💢", "💥", "🔥", "👊"],
                "base_score": 7.0, "priority": 1, "category": "anger"
            },
            "surprise": {
                "keywords": ["哇", "天哪", "天啊", "震惊", "惊讶", "意外", "没想到", "真的吗", "不会吧", "居然", "竟然", "难以置信", "wow", "omg", "天", "啊", "诶", "咦"],
                "regex": [r"哇{2,}", r"天.*哪", r"天.*啊", r"震.*惊", r"意.*外", r"没.*想.*到", r"居然", r"竟然"],
                "emojis": ["😲", "😮", "😯", "🤯", "😱", "😳", "🙀"],
                "base_score": 5.5, "priority": 0, "category": "surprise"
            },
            "hope": {
                "keywords": ["期待", "加油", "相信", "希望", "努力", "坚持", "奋斗", "一定", "肯定", "会好的", "没问题", "能行", "可以", "未来", "明天", "梦想", "目标", "理想", "愿望"],
                "regex": [r"加.*油", r"相.*信", r"希.*望", r"一.*定", r"肯.*定", r"没.*问.*题", r"能.*行"],
                "emojis": ["💪", "🌟", "✨", "🌈", "🎯", "🚀", "💫"],
                "base_score": 5.5, "priority": 0, "category": "hope"
            },
            "gratitude": {
                "keywords": ["谢谢", "感谢", "辛苦了", "多谢", "感谢", "谢啦", "thank", "thanks", "感激", "拜托", "麻烦", "不好意思"],
                "regex": [r"谢.*谢", r"感.*谢", r"辛.*苦", r"多.*谢", r"拜.*托", r"麻.*烦"],
                "emojis": ["🙏", "🙌", "💐", "🎁", "❤️", "🤝"],
                "base_score": 5.0, "priority": 0, "category": "gratitude"
            },
            "confusion": {
                "keywords": ["不懂", "不理解", "为什么", "怎么回事", "啥", "什么", "搞不懂", "不知道", "不明白", "疑问", "疑惑", "困惑", "how", "why", "what", "怎么", "如何"],
                "regex": [r"不.*懂", r"不.*理.*解", r"为.*什.*么", r"怎.*么.*回.*事", r"搞.*不.*懂", r"不.*明.*白"],
                "emojis": ["🤔", "❓", "❓", "🤷", "🤷‍♂️", "🤷‍♀️"],
                "base_score": 4.5, "priority": 0, "category": "confusion"
            },
            "excitement": {
                "keywords": ["太棒了", "激动", "开心", "快乐", "兴奋", "爽", "爽了", "厉害", "牛", "牛逼", "666", "强", "强啊", "太强了", "happy", "joy", "太好了", "太开心了", "太爽了", "好似", "笑死", "笑不活"],
                "regex": [r"太.*棒", r"激.*动", r"开.*心", r"快.*乐", r"爽.*了", r"牛.*逼", r"666", r"太.*好", r"太.*强"],
                "emojis": ["🎉", "🎊", "🥳", "😄", "😁", "🤩", "✨", "🌟"],
                "base_score": 6.5, "priority": 0, "category": "excitement"
            },
            "disappointment": {
                "keywords": ["失望", "没意思", "无聊", "没劲", "没趣", "没意思", "算了", "算了算了", "无所谓", "不在乎", "随便", "随便吧"],
                "regex": [r"失.*望", r"没.*意.*思", r"无.*聊", r"没.*劲", r"算.*了", r"无.*所.*谓", r"随.*便"],
                "emojis": ["😑", "😒", "🙄", "😞", "😔", "💔"],
                "base_score": 4.5, "priority": 0, "category": "disappointment"
            },
            "pride": {
                "keywords": ["骄傲", "自豪", "厉害", "牛", "牛逼", "强", "强啊", "太强了", "太厉害了", "太牛了", "太牛逼了", "太骄傲了", "awesome", "great", "amazing", "excellent"],
                "regex": [r"骄.*傲", r"自.*豪", r"厉.*害", r"牛.*逼", r"太.*强", r"太.*牛", r"太.*厉.*害"],
                "emojis": ["🏆", "🥇", "🌟", "✨", "💪", "🎖️"],
                "base_score": 6.0, "priority": 0, "category": "pride"
            }
        }

# ================= 测试入口 =================
if __name__ == "__main__":
    analyzer = SentimentAnalyzer()
    
    # 测试案例覆盖多种情况
    cases = [
        "我今天真的好累啊，不想加班了",       # 普通 - sanity
        "不得不说，这游戏真好玩",             # 强制肯定 - excitement
        "难道特雷西娅不可爱吗？",             # 反问+否定 - affection
        "笑死我了，这什么操作",               # 反模式 (not death) - excitement
        "我不是不相信你",                     # 双重否定 - trust
        "虽然很难过，但看到你我就开心了",       # 分句权重 - excitement (后半句权重高)
        "😭😭😭😭😭😭😭",                     # 边际效应 - dont_cry (分数抑制)
        "理智归零了，去睡了"                  # 领域黑话 - sanity
    ]
    
    print(f"{'Text':<30} | {'Tag':<10} | {'Score'}")
    print("-" * 55)
    for t in cases:
        tag, score = analyzer.analyze(t, "test_user")
        print(f"{t[:30]:<30} | {str(tag):<10} | {score:.1f}")