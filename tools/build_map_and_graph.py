import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import os
import re
import json
from pathlib import Path

tools_dir = Path(__file__).resolve().parent
novel_root = tools_dir.parent
projects_dir = novel_root / "projects"
web_dir = novel_root / "web"

def parse_characters(chars_file):
    if not chars_file.exists(): return [], {}
    content = chars_file.read_text(encoding="utf-8")
    nodes = []
    char_id_to_name = {}
    
    sections = re.split(r'\n(?=##\s+\[CHAR-\d+\])', content)

    for sec in sections:
        m = re.search(r'##\s+\[(CHAR-\d+)\]\s+([^\n]+)', sec)
        if not m: continue
        eid = m.group(1).strip()
        name = m.group(2).strip()
        char_id_to_name[eid] = name
        
        role_m = re.search(r'-\s+\*\*thiên_chức:\*\*\s*([^\n]+)', sec)
        role = role_m.group(1).strip() if role_m else "Nhân vật"
        
        desc_m = re.search(r'-\s+\*\*mô_tả:\*\*\s*([^\n]+)', sec)
        desc = desc_m.group(1).strip() if desc_m else ""
        
        origin_m = re.search(r'-\s+\*\*thân_phận:\*\*\s*([^\n]+)', sec)
        origin = origin_m.group(1).strip() if origin_m else ""

        # Xác định Phe Phái thông minh
        faction = "Khác"
        color = "#94a3b8"
        
        if any(k in name for k in ["Momokawa", "Meiko", "Kinako", "Aurelia"]):
            faction = "Nhân vật chính"
            color = "#8b5cf6"
        elif any(k in name for k in ["Tendou", "Kenzaki", "Shimokawa", "Nakai", "Azuma", "Shinohara", "Ueta", "Kurokawa"]):
            faction = "Học Viện Tháp"
            color = "#38bdf8"
        elif any(k in name for k in ["Souma", "Hayama", "Ritsuki", "Rerite", "Sakurai"]):
            faction = "Dũng Giả & Giáo Hội"
            color = "#fbbf24"
        elif any(k in name for k in ["Yokomichi", "Ooyama", "Saitou Masaru", "Zagan"]):
            faction = "Kẻ Thù & Trục Xuất"
            color = "#ef4444"
        elif any(k in name for k in ["Felix", "Beatrice", "Dylan", "Theodore", "Cedric", "Camilla", "Gazel"]):
            faction = "Hoàng Gia & Quý Tộc"
            color = "#ec4899"
        elif "Goma" in name or "Goma" in desc:
            faction = "Vương Quốc Goma"
            color = "#f97316"
        elif "Lớp 2-7" in origin or "Lớp 2-7" in desc:
            faction = "Học Sinh Lớp 2-7"
            color = "#06b6d4"

        clean_role = role.replace("『", "").replace("』", "").split("(")[0].strip()
        nodes.append({
            "id": name,
            "label": name,
            "name_orig": name,
            "eid": eid,
            "faction": faction,
            "color": color,
            "role": clean_role if clean_role else "Nhân vật",
            "description": desc or origin or f"Thành viên {faction}",
            "skills": [role] if role else [],
            "timeline": []
        })
    return nodes, char_id_to_name

