import base64
import os
from io import BytesIO
from urllib.request import urlopen

import gradio as gr
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image


load_dotenv()


DEFAULT_STYLE = (
    "children's picture book illustration, warm and soft colors, "
    "gentle lighting, whimsical, hand-drawn texture, highly detailed, no text"
)


def generate_picture_book_image(description: str) -> Image.Image:
    """Generate one picture-book-style image from the user's description."""
    if not description or not description.strip():
        raise gr.Error("请先输入一段绘本画面描述。")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise gr.Error("请先在 .env 中配置 OPENAI_API_KEY。")

    client = OpenAI(api_key=api_key)
    prompt = f"{description.strip()}\n\nStyle: {DEFAULT_STYLE}"

    result = client.images.generate(
        model=os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"),
        prompt=prompt,
        size=os.getenv("OPENAI_IMAGE_SIZE", "1024x1024"),
    )

    image_data = result.data[0]
    if image_data.b64_json:
        image_bytes = base64.b64decode(image_data.b64_json)
    elif image_data.url:
        image_bytes = urlopen(image_data.url, timeout=30).read()
    else:
        raise gr.Error("图片生成成功，但没有收到可显示的图片数据。")

    return Image.open(BytesIO(image_bytes)).convert("RGB")


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
            generate_button = gr.Button("生成绘本图片", variant="primary")

        image_output = gr.Image(label="生成结果", type="pil")

    generate_button.click(
        fn=generate_picture_book_image,
        inputs=description_input,
        outputs=image_output,
    )


if __name__ == "__main__":
    demo.launch()
