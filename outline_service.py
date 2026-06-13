import re
from textwrap import shorten

from models import PictureBookPage


class OutlineGenerationError(RuntimeError):
    """Raised when source text cannot be converted into a picture-book outline."""


class PictureBookOutlineService:
    DESIGNER_BRIEF = """你是一位世界级的儿童绘本设计师和故事讲述者。

你制作的绘本能根据源素材和目标受众进行调整。
凡事皆有故事，而你要找到最佳的讲述方式。

每一页必须包含以下 4 个部分：
// NARRATIVE GOAL (叙事目标)
// KEY CONTENT (关键内容)
// VISUAL (视觉画面)
// LAYOUT (布局结构)

CRITICAL:
- 避免"标题：副标题"格式，这很 AI 感
- 禁止"不仅仅是 [X]，而是 [Y]"这种废话
- 封底不要用"谢谢观看"，要有设计感的结束语
"""

    def __init__(self, default_page_count: int = 6) -> None:
        self.default_page_count = default_page_count

    def generate_outline(
        self,
        source_text: str,
        page_count: int | None = None,
    ) -> tuple[str, list[PictureBookPage]]:
        cleaned_text = self._clean_text(source_text)
        if not cleaned_text:
            raise OutlineGenerationError("没有可用于生成绘本大纲的文字内容。")

        creative_brief = self._build_creative_brief(cleaned_text)
        requested_page_count = page_count or self.default_page_count
        page_total = max(1, min(requested_page_count, 12))
        chunks = self._split_into_chunks(cleaned_text, page_total)
        title = self._make_title(cleaned_text)

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
            page_title = f"第 {index} 页"
            image_prompt = self._make_image_prompt(
                title=title,
                narration=narration,
                narrative_goal=narrative_goal,
                key_content=key_content,
                visual=visual,
                layout=layout,
                creative_brief=creative_brief,
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

        return title, pages

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

        chunk_count = min(page_count, len(sentences)) or 1
        chunk_size = max(1, (len(sentences) + chunk_count - 1) // chunk_count)
        return [
            " ".join(sentences[index : index + chunk_size])
            for index in range(0, len(sentences), chunk_size)
        ][:chunk_count]

    def _make_title(self, text: str) -> str:
        first_sentence = re.split(r"[。！？!?\.]", text, maxsplit=1)[0].strip()
        if not first_sentence:
            return "我的儿童绘本"
        return shorten(first_sentence, width=24, placeholder="...")

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
    ) -> str:
        return (
            f"{creative_brief}\n\n"
            "Generate one page illustration based on the following structured page plan.\n"
            f"Story title: {title}\n"
            f"// NARRATIVE GOAL: {narrative_goal}\n"
            f"// KEY CONTENT: {key_content}\n"
            f"// VISUAL: {visual}\n"
            f"// LAYOUT: {layout}\n"
            f"Page narration: {narration}\n\n"
            f"Create a children's picture book illustration for the story '{title}'. "
            "Warm soft colors, gentle lighting, whimsical hand-drawn texture, "
            "child-friendly, no visible text, no watermark. Avoid colon-style title "
            "composition and avoid generic AI-looking poster layouts."
        )
