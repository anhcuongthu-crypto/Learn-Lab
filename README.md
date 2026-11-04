# LearnLab
Ứng dụng học tập gamified, responsive, có tài khoản, khóa học, bài học, câu hỏi, XP, streak, trái tim, bảng xếp hạng và trang quản trị tự tạo nội dung.

## Chạy local
Python 3.10+:
```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```
Mở http://127.0.0.1:5000

## Deploy Render
1. Tải toàn bộ thư mục lên GitHub repository.
2. Render → New → Blueprint → kết nối repository.
3. Render đọc `render.yaml`, tạo web và PostgreSQL.
4. Đặt biến `ADMIN_EMAIL` thành email sẽ dùng đăng ký tài khoản admin.
5. Deploy, sau đó đăng ký bằng email đó.

Trong trang Quản trị, tạo khóa học, bài học, rồi câu hỏi. Các lựa chọn trắc nghiệm phân cách bằng dấu `|`.
