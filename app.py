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
REFERENCE_PHOTO_DIR = BASE_DIR / "storage" / "reference_photos"
ALLOWED_EXTENSIONS = DocumentParser.SUPPORTED_EXTENSIONS
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

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
      main { max-width: 1180px; margin: 0 auto; background: #fff; padding: 32px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,.08); }
      label { display: block; margin-top: 18px; font-weight: 700; }
      textarea, input, select, button { width: 100%; box-sizing: border-box; margin-top: 8px; padding: 12px; border: 1px solid #e5d2b8; border-radius: 10px; font-size: 15px; }
      textarea { min-height: 140px; }
      button { margin-top: 24px; background: #ff9f43; color: #fff; border: 0; font-weight: 700; cursor: pointer; }
      button:disabled { background: #c9b8a4; cursor: not-allowed; }
      .hint { color: #7a6754; line-height: 1.6; }
      .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
      .content-grid { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(320px, .8fr); gap: 28px; align-items: start; }
      .progress-panel { position: sticky; top: 24px; min-height: 520px; border: 1px dashed #ead8bf; border-radius: 18px; padding: 24px; background: #fffbf5; }
      .progress-panel h2 { margin-top: 0; }
      .progress-track { height: 14px; overflow: hidden; background: #f2dfc7; border-radius: 999px; }
      .progress-bar { width: 0%; height: 100%; background: linear-gradient(90deg, #ff9f43, #ffcf70); border-radius: 999px; transition: width .35s ease; }
      .progress-meta { display: flex; justify-content: space-between; margin: 10px 0 20px; color: #7a6754; font-size: 14px; }
      .stage-list { list-style: none; padding: 0; margin: 0; }
      .stage-list li { display: flex; gap: 10px; padding: 10px 0; color: #9b856f; border-bottom: 1px solid #f1e4d3; }
      .stage-list li.active { color: #3d2b1f; font-weight: 700; }
      .stage-list li.done { color: #4f8a4f; }
      .stage-dot { width: 10px; height: 10px; margin-top: 6px; border-radius: 50%; background: #dac5aa; flex: 0 0 auto; }
      .stage-list li.active .stage-dot { background: #ff9f43; box-shadow: 0 0 0 5px rgba(255,159,67,.18); }
      .stage-list li.done .stage-dot { background: #4f8a4f; }
      .result-box { margin-top: 22px; padding: 16px; border-radius: 14px; background: #fff; border: 1px solid #ecdcc8; line-height: 1.6; }
      .result-box a { color: #d87500; font-weight: 700; }
      .error-box { margin-top: 22px; padding: 16px; border-radius: 14px; background: #fff0f0; color: #9b1c1c; border: 1px solid #f3c0c0; line-height: 1.6; }
      @media (max-width: 900px) {
        body { margin: 20px; }
        .content-grid { grid-template-columns: 1fr; }
        .progress-panel { position: static; min-height: auto; }
      }
    </style>
  </head>
  <body>
    <main>
      <h1>AI 儿童绘本生成器</h1>
      <p class="hint">可以输入文字，也可以上传 PDF、Word 或 TXT。PDF/Word 会通过 MinerU 解析，PDF 中的图片会开启 OCR。也可以上传孩子或角色照片，让 AI 融入绘本插图。</p>
      <div class="content-grid">
        <form id="picture-book-form" action="/picture-books" method="post" enctype="multipart/form-data">
          <label>文字描述</label>
          <textarea name="text" placeholder="例如：一只戴红围巾的小狐狸，在月光下的森林里给星星写信"></textarea>

          <label>上传文档（PDF / Word / TXT，可选）</label>
          <input type="file" name="file" accept=".pdf,.doc,.docx,.txt" />

          <label>参考照片（可选，可上传孩子或角色照片）</label>
          <input type="file" name="reference_photos" accept=".jpg,.jpeg,.png,.webp" multiple />
          <p class="hint">参考照片会作为角色参考传给图片生成服务，用于把真实人物融入卡通绘本场景。</p>

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

          <button id="generate-button" type="submit">生成儿童绘本 PDF</button>
        </form>

        <aside class="progress-panel" aria-live="polite">
          <h2>生成进度</h2>
          <p class="hint">提交后这里会展示后台处理阶段。文档越长、页数越多，生成时间越长。</p>
          <div class="progress-track">
            <div id="progress-bar" class="progress-bar"></div>
          </div>
          <div class="progress-meta">
            <span id="progress-label">等待开始</span>
            <span id="progress-percent">0%</span>
          </div>
          <ul id="stage-list" class="stage-list">
            <li><span class="stage-dot"></span><span>准备素材和参考照片</span></li>
            <li><span class="stage-dot"></span><span>解析文档 / OCR</span></li>
            <li><span class="stage-dot"></span><span>梳理提示词与生成大纲</span></li>
            <li><span class="stage-dot"></span><span>生成每页绘本插图</span></li>
            <li><span class="stage-dot"></span><span>导出儿童绘本 PDF</span></li>
          </ul>
          <div id="progress-result"></div>
        </aside>
      </div>
    </main>
    <script>
      const form = document.getElementById("picture-book-form");
      const button = document.getElementById("generate-button");
      const progressBar = document.getElementById("progress-bar");
      const progressLabel = document.getElementById("progress-label");
      const progressPercent = document.getElementById("progress-percent");
      const progressResult = document.getElementById("progress-result");
      const stageItems = Array.from(document.querySelectorAll("#stage-list li"));
      const stages = [
        { label: "准备素材和参考照片", percent: 8 },
        { label: "解析文档 / OCR", percent: 24 },
        { label: "梳理提示词与生成大纲", percent: 42 },
        { label: "生成每页绘本插图", percent: 74 },
        { label: "导出儿童绘本 PDF", percent: 92 },
      ];
      let timer = null;

      function escapeHtml(value) {
        return String(value || "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#039;");
      }

      function setProgress(percent, label, stageIndex) {
        progressBar.style.width = `${percent}%`;
        progressPercent.textContent = `${percent}%`;
        progressLabel.textContent = label;
        stageItems.forEach((item, index) => {
          item.classList.toggle("done", index < stageIndex);
          item.classList.toggle("active", index === stageIndex);
        });
      }

      function startProgress() {
        let stageIndex = 0;
        setProgress(stages[0].percent, stages[0].label, 0);
        timer = window.setInterval(() => {
          stageIndex = Math.min(stageIndex + 1, stages.length - 1);
          setProgress(stages[stageIndex].percent, stages[stageIndex].label, stageIndex);
          if (stageIndex === stages.length - 1) {
            window.clearInterval(timer);
            timer = null;
          }
        }, 5500);
      }

      function finishProgress(data) {
        if (timer) {
          window.clearInterval(timer);
          timer = null;
        }
        setProgress(100, "生成完成", stages.length);
        stageItems.forEach((item) => {
          item.classList.add("done");
          item.classList.remove("active");
        });
        const outline = (data.pages || [])
          .map((page) => `<li><strong>${escapeHtml(page.title)}</strong>：${escapeHtml(page.narration)}</li>`)
          .join("");
        progressResult.innerHTML = `
          <div class="result-box">
            <strong>${escapeHtml(data.title || "绘本已生成")}</strong><br />
            <a href="${escapeHtml(data.download_url)}" target="_blank" rel="noopener">下载绘本 PDF</a>
            <ol>${outline}</ol>
          </div>
        `;
      }

      function failProgress(message) {
        if (timer) {
          window.clearInterval(timer);
          timer = null;
        }
        progressResult.innerHTML = `<div class="error-box">生成失败：${escapeHtml(message)}</div>`;
        progressLabel.textContent = "生成失败";
      }

      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        progressResult.innerHTML = "";
        button.disabled = true;
        button.textContent = "正在生成，请稍候...";
        startProgress();

        try {
          const response = await fetch("/api/picture-books", {
            method: "POST",
            body: new FormData(form),
          });
          const data = await response.json();
          if (!response.ok) {
            throw new Error(data.error || "未知错误");
          }
          finishProgress(data);
        } catch (error) {
          failProgress(error.message || "网络请求失败");
        } finally {
          button.disabled = false;
          button.textContent = "生成儿童绘本 PDF";
        }
      });
    </script>
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


@app.get("/reference-photos/<filename>")
def uploaded_reference_photo(filename: str):
    safe_name = secure_filename(filename)
    photo_path = REFERENCE_PHOTO_DIR / safe_name
    if not photo_path.exists():
        return jsonify({"error": "参考照片不存在或已被清理。"}), 404
    return send_file(photo_path)


def _create_picture_book_from_request():
    text = (request.form.get("text") or "").strip()
    uploaded_file = request.files.get("file")
    reference_image_urls = _save_reference_photos(request.files.getlist("reference_photos"))
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
            reference_image_urls=reference_image_urls,
        )

    if text:
        service = PictureBookService(output_dir=OUTPUT_DIR, upload_dir=UPLOAD_DIR)
        return service.create_from_text(
            text,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            page_count=page_count,
            reference_image_urls=reference_image_urls,
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


def _save_reference_photos(uploaded_files) -> list[str]:
    urls: list[str] = []
    REFERENCE_PHOTO_DIR.mkdir(parents=True, exist_ok=True)

    for uploaded_file in uploaded_files:
        if not uploaded_file or not uploaded_file.filename:
            continue

        filename = secure_filename(uploaded_file.filename)
        extension = Path(filename).suffix.lower()
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise PictureBookError("参考照片仅支持 JPG、PNG、WEBP 格式。")

        saved_name = f"{uuid.uuid4().hex}{extension}"
        saved_path = REFERENCE_PHOTO_DIR / saved_name
        uploaded_file.save(saved_path)
        urls.append(
            url_for(
                "uploaded_reference_photo",
                filename=saved_name,
                _external=True,
            )
        )

    return urls


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
