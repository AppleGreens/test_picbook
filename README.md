# AI 儿童绘本生成器

一个最小可用的 AI 儿童绘本生成器后端，使用 Python + Flask。用户可以输入文字，也可以上传 PDF、Word 或 TXT 文档；系统会解析文档内容，生成儿童绘本大纲，调用 Nano Banana Pro 生成每页插图，并导出一本 PDF 绘本。

## 项目结构

```text
.
├── app.py                  # Flask 后端入口
├── document_service.py     # PDF / Word / TXT 文档解析
├── image_service.py        # Nano Banana Pro 图片生成服务
├── mineru_service.py       # MinerU OCR / 文档解析服务
├── models.py               # 数据模型
├── outline_service.py      # 绘本大纲生成
├── pdf_export_service.py   # 绘本 PDF 导出
├── picture_book_service.py # 绘本生成总流程
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量示例
├── .gitignore              # Git 忽略规则
└── README.md               # 使用说明
```

## 功能

- 文档解析：支持 PDF、Word（`.doc` / `.docx`）和 TXT
- OCR：PDF / Word 通过 MinerU 解析，PDF 图片内容会开启 OCR
- 大纲生成：把原文拆成儿童绘本页，并生成每页旁白和图片提示词
- 图片生成：调用 Nano Banana Pro 生成绘本风格插图
- PDF 导出：将封面、插图和旁白合成为一本 PDF 绘本

## 准备环境

建议使用 Python 3.10 或更高版本。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

复制环境变量示例文件，并填写 API Key：

```bash
cp .env.example .env
```

至少需要配置：

```bash
NANO_BANANA_API_KEY=your_api_key_here
MINERU_API_KEY=your_mineru_api_key_here
```

默认接口配置如下，可按需调整：

```bash
NANO_BANANA_BASE_URL=https://api.grsai.com
NANO_BANANA_MODEL=nano-banana-pro
NANO_BANANA_ASPECT_RATIO=16:9
NANO_BANANA_IMAGE_SIZE=2k

MINERU_BASE_URL=https://mineru.net/api/v4
MINERU_MODEL_VERSION=vlm
MINERU_LANGUAGE=ch
```

## 启动应用

```bash
python3 app.py
```

启动后打开：

```text
http://localhost:5000
```

## 使用方式

### 网页方式

打开首页后，可以：

1. 输入文字描述；或
2. 上传 PDF、Word、TXT 文档

然后选择页数、图片比例、图片大小，点击「生成儿童绘本 PDF」。

### API 方式

```bash
curl -X POST http://localhost:5000/api/picture-books \
  -F "text=一只戴红围巾的小狐狸，在月光下的森林里给星星写信" \
  -F "page_count=6" \
  -F "aspect_ratio=16:9" \
  -F "image_size=2k"
```

上传文档：

```bash
curl -X POST http://localhost:5000/api/picture-books \
  -F "file=@story.pdf" \
  -F "page_count=6" \
  -F "aspect_ratio=16:9" \
  -F "image_size=2k"
```

接口返回 `download_url` 后，可访问该地址下载 PDF。

## MinerU 接入说明

本项目使用 MinerU v4 正式 API，并区分两种场景：

### 用户上传本地文件

网页和 `/api/picture-books` 文件上传会走签名上传流程：

1. 调用 `/file-urls/batch` 获取签名上传地址
2. 使用 `PUT` 上传用户文件
3. 轮询 `/extract-results/batch/{batch_id}`
4. 下载解析结果 zip，并读取其中的 `full.md`

### 已有远程文件 URL

如果已经有一个可公网访问的 PDF / Word / TXT 文件 URL，可直接使用
`MinerUOcrService.parse_url()`：

1. 调用 `/extract/task` 创建解析任务
2. 轮询 `/extract/task/{task_id}`
3. 下载解析结果 zip，并读取其中的 `full.md`

注意：MinerU 文档说明 `/extract/task` 不支持直接上传本地文件，所以用户上传文件时必须使用上面的签名上传流程。