def parse_relationships(rel_file, nodes, char_id_to_name):
    if not rel_file.exists(): return []
    content = rel_file.read_text(encoding="utf-8")
    edges = []

    # Pattern A: ### 1. 👥 Momokawa Kotarou ⮂ Futaba Meiko (Mei-chan)
    rel_sections = re.split(r'\n(?=###\s+\d+\.)', content)
    for sec in rel_sections:
        head_m = re.search(r'###\s+\d+\.\s*(?:👥\s*)?([^\n⮂<->→—]+)\s*(?:⮂|<->|->|→|—)\s*([^\n(]+)', sec)
        if not head_m: continue
        u = head_m.group(1).strip()
        v = head_m.group(2).strip()
        
        u_matched = next((n["id"] for n in nodes if u in n["id"] or n["id"] in u), u)
        v_matched = next((n["id"] for n in nodes if v in n["id"] or n["id"] in v), v)

        timeline_lines = re.findall(r'\*\s+\*\*Tập\s+([^:]+):\*\*\s*([^\n➔]+)(?:➔\s*([^\n]+))?', sec)
        if timeline_lines:
            for ep_range, nature, details in timeline_lines:
                nature = nature.strip()
                color = "#10b981"
                if any(w in nature.lower() for w in ["yêu", "hôn thê", "bạn đời", "tình cảm", "gắn bó"]): color = "#ec4899"
                elif any(w in nature.lower() for w in ["kẻ thù", "đối đầu", "căm ghét", "phản bội", "trục xuất"]): color = "#ef4444"
                elif any(w in nature.lower() for w in ["nghi ngờ", "đề phòng", "lợi dụng"]): color = "#f59e0b"
                elif any(w in nature.lower() for w in ["đồng minh", "bạn", "tin tưởng", "trợ thủ", "bảo bọc"]): color = "#10b981"

                edges.append({
                    "from": u_matched,
                    "to": v_matched,
                    "label": nature[:25],
                    "color": color,
                    "nature": f"[{ep_range}] {nature} " + (f"({details.strip()})" if details else "")
                })
        else:
            edges.append({
                "from": u_matched,
                "to": v_matched,
                "label": "Quan hệ đồng đội",
                "color": "#10b981",
                "nature": "Quan hệ cốt truyện"
            })

    # Pattern B: Bảng Ma Trận | Tập 270 | **CHAR-007** | BẠN | **CHAR-005** |
    matrix_rows = re.findall(r'\|\s*Tập\s+([^\s|]+)\s*\|\s*\*\*(CHAR-\d+)\*\*\s*\|\s*([^|]+)\s*\|\s*\*\*(CHAR-\d+)\*\*', content)
    for ep, c1, rel_type, c2 in matrix_rows:
        n1 = char_id_to_name.get(c1.strip(), c1.strip())
        n2 = char_id_to_name.get(c2.strip(), c2.strip())
        rel_type = rel_type.strip()
        
        color = "#10b981"
        if any(w in rel_type.lower() for w in ["yêu", "tình cảm"]): color = "#ec4899"
        elif any(w in rel_type.lower() for w in ["nghi ngờ", "đề phòng"]): color = "#f59e0b"
        elif any(w in rel_type.lower() for w in ["thù", "đối đầu"]): color = "#ef4444"

        edges.append({
            "from": n1,
            "to": n2,
            "label": rel_type,
            "color": color,
            "nature": f"[Tập {ep}] {rel_type}"
        })

    return edges

