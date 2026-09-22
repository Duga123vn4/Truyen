# -*- coding: utf-8 -*-
"""
Module Bộ Điều Phối Scraper Hợp Nhất (Unified Scraper Router Engine):
- Tự động nhận diện URL / Mã nguồn từ người dùng (Syosetu vs Kakuyomu)
- Khởi tạo đối tượng Scraper tương ứng
"""
import re
from typing import Tuple, Union, Optional
from tools.src.services.syosetu_scraper import SyosetuNovel, extract_novel_code as extract_syosetu_code
from tools.src.services.kakuyomu_scraper import KakuyomuNovel, extract_kakuyomu_code

def detect_novel_source(input_str: str) -> Tuple[str, str]:
    """
    Phân tích chuỗi đầu vào để xác định nguồn (syosetu / kakuyomu) và trích xuất mã.
    Returns:
        (source_type, code) trong đó source_type là 'syosetu' hoặc 'kakuyomu'
    """
    input_str = input_str.strip()

    # Kakuyomu URL hoặc ID (ID Kakuyomu thường là dãy số dài 10-20 chữ số)
    if 'kakuyomu.jp' in input_str.lower():
        return 'kakuyomu', extract_kakuyomu_code(input_str)

    # Nếu chỉ gồm toàn chữ số dài (ví dụ: 1177354054884234676) -> Kakuyomu
    if re.match(r'^\d{10,}$', input_str):
        return 'kakuyomu', input_str

    # Syosetu URL hoặc NCODE (ví dụ: n1132dk, https://ncode.syosetu.com/n1132dk/)
    return 'syosetu', extract_syosetu_code(input_str)

def get_novel_scraper(input_str: str) -> Tuple[str, str, Union[SyosetuNovel, KakuyomuNovel]]:
    """
    Trả về (source_type, code, scraper_instance) từ chuỗi URL/mã nhập vào.
    """
    source_type, code = detect_novel_source(input_str)
    if source_type == 'kakuyomu':
        return source_type, code, KakuyomuNovel(code)
    else:
        return source_type, code, SyosetuNovel(code)
