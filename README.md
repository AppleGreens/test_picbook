# AI 绘本生成器

一个最简单的 AI 绘本图片生成器示例，使用 Python + Gradio 搭建界面。用户输入一段文字描述后，应用会调用 AI 图片生成接口，生成并展示一张绘本风格图片。

## 项目结构

```text
.
├── app.py              # Gradio 应用入口
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

复制环境变量示例文件，并填写你的 OpenAI API Key：

```bash
cp .env.example .env
```

然后编辑 `.env`：

```bash
OPENAI_API_KEY=your_api_key_here
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

点击「生成绘本图片」，稍等片刻后即可看到生成结果。
