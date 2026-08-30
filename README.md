# Dự Án Dịch Truyện & Đọc Audio Light Novel
**Tác phẩm:** Chú thuật sư không thể trở thành Dũng Giả (呪術師は勇者になれない)

---

## 📂 Cấu Trúc Thư Mục Dự Án (Đã Gói Gọn & Ngăn Nắp)

```
d:\Novel\
├── 📁 Chu_Thuat_Su_Dung_Gia/       ➔ NƠI LƯU TRỮ TOÀN BỘ DỮ LIỆU TRUYỆN
│   ├── 📁 raw/                     ➔ Các file/chương thô chưa dịch (.txt, .md)
│   ├── 📁 translated/              ➔ Các bản dịch hoàn chỉnh (.md)
│   │   └── chuong_152_ruong_kho_bau_dau_tien.md
│   ├── 📁 audio/                   ➔ Các file âm thanh MP3 đã xuất (.mp3)
│   │   └── chuong_152_ruong_kho_bau_dau_tien.mp3
│   ├── 📁 glossary/               ➔ Bảng nhân vật & thuật ngữ
│   │   ├── characters.md
│   │   └── terms.md
│   └── style_guide.md              ➔ Quy tắc văn phong & định dạng dịch thuật
│
├── 📁 tools/                       ➔ NƠI CHỨA ỨNG DỤNG WEB & CÔNG CỤ TỰ ĐỘNG
│   ├── Doc_Truyen.html             ➔ Ứng dụng Web Đọc & Nghe Truyện Pro
│   ├── chapters.js                 ➔ Thư viện lưu các chương đã dịch
│   ├── chuyen_audio.bat            ➔ File kéo thả tạo MP3
│   └── export_audio.ps1            ➔ Script xử lý Audio MP3
│
└── README.md                       ➔ Hướng dẫn tổng quan
```

---

## 🚀 Hướng Dẫn Sử Dụng Nhanh

1. **Đọc & Nghe truyện trên Web App:**
   - Mở file [`tools/Doc_Truyen.html`](file:///d:/Novel/tools/Doc_Truyen.html) bằng Microsoft Edge hoặc Chrome.
   - Thưởng thức trọn vẹn tính năng đọc truyện, chuyển chương, chọn giọng đọc Bing (Hoài Mỹ, Nam Minh), Chị Google, TikTok TTS.

2. **Tạo file Audio MP3 offline:**
   - Kéo thả bất kỳ file `.md` nào trong [`Chu_Thuat_Su_Dung_Gia/translated/`](file:///d:/Novel/Chu_Thuat_Su_Dung_Gia/translated/) đè lên [`tools/chuyen_audio.bat`](file:///d:/Novel/tools/chuyen_audio.bat).
   - File `.mp3` sẽ được lưu tự động vào [`Chu_Thuat_Su_Dung_Gia/audio/`](file:///d:/Novel/Chu_Thuat_Su_Dung_Gia/audio/).
