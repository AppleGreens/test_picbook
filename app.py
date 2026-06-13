import os
from io import BytesIO

import gradio as gr
from dotenv import load_dotenv
from PIL import Image

from image_service import ImageServiceError, NanoBananaImageService


load_dotenv()


DEFAULT_STYLE = (
    "children's picture book illustration, warm and soft colors, "
    "gentle lighting, whimsical, hand-drawn texture, highly detailed, no text"
)


def generate_picture_book_image(
    description: str,
    aspect_ratio: str,
    image_size: str,
) -> Image.Image:
    """Generate one picture-book-style image from the user's description."""
    if not description or not description.strip():
        raise gr.Error("请先输入一段绘本画面描述。")

    prompt = f"{description.strip()}\n\nStyle: {DEFAULT_STYLE}"

    try:
        service = NanoBananaImageService()
        result = service.generate_image(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
    except ImageServiceError as exc:
        raise gr.Error(str(exc)) from exc

    return Image.open(BytesIO(result.image_bytes)).convert("RGB")


with gr.Blocks(title="AI 绘本生成器") as demo:
    gr.Markdown(
        """
        # AI 绘本生成器

        输入一段文字描述，生成一张温暖、柔和的绘本风格图片。
        """
    )

    with gr.Row():
        with gr.Column():
            description_input = gr.Textbox(
                label="绘本画面描述",
                placeholder="例如：一只戴红围巾的小狐狸，在月光下的森林里给星星写信",
                lines=5,
            )
            aspect_ratio_input = gr.Dropdown(
                label="图片比例",
                choices=["1:1", "16:9", "9:16", "4:3", "3:4"],
                value=os.getenv("NANO_BANANA_ASPECT_RATIO", "16:9"),
            )
            image_size_input = gr.Dropdown(
                label="图片大小",
                choices=["1k", "2k", "4k"],
                value=os.getenv("NANO_BANANA_IMAGE_SIZE", "2k"),
            )
            generate_button = gr.Button("生成绘本图片", variant="primary")

        image_output = gr.Image(label="生成结果", type="pil")

    generate_button.click(
        fn=generate_picture_book_image,
        inputs=[description_input, aspect_ratio_input, image_size_input],
        outputs=image_output,
    )


if __name__ == "__main__":
    demo.launch()
