# AI 绘本生成器

一个最简单的 AI 绘本图片生成器示例，使用 Python + Gradio 搭建界面。用户输入一段文字描述后，应用会调用 Nano Banana Pro 图片生成接口，生成并展示一张绘本风格图片。

## 项目结构

```text
.
├── app.py              # Gradio 应用入口
├── image_service.py    # Nano Banana Pro 图片生成服务
├── requirements.txt    # Python 依赖
├── .env.example        # 环境变量示例
├── .gitignore          # Git 忽略规则
└── README.md           # 使用说明
```

## 准备环境

建议使用 Python 3.10 或更高版本。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

复制环境变量示例文件，并填写你的 Nano Banana Pro API Key：

```bash
cp .env.example .env
```

然后编辑 `.env`：

```bash
NANO_BANANA_API_KEY=your_api_key_here
```

默认接口配置如下，可按需调整：

```bash
NANO_BANANA_BASE_URL=https://grsai.com
NANO_BANANA_MODEL=nano-banana-pro
NANO_BANANA_ASPECT_RATIO=16:9
NANO_BANANA_IMAGE_SIZE=2k
```

## 启动应用

```bash
python3 app.py
```

启动后，在浏览器中打开 Gradio 显示的本地地址即可使用。

## 使用方式

在输入框中写一段绘本场景描述，例如：

```text
一只戴红围巾的小狐狸，在月光下的森林里给星星写信
```

选择图片比例和图片大小，点击「生成绘本图片」。应用会先提交绘画任务，再轮询结果接口，完成后显示生成图片。
