# 🛠️ THƯ MỤC CÔNG CỤ (TOOLS) - HƯỚNG DẪN SỬ DỤNG

Thư mục này chứa toàn bộ các ứng dụng Web, file chạy 1-Click (`.bat`), và các script tự động hóa hỗ trợ việc đọc truyện, dịch thuật AI thông minh, cào raw và xuất audio.

---

## ⚡ 1. CÁC FILE CHẠY 1-CLICK (TIỆN DỤNG NHẤT)

| File chạy 1-Click | Chức năng | Cách sử dụng |
| :--- | :--- | :--- |
| ⚡ **`1_Cap_Nhat_Web.bat`** | **Đóng gói chương mới vào Web** | Click đúp để tự động quét toàn bộ file trong `translated/` và cập nhật vào `chapters.js` + `index.html`. |
| 📖 **`2_Mo_Web_Doc_Truyen.bat`** | **Mở Web Đọc Truyện** | Click đúp để mở ngay ứng dụng đọc truyện & nghe TTS Chị Google trên máy tính. |
| 📥 **`3_Cao_Raw_Syosetu.bat`** | **Cào Raw Siêu Tốc (Python Engine)** | Click đúp để mở phần mềm cào raw đa luồng, hỗ trợ mọi bộ truyện, tự phát hiện & cập nhật chương mới. |
| 🧠 **`4_Dich_Truyen_AI.bat`** | **Dịch Truyện AI & Tự Học Thuật Ngữ** | Click đúp để dịch truyện đa dự án, hỗ trợ **Tự học Glossary (Cách A)**, **Giao tiếp tinh chỉnh văn phong**, và **Quét trước Glossary (Cách B)**. |
| 🎧 **`5_Xuat_Audio_MP3.bat`** | **Xuất Audio MP3 Offline** | Kéo thả bất kỳ file `.txt` hoặc `.md` nào đè lên file này để tạo audio trong thư mục `audio/`. |

---

## 🌐 2. ỨNG DỤNG WEB & DỮ LIỆU

| Tệp Web / Giao diện | Mô tả chi tiết |
| :--- | :--- |
| 📄 **`Doc_Truyen.html`** | **Ứng dụng chính**: Thư viện truyện đọc & nghe TTS Giọng Chị Google, BGM nhạc nền thư giãn, Đọc văn bản tùy chọn, Dịch raw tự động bằng AI. |
| 📄 **`index.html`** | **Bản sao tự động**: Dùng để tải lên GitHub Pages / Vercel để đọc online mọi lúc mọi nơi bằng 4G/5G. |
| 📄 **`chapters.js`** | **Cơ sở dữ liệu truyện**: Chứa toàn bộ nội dung các chương truyện được tạo tự động bởi `build_chapters_js.ps1`. |

---

## ⚙️ 3. MÃ NGUỒN XỬ LÝ (ENGINES)

| Script Engine | Chức năng |
| :--- | :--- |
| 🧠 **`dich_truyen_gemini.py`** | Engine dịch thuật AI đa dự án, tự học thuật ngữ, tương tác phản hồi, quét trước Glossary. |
| 🐍 **`syosetu_scraper.py`** | Engine cào raw Python bất đồng bộ đa luồng siêu tốc từ Syosetu. |
| ⚙️ **`build_chapters_js.ps1`** | Quét file `.md`, `.docx`, `.txt`, sắp xếp thứ tự chương và đóng gói vào `chapters.js`. |
| ⚙️ **`export_audio.ps1`** | Chuyển đổi toàn bộ nội dung văn bản thành file âm thanh `.mp3` chất lượng cao. |