def parse_locations(loc_file, novel_key):
    if not loc_file.exists():
        if "Chu_Thuat_Su" in novel_key:
            return [
                {"id": "Thị Trấn Di Tích", "name": "Thị Trấn Di Tích", "type": "TOWN", "icon": "🏛️", "color": "#38bdf8", "x": 300, "y": 250, "desc": "Nơi các học sinh hạ trại và khám phá tàn tích."},
                {"id": "Học Viện Tháp", "name": "Học Viện Tháp", "type": "TOWER", "icon": "🗼", "color": "#fbbf24", "x": 600, "y": 200, "desc": "Căn cứ của nhóm học viện do Tendou chỉ huy."},
                {"id": "Hang Động Khởi Đầu", "name": "Hang Động Khởi Đầu", "type": "DUNGEON", "icon": "⛰️", "color": "#a855f7", "x": 150, "y": 400, "desc": "Nơi Kotarou thức tỉnh thiên chức Chú Thuật Sư."},
                {"id": "Vương Quốc Goma", "name": "Vương Quốc Goma", "type": "KINGDOM", "icon": "🏰", "color": "#ef4444", "x": 750, "y": 450, "desc": "Vương quốc của chủng tộc Goma."}
            ]
        elif "Ác Nữ" in novel_key:
            return [
                {"id": "Học Viện Hoàng Gia", "name": "Học Viện Hoàng Gia & Phòng Hội Học Sinh", "type": "ACADEMY", "icon": "🏫", "color": "#38bdf8", "x": 200, "y": 200, "desc": "Nơi diễn ra vụ ngã cầu thang định mệnh."},
                {"id": "Biệt Thự Suối Nước Nóng", "name": "Biệt Thự Suối Nước Nóng Rosenberg", "type": "MANSION", "icon": "♨️", "color": "#ec4899", "x": 480, "y": 180, "desc": "Nơi Aurelia lui về dưỡng thương sau khi hủy hôn ước."},
                {"id": "Khu Phố Ẩm Thực", "name": "Khu Phố Ẩm Thực Lãnh Địa Rosenberg", "type": "TOWN", "icon": "🍷", "color": "#10b981", "x": 420, "y": 380, "desc": "Nơi Aurelia thưởng thức ẩm thực và bánh kẹo."},
                {"id": "Lâu Đài Vương Đô", "name": "Lâu Đài Vương Đô Grandier", "type": "CASTLE", "icon": "👑", "color": "#f59e0b", "x": 700, "y": 220, "desc": "Nơi ở của Hoàng tộc và Tam Công Chúa Beatrice."}
            ]
        else:
            return [
                {"id": "Thị Trấn Khởi Đầu", "name": "Thị Trấn Khởi Đầu", "type": "TOWN", "icon": "🏡", "color": "#38bdf8", "x": 300, "y": 300, "desc": "Khu vực sinh sống của nhân vật chính."}
            ]

    content = loc_file.read_text(encoding="utf-8")
    locs = []
    sections = re.split(r'\n(?=##\s+)', content)
    default_coords = [(200, 200), (450, 200), (300, 400), (650, 350), (150, 450), (500, 500)]
    idx = 0

    for sec in sections:
        m = re.search(r'##\s+(?:\[LOC-\d+\]\s+)?([^\n]+)', sec)
        if not m: continue
        name = m.group(1).strip()
        desc_m = re.search(r'(?:Mô tả|Đặc điểm|Chi tiết):\s*([^\n]+)', sec, re.IGNORECASE)
        desc = desc_m.group(1).strip() if desc_m else ""
        
        cx, cy = default_coords[idx % len(default_coords)]
        idx += 1

        locs.append({
            "id": name,
            "name": name,
            "type": "LOCATION",
            "icon": "📍",
            "color": "#38bdf8",
            "x": cx,
            "y": cy,
            "desc": desc
        })
    return locs

def build_all():
    novel_dirs = [d for d in projects_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
    all_graphs = {}
    all_maps = {}

    for d in novel_dirs:
        key = d.name
        title = key.replace("_", " ")
        glossary_dir = d / "glossary"
        
        nodes, char_id_to_name = parse_characters(glossary_dir / "characters.md")
        edges = parse_relationships(glossary_dir / "relationship_timeline.md", nodes, char_id_to_name)
        factions = list(dict.fromkeys([n["faction"] for n in nodes])) if nodes else ["Nhân vật chính", "Khác"]
        
        all_graphs[key] = {
            "novel_key": key,
            "novel_title": title,
            "nodes": nodes,
            "edges": edges,
            "factions": factions
        }

        locs = parse_locations(glossary_dir / "locations.md", key)
        all_maps[key] = {
            "novel_key": key,
            "novel_title": title,
            "locations": locs
        }

    graph_js = f"window.GRAPH_DATA = {json.dumps(all_graphs, ensure_ascii=False, indent=2)};\n"
    map_js = f"window.MAP_DATA = {json.dumps(all_maps, ensure_ascii=False, indent=2)};\n"

    (web_dir / "graph_data.js").write_text(graph_js, encoding="utf-8")
    (web_dir / "map_data.js").write_text(map_js, encoding="utf-8")
    print(f"🎉 Đã cập nhật thành công graph_data.js và map_data.js cho {len(novel_dirs)} bộ truyện!")

if __name__ == "__main__":
    build_all()
