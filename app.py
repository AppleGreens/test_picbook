import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request, send_file, url_for
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

from document_service import DocumentParser
from picture_book_service import PictureBookError, PictureBookService

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "storage" / "uploads"
OUTPUT_DIR = BASE_DIR / "storage" / "outputs"
ALLOWED_EXTENSIONS = DocumentParser.SUPPORTED_EXTENSIONS

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024


INDEX_HTML = """
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <title>AI 儿童绘本生成器</title>
    <style>
      body { font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 40px; background: #fff8ed; color: #3d2b1f; }
      main { max-width: 760px; margin: 0 auto; background: #fff; padding: 32px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,.08); }
      label { display: block; margin-top: 18px; font-weight: 700; }
      textarea, input, select, button { width: 100%; box-sizing: border-box; margin-top: 8px; padding: 12px; border: 1px solid #e5d2b8; border-radius: 10px; font-size: 15px; }
      textarea { min-height: 140px; }
      button { margin-top: 24px; background: #ff9f43; color: #fff; border: 0; font-weight: 700; cursor: pointer; }
      .hint { color: #7a6754; line-height: 1.6; }
      .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
    </style>
  </head>
  <body>
    <main>
      <h1>AI 儿童绘本生成器</h1>
      <p class="hint">可以输入文字，也可以上传 PDF、Word 或 TXT。PDF/Word 会通过 MinerU 解析，PDF 中的图片会开启 OCR。</p>
      <form action="/picture-books" method="post" enctype="multipart/form-data">
        <label>文字描述</label>
        <textarea name="text" placeholder="例如：一只戴红围巾的小狐狸，在月光下的森林里给星星写信"></textarea>

        <label>上传文档（PDF / Word / TXT，可选）</label>
        <input type="file" name="file" accept=".pdf,.doc,.docx,.txt" />

        <div class="grid">
          <div>
            <label>页数</label>
            <select name="page_count">
              <option value="4">4 页</option>
              <option value="6" selected>6 页</option>
              <option value="8">8 页</option>
              <option value="10">10 页</option>
            </select>
          </div>
          <div>
            <label>图片比例</label>
            <select name="aspect_ratio">
              <option value="16:9" selected>16:9</option>
              <option value="1:1">1:1</option>
              <option value="9:16">9:16</option>
              <option value="4:3">4:3</option>
              <option value="3:4">3:4</option>
            </select>
          </div>
          <div>
            <label>图片大小</label>
            <select name="image_size">
              <option value="1k">1k</option>
              <option value="2k" selected>2k</option>
              <option value="4k">4k</option>
            </select>
          </div>
        </div>

        <button type="submit">生成儿童绘本 PDF</button>
      </form>
    </main>
  </body>
</html>
"""

RESULT_HTML = """
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <title>{{ result.title }}</title>
    <style>
      body { font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 40px; background: #fff8ed; color: #3d2b1f; }
      main { max-width: 860px; margin: 0 auto; background: #fff; padding: 32px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,.08); }
      a.button { display: inline-block; padding: 12px 18px; background: #ff9f43; color: #fff; border-radius: 10px; text-decoration: none; font-weight: 700; }
      li { margin: 12px 0; line-height: 1.6; }
    </style>
  </head>
  <body>
    <main>
      <h1>{{ result.title }}</h1>
      <p>来源：{{ result.source_name }}</p>
      <p><a class="button" href="{{ download_url }}">下载绘本 PDF</a></p>
      <h2>绘本大纲</h2>
      <ol>
        {% for page in result.pages %}
          <li>
            <strong>{{ page.title }}</strong><br />
            // NARRATIVE GOAL {{ page.narrative_goal }}<br />
            // KEY CONTENT {{ page.key_content }}<br />
            // VISUAL {{ page.visual }}<br />
            // LAYOUT {{ page.layout }}<br />
            {{ page.narration }}
          </li>
        {% endfor %}
      </ol>
      <p><a href="/">继续生成新的绘本</a></p>
    </main>
  </body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(INDEX_HTML)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/picture-books")
def create_picture_book_api():
    try:
        result = _create_picture_book_from_request()
    except PictureBookError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(_serialize_result(result))


@app.post("/picture-books")
def create_picture_book_page():
    try:
        result = _create_picture_book_from_request()
    except PictureBookError as exc:
        return render_template_string(
            "<p>生成失败：{{ error }}</p><p><a href='/'>返回</a></p>",
            error=str(exc),
        ), 400

    return render_template_string(
        RESULT_HTML,
        result=result,
        download_url=url_for("download_picture_book", job_id=result.job_id),
    )


@app.get("/api/picture-books/<job_id>/download")
def download_picture_book(job_id: str):
    pdf_path = OUTPUT_DIR / f"{job_id}.pdf"
    if not pdf_path.exists():
        return jsonify({"error": "绘本 PDF 不存在或已被清理。"}), 404
    return send_file(pdf_path, as_attachment=True, download_name=f"{job_id}.pdf")


def _create_picture_book_from_request():
    text = (request.form.get("text") or "").strip()
    uploaded_file = request.files.get("file")
    aspect_ratio = request.form.get("aspect_ratio") or "16:9"
    image_size = request.form.get("image_size") or "2k"
    page_count = _parse_page_count(request.form.get("page_count"))

    if uploaded_file and uploaded_file.filename:
        saved_path = _save_upload(uploaded_file)
        service = PictureBookService(output_dir=OUTPUT_DIR, upload_dir=UPLOAD_DIR)
        return service.create_from_file(
            saved_path,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            page_count=page_count,
        )

    if text:
        service = PictureBookService(output_dir=OUTPUT_DIR, upload_dir=UPLOAD_DIR)
        return service.create_from_text(
            text,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            page_count=page_count,
        )

    raise PictureBookError("请填写文字描述或上传一个文档。")


def _save_upload(uploaded_file) -> Path:
    filename = secure_filename(uploaded_file.filename or "")
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise PictureBookError("仅支持 PDF、Word（.doc/.docx）和 TXT 文件。")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{extension}"
    uploaded_file.save(saved_path)
    return saved_path


def _parse_page_count(raw_page_count: str | None) -> int:
    try:
        return max(1, min(int(raw_page_count or "6"), 12))
    except ValueError:
        return 6


def _serialize_result(result):
    return {
        "job_id": result.job_id,
        "title": result.title,
        "source_name": result.source_name,
        "download_url": url_for(
            "download_picture_book",
            job_id=result.job_id,
            _external=False,
        ),
        "pages": [
            {
                "page_number": page.page_number,
                "title": page.title,
                "narration": page.narration,
                "image_prompt": page.image_prompt,
                "narrative_goal": page.narrative_goal,
                "key_content": page.key_content,
                "visual": page.visual,
                "layout": page.layout,
            }
            for page in result.pages
        ],
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
