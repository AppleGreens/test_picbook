import re
from textwrap import shorten

from models import CharacterProfile, PictureBookPage


class OutlineGenerationError(RuntimeError):
    """Raised when source text cannot be converted into a picture-book outline."""


class PictureBookOutlineService:
    OUTLINE_PROMPT_TEMPLATE = """###生成大纲
你是一位世界级的儿童绘本设计师和故事讲述者。

#### 任务
根据以下文档内容，设计一本 10-15 页的儿童绘本大纲。

#### 文档内容
{document_content}

#### 输出要求
为每一页提供：
1. **标题**：叙事性标题（不是"标题：副标题"格式）
2. **叙事目标**：这一页在故事中的作用
3. **关键内容**：要展示的文字
4. **视觉画面**：场景、角色动作、表情
5. **布局**：构图建议

#### 禁止事项
- 禁止使用"让我们一起..."、"小朋友们..."等说教语气
- 禁止"不仅仅是X，而是Y"等 AI 味道的句式
- 禁止以"谢谢观看"结尾

#### 输出格式
JSON 格式，便于程序解析
"""

    DESIGNER_BRIEF = """用户要求：
用户没有明确要求的，按以上规则细化和生成；用户有明确要求的，按用户要求为准

生成顺序：
第一步，生成大纲
第二步，角色设定
第三步，生成图片

你是一位世界级的儿童绘本设计师和故事讲述者。

你制作的绘本能根据源素材和目标受众进行调整。
凡事皆有故事，而你要找到最佳的讲述方式。

每一页必须包含以下 4 个部分：
NARRATIVE GOAL 叙事目标
KEY CONTENT 关键内容
VISUAL 视觉画面
LAYOUT 布局结构

CRITICAL：
避免"标题：副标题"格式，这很 AI 感
禁止"不仅仅是 X，而是 Y"这种废话
封底不要用"谢谢观看"，要有设计感的结束语
"""

    CHARACTER_REFERENCE_PROMPT_TEMPLATE = """角色设定
创建一张角色设定图（Character Reference Sheet）。

角色信息
名称：{character_name}
描述：{character_description}

设定图要求
1. 展示角色的 3 个角度：正面、3/4 侧面、侧面
2. 展示 3-4 种表情：开心、好奇、惊讶、思考
3. 展示全身和面部特写
4. 使用干净的白色背景
5. 标注关键特征（发色、眼睛颜色、服装细节）

风格
{style}

布局
横向 16:9，像专业的角色设计稿一样排列
"""

    PAGE_IMAGE_PROMPT_TEMPLATE = """图片生成
你是一位专业的儿童绘本插画师。

任务
为绘本的第 {page_number} 页绘制插图。

页面内容
标题：{title}
文字：{content}
场景：{visual}

风格要求
1. {style}
2. 明亮温暖的色调，主色调为橙色、绿色、蓝色
3. 角色有大眼睛、圆润的线条
4. 背景简洁，有柔和的光线
5. 16:9 比例，4K 分辨率

角色一致性（重要！）
主角必须和参考图保持一致：
1. 相同的：脸型、眼睛颜色、发型、服装
2. 可以变化的：姿势、表情、与场景的互动

禁止
1. 禁止出现 Markdown 符号（井号、星号等）
2. 禁止文字模糊不清
3. 禁止风格突变
"""

    DEFAULT_STYLE = "迪士尼皮克斯 3D 动画风格"

    def __init__(self, default_page_count: int = 10) -> None:
        self.default_page_count = default_page_count

    def generate_outline(
        self,
        source_text: str,
        page_count: int | None = None,
    ) -> tuple[str, CharacterProfile, list[PictureBookPage]]:
        cleaned_text = self._clean_text(source_text)
        if not cleaned_text:
            raise OutlineGenerationError("没有可用于生成绘本大纲的文字内容。")

        creative_brief = self._build_creative_brief(cleaned_text)
        requested_page_count = page_count or self.default_page_count
        page_total = max(1, min(requested_page_count, 15))
        chunks = self._split_into_chunks(cleaned_text, page_total)
        title = self._make_title(cleaned_text)
        character_profile = self.generate_character_profile(cleaned_text, title)

        pages: list[PictureBookPage] = []
        for index, chunk in enumerate(chunks, start=1):
            narrative_goal = self._make_narrative_goal(index, len(chunks))
            key_content = self._make_key_content(chunk)
            visual = self._make_visual(chunk, index, len(chunks))
            layout = self._make_layout(index, len(chunks))
            narration = self._make_child_friendly_narration(
                chunk=chunk,
                page_number=index,
                page_count=len(chunks),
            )
            page_title = self._make_page_title(chunk, index, len(chunks))
            image_prompt = self._make_image_prompt(
                title=title,
                narration=narration,
                narrative_goal=narrative_goal,
                key_content=key_content,
                visual=visual,
                layout=layout,
                creative_brief=creative_brief,
                page_number=index,
                style=character_profile.style,
            )
            pages.append(
                PictureBookPage(
                    page_number=index,
                    title=page_title,
                    narration=narration,
                    image_prompt=image_prompt,
                    narrative_goal=narrative_goal,
                    key_content=key_content,
                    visual=visual,
                    layout=layout,
                )
            )

        return title, character_profile, pages

    def generate_character_profile(self, source_text: str, title: str) -> CharacterProfile:
        character_name = self._extract_character_name(source_text, title)
        character_description = self._make_character_description(source_text)
        reference_prompt = self.CHARACTER_REFERENCE_PROMPT_TEMPLATE.format(
            character_name=character_name,
            character_description=character_description,
            style=self.DEFAULT_STYLE,
        )
        return CharacterProfile(
            name=character_name,
            description=character_description,
            style=self.DEFAULT_STYLE,
            reference_prompt=reference_prompt,
        )

    def _build_creative_brief(self, source_text: str) -> str:
        source_summary = shorten(source_text, width=500, placeholder="...")
        return (
            f"{self.DESIGNER_BRIEF}\n"
            "请先理解用户或文档给出的源素材；用户明确提到的角色、场景、情绪、"
            "受众、风格和限制必须优先遵守。未提到的部分使用上述默认要求。\n\n"
            f"源素材摘要：{source_summary}"
        )

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"#+\s*", "", text)
        text = re.sub(r"[*_`>-]+", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _split_into_chunks(self, text: str, page_count: int) -> list[str]:
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[。！？!?\.])\s*", text)
            if sentence.strip()
        ]
        if not sentences:
            sentences = [text]

        chunk_count = max(1, page_count)
        if len(sentences) < chunk_count:
            return [sentences[index % len(sentences)] for index in range(chunk_count)]

        chunk_size = max(1, (len(sentences) + chunk_count - 1) // chunk_count)
        chunks = [
            " ".join(sentences[index : index + chunk_size])
            for index in range(0, len(sentences), chunk_size)
        ][:chunk_count]
        while len(chunks) < chunk_count:
            chunks.append(sentences[len(chunks) % len(sentences)])
        return chunks

    def _make_title(self, text: str) -> str:
        first_sentence = re.split(r"[。！？!?\.]", text, maxsplit=1)[0].strip()
        if not first_sentence:
            return "我的儿童绘本"
        return self._sanitize_title(shorten(first_sentence, width=24, placeholder="..."))

    def _make_page_title(self, chunk: str, page_number: int, page_count: int) -> str:
        title_seed = re.split(r"[。！？!?\.]", chunk, maxsplit=1)[0].strip()
        if not title_seed:
            if page_number == page_count:
                return "光停在最后一页"
            return f"新的发现"
        return self._sanitize_title(shorten(title_seed, width=18, placeholder="..."))

    def _sanitize_title(self, title: str) -> str:
        title = re.sub(r"[：:]\s*", " ", title)
        title = re.sub(r"#+|\*+|`+", "", title)
        return title.strip() or "我的儿童绘本"

    def _extract_character_name(self, text: str, title: str) -> str:
        patterns = [
            r"(?:主角|角色|名字|名称)[：:]\s*([A-Za-z0-9\u4e00-\u9fff]{1,12})",
            r"([A-Za-z0-9\u4e00-\u9fff]{1,12})(?:是一位|是一个|是一只|是个)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        candidates = re.findall(
            r"[\u4e00-\u9fff]{2,6}(?:小朋友|孩子|女孩|男孩|狐狸|兔子|猫|狗|熊|鸟)",
            text,
        )
        if candidates:
            return candidates[0]
        return shorten(title, width=10, placeholder="") or "主角"

    def _make_character_description(self, text: str) -> str:
        source_summary = shorten(text, width=180, placeholder="...")
        return (
            "根据源素材塑造一个适合儿童绘本的主角：大眼睛、圆润轮廓、亲切表情，"
            "服装和发型优先遵守用户或文档中明确提到的要求；若用户上传参考照片，"
            "以参考照片中的脸型、眼睛、发型和服装作为角色一致性依据。"
            f"源素材线索：{source_summary}"
        )

    def _make_child_friendly_narration(
        self,
        chunk: str,
        page_number: int,
        page_count: int,
    ) -> str:
        short_chunk = shorten(chunk, width=90, placeholder="...")
        if page_number == 1:
            return f"故事开始了。{short_chunk}"
        if page_number == page_count:
            return f"故事在一束温柔的光里停下脚步。{short_chunk}"
        return f"接着，新的发现出现了。{short_chunk}"

    def _make_narrative_goal(self, page_number: int, page_count: int) -> str:
        if page_number == 1:
            return "建立故事入口、主角处境和孩子愿意继续翻页的好奇心。"
        if page_number == page_count:
            return "用有余味的方式收束故事，让情感停留在温暖、希望或发现上。"
        return "推动情节前进，让角色在一次具体行动或发现中发生变化。"

    def _make_key_content(self, chunk: str) -> str:
        return shorten(chunk, width=120, placeholder="...")

    def _make_visual(self, chunk: str, page_number: int, page_count: int) -> str:
        key_scene = shorten(chunk, width=80, placeholder="...")
        if page_number == 1:
            return f"开场画面要清楚呈现主角和世界氛围：{key_scene}"
        if page_number == page_count:
            return f"封底式收束画面，有设计感的留白和温暖余韵：{key_scene}"
        return f"以一个清晰、可被儿童理解的动作或发现作为主画面：{key_scene}"

    def _make_layout(self, page_number: int, page_count: int) -> str:
        if page_number == 1:
            return "大幅沉浸式开场构图，主角位于视觉焦点，文字放在安静留白处。"
        if page_number == page_count:
            return "留白更多的收束构图，画面像轻轻合上的书页，避免使用'谢谢观看'。"
        return "插图占页面主体，保留清爽文字区，视觉动线从角色动作引向下一页。"

    def _make_image_prompt(
        self,
        title: str,
        narration: str,
        narrative_goal: str,
        key_content: str,
        visual: str,
        layout: str,
        creative_brief: str,
        page_number: int,
        style: str,
    ) -> str:
        return (
            f"{creative_brief}\n\n"
            f"{self.PAGE_IMAGE_PROMPT_TEMPLATE.format(page_number=page_number, title=title, content=key_content, visual=visual, style=style)}\n"
            "结构化页面计划：\n"
            f"NARRATIVE GOAL：{narrative_goal}\n"
            f"KEY CONTENT：{key_content}\n"
            f"VISUAL：{visual}\n"
            f"LAYOUT：{layout}\n"
            f"Page narration: {narration}\n\n"
            "请严格保持角色一致性。若存在角色设定图或用户上传照片，必须优先参考。"
        )
